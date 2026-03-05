"""Tender search, list, and detail endpoints."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.tender import Tender
from backend.schemas.tender import (
    TenderResponse, TenderListResponse, TenderSearchRequest,
    TenderDetailResponse, TenderStatsResponse,
)
from backend.services.search import search_tenders, get_tender_stats

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.post("/search", response_model=TenderListResponse)
async def search(req: TenderSearchRequest, db: AsyncSession = Depends(get_db)):
    # Convert single values to lists for backward compatibility
    states = req.states or ([req.state] if req.state else None)
    sources = req.sources or ([req.source] if req.source else None)
    categories = req.categories or ([req.category] if req.category else None)
    
    tenders, total = await search_tenders(
        db,
        query=req.query,
        states=states,
        sources=sources,
        categories=categories,
        departments=req.departments,
        tender_types=req.tender_types,
        status=req.status,
        min_value=req.min_value,
        max_value=req.max_value,
        bid_close_from=req.bid_close_from,
        bid_close_to=req.bid_close_to,
        published_from=req.published_from,
        published_to=req.published_to,
        closing_within=req.closing_within,
        department_search=req.department,
        category_search=req.category,
        page=req.page,
        page_size=req.page_size,
        sort_by=req.sort_by,
        sort_order=req.sort_order,
    )
    return TenderListResponse(
        tenders=[TenderResponse.model_validate(t) for t in tenders],
        total=total,
        page=req.page,
        page_size=req.page_size,
    )


@router.get("/", response_model=TenderListResponse)
async def list_tenders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    state: str = None,
    source: str = None,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    tenders, total = await search_tenders(
        db,
        states=[state] if state else None,
        sources=[source] if source else None,
        status=[status] if status else None,
        page=page,
        page_size=page_size,
    )
    return TenderListResponse(
        tenders=[TenderResponse.model_validate(t) for t in tenders],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=TenderStatsResponse)
async def stats(db: AsyncSession = Depends(get_db)):
    return await get_tender_stats(db)


@router.get("/browse/facets")
async def browse_facets(db: AsyncSession = Depends(get_db)):
    """Get counts by source, state, department for browse page."""
    from sqlalchemy import text
    
    by_source = {}
    result = await db.execute(text("SELECT source, COUNT(*) FROM tenders GROUP BY source ORDER BY count DESC"))
    for row in result.fetchall():
        by_source[row[0]] = row[1]
    
    by_state = {}
    result = await db.execute(text("SELECT state, COUNT(*) FROM tenders WHERE state != '' GROUP BY state ORDER BY count DESC LIMIT 20"))
    for row in result.fetchall():
        by_state[row[0]] = row[1]
    
    by_dept = {}
    result = await db.execute(text("SELECT department, COUNT(*) FROM tenders WHERE department != '' GROUP BY department ORDER BY count DESC LIMIT 50"))
    for row in result.fetchall():
        by_dept[row[0]] = row[1]
    
    by_org = {}
    result = await db.execute(text("SELECT organization, COUNT(*) FROM tenders WHERE organization != '' GROUP BY organization ORDER BY count DESC LIMIT 50"))
    for row in result.fetchall():
        by_org[row[0]] = row[1]
    
    return {"by_source": by_source, "by_state": by_state, "by_department": by_dept, "by_organization": by_org}


@router.get("/charts/timeline")
async def chart_timeline(days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)):
    """Tenders published per day for charts."""
    # from backend.services.cache import cache_get, cache_set
    
    cache_key = f"chart_timeline_{days}"
    try:
        # cached = cache_get(cache_key)
        if cached and isinstance(cached, list):
            return cached
    except Exception:
        pass
    
    result = await db.execute(text(
        f"SELECT DATE(publication_date) as day, source::text, COUNT(*) as cnt "
        f"FROM tenders "
        f"WHERE publication_date > NOW() - INTERVAL '{int(days)} days' "
        f"AND publication_date IS NOT NULL "
        f"GROUP BY DATE(publication_date), source "
        f"ORDER BY day"
    ))
    
    data = {}
    for row in result.fetchall():
        day_str = str(row[0])
        if day_str not in data:
            data[day_str] = {"date": day_str}
        data[day_str][str(row[1])] = row[2]
    
    timeline = list(data.values())
    # cache_set(cache_key, timeline, ttl=300)
    return timeline


@router.get("/charts/value-distribution")
async def chart_value_distribution(db: AsyncSession = Depends(get_db)):
    """Tender value distribution for charts."""
    # from backend.services.cache import cache_get, cache_set
    
    # cached = cache_get("chart_value_dist")
    if False:  # cached disabled
        return cached
    
    result = await db.execute(text("""
        SELECT 
            CASE 
                WHEN tender_value_estimated < 100000 THEN 'Under ₹1L'
                WHEN tender_value_estimated < 1000000 THEN '₹1L - ₹10L'
                WHEN tender_value_estimated < 10000000 THEN '₹10L - ₹1Cr'
                WHEN tender_value_estimated < 100000000 THEN '₹1Cr - ₹10Cr'
                ELSE 'Above ₹10Cr'
            END as bucket,
            COUNT(*) as cnt
        FROM tenders
        WHERE tender_value_estimated IS NOT NULL AND tender_value_estimated > 0
        GROUP BY bucket
        ORDER BY MIN(tender_value_estimated)
    """))
    
    dist = [{"range": row[0], "count": row[1]} for row in result.fetchall()]
    # cache_set("chart_value_dist", dist, ttl=300)
    return dist


@router.get("/keywords/popular")
async def popular_keywords(db: AsyncSession = Depends(get_db)):
    """Curated keyword categories with counts for Explore by Keywords."""
    # from backend.services.cache import cache_get, cache_set
    
    # cached = cache_get("popular_keywords")
    if False:  # cached disabled
        return cached
    
    keywords = [
        ("Construction", "construction building civil"),
        ("Road", "road highway nhai bridge flyover"),
        ("Water", "water supply pipeline sewerage drainage"),
        ("IT & Software", "software computer it hardware network"),
        ("Medical", "medical hospital health pharmaceutical equipment"),
        ("Railway", "railway rail ireps station"),
        ("Electrical", "electrical transformer power solar energy"),
        ("Education", "school college university education training"),
        ("Agriculture", "agriculture irrigation farming seed fertilizer"),
        ("Security", "security cctv surveillance guard patrol"),
        ("Transport", "transport vehicle bus fleet logistics"),
        ("Printing", "printing stationery paper office supply"),
    ]
    
    results = []
    for name, search_terms in keywords:
        # Use same search logic as the search endpoint (OR with full-text search)
        words = [w.strip() for w in search_terms.split() if w.strip()]
        if len(words) > 1:
            # OR between words  
            or_expr = ' | '.join(words)
            count_result = await db.execute(text(
                "SELECT COUNT(*) FROM tenders WHERE search_vector @@ to_tsquery('english', :query)"
            ), {"query": or_expr})
        else:
            count_result = await db.execute(text(
                "SELECT COUNT(*) FROM tenders WHERE search_vector @@ plainto_tsquery('english', :query)"
            ), {"query": search_terms})
        
        count = count_result.scalar() or 0
        if count > 0:
            results.append({"name": name, "keywords": search_terms, "count": count})
    
    results.sort(key=lambda x: x["count"], reverse=True)
    # cache_set("popular_keywords", results, ttl=600)
    return results


@router.get("/authorities/popular")
async def popular_authorities(db: AsyncSession = Depends(get_db)):
    """Popular authorities/organizations with counts."""
    # from backend.services.cache import cache_get, cache_set
    
    # cached = cache_get("popular_authorities")
    if False:  # cached disabled
        return cached
    
    authorities = [
        ("PWD", "pwd public works"),
        ("Municipal Corporation", "municipal corporation nagar nigam"),
        ("Zilla Parishad", "zilla parishad"),
        ("NHAI", "nhai national highway"),
        ("Railways", "railway ireps"),
        ("PHED", "phed public health engineering"),
        ("Irrigation", "irrigation water resources"),
        ("Education Dept", "education university school college"),
        ("Police", "police security home department"),
        ("Forest Dept", "forest environment wildlife"),
        ("Health Dept", "health medical hospital"),
        ("Rural Development", "rural development panchayat"),
    ]
    
    results = []
    for name, search_terms in authorities:
        terms = search_terms.split()
        conditions = " OR ".join([f"organization ILIKE '%{t}%' OR department ILIKE '%{t}%'" for t in terms])
        count_result = await db.execute(text(f"SELECT COUNT(*) FROM tenders WHERE {conditions}"))
        count = count_result.scalar() or 0
        if count > 0:
            results.append({"name": name, "keywords": search_terms, "count": count})
    
    results.sort(key=lambda x: x["count"], reverse=True)
    # cache_set("popular_authorities", results, ttl=600)
    return results


@router.get("/authorities/hierarchy")
async def authorities_hierarchy(db: AsyncSession = Depends(get_db)):
    """Hierarchical authorities: level=Central/State → states → departments with counts."""
    # Level 1: Central vs State counts
    level1 = await db.execute(text("""
        SELECT 
            CASE WHEN state = 'Central' THEN 'Central' ELSE 'State' END as level,
            COUNT(*) as cnt
        FROM tenders GROUP BY level ORDER BY cnt DESC
    """))
    levels = {r[0]: r[1] for r in level1.fetchall()}

    # Level 2: States with counts
    states_q = await db.execute(text("""
        SELECT state, COUNT(*) as cnt FROM tenders
        WHERE state != 'Central' AND state IS NOT NULL AND state != ''
        GROUP BY state ORDER BY cnt DESC
    """))
    states = [{"name": r[0], "count": r[1]} for r in states_q.fetchall()]

    # Level 3: Departments per state (top 15 each)
    depts = {}
    for s in [{"name": "Central"}] + states:
        dept_q = await db.execute(text("""
            SELECT department, COUNT(*) as cnt FROM tenders
            WHERE state = :state AND department IS NOT NULL AND department != '' AND department != 'NA'
            GROUP BY department ORDER BY cnt DESC
        """), {"state": s["name"]})
        depts[s["name"]] = [{"name": r[0], "count": r[1]} for r in dept_q.fetchall()]

    # Level 3b: Organizations per state (all)
    orgs = {}
    for s in [{"name": "Central"}] + states:
        org_q = await db.execute(text("""
            SELECT organization, COUNT(*) as cnt FROM tenders
            WHERE state = :state AND organization IS NOT NULL AND organization != ''
            GROUP BY organization ORDER BY cnt DESC
        """), {"state": s["name"]})
        orgs[s["name"]] = [{"name": r[0], "count": r[1]} for r in org_q.fetchall()]

    return {
        "central_count": levels.get("Central", 0),
        "state_count": levels.get("State", 0),
        "states": states,
        "departments": depts,
        "organizations": orgs,
    }


@router.get("/authorities/departments")
async def authority_departments(
    state: str = Query(..., description="State name to get departments for"),
    db: AsyncSession = Depends(get_db),
):
    """Get departments and organizations for a specific state."""
    dept_q = await db.execute(text("""
        SELECT department, COUNT(*) as cnt FROM tenders
        WHERE state = :state AND department IS NOT NULL AND department != '' AND department != 'NA'
        GROUP BY department ORDER BY cnt DESC
    """), {"state": state})
    departments = [{"name": r[0], "count": r[1]} for r in dept_q.fetchall()]

    org_q = await db.execute(text("""
        SELECT organization, COUNT(*) as cnt FROM tenders
        WHERE state = :state AND organization IS NOT NULL AND organization != ''
        GROUP BY organization ORDER BY cnt DESC
    """), {"state": state})
    organizations = [{"name": r[0], "count": r[1]} for r in org_q.fetchall()]

    return {"state": state, "departments": departments, "organizations": organizations}


@router.post("/compare")
async def compare_tenders(tender_ids: List[str], db: AsyncSession = Depends(get_db)):
    """Compare multiple tenders side by side."""
    from uuid import UUID as PyUUID
    
    if len(tender_ids) > 5:
        from fastapi import HTTPException
        raise HTTPException(400, "Max 5 tenders for comparison")
    
    tenders = []
    for tid in tender_ids:
        result = await db.execute(
            select(Tender).where(Tender.id == PyUUID(tid))
        )
        t = result.scalar_one_or_none()
        if t:
            tenders.append(TenderResponse.model_validate(t))
    
    return tenders


@router.get("/{tender_id}", response_model=TenderDetailResponse)
async def get_tender(tender_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tender)
        .where(Tender.id == tender_id)
        .options(
            selectinload(Tender.documents),
            selectinload(Tender.boq_items),
            selectinload(Tender.corrigenda),
            selectinload(Tender.result),
        )
    )
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Convert tender to dict and prepare documents/corrigenda separately
    tender_dict = {
        "id": str(tender.id),
        "source": tender.source,
        "source_url": tender.source_url or "",
        "source_id": tender.source_id or "",
        "tender_id": tender.tender_id or "",
        "title": tender.title or "",
        "description": tender.description or "",
        "department": tender.department or "",
        "organization": tender.organization or "",
        "state": tender.state or "",
        "category": tender.category or "",
        "procurement_category": tender.procurement_category or "",
        "tender_type": tender.tender_type or "",
        "tender_value_estimated": tender.tender_value_estimated,
        "emd_amount": tender.emd_amount,
        "document_fee": tender.document_fee,
        "publication_date": tender.publication_date,
        "bid_open_date": tender.bid_open_date,
        "bid_close_date": tender.bid_close_date,
        "pre_bid_meeting_date": tender.pre_bid_meeting_date,
        "pre_bid_meeting_venue": tender.pre_bid_meeting_venue or "",
        "contact_person": tender.contact_person or "",
        "contact_email": tender.contact_email or "",
        "contact_phone": tender.contact_phone or "",
        "eligibility_criteria": tender.eligibility_criteria,
        "status": tender.status,
        "tender_stage": tender.tender_stage,
        "created_at": tender.created_at,
        "updated_at": tender.updated_at,
        "documents": [
            {"id": str(d.id), "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type}
            for d in tender.documents
        ],
        "corrigenda": [
            {"id": str(c.id), "number": c.corrigendum_number, "date": str(c.published_date), "description": c.description}
            for c in tender.corrigenda
        ]
    }
    
    data = TenderDetailResponse.model_validate(tender_dict)
    if tender.result:
        data.result = {
            "winner": tender.result.winner_name,
            "org": tender.result.winner_org,
            "value": float(tender.result.award_value) if tender.result.award_value else None,
            "date": str(tender.result.award_date) if tender.result.award_date else None,
        }
    return data


@router.get("/{tender_id}/similar")
async def similar_tenders(tender_id: UUID, limit: int = 5, db: AsyncSession = Depends(get_db)):
    """Find similar tenders using PostgreSQL FTS similarity."""
    # Get the tender's search vector
    tender_result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = tender_result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Use title words to find similar tenders
    title_words = ' '.join(tender.title.split()[:10])

    result = await db.execute(text("""
        SELECT id, title, source, state, organization, tender_value_estimated,
               bid_close_date, status, publication_date, department,
               ts_rank(search_vector, plainto_tsquery('english', :query)) as rank
        FROM tenders
        WHERE id != :tid
        AND search_vector @@ plainto_tsquery('english', :query)
        ORDER BY rank DESC
        LIMIT :lim
    """), {"query": title_words, "tid": str(tender_id), "lim": limit})

    similar = []
    for row in result.fetchall():
        similar.append({
            "id": str(row[0]),
            "title": row[1],
            "source": str(row[2]),
            "state": row[3],
            "organization": row[4],
            "tender_value_estimated": float(row[5]) if row[5] else None,
            "bid_close_date": str(row[6]) if row[6] else None,
            "status": str(row[7]),
            "publication_date": str(row[8]) if row[8] else None,
            "department": row[9],
            "relevance": float(row[10]),
        })

    return similar
