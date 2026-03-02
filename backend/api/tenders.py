"""Tender search, list, and detail endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
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
    tenders, total = await search_tenders(
        db,
        query=req.query,
        states=req.states,
        sources=req.sources,
        categories=req.categories,
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
    result = await db.execute(text("SELECT department, COUNT(*) FROM tenders WHERE department != '' GROUP BY department ORDER BY count DESC LIMIT 20"))
    for row in result.fetchall():
        by_dept[row[0]] = row[1]
    
    by_org = {}
    result = await db.execute(text("SELECT organization, COUNT(*) FROM tenders WHERE organization != '' GROUP BY organization ORDER BY count DESC LIMIT 20"))
    for row in result.fetchall():
        by_org[row[0]] = row[1]
    
    return {"by_source": by_source, "by_state": by_state, "by_department": by_dept, "by_organization": by_org}


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

    data = TenderDetailResponse.model_validate(tender)
    data.documents = [
        {"id": str(d.id), "filename": d.filename, "file_size": d.file_size, "mime_type": d.mime_type}
        for d in tender.documents
    ]
    data.corrigenda = [
        {"id": str(c.id), "number": c.corrigendum_number, "date": str(c.published_date), "description": c.description}
        for c in tender.corrigenda
    ]
    if tender.result:
        data.result = {
            "winner": tender.result.winner_name,
            "org": tender.result.winner_org,
            "value": float(tender.result.award_value) if tender.result.award_value else None,
            "date": str(tender.result.award_date) if tender.result.award_date else None,
        }
    return data
