"""
Uttarakhand Tender Sync Service — HTTP-only.

Scrapes all active tenders from uktenders.gov.in, upserts to DB,
detects new tenders, updated dates (corrigenda), and status changes.

Designed to run 3x/day via cron (9am, 3pm, 6pm IST).
"""

import base64
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

logger = logging.getLogger(__name__)

BASE_URL = "https://uktenders.gov.in"
ACTIVE_TENDERS_URL = f"{BASE_URL}/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
STORAGE_DIR = Path("storage/sync_logs")


def _make_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )


def _get_captcha_bytes(soup: BeautifulSoup) -> Optional[bytes]:
    el = soup.find(id="captchaImage")
    if not el:
        return None
    src = el.get("src", "")
    if "," not in src:
        return None
    b64 = src.split(",", 1)[1].replace("%0A", "").replace("\n", "").replace(" ", "")
    if len(b64) % 4:
        b64 += "=" * (4 - len(b64) % 4)
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def _get_form_data(soup: BeautifulSoup) -> Optional[Dict[str, str]]:
    form = soup.find("form", {"action": "/nicgep/app"})
    if not form:
        return None
    data = {}
    for inp in form.find_all("input"):
        n = inp.get("name")
        if n and inp.get("type") not in ("radio",):
            data[n] = inp.get("value", "")
    return data


