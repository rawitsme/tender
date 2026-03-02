"""NIC eProcurement state portal Selenium connector.

Handles CAPTCHA-protected state tender portals (UP, Maharashtra, Uttarakhand, Haryana, MP).
All share similar NIC eProcurement structure.
"""

import base64
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from backend.ingestion.base_connector import BaseConnector, RawTender
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

logger = logging.getLogger(__name__)

STATE_PORTALS: Dict[str, dict] = {
    "up": {
        "base_url": "https://etender.up.nic.in",
        "state": "Uttar Pradesh",
        "active_page": "/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
    },
    "maharashtra": {
        "base_url": "https://mahatenders.gov.in",
        "state": "Maharashtra",
        "active_page": "/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
    },
    "uttarakhand": {
        "base_url": "https://uktenders.gov.in",
        "state": "Uttarakhand",
        "active_page": "/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
    },
    "haryana": {
        "base_url": "https://etenders.hry.nic.in",
        "state": "Haryana",
        "active_page": "/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
    },
    "mp": {
        "base_url": "https://mptenders.gov.in",
        "state": "Madhya Pradesh",
        "active_page": "/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
    },
}


def _get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,1024")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def _get_captcha_bytes(driver) -> bytes | None:
    try:
        captcha_el = driver.find_element(By.ID, "captchaImage")
        src = captcha_el.get_attribute("src")
        if src and src.startswith("data:"):
            b64 = src.split(",", 1)[1].replace("%0A", "").replace("\n", "").replace(" ", "")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            return base64.b64decode(b64)
        return captcha_el.screenshot_as_png
    except Exception as e:
        logger.warning(f"Failed to get CAPTCHA: {e}")
        return None


def _solve_captcha(driver, max_attempts=5) -> bool:
    for attempt in range(max_attempts):
        captcha_bytes = _get_captcha_bytes(driver)
        if not captcha_bytes:
            driver.refresh()
            time.sleep(2)
            continue

        solution = solve_captcha_image(captcha_bytes)
        if not solution:
            try:
                driver.find_element(By.NAME, "captcha").click()
                time.sleep(1)
            except Exception:
                driver.refresh()
                time.sleep(2)
            continue

        logger.info(f"CAPTCHA attempt {attempt+1}: trying '{solution}'")
        captcha_input = driver.find_element(By.NAME, "captchaText")
        captcha_input.clear()
        captcha_input.send_keys(solution)

        try:
            btn = driver.find_element(By.NAME, "Search")
        except Exception:
            btn = driver.find_element(By.NAME, "Submit")
        btn.click()
        time.sleep(3)

        page = driver.page_source
        if "e-Published Date" in page or "Closing Date" in page or "Tender Title" in page:
            logger.info(f"CAPTCHA solved on attempt {attempt+1}")
            return True

    return False


def _parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ["%d-%b-%Y %I:%M %p", "%d-%b-%Y %H:%M", "%d/%m/%Y %H:%M", "%d-%m-%Y", "%d-%b-%Y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


class NICSeleniumConnector(BaseConnector):
    """Generic NIC state portal connector."""

    def __init__(self, state_key: str):
        super().__init__()
        if state_key not in STATE_PORTALS:
            raise ValueError(f"Unknown state: {state_key}. Options: {list(STATE_PORTALS.keys())}")
        self.state_key = state_key
        self.config = STATE_PORTALS[state_key]
        self.source_name = state_key

    async def fetch_tenders(self, since: Optional[datetime] = None, page: int = 1) -> List[RawTender]:
        tenders = []
        driver = None

        try:
            driver = _get_driver()
            url = self.config["base_url"] + self.config["active_page"]
            driver.get(url)
            time.sleep(3)

            if not _solve_captcha(driver):
                logger.error(f"{self.state_key}: Failed to solve CAPTCHA")
                return []

            tenders = self._parse_table(driver)
            logger.info(f"{self.state_key}: Parsed {len(tenders)} tenders")

            # Pagination
            try:
                page_count = 1
                while page_count < 3:
                    next_links = driver.find_elements(By.LINK_TEXT, "Next")
                    if not next_links:
                        break
                    next_links[0].click()
                    time.sleep(3)
                    batch = self._parse_table(driver)
                    tenders.extend(batch)
                    page_count += 1
            except Exception as e:
                logger.debug(f"{self.state_key} pagination: {e}")

        except Exception as e:
            logger.error(f"{self.state_key} Selenium failed: {e}")
        finally:
            if driver:
                driver.quit()

        return tenders

    def _parse_table(self, driver) -> List[RawTender]:
        tenders = []
        state = self.config["state"]

        try:
            tables = driver.find_elements(By.TAG_NAME, "table")
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) < 3:
                    continue

                header = rows[0]
                headers = [h.text.strip().lower() for h in header.find_elements(By.TAG_NAME, "th")]
                if not headers:
                    headers = [h.text.strip().lower() for h in header.find_elements(By.TAG_NAME, "td")]
                if not any("tender" in h or "closing" in h or "title" in h for h in headers):
                    continue

                for row in rows[1:]:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) < 4:
                            continue

                        texts = [c.text.strip() for c in cells]

                        # Get detail link
                        links = row.find_elements(By.TAG_NAME, "a")
                        detail_url = None
                        title = None
                        for link in links:
                            href = link.get_attribute("href") or ""
                            lt = link.text.strip()
                            if lt and len(lt) > 10:
                                title = lt
                                detail_url = href
                                break

                        if not title:
                            title = max(texts, key=len) if texts else "Unknown"

                        tender_id = None
                        for ct in texts:
                            if re.match(r"^\d{4}_[A-Z]+_\d+", ct) or re.match(r"^[A-Z]{2,}/", ct):
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
                            if len(ct) > 15 and ct != title and not _parse_date(ct):
                                org = ct
                                break

                        sid = tender_id or f"{self.state_key}_{hash(title) & 0xFFFFFFFF}"

                        tenders.append(RawTender(
                            source_id=sid,
                            title=title[:2000],
                            source_url=detail_url or self.config["base_url"],
                            tender_id=tender_id,
                            state=state,
                            organization=org,
                            publication_date=pub_date,
                            bid_close_date=close_date,
                            raw_text=" | ".join(texts)[:10000],
                        ))
                    except Exception as e:
                        logger.debug(f"{self.state_key} row error: {e}")

                if tenders:
                    break

        except Exception as e:
            logger.error(f"{self.state_key} parse error: {e}")

        return tenders

    async def fetch_tender_detail(self, source_id: str) -> Optional[RawTender]:
        return None

    async def close(self):
        pass
