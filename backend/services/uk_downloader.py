"""
Uttarakhand (NIC eProcurement) Tender Document Downloader.

Proven workflow:
1. Navigate to active tenders, solve CAPTCHA
2. Find tender by ID in listing
3. Click "Download as zip" → CAPTCHA page
4. Solve CAPTCHA → session gets authorized
5. Click "Download as zip" AGAIN → file downloads

Works for all NIC eProcurement portals (UK, UP, Maharashtra, Haryana, MP).
"""

import base64
import json
import logging
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

logger = logging.getLogger(__name__)

# NIC portal configs
NIC_PORTALS = {
    "uttarakhand": {"base": "https://uktenders.gov.in", "state": "Uttarakhand"},
    "up": {"base": "https://etender.up.nic.in", "state": "Uttar Pradesh"},
    "maharashtra": {"base": "https://mahatenders.gov.in", "state": "Maharashtra"},
    "haryana": {"base": "https://etenders.hry.nic.in", "state": "Haryana"},
    "mp": {"base": "https://mptenders.gov.in", "state": "Madhya Pradesh"},
}

STORAGE_BASE = Path("storage/documents/tender_downloads")


def _make_driver(download_dir: str) -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1024")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    opts.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
        "behavior": "allow", "downloadPath": download_dir, "eventsEnabled": True
    })
    return driver


def _get_captcha_bytes(driver) -> Optional[bytes]:
    try:
        el = driver.find_element(By.ID, "captchaImage")
        src = el.get_attribute("src")
        if src and src.startswith("data:"):
            b64 = src.split(",", 1)[1].replace("%0A", "").replace("\n", "").replace(" ", "")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            return base64.b64decode(b64)
        return el.screenshot_as_png
    except:
        return None


def _solve_captcha(driver, btn_name="Search", max_tries=5) -> bool:
    for i in range(max_tries):
        cb = _get_captcha_bytes(driver)
        if not cb:
            try:
                driver.find_element(By.ID, "captcha").click()
                time.sleep(2)
            except:
                driver.refresh()
                time.sleep(2)
            continue
        sol = solve_captcha_image(cb)
        if not sol:
            continue
        logger.info(f"CAPTCHA attempt {i + 1}: '{sol}'")
        driver.find_element(By.NAME, "captchaText").clear()
        driver.find_element(By.NAME, "captchaText").send_keys(sol)
        for name in [btn_name, "Search", "Submit"]:
            try:
                driver.find_element(By.NAME, name).click()
                break
            except:
                pass
        time.sleep(2)
        # Dismiss JS alert if present
        try:
            alert = driver.switch_to.alert
            logger.info(f"CAPTCHA rejected (alert): {alert.text}")
            alert.accept()
            time.sleep(1)
            continue
        except:
            pass
        ps = driver.page_source
        if "Invalid Captcha" in ps:
            continue
        return True
    return False


def _find_tender(driver, tender_id: str, max_pages=80):
    """Find tender in listing table. First try Tender ID search, then paginate."""
    # Strategy 1: Use the portal's Tender ID search box (much faster)
    try:
        tid_input = None
        for name in ["TenderId", "tenderId", "tender_id"]:
            elems = driver.find_elements(By.NAME, name)
            if elems:
                tid_input = elems[0]
                break
        if tid_input:
            logger.info(f"Using Tender ID search for: {tender_id}")
            tid_input.clear()
            tid_input.send_keys(tender_id)
            for btn_name in ["Search", "search", "Go", "Submit"]:
                try:
                    driver.find_element(By.NAME, btn_name).click()
                    break
                except:
                    pass
            time.sleep(4)
            try:
                driver.switch_to.alert.accept()
                time.sleep(1)
            except:
                pass
            logger.info("Tender ID search submitted")
    except Exception as e:
        logger.warning(f"Tender ID search failed: {e}")

    # Now look for the tender in results (search or first page)
    for page in range(1, max_pages + 1):
        try:
            table = driver.find_element(By.ID, "table")
        except:
            tables = driver.find_elements(By.CSS_SELECTOR, "table.list_table")
            table = tables[0] if tables else None
        if not table:
            return None
        for row in table.find_elements(By.TAG_NAME, "tr"):
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 3:
                continue
            if tender_id in " ".join(c.text for c in cells):
                links = row.find_elements(By.TAG_NAME, "a")
                for lnk in links:
                    if len(lnk.text.strip()) > 10:
                        return lnk
                if links:
                    return links[0]
        try:
            nxt = driver.find_elements(By.LINK_TEXT, "Next >") or driver.find_elements(By.PARTIAL_LINK_TEXT, "Next")
            if not nxt:
                break
            nxt[0].click()
            time.sleep(3)
        except:
            break
    return None


def _extract_details(driver) -> Dict[str, str]:
    """Extract key-value pairs from detail page."""
    details = {}
    for table in driver.find_elements(By.TAG_NAME, "table"):
        for row in table.find_elements(By.TAG_NAME, "tr"):
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 2:
                k = cells[0].text.strip().rstrip(":")
                v = cells[1].text.strip()
                if k and v and len(k) < 100:
                    details[k] = v
    return details


def _wait_download(dl_dir: Path, timeout=30) -> Optional[Path]:
    for _ in range(timeout):
        files = [f for f in dl_dir.glob("*")
                 if not f.suffix in [".crdownload", ".html", ".py", ".png", ".json"]
                 and f.stat().st_size > 100]
        if files:
            return max(files, key=lambda f: f.stat().st_mtime)
        time.sleep(1)
    return None


