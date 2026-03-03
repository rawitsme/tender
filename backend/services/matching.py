"""Keyword auto-matching service — match new tenders against saved searches."""

import logging
from datetime import datetime, timezone
from typing import List, Dict

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def match_new_tenders_against_searches(db_session: Session, new_tender_ids: List[str]) -> List[Dict]:
    """Match newly ingested tenders against all active saved searches.
    Returns list of {search_id, search_name, user_email, tender_id, channels} matches.
    """
    if not new_tender_ids:
        return []

    matches = []

    try:
        # Get all active saved searches
        searches = db_session.execute(text("""
            SELECT ss.id, ss.name, ss.criteria, ss.alert_channels, u.email, u.phone
            FROM saved_searches ss
            JOIN users u ON u.id = ss.user_id
            WHERE ss.is_active = true AND ss.alert_enabled = true
        """)).fetchall()

        if not searches:
            return []

        # Get new tenders
        placeholders = ",".join([f"'{tid}'" for tid in new_tender_ids])
        new_tenders = db_session.execute(text(f"""
            SELECT id, title, description, department, organization, state, category,
                   tender_value_estimated, source
            FROM tenders WHERE id IN ({placeholders})
        """)).fetchall()

        for search in searches:
            search_id = str(search[0])
            search_name = search[1]
            criteria = search[2] or {}
            channels = search[3] or ["email"]
            user_email = search[4]
            user_phone = search[5]

            keywords = (criteria.get("keywords") or "").lower().split()
            filter_states = [s.lower() for s in (criteria.get("states") or [])]
            filter_sources = [s.lower() for s in (criteria.get("sources") or [])]
            min_value = criteria.get("min_value")
            max_value = criteria.get("max_value")

            for tender in new_tenders:
                tid = str(tender[0])
                title = (tender[1] or "").lower()
                desc = (tender[2] or "").lower()
                dept = (tender[3] or "").lower()
                org = (tender[4] or "").lower()
                state = (tender[5] or "").lower()
                category = (tender[6] or "").lower()
                value = float(tender[7]) if tender[7] else None
                source = (tender[8] or "").lower()

                # Check keyword match
                if keywords:
                    text_blob = f"{title} {desc} {dept} {org} {category}"
                    if not any(kw in text_blob for kw in keywords):
                        continue

                # Check state filter
                if filter_states and state not in filter_states:
                    continue

                # Check source filter
                if filter_sources and source not in filter_sources:
                    continue

                # Check value range
                if min_value and (not value or value < float(min_value)):
                    continue
                if max_value and (not value or value > float(max_value)):
                    continue

                matches.append({
                    "search_id": search_id,
                    "search_name": search_name,
                    "user_email": user_email,
                    "user_phone": user_phone,
                    "tender_id": tid,
                    "channels": channels,
                })

        # Create alert records for matches
        for m in matches:
            try:
                db_session.execute(text("""
                    INSERT INTO alerts (id, saved_search_id, tender_id, trigger, is_read, created_at)
                    VALUES (gen_random_uuid(), :sid, :tid, 'new_tender', false, NOW())
                    ON CONFLICT DO NOTHING
                """), {"sid": m["search_id"], "tid": m["tender_id"]})
            except Exception as e:
                logger.warning(f"Alert insert failed: {e}")

        # Update match counts
        for search in searches:
            try:
                db_session.execute(text("""
                    UPDATE saved_searches SET match_count = (
                        SELECT COUNT(*)::text FROM alerts WHERE saved_search_id = :sid
                    ), last_matched_at = NOW()
                    WHERE id = :sid
                """), {"sid": str(search[0])})
            except Exception:
                pass

        db_session.commit()

    except Exception as e:
        logger.error(f"Matching failed: {e}")

    return matches
