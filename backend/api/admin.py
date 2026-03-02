"""Admin endpoints — ingestion status, manual triggers, user management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.tender import Tender, TenderSource
from backend.api.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/dashboard")
async def admin_dashboard(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_tenders = (await db.execute(select(func.count(Tender.id)))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    # Per-source counts
    source_q = await db.execute(
        select(Tender.source, func.count(Tender.id)).group_by(Tender.source)
    )
    by_source = {str(r[0].value): r[1] for r in source_q.all()}

    # Unverified tenders needing human review
    unverified = (await db.execute(
        select(func.count(Tender.id)).where(Tender.human_verified == False)
    )).scalar() or 0

    return {
        "total_tenders": total_tenders,
        "total_users": total_users,
        "tenders_by_source": by_source,
        "unverified_tenders": unverified,
    }


@router.post("/verify/{tender_id}")
async def verify_tender(
    tender_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    tender.human_verified = True
    await db.commit()
    return {"status": "verified", "tender_id": str(tender.id)}


@router.post("/ingestion/trigger/{source}")
async def trigger_ingestion(
    source: str,
    user: User = Depends(require_admin),
):
    """Manually trigger ingestion for a source."""
    try:
        source_enum = TenderSource(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")
    
    # Trigger celery task
    from backend.ingestion.tasks import run_connector
    task = run_connector.delay(source)
    return {"status": "triggered", "source": source, "task_id": str(task.id)}
