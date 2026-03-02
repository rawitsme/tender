# 🏛️ Tender Portal — Government Tender Aggregator

A SaaS platform that aggregates government tenders from across India into a single searchable catalogue with alerts, document management, and analytics.

## Sources (Phase 1)

| Source | Portal | Type |
|--------|--------|------|
| **CPPP** | eprocure.gov.in | Central tenders |
| **GeM** | gem.gov.in | Government eMarketplace |
| **Uttar Pradesh** | etender.up.nic.in | State portal |
| **Maharashtra** | mahatenders.gov.in | State portal |
| **Uttarakhand** | uktenders.gov.in | State portal |
| **Haryana** | etenders.hry.nic.in | State portal |
| **Madhya Pradesh** | mptenders.gov.in | State portal |

## Tech Stack

- **Backend**: FastAPI (Python) + SQLAlchemy async + Celery
- **Database**: PostgreSQL 16 (with full-text search) + Redis
- **Frontend**: React + Vite + TailwindCSS
- **PDF/OCR**: pdfplumber + Tesseract
- **NLP**: regex + spaCy for field extraction

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for PostgreSQL + Redis)

### Setup

```bash
# One-click setup
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### Manual Setup

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Create .env
cp .env.example .env

# 4. Create database tables
python3 -c "import asyncio; from backend.database import init_db; asyncio.run(init_db())"

# 5. Seed sample data
python3 scripts/seed_data.py

# 6. Start backend
python3 -m backend.main
# → API at http://localhost:8000/api/docs

# 7. Start frontend (separate terminal)
cd frontend
npm install
npm run dev
# → UI at http://localhost:5173
```

### Running Ingestion

```bash
# Manual ingestion (all sources)
python3 scripts/run_ingestion.py

# Single source
python3 scripts/run_ingestion.py cppp

# With Celery (scheduled)
celery -A backend.ingestion.tasks worker -l info
celery -A backend.ingestion.tasks beat -l info   # every 30 min
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/tenders/search` | Full-text search + filters |
| GET | `/api/v1/tenders/` | List tenders |
| GET | `/api/v1/tenders/stats` | Dashboard stats |
| GET | `/api/v1/tenders/{id}` | Tender detail |
| GET | `/api/v1/documents/{id}` | Download document |
| GET/POST/DELETE | `/api/v1/alerts/searches` | Saved searches |
| GET | `/api/v1/alerts/` | Alert list |
| GET | `/api/v1/admin/dashboard` | Admin stats |
| POST | `/api/v1/admin/ingestion/trigger/{source}` | Trigger ingestion |

## Default Credentials (dev)

- **Admin**: admin@tenderportal.in / admin123
- **Demo**: demo@example.com / demo123

## Project Structure

```
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py             # Settings
│   ├── database.py           # SQLAlchemy async
│   ├── models/               # DB models (Tender, User, Alert)
│   ├── schemas/              # Pydantic schemas
│   ├── api/                  # API routes
│   ├── services/             # Search, dedup, auth, alerts
│   └── ingestion/
│       ├── base_connector.py # Abstract connector
│       ├── connectors/       # CPPP, GeM, UP, MH, UK, HR, MP
│       ├── parser/           # PDF, OCR, field extraction, BOQ
│       └── tasks.py          # Celery tasks
├── frontend/
│   └── src/
│       ├── pages/            # Dashboard, Search, Detail, Alerts, Admin
│       └── components/       # Layout, Cards, Filters, Tables
├── scripts/
│   ├── setup.sh              # One-click setup
│   ├── seed_data.py          # Sample data
│   └── run_ingestion.py      # Manual ingestion
└── docker-compose.yml        # PostgreSQL + Redis
```

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌────────────┐
│   React UI  │───▶│  FastAPI API  │───▶│ PostgreSQL │
│  (Vite/TW)  │    │   (uvicorn)  │    │  (FTS/GIN) │
└─────────────┘    └──────┬───────┘    └────────────┘
                          │
                   ┌──────┴───────┐
                   │ Celery + Redis│
                   │  (scheduler) │
                   └──────┬───────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌─────────┐     ┌──────────┐     ┌───────────┐
   │  CPPP   │     │   GeM    │     │ 5 States  │
   │ scraper │     │   API    │     │ scrapers  │
   └─────────┘     └──────────┘     └───────────┘
```
