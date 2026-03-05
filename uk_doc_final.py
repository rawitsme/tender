#!/usr/bin/env python3
"""
UK Tender Doc Download - Final approach.
After CAPTCHA solves, session is authorized. Click download AGAIN to get the file.
"""
import base64, json, os, sys, time, zipfile
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

BASE = "https://uktenders.gov.in"
DOCS_ROOT = Path("storage/documents").resolve()

def get_dl_dir(tender_id):
    """Per-tender document folder: storage/documents/{tender_id}/"""
    d = DOCS_ROOT / tender_id
    d.mkdir(parents=True, exist_ok=True)
    return d

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
        driver.find_element(By.NAME, "captchaText").clear()
        driver.find_element(By.NAME, "captchaText").send_keys(sol)
        for name in [btn_name, "Search", "Submit"]:
            try: driver.find_element(By.NAME, name).click(); break
            except: pass
        time.sleep(3)
        ps = driver.page_source
        if "Invalid Captcha" in ps: print("  ❌ Rejected"); continue
        return True
    return False

def wait_download(dl_dir, timeout=30):
    for _ in range(timeout):
        files = [f for f in dl_dir.glob("*") if f.suffix not in ['.crdownload','.html','.py','.png'] and f.stat().st_size > 100]
        if files: return max(files, key=lambda f: f.stat().st_mtime)
        time.sleep(1)
    return None

