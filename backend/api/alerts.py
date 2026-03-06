"""Saved searches and alerts endpoints."""

from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.models.tender import Tender
from backend.models.alert import SavedSearch, Alert, Notification
from backend.schemas.alert import SavedSearchCreate, SavedSearchResponse, AlertResponse
from backend.api.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/searches", response_model=List[SavedSearchResponse])
async def list_saved_searches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.created_at.desc())
    )
    return [SavedSearchResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/searches", response_model=SavedSearchResponse)
async def create_saved_search(
    data: SavedSearchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    search = SavedSearch(
        user_id=user.id,
        name=data.name,
        criteria=data.criteria,
        alert_enabled=data.alert_enabled,
        alert_channels=data.alert_channels,
        alert_frequency=data.alert_frequency,
    )
    db.add(search)
    await db.flush()
    await db.commit()
    return SavedSearchResponse.model_validate(search)


@router.delete("/searches/{search_id}")
async def delete_saved_search(
    search_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(status_code=404, detail="Saved search not found")
    await db.delete(search)
    await db.commit()
    return {"status": "deleted"}


@router.get("", response_model=List[dict])
async def list_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """List alerts with tender details."""
    result = await db.execute(
        select(Alert, Tender.title, Tender.bid_close_date, Tender.source, Tender.state, Tender.tender_value_estimated)
        .join(SavedSearch, Alert.saved_search_id == SavedSearch.id)
        .outerjoin(Tender, Alert.tender_id == Tender.id)
        .where(SavedSearch.user_id == user.id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    alerts = []
    for row in result.all():
        alert = row[0]
        alerts.append({
            "id": str(alert.id),
            "saved_search_id": str(alert.saved_search_id),
            "tender_id": str(alert.tender_id) if alert.tender_id else None,
            "trigger": alert.trigger.value if alert.trigger else None,
            "is_read": alert.is_read,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "tender_title": row[1],
            "tender_bid_close": row[2].isoformat() if row[2] else None,
            "tender_source": str(row[3]) if row[3] else None,
            "tender_state": row[4],
            "tender_value": float(row[5]) if row[5] else None,
        })
    return alerts


@router.post("/mark-read/{alert_id}")
async def mark_read(
    alert_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an alert as read."""
    result = await db.execute(
        select(Alert)
        .join(SavedSearch)
        .where(Alert.id == alert_id, SavedSearch.user_id == user.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.is_read = True
    await db.commit()
    return {"status": "read"}


@router.post("/mark-all-read")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all alerts as read."""
    await db.execute(
        update(Alert)
        .where(
            Alert.saved_search_id.in_(
                select(SavedSearch.id).where(SavedSearch.user_id == user.id)
            ),
            Alert.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"status": "all_read"}


@router.post("/run-matcher")
async def run_matcher(
    since_minutes: int = 180,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger the alert matcher."""
    from backend.services.alert_matcher import match_saved_searches
    result = await match_saved_searches(db, since_minutes=since_minutes)
    return result


@router.get("/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get unread alert count for badge."""
    count = await db.execute(
        select(func.count(Alert.id))
        .join(SavedSearch)
        .where(SavedSearch.user_id == user.id, Alert.is_read == False)
    )
    return {"count": count.scalar() or 0}
