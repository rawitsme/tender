#!/usr/bin/env python3
"""Download UK tender docs using CDP network interception to capture file responses."""

import base64, json, os, sys, time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

BASE = "https://uktenders.gov.in"
DL_DIR = Path("storage/documents/uk_cdp_dl")
DL_DIR.mkdir(parents=True, exist_ok=True)

def get_captcha_bytes(driver):
    try:
        el = driver.find_element(By.ID, "captchaImage")
        src = el.get_attribute("src")
        if src and src.startswith("data:"):
            b64 = src.split(",", 1)[1].replace("%0A","").replace("\n","").replace(" ","")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            return base64.b64decode(b64)
        return el.screenshot_as_png
    except: return None

def solve(driver, btn_name="Search", max_tries=5):
    for i in range(max_tries):
        cb = get_captcha_bytes(driver)
        if not cb:
            try: driver.find_element(By.ID, "captcha").click(); time.sleep(2)
            except: driver.refresh(); time.sleep(2)
            continue
        sol = solve_captcha_image(cb)
        if not sol: continue
        print(f"  🔑 Attempt {i+1}: '{sol}'")
        inp = driver.find_element(By.NAME, "captchaText")
        inp.clear(); inp.send_keys(sol)
        for name in [btn_name, "Search", "Submit"]:
            try: driver.find_element(By.NAME, name).click(); break
            except: pass
        time.sleep(3)
        ps = driver.page_source
        if "Invalid Captcha" in ps: print("  ❌ Rejected"); continue
        return True
    return False

