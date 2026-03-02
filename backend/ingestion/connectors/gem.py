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
            url = f"{self.base_url}/showbidDocument/{source_id}"
            async with session.get(url, ssl=True) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

            soup = BeautifulSoup(html, "lxml")
            raw_text = soup.get_text(separator="\n", strip=True)
            doc_urls = [
                (a["href"] if a["href"].startswith("http") else f"{self.base_url}{a['href']}")
                for a in soup.find_all("a", href=True)
                if any(ext in a["href"].lower() for ext in [".pdf", ".doc", ".xls"])
            ]

            return RawTender(
                source_id=source_id,
                title=f"GeM Bid {source_id}",
                source_url=url,
                state="Central",
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
