#!/usr/bin/env python3
"""One-shot scraping script — no Celery needed.
Usage: python3 scrape_now.py [--days-gem 3] [--days-state 30]
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.config import get_settings
from backend.ingestion.connector_registry import get_connector
from backend.ingestion.parser.normalizer import normalize_state, normalize_title, clean_department
from backend.services.dedup import generate_fingerprint

settings = get_settings()

# Sync DB
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.DATABASE_URL_SYNC)
Session = sessionmaker(bind=engine)


def guess_mime(filename: str) -> str:
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    return {
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'zip': 'application/zip',
    }.get(ext, 'application/octet-stream')


def calc_quality(raw) -> float:
    fields = [raw.description, raw.category, getattr(raw, 'tender_value', None),
              getattr(raw, 'emd_amount', None), getattr(raw, 'document_fee', None),
              raw.contact_person, raw.contact_email,
              raw.bid_open_date, raw.pre_bid_meeting_date]
    filled = sum(1 for f in fields if f)
    return round(filled / len(fields), 2)


async def scrape_source(source: str, max_age_days: int):
    """Scrape a single source and insert new tenders."""
    print(f"\n{'='*60}")
    print(f"  Scraping: {source.upper()} (max age: {max_age_days} days)")
    print(f"{'='*60}")

    connector = get_connector(source)
    stats = {"source": source, "fetched": 0, "new": 0, "duplicate": 0, "errors": 0, "docs": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    try:
        print(f"  Fetching tender list...")
        raw_tenders = await connector.fetch_tenders()
        stats["fetched"] = len(raw_tenders)
        print(f"  Got {len(raw_tenders)} tenders from {source}")

        session = Session()
        try:
            for i, raw in enumerate(raw_tenders):
                try:
                    # Filter by date if available
                    pub_date = getattr(raw, 'publication_date', None)
                    if pub_date:
                        # Ensure both are timezone-aware for comparison
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        if pub_date < cutoff:
                            continue

                    fp = generate_fingerprint(
                        raw.tender_id, raw.title, raw.department,
                        str(raw.bid_close_date) if raw.bid_close_date else None,
                    )

                    existing = session.execute(
                        text("SELECT id FROM tenders WHERE fingerprint = :fp"), {"fp": fp}
                    ).fetchone()

                    if existing:
                        stats["duplicate"] += 1
                        continue

                    # Try detail fetch (skip for Selenium sources to save memory)
                    if source in ('gem',) and hasattr(connector, 'fetch_tender_detail') and (raw.source_id or raw.tender_id):
                        try:
                            detail = await connector.fetch_tender_detail(raw.source_id or raw.tender_id)
                            if detail:
                                for field in ['description', 'category', 'tender_type', 'tender_value',
                                              'emd_amount', 'document_fee', 'bid_open_date',
                                              'pre_bid_meeting_date', 'pre_bid_meeting_venue',
                                              'contact_person', 'contact_email', 'contact_phone',
                                              'eligibility', 'raw_text']:
                                    dv = getattr(detail, field, None)
                                    if dv and not getattr(raw, field, None):
                                        setattr(raw, field, dv)
                                if hasattr(detail, 'document_urls') and detail.document_urls:
                                    existing_urls = set(getattr(raw, 'document_urls', []) or [])
                                    for url in detail.document_urls:
                                        if url not in existing_urls:
                                            if not hasattr(raw, 'document_urls') or not raw.document_urls:
                                                raw.document_urls = []
                                            raw.document_urls.append(url)
                        except Exception as e:
                            pass  # detail fetch is optional

                    # Map tender_type to DB enum (uppercase)
                    raw_type = (getattr(raw, 'tender_type', None) or 'open_tender').upper()
                    valid_types = {'OPEN_TENDER', 'NIT', 'RFP', 'EOI', 'AUCTION', 'RFQ', 'LIMITED_TENDER', 'OTHER'}
                    if raw_type not in valid_types:
                        raw_type = 'OTHER'

                    result = session.execute(
                        text("""
                            INSERT INTO tenders (
                                id, source, source_url, source_id, tender_id, title, description,
                                department, organization, state, category, tender_type,
                                tender_value_estimated, emd_amount, document_fee,
                                publication_date, bid_open_date, bid_close_date,
                                pre_bid_meeting_date, pre_bid_meeting_venue,
                                contact_person, contact_email, contact_phone,
                                eligibility_criteria,
                                status, raw_text, fingerprint, parsed_quality_score, tender_stage
                            ) VALUES (
                                gen_random_uuid(), :source, :source_url, :source_id, :tender_id,
                                :title, :description, :department, :organization, :state,
                                :category, :tender_type, :tender_value, :emd, :doc_fee,
                                :pub_date, :bid_open, :close_date,
                                :prebid_date, :prebid_venue,
                                :contact_person, :contact_email, :contact_phone,
                                :eligibility,
                                'ACTIVE', :raw_text, :fingerprint, :quality, 'bidding'
                            ) RETURNING id
                        """),
                        {
                            "source": source.upper(),
                            "source_url": raw.source_url,
                            "source_id": raw.source_id,
                            "tender_id": raw.tender_id,
                            "title": normalize_title(raw.title),
                            "description": getattr(raw, 'description', None),
                            "department": clean_department(raw.department),
                            "organization": raw.organization,
                            "state": normalize_state(raw.state),
                            "category": getattr(raw, 'category', None),
                            "tender_type": raw_type,
                            "tender_value": getattr(raw, 'tender_value', None),
                            "emd": getattr(raw, 'emd_amount', None),
                            "doc_fee": getattr(raw, 'document_fee', None),
                            "pub_date": getattr(raw, 'publication_date', None),
                            "bid_open": getattr(raw, 'bid_open_date', None),
                            "close_date": raw.bid_close_date,
                            "prebid_date": getattr(raw, 'pre_bid_meeting_date', None),
                            "prebid_venue": getattr(raw, 'pre_bid_meeting_venue', None),
                            "contact_person": getattr(raw, 'contact_person', None),
                            "contact_email": getattr(raw, 'contact_email', None),
                            "contact_phone": getattr(raw, 'contact_phone', None),
                            "eligibility": str(getattr(raw, 'eligibility', None)) if getattr(raw, 'eligibility', None) else None,
                            "raw_text": getattr(raw, 'raw_text', None),
                            "fingerprint": fp,
                            "quality": calc_quality(raw),
                        }
                    )
                    row = result.fetchone()
                    tender_db_id = str(row[0]) if row else None
                    stats["new"] += 1

                    # Download documents
                    doc_urls = getattr(raw, 'document_urls', None) or []
                    if doc_urls and tender_db_id:
                        try:
                            doc_dir = Path(settings.DOCUMENT_STORAGE_PATH) / tender_db_id
                            doc_dir.mkdir(parents=True, exist_ok=True)
                            if hasattr(connector, 'download_documents'):
                                downloaded = await connector.download_documents(doc_urls, doc_dir)
                                for doc_path in downloaded:
                                    session.execute(
                                        text("""
                                            INSERT INTO tender_documents (id, tender_id, filename, file_path, file_size, mime_type)
                                            VALUES (gen_random_uuid(), :tid, :fname, :fpath, :fsize, :mime)
                                        """),
                                        {
                                            "tid": tender_db_id,
                                            "fname": doc_path.name,
                                            "fpath": str(doc_path),
                                            "fsize": doc_path.stat().st_size,
                                            "mime": guess_mime(doc_path.name),
                                        }
                                    )
                                    stats["docs"] += 1
                        except Exception as e:
                            print(f"    Doc download error: {e}")

                    if stats["new"] % 10 == 0:
                        print(f"    Progress: {stats['new']} new, {stats['duplicate']} dup, {stats['errors']} err")

                except Exception as e:
                    session.rollback()
                    stats["errors"] += 1
                    if stats["errors"] <= 3:
                        print(f"    Error: {e}")

            session.commit()
        finally:
            session.close()

    except Exception as e:
        print(f"  FAILED: {e}")
        stats["errors"] += 1
    finally:
        try:
            await connector.close()
        except Exception:
            pass
        # Force garbage collection to free Selenium memory
        import gc
        gc.collect()

    print(f"  Result: {stats['new']} new | {stats['duplicate']} dup | {stats['docs']} docs | {stats['errors']} errors")
    return stats


async def update_statuses():
    """Update tender statuses and stages based on dates."""
    print(f"\n{'='*60}")
    print(f"  Updating tender statuses & stages")
    print(f"{'='*60}")

    session = Session()
    try:
        # Close expired tenders
        r1 = session.execute(text("""
            UPDATE tenders SET status = 'CLOSED', tender_stage = 'technical_bid_opening'
            WHERE status::text = 'ACTIVE' AND bid_close_date < NOW() AND bid_close_date IS NOT NULL
            AND (tender_stage = 'bidding' OR tender_stage IS NULL)
        """))
        print(f"  Closed expired: {r1.rowcount} tenders")

        # Progress stages
        r2 = session.execute(text("""
            UPDATE tenders SET tender_stage = 'technical_evaluation'
            WHERE status::text = 'CLOSED'
            AND bid_close_date < NOW() - INTERVAL '7 days'
            AND bid_close_date > NOW() - INTERVAL '30 days'
            AND tender_stage = 'technical_bid_opening'
        """))
        print(f"  Tech evaluation: {r2.rowcount}")

        r3 = session.execute(text("""
            UPDATE tenders SET tender_stage = 'financial_bid_opening'
            WHERE status::text = 'CLOSED'
            AND bid_close_date < NOW() - INTERVAL '30 days'
            AND bid_close_date > NOW() - INTERVAL '60 days'
            AND tender_stage = 'technical_evaluation'
        """))
        print(f"  Financial bid opening: {r3.rowcount}")

        r4 = session.execute(text("""
            UPDATE tenders SET tender_stage = 'financial_evaluation'
            WHERE status::text = 'CLOSED'
            AND bid_close_date < NOW() - INTERVAL '60 days'
            AND tender_stage = 'financial_bid_opening'
        """))
        print(f"  Financial evaluation: {r4.rowcount}")

        session.commit()
        print("  Done")
    except Exception as e:
        print(f"  Error: {e}")
        session.rollback()
    finally:
        session.close()


async def main():
    parser = argparse.ArgumentParser(description='TenderWatch Scraper')
    parser.add_argument('--days-gem', type=int, default=3, help='Days to look back for GeM/CPPP (default: 3)')
    parser.add_argument('--days-state', type=int, default=30, help='Days to look back for state portals (default: 30)')
    parser.add_argument('--sources', type=str, default='all', help='Comma-separated sources or "all" (default: all)')
    parser.add_argument('--update-status', action='store_true', default=True, help='Update tender statuses after scraping')
    parser.add_argument('--no-update-status', action='store_true', help='Skip status update')
    args = parser.parse_args()

    central_sources = ['gem', 'cppp']
    state_sources = ['up', 'maharashtra', 'uttarakhand', 'haryana', 'mp']

    if args.sources == 'all':
        sources_to_run = central_sources + state_sources
    else:
        sources_to_run = [s.strip() for s in args.sources.split(',')]

    print(f"\n{'#'*60}")
    print(f"  TenderWatch Scraper")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Sources: {', '.join(sources_to_run)}")
    print(f"  GeM/CPPP lookback: {args.days_gem} days")
    print(f"  State lookback: {args.days_state} days")
    print(f"{'#'*60}")

    all_stats = {}
    for source in sources_to_run:
        days = args.days_gem if source in central_sources else args.days_state
        try:
            stats = await scrape_source(source, days)
            all_stats[source] = stats
        except Exception as e:
            print(f"  {source} CRASHED: {e}")
            all_stats[source] = {"error": str(e)}

    # Update statuses
    if not args.no_update_status:
        await update_statuses()

    # Summary
    print(f"\n{'#'*60}")
    print(f"  SUMMARY")
    print(f"{'#'*60}")
    total_new = sum(s.get('new', 0) for s in all_stats.values())
    total_docs = sum(s.get('docs', 0) for s in all_stats.values())
    for src, s in all_stats.items():
        if 'error' in s and isinstance(s['error'], str):
            print(f"  {src:15s} ERROR: {s['error']}")
        else:
            print(f"  {src:15s} fetched={s.get('fetched',0):4d}  new={s.get('new',0):4d}  dup={s.get('duplicate',0):4d}  docs={s.get('docs',0):3d}  err={s.get('errors',0):2d}")
    print(f"\n  TOTAL: {total_new} new tenders, {total_docs} documents")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    # Force unbuffered output
    import functools
    print = functools.partial(print, flush=True)
    asyncio.run(main())
