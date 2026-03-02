"""Deduplication service — fingerprinting and matching."""

import hashlib
import re
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.tender import Tender


def normalize_text(text: str) -> str:
    """Normalize text for fingerprinting — lowercase, strip extra whitespace, remove punctuation."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def generate_fingerprint(
    tender_id: Optional[str],
    title: str,
    department: Optional[str],
    bid_close_date: Optional[str],
) -> str:
    """Generate a dedup fingerprint from key tender fields.
    
    Uses a combination of tender ID, normalized title, department, and close date.
    If tender_id is available, it's the primary signal (most reliable).
    """
    parts = []
    
    if tender_id:
        parts.append(normalize_text(tender_id))
    
    parts.append(normalize_text(title)[:200])  # Cap title length
    
    if department:
        parts.append(normalize_text(department)[:100])
    
    if bid_close_date:
        parts.append(str(bid_close_date)[:10])  # Date only, no time
    
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()


async def find_duplicate(db: AsyncSession, fingerprint: str) -> Optional[Tender]:
    """Check if a tender with this fingerprint already exists."""
    result = await db.execute(
        select(Tender).where(Tender.fingerprint == fingerprint)
    )
    return result.scalar_one_or_none()


async def is_duplicate(db: AsyncSession, fingerprint: str) -> bool:
    """Quick boolean check."""
    return (await find_duplicate(db, fingerprint)) is not None
