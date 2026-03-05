#!/usr/bin/env python3
"""Quick test: click docDownoad link and see what happens after CAPTCHA."""

import base64, os, sys, time, glob
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

BASE = "https://uktenders.gov.in"
DL_DIR = Path("storage/documents/uk_test_dl").resolve()
DL_DIR.mkdir(parents=True, exist_ok=True)

# Clean download dir
for f in DL_DIR.glob("*"): f.unlink()

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1400,1024")
opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
prefs = {
    "download.default_directory": str(DL_DIR),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True,
}
opts.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(DL_DIR)})

# Also try Browser.setDownloadBehavior
try:
    driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(DL_DIR)})
except: pass

def get_captcha():
    try:
        el = driver.find_element(By.ID, "captchaImage")
        src = el.get_attribute("src")
        if src and src.startswith("data:"):
            b64 = src.split(",", 1)[1].replace("%0A","").replace("\n","").replace(" ","")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            return base64.b64decode(b64)
        return el.screenshot_as_png
    except: return None

def solve(max_tries=5):
    for i in range(max_tries):
        cb = get_captcha()
        if not cb:
            try: driver.find_element(By.ID, "captcha").click(); time.sleep(2)
            except: driver.refresh(); time.sleep(2)
            continue
        sol = solve_captcha_image(cb)
        if not sol: continue
        print(f"  🔑 Attempt {i+1}: '{sol}'")
        inp = driver.find_element(By.NAME, "captchaText")
        inp.clear(); inp.send_keys(sol)
        for name in ["Search", "Submit"]:
            try: driver.find_element(By.NAME, name).click(); break
            except: pass
        time.sleep(3)
        ps = driver.page_source
        if "Invalid Captcha" in ps: print("  ❌ Rejected"); continue
        return True
    return False

try:
    # Step 1: Access active tenders
    print("📡 Step 1: Loading portal...")
    driver.get(BASE + "/nicgep/app?page=FrontEndLatestActiveTenders&service=page")
    time.sleep(3)
    
    print("🔐 Step 2: Solving listing CAPTCHA...")
    if not solve(): print("FAILED"); sys.exit(1)
    
    # Find the tender
    print("🔍 Step 3: Finding tender...")
    tender_id = "2026_UKJS_92617_1"
    for page in range(1, 6):
        print(f"  Page {page}...")
        try:
            table = driver.find_element(By.ID, "table")
            for row in table.find_elements(By.TAG_NAME, "tr"):
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 3: continue
                if tender_id in " ".join(c.text for c in cells):
                    links = row.find_elements(By.TAG_NAME, "a")
                    for lnk in links:
                        if len(lnk.text.strip()) > 10:
                            lnk.click()
                            time.sleep(4)
                            raise StopIteration
        except StopIteration: break
        try:
            nxt = driver.find_elements(By.LINK_TEXT, "Next >") or driver.find_elements(By.LINK_TEXT, "Next")
            if nxt: nxt[0].click(); time.sleep(3)
            else: break
        except: break
    
    print(f"📋 On detail page: {driver.current_url[:80]}")
    
    # Find the docDownoad link (individual PDF)
    print("\n📄 Step 4: Clicking individual document link...")
    doc_links = driver.find_elements(By.ID, "docDownoad")
    if doc_links:
        print(f"  Found {len(doc_links)} docDownoad links")
        print(f"  First: {doc_links[0].text} -> {doc_links[0].get_attribute('href')[:80]}")
        doc_links[0].click()
        time.sleep(3)
    else:
        # Try by partial link text
        for a in driver.find_elements(By.TAG_NAME, "a"):
            if a.get_attribute("id") == "docDownoad":
                a.click(); time.sleep(3); break
    
    # Now on CAPTCHA page
    print(f"\n🔐 Step 5: On page: {driver.current_url[:80]}")
    print(f"  Page title: {driver.title}")
    
    # Check current page content
    ps = driver.page_source
    if "captchaImage" in ps:
        print("  CAPTCHA page detected!")
        
        # Solve it
        if solve():
            print("  ✅ CAPTCHA solved!")
            
            # Wait and check for downloads
            print("  ⏳ Waiting for download...")
            for i in range(20):
                time.sleep(2)
                files = list(DL_DIR.glob("*"))
                complete = [f for f in files if not f.name.endswith(".crdownload")]
                if complete:
                    for f in complete:
                        print(f"  ✅ DOWNLOADED: {f.name} ({f.stat().st_size:,} bytes)")
                    break
                print(f"  ⏳ Waiting... ({i*2}s) files: {[f.name for f in files]}")
            else:
                print("  ❌ No download after 40s")
            
            # Check what page we're on now
            print(f"\n  📄 Current URL: {driver.current_url[:100]}")
            print(f"  Page has 'download' in it: {'download' in driver.page_source.lower()}")
            
            # Save page for analysis
            with open(DL_DIR / "post_captcha.html", "w") as f:
                f.write(driver.page_source)
        else:
            print("  ❌ CAPTCHA failed")
    else:
        print("  No CAPTCHA on this page")
        print(f"  Page content preview: {ps[:500]}")

finally:
    driver.quit()
    
print(f"\n📂 Download dir contents:")
for f in DL_DIR.glob("*"):
    print(f"  {f.name} ({f.stat().st_size:,} bytes)")
