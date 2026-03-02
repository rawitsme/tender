"""Debug CPPP page source after captcha."""
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

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
driver.get("https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page")
time.sleep(3)

# Check if captcha exists
try:
    captcha = driver.find_element(By.ID, "captchaImage")
    print("CAPTCHA found")
except:
    print("NO CAPTCHA on page")
    print("Page has 'Total records':", "Total records" in driver.page_source)
    print("Page has 'Organisation Chain':", "Organisation Chain" in driver.page_source)

# Check what text is on page
src = driver.page_source
for keyword in ["Invalid Captcha", "e-Published", "Organisation Chain", "Total records", "list_table", "id=\"table\""]:
    print(f"  '{keyword}': {keyword in src}")

# Save page source for inspection
with open("/tmp/cppp_page.html", "w") as f:
    f.write(src)
print("Saved page source to /tmp/cppp_page.html")

driver.quit()
