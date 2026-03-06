"""
Uttarakhand (NIC eProcurement) Tender Document Downloader — HTTP-only version.

Uses httpx + BeautifulSoup + 2Captcha. No Selenium/Chrome needed.

Proven workflow:
1. GET active tenders page → solve CAPTCHA → search by Tender ID
2. Follow DirectLink to detail page
3. Click "Download as zip" → CAPTCHA page
4. Solve CAPTCHA (must include Submit=Submit in POST) → session authorized
5. Re-load detail → click "Download as zip" again → file streams back

Works for all NIC eProcurement portals (UK, UP, Maharashtra, Haryana, MP).
"""

import base64
import json
import logging
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from backend.ingestion.connectors.captcha_solver import solve_captcha_image

logger = logging.getLogger(__name__)

# NIC portal configs
NIC_PORTALS = {
    "uttarakhand": {"base": "https://uktenders.gov.in", "state": "Uttarakhand"},
    "up": {"base": "https://etender.up.nic.in", "state": "Uttar Pradesh"},
    "maharashtra": {"base": "https://mahatenders.gov.in", "state": "Maharashtra"},
    "haryana": {"base": "https://etenders.hry.nic.in", "state": "Haryana"},
    "mp": {"base": "https://mptenders.gov.in", "state": "Madhya Pradesh"},
}

STORAGE_BASE = Path("storage/documents/tender_downloads")

# Timeouts
HTTP_TIMEOUT = 60  # seconds per request
MAX_CAPTCHA_ATTEMPTS = 6


def _make_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=HTTP_TIMEOUT,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )


def _get_captcha_bytes(soup: BeautifulSoup) -> Optional[bytes]:
    """Extract CAPTCHA image bytes from page."""
    el = soup.find(id="captchaImage")
    if not el:
        return None
    src = el.get("src", "")
    if not src or "," not in src:
        return None
    b64 = src.split(",", 1)[1].replace("%0A", "").replace("\n", "").replace(" ", "")
    if len(b64) % 4:
        b64 += "=" * (4 - len(b64) % 4)
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def _get_form_data(soup: BeautifulSoup) -> Optional[Dict[str, str]]:
    """Extract all form fields (hidden + text + submit) from first form."""
    form = soup.find("form", {"action": "/nicgep/app"})
    if not form:
        return None
    data = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if name and inp.get("type") not in ("radio",):
            data[name] = inp.get("value", "")
    # Default radio "size" to 0 if present
    radios = form.find_all("input", {"type": "radio", "name": "size"})
    if radios:
        data["size"] = "0"
    return data


def _solve_captcha_and_post(
    client: httpx.Client,
    base_url: str,
    soup: BeautifulSoup,
    extra_data: Optional[Dict] = None,
    submit_name: str = "Search",
    max_attempts: int = MAX_CAPTCHA_ATTEMPTS,
) -> Optional[Tuple[BeautifulSoup, httpx.Response]]:
    """Solve CAPTCHA on current page and submit form.
    
    Returns (result_soup, response) or None if all attempts fail.
    """
    for i in range(max_attempts):
        captcha_bytes = _get_captcha_bytes(soup)
        if not captcha_bytes:
            logger.warning(f"No CAPTCHA image on attempt {i + 1}")
            return None

        solution = solve_captcha_image(captcha_bytes)
        if not solution:
            logger.warning(f"2Captcha returned nothing on attempt {i + 1}")
            # Reload page to get fresh captcha
            continue

        logger.info(f"CAPTCHA attempt {i + 1}/{max_attempts}: '{solution}'")

        data = _get_form_data(soup)
        if not data:
            logger.error("No form found on page")
            return None

        data["captchaText"] = solution
        data["submitname"] = submit_name

        # Tapestry framework requires submit button name=value in POST data
        if submit_name in data or any(
            inp.get("name") == submit_name
            for inp in soup.find_all("input", {"type": "submit"})
        ):
            data[submit_name] = submit_name

        if extra_data:
            data.update(extra_data)

        r = client.post(f"{base_url}/nicgep/app", data=data)

        # Check for explicit rejection
        if "Invalid Captcha" in r.text or "invalidcaptcha" in r.text.lower():
            logger.info(f"CAPTCHA rejected (attempt {i + 1})")
            soup = BeautifulSoup(r.text, "html.parser")
            continue

        # Check for silent rejection (still on same captcha page)
        result_soup = BeautifulSoup(r.text, "html.parser")
        page_inp = result_soup.find("input", {"name": "page"})
        current_page = page_inp.get("value", "") if page_inp else ""

        # For download captcha, check if we left DocDownCaptcha
        if current_page == "DocDownCaptcha":
            logger.info(f"Still on captcha page (silent rejection, attempt {i + 1})")
            soup = result_soup
            continue

        return result_soup, r

    logger.error(f"All {max_attempts} CAPTCHA attempts failed")
    return None


