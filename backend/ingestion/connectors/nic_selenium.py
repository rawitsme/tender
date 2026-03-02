"""NIC eProcurement state portal Selenium connector.

Handles CAPTCHA-protected state tender portals (UP, Maharashtra, Uttarakhand, Haryana, MP).
All share similar NIC eProcurement structure.
"""

import logging
import re
import tempfile
import time
from datetime import datetime
from typing import Dict, List, Optional

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from backend.ingestion.base_connector import BaseConnector, RawTender

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


def _solve_captcha(driver, max_attempts=5) -> bool:
    for attempt in range(max_attempts):
        try:
            captcha_el = driver.find_element(By.ID, "captchaImage")
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                captcha_el.screenshot(f.name)
                img = Image.open(f.name)

            img = img.convert("L")
            img = ImageOps.invert(img)
            img = img.point(lambda x: 0 if x < 140 else 255)
            img = img.filter(ImageFilter.MedianFilter(3))
            img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)

            text = pytesseract.image_to_string(
                img, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
            ).strip()

            if len(text) < 3:
                driver.refresh()
                time.sleep(2)
                continue

            captcha_input = driver.find_element(By.NAME, "captchaText")
            captcha_input.clear()
            captcha_input.send_keys(text)

            try:
                search_btn = driver.find_element(By.NAME, "Search")
            except Exception:
                search_btn = driver.find_element(By.NAME, "Submit")
            search_btn.click()
            time.sleep(3)

            page_src = driver.page_source.lower()
            if "invalid" in page_src and "captcha" in page_src:
                continue

            rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
            if len(rows) > 10:
                return True

        except Exception as e:
            logger.debug(f"CAPTCHA attempt {attempt+1}: {e}")
            driver.refresh()
            time.sleep(2)

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
