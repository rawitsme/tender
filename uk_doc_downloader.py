#!/usr/bin/env python3
"""
Uttarakhand Tender Document Downloader (Selenium)

Workflow:
1. Navigate to uktenders.gov.in active tenders
2. Solve CAPTCHA to access listings
3. Find target tender by ID
4. Click into detail page
5. Download all documents as ZIP
6. Extract and summarize contents
"""

import base64
import json
import os
import re
import requests
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

BASE_URL = "https://uktenders.gov.in"
ACTIVE_PAGE = "/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
DOWNLOADS_DIR = Path("storage/documents/uttarakhand_downloads")


def get_driver(headless=True, download_dir=None):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1024")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

    if download_dir:
        prefs = {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        }
        opts.add_experimental_option("prefs", prefs)

    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


def get_captcha_bytes(driver) -> Optional[bytes]:
    """Extract CAPTCHA image bytes from the page."""
    try:
        captcha_el = driver.find_element(By.ID, "captchaImage")
        src = captcha_el.get_attribute("src")
        if src and src.startswith("data:"):
            b64 = src.split(",", 1)[1].replace("%0A", "").replace("\n", "").replace(" ", "")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            return base64.b64decode(b64)
        return captcha_el.screenshot_as_png
    except Exception as e:
        print(f"  ⚠️ Failed to get CAPTCHA image: {e}")
        return None


def solve_captcha_on_page(driver, max_attempts=5) -> bool:
    """Solve the CAPTCHA on an NIC portal page."""
    for attempt in range(max_attempts):
        captcha_bytes = get_captcha_bytes(driver)
        if not captcha_bytes:
            print(f"  ⚠️ No CAPTCHA image found, refreshing...")
            driver.refresh()
            time.sleep(2)
            continue

        solution = solve_captcha_image(captcha_bytes)
        if not solution:
            print(f"  ⚠️ CAPTCHA solver returned None, retrying...")
            try:
                driver.find_element(By.NAME, "captcha").click()
                time.sleep(1)
            except Exception:
                driver.refresh()
                time.sleep(2)
            continue

        print(f"  🔑 CAPTCHA attempt {attempt + 1}: trying '{solution}'")
        captcha_input = driver.find_element(By.NAME, "captchaText")
        captcha_input.clear()
        captcha_input.send_keys(solution)

        # Click submit
        try:
            btn = driver.find_element(By.NAME, "Search")
        except Exception:
            try:
                btn = driver.find_element(By.NAME, "Submit")
            except Exception:
                # Try any submit button
                btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
        btn.click()
        time.sleep(3)

        page = driver.page_source
        if "Invalid Captcha" in page or "Incorrect Captcha" in page:
            print(f"  ❌ CAPTCHA rejected, retrying...")
            continue
        if "Organisation Chain" in page or "Total records:" in page or "e-Published Date" in page:
            print(f"  ✅ CAPTCHA solved on attempt {attempt + 1}")
            return True

    print("  ❌ Failed to solve CAPTCHA after all attempts")
    return False


