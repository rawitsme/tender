"""Base connector for NIC eProcurement state portals.

Most Indian state eProcurement portals run on NIC's platform (etenders.xxx.nic.in).
They share a similar HTML structure with minor variations. This base class
handles the common scraping logic; state-specific connectors override URLs
and field mappings.

Common NIC portal structure:
- Active tenders list at /nicgep/app?page=FrontEndLatestActiveTenders
- Tender detail via tender ID link
- Tables with standard column ordering (varies slightly per state)
"""

import re
import logging
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from backend.ingestion.base_connector import BaseConnector, RawTender

logger = logging.getLogger(__name__)


class NICBaseConnector(BaseConnector):
    """Base for NIC eProcurement portals used by most Indian states."""

    source_name = "nic"
    base_url = ""  # Override per state
    state = ""     # Override per state
    
    # NIC portals typically use these URL patterns
    active_tenders_path = "/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
    tender_detail_path = "/nicgep/app?page=FrontEndTenderDetailsViewForGuest&service=page"

    # Column indices in the tenders table (override if different per state)
    COL_SNO = 0
    COL_PUBLISHED_DATE = 1
    COL_CLOSING_DATE = 2
    COL_OPENING_DATE = 3
    COL_TITLE = 4
    COL_ORG = 5

    async def fetch_tenders(self, since: Optional[datetime] = None, page: int = 1) -> List[RawTender]:
        """Fetch active tenders from the NIC portal."""
        session = await self._get_session()
        tenders = []

        try:
            url = f"{self.base_url}{self.active_tenders_path}"
            logger.info(f"[{self.source_name}] Fetching: {url}")

            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"[{self.source_name}] Status {resp.status}")
                    return []
                html = await resp.text()

            soup = BeautifulSoup(html, "lxml")

            # Find the main tenders table
            table = self._find_tender_table(soup)
            if not table:
                logger.warning(f"[{self.source_name}] Could not find tender table")
                return []

            rows = table.find_all("tr")[1:]  # Skip header row

            for row in rows:
                try:
                    tender = self._parse_table_row(row)
                    if tender:
                        tenders.append(tender)
                except Exception as e:
                    logger.warning(f"[{self.source_name}] Row parse error: {e}")
                    continue

            logger.info(f"[{self.source_name}] Fetched {len(tenders)} tenders")

        except Exception as e:
            logger.error(f"[{self.source_name}] Fetch failed: {e}")

        return tenders

    def _find_tender_table(self, soup: BeautifulSoup):
        """Find the main tenders table in NIC portal HTML."""
        # Try common table identifiers
        for selector in [
            {"id": "table"},
            {"id": "tenderTable"},
            {"class_": "list_table"},
            {"class_": "table_list"},
            {"class_": "table"},
        ]:
            table = soup.find("table", selector)
            if table and len(table.find_all("tr")) > 1:
                return table

        # Fallback: find largest table with enough rows
        tables = soup.find_all("table")
        best = None
        best_rows = 0
        for t in tables:
            rows = len(t.find_all("tr"))
            if rows > best_rows:
                best = t
                best_rows = rows
        return best if best_rows > 2 else None

    def _parse_table_row(self, row) -> Optional[RawTender]:
        """Parse a single table row into a RawTender."""
        cols = row.find_all("td")
        if len(cols) < 5:
            return None

        # Extract title and link
        title_cell = cols[self.COL_TITLE] if len(cols) > self.COL_TITLE else cols[1]
        title_el = title_cell.find("a") or title_cell
        title = title_el.get_text(strip=True)
        if not title or len(title) < 5:
            return None

        # Source URL
        source_url = ""
        source_id = ""
        if title_el.name == "a" and title_el.get("href"):
            href = title_el["href"]
            source_url = href if href.startswith("http") else f"{self.base_url}{href}"
            id_match = re.search(r'id=(\d+)', href)
            if id_match:
                source_id = id_match.group(1)

        if not source_id:
            source_id = f"{self.source_name}_{hash(title) % 10**8}"

        # Dates
        pub_date = self._parse_date(cols[self.COL_PUBLISHED_DATE].get_text(strip=True)) if len(cols) > self.COL_PUBLISHED_DATE else None
        close_date = self._parse_date(cols[self.COL_CLOSING_DATE].get_text(strip=True)) if len(cols) > self.COL_CLOSING_DATE else None

        # Department/Organization
        department = cols[self.COL_ORG].get_text(strip=True) if len(cols) > self.COL_ORG else None

        # Extract NIT number from title
        tender_id = None
        nit_match = re.search(r'(NIT[- ]?(?:No\.?)?[- ]?\w+[-/]\w+|[\w/]+-\d{4,})', title)
        if nit_match:
            tender_id = nit_match.group(1)

        return RawTender(
            source_id=source_id,
            title=title[:1000],
            source_url=source_url,
            tender_id=tender_id,
            department=department,
            organization=department,
            state=self.state,
            publication_date=pub_date,
            bid_close_date=close_date,
            tender_type="open_tender",
        )

    async def fetch_tender_detail(self, source_id: str) -> Optional[RawTender]:
        """Fetch full tender details from NIC portal."""
        session = await self._get_session()
        try:
            url = f"{self.base_url}{self.tender_detail_path}&id={source_id}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

            soup = BeautifulSoup(html, "lxml")
            raw_text = soup.get_text(separator="\n", strip=True)

            # Extract key-value pairs from detail page
            fields = {}
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True).lower().strip(":")
                    val = cells[1].get_text(strip=True)
                    if key and val:
                        fields[key] = val

            # Document links
            doc_urls = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if any(ext in href.lower() for ext in [".pdf", ".doc", ".xls", ".zip"]):
                    full = href if href.startswith("http") else f"{self.base_url}{href}"
                    doc_urls.append(full)

            return RawTender(
                source_id=source_id,
                title=fields.get("tender title", fields.get("work description", f"Tender {source_id}")),
                source_url=url,
                tender_id=fields.get("tender id", fields.get("nit no", fields.get("nit/rfp no", None))),
                description=fields.get("work description", fields.get("brief description", None)),
                department=fields.get("organisation name", fields.get("department", None)),
                organization=fields.get("organisation name", None),
                state=self.state,
                category=fields.get("product category", fields.get("category", None)),
                tender_value=self._parse_amount(fields.get("tender value", fields.get("estimated cost", ""))),
                emd_amount=self._parse_amount(fields.get("emd", fields.get("earnest money deposit", ""))),
                document_fee=self._parse_amount(fields.get("tender fee", fields.get("document fee", ""))),
                publication_date=self._parse_date(fields.get("published date", fields.get("publish date", ""))),
                bid_close_date=self._parse_date(
                    fields.get("bid submission end date", fields.get("closing date", fields.get("bid due date", "")))
                ),
                pre_bid_meeting_date=self._parse_date(fields.get("pre-bid meeting date", "")),
                pre_bid_meeting_venue=fields.get("pre-bid meeting venue", fields.get("pre-bid meeting place", None)),
                contact_person=fields.get("tender inviting authority", fields.get("officer inviting bids", None)),
                contact_email=fields.get("email", fields.get("e-mail", None)),
                contact_phone=fields.get("phone", fields.get("contact no", None)),
                raw_text=raw_text[:50000],
                document_urls=doc_urls,
            )

        except Exception as e:
            logger.error(f"[{self.source_name}] Detail fetch failed for {source_id}: {e}")
            return None

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        date_str = date_str.strip()
        formats = [
            "%d-%b-%Y %I:%M %p", "%d-%b-%Y %H:%M", "%d-%m-%Y %H:%M",
            "%d/%m/%Y %H:%M", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_amount(amount_str: str) -> Optional[float]:
        if not amount_str:
            return None
        cleaned = re.sub(r'[₹Rs.\s,]', '', amount_str)
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
