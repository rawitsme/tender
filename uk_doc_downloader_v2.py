#!/usr/bin/env python3
"""
Uttarakhand Tender Document Downloader v2
Uses Selenium for navigation/CAPTCHA, requests for file download.
"""

import base64, json, os, re, requests as req, sys, time, zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

BASE = "https://uktenders.gov.in"
ACTIVE = "/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
STORE = Path("storage/documents/uttarakhand_downloads")


def make_driver(download_dir=None):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1024")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    if download_dir:
        prefs = {
            "download.default_directory": str(Path(download_dir).resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        }
        opts.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    if download_dir:
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": str(Path(download_dir).resolve())
        })
    return driver


def get_captcha_bytes(driver) -> Optional[bytes]:
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


def solve_page_captcha(driver, max_tries=5) -> bool:
    """Solve CAPTCHA on active tenders listing page."""
    for i in range(max_tries):
        cb = get_captcha_bytes(driver)
        if not cb:
            driver.refresh(); time.sleep(2); continue
        sol = solve_captcha_image(cb)
        if not sol:
            try: driver.find_element(By.ID, "captcha").click()
            except: driver.refresh()
            time.sleep(2); continue
        
        print(f"  🔑 Attempt {i+1}: '{sol}'")
        inp = driver.find_element(By.NAME, "captchaText")
        inp.clear(); inp.send_keys(sol)
        
        for name in ["Search", "Submit"]:
            try:
                driver.find_element(By.NAME, name).click(); break
            except: pass
        time.sleep(3)
        
        ps = driver.page_source
        if "Invalid Captcha" in ps: print("  ❌ Rejected"); continue
        if any(k in ps for k in ["Organisation Chain", "Total records:", "e-Published Date"]):
            print(f"  ✅ Solved!"); return True
    return False


def solve_download_captcha(driver, max_tries=5) -> bool:
    """Solve CAPTCHA on the DocDownCaptcha page. Returns True if solved."""
    for i in range(max_tries):
        cb = get_captcha_bytes(driver)
        if not cb:
            # Try clicking refresh button
            try: driver.find_element(By.ID, "captcha").click(); time.sleep(2)
            except: driver.refresh(); time.sleep(2)
            continue
        
        sol = solve_captcha_image(cb)
        if not sol: continue
        
        print(f"  🔑 Download CAPTCHA attempt {i+1}: '{sol}'")
        inp = driver.find_element(By.NAME, "captchaText")
        inp.clear(); inp.send_keys(sol)
        driver.find_element(By.NAME, "Submit").click()
        time.sleep(3)
        
        ps = driver.page_source
        if "Invalid Captcha" in ps:
            print("  ❌ Rejected"); continue
        # If no error, CAPTCHA was accepted
        print("  ✅ Download CAPTCHA solved!")
        return True
    return False


def selenium_cookies_to_requests(driver) -> dict:
    """Transfer Selenium cookies to a requests session."""
    s = req.Session()
    for c in driver.get_cookies():
        s.cookies.set(c['name'], c['value'], domain=c.get('domain'))
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': driver.current_url,
    })
    return s


def find_tender(driver, tender_id: str):
    """Find tender in listing, return the link WebElement."""
    for page in range(1, 11):
        print(f"    📄 Page {page}...")
        try:
            table = driver.find_element(By.ID, "table")
        except:
            tables = driver.find_elements(By.CSS_SELECTOR, "table.list_table")
            table = tables[0] if tables else None
        if not table: return None
        
        for row in table.find_elements(By.TAG_NAME, "tr"):
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 3: continue
            text = " ".join(c.text for c in cells)
            if tender_id in text:
                print(f"    🎯 Found!")
                links = row.find_elements(By.TAG_NAME, "a")
                for lnk in links:
                    if len(lnk.text.strip()) > 10: return lnk
                if links: return links[0]
        
        # Next page
        try:
            nxt = driver.find_elements(By.LINK_TEXT, "Next >") or driver.find_elements(By.LINK_TEXT, "Next")
            if not nxt: break
            nxt[0].click(); time.sleep(3)
        except: break
    return None


def extract_details(driver) -> dict:
    """Extract key-value pairs from tender detail page."""
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


