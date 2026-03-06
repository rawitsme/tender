"""
Alert Matcher Service.

Runs periodically to match new tenders against saved searches
and generate alerts for users.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from sqlalchemy import select, text as sa_text, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.alert import SavedSearch, Alert, AlertTrigger
from backend.models.tender import Tender

logger = logging.getLogger(__name__)


async def match_saved_searches(db: AsyncSession, since_minutes: int = 60) -> Dict:
    """
    Match new/updated tenders (from last `since_minutes`) against all active saved searches.
    Creates Alert records for matches.
    Returns summary stats.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)

    # Get all active saved searches
    ss_result = await db.execute(
        select(SavedSearch).where(
            SavedSearch.is_active == True,
            SavedSearch.alert_enabled == True,
        )
    )
    saved_searches = ss_result.scalars().all()

    if not saved_searches:
        return {"matched": 0, "alerts_created": 0, "searches_checked": 0}

    # Get new tenders since cutoff
    new_tenders = await db.execute(
        select(Tender).where(
            Tender.created_at >= cutoff,
            Tender.is_archived == False,
        )
    )
    new_tender_list = new_tenders.scalars().all()

    # Get recently updated tenders (corrigenda/date changes)
    updated_tenders = await db.execute(
        select(Tender).where(
            Tender.updated_at >= cutoff,
            Tender.created_at < cutoff,  # not new, just updated
            Tender.is_archived == False,
        )
    )
    updated_list = updated_tenders.scalars().all()

    alerts_created = 0
    matches = 0

    for ss in saved_searches:
        criteria = ss.criteria or {}
        keywords = criteria.get("keywords", "").strip()
        states = criteria.get("states", [])
        categories = criteria.get("categories", [])
        min_value = criteria.get("min_value")
        max_value = criteria.get("max_value")
        departments = criteria.get("departments", [])
        sources = criteria.get("sources", [])

        # Match new tenders
        for tender in new_tender_list:
            if _matches(tender, keywords, states, categories, min_value, max_value, departments, sources):
                created = await _create_alert_if_new(
                    db, ss.id, tender.id, AlertTrigger.NEW_TENDER
                )
                if created:
                    alerts_created += 1
                matches += 1

        # Match updated tenders (corrigenda)
        for tender in updated_list:
            if _matches(tender, keywords, states, categories, min_value, max_value, departments, sources):
                created = await _create_alert_if_new(
                    db, ss.id, tender.id, AlertTrigger.CORRIGENDUM
                )
                if created:
                    alerts_created += 1

    # Deadline approaching alerts — tenders closing within 24h
    deadline_cutoff = datetime.now(timezone.utc) + timedelta(hours=24)
    closing_soon = await db.execute(
        select(Tender).where(
            Tender.bid_close_date >= datetime.now(timezone.utc),
            Tender.bid_close_date <= deadline_cutoff,
            Tender.is_archived == False,
            Tender.status == "ACTIVE",
        )
    )
    closing_list = closing_soon.scalars().all()

    for ss in saved_searches:
        criteria = ss.criteria or {}
        keywords = criteria.get("keywords", "").strip()
        states = criteria.get("states", [])
        categories = criteria.get("categories", [])
        min_value = criteria.get("min_value")
        max_value = criteria.get("max_value")
        departments = criteria.get("departments", [])
        sources = criteria.get("sources", [])

        for tender in closing_list:
            if _matches(tender, keywords, states, categories, min_value, max_value, departments, sources):
                created = await _create_alert_if_new(
                    db, ss.id, tender.id, AlertTrigger.DEADLINE_APPROACHING
                )
                if created:
                    alerts_created += 1

    # Update match counts
    for ss in saved_searches:
        count_result = await db.execute(
            select(func.count(Alert.id)).where(Alert.saved_search_id == ss.id)
        )
        ss.match_count = str(count_result.scalar() or 0)
        ss.last_matched_at = datetime.now(timezone.utc)

    await db.commit()

    summary = {
        "searches_checked": len(saved_searches),
        "new_tenders_scanned": len(new_tender_list),
        "updated_tenders_scanned": len(updated_list),
        "closing_soon_scanned": len(closing_list),
        "alerts_created": alerts_created,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[AlertMatcher] {summary}")
    return summary


def _matches(
    tender: Tender,
    keywords: str,
    states: List[str],
    categories: List[str],
    min_value=None,
    max_value=None,
    departments: List[str] = [],
    sources: List[str] = [],
) -> bool:
    """Check if a tender matches the saved search criteria."""
    # Keywords — any keyword must appear in title or description
    if keywords:
        text_blob = f"{tender.title or ''} {tender.description or ''} {tender.department or ''} {tender.category or ''}".lower()
        keyword_list = [k.strip().lower() for k in keywords.split() if k.strip()]
        if not any(kw in text_blob for kw in keyword_list):
            return False

    # State filter
    if states:
        tender_state = (tender.state or "").lower()
        if not any(s.lower() in tender_state for s in states):
            return False

    # Category filter
    if categories:
        tender_cat = (tender.category or "").lower()
        if not any(c.lower() in tender_cat for c in categories):
            return False

    # Department filter
    if departments:
        tender_dept = f"{tender.department or ''} {tender.organization or ''}".lower()
        if not any(d.lower() in tender_dept for d in departments):
            return False

    # Source filter
    if sources:
        tender_source = str(tender.source or "").lower()
        if tender_source not in [s.lower() for s in sources]:
            return False

    # Value filters
    val = float(tender.tender_value_estimated) if tender.tender_value_estimated else None
    if min_value and (val is None or val < float(min_value)):
        return False
    if max_value and (val is None or val > float(max_value)):
        return False

    return True


async def _create_alert_if_new(
    db: AsyncSession,
    saved_search_id,
    tender_id,
    trigger: AlertTrigger,
) -> bool:
    """Create an alert if one doesn't already exist for this search+tender+trigger combo."""
    existing = await db.execute(
        select(func.count(Alert.id)).where(
            Alert.saved_search_id == saved_search_id,
            Alert.tender_id == tender_id,
            Alert.trigger == trigger,
        )
    )
    if existing.scalar() > 0:
        return False

    alert = Alert(
        saved_search_id=saved_search_id,
        tender_id=tender_id,
        trigger=trigger,
    )
    db.add(alert)
    return True


async def run_alert_matcher(since_minutes: int = 60) -> Dict:
    """Entry point — creates its own DB session."""
    from backend.database import async_session

    async with async_session() as db:
        return await match_saved_searches(db, since_minutes=since_minutes)
