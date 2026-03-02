"""Central Public Procurement Portal (eprocure.gov.in) connector.

CPPP uses a search form with POST requests. The main search URL returns
paginated HTML results that we parse with BeautifulSoup.
"""

import re
import logging
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from backend.ingestion.base_connector import BaseConnector, RawTender

logger = logging.getLogger(__name__)


class CPPPConnector(BaseConnector):
    source_name = "cppp"
    base_url = "https://eprocure.gov.in/eprocure/app"
    search_url = "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page"

    async def fetch_tenders(self, since: Optional[datetime] = None, page: int = 1) -> List[RawTender]:
        """Fetch active tenders from CPPP search page."""
        session = await self._get_session()
        tenders = []

        try:
            # CPPP uses a GET-based paginated listing for active tenders
            params = {
                "page": "FrontEndLatestActiveTenders",
                "service": "page",
            }
            url = f"{self.base_url}?page=FrontEndLatestActiveTenders&service=page"

            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"CPPP returned status {resp.status}")
                    return []
                html = await resp.text()

            soup = BeautifulSoup(html, "lxml")

            # CPPP renders tenders in a table with class 'list_table' or similar
            table = soup.find("table", {"id": "table"}) or soup.find("table", class_="list_table")
            if not table:
                # Try finding any data table
                tables = soup.find_all("table")
                for t in tables:
                    if t.find("tr") and len(t.find_all("tr")) > 2:
                        table = t
                        break

            if not table:
                logger.warning("CPPP: Could not find tender table in HTML")
                return []

            rows = table.find_all("tr")[1:]  # Skip header

            for row in rows:
                try:
                    cols = row.find_all("td")
                    if len(cols) < 5:
                        continue

                    # Extract fields from table columns
                    # Typical CPPP columns: S.No, e-Published Date, Bid Submission Closing Date,
                    # Tender Opening Date, Title/Ref.No/Tender ID, Organisation
                    tender_link = cols[4].find("a") if len(cols) > 4 else None
                    title_text = cols[4].get_text(strip=True) if len(cols) > 4 else cols[1].get_text(strip=True)
                    
                    source_url = ""
                    source_id = ""
                    if tender_link and tender_link.get("href"):
                        href = tender_link["href"]
                        source_url = href if href.startswith("http") else f"https://eprocure.gov.in{href}"
                        # Extract tender ID from URL
                        id_match = re.search(r'id=(\d+)', href)
                        if id_match:
                            source_id = id_match.group(1)

                    # Parse dates
                    pub_date = self._parse_date(cols[1].get_text(strip=True)) if len(cols) > 1 else None
                    close_date = self._parse_date(cols[2].get_text(strip=True)) if len(cols) > 2 else None
                    
                    department = cols[5].get_text(strip=True) if len(cols) > 5 else None

                    # Extract tender ID / NIT from title text
                    tender_id = None
                    nit_match = re.search(r'(NIT[- ]?\w+[-/]\w+|[\w/]+-\d{4,})', title_text)
                    if nit_match:
                        tender_id = nit_match.group(1)

                    raw = RawTender(
                        source_id=source_id or f"cppp_{hash(title_text)}",
                        title=title_text[:1000],
                        source_url=source_url,
                        tender_id=tender_id,
                        department=department,
                        organization=department,
                        state="Central",
                        publication_date=pub_date,
                        bid_close_date=close_date,
                        tender_type="open_tender",
                    )
                    tenders.append(raw)

                except Exception as e:
                    logger.warning(f"CPPP: Error parsing row: {e}")
                    continue

            logger.info(f"CPPP: Fetched {len(tenders)} tenders")

        except Exception as e:
            logger.error(f"CPPP fetch failed: {e}")

        return tenders

    async def fetch_tender_detail(self, source_id: str) -> Optional[RawTender]:
        """Fetch full details for a CPPP tender by clicking through to detail page."""
        session = await self._get_session()
        try:
            url = f"{self.base_url}?page=FrontEndTendersByOrganisation&service=page&id={source_id}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

            soup = BeautifulSoup(html, "lxml")
            
            # Extract all text content for raw_text
            raw_text = soup.get_text(separator="\n", strip=True)
            
            # Try to extract structured fields from detail page
            fields = {}
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True).lower()
                    val = cells[1].get_text(strip=True)
                    fields[key] = val

            # Map fields
            title = fields.get("tender title", fields.get("work description", ""))
            
            # Find document download links
            doc_urls = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if any(ext in href.lower() for ext in [".pdf", ".doc", ".xls", ".zip"]):
                    full_url = href if href.startswith("http") else f"https://eprocure.gov.in{href}"
                    doc_urls.append(full_url)

            return RawTender(
                source_id=source_id,
                title=title or f"CPPP Tender {source_id}",
                source_url=f"{self.base_url}?page=FrontEndTendersByOrganisation&service=page&id={source_id}",
                tender_id=fields.get("tender id", fields.get("nit/rfp no", None)),
                description=fields.get("work description", None),
                department=fields.get("organisation name", fields.get("department", None)),
                tender_value=self._parse_amount(fields.get("tender value", fields.get("estimated cost", ""))),
                emd_amount=self._parse_amount(fields.get("emd", fields.get("earnest money", ""))),
                document_fee=self._parse_amount(fields.get("document fee", fields.get("tender fee", ""))),
                publication_date=self._parse_date(fields.get("published date", "")),
                bid_close_date=self._parse_date(fields.get("bid submission end date", fields.get("closing date", ""))),
                pre_bid_meeting_date=self._parse_date(fields.get("pre-bid meeting date", "")),
                contact_person=fields.get("tender inviting authority", None),
                contact_email=fields.get("email", None),
                raw_text=raw_text[:50000],
                document_urls=doc_urls,
            )

        except Exception as e:
            logger.error(f"CPPP detail fetch failed for {source_id}: {e}")
            return None

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Parse various Indian date formats."""
        if not date_str:
            return None
        date_str = date_str.strip()
        formats = [
            "%d-%b-%Y %I:%M %p",
            "%d-%b-%Y %H:%M",
            "%d-%m-%Y %H:%M",
            "%d/%m/%Y %H:%M",
            "%d-%b-%Y",
            "%d-%m-%Y",
            "%d/%m/%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_amount(amount_str: str) -> Optional[float]:
        """Parse Indian currency amounts like '₹ 1,50,000' or 'Rs. 15 Lakh'."""
        if not amount_str:
            return None
        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[₹Rs.\s,]', '', amount_str)
        
        # Handle Lakh/Crore
        multiplier = 1
        lower = amount_str.lower()
        if 'crore' in lower or 'cr' in lower:
            multiplier = 10_000_000
            cleaned = re.sub(r'(?i)(crore|cr)', '', cleaned)
        elif 'lakh' in lower or 'lac' in lower:
            multiplier = 100_000
            cleaned = re.sub(r'(?i)(lakh|lac)', '', cleaned)

        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None
