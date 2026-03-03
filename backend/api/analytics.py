"""Analytics endpoints — charts data, similar tenders, comparison, keyword/authority explore."""

from uuid import UUID
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.tender import Tender, TenderStatus
from backend.schemas.tender import TenderResponse
from backend.services.cache import cache_get, cache_set

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Curated keyword categories for "Explore by Keywords"
KEYWORD_CATEGORIES = {
    "construction": {"label": "Construction", "icon": "🏗️", "keywords": ["construction", "building", "civil"]},
    "road": {"label": "Road & Highway", "icon": "🛣️", "keywords": ["road", "highway", "bridge", "flyover"]},
    "water": {"label": "Water & Sanitation", "icon": "💧", "keywords": ["water", "sewerage", "pipeline", "sanitation", "drainage"]},
    "electricity": {"label": "Electricity & Power", "icon": "⚡", "keywords": ["electrical", "power", "transformer", "transmission"]},
    "it": {"label": "IT & Software", "icon": "💻", "keywords": ["software", "computer", "it ", "digital", "server"]},
    "medical": {"label": "Medical & Health", "icon": "🏥", "keywords": ["medical", "hospital", "health", "pharmaceutical", "medicine"]},
    "education": {"label": "Education", "icon": "📚", "keywords": ["school", "education", "university", "college", "training"]},
    "transport": {"label": "Transport", "icon": "🚌", "keywords": ["vehicle", "transport", "bus", "railway", "logistics"]},
    "agriculture": {"label": "Agriculture", "icon": "🌾", "keywords": ["agriculture", "farming", "irrigation", "fertilizer"]},
    "security": {"label": "Security & Defense", "icon": "🛡️", "keywords": ["security", "guard", "cctv", "surveillance", "defense"]},
    "furniture": {"label": "Furniture & Supplies", "icon": "🪑", "keywords": ["furniture", "office", "stationery", "supply"]},
    "cleaning": {"label": "Cleaning & Maintenance", "icon": "🧹", "keywords": ["cleaning", "housekeeping", "maintenance", "repair"]},
}

# Curated authority categories
AUTHORITY_CATEGORIES = {
    "pwd": {"label": "PWD (Public Works)", "keywords": ["pwd", "public works"]},
    "nhai": {"label": "NHAI", "keywords": ["nhai", "national highway"]},
    "railways": {"label": "Railways", "keywords": ["railway", "indian railways", "ircon"]},
    "municipal": {"label": "Municipal Corporations", "keywords": ["municipal", "nagar nigam", "nagar palika", "corporation"]},
    "phed": {"label": "PHED (Public Health)", "keywords": ["phed", "public health engineering"]},
    "education_dept": {"label": "Education Dept", "keywords": ["education", "university", "iit", "nit"]},
    "health_dept": {"label": "Health & Family Welfare", "keywords": ["health", "family welfare", "hospital", "aiims"]},
    "defense": {"label": "Defense & Military", "keywords": ["army", "navy", "air force", "defense", "drdo", "ordnance"]},
    "irrigation": {"label": "Irrigation Dept", "keywords": ["irrigation", "water resources"]},
    "police": {"label": "Police & Home", "keywords": ["police", "home department", "security"]},
}


