# Database Seed

Contains a full export of the TenderWatch database (1041 tenders, users, documents, etc.)

## Quick Setup

```bash
# 1. Create PostgreSQL database
createdb tender_portal
psql -c "CREATE USER tender WITH PASSWORD 'tender_dev_2026';"
psql -c "GRANT ALL ON DATABASE tender_portal TO tender;"

# 2. Install Python deps
cd /path/to/Tender
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Seed the database
python db_seed/seed_db.py

# 4. Start the app
# Backend:
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
# Frontend:
cd frontend && npm install && npm run dev
```

## Login

- **Email:** admin@tenderportal.in
- **Password:** admin123

## Data Included

| Table | Rows |
|-------|------|
| tenders | 1041 |
| users | 5 |
| organizations | 3 |
| tender_documents | 10 |
| corrigenda | 15 |
| subscriptions | 3 |

## Environment Variables

Set `DATABASE_URL` if your DB credentials differ:
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/tender_portal
```
