"""Main API router — aggregates all sub-routers."""

from fastapi import APIRouter
from backend.api.auth import router as auth_router
from backend.api.tenders import router as tenders_router
from backend.api.alerts import router as alerts_router
from backend.api.documents import router as documents_router
from backend.api.admin import router as admin_router
from backend.api.bookmarks import router as bookmarks_router
from backend.api.export import router as export_router
from backend.api.analytics import router as analytics_router
from backend.api.details import router as details_router
from backend.api.real_documents import router as real_documents_router
from backend.api.tender_analysis import router as tender_analysis_router
from backend.api.health import router as health_router
from backend.api.download_center import router as download_center_router
from backend.api.sync import router as sync_router
from backend.api.archive import router as archive_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(tenders_router)
api_router.include_router(alerts_router)
api_router.include_router(documents_router)
api_router.include_router(admin_router)
api_router.include_router(bookmarks_router)
api_router.include_router(export_router)
api_router.include_router(analytics_router)
api_router.include_router(details_router)
api_router.include_router(real_documents_router, prefix="/real-docs", tags=["Real Documents"])
api_router.include_router(tender_analysis_router, tags=["Tender Analysis"])
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(download_center_router)
api_router.include_router(sync_router, prefix="/sync", tags=["Sync"])
api_router.include_router(archive_router)
