"""
Real Documents API - Serve actual PDF documents from government portals
Fixed version with proper async database handling
"""

import asyncio
import os
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select

from backend.database import get_db
from backend.models.tender import Tender

router = APIRouter()

REAL_DOCS_BASE = Path("storage/documents/real_pdfs")

@router.get("/test")
async def test_real_documents():
    """Test endpoint to verify real document functionality"""
    
    # Check if we have any downloaded documents
    if not REAL_DOCS_BASE.exists():
        return {"status": "no_downloads", "message": "No real documents downloaded yet"}
    
    folders = [f for f in REAL_DOCS_BASE.iterdir() if f.is_dir()]
    total_pdfs = 0
    total_size = 0
    
    documents = []
    for folder in folders:
        pdfs = list(folder.glob("*.pdf")) + list(folder.glob("*.PDF"))
        for pdf in pdfs:
            size = pdf.stat().st_size
            total_pdfs += 1
            total_size += size
            
            documents.append({
                "folder": folder.name,
                "filename": pdf.name,
                "size_mb": size / (1024 * 1024),
                "path": str(pdf)
            })
    
    return {
        "status": "success",
        "total_folders": len(folders),
        "total_pdfs": total_pdfs,
        "total_size_mb": total_size / (1024 * 1024),
        "sample_documents": documents[:5]  # Show first 5
    }

@router.get("/list/{tender_id}")
async def list_real_documents(tender_id: str, db = Depends(get_db)):
    """
    List already downloaded real documents for a tender
    """
    
    # Check if tender exists
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    # Look for existing downloads
    source = tender.source.upper()
    source_id = tender.source_id
    
    # Check possible folder names
    possible_folders = [
        REAL_DOCS_BASE / f"{source}_{source_id}_{tender_id[:8]}",
        REAL_DOCS_BASE / f"{source}_{source_id}_{tender_id}",
        REAL_DOCS_BASE / f"{source}_{source_id}"
    ]
    
    for folder in possible_folders:
        if folder.exists():
            files = []
            total_size = 0
            
            # List PDF files
            for pdf_file in list(folder.glob("*.pdf")) + list(folder.glob("*.PDF")):
                file_size = pdf_file.stat().st_size
                total_size += file_size
                
                files.append({
                    "filename": pdf_file.name,
                    "size": file_size,
                    "size_mb": file_size / (1024 * 1024),
                    "path": str(pdf_file),
                    "type": "PDF"
                })
            
            # Check for metadata
            metadata_file = folder / "download_metadata.json"
            metadata = {}
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                except:
                    pass
            
            return {
                "status": "found",
                "tender_id": tender_id,
                "source": source,
                "source_id": source_id,
                "folder": str(folder),
                "files": files,
                "total_files": len(files),
                "total_size_mb": total_size / (1024 * 1024),
                "metadata": metadata
            }
    
    return {
        "status": "not_found",
        "tender_id": tender_id,
        "message": "No downloaded documents found. Use /download/{tender_id} to fetch them."
    }

@router.get("/file/{tender_id}/{filename}")
async def serve_real_document(tender_id: str, filename: str, db = Depends(get_db)):
    """
    Serve a specific downloaded document file
    """
    
    # Check if tender exists
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    # Find the file
    source = tender.source.upper()
    source_id = tender.source_id
    
    possible_folders = [
        REAL_DOCS_BASE / f"{source}_{source_id}_{tender_id[:8]}",
        REAL_DOCS_BASE / f"{source}_{source_id}_{tender_id}",
        REAL_DOCS_BASE / f"{source}_{source_id}"
    ]
    
    for folder in possible_folders:
        file_path = folder / filename
        if file_path.exists() and file_path.suffix.lower() in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']:
            # Determine media type
            media_type = "application/pdf" if file_path.suffix.lower() == '.pdf' else "application/octet-stream"
            
            return FileResponse(
                path=file_path,
                media_type=media_type,
                filename=filename,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-Tender-ID": tender_id,
                    "X-Source": source
                }
            )
    
    raise HTTPException(status_code=404, detail="Document file not found")

@router.post("/download/{tender_id}")
async def download_real_documents(tender_id: str, db = Depends(get_db)):
    """
    Download real PDF documents for a tender
    Returns download status and list of available files
    """
    
    # Check if tender exists
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    try:
        # Import and run the real PDF downloader
        import sys
        sys.path.append('/Users/rahulwealthdiscovery.in/Code/Tender')
        
        from real_pdf_downloader import download_real_pdfs_for_tender
        
        download_result = await download_real_pdfs_for_tender(tender_id)
        
        if download_result and download_result["downloaded_files"]:
            return {
                "status": "success",
                "tender_id": tender_id,
                "source": download_result["source"],
                "files_downloaded": len(download_result["downloaded_files"]),
                "total_size_mb": download_result["total_size"] / (1024 * 1024),
                "files": download_result["downloaded_files"],
                "download_folder": download_result["folder_path"]
            }
        else:
            return {
                "status": "no_documents_found", 
                "tender_id": tender_id,
                "message": "No PDF documents could be downloaded from the portal",
                "reason": download_result.get("error") if download_result else "Unknown error"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download documents: {str(e)}"
        )