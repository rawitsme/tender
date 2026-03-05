#!/usr/bin/env python3
"""Populate database with targeted tender counts per source.

Usage: python3 populate_db.py
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.config import get_settings
from backend.ingestion.connector_registry import get_connector
from backend.services.dedup import generate_fingerprint

settings = get_settings()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.DATABASE_URL_SYNC)
Session = sessionmaker(bind=engine)


def get_existing_count(source: str) -> int:
    s = Session()
    result = s.execute(text("SELECT COUNT(*) FROM tenders WHERE source = :src"), {"src": source.upper()}).scalar()
    s.close()
    return result


def calc_quality(raw) -> float:
    fields = [raw.description, raw.category, getattr(raw, 'tender_value', None),
              getattr(raw, 'emd_amount', None), getattr(raw, 'document_fee', None),
              raw.contact_person, raw.contact_email,
              raw.bid_open_date, raw.pre_bid_meeting_date]
    filled = sum(1 for f in fields if f)
    return round(filled / len(fields), 2)


def insert_tenders(raw_tenders, source_label: str, limit: int = None):
    """Insert tenders into DB, respecting limit. Returns (new, duplicate) counts."""
    session = Session()
    new_count = 0
    dup_count = 0
    
    for raw in raw_tenders:
        if limit and new_count >= limit:
            break
        try:
            fp = generate_fingerprint(
                getattr(raw, 'tender_id', None),
                raw.title or "",
                raw.department,
                str(raw.bid_close_date) if raw.bid_close_date else None
            )
            exists = session.execute(
                text("SELECT id FROM tenders WHERE fingerprint = :fp"), {"fp": fp}
            ).fetchone()
            
            if exists:
                dup_count += 1
                continue

            # Determine state
            state = getattr(raw, 'state', None) or 'Central'
            source_upper = source_label.upper()
            
            session.execute(text("""
                INSERT INTO tenders (
                    id, title, description, source, source_url, source_id, tender_id,
                    state, category, department, organization, tender_type,
                    publication_date, bid_close_date, bid_open_date,
                    tender_value_estimated, emd_amount, document_fee,
                    contact_person, contact_email, contact_phone,
                    pre_bid_meeting_date, status, fingerprint, parsed_quality_score,
                    raw_text, created_at, updated_at
                ) VALUES (
                    :id, :title, :description, :source, :source_url, :source_id, :tender_id,
                    :state, :category, :department, :organization, :tender_type,
                    :publication_date, :bid_close_date, :bid_open_date,
                    :tender_value_estimated, :emd_amount, :document_fee,
                    :contact_person, :contact_email, :contact_phone,
                    :pre_bid_meeting_date, :status, :fingerprint, :parsed_quality_score,
                    :raw_text, :created_at, :updated_at
                )
            """), {
                "id": str(uuid.uuid4()),
                "title": (raw.title or "")[:2000],
                "description": raw.description,
                "source": source_upper,
                "source_url": raw.source_url,
                "source_id": raw.source_id,
                "tender_id": getattr(raw, 'tender_id', None),
                "state": state,
                "category": raw.category,
                "department": raw.department,
                "organization": raw.organization,
                "tender_type": (getattr(raw, 'tender_type', None) or '').upper() or None,
                "publication_date": getattr(raw, 'publication_date', None),
                "bid_close_date": raw.bid_close_date,
                "bid_open_date": raw.bid_open_date,
                "tender_value_estimated": getattr(raw, 'tender_value', None),
                "emd_amount": getattr(raw, 'emd_amount', None),
                "document_fee": getattr(raw, 'document_fee', None),
                "contact_person": raw.contact_person,
                "contact_email": raw.contact_email,
                "contact_phone": getattr(raw, 'contact_phone', None),
                "pre_bid_meeting_date": raw.pre_bid_meeting_date,
                "status": "ACTIVE",
                "fingerprint": fp,
                "parsed_quality_score": calc_quality(raw),
                "raw_text": getattr(raw, 'raw_text', None),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
            new_count += 1
            
        except Exception as e:
            print(f"    ⚠️ Error inserting tender: {e}")
            session.rollback()
            continue
    
    session.commit()
    session.close()
    return new_count, dup_count


async def scrape_gem_multi_page(target: int = 50) -> list:
    """Fetch multiple pages from GEM to get target number of tenders."""
    from backend.ingestion.connectors.gem import GeMConnector
    all_tenders = []
    page = 1
    max_pages = 10  # safety limit
    
    while len(all_tenders) < target and page <= max_pages:
        print(f"  📄 Fetching GEM page {page}...")
        connector = GeMConnector()
        tenders = await connector.fetch_tenders(page=page)
        if not tenders:
            print(f"  ℹ️ No more results on page {page}")
            break
        all_tenders.extend(tenders)
        print(f"  ✅ Page {page}: got {len(tenders)} tenders (total: {len(all_tenders)})")
        page += 1
    
    return all_tenders


async def main():
    print("=" * 60)
    print("  🏛️ TenderWatch Database Population")
    print("=" * 60)
    
    # Current state
    print("\n📊 Current database:")
    for src in ["GEM", "CPPP", "UTTARAKHAND", "UP", "MAHARASHTRA", "HARYANA", "MP"]:
        count = get_existing_count(src)
        if count > 0:
            print(f"  {src}: {count}")
    
    # --- TARGETS ---
    targets = {
        "gem": {"target": 50, "label": "GEM"},
        "cppp": {"target": 50, "label": "CPPP"},
        "uttarakhand": {"target": None, "label": "UTTARAKHAND"},  # All active
        "up": {"target": 1, "label": "UP"},
        "mp": {"target": 1, "label": "MP"},
        "haryana": {"target": 1, "label": "HARYANA"},
        "maharashtra": {"target": 1, "label": "MAHARASHTRA"},
    }
    
    results = {}
    
    # 1. GEM - multi-page
    print("\n" + "=" * 60)
    print("  🛒 Scraping GEM (target: 50 tenders)")
    print("=" * 60)
    existing = get_existing_count("GEM")
    needed = max(0, 50 - existing)
    if needed > 0:
        gem_tenders = await scrape_gem_multi_page(target=needed + 20)  # fetch extra for dedup
        new, dup = insert_tenders(gem_tenders, "GEM", limit=needed)
        results["GEM"] = {"new": new, "dup": dup, "total": get_existing_count("GEM")}
        print(f"  ✅ GEM: +{new} new, {dup} duplicates (total: {results['GEM']['total']})")
    else:
        print(f"  ℹ️ GEM already has {existing} tenders, skipping")
        results["GEM"] = {"new": 0, "dup": 0, "total": existing}
    
    # 2. CPPP
    print("\n" + "=" * 60)
    print("  🏛️ Scraping CPPP (target: 50 tenders)")
    print("=" * 60)
    existing = get_existing_count("CPPP")
    needed = max(0, 50 - existing)
    if needed > 0:
        connector = get_connector("cppp")
        tenders = await connector.fetch_tenders()
        print(f"  📥 Fetched {len(tenders)} tenders from CPPP")
        new, dup = insert_tenders(tenders, "CPPP", limit=needed)
        results["CPPP"] = {"new": new, "dup": dup, "total": get_existing_count("CPPP")}
        print(f"  ✅ CPPP: +{new} new, {dup} duplicates (total: {results['CPPP']['total']})")
    else:
        print(f"  ℹ️ CPPP already has {existing} tenders, skipping")
        results["CPPP"] = {"new": 0, "dup": 0, "total": existing}
    
    # 3. Uttarakhand - ALL active
    print("\n" + "=" * 60)
    print("  🏔️ Scraping Uttarakhand (ALL active tenders)")
    print("=" * 60)
    connector = get_connector("uttarakhand")
    tenders = await connector.fetch_tenders()
    print(f"  📥 Fetched {len(tenders)} tenders from Uttarakhand")
    new, dup = insert_tenders(tenders, "UTTARAKHAND")  # no limit
    results["UTTARAKHAND"] = {"new": new, "dup": dup, "total": get_existing_count("UTTARAKHAND")}
    print(f"  ✅ Uttarakhand: +{new} new, {dup} duplicates (total: {results['UTTARAKHAND']['total']})")
    
    # 4. State portals - 1 each
    for state_key, state_name in [("up", "UP"), ("mp", "MP"), ("haryana", "HARYANA"), ("maharashtra", "MAHARASHTRA")]:
        print(f"\n{'=' * 60}")
        print(f"  🗺️ Scraping {state_name} (target: 1 tender)")
        print(f"{'=' * 60}")
        existing = get_existing_count(state_name)
        if existing >= 1:
            print(f"  ℹ️ {state_name} already has {existing} tender(s), skipping")
            results[state_name] = {"new": 0, "dup": 0, "total": existing}
            continue
        
        try:
            connector = get_connector(state_key)
            tenders = await connector.fetch_tenders()
            print(f"  📥 Fetched {len(tenders)} tenders from {state_name}")
            new, dup = insert_tenders(tenders, state_name, limit=1)
            results[state_name] = {"new": new, "dup": dup, "total": get_existing_count(state_name)}
            print(f"  ✅ {state_name}: +{new} new, {dup} duplicates (total: {results[state_name]['total']})")
        except Exception as e:
            print(f"  ❌ {state_name} failed: {e}")
            results[state_name] = {"new": 0, "dup": 0, "total": 0, "error": str(e)}
    
    # Final summary
    print("\n" + "=" * 60)
    print("  📊 FINAL DATABASE SUMMARY")
    print("=" * 60)
    grand_total = 0
    for src, data in results.items():
        total = data["total"]
        grand_total += total
        status = "✅" if total > 0 else "❌"
        error = f" (Error: {data.get('error', '')})" if data.get('error') else ""
        print(f"  {status} {src}: {total} tenders (+{data['new']} new){error}")
    print(f"\n  🏛️ GRAND TOTAL: {grand_total} tenders")


if __name__ == "__main__":
    asyncio.run(main())
