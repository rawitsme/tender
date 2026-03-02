"""Celery tasks for scheduled ingestion and processing."""

import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path

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
        "ingest-all-sources-every-30m": {
            "task": "backend.ingestion.tasks.run_all_connectors",
            "schedule": settings.INGESTION_INTERVAL_MINUTES * 60,
        },
    },
)

# Sync DB session for Celery tasks (Celery doesn't play well with async)
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
    from backend.ingestion.connector_registry import CONNECTORS
    
    results = {}
    for source in CONNECTORS:
        try:
            result = run_connector(source)
            results[source] = result
        except Exception as e:
            logger.error(f"Connector {source} failed: {e}")
            results[source] = {"error": str(e)}
    
    return results


async def _run_connector_async(source: str) -> dict:
    """Async implementation of connector run."""
    from backend.ingestion.connector_registry import get_connector
    from backend.ingestion.parser.normalizer import normalize_state, normalize_title, clean_department, normalize_date
    from backend.services.dedup import generate_fingerprint
    
    connector = get_connector(source)
    stats = {"source": source, "fetched": 0, "new": 0, "duplicate": 0, "errors": 0}
    
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
                    
                    # Insert new tender
                    session.execute(
                        text("""
                            INSERT INTO tenders (
                                id, source, source_url, source_id, tender_id, title, description,
                                department, organization, state, category, tender_type,
                                tender_value_estimated, emd_amount, document_fee,
                                publication_date, bid_close_date, pre_bid_meeting_date,
                                contact_person, contact_email, contact_phone,
                                status, raw_text, fingerprint, parsed_quality_score
                            ) VALUES (
                                gen_random_uuid(), :source, :source_url, :source_id, :tender_id,
                                :title, :description, :department, :organization, :state,
                                :category, :tender_type, :tender_value, :emd, :doc_fee,
                                :pub_date, :close_date, :prebid_date,
                                :contact_person, :contact_email, :contact_phone,
                                'active', :raw_text, :fingerprint, :quality
                            )
                        """),
                        {
                            "source": source,
                            "source_url": raw.source_url,
                            "source_id": raw.source_id,
                            "tender_id": raw.tender_id,
                            "title": normalize_title(raw.title),
                            "description": raw.description,
                            "department": clean_department(raw.department),
                            "organization": raw.organization,
                            "state": normalize_state(raw.state),
                            "category": raw.category,
                            "tender_type": raw.tender_type or "open_tender",
                            "tender_value": raw.tender_value,
                            "emd": raw.emd_amount,
                            "doc_fee": raw.document_fee,
                            "pub_date": raw.publication_date,
                            "close_date": raw.bid_close_date,
                            "prebid_date": raw.pre_bid_meeting_date,
                            "contact_person": raw.contact_person,
                            "contact_email": raw.contact_email,
                            "contact_phone": raw.contact_phone,
                            "raw_text": raw.raw_text,
                            "fingerprint": fp,
                            "quality": 0.5,  # Default for auto-parsed
                        }
                    )
                    stats["new"] += 1
                    
                except Exception as e:
                    logger.warning(f"Error ingesting tender: {e}")
                    stats["errors"] += 1
                    continue
            
            session.commit()
        finally:
            session.close()
    
    finally:
        await connector.close()
    
    return stats


@celery_app.task(name="backend.ingestion.tasks.download_and_parse_documents")
def download_and_parse_documents(tender_id: str, doc_urls: list):
    """Download documents for a tender and extract text."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_download_and_parse(tender_id, doc_urls))
    finally:
        loop.close()


async def _download_and_parse(tender_id: str, doc_urls: list):
    """Download docs, run OCR, and store extracted text."""
    from backend.ingestion.parser.pdf_parser import extract_text_from_pdf
    from backend.ingestion.parser.field_extractor import extract_fields
    
    dest_dir = Path(settings.DOCUMENT_STORAGE_PATH) / tender_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    import aiohttp
    async with aiohttp.ClientSession() as session:
        for url in doc_urls:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    filename = url.split("/")[-1].split("?")[0] or "document.pdf"
                    file_path = dest_dir / filename
                    content = await resp.read()
                    file_path.write_bytes(content)
                    
                    # Extract text if PDF
                    if filename.lower().endswith(".pdf"):
                        text, confidence = extract_text_from_pdf(file_path)
                        
                        # Store document record
                        db = SyncSession()
                        try:
                            db.execute(
                                text("""
                                    INSERT INTO tender_documents (id, tender_id, filename, file_path, file_size, mime_type, ocr_text)
                                    VALUES (gen_random_uuid(), :tid, :fname, :fpath, :fsize, 'application/pdf', :ocr)
                                """),
                                {
                                    "tid": tender_id,
                                    "fname": filename,
                                    "fpath": str(file_path),
                                    "fsize": len(content),
                                    "ocr": text[:100000] if text else None,
                                }
                            )
                            db.commit()
                        finally:
                            db.close()
                        
            except Exception as e:
                logger.error(f"Failed to download/parse {url}: {e}")
