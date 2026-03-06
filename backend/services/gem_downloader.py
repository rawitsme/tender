"""
GeM (Government eMarketplace) Document Downloader — HTTP-only.

Downloads ALL bid documents from bidplus.gem.gov.in using pure httpx.
No Selenium/Chrome needed.

Document strategy:
1. Fetch bid metadata via AJAX to find parent bid ID
2. Download RA summary PDF: /showradocumentPdf/{ra_id}
3. Download full bid document (specs, BOQ, terms): /showbidDocument/{parent_id}
4. Try direct RA doc as fallback: /showdirectradocumentPdf/{id}

The parent bid document is the important one — it has 6-10 pages with
full specifications, BOQ, delivery terms, ATC, etc.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

GEM_BASE = "https://bidplus.gem.gov.in"
STORAGE_BASE = Path("storage/documents/gem_downloads")


def _make_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )


def _init_session(client: httpx.Client) -> Optional[str]:
    """Visit all-bids page to get session cookies + CSRF token."""
    r = client.get(f"{GEM_BASE}/all-bids")
    if r.status_code != 200:
        logger.error(f"[GeM] Failed to init session: {r.status_code}")
        return None
    csrf_match = re.search(r"csrf_bd_gem_nk'\s*:\s*'([a-f0-9]+)'", r.text)
    csrf = csrf_match.group(1) if csrf_match else None
    logger.info(f"[GeM] Session initialized, CSRF={csrf is not None}")
    return csrf


def _get_bid_metadata(client: httpx.Client, csrf: str, bid_id: str, bid_number: str = "") -> Optional[Dict]:
    """Fetch bid metadata from GeM AJAX API to get parent ID and details."""
    # Search terms: try bid number first (GEM/2026/R/xxx), then numeric ID
    search_terms = []
    if bid_number:
        search_terms.append(bid_number)
    search_terms.append(str(bid_id))

    for search_term in search_terms:
        for bid_status in ["ongoing_bids", "closed_bids"]:
            payload = {
                "param": {"searchBid": search_term, "searchType": "fullText"},
                "filter": {"bidStatusType": bid_status, "byType": "all", "highBidValue": "",
                           "byEndDate": {"from": "", "to": ""}, "sort": "Bid-Start-Date-Latest"},
                "page": 1,
            }
            try:
                r = client.post(f"{GEM_BASE}/all-bids-data", data={
                    "payload": json.dumps(payload),
                    "csrf_bd_gem_nk": csrf,
                })
                data = r.json()
                docs = data.get("response", {}).get("response", {}).get("docs", [])
                for d in docs:
                    if str(d.get("id")) == str(bid_id) or str(d.get("b_id", [None])[0]) == str(bid_id):
                        return d
            except Exception as e:
                logger.warning(f"[GeM] Metadata fetch error for '{search_term}': {e}")
    return None


def _download_pdf(client: httpx.Client, url: str) -> Optional[Tuple[bytes, str]]:
    """Download a PDF from URL. Returns (content, filename) or None."""
    try:
        r = client.get(url)
        if r.status_code != 200 or len(r.content) == 0:
            return None
        if r.content[:4] != b"%PDF":
            return None
        cd = r.headers.get("content-disposition", "")
        filename = ""
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip().strip('"')
        return r.content, filename
    except Exception as e:
        logger.warning(f"[GeM] Download error for {url}: {e}")
        return None


def download_gem_document(
    bid_id: str,
    bid_number: str = "",
    title: str = "",
) -> Dict:
    """
    Download ALL documents for a GeM bid.
    
    Downloads:
    1. RA summary PDF (2-page bid overview)
    2. Parent bid document (6-10 page full specs, BOQ, terms)
    
    Args:
        bid_id: The numeric bid ID (source_id in our DB)
        bid_number: e.g. "GEM/2026/R/636911" (for logging)
        title: Bid title (for logging)
    
    Returns dict with: success, documents[], bid_details{}, errors[]
    """
    safe_id = str(bid_id)
    bid_dir = STORAGE_BASE / safe_id
    bid_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "bid_id": bid_id,
        "bid_number": bid_number,
        "portal": "gem",
        "success": False,
        "documents": [],
        "bid_details": {},
        "errors": [],
        "files_dir": str(bid_dir),
    }

    client = _make_client()
    try:
        # Step 1: Initialize session
        csrf = _init_session(client)
        if not csrf:
            result["errors"].append("Failed to initialize GeM session")
            return result

        # Step 2: Look up bid number from DB if not provided
        if not bid_number:
            try:
                import sqlalchemy
                engine = sqlalchemy.create_engine("postgresql://tender:tender_dev_2026@localhost:5432/tender_portal")
                with engine.connect() as conn:
                    row = conn.execute(sqlalchemy.text(
                        "SELECT tender_id FROM tenders WHERE source='GEM' AND source_id=:sid LIMIT 1"
                    ), {"sid": str(bid_id)}).fetchone()
                    if row and row[0]:
                        bid_number = row[0]
                        logger.info(f"[GeM] Looked up bid number: {bid_number}")
                engine.dispose()
            except Exception as e:
                logger.warning(f"[GeM] DB lookup failed: {e}")

        # Step 3: Get bid metadata (for parent ID)
        metadata = _get_bid_metadata(client, csrf, bid_id, bid_number)
        parent_id = None
        if metadata:
            parent_id = metadata.get("b_id_parent", [None])[0]
            bid_number = bid_number or (metadata.get("b_bid_number", [""])[0])
            parent_number = metadata.get("b_bid_number_parent", [""])[0]
            
            result["bid_details"] = {
                "bid_number": bid_number,
                "parent_bid_number": parent_number,
                "parent_id": parent_id,
                "category": metadata.get("b_category_name", [""])[0],
                "department": metadata.get("ba_official_details_deptName", [""])[0],
                "ministry": metadata.get("ba_official_details_minName", [""])[0],
                "start_date": metadata.get("final_start_date_sort", [""])[0],
                "end_date": metadata.get("final_end_date_sort", [""])[0],
                "quantity": metadata.get("b_total_quantity", [""])[0],
                "is_ra": metadata.get("b_bid_to_ra", [0])[0] == 1,
            }
            logger.info(f"[GeM] Bid {bid_id}: parent={parent_id}, category={result['bid_details']['category'][:50]}")
        else:
            logger.info(f"[GeM] No metadata found for {bid_id}, trying direct download")

        # Step 3: Download RA summary PDF
        ra_result = _download_pdf(client, f"{GEM_BASE}/showradocumentPdf/{bid_id}")
        if ra_result:
            content, fname = ra_result
            filename = fname or f"GeM-RA-{bid_id}.pdf"
            (bid_dir / filename).write_bytes(content)
            result["documents"].append({
                "name": filename,
                "size": len(content),
                "path": str(bid_dir / filename),
                "type": "ra_summary",
                "description": "RA Bid Summary (overview, dates, terms)",
            })
            logger.info(f"[GeM] RA summary: {filename} ({len(content):,} bytes)")

        # Step 4: Download parent bid document (the important one!)
        if parent_id:
            parent_result = _download_pdf(client, f"{GEM_BASE}/showbidDocument/{parent_id}")
            if parent_result:
                content, fname = parent_result
                filename = fname or f"GeM-Bidding-{parent_id}.pdf"
                (bid_dir / filename).write_bytes(content)
                result["documents"].append({
                    "name": filename,
                    "size": len(content),
                    "path": str(bid_dir / filename),
                    "type": "full_bid_document",
                    "description": "Full Bid Document (specifications, BOQ, delivery terms, ATC)",
                })
                logger.info(f"[GeM] Full bid doc: {filename} ({len(content):,} bytes)")

        # Step 5: Try showbidDocument for the RA bid itself (sometimes has content)
        if not parent_id:
            bid_result = _download_pdf(client, f"{GEM_BASE}/showbidDocument/{bid_id}")
            if bid_result:
                content, fname = bid_result
                filename = fname or f"GeM-Bidding-{bid_id}.pdf"
                (bid_dir / filename).write_bytes(content)
                result["documents"].append({
                    "name": filename,
                    "size": len(content),
                    "path": str(bid_dir / filename),
                    "type": "bid_document",
                    "description": "Bid Document",
                })

        # Step 6: Try direct RA document
        dra_result = _download_pdf(client, f"{GEM_BASE}/showdirectradocumentPdf/{bid_id}")
        if dra_result:
            content, fname = dra_result
            filename = fname or f"GeM-DRA-{bid_id}.pdf"
            (bid_dir / filename).write_bytes(content)
            result["documents"].append({
                "name": filename,
                "size": len(content),
                "path": str(bid_dir / filename),
                "type": "direct_ra_document",
                "description": "Direct RA Document",
            })

        result["success"] = len(result["documents"]) > 0

        if not result["success"]:
            result["errors"].append("No documents available for this bid")

        # Save result
        with open(bid_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)

        logger.info(f"[GeM] {'✅' if result['success'] else '❌'} Bid {bid_id}: {len(result['documents'])} document(s)")
        return result

    except Exception as e:
        logger.error(f"[GeM] Download failed for {bid_id}: {e}", exc_info=True)
        result["errors"].append(str(e))
        return result
    finally:
        client.close()


def download_gem_documents_batch(
    bids: List[Dict],
) -> List[Dict]:
    """
    Download documents for multiple GeM bids.
    Uses individual download_gem_document() for each — each gets full treatment
    (RA summary + parent bid document).
    """
    results = []
    for i, bid in enumerate(bids):
        bid_id = str(bid.get("bid_id") or bid.get("source_id"))
        bid_number = bid.get("bid_number", bid.get("tender_id", ""))
        title = bid.get("title", "")

        # Check if already downloaded with full docs
        existing = get_downloaded_gem_document(bid_id)
        if existing and existing.get("success") and len(existing.get("documents", [])) >= 2:
            logger.info(f"[GeM] [{i+1}/{len(bids)}] Already downloaded: {bid_id}")
            results.append(existing)
            continue

        result = download_gem_document(bid_id, bid_number, title)
        results.append(result)
        logger.info(f"[GeM] [{i+1}/{len(bids)}] {bid_id}: {len(result.get('documents',[]))} docs")

    success = sum(1 for r in results if r["success"])
    total_docs = sum(len(r.get("documents", [])) for r in results)
    logger.info(f"[GeM] Batch complete: {success}/{len(results)} bids, {total_docs} total documents")
    return results


def get_downloaded_gem_document(bid_id: str) -> Optional[Dict]:
    """Check if document already downloaded for this bid."""
    result_file = STORAGE_BASE / str(bid_id) / "result.json"
    if result_file.exists():
        with open(result_file) as f:
            return json.load(f)
    return None
