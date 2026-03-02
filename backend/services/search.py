"""PostgreSQL full-text search service for tenders."""

from typing import Optional, List, Tuple
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, func, text, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tender import Tender, TenderSource, TenderStatus


async def search_tenders(
    db: AsyncSession,
    query: Optional[str] = None,
    states: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    departments: Optional[List[str]] = None,
    tender_types: Optional[List[str]] = None,
    status: Optional[List[str]] = None,
    min_value: Optional[Decimal] = None,
    max_value: Optional[Decimal] = None,
    bid_close_from: Optional[datetime] = None,
    bid_close_to: Optional[datetime] = None,
    published_from: Optional[datetime] = None,
    published_to: Optional[datetime] = None,
    closing_within: Optional[str] = None,
    department_search: Optional[str] = None,
    category_search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "publication_date",
    sort_order: str = "desc",
) -> Tuple[List[Tender], int]:
    """Full-text search with filters. Returns (tenders, total_count)."""

    conditions = []

    # Full-text search using PostgreSQL tsvector
    if query:
        ts_query = func.plainto_tsquery("english", query)
        conditions.append(Tender.search_vector.op("@@")(ts_query))

    # Filters
    if states:
        conditions.append(Tender.state.in_(states))
    if sources:
        conditions.append(Tender.source.in_(sources))
    if categories:
        conditions.append(Tender.category.in_(categories))
    if departments:
        conditions.append(Tender.department.in_(departments))
    if tender_types:
        conditions.append(Tender.tender_type.in_(tender_types))
    if status:
        conditions.append(Tender.status.in_(status))
    if min_value is not None:
        conditions.append(Tender.tender_value_estimated >= min_value)
    if max_value is not None:
        conditions.append(Tender.tender_value_estimated <= max_value)
    if bid_close_from:
        conditions.append(Tender.bid_close_date >= bid_close_from)
    if bid_close_to:
        conditions.append(Tender.bid_close_date <= bid_close_to)
    if published_from:
        conditions.append(Tender.publication_date >= published_from)
    if published_to:
        conditions.append(Tender.publication_date <= published_to)

    # Closing within filter
    if closing_within:
        from datetime import timedelta, timezone as tz
        now = datetime.now(tz.utc)
        delta_map = {"today": 1, "3days": 3, "7days": 7, "30days": 30}
        days = delta_map.get(closing_within, 7)
        conditions.append(Tender.bid_close_date >= now)
        conditions.append(Tender.bid_close_date <= now + timedelta(days=days))

    # Text search on department
    if department_search:
        conditions.append(Tender.department.ilike(f"%{department_search}%"))

    # Text search on category
    if category_search:
        conditions.append(Tender.category.ilike(f"%{category_search}%"))

    where_clause = and_(*conditions) if conditions else True

    # Count
    count_q = select(func.count(Tender.id)).where(where_clause)
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    sort_col = getattr(Tender, sort_by, Tender.publication_date)
    order = desc(sort_col) if sort_order == "desc" else asc(sort_col)

    # If FTS query, also sort by relevance
    if query:
        ts_query = func.plainto_tsquery("english", query)
        rank = func.ts_rank(Tender.search_vector, ts_query)
        order = desc(rank)

    # Query
    q = (
        select(Tender)
        .where(where_clause)
        .order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(q)
    tenders = result.scalars().all()

    return tenders, total


async def get_tender_stats(db: AsyncSession) -> dict:
    """Dashboard statistics."""
    from datetime import timedelta, timezone

    now = datetime.now(timezone.utc)
    week_end = now + timedelta(days=7)

    total = (await db.execute(select(func.count(Tender.id)))).scalar() or 0
    active = (await db.execute(
        select(func.count(Tender.id)).where(Tender.status == TenderStatus.ACTIVE)
    )).scalar() or 0

    # By source
    source_q = await db.execute(
        select(Tender.source, func.count(Tender.id)).group_by(Tender.source)
    )
    by_source = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in source_q.all()}

    # By state
    state_q = await db.execute(
        select(Tender.state, func.count(Tender.id)).where(Tender.state.isnot(None)).group_by(Tender.state)
    )
    by_state = {row[0]: row[1] for row in state_q.all()}

    # By department (top 20)
    dept_q = await db.execute(
        select(Tender.department, func.count(Tender.id))
        .where(Tender.department.isnot(None))
        .group_by(Tender.department)
        .order_by(func.count(Tender.id).desc())
        .limit(20)
    )
    by_department = {row[0]: row[1] for row in dept_q.all()}

    # By organization (top 20)
    org_q = await db.execute(
        select(Tender.organization, func.count(Tender.id))
        .where(Tender.organization.isnot(None))
        .group_by(Tender.organization)
        .order_by(func.count(Tender.id).desc())
        .limit(20)
    )
    by_organization = {row[0]: row[1] for row in org_q.all()}

    # Closing this week
    closing_week = (await db.execute(
        select(func.count(Tender.id)).where(
            and_(Tender.bid_close_date >= now, Tender.bid_close_date <= week_end)
        )
    )).scalar() or 0

    # Avg value
    avg_val = (await db.execute(
        select(func.avg(Tender.tender_value_estimated)).where(Tender.tender_value_estimated.isnot(None))
    )).scalar()

    return {
        "total_tenders": total,
        "active_tenders": active,
        "tenders_by_source": by_source,
        "tenders_by_state": by_state,
        "avg_tender_value": float(avg_val) if avg_val else None,
        "tenders_closing_this_week": closing_week,
        "tenders_by_department": by_department,
        "tenders_by_organization": by_organization,
    }
