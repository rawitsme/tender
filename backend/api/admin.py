"""Admin endpoints — ingestion, users, system health, logs."""

from typing import Optional, List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.tender import Tender, TenderSource, TenderDocument
from backend.models.alert import SavedSearch, Alert, Notification
from backend.api.auth import get_current_user
from backend.config import get_settings

settings = get_settings()
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
    total_docs = (await db.execute(select(func.count(TenderDocument.id)))).scalar() or 0
    total_searches = (await db.execute(select(func.count(SavedSearch.id)))).scalar() or 0
    total_alerts = (await db.execute(select(func.count(Alert.id)))).scalar() or 0

    # Per-source counts
    source_q = await db.execute(
        select(Tender.source, func.count(Tender.id)).group_by(Tender.source)
    )
    by_source = {}
    for r in source_q.all():
        key = str(r[0].value) if hasattr(r[0], 'value') else str(r[0])
        by_source[key] = r[1]

    # Unverified
    unverified = (await db.execute(
        select(func.count(Tender.id)).where(Tender.human_verified == False)
    )).scalar() or 0

    # Recent ingestion (last 24h)
    now = datetime.now(timezone.utc)
    recent_count = (await db.execute(
        select(func.count(Tender.id)).where(Tender.created_at > now - timedelta(hours=24))
    )).scalar() or 0

    # Per-source recent
    recent_by_source = {}
    rq = await db.execute(
        select(Tender.source, func.count(Tender.id))
        .where(Tender.created_at > now - timedelta(hours=24))
        .group_by(Tender.source)
    )
    for r in rq.all():
        key = str(r[0].value) if hasattr(r[0], 'value') else str(r[0])
        recent_by_source[key] = r[1]

    # Data quality — fields populated %
    quality_q = await db.execute(text("""
        SELECT 
            COUNT(*) as total,
            COUNT(description) as has_desc,
            COUNT(category) as has_cat,
            COUNT(tender_value_estimated) as has_value,
            COUNT(emd_amount) as has_emd,
            COUNT(contact_person) as has_contact,
            COUNT(NULLIF(department, '')) as has_dept
        FROM tenders
    """))
    qr = quality_q.fetchone()
    total = qr[0] or 1
    data_quality = {
        "description": round(qr[1] / total * 100, 1),
        "category": round(qr[2] / total * 100, 1),
        "estimated_value": round(qr[3] / total * 100, 1),
        "emd_amount": round(qr[4] / total * 100, 1),
        "contact_info": round(qr[5] / total * 100, 1),
        "department": round(qr[6] / total * 100, 1),
    }

    return {
        "total_tenders": total_tenders,
        "total_users": total_users,
        "total_documents": total_docs,
        "total_saved_searches": total_searches,
        "total_alerts": total_alerts,
        "unverified_tenders": unverified,
        "tenders_by_source": by_source,
        "recent_24h": recent_count,
        "recent_by_source": recent_by_source,
        "data_quality": data_quality,
    }


@router.get("/users")
async def list_users(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return [{
        "id": str(u.id),
        "email": u.email,
        "full_name": u.full_name,
        "phone": u.phone,
        "role": str(u.role.value) if hasattr(u.role, 'value') else str(u.role),
        "is_active": u.is_active,
        "created_at": str(u.created_at),
    } for u in users]


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str, role: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if role not in ["user", "admin", "operator"]:
        raise HTTPException(400, "Invalid role")
    await db.execute(
        update(User).where(User.id == user_id).values(role=role)
    )
    await db.commit()
    return {"status": "updated"}


@router.put("/users/{user_id}/toggle")
async def toggle_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")
    u.is_active = not u.is_active
    await db.commit()
    return {"status": "toggled", "is_active": u.is_active}


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
    try:
        source_enum = TenderSource(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")
    
    from backend.ingestion.tasks import run_connector
    task = run_connector.delay(source)
    return {"status": "triggered", "source": source, "task_id": str(task.id)}


@router.post("/update-statuses")
async def trigger_status_update(user: User = Depends(require_admin)):
    """Trigger daily tender status/stage update manually."""
    from backend.ingestion.tasks import update_tender_statuses
    task = update_tender_statuses.delay()
    return {"status": "triggered", "task_id": str(task.id)}


@router.post("/ingestion/trigger-all")
async def trigger_all_ingestion(user: User = Depends(require_admin)):
    from backend.ingestion.tasks import run_all_connectors
    task = run_all_connectors.delay()
    return {"status": "triggered_all", "task_id": str(task.id)}


@router.get("/ingestion/sources")
async def ingestion_sources(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get all sources with their status and last ingestion time."""
    sources = []
    all_sources = [
        {"key": "gem", "label": "GeM (Government eMarketplace)", "type": "api"},
        {"key": "cppp", "label": "CPPP (Central Portal)", "type": "selenium"},
        {"key": "up", "label": "Uttar Pradesh", "type": "selenium"},
        {"key": "maharashtra", "label": "Maharashtra", "type": "selenium"},
        {"key": "uttarakhand", "label": "Uttarakhand", "type": "selenium"},
        {"key": "haryana", "label": "Haryana", "type": "selenium"},
        {"key": "mp", "label": "Madhya Pradesh", "type": "selenium"},
    ]

    for src in all_sources:
        count_q = await db.execute(
            select(func.count(Tender.id)).where(Tender.source == src["key"])
        )
        count = count_q.scalar() or 0

        last_q = await db.execute(
            select(func.max(Tender.created_at)).where(Tender.source == src["key"])
        )
        last = last_q.scalar()

        sources.append({
            **src,
            "count": count,
            "last_ingested": str(last) if last else None,
        })

    return sources


@router.get("/notifications")
async def list_notifications(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    result = await db.execute(
        select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    )
    notifs = result.scalars().all()
    return [{
        "id": str(n.id),
        "channel": str(n.channel.value) if hasattr(n.channel, 'value') else str(n.channel),
        "subject": n.subject,
        "sent": n.sent,
        "sent_at": str(n.sent_at) if n.sent_at else None,
        "created_at": str(n.created_at),
    } for n in notifs]


@router.get("/system-health")
async def system_health(user: User = Depends(require_admin)):
    """Check system component health."""
    health = {"database": False, "redis": False, "celery": False, "storage": False}
    
    # DB
    try:
        from backend.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["database"] = True
    except Exception:
        pass

    # Redis
    try:
        import redis as r
        client = r.from_url(settings.REDIS_URL)
        client.ping()
        health["redis"] = True
    except Exception:
        pass

    # Storage
    from pathlib import Path
    storage = Path(settings.DOCUMENT_STORAGE_PATH)
    health["storage"] = storage.exists()

    # Celery (check if broker is reachable)
    health["celery"] = health["redis"]  # Celery uses Redis as broker

    # SMTP configured
    health["smtp_configured"] = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)

    return health
