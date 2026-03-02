"""NIC eProcurement state portal Selenium connector.

Handles CAPTCHA-protected state tender portals (UP, Maharashtra, Uttarakhand, Haryana, MP).
All share similar NIC eProcurement structure with id='table' class='list_table'.
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


def _get_captcha_bytes(driver) -> Optional[bytes]:
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
        # Reject false positives — "Invalid Captcha" means it failed
        if "Invalid Captcha" in page or "Incorrect Captcha" in page:
            logger.debug(f"CAPTCHA attempt {attempt+1}: rejected by server")
            continue
        # Check for actual tender results
        if "Organisation Chain" in page or "Total records:" in page or "e-Published Date" in page:
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
                logger.error(f"{self.state_key}: Failed to solve CAPTCHA after all attempts")
                return []

            tenders = self._parse_tender_table(driver)
            logger.info(f"{self.state_key}: Parsed {len(tenders)} tenders from page 1")

            # Pagination — click Next
            page_count = 1
            while page_count < 5:
                try:
                    next_links = driver.find_elements(By.LINK_TEXT, "Next >")
                    if not next_links:
                        next_links = driver.find_elements(By.LINK_TEXT, "Next")
                    if not next_links:
                        break
                    next_links[0].click()
                    time.sleep(3)
                    batch = self._parse_tender_table(driver)
                    if not batch:
                        break
                    tenders.extend(batch)
                    page_count += 1
                    logger.info(f"{self.state_key}: Page {page_count+1}: +{len(batch)} tenders")
                except Exception as e:
                    logger.debug(f"{self.state_key} pagination: {e}")
                    break

        except Exception as e:
            logger.error(f"{self.state_key} Selenium failed: {e}")
        finally:
            if driver:
                driver.quit()

        return tenders

    def _parse_tender_table(self, driver) -> List[RawTender]:
        """Parse the actual tender data table (id='table', class='list_table' with 7 cols)."""
        tenders = []
        state = self.config["state"]
        base_url = self.config["base_url"]

        try:
            # Target the specific tender results table
            # NIC portals use id="table" class="list_table" for the results
            target_table = None
            
            # Try by ID first
            try:
                target_table = driver.find_element(By.ID, "table")
            except Exception:
                pass
            
            # Fallback: find list_table with 7-column rows
            if not target_table:
                tables = driver.find_elements(By.CSS_SELECTOR, "table.list_table")
                for t in tables:
                    rows = t.find_elements(By.TAG_NAME, "tr")
                    if rows:
                        cells = rows[0].find_elements(By.TAG_NAME, "td")
                        if len(cells) == 7:
                            target_table = t
                            break
            
            if not target_table:
                logger.warning(f"{self.state_key}: No tender results table found")
                return []

            rows = target_table.find_elements(By.TAG_NAME, "tr")
            logger.info(f"{self.state_key}: Found results table with {len(rows)} rows")

            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) != 7:
                        continue

                    sno = cells[0].text.strip().rstrip(".")
                    if not sno or not sno.replace(".", "").isdigit():
                        continue  # Skip header/footer rows

                    pub_date_str = cells[1].text.strip()
                    close_date_str = cells[2].text.strip()
                    open_date_str = cells[3].text.strip()
                    title_cell = cells[4]
                    org_text = cells[5].text.strip()
                    value_text = cells[6].text.strip()

                    # Extract title and link
                    title_text = title_cell.text.strip()
                    links = title_cell.find_elements(By.TAG_NAME, "a")
                    detail_url = ""
                    if links:
                        detail_url = links[0].get_attribute("href") or ""

                    # Extract tender ID from title text: [Title] [RefNo][TenderID]
                    tender_id = ""
                    id_match = re.search(r'\[(\d{4}_[A-Z]+_\d+_\d+)\]', title_text)
                    if id_match:
                        tender_id = id_match.group(1)
                    
                    # Clean title — extract just the first [...] part
                    title_match = re.match(r'\[(.+?)\]', title_text)
                    title = title_match.group(1) if title_match else title_text
                    title = title[:2000]

                    pub_date = _parse_date(pub_date_str)
                    close_date = _parse_date(close_date_str)

                    source_id = tender_id or f"{self.state_key}_{hash(title + pub_date_str) & 0xFFFFFFFF}"

                    tenders.append(RawTender(
                        source_id=source_id,
                        title=title,
                        source_url=detail_url or base_url,
                        tender_id=tender_id,
                        state=state,
                        organization=org_text[:1000],
                        publication_date=pub_date,
                        bid_close_date=close_date,
                        raw_text=f"{title_text} | {org_text} | {value_text}"[:10000],
                    ))
                except Exception as e:
                    logger.debug(f"{self.state_key} row error: {e}")

        except Exception as e:
            logger.error(f"{self.state_key} parse error: {e}")

        return tenders

    async def fetch_tender_detail(self, source_id: str) -> Optional[RawTender]:
        return None

    async def close(self):
        pass
