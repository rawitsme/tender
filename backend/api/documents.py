"""Document download endpoints."""

import io
import zipfile
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.tender import TenderDocument
from backend.config import get_settings

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()


@router.get("/tender/{tender_id}/download-all")
async def download_all_documents(tender_id: UUID, db: AsyncSession = Depends(get_db)):
    """Download all documents for a tender as a ZIP file."""
    result = await db.execute(
        select(TenderDocument).where(TenderDocument.tender_id == tender_id)
    )
    docs = result.scalars().all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found for this tender")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            file_path = Path(doc.file_path)
            if file_path.exists():
                zf.write(file_path, doc.filename)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=tender_{tender_id}_documents.zip"}
    )


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
