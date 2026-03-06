"""
GeM (Government eMarketplace) Document Downloader — HTTP-only.

Downloads bid documents from bidplus.gem.gov.in using pure httpx.
No Selenium/Chrome needed.

URL patterns (based on bid type):
- RA bids (b_bid_to_ra=1): /showradocumentPdf/{bid_id}  → GeM-RA-{id}.pdf
- Regular bids:             /showbidDocument/{bid_id}     → GeM-Bidding-{id}.pdf
- Direct RA:                /showdirectradocumentPdf/{id} → GeM-DRA-{id}.pdf

Currently all ongoing GeM bids are RA type, so showradocumentPdf is primary.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEM_BASE = "https://bidplus.gem.gov.in"
STORAGE_BASE = Path("storage/documents/gem_downloads")

# Document URL patterns to try, in order of likelihood
DOC_PATTERNS = [
    ("showradocumentPdf", "GeM-RA-{bid_id}.pdf"),
    ("showbidDocument", "GeM-Bidding-{bid_id}.pdf"),
    ("showdirectradocumentPdf", "GeM-DRA-{bid_id}.pdf"),
]


def _make_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )


def _init_session(client: httpx.Client):
    """Visit all-bids page to get session cookies (needed for downloads)."""
    r = client.get(f"{GEM_BASE}/all-bids")
    if r.status_code != 200:
        logger.error(f"[GeM] Failed to init session: {r.status_code}")
        return False
    logger.info(f"[GeM] Session initialized, cookies: {list(client.cookies.keys())}")
    return True


def download_gem_document(
    bid_id: str,
    bid_number: str = "",
    title: str = "",
) -> Dict:
    """
    Download document for a GeM bid.
    
    Args:
        bid_id: The numeric bid ID (source_id in our DB)
        bid_number: e.g. "GEM/2026/R/636911" (for logging)
        title: Bid title (for logging)
    
    Returns dict with: success, documents[], errors[]
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
        "errors": [],
        "files_dir": str(bid_dir),
    }

    client = _make_client()
    try:
        # Initialize session
        if not _init_session(client):
            result["errors"].append("Failed to initialize GeM session")
            return result

        # Try each document URL pattern
        for pattern, filename_template in DOC_PATTERNS:
            url = f"{GEM_BASE}/{pattern}/{bid_id}"
            logger.info(f"[GeM] Trying {pattern}/{bid_id}...")

            r = client.get(url)

            if r.status_code != 200:
                logger.info(f"[GeM] {pattern}: HTTP {r.status_code}")
                continue

            content = r.content
            if len(content) == 0:
                logger.info(f"[GeM] {pattern}: empty response")
                continue

            # Verify it's a real PDF
            if content[:4] != b"%PDF":
                logger.warning(f"[GeM] {pattern}: not a PDF (starts with {content[:20]})")
                continue

            # Get filename from Content-Disposition or use template
            cd = r.headers.get("content-disposition", "")
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip().strip('"')
            else:
                filename = filename_template.format(bid_id=bid_id)

            # Save
            file_path = bid_dir / filename
            file_path.write_bytes(content)

            result["documents"].append({
                "name": filename,
                "size": len(content),
                "path": str(file_path),
                "url_pattern": pattern,
            })

            logger.info(f"[GeM] ✅ Downloaded: {filename} ({len(content):,} bytes)")
            result["success"] = True
            break  # Got one, that's enough

        if not result["success"]:
            result["errors"].append("No document available from any URL pattern")
            logger.warning(f"[GeM] No document found for bid {bid_id}")

        # Save result
        with open(bid_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)

        return result

    except Exception as e:
        logger.error(f"[GeM] Download failed for {bid_id}: {e}", exc_info=True)
        result["errors"].append(str(e))
        return result
    finally:
        client.close()


def download_gem_documents_batch(
    bids: List[Dict],
    max_concurrent: int = 5,
) -> List[Dict]:
    """
    Download documents for multiple GeM bids.
    
    Args:
        bids: List of dicts with at least 'bid_id' key
              Optional: 'bid_number', 'title'
    
    Returns list of result dicts.
    """
    results = []
    client = _make_client()

    try:
        if not _init_session(client):
            return [{"bid_id": b.get("bid_id"), "success": False,
                      "errors": ["Session init failed"]} for b in bids]

        for i, bid in enumerate(bids):
            bid_id = bid.get("bid_id") or bid.get("source_id")
            bid_number = bid.get("bid_number", bid.get("tender_id", ""))
            title = bid.get("title", "")

            safe_id = str(bid_id)
            bid_dir = STORAGE_BASE / safe_id
            bid_dir.mkdir(parents=True, exist_ok=True)

            result = {
                "bid_id": bid_id,
                "bid_number": bid_number,
                "portal": "gem",
                "success": False,
                "documents": [],
                "errors": [],
                "files_dir": str(bid_dir),
            }

            # Check if already downloaded
            result_file = bid_dir / "result.json"
            if result_file.exists():
                try:
                    existing = json.loads(result_file.read_text())
                    if existing.get("success"):
                        logger.info(f"[GeM] Already downloaded: {bid_id}")
                        results.append(existing)
                        continue
                except Exception:
                    pass

            for pattern, filename_template in DOC_PATTERNS:
                url = f"{GEM_BASE}/{pattern}/{bid_id}"
                try:
                    r = client.get(url)
                    if r.status_code == 200 and len(r.content) > 0 and r.content[:4] == b"%PDF":
                        cd = r.headers.get("content-disposition", "")
                        if "filename=" in cd:
                            filename = cd.split("filename=")[-1].strip().strip('"')
                        else:
                            filename = filename_template.format(bid_id=bid_id)

                        file_path = bid_dir / filename
                        file_path.write_bytes(r.content)

                        result["documents"].append({
                            "name": filename,
                            "size": len(r.content),
                            "path": str(file_path),
                            "url_pattern": pattern,
                        })
                        result["success"] = True
                        logger.info(f"[GeM] [{i+1}/{len(bids)}] ✅ {bid_id}: {filename} ({len(r.content):,} bytes)")
                        break
                except Exception as e:
                    logger.warning(f"[GeM] {pattern}/{bid_id} error: {e}")

            if not result["success"]:
                result["errors"].append("No document available")
                logger.info(f"[GeM] [{i+1}/{len(bids)}] ❌ {bid_id}: no document")

            with open(bid_dir / "result.json", "w") as f:
                json.dump(result, f, indent=2, default=str)
            results.append(result)

    finally:
        client.close()

    success = sum(1 for r in results if r["success"])
    logger.info(f"[GeM] Batch complete: {success}/{len(results)} downloaded")
    return results


def get_downloaded_gem_document(bid_id: str) -> Optional[Dict]:
    """Check if document already downloaded for this bid."""
    result_file = STORAGE_BASE / str(bid_id) / "result.json"
    if result_file.exists():
        with open(result_file) as f:
            return json.load(f)
    return None
