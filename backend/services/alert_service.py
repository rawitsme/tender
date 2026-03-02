"""Alert matching and notification dispatch service."""

import logging
from typing import List
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tender import Tender
from backend.models.alert import SavedSearch, Alert, Notification, AlertTrigger, NotificationChannel

logger = logging.getLogger(__name__)


async def match_tender_against_searches(db: AsyncSession, tender: Tender) -> List[SavedSearch]:
    """Find all saved searches that match a newly ingested tender."""
    result = await db.execute(
        select(SavedSearch).where(
            and_(SavedSearch.is_active == True, SavedSearch.alert_enabled == True)
        )
    )
    searches = result.scalars().all()
    matched = []

    for search in searches:
        if _matches_criteria(tender, search.criteria):
            matched.append(search)

    return matched


def _matches_criteria(tender: Tender, criteria: dict) -> bool:
    """Check if a tender matches search criteria."""
    # Keyword match
    keywords = criteria.get("keywords", "").lower()
    if keywords:
        text_to_search = f"{tender.title or ''} {tender.description or ''} {tender.raw_text or ''}".lower()
        # All keywords must appear
        for kw in keywords.split():
            if kw not in text_to_search:
                return False

    # State filter
    states = criteria.get("states", [])
    if states and tender.state and tender.state.lower() not in [s.lower() for s in states]:
        return False

    # Category filter
    categories = criteria.get("categories", [])
    if categories and tender.category:
        if tender.category.lower() not in [c.lower() for c in categories]:
            return False

    # Value range
    min_val = criteria.get("min_value")
    if min_val and tender.tender_value_estimated and tender.tender_value_estimated < min_val:
        return False
    
    max_val = criteria.get("max_value")
    if max_val and tender.tender_value_estimated and tender.tender_value_estimated > max_val:
        return False

    # Tender type
    types = criteria.get("tender_types", [])
    if types and tender.tender_type and tender.tender_type.value not in types:
        return False

    return True


async def create_alert_and_notify(
    db: AsyncSession,
    tender: Tender,
    saved_search: SavedSearch,
):
    """Create an alert record and queue notifications for each channel."""
    alert = Alert(
        saved_search_id=saved_search.id,
        tender_id=tender.id,
        trigger=AlertTrigger.NEW_TENDER,
    )
    db.add(alert)
    await db.flush()

    channels = saved_search.alert_channels or ["email"]
    for ch in channels:
        try:
            channel_enum = NotificationChannel(ch)
        except ValueError:
            continue

        notification = Notification(
            user_id=saved_search.user_id,
            alert_id=alert.id,
            channel=channel_enum,
            subject=f"New Tender Match: {tender.title[:100]}",
            body=_build_notification_body(tender),
        )
        db.add(notification)

    # Update saved search stats
    saved_search.last_matched_at = datetime.now(timezone.utc)
    saved_search.match_count = str(int(saved_search.match_count or "0") + 1)

    await db.commit()
    logger.info(f"Alert created for tender {tender.id} → saved_search {saved_search.id}")


def _build_notification_body(tender: Tender) -> str:
    """Build notification body text."""
    lines = [
        f"📋 {tender.title}",
        f"🏢 {tender.department or 'N/A'} | {tender.state or 'N/A'}",
    ]
    if tender.tender_value_estimated:
        lines.append(f"💰 Estimated Value: ₹{tender.tender_value_estimated:,.2f}")
    if tender.bid_close_date:
        lines.append(f"⏰ Closing: {tender.bid_close_date.strftime('%d %b %Y %H:%M')}")
    if tender.emd_amount:
        lines.append(f"🏦 EMD: ₹{tender.emd_amount:,.2f}")
    if tender.source_url:
        lines.append(f"🔗 {tender.source_url}")
    return "\n".join(lines)
