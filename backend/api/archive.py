"""Archive management endpoints."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text, select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.tender import Tender, TenderStatus
from backend.schemas.tender import TenderResponse, TenderListResponse, TenderSearchRequest
from backend.services.search import search_tenders

router = APIRouter(prefix="/archive", tags=["archive"])


@router.get("/stats")
async def archive_stats(db: AsyncSession = Depends(get_db)):
    """Get archive statistics."""
    row = await db.execute(text("""
        SELECT 
            count(*) as total,
            count(*) FILTER (WHERE is_archived) as archived,
            count(*) FILTER (WHERE NOT is_archived) as active,
            count(*) FILTER (WHERE is_archived AND status = 'CLOSED') as closed,
            count(*) FILTER (WHERE is_archived AND status = 'CANCELLED') as cancelled,
            count(*) FILTER (WHERE is_archived AND status = 'AWARDED') as awarded
        FROM tenders
    """))
    r = row.fetchone()
    return {
        "total": r[0], "archived": r[1], "active": r[2],
        "closed": r[3], "cancelled": r[4], "awarded": r[5],
    }


@router.post("/auto")
async def auto_archive(db: AsyncSession = Depends(get_db)):
    """Auto-archive closed/cancelled/awarded tenders and expired active ones."""
    r1 = await db.execute(text("""
        UPDATE tenders SET is_archived = true
        WHERE status IN ('CLOSED', 'CANCELLED', 'AWARDED')
        AND is_archived = false
    """))
    closed_count = r1.rowcount

    r2 = await db.execute(text("""
        UPDATE tenders SET is_archived = true, status = 'CLOSED'
        WHERE bid_close_date < NOW()
        AND status = 'ACTIVE'
        AND is_archived = false
    """))
    expired_count = r2.rowcount

    await db.commit()

    row = await db.execute(text(
        "SELECT count(*) as total, count(*) FILTER (WHERE is_archived) as archived FROM tenders"
    ))
    stats = row.fetchone()

    return {
        "archived_closed": closed_count,
        "archived_expired": expired_count,
        "total_tenders": stats[0],
        "total_archived": stats[1],
        "total_active": stats[0] - stats[1],
    }


@router.post("/search", response_model=TenderListResponse)
async def search_archived(req: TenderSearchRequest, db: AsyncSession = Depends(get_db)):
    """Search only within archived tenders."""
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
        archived_only=True,
    )
    return TenderListResponse(
        tenders=[TenderResponse.model_validate(t) for t in tenders],
        total=total,
        page=req.page,
        page_size=req.page_size,
    )


@router.post("/{tender_id}")
async def archive_tender(tender_id: UUID, db: AsyncSession = Depends(get_db)):
    """Manually archive a tender."""
    result = await db.execute(
        update(Tender).where(Tender.id == tender_id).values(is_archived=True)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Tender not found")
    await db.commit()
    return {"status": "archived", "tender_id": str(tender_id)}


@router.delete("/{tender_id}")
async def unarchive_tender(tender_id: UUID, db: AsyncSession = Depends(get_db)):
    """Unarchive a tender (restore to active view)."""
    result = await db.execute(
        update(Tender).where(Tender.id == tender_id).values(is_archived=False)
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Tender not found")
    await db.commit()
    return {"status": "unarchived", "tender_id": str(tender_id)}