def download_nic_tender_documents(
    tender_id: str,
    portal_key: str = "uttarakhand",
    title: str = "",
) -> Dict:
    """
    Download all documents for a tender from an NIC eProcurement portal.
    
    Returns dict with: success, details, documents[], errors[]
    """
    portal = NIC_PORTALS.get(portal_key)
    if not portal:
        return {"success": False, "errors": [f"Unknown portal: {portal_key}"]}

    base_url = portal["base"]
    safe_id = tender_id.replace("/", "_").replace("\\", "_")
    tender_dir = STORAGE_BASE / portal_key / safe_id
    tender_dir.mkdir(parents=True, exist_ok=True)
    dl_dir = tender_dir / "downloads"
    dl_dir.mkdir(exist_ok=True)

    # Clean old downloads
    for f in dl_dir.iterdir():
        if f.is_file():
            f.unlink()

    result = {
        "tender_id": tender_id,
        "portal": portal_key,
        "success": False,
        "details": {},
        "documents": [],
        "files_dir": str(tender_dir),
        "errors": [],
    }

    driver = None
    try:
        dl_abs = str(dl_dir.resolve())
        driver = _make_driver(dl_abs)

        # Step 1: Navigate to active tenders
        logger.info(f"Loading {portal_key} portal...")
        driver.get(base_url + "/nicgep/app?page=FrontEndLatestActiveTenders&service=page")
        time.sleep(3)

        # Step 2: Solve listing CAPTCHA
        logger.info("Solving listing CAPTCHA...")
        if not _solve_captcha(driver, "Search"):
            result["errors"].append("Listing CAPTCHA failed")
            return result

        # Step 3: Find tender
        logger.info(f"Finding tender {tender_id}...")
        link = _find_tender(driver, tender_id)
        if not link:
            result["errors"].append(f"Tender {tender_id} not found in portal")
            return result

        # Step 4: Open detail page
        try:
            link.click()
        except:
            driver.execute_script("arguments[0].click();", link)
        time.sleep(4)
        detail_url = driver.current_url

        # Save detail page
        with open(tender_dir / "detail.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        # Extract details
        details = _extract_details(driver)
        result["details"] = details

        # Step 5: Click "Download as zip" → CAPTCHA page
        zip_link = None
        for a in driver.find_elements(By.TAG_NAME, "a"):
            if "download as zip" in a.text.lower():
                zip_link = a
                break
        if not zip_link:
            result["errors"].append("No 'Download as zip' link on detail page")
            return result

        zip_link.click()
        time.sleep(3)

        # Step 6: Solve download CAPTCHA
        logger.info("Solving download CAPTCHA...")
        if not _solve_captcha(driver, "Submit"):
            result["errors"].append("Download CAPTCHA failed")
            return result

        logger.info("CAPTCHA solved, session authorized.")
        time.sleep(2)

        # Step 7: Go back to detail page and click download AGAIN
        if "FrontEndTenderDetails" not in driver.page_source:
            driver.get(detail_url)
            time.sleep(4)

        for a in driver.find_elements(By.TAG_NAME, "a"):
            if "download as zip" in a.text.lower():
                a.click()
                break

        # Wait for download
        dl_file = _wait_download(dl_dir, timeout=60)
        if not dl_file:
            result["errors"].append("Download timed out")
            return result

        logger.info(f"Downloaded: {dl_file.name} ({dl_file.stat().st_size:,} bytes)")

        # Extract ZIP
        if zipfile.is_zipfile(dl_file):
            extract_dir = tender_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(dl_file) as zf:
                zf.extractall(extract_dir)
                for info in zf.infolist():
                    if not info.is_dir():
                        result["documents"].append({
                            "name": info.filename,
                            "size": info.file_size,
                            "path": str(extract_dir / info.filename),
                        })
        else:
            result["documents"].append({
                "name": dl_file.name,
                "size": dl_file.stat().st_size,
                "path": str(dl_file),
            })

        result["success"] = True
        
        # Save result
        with open(tender_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)

        return result

    except Exception as e:
        logger.error(f"Download failed: {e}")
        result["errors"].append(str(e))
        return result
    finally:
        if driver:
            driver.quit()


def get_downloaded_documents(tender_id: str, portal_key: str = "uttarakhand") -> Optional[Dict]:
    """Check if documents already downloaded for this tender."""
    safe_id = tender_id.replace("/", "_").replace("\\", "_")
    result_file = STORAGE_BASE / portal_key / safe_id / "result.json"
    if result_file.exists():
        with open(result_file) as f:
            return json.load(f)
    return None


def get_tender_summary(details: Dict) -> Dict:
    """Extract a clean summary from raw detail key-value pairs."""
    def find(keys):
        for k in keys:
            for dk, dv in details.items():
                if k.lower() in dk.lower() and dv and len(dv) < 300:
                    return dv
        return None

    return {
        "title": find(["Title", "Work Description"]),
        "organization": find(["Organisation Chain"]),
        "tender_ref": find(["Tender Reference Number"]),
        "tender_id": find(["Tender ID"]),
        "published_date": find(["Published Date"]),
        "bid_submission_start": find(["Bid Submission Start Date"]),
        "bid_submission_end": find(["Bid Submission End Date"]),
        "bid_opening_date": find(["Bid Opening Date"]),
        "pre_bid_meeting_date": find(["Pre Bid Meeting Date"]),
        "pre_bid_meeting_address": find(["Pre Bid Meeting Address"]),
        "emd_amount": find(["EMD Amount"]),
        "tender_fee": find(["Tender Fee in"]),
        "tender_value": find(["Tender Value"]),
        "tender_category": find(["Tender Category"]),
        "tender_type": find(["Tender Type"]),
        "location": find(["Location"]),
        "eligibility": find(["NDA/Pre Qualification"]),
        "contract_type": find(["Contract Type"]),
    }
