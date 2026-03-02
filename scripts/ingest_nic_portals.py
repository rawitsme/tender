"""Ingest tenders from CPPP + all NIC state portals using 2Captcha.

Usage: PYTHONPATH=. python3 scripts/ingest_nic_portals.py
"""
import asyncio
import logging
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import uuid
from sqlalchemy import create_engine, text
from datetime import datetime

from backend.ingestion.connectors.cppp_selenium import CPPPSeleniumConnector
from backend.ingestion.connectors.nic_selenium import NICSeleniumConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nic_ingest")

DB_URL = os.getenv("DATABASE_URL_SYNC", "postgresql://tender:tender_dev_2026@localhost:5432/tender_portal")
engine = create_engine(DB_URL)

# key -> (DB enum value, display label)
PORTALS = [
    ("cppp",        "CPPP",         "CPPP (Central)"),
    ("up",          "UP",           "Uttar Pradesh"),
    ("maharashtra", "MAHARASHTRA",  "Maharashtra"),
    ("uttarakhand", "UTTARAKHAND",  "Uttarakhand"),
    ("haryana",     "HARYANA",      "Haryana"),
    ("mp",          "MP",           "Madhya Pradesh"),
]

# Junk titles to filter out
JUNK_TITLES = {"active tenders", "tenders", "search", "corrigendum", "results of tenders", ""}


def is_valid_tender(t) -> bool:
    """Filter out junk rows (nav elements, headers, etc.)."""
    title = (t.title or "").strip().lower()
    if title in JUNK_TITLES or len(title) < 15:
        return False
    if "search |" in title or "active tenders" in title.lower():
        return False
    return True


def save_tenders(tenders, db_source):
    """Save tenders to DB, skip duplicates. Each row in its own transaction."""
    saved = 0
    skipped = 0
    for t in tenders:
        try:
            with engine.begin() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM tenders WHERE source_id = :sid LIMIT 1"),
                    {"sid": t.source_id}
                ).fetchone()
                if exists:
                    skipped += 1
                    continue
                
                conn.execute(text("""
                    INSERT INTO tenders (
                        id, source, source_id, source_url, tender_id, title,
                        state, organization, department,
                        publication_date, bid_close_date,
                        raw_text, status, created_at
                    ) VALUES (
                        :id, :source, :source_id, :source_url, :tender_id, :title,
                        :state, :org, :dept,
                        :pub_date, :close_date,
                        :raw_text, 'ACTIVE', NOW()
                    )
                """), {
                    "id": str(uuid.uuid4()),
                    "source": db_source,
                    "source_id": t.source_id,
                    "source_url": t.source_url or "",
                    "tender_id": t.tender_id or "",
                    "title": (t.title or "")[:2000],
                    "state": t.state or "",
                    "org": (t.organization or "")[:1000],
                    "dept": (getattr(t, 'department', None) or "")[:1000],
                    "pub_date": t.publication_date,
                    "close_date": t.bid_close_date,
                    "raw_text": (t.raw_text or "")[:50000],
                })
                saved += 1
        except Exception as e:
            logger.warning(f"  Skip bad record ({t.source_id}): {e}")
            skipped += 1
    
    return saved, skipped


async def ingest_portal(key, db_source, label):
    logger.info(f"\n{'='*60}")
    logger.info(f"🔍 Starting: {label} ({key})")
    logger.info(f"{'='*60}")
    
    try:
        if key == "cppp":
            connector = CPPPSeleniumConnector()
        else:
            connector = NICSeleniumConnector(key)
        
        tenders = await connector.fetch_tenders()
        logger.info(f"  Raw: {len(tenders)} rows from {label}")
        
        # Filter junk
        tenders = [t for t in tenders if is_valid_tender(t)]
        logger.info(f"  After filtering: {len(tenders)} valid tenders")
        
        if tenders:
            saved, skipped = save_tenders(tenders, db_source)
            logger.info(f"  ✅ {label}: {saved} new, {skipped} skipped/dupes")
        else:
            logger.warning(f"  ⚠️ {label}: No valid tenders")
        
        await connector.close()
        return len(tenders), saved if tenders else 0
        
    except Exception as e:
        logger.error(f"  ❌ {label} FAILED: {e}")
        traceback.print_exc()
        return 0, 0


async def main():
    with engine.connect() as conn:
        count_before = conn.execute(text("SELECT COUNT(*) FROM tenders")).scalar()
    logger.info(f"DB has {count_before} tenders before ingestion")
    
    total_fetched = 0
    total_saved = 0
    results = []
    
    for key, db_source, label in PORTALS:
        fetched, saved = await ingest_portal(key, db_source, label)
        total_fetched += fetched
        total_saved += saved
        results.append((label, fetched, saved))
    
    with engine.connect() as conn:
        count_after = conn.execute(text("SELECT COUNT(*) FROM tenders")).scalar()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 INGESTION COMPLETE")
    logger.info(f"{'='*60}")
    for label, fetched, saved in results:
        status = "✅" if fetched > 0 else "❌"
        logger.info(f"  {status} {label}: {fetched} fetched, {saved} saved")
    logger.info(f"  Total: {total_fetched} fetched, {total_saved} new tenders saved")
    logger.info(f"  DB: {count_before} → {count_after} tenders")


if __name__ == "__main__":
    asyncio.run(main())
