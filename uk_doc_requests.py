#!/usr/bin/env python3
"""
Download Uttarakhand tender docs using Selenium for navigation + requests for download.
Key insight: After solving CAPTCHA on DocDownCaptcha page via POST,
the response itself should contain the file (not a redirect).
"""

import base64, json, os, sys, time
from pathlib import Path
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

BASE = "https://uktenders.gov.in"
DL_DIR = Path("storage/documents/uk_requests_dl")
DL_DIR.mkdir(parents=True, exist_ok=True)


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1024")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)


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


def solve_listing_captcha(driver, max_tries=5):
    for i in range(max_tries):
        cb = get_captcha_bytes(driver)
        if not cb: driver.refresh(); time.sleep(2); continue
        sol = solve_captcha_image(cb)
        if not sol: continue
        print(f"  🔑 Listing CAPTCHA attempt {i+1}: '{sol}'")
        driver.find_element(By.NAME, "captchaText").clear()
        driver.find_element(By.NAME, "captchaText").send_keys(sol)
        for name in ["Search", "Submit"]:
            try: driver.find_element(By.NAME, name).click(); break
            except: pass
        time.sleep(3)
        ps = driver.page_source
        if "Invalid Captcha" in ps: continue
        if any(k in ps for k in ["Organisation Chain", "Total records:", "e-Published Date"]):
            return True
    return False


def transfer_cookies(driver):
    """Create a requests session with Selenium's cookies."""
    s = requests.Session()
    for c in driver.get_cookies():
        s.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    return s