def download_tender(tender_id: str, title: str = ""):
    """Main workflow."""
    print("=" * 60)
    print(f"  📥 UK DOCUMENT DOWNLOADER v2")
    print(f"  Tender: {tender_id}")
    print("=" * 60)
    
    safe_id = tender_id.replace("/", "_")
    tender_dir = STORE / safe_id
    tender_dir.mkdir(parents=True, exist_ok=True)
    
    driver = None
    result = {"tender_id": tender_id, "success": False, "details": {}, "documents": [], "errors": []}
    
    try:
        # Step 1: Navigate & solve listing CAPTCHA
        download_dir = tender_dir / "downloads"
        download_dir.mkdir(exist_ok=True)
        
        print("\n📡 Step 1: Opening portal...")
        driver = make_driver(download_dir=str(download_dir))
        driver.get(BASE + ACTIVE)
        time.sleep(3)
        
        print("\n🔐 Step 2: Solving listing CAPTCHA...")
        if not solve_page_captcha(driver):
            result["errors"].append("Listing CAPTCHA failed"); return result
        
        # Step 3: Find tender
        print(f"\n🔍 Step 3: Finding {tender_id}...")
        link = find_tender(driver, tender_id)
        if not link:
            result["errors"].append("Tender not found"); return result
        
        # Step 4: Open detail page
        print("\n📋 Step 4: Opening detail page...")
        try: link.click()
        except: driver.execute_script("arguments[0].click();", link)
        time.sleep(4)
        
        # Save detail page
        with open(tender_dir / "detail.html", "w") as f:
            f.write(driver.page_source)
        
        # Extract details
        details = extract_details(driver)
        result["details"] = details
        
        # Print key fields
        key_fields = ["Tender Reference Number", "Tender ID", "Organisation Chain",
                       "Title", "Work Description", "Published Date", 
                       "Bid Submission Start Date", "Bid Submission End Date",
                       "Document Download / Sale End Date",
                       "Bid Opening Date", "Pre Bid Meeting Date",
                       "EMD Amount", "Tender Fee", "Tender Value",
                       "Tender Category", "Location", "NDA/Pre Qualification"]
        print("\n  📊 Tender Details:")
        for kf in key_fields:
            for k, v in details.items():
                if kf.lower() in k.lower() and len(v) < 200:
                    print(f"    {k}: {v}")
                    break
        
        # Step 5: Find and click "Download as zip file"
        print("\n📦 Step 5: Clicking 'Download as zip file'...")
        zip_link = None
        for a in driver.find_elements(By.TAG_NAME, "a"):
            if "download as zip" in a.text.lower():
                zip_link = a; break
        
        if not zip_link:
            # Try by image alt/title
            for img in driver.find_elements(By.TAG_NAME, "img"):
                if "zip" in (img.get_attribute("title") or "").lower():
                    parent = img.find_element(By.XPATH, "..")
                    if parent.tag_name == "a": zip_link = parent; break
        
        if not zip_link:
            result["errors"].append("No 'Download as zip' link found")
            driver.save_screenshot(str(tender_dir / "no_zip_link.png"))
            return result
        
        # Get the zip link href BEFORE clicking (for requests fallback)
        zip_href = zip_link.get_attribute("href")
        print(f"  🔗 ZIP link: {zip_href[:80]}...")
        
        zip_link.click()
        time.sleep(3)
        
        # Step 6: We should now be on DocDownCaptcha page
        print("\n🔐 Step 6: Solving download CAPTCHA...")
        page_src = driver.page_source
        
        if "DocDownCaptcha" not in page_src and "captchaImage" not in page_src:
            print("  ⚠️ Not on CAPTCHA page, checking for direct download...")
            driver.save_screenshot(str(tender_dir / "after_zip_click.png"))
        
        # Solve the download CAPTCHA
        if not solve_download_captcha(driver):
            result["errors"].append("Download CAPTCHA failed")
            driver.save_screenshot(str(tender_dir / "captcha_failed.png"))
            with open(tender_dir / "captcha_page.html", "w") as f:
                f.write(driver.page_source)
            return result
        
        # Step 7: After CAPTCHA is solved, check for file download
        print("\n📥 Step 7: Downloading file...")
        
        downloaded = False
        
        # Method 0: Check if headless Chrome downloaded the file directly
        print("  ⏳ Waiting for Chrome download (15s)...")
        time.sleep(5)
        dl_files = [f for f in download_dir.iterdir() if not f.name.endswith(".crdownload") and f.stat().st_size > 0] if download_dir.exists() else []
        if dl_files:
            newest = max(dl_files, key=lambda f: f.stat().st_mtime)
            print(f"  ✅ Chrome downloaded: {newest.name} ({newest.stat().st_size:,} bytes)")
            downloaded = True
            if zipfile.is_zipfile(newest):
                extract_dir = tender_dir / "extracted"
                extract_dir.mkdir(exist_ok=True)
                with zipfile.ZipFile(newest) as zf:
                    zf.extractall(extract_dir)
                    for info in zf.infolist():
                        if not info.is_dir():
                            result["documents"].append({"name": info.filename, "size": info.file_size, "path": str(extract_dir / info.filename)})
                            print(f"    📄 {info.filename} ({info.file_size:,} bytes)")
            else:
                result["documents"].append({"name": newest.name, "size": newest.stat().st_size, "path": str(newest)})
        
        if not downloaded:
            # Transfer cookies to requests session
            rs = selenium_cookies_to_requests(driver)
            current_url = driver.current_url
            print(f"  🔗 Current URL: {current_url[:80]}...")
            
            # Method 1: Try current URL with requests
            try:
                resp = rs.get(current_url, timeout=60, stream=True)
                ct = resp.headers.get("content-type", "")
                print(f"  📡 Response: {resp.status_code}, Content-Type: {ct}, Size: {len(resp.content):,}")
                
                if resp.status_code == 200 and "html" not in ct.lower() and len(resp.content) > 500:
                    ext = ".zip" if "zip" in ct else ".pdf" if "pdf" in ct else ".bin"
                    out = tender_dir / f"documents{ext}"
                    with open(out, "wb") as f: f.write(resp.content)
                    print(f"  ✅ Downloaded: {out.name} ({len(resp.content):,} bytes)")
                    downloaded = True
            except Exception as e:
                print(f"  ⚠️ Method 1 failed: {e}")
        
        # Method 2: Check page source for download links
        if not downloaded:
            page_after = driver.page_source
            # Look for any content-disposition or auto-download triggers
            urls = re.findall(r'href="([^"]*(?:download|zip|document)[^"]*)"', page_after, re.I)
            for u in urls[:5]:
                full = u.replace("&amp;", "&") if not u.startswith("http") else u
                if not full.startswith("http"): full = BASE + full
                try:
                    resp = rs.get(full, timeout=60)
                    ct = resp.headers.get("content-type", "")
                    if "html" not in ct.lower() and len(resp.content) > 500:
                        ext = ".zip" if "zip" in ct else ".pdf" if "pdf" in ct else ".bin"
                        out = tender_dir / f"documents{ext}"
                        with open(out, "wb") as f: f.write(resp.content)
                        print(f"  ✅ Downloaded via link: {out.name} ({len(resp.content):,} bytes)")
                        downloaded = True
                        break
                except: pass
        
        # Method 3: Replay the original zip href with cookies (session might now be authorized)
        if not downloaded and zip_href:
            print(f"  🔄 Method 3: Replaying original zip link with authorized session...")
            try:
                resp = rs.get(zip_href, timeout=60)
                ct = resp.headers.get("content-type", "")
                print(f"  📡 Response: {resp.status_code}, CT: {ct}, Size: {len(resp.content):,}")
                if "html" not in ct.lower() and len(resp.content) > 500:
                    ext = ".zip" if "zip" in ct else ".pdf" if "pdf" in ct else ".bin"
                    out = tender_dir / f"documents{ext}"
                    with open(out, "wb") as f: f.write(resp.content)
                    print(f"  ✅ Downloaded: {out.name} ({len(resp.content):,} bytes)")
                    downloaded = True
            except Exception as e:
                print(f"  ⚠️ Method 3 failed: {e}")
        
        # Method 4: Try individual document URLs from the detail page
        if not downloaded:
            print("  📄 Method 4: Downloading individual documents from detail page...")
            doc_info = details.get("Work Item Documents", "") + " " + details.get("NIT Document", "")
            # Extract document names
            doc_names = re.findall(r'(\S+\.(?:pdf|xls|xlsx|doc|docx))', doc_info, re.I)
            print(f"  📋 Found document names: {doc_names}")
            
            if doc_names:
                for dname in doc_names:
                    # NIC portals typically serve docs at specific endpoints
                    # Try common NIC document URL patterns
                    patterns = [
                        f"{BASE}/nicgep/app?page=TenderDocumentDownload&service=page&docname={dname}",
                    ]
                    for pat in patterns:
                        try:
                            resp = rs.get(pat, timeout=30)
                            ct = resp.headers.get("content-type", "")
                            if "html" not in ct.lower() and len(resp.content) > 500:
                                out = tender_dir / dname
                                with open(out, "wb") as f: f.write(resp.content)
                                print(f"    ✅ Got {dname} ({len(resp.content):,} bytes)")
                                result["documents"].append({"name": dname, "size": len(resp.content), "path": str(out)})
                                downloaded = True
                        except: pass
        
        if downloaded:
            # Extract ZIP if applicable
            for f in tender_dir.glob("documents.zip"):
                if zipfile.is_zipfile(f):
                    extract_dir = tender_dir / "extracted"
                    extract_dir.mkdir(exist_ok=True)
                    with zipfile.ZipFile(f) as zf:
                        zf.extractall(extract_dir)
                        for info in zf.infolist():
                            if not info.is_dir():
                                result["documents"].append({
                                    "name": info.filename,
                                    "size": info.file_size,
                                    "path": str(extract_dir / info.filename),
                                })
                                print(f"    📄 {info.filename} ({info.file_size:,} bytes)")
            result["success"] = True
        else:
            result["errors"].append("All download methods failed")
            driver.save_screenshot(str(tender_dir / "final_state.png"))
            with open(tender_dir / "final_page.html", "w") as f:
                f.write(driver.page_source)
        
        # Save result
        with open(tender_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        
        return result
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback; traceback.print_exc()
        result["errors"].append(str(e))
        if driver:
            try: driver.save_screenshot(str(tender_dir / "error.png"))
            except: pass
        return result
    finally:
        if driver: driver.quit()


def print_summary(result):
    print("\n" + "=" * 60)
    print("  📊 RESULT SUMMARY")
    print("=" * 60)
    
    d = result["details"]
    
    # Key tender info
    for label, keys in [
        ("📋 Title", ["Title", "Work Description"]),
        ("🏢 Organization", ["Organisation Chain"]),
        ("📅 Published", ["Published Date"]),
        ("📅 Bid Submission End", ["Bid Submission End Date"]),
        ("📅 Bid Opening", ["Bid Opening Date"]),
        ("📅 Pre-Bid Meeting", ["Pre Bid Meeting Date", "Pre Bid Meeting Address"]),
        ("💰 EMD", ["EMD Amount"]),
        ("💰 Tender Fee", ["Tender Fee"]),
        ("💰 Tender Value", ["Tender Value"]),
        ("📂 Category", ["Tender Category"]),
        ("📍 Location", ["Location"]),
        ("📝 Eligibility/Pre-Qual", ["NDA/Pre Qualification"]),
    ]:
        for k in keys:
            for dk, dv in d.items():
                if k.lower() in dk.lower() and dv and len(dv) < 300:
                    print(f"  {label}: {dv}")
                    break
    
    if result["success"]:
        print(f"\n  ✅ Documents: {len(result['documents'])}")
        for doc in result["documents"]:
            print(f"    📄 {doc['name']} ({doc['size']/1024:.1f} KB)")
    else:
        print(f"\n  ❌ Download failed:")
        for e in result["errors"]:
            print(f"    ⚠️ {e}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--tender-id", default="2026_UKJS_92617_1")
    p.add_argument("--title", default="")
    args = p.parse_args()
    
    r = download_tender(args.tender_id, args.title)
    print_summary(r)
