"""Document download endpoints."""

from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.tender import TenderDocument
from backend.config import get_settings

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()


@router.get("/{doc_id}")
async def download_document(doc_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TenderDocument).where(TenderDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=doc.filename,
        media_type=doc.mime_type or "application/octet-stream",
    )