def main():
    tender_id = "2026_UKJS_92617_1"
    print(f"🎯 Target: {tender_id}")
    
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1024")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    
    # Enable performance logging to capture network
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    dl_abs = str(DL_DIR.resolve())
    prefs = {
        "download.default_directory": dl_abs,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    opts.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    
    # Enable download via CDP
    driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
        "behavior": "allow", "downloadPath": dl_abs, "eventsEnabled": True
    })
    
    # Enable network domain for response capture
    driver.execute_cdp_cmd("Network.enable", {})
    
    try:
        # Step 1-3: Navigate to tender detail (same as before)
        print("\n📡 Loading portal & solving CAPTCHA...")
        driver.get(BASE + "/nicgep/app?page=FrontEndLatestActiveTenders&service=page")
        time.sleep(3)
        if not solve(driver, "Search"): print("FAILED"); return
        
        print(f"🔍 Finding {tender_id}...")
        found = False
        for page in range(1, 6):
            try:
                table = driver.find_element(By.ID, "table")
                for row in table.find_elements(By.TAG_NAME, "tr"):
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 3: continue
                    if tender_id in " ".join(c.text for c in cells):
                        for lnk in row.find_elements(By.TAG_NAME, "a"):
                            if len(lnk.text.strip()) > 10: lnk.click(); found = True; break
                    if found: break
            except: pass
            if found: break
            try:
                nxt = driver.find_elements(By.LINK_TEXT, "Next >") or driver.find_elements(By.LINK_TEXT, "Next")
                if nxt: nxt[0].click(); time.sleep(3)
                else: break
            except: break
        
        if not found: print("❌ Not found"); return
        time.sleep(4)
        print("✅ On detail page")
        
        # Step 4: Click Download as zip
        print("\n📦 Clicking 'Download as zip file'...")
        for a in driver.find_elements(By.TAG_NAME, "a"):
            if "download as zip" in a.text.lower():
                a.click(); break
        time.sleep(3)
        
        # Step 5: Solve download CAPTCHA
        print("\n🔐 Solving download CAPTCHA...")
        if not solve(driver, "Submit"):
            print("❌ CAPTCHA failed"); return
        
        print("✅ CAPTCHA solved!")
        
        # Step 6: Check for download via multiple methods
        print("\n📥 Checking for download...")
        
        # Wait a bit for any download to start
        time.sleep(5)
        
        # Check download directory
        files = [f for f in DL_DIR.glob("*") if not f.name.endswith((".crdownload", ".html", ".py")) and f.stat().st_size > 0]
        if files:
            for f in files:
                print(f"  ✅ FILE: {f.name} ({f.stat().st_size:,} bytes)")
            return
        
        # Check CDP for download events in performance log
        print("  🔍 Checking performance logs...")
        try:
            logs = driver.get_log("performance")
            for log in logs[-50:]:  # Check last 50 entries
                msg = json.loads(log["message"])["message"]
                method = msg.get("method", "")
                if "download" in method.lower() or "Network.responseReceived" == method:
                    params = msg.get("params", {})
                    if "Network.responseReceived" == method:
                        resp = params.get("response", {})
                        mime = resp.get("mimeType", "")
                        url = resp.get("url", "")
                        if "html" not in mime and mime:
                            print(f"    📡 Response: {mime} from {url[:80]}")
                            # Try to get response body
                            req_id = params.get("requestId")
                            if req_id:
                                try:
                                    body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": req_id})
                                    data = body.get("body", "")
                                    is_base64 = body.get("base64Encoded", False)
                                    if is_base64:
                                        content = base64.b64decode(data)
                                    else:
                                        content = data.encode()
                                    
                                    if len(content) > 500:
                                        ext = ".zip" if "zip" in mime else ".pdf" if "pdf" in mime else ".bin"
                                        out = DL_DIR / f"tender_docs{ext}"
                                        with open(out, "wb") as f:
                                            f.write(content)
                                        print(f"    ✅ CAPTURED via CDP: {out.name} ({len(content):,} bytes)")
                                        
                                        # Verify
                                        if ext == ".zip":
                                            import zipfile
                                            if zipfile.is_zipfile(out):
                                                with zipfile.ZipFile(out) as zf:
                                                    for info in zf.infolist():
                                                        print(f"      📄 {info.filename} ({info.file_size:,} bytes)")
                                                print("    ✅ SUCCESS!")
                                                return
                                        elif ext == ".pdf" and content[:5] == b'%PDF-':
                                            print("    ✅ Valid PDF!")
                                            return
                                except Exception as e:
                                    print(f"    ⚠️ Could not get body: {e}")
                    elif "download" in method.lower():
                        print(f"    📥 Download event: {method} - {json.dumps(params)[:200]}")
        except Exception as e:
            print(f"  ⚠️ Log check failed: {e}")
        
        # Last resort: check if we're on a page with downloadable content
        # Try navigating to the detail page and clicking docDownoad directly
        print("\n🔄 Alternative: Try clicking individual doc link...")
        driver.back()
        time.sleep(3)
        
        # Look for docDownoad links
        doc_links = driver.find_elements(By.ID, "docDownoad")
        for dl in doc_links:
            href = dl.get_attribute("href")
            text = dl.text.strip()
            print(f"  📄 Doc link: {text} -> {href[:80]}")
            dl.click()
            time.sleep(3)
            
            # Might get CAPTCHA again
            caps = driver.find_elements(By.ID, "captchaImage")
            if caps:
                print("  🔐 CAPTCHA for individual doc...")
                if solve(driver, "Submit"):
                    time.sleep(5)
                    files = [f for f in DL_DIR.glob("*") if not f.name.endswith((".crdownload", ".html", ".py")) and f.stat().st_size > 0]
                    if files:
                        for f in files:
                            print(f"  ✅ FILE: {f.name} ({f.stat().st_size:,} bytes)")
                        return
                    
                    # Check if the page itself has the PDF embedded
                    current_url = driver.current_url
                    print(f"  Current URL: {current_url[:100]}")
                    
                    # Try fetching the URL directly via CDP
                    try:
                        logs = driver.get_log("performance")
                        for log in logs[-30:]:
                            msg = json.loads(log["message"])["message"]
                            if msg.get("method") == "Network.responseReceived":
                                params = msg.get("params", {})
                                resp = params.get("response", {})
                                mime = resp.get("mimeType", "")
                                if "html" not in mime and mime and "image" not in mime:
                                    req_id = params.get("requestId")
                                    try:
                                        body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": req_id})
                                        data = body.get("body", "")
                                        is_b64 = body.get("base64Encoded", False)
                                        content = base64.b64decode(data) if is_b64 else data.encode()
                                        if len(content) > 500:
                                            out = DL_DIR / text
                                            with open(out, "wb") as f: f.write(content)
                                            print(f"  ✅ CAPTURED: {out.name} ({len(content):,} bytes)")
                                            return
                                    except: pass
                    except: pass
            break
        
        print("\n❌ All methods failed")
        driver.save_screenshot(str(DL_DIR / "final.png"))
        with open(DL_DIR / "final.html", "w") as f: f.write(driver.page_source)
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
