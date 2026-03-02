"""Normalize and clean raw tender data before storage."""

import re
from datetime import datetime, timezone
from typing import Optional


def normalize_title(title: str) -> str:
    """Clean and normalize a tender title."""
    if not title:
        return ""
    title = re.sub(r'\s+', ' ', title.strip())
    title = title[:1000]  # Cap length
    return title


def normalize_state(state: Optional[str]) -> Optional[str]:
    """Normalize state name to canonical form."""
    if not state:
        return None
    
    state_map = {
        "up": "Uttar Pradesh",
        "uttar pradesh": "Uttar Pradesh",
        "mh": "Maharashtra",
        "maharashtra": "Maharashtra",
        "uk": "Uttarakhand",
        "uttarakhand": "Uttarakhand",
        "hr": "Haryana",
        "haryana": "Haryana",
        "mp": "Madhya Pradesh",
        "madhya pradesh": "Madhya Pradesh",
        "central": "Central",
    }
    
    return state_map.get(state.lower().strip(), state.strip().title())


def normalize_amount(amount) -> Optional[float]:
    """Normalize amount to float."""
    if amount is None:
        return None
    if isinstance(amount, (int, float)):
        return float(amount)
    if isinstance(amount, str):
        cleaned = re.sub(r'[₹Rs.\s,]', '', amount)
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def normalize_date(dt) -> Optional[datetime]:
    """Ensure datetime is timezone-aware (UTC if naive)."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return None  # Should already be parsed
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def clean_department(dept: Optional[str]) -> Optional[str]:
    """Clean department name."""
    if not dept:
        return None
    dept = re.sub(r'\s+', ' ', dept.strip())
    dept = dept[:500]
    return dept