@router.get("/similar/{tender_id}")
async def get_similar_tenders(
    tender_id: UUID,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Find similar tenders using PostgreSQL FTS ranking."""
    # Get the target tender
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(404, "Tender not found")

    # Use title + category + department for similarity
    search_text = " ".join(filter(None, [tender.title, tender.category, tender.department]))
    if not search_text.strip():
        return []

    # Find similar using FTS
    q = text("""
        SELECT t.*, ts_rank(t.search_vector, plainto_tsquery('english', :q)) AS rank
        FROM tenders t
        WHERE t.id != :tid
        AND t.search_vector @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :lim
    """)
    result = await db.execute(q, {"q": search_text[:200], "tid": str(tender_id), "lim": limit})
    rows = result.fetchall()

    return [dict(r._mapping) for r in rows]


@router.get("/charts/timeline")
async def chart_timeline(
    days: int = Query(30, ge=7, le=365),
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get tender counts by day for timeline chart."""
    cache_key = f"chart:timeline:{days}:{source or 'all'}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    conditions = "WHERE publication_date >= :start AND publication_date IS NOT NULL"
    params = {"start": start}
    if source:
        conditions += " AND source = :source"
        params["source"] = source

    result = await db.execute(text(f"""
        SELECT DATE(publication_date) as day, COUNT(*) as count
        FROM tenders {conditions}
        GROUP BY DATE(publication_date)
        ORDER BY day ASC
    """), params)

    data = [{"date": str(r[0]), "count": r[1]} for r in result.fetchall()]
    await cache_set(cache_key, data, ttl=600)
    return data


@router.get("/charts/value-distribution")
async def chart_value_distribution(db: AsyncSession = Depends(get_db)):
    """Get tender value distribution for histogram."""
    cache_key = "chart:value_dist"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    result = await db.execute(text("""
        SELECT
            CASE
                WHEN tender_value_estimated < 100000 THEN 'Under ₹1L'
                WHEN tender_value_estimated < 1000000 THEN '₹1L - ₹10L'
                WHEN tender_value_estimated < 10000000 THEN '₹10L - ₹1Cr'
                WHEN tender_value_estimated < 100000000 THEN '₹1Cr - ₹10Cr'
                ELSE 'Above ₹10Cr'
            END as range,
            COUNT(*) as count
        FROM tenders
        WHERE tender_value_estimated IS NOT NULL AND tender_value_estimated > 0
        GROUP BY range
        ORDER BY MIN(tender_value_estimated)
    """))

    data = [{"range": r[0], "count": r[1]} for r in result.fetchall()]
    await cache_set(cache_key, data, ttl=600)
    return data


@router.get("/charts/source-trend")
async def chart_source_trend(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get tender count by source over time."""
    cache_key = f"chart:source_trend:{days}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    result = await db.execute(text("""
        SELECT DATE(publication_date) as day, source, COUNT(*) as count
        FROM tenders
        WHERE publication_date >= :start AND publication_date IS NOT NULL
        GROUP BY DATE(publication_date), source
        ORDER BY day ASC
    """), {"start": start})

    data = {}
    for r in result.fetchall():
        day = str(r[0])
        source = str(r[1])
        if day not in data:
            data[day] = {"date": day}
        data[day][source] = r[2]

    await cache_set(cache_key, list(data.values()), ttl=600)
    return list(data.values())


@router.get("/keywords")
async def explore_keywords(db: AsyncSession = Depends(get_db)):
    """Get keyword categories with live tender counts."""
    cache_key = "explore:keywords"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    categories = []
    for slug, info in KEYWORD_CATEGORIES.items():
        # Build OR condition for keywords
        conditions = " OR ".join([f"search_vector @@ plainto_tsquery('english', '{kw}')" for kw in info["keywords"]])
        result = await db.execute(text(f"""
            SELECT COUNT(*) FROM tenders WHERE status::text = 'active' AND ({conditions})
        """))
        count = result.scalar() or 0
        categories.append({
            "slug": slug,
            "label": info["label"],
            "icon": info["icon"],
            "count": count,
            "keywords": info["keywords"],
        })

    categories.sort(key=lambda x: x["count"], reverse=True)
    await cache_set(cache_key, categories, ttl=600)
    return categories


@router.get("/authorities")
async def explore_authorities(db: AsyncSession = Depends(get_db)):
    """Get authority categories with live tender counts."""
    cache_key = "explore:authorities"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    authorities = []
    for slug, info in AUTHORITY_CATEGORIES.items():
        conditions = " OR ".join([
            f"LOWER(organization) LIKE '%{kw}%' OR LOWER(department) LIKE '%{kw}%'"
            for kw in info["keywords"]
        ])
        result = await db.execute(text(f"""
            SELECT COUNT(*) FROM tenders WHERE status::text = 'active' AND ({conditions})
        """))
        count = result.scalar() or 0
        authorities.append({
            "slug": slug,
            "label": info["label"],
            "count": count,
            "keywords": info["keywords"],
        })

    authorities.sort(key=lambda x: x["count"], reverse=True)
    await cache_set(cache_key, authorities, ttl=600)
    return authorities


@router.post("/compare")
async def compare_tenders(
    tender_ids: List[UUID],
    db: AsyncSession = Depends(get_db),
):
    """Compare 2-5 tenders side by side."""
    if len(tender_ids) < 2 or len(tender_ids) > 5:
        raise HTTPException(400, "Provide 2-5 tender IDs")

    result = await db.execute(
        select(Tender).where(Tender.id.in_(tender_ids))
    )
    tenders = result.scalars().all()

    if len(tenders) != len(tender_ids):
        raise HTTPException(404, "One or more tenders not found")

    comparison = []
    for t in tenders:
        comparison.append({
            "id": str(t.id),
            "title": t.title,
            "source": str(t.source.value if hasattr(t.source, 'value') else t.source),
            "state": t.state,
            "department": t.department,
            "organization": t.organization,
            "category": t.category,
            "tender_value_estimated": float(t.tender_value_estimated) if t.tender_value_estimated else None,
            "emd_amount": float(t.emd_amount) if t.emd_amount else None,
            "document_fee": float(t.document_fee) if t.document_fee else None,
            "publication_date": str(t.publication_date) if t.publication_date else None,
            "bid_close_date": str(t.bid_close_date) if t.bid_close_date else None,
            "status": str(t.status.value if hasattr(t.status, 'value') else t.status),
            "contact_person": t.contact_person,
            "contact_email": t.contact_email,
            "contact_phone": t.contact_phone,
            "source_url": t.source_url,
        })

    return comparison
