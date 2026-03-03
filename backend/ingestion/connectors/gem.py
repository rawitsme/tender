"""Government eMarketplace (GeM) connector.

GeM uses AJAX at https://bidplus.gem.gov.in/all-bids-data
We GET /all-bids to get session cookies + CSRF, then POST for bid data.
Returns Solr-style JSON with ~50k+ active bids.
"""

import re
import json
import logging
from datetime import datetime
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup

from backend.ingestion.base_connector import BaseConnector, RawTender

logger = logging.getLogger(__name__)


class GeMConnector(BaseConnector):
    source_name = "gem"
    base_url = "https://bidplus.gem.gov.in"

    async def fetch_tenders(self, since: Optional[datetime] = None, page: int = 1) -> List[RawTender]:
        """Fetch bids from GeM via AJAX API."""
        tenders = []

        try:
            # Need a fresh session with cookie jar for CSRF
            jar = aiohttp.CookieJar()
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(
                headers=self._headers, cookie_jar=jar, timeout=timeout
            ) as session:
                # Step 1: Get page + CSRF token + cookies
                async with session.get(f"{self.base_url}/all-bids", ssl=True) as resp:
                    html = await resp.text()

                csrf_match = re.search(r"csrf_bd_gem_nk'\s*:\s*'([a-f0-9]+)'", html)
                if not csrf_match:
                    logger.warning("GeM: Could not extract CSRF token")
                    return []

                csrf_token = csrf_match.group(1)

                # Step 2: POST to AJAX endpoint
                payload = {
                    "param": {"searchBid": "", "searchType": "fullText"},
                    "filter": {
                        "bidStatusType": "ongoing_bids",
                        "byType": "all",
                        "highBidValue": "",
                        "byEndDate": {"from": "", "to": ""},
                        "sort": "Bid-Start-Date-Latest",
                    },
                    "page": page,
                }

                form_data = aiohttp.FormData()
                form_data.add_field("payload", json.dumps(payload))
                form_data.add_field("csrf_bd_gem_nk", csrf_token)

                async with session.post(
                    f"{self.base_url}/all-bids-data",
                    data=form_data,
                    ssl=True,
                ) as resp:
                    text = await resp.text()
                    data = json.loads(text)

                if data.get("code") != 200:
                    logger.error(f"GeM API error code: {data.get('code')}")
                    return []

                # Step 3: Parse Solr response
                docs = data.get("response", {}).get("response", {}).get("docs", [])
                total = data.get("response", {}).get("response", {}).get("numFound", 0)

                for doc in docs:
                    try:
                        bid_number = self._first(doc.get("b_bid_number", []))
                        category = self._first(doc.get("bd_category_name", doc.get("b_category_name", [])))
                        start_date = self._first(doc.get("final_start_date_sort", []))
                        end_date = self._first(doc.get("final_end_date_sort", []))
                        buyer_email = self._first(doc.get("b.b_created_by", []))
                        department = self._first(doc.get("ba_official_details_deptName", []))
                        organization = self._first(doc.get("ba_official_details_minName", []))
                        quantity = self._first(doc.get("b_total_quantity", []))
                        
                        title = category or bid_number or "GeM Bid"
                        desc_parts = []
                        if quantity:
                            desc_parts.append(f"Quantity: {quantity}")
                        if department:
                            desc_parts.append(f"Department: {department}")

                        raw = RawTender(
                            source_id=str(doc.get("id", "")),
                            title=str(title)[:2000],
                            description="; ".join(desc_parts) if desc_parts else None,
                            source_url=f"{self.base_url}/showbidDocument/{doc.get('id', '')}",
                            tender_id=bid_number,
                            state="Central",
                            category=category,
                            department=department,
                            organization=organization,
                            tender_type="rfq",
                            publication_date=self._parse_iso(start_date),
                            bid_close_date=self._parse_iso(end_date),
                            contact_email=buyer_email,
                            raw_text=json.dumps(doc, default=str)[:10000],
                        )
                        tenders.append(raw)
                    except Exception as e:
                        logger.warning(f"GeM: Error parsing doc: {e}")

                logger.info(f"GeM: Fetched {len(tenders)} of {total} total bids (page {page})")

        except Exception as e:
            logger.error(f"GeM fetch failed: {e}")

        return tenders

    async def fetch_tender_detail(self, source_id: str) -> Optional[RawTender]:
        session = await self._get_session()
        try:
            # Use the correct bidplus domain for document details
            url = f"https://bidplus.gem.gov.in/showbidDocument/{source_id}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            async with session.get(url, headers=headers, ssl=True) as resp:
                if resp.status != 200:
                    return None
                
                content_type = resp.headers.get('content-type', '').lower()
                
                if 'pdf' in content_type:
                    # GeM returns PDF directly - this IS the document
                    pdf_content = await resp.read()
                    logger.info(f"GeM returned PDF document: {len(pdf_content):,} bytes")
                    
                    # Extract text from PDF if possible
                    raw_text = ""
                    try:
                        from backend.ingestion.parser.pdf_parser import extract_text_from_pdf
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                            tmp.write(pdf_content)
                            tmp_path = tmp.name
                        
                        text_content, _ = extract_text_from_pdf(Path(tmp_path))
                        raw_text = text_content[:10000] if text_content else ""
                        
                        import os
                        os.unlink(tmp_path)
                        
                    except Exception as e:
                        logger.warning(f"PDF text extraction failed: {e}")
                        raw_text = f"PDF document ({len(pdf_content):,} bytes) - text extraction failed"
                    
                    # For GeM, the document URL IS the detail URL  
                    doc_urls = [url]
                    
                    # Extract basic info from our existing tender data
                    # Since GeM returns PDF directly, we get limited structured data
                    return RawTender(
                        source_id=source_id,
                        title=f"GeM Bid {source_id}",
                        source_url=url,
                        description=f"GeM procurement document ({len(pdf_content):,} bytes PDF)",
                        department="GeM Portal",
                        organization="Government e-Marketplace",
                        state="Central",
                        category="GeM Procurement",
                        tender_type="rfq",
                        raw_text=raw_text,
                        document_urls=doc_urls,
                    )
                    
                else:
                    # HTML response - parse normally
                    html = await resp.text()
                    soup = BeautifulSoup(html, "lxml")
                    raw_text = soup.get_text(separator="\n", strip=True)
                    
                    # Extract structured info from GeM detail page
                    details = {}
                    
                    # Look for key-value pairs in various formats
                    for row in soup.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            key = cells[0].get_text(strip=True).lower().rstrip(":")
                            val = cells[1].get_text(strip=True)
                            if key and val and len(val) < 5000:
                                details[key] = val
                    
                    # Find document links
                    doc_urls = []
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if any(ext in href.lower() for ext in [".pdf", ".doc", ".xls", ".xlsx", ".docx"]):
                            full_url = href if href.startswith("http") else f"https://bidplus.gem.gov.in{href}"
                            doc_urls.append(full_url)
                    
                    # Parse financial values
                    def parse_amount(text):
                        if not text:
                            return None
                        import re
                        # Remove common prefixes and symbols
                        cleaned = re.sub(r'[₹Rs.\s,]', '', str(text))
                        try:
                            # Handle crore/lakh
                            if 'crore' in text.lower():
                                return float(cleaned.replace('crore', '').replace('cr', '')) * 10000000
                            elif 'lakh' in text.lower():
                                return float(cleaned.replace('lakh', '').replace('lac', '')) * 100000
                            else:
                                return float(cleaned) if cleaned.replace('.', '').isdigit() else None
                        except:
                            return None

                    return RawTender(
                        source_id=source_id,
                        title=details.get("title", f"GeM Bid {source_id}"),
                        source_url=url,
                        description=details.get("description", details.get("item description")),
                        department=details.get("department", details.get("buyer organization")),
                        organization=details.get("ministry", details.get("buyer")),
                        state="Central",
                        category=details.get("category", details.get("product category")),
                        tender_type="rfq",
                        tender_value=parse_amount(details.get("estimated value")),
                        emd_amount=parse_amount(details.get("emd", details.get("earnest money"))),
                        document_fee=parse_amount(details.get("document fee")),
                        bid_open_date=self._parse_iso(details.get("bid opening date")),
                        bid_close_date=self._parse_iso(details.get("bid closing date")),
                        contact_person=details.get("contact person"),
                        contact_email=details.get("email"),
                        contact_phone=details.get("phone"),
                        raw_text=raw_text[:50000],
                        document_urls=doc_urls,
                    )
                    
        except Exception as e:
            logger.error(f"GeM detail failed: {e}")
            return None

    @staticmethod
    def _first(val):
        """Get first element from Solr multi-value field."""
        if isinstance(val, list):
            return val[0] if val else None
        return val

    @staticmethod
    def _parse_iso(date_str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            # Solr format: 2026-02-24T14:00:00Z
            return datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        except:
            return None
