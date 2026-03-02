"""Quick test: fetch CPPP CAPTCHA and solve via 2Captcha."""
import sys, os, time
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
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    
    print("Launching Chrome...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    
    url = "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page"
    print(f"Loading {url}")
    driver.get(url)
    time.sleep(3)
    
    # Get CAPTCHA image
    try:
        captcha_el = driver.find_element(By.ID, "captchaImage")
        src = captcha_el.get_attribute("src")
        if src and src.startswith("data:"):
            b64 = src.split(",", 1)[1].replace("%0A", "").replace("\n", "").replace(" ", "")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            image_data = base64.b64decode(b64)
        else:
            image_data = captcha_el.screenshot_as_png
        print(f"Got CAPTCHA image: {len(image_data)} bytes")
    except Exception as e:
        print(f"No CAPTCHA found: {e}")
        # Maybe no captcha needed?
        print("Page title:", driver.title)
        print("Has tender table?", "Tender Title" in driver.page_source or "e-Published" in driver.page_source)
        driver.quit()
        return
    
    # Solve with 2Captcha
    from backend.ingestion.connectors.captcha_solver import solve_captcha_image
    print("Sending to 2Captcha...")
    solution = solve_captcha_image(image_data)
    print(f"Solution: '{solution}'")
    
    if solution:
        captcha_input = driver.find_element(By.NAME, "captchaText")
        captcha_input.clear()
        captcha_input.send_keys(solution)
        
        try:
            btn = driver.find_element(By.NAME, "Search")
        except:
            btn = driver.find_element(By.NAME, "Submit")
        btn.click()
        time.sleep(3)
        
        page = driver.page_source
        if "e-Published Date" in page or "Closing Date" in page or "Tender Title" in page:
            print("✅ CAPTCHA SOLVED — got tender data!")
            # Count rows
            tables = driver.find_elements(By.TAG_NAME, "table")
            for t in tables:
                rows = t.find_elements(By.TAG_NAME, "tr")
                if len(rows) > 3:
                    print(f"  Found table with {len(rows)-1} tender rows")
        else:
            print("❌ CAPTCHA rejected by server")
    
    driver.quit()

if __name__ == "__main__":
    main()
