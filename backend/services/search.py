"""PostgreSQL full-text search service for tenders."""

from typing import Optional, List, Tuple
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, func, text, and_, or_, desc, asc, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tender import Tender, TenderSource, TenderStatus


def _build_tsquery(query: str):
    """
    Build a smart tsquery from user input.
    
    Strategy:
    - Single word: plain match
    - Multi-word: AND between words (user wants all terms, not any)
    - Quoted phrases: kept as phrase search
    - Falls back to OR only if AND returns 0 results (handled at query level)
    """
    words = [w.strip() for w in query.split() if w.strip() and len(w.strip()) > 1]
    if not words:
        return None, None
    
    if len(words) == 1:
        # Single word — use prefix matching for partial matches
        and_expr = words[0] + ":*"
        or_expr = words[0] + ":*"
    else:
        # Multi-word: AND for precision, OR as fallback
        and_expr = " & ".join(w for w in words)
        or_expr = " | ".join(w for w in words)
    
    return and_expr, or_expr


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
    use_fts = False
    ts_query_expr = None

    # Full-text search
    if query:
        and_expr, or_expr = _build_tsquery(query)
        if and_expr:
            use_fts = True
            # Try AND first (all words must match) — if that gives results, use it
            # Otherwise fall back to OR
            and_tsq = func.to_tsquery("english", and_expr)
            or_tsq = func.to_tsquery("english", or_expr)
            
            # Check AND match count
            and_count = await db.execute(
                select(func.count(Tender.id)).where(Tender.search_vector.op("@@")(and_tsq))
            )
            and_total = and_count.scalar() or 0
            
            if and_total > 0:
                # AND has results — use it for precision
                ts_query_expr = and_tsq
                conditions.append(Tender.search_vector.op("@@")(and_tsq))
            else:
                # Fall back to OR but also add ILIKE on title for fuzzy matching
                ts_query_expr = or_tsq
                # Use OR FTS + title ILIKE as combined condition
                fts_cond = Tender.search_vector.op("@@")(or_tsq)
                ilike_cond = Tender.title.ilike(f"%{query}%")
                conditions.append(or_(fts_cond, ilike_cond))

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
        # Handle case-insensitive status matching
        status_upper = [s.upper() for s in status]
        conditions.append(Tender.status.in_(status_upper))
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

    # Text search on department/org (ILIKE for partial match)
    if department_search:
        conditions.append(or_(
            Tender.department.ilike(f"%{department_search}%"),
            Tender.organization.ilike(f"%{department_search}%"),
        ))

    # Text search on category
    if category_search:
        conditions.append(Tender.category.ilike(f"%{category_search}%"))

    where_clause = and_(*conditions) if conditions else True

    # Count
    count_q = select(func.count(Tender.id)).where(where_clause)
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    if use_fts and ts_query_expr is not None and sort_by in ("relevance", "created_at", "publication_date"):
        # Rank by relevance: ts_rank with normalization
        # Weight: title match (A) > department (B) > description (B) > category (C)
        rank = func.ts_rank(
            Tender.search_vector,
            ts_query_expr,
            32  # normalization: rank / (rank + 1) to dampen long doc advantage
        )
        order = desc(rank)
    else:
        sort_col = getattr(Tender, sort_by, Tender.publication_date)
        order = desc(sort_col) if sort_order == "desc" else asc(sort_col)

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

    # By department (top 30)
    dept_q = await db.execute(
        select(Tender.department, func.count(Tender.id))
        .where(Tender.department.isnot(None))
        .group_by(Tender.department)
        .order_by(func.count(Tender.id).desc())
        .limit(30)
    )
    by_department = {row[0]: row[1] for row in dept_q.all()}

    # By organization (top 30)
    org_q = await db.execute(
        select(Tender.organization, func.count(Tender.id))
        .where(Tender.organization.isnot(None))
        .group_by(Tender.organization)
        .order_by(func.count(Tender.id).desc())
        .limit(30)
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
        select(func.avg(Tender.tender_value_estimated)).where(
            and_(Tender.tender_value_estimated.isnot(None), Tender.tender_value_estimated > 0)
        )
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
