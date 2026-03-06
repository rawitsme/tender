"""
Database Seed Script — Import data from data.json into PostgreSQL.

Usage:
    cd /path/to/Tender
    python db_seed/seed_db.py

Prerequisites:
    1. PostgreSQL running with database 'tender_portal'
    2. pip install asyncpg  (or use the project's .venv)
    3. Update DB_URL below if your credentials differ

This will:
    - Create all tables (via SQLAlchemy models)
    - Import all data from data.json
    - Skip existing records (safe to re-run)
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from uuid import UUID

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://tender:tender_dev_2026@localhost:5432/tender_portal"
)

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

# Table import order (respects foreign keys)
TABLE_ORDER = [
    "organizations",
    "users",
    "subscriptions",
    "tenders",
    "tender_documents",
    "boq_items",
    "corrigenda",
    "tender_results",
    "saved_searches",
    "alerts",
    "notifications",
    "bookmarks",
]


async def seed():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text

    # Create tables from models
    from backend.database import Base
    # Import all models so they register with Base
    import backend.models.tender  # noqa
    import backend.models.user    # noqa
    import backend.models.alert   # noqa

    engine = create_async_engine(DB_URL)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")

    # Load data
    with open(DATA_FILE) as f:
        data = json.load(f)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        for table_name in TABLE_ORDER:
            rows = data.get(table_name, [])
            if not rows:
                print(f"  {table_name}: 0 rows (skip)")
                continue

            # Get column names from first row
            cols = list(rows[0].keys())
            col_list = ", ".join(cols)
            val_list = ", ".join(f":{c}" for c in cols)

            inserted = 0
            skipped = 0
            for row in rows:
                # Clean up None values and parse dates
                clean = {}
                for k, v in row.items():
                    if v is None:
                        clean[k] = None
                    else:
                        clean[k] = v
                try:
                    await session.execute(
                        text(f"INSERT INTO {table_name} ({col_list}) VALUES ({val_list}) ON CONFLICT DO NOTHING"),
                        clean
                    )
                    inserted += 1
                except Exception as e:
                    skipped += 1
                    if skipped <= 3:
                        print(f"    ⚠ {table_name} skip: {str(e)[:80]}")
                    await session.rollback()
                    continue

            await session.commit()
            print(f"  {table_name}: {inserted} inserted, {skipped} skipped")

    await engine.dispose()
    print("\n🎉 Database seeded successfully!")
    print("\nDefault login: admin@tenderportal.in / admin123")


if __name__ == "__main__":
    asyncio.run(seed())
