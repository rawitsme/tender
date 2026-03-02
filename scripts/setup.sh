#!/bin/bash
set -e

echo "🏛️ Tender Portal — Setup"
echo "========================="

cd "$(dirname "$0")/.."

# Python venv
if [ ! -d ".venv" ]; then
  echo "📦 Creating Python virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --quiet

# .env
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "📝 Created .env from .env.example — edit it with your settings"
fi

# Frontend
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --silent
cd ..

# Docker (PostgreSQL + Redis)
echo "🐳 Starting PostgreSQL & Redis via Docker..."
docker compose up -d

echo "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
  if docker exec tender_postgres pg_isready -U tender > /dev/null 2>&1; then
    echo "✅ PostgreSQL ready"
    break
  fi
  sleep 1
done

# Create DB tables
echo "🗄️ Creating database tables..."
python3 -c "
import asyncio
from backend.database import init_db
asyncio.run(init_db())
print('✅ Tables created')
"

# Create FTS trigger
echo "🔍 Setting up full-text search trigger..."
docker exec tender_postgres psql -U tender -d tender_portal -c "
CREATE OR REPLACE FUNCTION tenders_search_vector_update() RETURNS trigger AS \$\$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.department, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.category, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.raw_text, '')), 'D');
    RETURN NEW;
END;
\$\$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tenders_search_vector_trigger ON tenders;
CREATE TRIGGER tenders_search_vector_trigger
    BEFORE INSERT OR UPDATE ON tenders
    FOR EACH ROW
    EXECUTE FUNCTION tenders_search_vector_update();
"

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start:"
echo "  Backend:  source .venv/bin/activate && python -m backend.main"
echo "  Frontend: cd frontend && npm run dev"
echo "  Celery:   celery -A backend.ingestion.tasks worker -l info"
echo "  Beat:     celery -A backend.ingestion.tasks beat -l info"
echo ""
echo "  Backend API: http://localhost:8000/api/docs"
echo "  Frontend:    http://localhost:5173"
