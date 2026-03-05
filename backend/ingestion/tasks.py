"""Celery tasks for scheduled ingestion and processing."""

import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from celery import Celery
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Celery app
celery_app = Celery(
    "tender_portal",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    beat_schedule={
        "ingest-all-sources-every-6h": {
            "task": "backend.ingestion.tasks.run_all_connectors",
            "schedule": 6 * 60 * 60,  # 6 hours
        },
        "match-alerts-every-hour": {
            "task": "backend.ingestion.tasks.process_pending_alerts",
            "schedule": 60 * 60,  # 1 hour
        },
        "update-tender-statuses-daily": {
            "task": "backend.ingestion.tasks.update_tender_statuses",
            "schedule": 24 * 60 * 60,  # daily
        },
    },
)

# Sync DB session for Celery tasks
sync_engine = create_engine(settings.DATABASE_URL_SYNC)
SyncSession = sessionmaker(bind=sync_engine)


@celery_app.task(name="backend.ingestion.tasks.run_connector")
def run_connector(source: str):
    """Run a single connector and ingest tenders."""
    logger.info(f"Starting ingestion for source: {source}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run_connector_async(source))
        logger.info(f"Ingestion complete for {source}: {result}")
        return result
    finally:
        loop.close()


@celery_app.task(name="backend.ingestion.tasks.run_all_connectors")
def run_all_connectors():
    """Run all connectors sequentially."""
    from backend.ingestion.connector_registry import CONNECTORS, NIC_STATES
    
    all_sources = list(CONNECTORS.keys()) + NIC_STATES
    results = {}
    for source in all_sources:
        try:
            result = run_connector(source)
            results[source] = result
        except Exception as e:
            logger.error(f"Connector {source} failed: {e}")
            results[source] = {"error": str(e)}
    
    # After all ingestion, run alert matching
    try:
        process_pending_alerts()
    except Exception as e:
        logger.error(f"Alert matching failed: {e}")

    return results


async def _run_connector_async(source: str) -> dict:
    """Async implementation of connector run with detail fetching."""
    from backend.ingestion.connector_registry import get_connector
    from backend.ingestion.parser.normalizer import normalize_state, normalize_title, clean_department, normalize_date
    from backend.services.dedup import generate_fingerprint
    
    connector = get_connector(source)
    stats = {"source": source, "fetched": 0, "new": 0, "duplicate": 0, "errors": 0, "details_fetched": 0, "docs_downloaded": 0}
    new_tender_ids: List[str] = []
    
    try:
        raw_tenders = await connector.fetch_tenders()
        stats["fetched"] = len(raw_tenders)
        
        session = SyncSession()
        try:
            for raw in raw_tenders:
                try:
                    # Generate fingerprint for dedup
                    fp = generate_fingerprint(
                        raw.tender_id,
                        raw.title,
                        raw.department,
                        str(raw.bid_close_date) if raw.bid_close_date else None,
                    )
                    
                    # Check for duplicate
                    existing = session.execute(
                        text("SELECT id FROM tenders WHERE fingerprint = :fp"),
                        {"fp": fp}
                    ).fetchone()
                    
                    if existing:
                        stats["duplicate"] += 1
                        continue

                    # Try to fetch detail if connector supports it
                    detail = None
                    if raw.source_url and hasattr(connector, 'fetch_tender_detail'):
                        try:
                            source_id = raw.source_id or raw.tender_id
                            if source_id:
                                detail = await connector.fetch_tender_detail(source_id)
                                if detail:
                                    stats["details_fetched"] += 1
                                    # Merge detail into raw
                                    raw = _merge_detail(raw, detail)
                        except Exception as e:
                            logger.debug(f"Detail fetch failed for {raw.source_id}: {e}")

                    # Insert new tender
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
                                status, raw_text, fingerprint, parsed_quality_score
                            ) VALUES (
                                gen_random_uuid(), :source, :source_url, :source_id, :tender_id,
                                :title, :description, :department, :organization, :state,
                                :category, :tender_type, :tender_value, :emd, :doc_fee,
                                :pub_date, :bid_open, :close_date,
                                :prebid_date, :prebid_venue,
                                :contact_person, :contact_email, :contact_phone,
                                :eligibility,
                                'ACTIVE', :raw_text, :fingerprint, :quality
                            ) RETURNING id
                        """),
                        {
                            "source": source.upper(),
                            "source_url": raw.source_url,
                            "source_id": raw.source_id,
                            "tender_id": raw.tender_id,
                            "title": normalize_title(raw.title),
                            "description": raw.description,
                            "department": clean_department(raw.department),
                            "organization": raw.organization,
                            "state": normalize_state(raw.state),
                            "category": raw.category,
                            "tender_type": (raw.tender_type or "open_tender").upper(),
                            "tender_value": raw.tender_value,
                            "emd": raw.emd_amount,
                            "doc_fee": raw.document_fee,
                            "pub_date": raw.publication_date,
                            "bid_open": raw.bid_open_date,
                            "close_date": raw.bid_close_date,
                            "prebid_date": raw.pre_bid_meeting_date,
                            "prebid_venue": raw.pre_bid_meeting_venue,
                            "contact_person": raw.contact_person,
                            "contact_email": raw.contact_email,
                            "contact_phone": raw.contact_phone,
                            "eligibility": str(raw.eligibility) if raw.eligibility else None,
                            "raw_text": raw.raw_text,
                            "fingerprint": fp,
                            "quality": _calc_quality(raw),
                        }
                    )
                    row = result.fetchone()
                    tender_db_id = str(row[0]) if row else None
                    
                    if tender_db_id:
                        new_tender_ids.append(tender_db_id)
                    stats["new"] += 1

                    # Download documents if available
                    if raw.document_urls and tender_db_id:
                        try:
                            doc_dir = Path(settings.DOCUMENT_STORAGE_PATH) / tender_db_id
                            downloaded = await connector.download_documents(raw.document_urls, doc_dir)
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
                                        "mime": _guess_mime(doc_path.name),
                                    }
                                )
                                stats["docs_downloaded"] += 1
                        except Exception as e:
                            logger.warning(f"Doc download failed: {e}")
                    
                except Exception as e:
                    logger.warning(f"Error ingesting tender: {e}")
                    stats["errors"] += 1
                    continue
            
            session.commit()
        finally:
            session.close()

        # Auto-match new tenders against saved searches
        if new_tender_ids:
            try:
                _match_and_notify(new_tender_ids)
            except Exception as e:
                logger.error(f"Auto-matching failed: {e}")

    finally:
        await connector.close()
    
    return stats


def _merge_detail(raw, detail):
    """Merge detail data into raw tender, preferring detail values."""
    if not detail:
        return raw
    for field in ['description', 'category', 'tender_type', 'tender_value',
                  'emd_amount', 'document_fee', 'bid_open_date',
                  'pre_bid_meeting_date', 'pre_bid_meeting_venue',
                  'contact_person', 'contact_email', 'contact_phone',
                  'eligibility', 'raw_text']:
        detail_val = getattr(detail, field, None)
        if detail_val and not getattr(raw, field, None):
            setattr(raw, field, detail_val)
    # Merge document URLs
    if detail.document_urls:
        existing = set(raw.document_urls)
        for url in detail.document_urls:
            if url not in existing:
                raw.document_urls.append(url)
    return raw


def _calc_quality(raw) -> float:
    """Calculate parsed quality score based on how many fields are populated."""
    fields = [raw.description, raw.category, raw.tender_value, raw.emd_amount,
              raw.document_fee, raw.contact_person, raw.contact_email,
              raw.bid_open_date, raw.pre_bid_meeting_date]
    filled = sum(1 for f in fields if f)
    return round(filled / len(fields), 2)


def _guess_mime(filename: str) -> str:
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    return {
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'zip': 'application/zip',
    }.get(ext, 'application/octet-stream')


def _match_and_notify(new_tender_ids: List[str]):
    """Match new tenders against saved searches and send notifications."""
    from backend.services.matching import match_new_tenders_against_searches
    from backend.services.notifications import send_email, send_whatsapp, send_sms, build_tender_alert_html
    
    session = SyncSession()
    try:
        matches = match_new_tenders_against_searches(session, new_tender_ids)
        
        if not matches:
            return

        # Group matches by search
        by_search = {}
        for m in matches:
            key = m["search_id"]
            if key not in by_search:
                by_search[key] = {**m, "tender_ids": []}
            by_search[key]["tender_ids"].append(m["tender_id"])

        for search_id, info in by_search.items():
            # Get tender details for the email
            tid_list = ",".join([f"'{t}'" for t in info["tender_ids"][:20]])
            tenders = session.execute(text(f"""
                SELECT title, source, state, tender_value_estimated, bid_close_date
                FROM tenders WHERE id IN ({tid_list})
            """)).fetchall()
            
            tender_dicts = [
                {"title": t[0], "source": t[1], "state": t[2],
                 "tender_value_estimated": t[3], "bid_close_date": t[4]}
                for t in tenders
            ]

            channels = info.get("channels", ["email"])
            
            if "email" in channels and info.get("user_email"):
                html = build_tender_alert_html(tender_dicts, info["search_name"])
                send_email(
                    info["user_email"],
                    f"🔔 TenderWatch: {len(info['tender_ids'])} new tenders match '{info['search_name']}'",
                    html,
                )
            
            if "whatsapp" in channels and info.get("user_phone"):
                msg = f"TenderWatch Alert: {len(info['tender_ids'])} new tenders match '{info['search_name']}'. Check your dashboard."
                send_whatsapp(info["user_phone"], msg)
            
            if "sms" in channels and info.get("user_phone"):
                msg = f"TenderWatch: {len(info['tender_ids'])} new matches for '{info['search_name']}'"
                send_sms(info["user_phone"], msg)

            # Create notification records
            for ch in channels:
                session.execute(text("""
                    INSERT INTO notifications (id, user_id, channel, subject, body, sent, sent_at, created_at)
                    SELECT gen_random_uuid(), ss.user_id, :ch, :subj, :body, true, NOW(), NOW()
                    FROM saved_searches ss WHERE ss.id = :sid
                """), {
                    "ch": ch,
                    "subj": f"{len(info['tender_ids'])} new matches for '{info['search_name']}'",
                    "body": f"Tenders: {', '.join(info['tender_ids'][:5])}",
                    "sid": search_id,
                })

        session.commit()
        logger.info(f"Sent {len(by_search)} alert notifications for {len(matches)} matches")

    except Exception as e:
        logger.error(f"Match & notify failed: {e}")
    finally:
        session.close()


@celery_app.task(name="backend.ingestion.tasks.process_pending_alerts")
def process_pending_alerts():
    """Periodic task to check for unmatched tenders and process alerts."""
    session = SyncSession()
    try:
        # Get tender IDs from last 6 hours that haven't been matched
        result = session.execute(text("""
            SELECT t.id FROM tenders t
            WHERE t.created_at > NOW() - INTERVAL '6 hours'
            AND NOT EXISTS (SELECT 1 FROM alerts a WHERE a.tender_id = t.id)
            LIMIT 500
        """))
        new_ids = [str(r[0]) for r in result.fetchall()]
        
        if new_ids:
            _match_and_notify(new_ids)
            logger.info(f"Processed {len(new_ids)} pending tenders for alerts")
    except Exception as e:
        logger.error(f"Pending alerts processing failed: {e}")
    finally:
        session.close()


@celery_app.task(name="backend.ingestion.tasks.download_and_parse_documents")
def download_and_parse_documents(tender_id: str, doc_urls: list):
    """Download documents for a tender and extract text."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_download_and_parse(tender_id, doc_urls))
    finally:
        loop.close()