def main():
    tender_id = "2026_UKJS_92617_1"
    DL_DIR = get_dl_dir(tender_id)
    
    # Clean download dir (keep previously extracted files)
    for f in DL_DIR.iterdir():
        if f.is_file() and f.suffix in ['.crdownload', '.html', '.png']:
            f.unlink()
    
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1024")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    prefs = {"download.default_directory": str(DL_DIR), "download.prompt_for_download": False, "download.directory_upgrade": True}
    opts.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(DL_DIR), "eventsEnabled": True})
    
    try:
        # Step 1: Navigate to active tenders & solve CAPTCHA
        print("📡 Loading portal...")
        driver.get(BASE + "/nicgep/app?page=FrontEndLatestActiveTenders&service=page")
        time.sleep(3)
        print("🔐 Solving listing CAPTCHA...")
        if not solve(driver, "Search"): print("FAILED"); return
        
        # Step 2: Find tender
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
        detail_url = driver.current_url
        print(f"✅ Detail page: {detail_url[:80]}")
        
        # Step 3: Click "Download as zip" → goes to CAPTCHA page
        print("\n📦 Click 1: Download as zip file...")
        for a in driver.find_elements(By.TAG_NAME, "a"):
            if "download as zip" in a.text.lower(): a.click(); break
        time.sleep(3)
        print(f"  On: {driver.current_url[:80]}")
        
        # Step 4: Solve download CAPTCHA
        print("🔐 Solving download CAPTCHA...")
        if not solve(driver, "Submit"):
            print("❌ CAPTCHA failed"); return
        print("✅ CAPTCHA solved! Session should be authorized now.")
        time.sleep(2)
        
        # Step 5: NOW we should be back on detail page with an authorized session.
        # Click "Download as zip" AGAIN - this time it should download directly
        print(f"\n📦 Click 2: Download as zip file AGAIN (now authorized)...")
        print(f"  Current page: {driver.current_url[:80]}")
        
        # Check if we're on detail page
        if "FrontEndTenderDetails" not in driver.page_source:
            print("  ⚠️ Not on detail page, navigating back...")
            driver.get(detail_url)
            time.sleep(4)
        
        # Click download again
        for a in driver.find_elements(By.TAG_NAME, "a"):
            if "download as zip" in a.text.lower():
                print(f"  🔗 Clicking: {a.get_attribute('href')[:80]}")
                a.click()
                break
        
        # This time it should either:
        # a) Download directly (session authorized)
        # b) Show CAPTCHA again (session not persistent)
        time.sleep(5)
        
        # Check if we got a CAPTCHA page again
        ps = driver.page_source
        if "captchaImage" in ps and "DocDownCaptcha" in ps:
            print("  ⚠️ Got CAPTCHA again! Session auth didn't persist.")
            print("  The portal requires CAPTCHA every time.")
            print("  Trying: solve CAPTCHA and DON'T follow redirect...")
            
            # This time, we'll use JavaScript to intercept the form submission
            # and capture the response
            cb = get_captcha_bytes(driver)
            if cb:
                sol = solve_captcha_image(cb)
                if sol:
                    print(f"  🔑 Solution: '{sol}'")
                    # Instead of clicking Submit, use fetch() in browser to POST
                    # and capture the response
                    js_code = f"""
                    var form = document.getElementById('frmCaptcha');
                    var formData = new FormData(form);
                    formData.set('captchaText', '{sol}');
                    formData.set('Submit', 'Submit');
                    
                    var result = await fetch(form.action || '/nicgep/app', {{
                        method: 'POST',
                        body: new URLSearchParams(formData),
                        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                    }});
                    
                    var contentType = result.headers.get('content-type') || '';
                    var contentDisp = result.headers.get('content-disposition') || '';
                    var blob = await result.blob();
                    
                    // Convert to base64
                    var reader = new FileReader();
                    var base64 = await new Promise(resolve => {{
                        reader.onload = () => resolve(reader.result);
                        reader.readAsDataURL(blob);
                    }});
                    
                    return JSON.stringify({{
                        contentType: contentType,
                        contentDisposition: contentDisp,
                        size: blob.size,
                        status: result.status,
                        base64: base64,
                    }});
                    """
                    
                    try:
                        result_json = driver.execute_async_script(f"""
                        var callback = arguments[arguments.length - 1];
                        (async function() {{
                            try {{
                                var form = document.getElementById('frmCaptcha');
                                var formData = new URLSearchParams();
                                var inputs = form.querySelectorAll('input');
                                for (var inp of inputs) {{
                                    if (inp.name) formData.set(inp.name, inp.value);
                                }}
                                formData.set('captchaText', '{sol}');
                                formData.set('Submit', 'Submit');
                                
                                var resp = await fetch(form.action || '/nicgep/app', {{
                                    method: 'POST',
                                    body: formData,
                                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                                }});
                                
                                var ct = resp.headers.get('content-type') || '';
                                var cd = resp.headers.get('content-disposition') || '';
                                var blob = await resp.blob();
                                
                                var reader = new FileReader();
                                reader.onload = function() {{
                                    callback(JSON.stringify({{
                                        ct: ct, cd: cd, size: blob.size, status: resp.status,
                                        data: reader.result
                                    }}));
                                }};
                                reader.readAsDataURL(blob);
                            }} catch(e) {{
                                callback(JSON.stringify({{error: e.toString()}}));
                            }}
                        }})();
                        """)
                        
                        result = json.loads(result_json)
                        print(f"  📡 Fetch result: status={result.get('status')}, ct={result.get('ct','')[:40]}, size={result.get('size')}")
                        
                        if result.get('error'):
                            print(f"  ❌ Error: {result['error']}")
                        elif result.get('size', 0) > 500 and 'html' not in result.get('ct', ''):
                            # Got a file!
                            data_url = result.get('data', '')
                            if ',' in data_url:
                                b64_data = data_url.split(',', 1)[1]
                                content = base64.b64decode(b64_data)
                                
                                ct = result.get('ct', '')
                                ext = '.zip' if 'zip' in ct else '.pdf' if 'pdf' in ct else '.bin'
                                out = DL_DIR / f"tender_docs{ext}"
                                with open(out, 'wb') as f: f.write(content)
                                print(f"  ✅ CAPTURED: {out.name} ({len(content):,} bytes)")
                                
                                if ext == '.zip' and zipfile.is_zipfile(out):
                                    with zipfile.ZipFile(out) as zf:
                                        for info in zf.infolist():
                                            if not info.is_dir():
                                                print(f"    📄 {info.filename} ({info.file_size:,} bytes)")
                                        zf.extractall(DL_DIR)
                                    print("  🎉 SUCCESS!")
                                elif content[:5] == b'%PDF-':
                                    print("  ✅ Valid PDF!")
                                return
                        else:
                            # Got HTML - CAPTCHA might have been wrong
                            text = base64.b64decode(result.get('data','').split(',',1)[-1]).decode('utf-8', errors='replace')
                            if 'Invalid Captcha' in text:
                                print("  ❌ CAPTCHA was wrong")
                            else:
                                print("  ⚠️ Got HTML response")
                                with open(DL_DIR / "fetch_response.html", 'w') as f: f.write(text)
                                print(f"  Saved to fetch_response.html for analysis")
                    except Exception as e:
                        print(f"  ❌ JS fetch failed: {e}")
        else:
            # Check for download
            print("  Checking for download...")
            dl = wait_download(DL_DIR, 20)
            if dl:
                print(f"  ✅ DOWNLOADED: {dl.name} ({dl.stat().st_size:,} bytes)")
            else:
                print("  ❌ No download")
                driver.save_screenshot(str(DL_DIR / "after_click2.png"))
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