def find_tender_in_listing(driver, tender_id: str) -> Optional[str]:
    """Find a specific tender in the listing table and return its detail link onclick/href."""
    print(f"  🔍 Searching for tender: {tender_id}")

    # Look through all pages
    page_num = 1
    while page_num <= 10:
        print(f"    📄 Scanning page {page_num}...")
        
        # Find the results table
        try:
            table = driver.find_element(By.ID, "table")
        except Exception:
            tables = driver.find_elements(By.CSS_SELECTOR, "table.list_table")
            table = tables[0] if tables else None

        if not table:
            print("    ⚠️ No results table found")
            return None

        rows = table.find_elements(By.TAG_NAME, "tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 3:
                continue
            row_text = " ".join(c.text for c in cells)
            
            if tender_id in row_text:
                print(f"    🎯 Found tender in row!")
                # Find clickable link in the row - usually the tender title link
                links = row.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href") or ""
                    onclick = link.get_attribute("onclick") or ""
                    text = link.text.strip()
                    if text and len(text) > 10:
                        print(f"    📋 Found link: {text[:60]}...")
                        return link  # Return the WebElement to click
                
                # If no text link, try any link in the row
                if links:
                    return links[0]
        
        # Try next page
        try:
            next_links = driver.find_elements(By.LINK_TEXT, "Next >")
            if not next_links:
                next_links = driver.find_elements(By.LINK_TEXT, "Next")
            if not next_links:
                print("    ℹ️ No more pages")
                break
            next_links[0].click()
            time.sleep(3)
            page_num += 1
        except Exception:
            break

    print(f"    ❌ Tender {tender_id} not found in listing")
    return None


def extract_tender_details(driver) -> dict:
    """Extract tender details from the detail page."""
    details = {}
    page_source = driver.page_source
    
    # Try to find detail tables
    tables = driver.find_elements(By.TAG_NAME, "table")
    
    for table in tables:
        rows = table.find_elements(By.TAG_NAME, "tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 2:
                label = cells[0].text.strip().rstrip(":")
                value = cells[1].text.strip()
                if label and value and len(label) < 100:
                    details[label] = value
    
    return details


def find_download_zip_link(driver):
    """Find the 'Download as Zip' or similar document download link."""
    # Common patterns for document download on NIC portals
    search_texts = [
        "Download as Zip",
        "Download All",
        "Download Documents", 
        "Download as zip",
        "Zip File",
        "Document Download",
        "Tender Document",
    ]
    
    # Search by link text
    for text in search_texts:
        try:
            links = driver.find_elements(By.PARTIAL_LINK_TEXT, text)
            if links:
                print(f"    📦 Found download link: '{links[0].text}'")
                return links[0]
        except Exception:
            continue
    
    # Search by href patterns
    all_links = driver.find_elements(By.TAG_NAME, "a")
    for link in all_links:
        href = (link.get_attribute("href") or "").lower()
        text = link.text.strip().lower()
        onclick = (link.get_attribute("onclick") or "").lower()
        
        if any(kw in href for kw in ["download", "zip", "document"]):
            print(f"    📦 Found download link by href: '{link.text}' -> {href[:80]}")
            return link
        if any(kw in onclick for kw in ["download", "zip"]):
            print(f"    📦 Found download link by onclick: '{link.text}'")
            return link
        if any(kw in text for kw in ["download", "zip file", "tender document"]):
            print(f"    📦 Found download link by text: '{text}'")
            return link
    
    # Look for download images/icons
    imgs = driver.find_elements(By.TAG_NAME, "img")
    for img in imgs:
        alt = (img.get_attribute("alt") or "").lower()
        src = (img.get_attribute("src") or "").lower()
        title = (img.get_attribute("title") or "").lower()
        if any(kw in alt + src + title for kw in ["download", "zip"]):
            parent = img.find_element(By.XPATH, "..")
            if parent.tag_name == "a":
                print(f"    📦 Found download via icon: alt='{alt}'")
                return parent
    
    return None


def wait_for_download(download_dir: Path, timeout=60) -> Optional[Path]:
    """Wait for a file to appear in the download directory."""
    start = time.time()
    while time.time() - start < timeout:
        files = list(download_dir.glob("*"))
        # Filter out .crdownload (Chrome partial downloads)
        complete = [f for f in files if not f.name.endswith(".crdownload") and f.stat().st_size > 0]
        if complete:
            # Return the newest file
            complete.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            return complete[0]
        time.sleep(1)
    return None


def extract_and_list_files(zip_path: Path, extract_dir: Path) -> list:
    """Extract ZIP and return list of extracted files."""
    extracted = []
    
    if zipfile.is_zipfile(zip_path):
        print(f"    📂 Extracting ZIP: {zip_path.name}")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
            for info in zf.infolist():
                if not info.is_dir():
                    extracted.append({
                        "name": info.filename,
                        "size": info.file_size,
                        "path": str(extract_dir / info.filename),
                    })
                    print(f"      📄 {info.filename} ({info.file_size:,} bytes)")
    else:
        # Not a zip - might be a PDF or other document directly
        print(f"    📄 Downloaded file: {zip_path.name} ({zip_path.stat().st_size:,} bytes)")
        extracted.append({
            "name": zip_path.name,
            "size": zip_path.stat().st_size,
            "path": str(zip_path),
        })
    
    return extracted


def download_tender_documents(tender_id: str, tender_title: str = ""):
    """
    Main workflow: download all documents for an Uttarakhand tender.
    
    Args:
        tender_id: The NIC tender ID (e.g., '2026_UKJS_92617_1')
        tender_title: Optional title for folder naming
    """
    print("=" * 60)
    print(f"  📥 UTTARAKHAND DOCUMENT DOWNLOADER")
    print(f"  Tender: {tender_id}")
    if tender_title:
        print(f"  Title: {tender_title[:80]}")
    print("=" * 60)
    
    # Create download directory
    safe_id = tender_id.replace("/", "_").replace("\\", "_")
    tender_dir = DOWNLOADS_DIR / safe_id
    download_dir = tender_dir / "downloads"
    extract_dir = tender_dir / "extracted"
    tender_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(exist_ok=True)
    extract_dir.mkdir(exist_ok=True)
    
    driver = None
    result = {
        "tender_id": tender_id,
        "success": False,
        "details": {},
        "documents": [],
        "errors": [],
    }
    
    try:
        print("\n📡 Step 1: Starting browser and navigating to portal...")
        driver = get_driver(headless=True, download_dir=str(download_dir.resolve()))
        
        url = BASE_URL + ACTIVE_PAGE
        driver.get(url)
        time.sleep(3)
        print(f"  ✅ Portal loaded: {driver.title}")
        
        # Step 2: Solve CAPTCHA
        print("\n🔐 Step 2: Solving CAPTCHA...")
        if not solve_captcha_on_page(driver):
            result["errors"].append("Failed to solve CAPTCHA")
            return result
        
        # Step 3: Find the tender
        print(f"\n🔍 Step 3: Finding tender {tender_id}...")
        tender_link = find_tender_in_listing(driver, tender_id)
        
        if not tender_link:
            # Try searching by organization or tender search
            print("  ⚠️ Not found in active listing, trying tender search...")
            # Try the tender search page
            search_url = BASE_URL + "/nicgep/app?page=FrontEndTendersByOrganisation&service=page"
            driver.get(search_url)
            time.sleep(3)
            
            # Check if there's a CAPTCHA here too
            captcha_elements = driver.find_elements(By.ID, "captchaImage")
            if captcha_elements:
                if not solve_captcha_on_page(driver):
                    result["errors"].append("Failed to solve search page CAPTCHA")
                    return result
            
            tender_link = find_tender_in_listing(driver, tender_id)
        
        if not tender_link:
            result["errors"].append(f"Tender {tender_id} not found in portal listings")
            return result
        
        # Step 4: Click into detail page
        print(f"\n📋 Step 4: Opening tender detail page...")
        try:
            tender_link.click()
            time.sleep(4)
        except Exception as e:
            # Try JavaScript click
            driver.execute_script("arguments[0].click();", tender_link)
            time.sleep(4)
        
        print(f"  📄 Detail page: {driver.title}")
        print(f"  🔗 URL: {driver.current_url}")
        
        # Save the detail page HTML
        detail_html = driver.page_source
        with open(tender_dir / "detail_page.html", "w", encoding="utf-8") as f:
            f.write(detail_html)
        
        # Extract tender details
        print("\n📊 Step 5: Extracting tender details...")
        details = extract_tender_details(driver)
        result["details"] = details
        
        for key, value in details.items():
            if len(value) < 200:
                print(f"  📌 {key}: {value}")
        
        # Step 6: Find and click download link
        print("\n📦 Step 6: Looking for document download...")
        download_link = find_download_zip_link(driver)
        
        if not download_link:
            print("  ⚠️ No download link found on detail page")
            # Save screenshot for debugging
            driver.save_screenshot(str(tender_dir / "detail_page_screenshot.png"))
            
            # Try looking in frames/iframes
            frames = driver.find_elements(By.TAG_NAME, "iframe")
            for i, frame in enumerate(frames):
                try:
                    driver.switch_to.frame(frame)
                    download_link = find_download_zip_link(driver)
                    if download_link:
                        print(f"  ✅ Found download in iframe {i}")
                        break
                    driver.switch_to.default_content()
                except Exception:
                    driver.switch_to.default_content()
            
            if not download_link:
                # Look for individual document links instead
                print("  🔍 Looking for individual document links...")
                doc_links = []
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for link in all_links:
                    href = (link.get_attribute("href") or "").lower()
                    text = link.text.strip()
                    if any(ext in href for ext in [".pdf", ".doc", ".xls", ".zip"]):
                        doc_links.append(link)
                        print(f"    📄 Found: {text or href[:60]}")
                
                if not doc_links:
                    result["errors"].append("No download links found on detail page")
                    driver.save_screenshot(str(tender_dir / "no_downloads_screenshot.png"))
                    return result
        
        if download_link:
            print(f"  🔗 Clicking download: {download_link.text[:60]}...")
            
            # Click the download link
            download_link.click()
            time.sleep(3)
            
            # Check if we got a CAPTCHA page for download
            captcha_elements = driver.find_elements(By.ID, "captchaImage")
            if captcha_elements:
                print("  🔐 Download requires CAPTCHA...")
                
                # On NIC portals, after CAPTCHA the download starts automatically
                # We need to solve CAPTCHA and then check for file download
                for captcha_attempt in range(5):
                    captcha_bytes = get_captcha_bytes(driver)
                    if not captcha_bytes:
                        driver.refresh()
                        time.sleep(2)
                        continue
                    
                    solution = solve_captcha_image(captcha_bytes)
                    if not solution:
                        continue
                    
                    print(f"  🔑 Download CAPTCHA attempt {captcha_attempt+1}: '{solution}'")
                    captcha_input = driver.find_element(By.NAME, "captchaText")
                    captcha_input.clear()
                    captcha_input.send_keys(solution)
                    
                    # Find and click submit
                    try:
                        btn = driver.find_element(By.NAME, "Submit")
                    except Exception:
                        try:
                            btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
                        except Exception:
                            btn = driver.find_element(By.NAME, "Search")
                    btn.click()
                    time.sleep(5)
                    
                    # Check if CAPTCHA was rejected
                    page_text = driver.page_source
                    if "Invalid Captcha" in page_text or "Incorrect Captcha" in page_text:
                        print(f"  ❌ CAPTCHA rejected, retrying...")
                        continue
                    
                    # Check if download started
                    downloaded_file = wait_for_download(download_dir, timeout=30)
                    if downloaded_file:
                        print(f"  ✅ Downloaded: {downloaded_file.name} ({downloaded_file.stat().st_size:,} bytes)")
                        files = extract_and_list_files(downloaded_file, extract_dir)
                        result["documents"] = files
                        result["success"] = True
                        break
                    
                    # Maybe the page changed - look for direct download links now
                    print("  🔍 Checking for post-CAPTCHA download links...")
                    new_links = driver.find_elements(By.TAG_NAME, "a")
                    for nl in new_links:
                        href = (nl.get_attribute("href") or "").lower()
                        if any(ext in href for ext in [".zip", ".pdf", "download"]):
                            print(f"    📥 Found post-CAPTCHA link: {href[:80]}")
                            # Use requests to download via the browser's cookies
                            cookies = {c['name']: c['value'] for c in driver.get_cookies()}

                            resp = requests.get(nl.get_attribute("href"), cookies=cookies, stream=True, timeout=30,
                                              headers={"User-Agent": "Mozilla/5.0"})
                            if resp.status_code == 200 and len(resp.content) > 1000:
                                ct = resp.headers.get("content-type", "")
                                ext = ".zip" if "zip" in ct else ".pdf" if "pdf" in ct else ".bin"
                                out_path = download_dir / f"tender_docs{ext}"
                                with open(out_path, "wb") as f:
                                    f.write(resp.content)
                                print(f"    ✅ Downloaded via requests: {out_path.name} ({len(resp.content):,} bytes)")
                                files = extract_and_list_files(out_path, extract_dir)
                                result["documents"] = files
                                result["success"] = True
                                break
                    
                    if result["success"]:
                        break
                    
                    # Last resort: try to get the download URL from page source and use requests
                    print("  🔍 Trying to extract download URL from page source...")

                    zip_urls = re.findall(r'href="([^"]*(?:zip|download|document)[^"]*)"', page_text, re.I)
                    for zu in zip_urls[:3]:
                        full_url = zu if zu.startswith("http") else BASE_URL + zu
                        print(f"    📥 Trying: {full_url[:80]}")
                        try:
                            cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                            resp = requests.get(full_url, cookies=cookies, stream=True, timeout=30,
                                              headers={"User-Agent": "Mozilla/5.0"})
                            if resp.status_code == 200 and len(resp.content) > 1000:
                                ct = resp.headers.get("content-type", "")
                                if "html" not in ct:
                                    ext = ".zip" if "zip" in ct else ".pdf" if "pdf" in ct else ".bin"
                                    out_path = download_dir / f"tender_docs{ext}"
                                    with open(out_path, "wb") as f:
                                        f.write(resp.content)
                                    print(f"    ✅ Downloaded: {out_path.name} ({len(resp.content):,} bytes)")
                                    files = extract_and_list_files(out_path, extract_dir)
                                    result["documents"] = files
                                    result["success"] = True
                                    break
                        except Exception as e:
                            print(f"    ⚠️ Failed: {e}")
                    
                    if result["success"]:
                        break
                
                if not result["success"]:
                    # Save the post-CAPTCHA page for debugging
                    with open(tender_dir / "post_captcha_page.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    driver.save_screenshot(str(tender_dir / "post_captcha_screenshot.png"))
                    result["errors"].append("Download failed after CAPTCHA")
            else:
                # No CAPTCHA - direct download
                print("  ⏳ Waiting for direct download...")
                downloaded_file = wait_for_download(download_dir, timeout=30)
                if downloaded_file:
                    print(f"  ✅ Downloaded: {downloaded_file.name} ({downloaded_file.stat().st_size:,} bytes)")
                    files = extract_and_list_files(downloaded_file, extract_dir)
                    result["documents"] = files
                    result["success"] = True
                else:
                    result["errors"].append("Download timed out")
        
        # Save result
        with open(tender_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        result["errors"].append(str(e))
        if driver:
            try:
                driver.save_screenshot(str(tender_dir / "error_screenshot.png"))
            except:
                pass
        return result
        
    finally:
        if driver:
            driver.quit()


def summarize_result(result: dict):
    """Print a summary of the download result."""
    print("\n" + "=" * 60)
    print("  📊 DOWNLOAD SUMMARY")
    print("=" * 60)
    
    if result["success"]:
        print(f"  ✅ Status: SUCCESS")
        print(f"  📄 Documents: {len(result['documents'])}")
        for doc in result["documents"]:
            size_kb = doc["size"] / 1024
            print(f"     • {doc['name']} ({size_kb:.1f} KB)")
    else:
        print(f"  ❌ Status: FAILED")
        for err in result["errors"]:
            print(f"     ⚠️ {err}")
    
    if result["details"]:
        print(f"\n  📋 Tender Details Extracted:")
        important_fields = [
            "Tender Reference Number", "Tender ID", "Tender Title",
            "Organisation Chain", "e-Published Date", "Document Download / Sale Start Date",
            "Document Download / Sale End Date", "Bid Submission Start Date",
            "Bid Submission End Date", "Bid Opening Date",
            "Pre Bid Meeting Date", "EMD Amount", "Tender Value",
            "Fee Payable To", "Tender Fee", "Work Description",
            "Pre Qualification", "Tender Category", "Product Category",
        ]
        for field in important_fields:
            for key, value in result["details"].items():
                if field.lower() in key.lower():
                    print(f"     📌 {key}: {value}")
                    break


if __name__ == "__main__":
    # Test with one of our Uttarakhand tenders
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tender-id", default="2026_UKJS_92617_1", help="Tender ID to download")
    parser.add_argument("--title", default="", help="Tender title")
    args = parser.parse_args()
    
    result = download_tender_documents(args.tender_id, args.title)
    summarize_result(result)