@celery_app.task(name="backend.ingestion.tasks.update_tender_statuses")
def update_tender_statuses():
    """Daily task: update tender status/stage based on dates, track lifecycle."""
    session = SyncSession()
    try:
        # Mark active tenders as closed if bid_close_date has passed
        session.execute(text("""
            UPDATE tenders SET status = 'CLOSED', tender_stage = 'technical_bid_opening'
            WHERE status::text = 'ACTIVE' AND bid_close_date < NOW() AND bid_close_date IS NOT NULL
            AND tender_stage = 'bidding'
        """))

        # Stage progression based on time since close
        # Tech evaluation: 7-30 days after close
        session.execute(text("""
            UPDATE tenders SET tender_stage = 'technical_evaluation'
            WHERE status::text = 'CLOSED'
            AND bid_close_date < NOW() - INTERVAL '7 days'
            AND bid_close_date > NOW() - INTERVAL '30 days'
            AND tender_stage = 'technical_bid_opening'
        """))

        # Financial bid opening: 30-60 days after close
        session.execute(text("""
            UPDATE tenders SET tender_stage = 'financial_bid_opening'
            WHERE status::text = 'CLOSED'
            AND bid_close_date < NOW() - INTERVAL '30 days'
            AND bid_close_date > NOW() - INTERVAL '60 days'
            AND tender_stage = 'technical_evaluation'
        """))

        # Financial evaluation: 60-120 days after close
        session.execute(text("""
            UPDATE tenders SET tender_stage = 'financial_evaluation'
            WHERE status::text = 'CLOSED'
            AND bid_close_date < NOW() - INTERVAL '60 days'
            AND bid_close_date > NOW() - INTERVAL '120 days'
            AND tender_stage = 'financial_bid_opening'
        """))

        # Awarded tenders
        session.execute(text("""
            UPDATE tenders SET tender_stage = 'awarded'
            WHERE status::text = 'AWARDED' AND tender_stage != 'awarded'
        """))

        # Cancelled tenders
        session.execute(text("""
            UPDATE tenders SET tender_stage = 'cancelled'
            WHERE status::text = 'CANCELLED' AND tender_stage != 'cancelled'
        """))

        session.commit()
        logger.info("Tender statuses and stages updated successfully")
    except Exception as e:
        logger.error(f"Status update failed: {e}")
        session.rollback()
    finally:
        session.close()


