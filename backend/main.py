"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.config import get_settings
from backend.database import init_db
from backend.api.router import api_router
from backend.utils.logging import setup_logging

settings = get_settings()
setup_logging("DEBUG" if settings.DEBUG else "INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await init_db()
    
    # Create storage directory
    Path(settings.DOCUMENT_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router, prefix=settings.API_PREFIX)


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


# Search vector trigger SQL (run once via migration)
SEARCH_VECTOR_TRIGGER = """
CREATE OR REPLACE FUNCTION tenders_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.department, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.category, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.raw_text, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tenders_search_vector_trigger ON tenders;
CREATE TRIGGER tenders_search_vector_trigger
    BEFORE INSERT OR UPDATE ON tenders
    FOR EACH ROW
    EXECUTE FUNCTION tenders_search_vector_update();
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
