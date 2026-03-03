"""Alert matching service — matches new tenders against saved searches and triggers notifications."""

import logging
from typing import List, Dict
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.models.alert import SavedSearch, Alert, AlertTrigger, Notification, NotificationChannel

logger = logging.getLogger(__name__)


def match_tender_against_searches(tender_data: dict, session: Session) -> List[dict]:
    """Match a newly ingested tender against all active saved searches.
    
    Returns list of matching saved search IDs with user info.
    """
    matches = []

    result = session.execute(
        select(SavedSearch).where(
            SavedSearch.alert_enabled == True,
            SavedSearch.is_active == True,
        )
    )
    searches = result.scalars().all()

    for search in searches:
        if _does_tender_match(tender_data, search.criteria):
            matches.append({
                "saved_search_id": str(search.id),
                "user_id": str(search.user_id),
                "search_name": search.name,
                "alert_channels": search.alert_channels or ["email"],
                "alert_frequency": search.alert_frequency or "instant",
            })

            # Create alert record
            alert = Alert(
                saved_search_id=search.id,
                tender_id=tender_data.get("id"),
                trigger=AlertTrigger.NEW_TENDER,
            )
            session.add(alert)

            # Update match count
            try:
                count = int(search.match_count or "0") + 1
                search.match_count = str(count)
            except (ValueError, TypeError):
                search.match_count = "1"
            search.last_matched_at = datetime.now(timezone.utc)

    if matches:
        session.commit()
        logger.info(f"Tender matched {len(matches)} saved searches")

    return matches


def _does_tender_match(tender: dict, criteria: dict) -> bool:
    """Check if a tender matches the given search criteria."""
    if not criteria:
        return False

    # Keyword matching
    keywords = criteria.get("keywords", "").lower().strip()
    if keywords:
        searchable = " ".join([
            (tender.get("title") or ""),
            (tender.get("description") or ""),
            (tender.get("department") or ""),
            (tender.get("organization") or ""),
            (tender.get("category") or ""),
        ]).lower()

        # All keywords must match (AND logic)
        keyword_list = keywords.split()
        if not all(kw in searchable for kw in keyword_list):
            return False

    # State filter
    states = criteria.get("states", [])
    if states:
        tender_state = (tender.get("state") or "").lower()
        if not any(s.lower() in tender_state or tender_state in s.lower() for s in states):
            return False

    # Source filter
    sources = criteria.get("sources", [])
    if sources:
        if (tender.get("source") or "").lower() not in [s.lower() for s in sources]:
            return False

    # Category filter
    categories = criteria.get("categories", [])
    if categories:
        tender_cat = (tender.get("category") or "").lower()
        if not any(c.lower() in tender_cat for c in categories):
            return False

    # Min value filter
    min_value = criteria.get("min_value")
    if min_value:
        tender_value = tender.get("tender_value_estimated") or tender.get("tender_value")
        if tender_value is None or float(tender_value) < float(min_value):
            return False

    # Max value filter
    max_value = criteria.get("max_value")
    if max_value:
        tender_value = tender.get("tender_value_estimated") or tender.get("tender_value")
        if tender_value is not None and float(tender_value) > float(max_value):
            return False

    return True


def create_notifications_for_matches(matches: List[dict], tender_data: dict, session: Session):
    """Create notification records for matched alerts."""
    from backend.services.notifications import build_tender_alert_email, build_tender_alert_text

    for match in matches:
        channels = match.get("alert_channels", ["email"])

        for channel in channels:
            try:
                ch_enum = NotificationChannel(channel)
            except ValueError:
                continue

            if channel == "email":
                subject, html, text_body = build_tender_alert_email(
                    [tender_data], match["search_name"]
                )
                body = html
            else:
                body = build_tender_alert_text([tender_data], match["search_name"])
                subject = f"TenderWatch: New match for '{match['search_name']}'"

            notif = Notification(
                user_id=match["user_id"],
                channel=ch_enum,
                subject=subject,
                body=body,
                sent=False,
            )
            session.add(notif)

    session.commit()