def download_nic_tender_documents(
    tender_id: str,
    portal_key: str = "uttarakhand",
    title: str = "",
) -> Dict:
    """
    Download all documents for a tender from an NIC eProcurement portal.
    Pure HTTP — no Selenium/Chrome.
    
    Returns dict with: success, details, documents[], errors[]
    """
    portal = NIC_PORTALS.get(portal_key)
    if not portal:
        return {"success": False, "errors": [f"Unknown portal: {portal_key}"]}

    base_url = portal["base"]
    safe_id = tender_id.replace("/", "_").replace("\\", "_")
    tender_dir = STORAGE_BASE / portal_key / safe_id
    tender_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "tender_id": tender_id,
        "portal": portal_key,
        "success": False,
        "details": {},
        "documents": [],
        "files_dir": str(tender_dir),
        "errors": [],
    }

    client = _make_client()
    try:
        # ── Step 1: Load active tenders page ──
        logger.info(f"[{tender_id}] Loading {portal_key} portal...")
        r = client.get(f"{base_url}/nicgep/app?page=FrontEndLatestActiveTenders&service=page")
        soup = BeautifulSoup(r.text, "html.parser")

        # ── Step 2: Solve CAPTCHA + search by Tender ID ──
        logger.info(f"[{tender_id}] Searching...")
        search_result = _solve_captcha_and_post(
            client, base_url, soup,
            extra_data={"TenderId": tender_id, "size": "0"},
            submit_name="Search",
        )
        if not search_result:
            result["errors"].append("Search CAPTCHA failed after all attempts")
            return result

        search_soup, search_resp = search_result

        if tender_id not in search_resp.text:
            result["errors"].append(f"Tender {tender_id} not found in search results")
            return result

        # ── Step 3: Find and follow detail page link ──
        detail_href = None
        for a in search_soup.find_all("a", id="DirectLink"):
            h = a.get("href", "")
            if h:
                detail_href = h if h.startswith("http") else base_url + h
                break

        if not detail_href:
            # Fallback: any link with tender details
            for a in search_soup.find_all("a", title="View Tender Information"):
                h = a.get("href", "")
                if h:
                    detail_href = h if h.startswith("http") else base_url + h
                    break

        if not detail_href:
            result["errors"].append("Could not find tender detail link")
            return result

        logger.info(f"[{tender_id}] Loading detail page...")
        r_detail = client.get(detail_href)
        detail_soup = BeautifulSoup(r_detail.text, "html.parser")
        detail_html = r_detail.text

        # Save detail page HTML
        with open(tender_dir / "detail.html", "w", encoding="utf-8") as f:
            f.write(detail_html)

        # ── Step 4: Find "Download as zip" link ──
        zip_href = None
        for a in detail_soup.find_all("a"):
            aid = a.get("id", "")
            text = a.get_text().strip().lower()
            if aid == "DirectLink_8" or "download as zip" in text:
                h = a.get("href", "")
                if h:
                    zip_href = h if h.startswith("http") else base_url + h
                    break

        if not zip_href:
            result["errors"].append("No 'Download as zip' link on detail page")
            return result

        # ── Step 5: Click zip → get CAPTCHA page ──
        logger.info(f"[{tender_id}] Loading download CAPTCHA page...")
        r_zip = client.get(zip_href)
        zip_soup = BeautifulSoup(r_zip.text, "html.parser")

        # ── Step 6: Solve download CAPTCHA ──
        logger.info(f"[{tender_id}] Solving download CAPTCHA...")
        captcha_result = _solve_captcha_and_post(
            client, base_url, zip_soup,
            submit_name="Submit",
        )
        if not captcha_result:
            result["errors"].append("Download CAPTCHA failed after all attempts")
            return result

        logger.info(f"[{tender_id}] CAPTCHA solved, session authorized")

        # ── Step 7: Re-load detail page + click zip again → file downloads ──
        logger.info(f"[{tender_id}] Re-loading detail for download...")
        r_detail2 = client.get(detail_href)
        detail_soup2 = BeautifulSoup(r_detail2.text, "html.parser")

        zip_href2 = None
        for a in detail_soup2.find_all("a"):
            aid = a.get("id", "")
            text = a.get_text().strip().lower()
            if aid == "DirectLink_8" or "download as zip" in text:
                h = a.get("href", "")
                if h:
                    zip_href2 = h if h.startswith("http") else base_url + h
                    break

        if not zip_href2:
            result["errors"].append("Could not find zip link on second visit")
            return result

        r_download = client.get(zip_href2)
        content_type = r_download.headers.get("content-type", "")
        logger.info(
            f"[{tender_id}] Download response: {r_download.status_code}, "
            f"type={content_type}, size={len(r_download.content)}"
        )

        # ── Step 8: Save and extract file ──
        file_data = r_download.content

        if len(file_data) < 200 and b"<html" in file_data[:500].lower():
            result["errors"].append("Got HTML instead of file — download session may have expired")
            return result

        # Determine filename
        cd = r_download.headers.get("content-disposition", "")
        if "filename=" in cd:
            fname = cd.split("filename=")[-1].strip().strip('"')
        elif file_data[:2] == b"PK":
            fname = f"{safe_id}.zip"
        elif file_data[:4] == b"%PDF":
            fname = f"{safe_id}.pdf"
        else:
            fname = f"{safe_id}.bin"

        dl_path = tender_dir / "downloads"
        dl_path.mkdir(exist_ok=True)
        file_path = dl_path / fname
        file_path.write_bytes(file_data)
        logger.info(f"[{tender_id}] Saved: {fname} ({len(file_data):,} bytes)")

        # Extract ZIP if applicable
        if zipfile.is_zipfile(file_path):
            extract_dir = tender_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(file_path) as zf:
                zf.extractall(extract_dir)
                for info in zf.infolist():
                    if not info.is_dir():
                        result["documents"].append({
                            "name": info.filename,
                            "size": info.file_size,
                            "path": str(extract_dir / info.filename),
                        })
        else:
            result["documents"].append({
                "name": fname,
                "size": len(file_data),
                "path": str(file_path),
            })

        # ── Step 9: Extract details from saved HTML ──
        try:
            detail_parse = BeautifulSoup(detail_html, "html.parser")
            for row in detail_parse.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    k = cells[0].get_text(strip=True).rstrip(":")
                    v = cells[1].get_text(strip=True)
                    if k and v and len(k) < 100:
                        result["details"][k] = v
        except Exception as e:
            logger.warning(f"Detail extraction failed: {e}")

        result["success"] = True

        # Save result
        with open(tender_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)

        logger.info(f"[{tender_id}] ✅ Download complete: {len(result['documents'])} document(s)")
        return result

    except httpx.TimeoutException as e:
        logger.error(f"[{tender_id}] HTTP timeout: {e}")
        result["errors"].append(f"HTTP timeout: {e}")
        return result
    except Exception as e:
        logger.error(f"[{tender_id}] Download failed: {e}", exc_info=True)
        result["errors"].append(str(e))
        return result
    finally:
        client.close()


