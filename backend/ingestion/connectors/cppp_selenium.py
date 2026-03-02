"""CPPP (Central Public Procurement Portal) Selenium connector with 2Captcha.

Uses headless Chrome + 2Captcha (or Tesseract fallback) to solve CAPTCHAs.
"""

import base64
import io
import logging
import re
import time
from datetime import datetime
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from backend.ingestion.base_connector import BaseConnector, RawTender
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

logger = logging.getLogger(__name__)

BASE_URL = "https://eprocure.gov.in/eprocure/app"


def _get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,1024")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def _get_captcha_bytes(driver) -> Optional[bytes]:
    """Extract CAPTCHA image bytes from the page."""
    try:
        captcha_el = driver.find_element(By.ID, "captchaImage")
        src = captcha_el.get_attribute("src")

        if src and src.startswith("data:"):
            b64 = src.split(",", 1)[1].replace("%0A", "").replace("\n", "").replace(" ", "")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            return base64.b64decode(b64)
        else:
            # Screenshot fallback
            return captcha_el.screenshot_as_png
    except Exception as e:
        logger.warning(f"Failed to get CAPTCHA image: {e}")
        return None


def _solve_and_submit(driver, max_attempts=5) -> bool:
    """Solve CAPTCHA and submit. Returns True if we got tender data."""
    for attempt in range(max_attempts):
        captcha_bytes = _get_captcha_bytes(driver)
        if not captcha_bytes:
            driver.refresh()
            time.sleep(2)
            continue

        solution = solve_captcha_image(captcha_bytes)
        if not solution:
            logger.debug(f"CAPTCHA attempt {attempt+1}: solver returned nothing, refreshing")
            try:
                driver.find_element(By.NAME, "captcha").click()  # Refresh captcha
                time.sleep(1)
            except Exception:
                driver.refresh()
                time.sleep(2)
            continue

        logger.info(f"CAPTCHA attempt {attempt+1}: trying '{solution}'")

        # Enter and submit
        captcha_input = driver.find_element(By.NAME, "captchaText")
        captcha_input.clear()
        captcha_input.send_keys(solution)

        try:
            btn = driver.find_element(By.NAME, "Search")
        except Exception:
            btn = driver.find_element(By.NAME, "Submit")
        btn.click()
        time.sleep(3)

        # Check if we got results
        page = driver.page_source
        if "e-Published Date" in page or "Closing Date" in page or "Tender Title" in page:
            logger.info(f"CAPTCHA solved on attempt {attempt+1}")
            return True

        logger.debug(f"CAPTCHA attempt {attempt+1}: rejected")

    return False


def _parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ["%d-%b-%Y %I:%M %p", "%d-%b-%Y %H:%M", "%d/%m/%Y %H:%M",
                "%d-%m-%Y", "%d-%b-%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


class CPPPSeleniumConnector(BaseConnector):
    source_name = "cppp"

    async def fetch_tenders(self, since: Optional[datetime] = None, page: int = 1) -> List[RawTender]:
        tenders = []
        driver = None

        try:
            driver = _get_driver()
            driver.get(f"{BASE_URL}?page=FrontEndLatestActiveTenders&service=page")
            time.sleep(3)

            if not _solve_and_submit(driver):
                logger.error("CPPP: Failed to solve CAPTCHA")
                return []

            tenders = self._parse_table(driver)
            logger.info(f"CPPP: Parsed {len(tenders)} tenders")

            # Pagination
            page_count = 1
            while page_count < 5:
                try:
                    next_links = driver.find_elements(By.LINK_TEXT, "Next")
                    if not next_links:
                        break
                    next_links[0].click()
                    time.sleep(3)
                    batch = self._parse_table(driver)
                    tenders.extend(batch)
                    page_count += 1
                except Exception:
                    break

        except Exception as e:
            logger.error(f"CPPP fetch failed: {e}")
        finally:
            if driver:
                driver.quit()

        return tenders

    def _parse_table(self, driver) -> List[RawTender]:
        tenders = []
        try:
            tables = driver.find_elements(By.TAG_NAME, "table")
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) < 3:
                    continue

                headers = [h.text.strip().lower() for h in rows[0].find_elements(By.TAG_NAME, "th")]
                if not any("tender" in h or "closing" in h or "published" in h for h in headers):
                    continue

                logger.info(f"Found tender table: {len(rows)-1} rows")

                for row in rows[1:]:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) < 4:
                            continue

                        texts = [c.text.strip() for c in cells]
                        links = row.find_elements(By.TAG_NAME, "a")
                        detail_url = title = None
                        for link in links:
                            lt = link.text.strip()
                            if lt and len(lt) > 10:
                                title = lt
                                detail_url = link.get_attribute("href") or ""
                                break

                        if not title:
                            title = max(texts, key=len) if texts else "Unknown"

                        tender_id = None
                        for ct in texts:
                            if re.match(r"^\d{4}_[A-Z]+_\d+", ct):
                                tender_id = ct
                                break

                        pub_date = close_date = None
                        for ct in texts:
                            d = _parse_date(ct)
                            if d:
                                if not pub_date:
                                    pub_date = d
                                else:
                                    close_date = d

                        org = None
                        for ct in texts:
                            if len(ct) > 15 and ct != title and not _parse_date(ct) and ct != tender_id:
                                org = ct
                                break

                        sid = tender_id or f"cppp_{hash(title) & 0xFFFFFFFF}"
                        tenders.append(RawTender(
                            source_id=sid, title=title[:2000],
                            source_url=detail_url or BASE_URL,
                            tender_id=tender_id, state="Central",
                            organization=org,
                            publication_date=pub_date, bid_close_date=close_date,
                            raw_text=" | ".join(texts)[:10000],
                        ))
                    except Exception as e:
                        logger.debug(f"Row error: {e}")

                if tenders:
                    break
        except Exception as e:
            logger.error(f"Table parse error: {e}")
        return tenders

    async def fetch_tender_detail(self, source_id: str) -> Optional[RawTender]:
        return None

    async def close(self):
        pass
