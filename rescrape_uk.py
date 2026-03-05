#!/usr/bin/env python3
"""Re-scrape ALL active Uttarakhand tenders. Selenium + CAPTCHA + pagination."""
import base64, json, os, re, sys, time, uuid
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

BASE = "https://uktenders.gov.in"
DB_URL = "postgresql://tender:tender_dev_2026@localhost:5432/tender_portal"

def parse_date(s):
    for fmt in ["%d-%b-%Y %I:%M %p", "%d-%b-%Y %H:%M", "%d-%m-%Y"]:
        try: return datetime.strptime(s.strip(), fmt)
        except: pass
    return None

def main():
    opts = Options()
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    try:
        driver.get(BASE + "/nicgep/app?page=FrontEndLatestActiveTenders&service=page")
        time.sleep(3)

        # Solve CAPTCHA
        print("🔐 Solving CAPTCHA...", flush=True)
        solved = False
        for i in range(10):
            try: el = driver.find_element(By.ID, "captchaImage")
            except:
                print("  No captcha element — may already be solved", flush=True)
                solved = True
                break
            src = el.get_attribute("src")
            if not src or "data:" not in src:
                print(f"  No data URI on attempt {i+1}, refreshing...", flush=True)
                driver.refresh()
                time.sleep(3)
                continue
            b64 = src.split(",",1)[1].replace("%0A","").replace("\n","").replace(" ","")
            b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
            print(f"  Sending to 2Captcha (attempt {i+1})...", flush=True)
            sol = solve_captcha_image(base64.b64decode(b64))
            if not sol:
                print(f"  2Captcha returned no solution, refreshing...", flush=True)
                driver.refresh()
                time.sleep(3)
                continue
            print(f"  CAPTCHA attempt {i+1}: '{sol}'", flush=True)
            driver.find_element(By.NAME, "captchaText").clear()
            driver.find_element(By.NAME, "captchaText").send_keys(sol)
            try: driver.find_element(By.NAME, "Search").click()
            except: driver.find_element(By.CSS_SELECTOR, "input[type='submit']").click()
            time.sleep(2)
            try:
                alert = driver.switch_to.alert
                print(f"  ❌ Alert: {alert.text}", flush=True)
                alert.accept()
                time.sleep(1)
                continue
            except:
                pass
            if "Invalid Captcha" not in driver.page_source:
                print("  ✅ CAPTCHA solved!", flush=True)
                solved = True
                break
        if not solved:
            print("❌ CAPTCHA failed after all attempts", flush=True)
            return

        # Scrape all pages — table#table has cols: S.No, Published, Closing, Opening, Title, Org, Value
        all_tenders = []
        for page in range(1, 100):  # up to 990 tenders
            try:
                table = driver.find_element(By.ID, "table")
            except:
                print(f"  No table#table on page {page}")
                break

            rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # skip header
            count = 0
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 6: continue
                try:
                    pub = cells[1].text.strip()
                    close = cells[2].text.strip()
                    opening = cells[3].text.strip()
                    title_cell = cells[4]
                    org = cells[5].text.strip()
                    value = cells[6].text.strip() if len(cells) > 6 else ""

                    # Get title and link
                    link = title_cell.find_elements(By.TAG_NAME, "a")
                    title = link[0].text.strip() if link else title_cell.text.strip()
                    href = link[0].get_attribute("href") if link else ""
                    
                    # Extract source_id and tender_id
                    sid_m = re.search(r'id=(\d+)', href or "")
                    source_id = sid_m.group(1) if sid_m else ""
                    tid_m = re.search(r'(\d{4}_\w+_\d+_\d+)', title_cell.text)
                    tender_id = tid_m.group(1) if tid_m else None

                    if len(title) < 10: continue

                    all_tenders.append({
                        "source_id": source_id or f"uk_{hash(title) % 10**8}",
                        "tender_id": tender_id,
                        "title": title[:1000],
                        "source_url": href,
                        "organization": org[:500],
                        "state": "Uttarakhand",
                        "publication_date": parse_date(pub),
                        "bid_close_date": parse_date(close),
                        "bid_open_date": parse_date(opening),
                        "tender_value": value,
                    })
                    count += 1
                except Exception as e:
                    continue

            print(f"  Page {page}: {count} tenders (total: {len(all_tenders)})")

            # Next page
            try:
                nxt = driver.find_elements(By.PARTIAL_LINK_TEXT, "Next")
                if not nxt: break
                nxt[0].click()
                time.sleep(3)
            except:
                break

        print(f"\n📊 Scraped {len(all_tenders)} tenders from portal")
        
        # Save raw
        with open("storage/uk_rescrape_raw.json", "w") as f:
            json.dump(all_tenders, f, indent=2, default=str)

        # Insert to DB
        import sqlalchemy
        engine = sqlalchemy.create_engine(DB_URL)
        new_count = dup_count = 0
        with engine.connect() as conn:
            for t in all_tenders:
                exists = conn.execute(sqlalchemy.text(
                    "SELECT 1 FROM tenders WHERE source='UTTARAKHAND' AND (source_id=:sid OR title=:title) LIMIT 1"
                ), {"sid": t["source_id"], "title": t["title"]}).fetchone()
                if exists:
                    dup_count += 1
                    continue
                try:
                    conn.execute(sqlalchemy.text("""
                        INSERT INTO tenders (id, title, source, source_id, source_url, tender_id,
                            organization, department, state, status, tender_type,
                            publication_date, bid_close_date, bid_open_date,
                            tender_value_estimated, parsed_quality_score, created_at, updated_at)
                        VALUES (:id, :title, 'UTTARAKHAND', :sid, :url, :tid,
                            :org, :org, 'Uttarakhand', 'ACTIVE', 'OPEN_TENDER',
                            :pub, :close, :open, 0, 0.5, NOW(), NOW())
                    """), {
                        "id": str(uuid.uuid4()), "title": t["title"],
                        "sid": t["source_id"], "url": t["source_url"],
                        "tid": t["tender_id"], "org": t["organization"],
                        "pub": t["publication_date"], "close": t["bid_close_date"],
                        "open": t["bid_open_date"],
                    })
                    new_count += 1
                except Exception as e:
                    print(f"  Insert err: {e}")
                    dup_count += 1
            conn.commit()

        total = 0
        with engine.connect() as conn:
            total = conn.execute(sqlalchemy.text("SELECT count(*) FROM tenders WHERE source='UTTARAKHAND'")).scalar()

        print(f"  ✅ New: {new_count}, Duplicates: {dup_count}")
        print(f"  📊 Total Uttarakhand in DB: {total}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
