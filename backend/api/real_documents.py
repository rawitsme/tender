"""
Real Documents API - Download and serve actual tender documents from government portals.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse

from backend.services.uk_downloader import (
    download_nic_tender_documents,
    get_downloaded_documents,
    get_tender_summary,
    STORAGE_BASE,
)
from backend.services.tender_summary import generate_detailed_summary

router = APIRouter()

# Track active downloads
_active_downloads = {}


@router.get("/test")
async def test_real_documents():
    """Test endpoint."""
    return {"status": "ok", "storage": str(STORAGE_BASE), "exists": STORAGE_BASE.exists()}


@router.get("/status/{tender_id}")
async def check_document_status(tender_id: str, portal: str = "uttarakhand"):
    """Check if documents are already downloaded for a tender."""
    result = get_downloaded_documents(tender_id, portal)
    if result and result.get("success"):
        summary = get_tender_summary(result.get("details", {}))
        return {
            "status": "downloaded",
            "documents": result["documents"],
            "summary": summary,
            "details": result["details"],
        }
    
    if tender_id in _active_downloads:
        return {"status": "downloading"}
    
    return {"status": "not_downloaded"}


@router.post("/download/{tender_id}")
async def start_download(
    tender_id: str,
    background_tasks: BackgroundTasks,
    portal: str = "uttarakhand",
    title: str = "",
):
    """Start downloading documents for a tender (runs in background)."""
    # Check if already downloaded
    existing = get_downloaded_documents(tender_id, portal)
    if existing and existing.get("success"):
        summary = get_tender_summary(existing.get("details", {}))
        return {
            "status": "already_downloaded",
            "documents": existing["documents"],
            "summary": summary,
        }
    
    # Check if already downloading
    if tender_id in _active_downloads:
        return {"status": "already_downloading"}
    
    # Start background download
    _active_downloads[tender_id] = "downloading"
    
    def do_download():
        try:
            result = download_nic_tender_documents(tender_id, portal, title)
            _active_downloads[tender_id] = "done" if result["success"] else "failed"
        except Exception as e:
            _active_downloads[tender_id] = f"error: {e}"
    
    background_tasks.add_task(asyncio.to_thread, do_download)
    
    return {"status": "started", "message": f"Downloading documents for {tender_id}..."}


@router.get("/download-sync/{tender_id}")
async def download_sync(
    tender_id: str,
    portal: str = "uttarakhand",
    title: str = "",
):
    """Download documents synchronously (blocking). Use for testing."""
    existing = get_downloaded_documents(tender_id, portal)
    if existing and existing.get("success"):
        summary = get_tender_summary(existing.get("details", {}))
        return {
            "status": "already_downloaded",
            "documents": existing["documents"],
            "summary": summary,
        }
    
    result = await asyncio.to_thread(download_nic_tender_documents, tender_id, portal, title)
    
    if result["success"]:
        summary = get_tender_summary(result.get("details", {}))
        return {
            "status": "downloaded",
            "documents": result["documents"],
            "summary": summary,
            "details": result["details"],
        }
    else:
        raise HTTPException(status_code=500, detail={"errors": result["errors"]})


@router.get("/list/{tender_id}")
async def list_documents(tender_id: str, portal: str = "uttarakhand"):
    """List downloaded documents for a tender."""
    result = get_downloaded_documents(tender_id, portal)
    if not result or not result.get("success"):
        return {"documents": [], "downloaded": False}
    
    docs = []
    for doc in result.get("documents", []):
        p = Path(doc["path"])
        docs.append({
            "name": doc["name"],
            "size": doc["size"],
            "exists": p.exists(),
            "download_url": f"/api/v1/real-docs/file/{tender_id}/{doc['name']}?portal={portal}",
        })
    
    summary = get_tender_summary(result.get("details", {}))
    return {"documents": docs, "downloaded": True, "summary": summary}


@router.get("/file/{tender_id}/{filename}")
async def serve_document(tender_id: str, filename: str, portal: str = "uttarakhand"):
    """Serve a downloaded document file."""
    safe_id = tender_id.replace("/", "_").replace("\\", "_")
    
    # Look in extracted dir first, then downloads
    for subdir in ["extracted", "downloads"]:
        file_path = STORAGE_BASE / portal / safe_id / subdir / filename
        if file_path.exists():
            # Determine media type
            ext = file_path.suffix.lower()
            media_types = {
                ".pdf": "application/pdf",
                ".xls": "application/vnd.ms-excel",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".doc": "application/msword",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".zip": "application/zip",
            }
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type=media_types.get(ext, "application/octet-stream"),
            )
    
    raise HTTPException(status_code=404, detail=f"Document not found: {filename}")


@router.get("/summary/{tender_id}")
async def get_summary(tender_id: str, portal: str = "uttarakhand"):
    """Get tender summary from downloaded detail page."""
    result = get_downloaded_documents(tender_id, portal)
    if not result:
        raise HTTPException(status_code=404, detail="Documents not downloaded yet")
    
    summary = get_tender_summary(result.get("details", {}))
    return {
        "tender_id": tender_id,
        "summary": summary,
        "documents": result.get("documents", []),
        "raw_details": result.get("details", {}),
    }


@router.get("/detailed-summary/{tender_id}")
async def get_detailed_summary(tender_id: str, portal: str = "uttarakhand"):
    """
    Generate a one-pager detailed summary by extracting text from
    downloaded PDFs/XLS and combining with portal-scraped metadata.
    
    Returns: tender_title, publishing_agency, published_date, last_date,
    pre_bid_date, emd, estimated_value, scope_of_work, eligibility_criteria,
    jv_allowed, documents list.
    """
    result = get_downloaded_documents(tender_id, portal)
    if not result or not result.get("success"):
        raise HTTPException(
            status_code=404,
            detail="Documents not downloaded yet. Download documents first.",
        )
    
    tender_dir = result.get("files_dir")
    if not tender_dir or not Path(tender_dir).exists():
        # Reconstruct path
        safe_id = tender_id.replace("/", "_").replace("\\", "_")
        tender_dir = str(STORAGE_BASE / portal / safe_id)
    
    portal_details = result.get("details", {})
    
    summary = await asyncio.to_thread(
        generate_detailed_summary, tender_dir, portal_details
    )
    
    if summary.get("error"):
        raise HTTPException(status_code=500, detail=summary["error"])
    
    return {
        "tender_id": tender_id,
        "portal": portal,
        "summary": summary,
    }