def get_downloaded_documents(tender_id: str, portal_key: str = "uttarakhand") -> Optional[Dict]:
    """Check if documents already downloaded for this tender."""
    safe_id = tender_id.replace("/", "_").replace("\\", "_")
    result_file = STORAGE_BASE / portal_key / safe_id / "result.json"
    if result_file.exists():
        with open(result_file) as f:
            return json.load(f)
    return None


def get_tender_summary(details: Dict) -> Dict:
    """Extract a clean summary from raw detail key-value pairs."""
    def find(keys):
        for k in keys:
            for dk, dv in details.items():
                if k.lower() in dk.lower() and dv and len(dv) < 300:
                    return dv
        return None

    return {
        "title": find(["Title", "Work Description"]),
        "organization": find(["Organisation Chain"]),
        "tender_ref": find(["Tender Reference Number"]),
        "tender_id": find(["Tender ID"]),
        "published_date": find(["Published Date"]),
        "bid_submission_start": find(["Bid Submission Start Date"]),
        "bid_submission_end": find(["Bid Submission End Date"]),
        "bid_opening_date": find(["Bid Opening Date"]),
        "pre_bid_meeting_date": find(["Pre Bid Meeting Date"]),
        "pre_bid_meeting_address": find(["Pre Bid Meeting Address"]),
        "emd_amount": find(["EMD Amount"]),
        "tender_fee": find(["Tender Fee in"]),
        "tender_value": find(["Tender Value"]),
        "tender_category": find(["Tender Category"]),
        "tender_type": find(["Tender Type"]),
        "location": find(["Location"]),
        "eligibility": find(["NDA/Pre Qualification"]),
        "contract_type": find(["Contract Type"]),
    }
