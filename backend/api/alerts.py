"""Saved searches and alerts endpoints."""

from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
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


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    result = await db.execute(
        select(Alert)
        .join(SavedSearch)
        .where(SavedSearch.user_id == user.id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    return [AlertResponse.model_validate(a) for a in result.scalars().all()]