async def _download_and_parse(tender_id: str, doc_urls: list):
    """Download docs and store records."""
    from backend.ingestion.parser.pdf_parser import extract_text_from_pdf
    
    dest_dir = Path(settings.DOCUMENT_STORAGE_PATH) / tender_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    import aiohttp
    async with aiohttp.ClientSession() as http_session:
        for url in doc_urls:
            try:
                async with http_session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    filename = url.split("/")[-1].split("?")[0] or "document.pdf"
                    file_path = dest_dir / filename
                    content = await resp.read()
                    file_path.write_bytes(content)
                    
                    ocr_text = None
                    if filename.lower().endswith(".pdf"):
                        try:
                            ocr_text, _ = extract_text_from_pdf(file_path)
                        except Exception:
                            pass
                    
                    db = SyncSession()
                    try:
                        db.execute(
                            text("""
                                INSERT INTO tender_documents (id, tender_id, filename, file_path, file_size, mime_type, ocr_text)
                                VALUES (gen_random_uuid(), :tid, :fname, :fpath, :fsize, :mime, :ocr)
                            """),
                            {
                                "tid": tender_id,
                                "fname": filename,
                                "fpath": str(file_path),
                                "fsize": len(content),
                                "mime": _guess_mime(filename),
                                "ocr": ocr_text[:100000] if ocr_text else None,
                            }
                        )
                        db.commit()
                    finally:
                        db.close()
                    
            except Exception as e:
                logger.error(f"Failed to download/parse {url}: {e}")
