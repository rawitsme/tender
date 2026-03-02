"""CPPP (Central Public Procurement Portal) Selenium connector.

Uses headless Chrome + Tesseract OCR to solve CAPTCHAs and scrape tender listings.
NIC CAPTCHAs are tricky — we try multiple OCR strategies.
"""

import io
import base64
import logging
import re
import time
from datetime import datetime
from typing import List, Optional

import pytesseract
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from backend.ingestion.base_connector import BaseConnector, RawTender

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


def _ocr_captcha_image(img: Image.Image) -> List[str]:
    """Try multiple OCR preprocessing strategies and return candidate texts."""
    candidates = []

    for threshold in [100, 120, 140, 160]:
        for invert in [True, False]:
            try:
                g = img.convert("L")
                if invert:
                    g = ImageOps.invert(g)
                g = g.point(lambda x, t=threshold: 0 if x < t else 255)
                g = g.filter(ImageFilter.MedianFilter(3))
                g = g.resize((g.width * 3, g.height * 3), Image.LANCZOS)

                text = pytesseract.image_to_string(
                    g, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
                ).strip().replace(" ", "")

                if 4 <= len(text) <= 10:
                    candidates.append(text)
            except Exception:
                pass

    # Also try with contrast enhancement
    try:
        enhanced = ImageEnhance.Contrast(img.convert("L")).enhance(2.0)
        enhanced = enhanced.point(lambda x: 0 if x < 128 else 255)
        enhanced = enhanced.resize((enhanced.width * 3, enhanced.height * 3), Image.LANCZOS)
        text = pytesseract.image_to_string(
            enhanced, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        ).strip().replace(" ", "")
        if 4 <= len(text) <= 10:
            candidates.append(text)
    except Exception:
        pass

    return list(dict.fromkeys(candidates))  # deduplicate preserving order


def _solve_captcha(driver, max_attempts=15):
    """Try to OCR-solve the CAPTCHA with multiple strategies. Returns True if successful."""
    for attempt in range(max_attempts):
        try:
            # Get captcha from base64 src (more reliable than screenshot)
            captcha_el = driver.find_element(By.ID, "captchaImage")
            src = captcha_el.get_attribute("src")

            if src and src.startswith("data:"):
                b64 = src.split(",", 1)[1]
                # Fix URL-safe base64 and padding
                b64 = b64.replace("%0A", "").replace("\n", "").replace(" ", "")
                b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
                img = Image.open(io.BytesIO(base64.b64decode(b64)))
            else:
                # Fallback to screenshot
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    captcha_el.screenshot(f.name)
                    img = Image.open(f.name)

            candidates = _ocr_captcha_image(img)

            if not candidates:
                logger.debug(f"CAPTCHA attempt {attempt+1}: no valid candidates, refreshing")
                # Click refresh button if available
                try:
                    driver.find_element(By.NAME, "captcha").click()
                    time.sleep(1)
                except Exception:
                    driver.refresh()
                    time.sleep(2)
                continue

            # Try the best candidate
            text = candidates[0]
            logger.info(f"CAPTCHA attempt {attempt+1}: trying '{text}' (of {len(candidates)} candidates)")

            captcha_input = driver.find_element(By.NAME, "captchaText")
            captcha_input.clear()
            captcha_input.send_keys(text)

            # Submit
            try:
                btn = driver.find_element(By.NAME, "Search")
            except Exception:
                btn = driver.find_element(By.NAME, "Submit")
            btn.click()
            time.sleep(3)

            # Check result
            page_src = driver.page_source

            # Look for actual tender data table markers
            if "e-Published Date" in page_src or "Closing Date" in page_src or "Tender Title" in page_src:
                logger.info(f"CAPTCHA solved on attempt {attempt+1}!")
                return True

            # Wrong CAPTCHA — just keep trying (page reloads with new CAPTCHA)
            logger.debug(f"CAPTCHA attempt {attempt+1}: rejected")

        except Exception as e:
            logger.warning(f"CAPTCHA attempt {attempt+1} error: {e}")
            try:
                driver.refresh()
                time.sleep(2)
            except Exception:
                pass

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

            if not _solve_captcha(driver):
                logger.error("CPPP: Failed to solve CAPTCHA after max attempts")
                return []

            tenders = self._parse_tender_table(driver)
            logger.info(f"CPPP: Parsed {len(tenders)} tenders from page")

            # Pagination
            page_count = 1
            while page_count < 5:
                try:
                    next_links = driver.find_elements(By.LINK_TEXT, "Next")
                    if not next_links:
                        break
                    next_links[0].click()
                    time.sleep(3)
                    batch = self._parse_tender_table(driver)
                    tenders.extend(batch)
                    page_count += 1
                    logger.info(f"CPPP: Page {page_count}, total {len(tenders)} tenders")
                except Exception:
                    break

        except Exception as e:
            logger.error(f"CPPP Selenium fetch failed: {e}")
        finally:
            if driver:
                driver.quit()

        return tenders

    def _parse_tender_table(self, driver) -> List[RawTender]:
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

                logger.info(f"Found tender table: {len(rows)-1} data rows, headers={headers[:6]}")

                for row in rows[1:]:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) < 4:
                            continue

                        texts = [c.text.strip() for c in cells]

                        # Get links
                        links = row.find_elements(By.TAG_NAME, "a")
                        detail_url = title = None
                        for link in links:
                            lt = link.text.strip()
                            href = link.get_attribute("href") or ""
                            if lt and len(lt) > 10:
                                title = lt
                                detail_url = href
                                break

                        if not title:
                            title = max(texts, key=len) if texts else "Unknown Tender"

                        # Tender ID
                        tender_id = None
                        for ct in texts:
                            if re.match(r"^\d{4}_[A-Z]+_\d+", ct):
                                tender_id = ct
                                break

                        # Dates
                        pub_date = close_date = None
                        for ct in texts:
                            d = _parse_date(ct)
                            if d:
                                if not pub_date:
                                    pub_date = d
                                else:
                                    close_date = d

                        # Org
                        org = None
                        for ct in texts:
                            if len(ct) > 15 and ct != title and not _parse_date(ct) and ct != tender_id:
                                org = ct
                                break

                        sid = tender_id or f"cppp_{hash(title) & 0xFFFFFFFF}"

                        tenders.append(RawTender(
                            source_id=sid,
                            title=title[:2000],
                            source_url=detail_url or f"{BASE_URL}?page=FrontEndLatestActiveTenders",
                            tender_id=tender_id,
                            state="Central",
                            organization=org,
                            publication_date=pub_date,
                            bid_close_date=close_date,
                            raw_text=" | ".join(texts)[:10000],
                        ))
                    except Exception as e:
                        logger.debug(f"CPPP row error: {e}")

                if tenders:
                    break

        except Exception as e:
            logger.error(f"CPPP table parse error: {e}")

        return tenders

    async def fetch_tender_detail(self, source_id: str) -> Optional[RawTender]:
        return None

    async def close(self):
        pass