def _parse_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    for fmt in ["%d-%b-%Y %I:%M %p", "%d-%b-%Y %H:%M", "%d-%m-%Y %H:%M",
                "%d/%m/%Y %H:%M", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _parse_value(v: str) -> Optional[float]:
    if not v or v.upper() == "NA":
        return None
    cleaned = re.sub(r"[^0-9.]", "", v)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def scrape_all_active_tenders() -> List[Dict]:
    """
    Scrape ALL active tenders from Uttarakhand portal using pure HTTP.
    Returns list of tender dicts.
    """
    client = _make_client()
    all_tenders = []

    try:
        # Step 1: Load listing page
        logger.info("[UK-Sync] Loading portal...")
        r = client.get(ACTIVE_TENDERS_URL)
        soup = BeautifulSoup(r.text, "html.parser")

        # Step 2: Solve CAPTCHA (just submit with no Tender ID to get all)
        logger.info("[UK-Sync] Solving CAPTCHA...")
        solved = False
        for attempt in range(6):
            cb = _get_captcha_bytes(soup)
            if not cb:
                logger.warning("[UK-Sync] No captcha image")
                break
            sol = solve_captcha_image(cb)
            if not sol:
                continue
            logger.info(f"[UK-Sync] CAPTCHA attempt {attempt + 1}: '{sol}'")

            data = _get_form_data(soup)
            if not data:
                break
            data["TenderId"] = ""
            data["TenderTitle"] = ""
            data["size"] = "3"  # "3" = All (radio button for page size)
            data["captchaText"] = sol
            data["submitname"] = "Search"

            r2 = client.post(f"{BASE_URL}/nicgep/app", data=data)
            soup2 = BeautifulSoup(r2.text, "html.parser")

            # Check: did we get tender results? Look for the listing table
            has_table = soup2.find("table", {"id": "table"}) is not None
            has_invalid = "Invalid Captcha" in r2.text

            if has_invalid or not has_table:
                logger.info(f"[UK-Sync] CAPTCHA rejected (attempt {attempt + 1}, table={has_table})")
                soup = soup2
                continue

            soup = soup2
            solved = True
            logger.info(f"[UK-Sync] CAPTCHA solved, got listing table")
            break

        if not solved:
            logger.error("[UK-Sync] CAPTCHA failed after all attempts")
            return []

        # Step 3: Parse all pages
        page_num = 1
        while True:
            logger.info(f"[UK-Sync] Parsing page {page_num}...")
            tenders_on_page = _parse_tender_table(soup)
            all_tenders.extend(tenders_on_page)
            logger.info(f"[UK-Sync] Page {page_num}: {len(tenders_on_page)} tenders (total: {len(all_tenders)})")

            if len(tenders_on_page) == 0:
                break

            # Find "Next" link
            next_link = None
            for a in soup.find_all("a"):
                text = a.get_text(strip=True)
                if text in ("Next >", "Next>", "Next"):
                    href = a.get("href", "")
                    if href:
                        next_link = href if href.startswith("http") else BASE_URL + href
                        break

            if not next_link:
                logger.info("[UK-Sync] No more pages")
                break

            r3 = client.get(next_link)
            soup = BeautifulSoup(r3.text, "html.parser")
            page_num += 1

            if page_num > 100:  # safety limit
                break

        logger.info(f"[UK-Sync] Total scraped: {len(all_tenders)} tenders")
        return all_tenders

    except Exception as e:
        logger.error(f"[UK-Sync] Scrape failed: {e}", exc_info=True)
        return all_tenders
    finally:
        client.close()


def _parse_tender_table(soup: BeautifulSoup) -> List[Dict]:
    """Parse tender rows from the listing table."""
    tenders = []

    # Find the main table
    table = soup.find("table", {"id": "table"})
    if not table:
        tables = soup.find_all("table", class_="list_table")
        table = tables[0] if tables else None
    if not table:
        return []

    rows = table.find_all("tr")[1:]  # skip header

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        try:
            pub_date_str = cells[1].get_text(strip=True)
            close_date_str = cells[2].get_text(strip=True)
            open_date_str = cells[3].get_text(strip=True)

            title_cell = cells[4]
            org_text = cells[5].get_text(strip=True)
            value_text = cells[6].get_text(strip=True) if len(cells) > 6 else ""

            # Title and link
            link = title_cell.find("a")
            title = link.get_text(strip=True) if link else title_cell.get_text(strip=True)
            href = ""
            if link and link.get("href"):
                h = link["href"]
                href = h if h.startswith("http") else BASE_URL + h

            if len(title) < 10:
                continue

            # Extract IDs
            full_text = title_cell.get_text(strip=True)
            tid_match = re.search(r"(\d{4}_\w+_\d+_\d+)", full_text)
            tender_id = tid_match.group(1) if tid_match else None

            sid_match = re.search(r"id=(\d+)", href)
            source_id = sid_match.group(1) if sid_match else f"uk_{abs(hash(title)) % 10**8}"

            tenders.append({
                "source_id": source_id,
                "tender_id": tender_id,
                "title": title[:1000],
                "source_url": href,
                "organization": org_text[:500],
                "department": org_text[:500],
                "state": "Uttarakhand",
                "publication_date": _parse_date(pub_date_str),
                "bid_close_date": _parse_date(close_date_str),
                "bid_open_date": _parse_date(open_date_str),
                "tender_value_str": value_text,
                "tender_value": _parse_value(value_text),
            })
        except Exception as e:
            logger.warning(f"[UK-Sync] Row parse error: {e}")
            continue

    return tenders


async def sync_tenders_to_db(db: AsyncSession, scraped: List[Dict]) -> Dict:
    """
    Upsert scraped tenders into the database.
    
    Returns summary: {new, updated, unchanged, closed, errors}
    """
    summary = {"new": 0, "updated": 0, "unchanged": 0, "closed": 0, "errors": 0, "details": []}

    if not scraped:
        return summary

    # Get all existing UK tenders from DB
    result = await db.execute(sql_text(
        "SELECT id, source_id, tender_id, title, bid_close_date, bid_open_date, "
        "tender_value_estimated, organization, status FROM tenders WHERE source = 'UTTARAKHAND'"
    ))
    existing = {}
    existing_by_title = {}
    for row in result.fetchall():
        existing[row[1]] = {  # key by source_id
            "id": row[0], "source_id": row[1], "tender_id": row[2],
            "title": row[3], "bid_close_date": row[4], "bid_open_date": row[5],
            "tender_value_estimated": row[6], "organization": row[7], "status": row[8],
        }
        existing_by_title[row[3][:200]] = existing[row[1]]

    # Track which source_ids are still active on portal
    active_source_ids = set()

    for t in scraped:
        sid = t["source_id"]
        active_source_ids.add(sid)

        # Match by source_id first, then by title
        db_tender = existing.get(sid) or existing_by_title.get(t["title"][:200])

        if db_tender:
            # Existing tender — check for updates
            changes = []
            update_fields = {}

            # Check bid_close_date change (corrigendum indicator)
            new_close = t.get("bid_close_date")
            old_close = db_tender["bid_close_date"]
            if new_close and old_close:
                # Compare without timezone
                old_naive = old_close.replace(tzinfo=None) if hasattr(old_close, 'replace') else old_close
                if new_close != old_naive:
                    changes.append(f"bid_close_date: {old_close} → {new_close}")
                    update_fields["bid_close_date"] = new_close

            # Check bid_open_date change
            new_open = t.get("bid_open_date")
            old_open = db_tender["bid_open_date"]
            if new_open and old_open:
                old_naive = old_open.replace(tzinfo=None) if hasattr(old_open, 'replace') else old_open
                if new_open != old_naive:
                    changes.append(f"bid_open_date: {old_open} → {new_open}")
                    update_fields["bid_open_date"] = new_open

            # Check tender_value change
            new_val = t.get("tender_value")
            old_val = float(db_tender["tender_value_estimated"]) if db_tender["tender_value_estimated"] else None
            if new_val and old_val and abs(new_val - old_val) > 1:
                changes.append(f"value: {old_val} → {new_val}")
                update_fields["tender_value_estimated"] = new_val

            # Check tender_id (NIT) — fill if missing
            if t.get("tender_id") and not db_tender.get("tender_id"):
                update_fields["tender_id"] = t["tender_id"]

            # Reactivate if was closed but now appears active again
            if db_tender["status"] and db_tender["status"].upper() != "ACTIVE":
                changes.append(f"status: {db_tender['status']} → ACTIVE")
                update_fields["status"] = "ACTIVE"

            if update_fields:
                # Build UPDATE SQL
                set_clauses = ", ".join(f"{k} = :{k}" for k in update_fields)
                set_clauses += ", updated_at = NOW()"
                update_fields["tid"] = str(db_tender["id"])

                try:
                    await db.execute(sql_text("SAVEPOINT tender_update"))
                    await db.execute(sql_text(
                        f"UPDATE tenders SET {set_clauses} WHERE id = :tid"
                    ), update_fields)

                    summary["updated"] += 1
                    change_desc = f"{t.get('tender_id', sid)}: {', '.join(changes)}"
                    summary["details"].append({"type": "updated", "tender_id": t.get("tender_id", sid), "changes": changes})
                    logger.info(f"[UK-Sync] Updated: {change_desc}")

                    # If date changed, record corrigendum
                    if any("bid_close_date" in c or "bid_open_date" in c for c in changes):
                        try:
                            await db.execute(sql_text("""
                                INSERT INTO corrigenda (id, tender_id, corrigendum_number, published_date, description)
                                VALUES (:cid, :tid, 
                                    COALESCE((SELECT MAX(corrigendum_number) FROM corrigenda WHERE tender_id = :tid), 0) + 1,
                                    NOW(), :desc)
                            """), {
                                "cid": str(uuid.uuid4()),
                                "tid": str(db_tender["id"]),
                                "desc": f"Auto-detected date change: {', '.join(changes)}",
                            })
                        except Exception as e:
                            logger.warning(f"[UK-Sync] Corrigendum insert failed: {e}")
                    await db.execute(sql_text("RELEASE SAVEPOINT tender_update"))
                except Exception as e:
                    await db.execute(sql_text("ROLLBACK TO SAVEPOINT tender_update"))
                    logger.error(f"[UK-Sync] Update failed for {sid}: {e}")
                    summary["errors"] += 1
            else:
                summary["unchanged"] += 1
        else:
            # New tender — INSERT
            try:
                # Use SAVEPOINT so a single failure doesn't abort the whole transaction
                await db.execute(sql_text("SAVEPOINT tender_insert"))
                await db.execute(sql_text("""
                    INSERT INTO tenders (id, title, source, source_id, source_url, tender_id,
                        organization, department, state, status, tender_type,
                        publication_date, bid_close_date, bid_open_date,
                        tender_value_estimated, parsed_quality_score, created_at, updated_at)
                    VALUES (:id, :title, 'UTTARAKHAND', :sid, :url, :tid,
                        :org, :org, 'Uttarakhand', 'ACTIVE', 'OPEN_TENDER',
                        :pub, :close, :open, :val, 0.5, NOW(), NOW())
                """), {
                    "id": str(uuid.uuid4()),
                    "title": t["title"],
                    "sid": t["source_id"],
                    "url": t["source_url"],
                    "tid": t.get("tender_id"),
                    "org": t.get("organization"),
                    "pub": t.get("publication_date"),
                    "close": t.get("bid_close_date"),
                    "open": t.get("bid_open_date"),
                    "val": t.get("tender_value"),
                })
                await db.execute(sql_text("RELEASE SAVEPOINT tender_insert"))
                summary["new"] += 1
                summary["details"].append({"type": "new", "tender_id": t.get("tender_id", t["source_id"]), "title": t["title"][:100]})
                logger.info(f"[UK-Sync] New: {t.get('tender_id', t['source_id'])} - {t['title'][:80]}")
            except Exception as e:
                await db.execute(sql_text("ROLLBACK TO SAVEPOINT tender_insert"))
                if "ix_tenders_source_source_id" in str(e) or "unique" in str(e).lower():
                    summary["unchanged"] += 1
                else:
                    logger.error(f"[UK-Sync] Insert failed: {e}")
                    summary["errors"] += 1

    # Step: Mark tenders no longer on portal as CLOSED
    for sid, db_t in existing.items():
        if sid not in active_source_ids and db_t["status"] and db_t["status"].upper() == "ACTIVE":
            try:
                await db.execute(sql_text(
                    "UPDATE tenders SET status = 'CLOSED', updated_at = NOW() WHERE id = :tid"
                ), {"tid": str(db_t["id"])})
                summary["closed"] += 1
                summary["details"].append({"type": "closed", "tender_id": db_t.get("tender_id", sid)})
                logger.info(f"[UK-Sync] Closed: {db_t.get('tender_id', sid)}")
            except Exception as e:
                logger.error(f"[UK-Sync] Close failed for {sid}: {e}")

    await db.commit()
    return summary


async def run_sync() -> Dict:
    """
    Full sync: scrape + upsert + return summary.
    Called by the cron API endpoint.
    """
    from backend.database import async_session

    logger.info("[UK-Sync] Starting full sync...")
    start = datetime.now()

    # Scrape (blocking HTTP, run in thread)
    import asyncio
    scraped = await asyncio.to_thread(scrape_all_active_tenders)

    if not scraped:
        return {"success": False, "error": "Scrape returned 0 tenders", "duration_s": 0}

    # Save raw scrape for audit
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    ts = start.strftime("%Y%m%d_%H%M%S")
    with open(STORAGE_DIR / f"uk_sync_{ts}.json", "w") as f:
        json.dump(scraped, f, indent=2, default=str)

    # Upsert to DB
    async with async_session() as db:
        summary = await sync_tenders_to_db(db, scraped)

    duration = (datetime.now() - start).total_seconds()
    summary["success"] = True
    summary["scraped_count"] = len(scraped)
    summary["duration_s"] = round(duration, 1)
    summary["timestamp"] = start.isoformat()

    logger.info(
        f"[UK-Sync] Complete in {duration:.1f}s: "
        f"{summary['new']} new, {summary['updated']} updated, "
        f"{summary['unchanged']} unchanged, {summary['closed']} closed, "
        f"{summary['errors']} errors"
    )

    return summary
