"""Bookmark (Follow List) endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.tender import Tender
from backend.schemas.tender import TenderResponse

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


# Simplified: use a fixed demo user for now (no auth required)
DEMO_USER_ID = None  # Will be resolved on first call


async def _get_demo_user_id(db: AsyncSession) -> str:
    global DEMO_USER_ID
    if DEMO_USER_ID:
        return DEMO_USER_ID
    result = await db.execute(text("SELECT id FROM users LIMIT 1"))
    row = result.fetchone()
    if row:
        DEMO_USER_ID = str(row[0])
    return DEMO_USER_ID


@router.get("")
async def list_bookmarks(db: AsyncSession = Depends(get_db)):
    user_id = await _get_demo_user_id(db)
    if not user_id:
        return []
    result = await db.execute(text("""
        SELECT t.* FROM tenders t
        JOIN bookmarks b ON b.tender_id = t.id
        WHERE b.user_id = :uid
        ORDER BY b.created_at DESC
    """), {"uid": user_id})
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/ids")
async def list_bookmark_ids(db: AsyncSession = Depends(get_db)):
    user_id = await _get_demo_user_id(db)
    if not user_id:
        return []
    result = await db.execute(text(
        "SELECT tender_id FROM bookmarks WHERE user_id = :uid"
    ), {"uid": user_id})
    return [str(r[0]) for r in result.fetchall()]


@router.post("/{tender_id}")
async def add_bookmark(tender_id: UUID, db: AsyncSession = Depends(get_db)):
    user_id = await _get_demo_user_id(db)
    if not user_id:
        raise HTTPException(400, "No user found")
    await db.execute(text("""
        INSERT INTO bookmarks (id, user_id, tender_id)
        VALUES (gen_random_uuid(), :uid, :tid)
        ON CONFLICT (user_id, tender_id) DO NOTHING
    """), {"uid": user_id, "tid": str(tender_id)})
    await db.commit()
    return {"status": "bookmarked"}


@router.delete("/{tender_id}")
async def remove_bookmark(tender_id: UUID, db: AsyncSession = Depends(get_db)):
    user_id = await _get_demo_user_id(db)
    if not user_id:
        raise HTTPException(400, "No user found")
    await db.execute(text(
        "DELETE FROM bookmarks WHERE user_id = :uid AND tender_id = :tid"
    ), {"uid": user_id, "tid": str(tender_id)})
    await db.commit()
    return {"status": "removed"}
