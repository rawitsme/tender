"""Debug: fetch one NIC page and dump the table structure."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import base64

def main():
    portal = sys.argv[1] if len(sys.argv) > 1 else "up"
    urls = {
        "cppp": "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
        "up": "https://etender.up.nic.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
        "maharashtra": "https://mahatenders.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
    }
    
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.get(urls[portal])
    time.sleep(3)
    
    # Solve captcha
    from backend.ingestion.connectors.captcha_solver import solve_captcha_image
    try:
        captcha_el = driver.find_element(By.ID, "captchaImage")
        src = captcha_el.get_attribute("src")
        if src and src.startswith("data:"):
            b64 = src.split(",", 1)[1].replace("%0A", "").replace("\n", "").replace(" ", "")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            image_data = base64.b64decode(b64)
        else:
            image_data = captcha_el.screenshot_as_png
        
        solution = solve_captcha_image(image_data)
        print(f"CAPTCHA solution: {solution}")
        
        captcha_input = driver.find_element(By.NAME, "captchaText")
        captcha_input.clear()
        captcha_input.send_keys(solution)
        try:
            btn = driver.find_element(By.NAME, "Search")
        except:
            btn = driver.find_element(By.NAME, "Submit")
        btn.click()
        time.sleep(3)
    except Exception as e:
        print(f"No captcha or error: {e}")
    
    # Dump table structure
    tables = driver.find_elements(By.TAG_NAME, "table")
    print(f"\nFound {len(tables)} tables\n")
    
    for i, table in enumerate(tables):
        rows = table.find_elements(By.TAG_NAME, "tr")
        if len(rows) < 2:
            continue
        
        # Get table ID/class
        tid = table.get_attribute("id") or ""
        tcls = table.get_attribute("class") or ""
        print(f"=== Table {i}: id='{tid}' class='{tcls}' rows={len(rows)} ===")
        
        # Header
        header = rows[0]
        ths = header.find_elements(By.TAG_NAME, "th")
        if ths:
            print(f"  Headers: {[th.text.strip()[:40] for th in ths]}")
        
        # First 3 data rows
        for j, row in enumerate(rows[1:4]):
            cells = row.find_elements(By.TAG_NAME, "td")
            print(f"  Row {j+1} ({len(cells)} cells):")
            for k, cell in enumerate(cells):
                text = cell.text.strip()[:100]
                links = cell.find_elements(By.TAG_NAME, "a")
                link_info = f" [link: {links[0].get_attribute('href')[:80]}]" if links else ""
                print(f"    [{k}] {text}{link_info}")
        print()
    
    driver.quit()

if __name__ == "__main__":
    main()
