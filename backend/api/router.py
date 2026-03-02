"""Main API router — aggregates all sub-routers."""

from fastapi import APIRouter
from backend.api.auth import router as auth_router
from backend.api.tenders import router as tenders_router
from backend.api.alerts import router as alerts_router
from backend.api.documents import router as documents_router
from backend.api.admin import router as admin_router
from backend.api.bookmarks import router as bookmarks_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(tenders_router)
api_router.include_router(alerts_router)
api_router.include_router(documents_router)
api_router.include_router(admin_router)
api_router.include_router(bookmarks_router)
