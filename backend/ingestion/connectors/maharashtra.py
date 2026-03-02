"""Maharashtra eProcurement portal connector.
Portal: https://mahatenders.gov.in
Note: Maharashtra uses mahatenders.gov.in which may differ from standard NIC layout.
"""

import logging
from typing import List, Optional
from datetime import datetime

from bs4 import BeautifulSoup

from backend.ingestion.connectors.nic_base import NICBaseConnector
from backend.ingestion.base_connector import RawTender

logger = logging.getLogger(__name__)


class MaharashtraConnector(NICBaseConnector):
    source_name = "maharashtra"
    base_url = "https://mahatenders.gov.in"
    state = "Maharashtra"
    
    # Maharashtra portal uses slightly different URL patterns
    active_tenders_path = "/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
    
    async def fetch_tenders(self, since: Optional[datetime] = None, page: int = 1) -> List[RawTender]:
        """Fetch from mahatenders.gov.in — tries NIC standard first, then fallback."""
        tenders = await super().fetch_tenders(since, page)
        
        if not tenders:
            # Fallback: try alternative URL patterns used by Maharashtra
            logger.info("[maharashtra] Trying alternative URL pattern")
            tenders = await self._fetch_alternative(page)
        
        return tenders

    async def _fetch_alternative(self, page: int = 1) -> List[RawTender]:
        """Alternative scraping for non-standard Maharashtra layout."""
        session = await self._get_session()
        tenders = []
        
        try:
            # Some Maharashtra portals use a different search interface
            url = f"{self.base_url}/tender/index"
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
            
            soup = BeautifulSoup(html, "lxml")
            table = self._find_tender_table(soup)
            if not table:
                return []
            
            for row in table.find_all("tr")[1:]:
                try:
                    tender = self._parse_table_row(row)
                    if tender:
                        tenders.append(tender)
                except Exception as e:
                    logger.warning(f"[maharashtra] Alt parse error: {e}")
                    
        except Exception as e:
            logger.error(f"[maharashtra] Alt fetch failed: {e}")
        
        return tenders