def main():
    tender_id = "2026_UKJS_92617_1"
    print(f"🎯 Target: {tender_id}")
    
    driver = make_driver()
    
    try:
        # Step 1: Get to active tenders
        print("\n📡 Step 1: Loading portal...")
        driver.get(BASE + "/nicgep/app?page=FrontEndLatestActiveTenders&service=page")
        time.sleep(3)
        
        # Step 2: Solve listing CAPTCHA
        print("\n🔐 Step 2: Solving listing CAPTCHA...")
        if not solve_listing_captcha(driver):
            print("FAILED"); return
        
        # Step 3: Navigate to tender
        print(f"\n🔍 Step 3: Finding tender {tender_id}...")
        found = False
        for page in range(1, 6):
            print(f"  Page {page}...")
            try:
                table = driver.find_element(By.ID, "table")
                for row in table.find_elements(By.TAG_NAME, "tr"):
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 3: continue
                    if tender_id in " ".join(c.text for c in cells):
                        for lnk in row.find_elements(By.TAG_NAME, "a"):
                            if len(lnk.text.strip()) > 10:
                                lnk.click(); time.sleep(4); found = True; break
                    if found: break
            except: pass
            if found: break
            try:
                nxt = driver.find_elements(By.LINK_TEXT, "Next >") or driver.find_elements(By.LINK_TEXT, "Next")
                if nxt: nxt[0].click(); time.sleep(3)
                else: break
            except: break
        
        if not found:
            print("❌ Tender not found"); return
        
        print(f"  ✅ On detail page")
        
        # Step 4: Click "Download as zip file" to get to CAPTCHA page
        print("\n📦 Step 4: Clicking 'Download as zip file'...")
        zip_link = None
        for a in driver.find_elements(By.TAG_NAME, "a"):
            if "download as zip" in a.text.lower():
                zip_link = a; break
        
        if not zip_link:
            print("❌ No zip link found"); return
        
        zip_link.click()
        time.sleep(3)
        
        # Step 5: We're now on DocDownCaptcha page
        # Instead of solving via Selenium, get the CAPTCHA image and form details,
        # then submit via requests (so we get the response body = the file)
        print("\n🔐 Step 5: On download CAPTCHA page...")
        print(f"  URL: {driver.current_url[:100]}")
        
        # Transfer session to requests
        rs = transfer_cookies(driver)
        
        # Get the CAPTCHA page HTML via requests too (for form fields)
        captcha_page_url = driver.current_url
        
        for attempt in range(5):
            # Get CAPTCHA image from Selenium (it renders base64 inline)
            captcha_bytes = get_captcha_bytes(driver)
            if not captcha_bytes:
                print(f"  ⚠️ No CAPTCHA image, refreshing...")
                driver.find_element(By.ID, "captcha").click()
                time.sleep(2)
                continue
            
            sol = solve_captcha_image(captcha_bytes)
            if not sol: continue
            
            print(f"  🔑 Attempt {attempt+1}: '{sol}'")
            
            # Get current page HTML for form fields
            page_html = driver.page_source
            soup = BeautifulSoup(page_html, 'html.parser')
            
            # Find the captcha form
            form = soup.find('form', id='frmCaptcha')
            if not form:
                print("  ⚠️ No frmCaptcha form found")
                continue
            
            # Collect all hidden fields
            form_data = {}
            for inp in form.find_all('input', type='hidden'):
                name = inp.get('name', '')
                val = inp.get('value', '')
                if name: form_data[name] = val
            
            form_data['captchaText'] = sol
            form_data['Submit'] = 'Submit'
            
            print(f"  📋 Form fields: {list(form_data.keys())}")
            
            # Get form action
            action = form.get('action', '/nicgep/app')
            form_url = BASE + action if not action.startswith('http') else action
            
            # Also get the JSESSIONID from Selenium
            jsession = None
            for c in driver.get_cookies():
                if 'session' in c['name'].lower():
                    jsession = c['value']
                    rs.cookies.set(c['name'], c['value'])
            
            # Submit via requests POST
            rs.headers['Referer'] = captcha_page_url
            rs.headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            print(f"  📤 POSTing to: {form_url}")
            resp = rs.post(form_url, data=form_data, timeout=60, allow_redirects=True)
            
            ct = resp.headers.get('content-type', '')
            cd = resp.headers.get('content-disposition', '')
            print(f"  📡 Response: {resp.status_code}, CT: {ct[:60]}, CD: {cd[:60]}, Size: {len(resp.content):,}")
            
            # Check if we got the file
            if 'html' not in ct.lower() and len(resp.content) > 500:
                # Got a file!
                if 'zip' in ct or 'zip' in cd:
                    ext = '.zip'
                elif 'pdf' in ct or 'pdf' in cd:
                    ext = '.pdf'
                elif 'octet' in ct:
                    ext = '.zip'  # assume zip for octet-stream
                else:
                    ext = '.bin'
                
                out = DL_DIR / f"tender_docs{ext}"
                with open(out, 'wb') as f:
                    f.write(resp.content)
                print(f"  ✅ DOWNLOADED: {out.name} ({len(resp.content):,} bytes)")
                
                # Verify it's a real file
                if ext == '.zip':
                    import zipfile
                    if zipfile.is_zipfile(out):
                        with zipfile.ZipFile(out) as zf:
                            print(f"  📂 ZIP contents:")
                            for info in zf.infolist():
                                print(f"    📄 {info.filename} ({info.file_size:,} bytes)")
                            zf.extractall(DL_DIR / "extracted")
                        print("  ✅ SUCCESS!")
                    else:
                        print("  ⚠️ Not a valid ZIP, checking content...")
                        print(f"  First 100 bytes: {resp.content[:100]}")
                elif ext == '.pdf':
                    if resp.content[:5] == b'%PDF-':
                        print("  ✅ Valid PDF!")
                    else:
                        print(f"  ⚠️ Not a valid PDF, first bytes: {resp.content[:50]}")
                return
            
            # Got HTML back - check if CAPTCHA was wrong
            if 'Invalid Captcha' in resp.text:
                print("  ❌ CAPTCHA rejected")
                # Refresh the CAPTCHA in Selenium
                driver.refresh()
                time.sleep(2)
                # Re-navigate to download CAPTCHA page
                driver.get(captcha_page_url)
                time.sleep(3)
                # Update cookies
                for c in driver.get_cookies():
                    rs.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
                continue
            
            # Got HTML but not an error - save for analysis
            print("  ⚠️ Got HTML response (not a file)")
            with open(DL_DIR / f"response_{attempt}.html", 'w') as f:
                f.write(resp.text)
            
            # The cookies in requests might be out of sync with Selenium
            # Let's try: after CAPTCHA solves in Selenium, immediately use Selenium to go back
            print("  🔄 Trying Selenium approach: solve in Selenium then grab cookies...")
            
            # Solve in Selenium instead
            inp = driver.find_element(By.NAME, "captchaText")
            inp.clear(); inp.send_keys(sol)
            driver.find_element(By.NAME, "Submit").click()
            time.sleep(3)
            
            sel_page = driver.page_source
            if "Invalid Captcha" in sel_page:
                print("  ❌ Selenium CAPTCHA also rejected")
                continue
            
            # If Selenium accepted it, we're back on detail page
            # The session is now authorized - try clicking the doc link again
            print("  ✅ Selenium CAPTCHA accepted, trying doc link again...")
            
            # Transfer updated cookies
            for c in driver.get_cookies():
                rs.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
            
            # Click docDownoad link
            doc_links = driver.find_elements(By.ID, "docDownoad")
            if doc_links:
                href = doc_links[0].get_attribute("href")
                print(f"  📥 Fetching doc link via requests: {href[:80]}")
                resp2 = rs.get(href, timeout=60)
                ct2 = resp2.headers.get('content-type', '')
                cd2 = resp2.headers.get('content-disposition', '')
                print(f"  📡 Response: {resp2.status_code}, CT: {ct2[:60]}, CD: {cd2[:60]}, Size: {len(resp2.content):,}")
                
                if 'html' not in ct2.lower() and len(resp2.content) > 500:
                    out = DL_DIR / "Tendernotice_1.pdf"
                    with open(out, 'wb') as f: f.write(resp2.content)
                    print(f"  ✅ DOWNLOADED: {out.name} ({len(resp2.content):,} bytes)")
                    if resp2.content[:5] == b'%PDF-':
                        print("  ✅ Valid PDF!")
                    return
                else:
                    print("  ⚠️ Still getting HTML")
                    with open(DL_DIR / f"doc_response_{attempt}.html", 'w') as f:
                        f.write(resp2.text)
            break
        
        print("  ❌ All attempts failed")
    
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
