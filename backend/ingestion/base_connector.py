"""Abstract base class for all tender source connectors."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path

import aiohttp

from backend.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class RawTender:
    """Raw tender data as scraped from a source, before normalization."""
    source_id: str
    title: str
    source_url: str = ""
    tender_id: Optional[str] = None  # NIT number
    description: Optional[str] = None
    department: Optional[str] = None
    organization: Optional[str] = None
    state: Optional[str] = None
    category: Optional[str] = None
    tender_type: Optional[str] = None
    tender_value: Optional[float] = None
    emd_amount: Optional[float] = None
    document_fee: Optional[float] = None
    publication_date: Optional[datetime] = None
    bid_open_date: Optional[datetime] = None
    bid_close_date: Optional[datetime] = None
    pre_bid_meeting_date: Optional[datetime] = None
    pre_bid_meeting_venue: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    eligibility: Optional[Dict] = None
    raw_text: Optional[str] = None
    document_urls: List[str] = field(default_factory=list)


@dataclass
class ConnectorHealth:
    source: str
    is_healthy: bool
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    total_fetched: int = 0


class BaseConnector(ABC):
    """Abstract base for all tender source connectors."""

    source_name: str = "unknown"
    base_url: str = ""
    state: Optional[str] = None  # For state-specific connectors

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT_SECONDS)
            self.session = aiohttp.ClientSession(headers=self._headers, timeout=timeout)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    @abstractmethod
    async def fetch_tenders(self, since: Optional[datetime] = None, page: int = 1) -> List[RawTender]:
        """Fetch tenders from the source. Implement pagination internally."""
        ...

    @abstractmethod
    async def fetch_tender_detail(self, source_id: str) -> Optional[RawTender]:
        """Fetch full details for a single tender."""
        ...

    async def download_documents(self, doc_urls: List[str], dest_dir: Path) -> List[Path]:
        """Download documents from the given URLs to dest_dir."""
        session = await self._get_session()
        downloaded = []
        dest_dir.mkdir(parents=True, exist_ok=True)

        for url in doc_urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        filename = url.split("/")[-1].split("?")[0] or "document.pdf"
                        dest = dest_dir / filename
                        content = await resp.read()
                        dest.write_bytes(content)
                        downloaded.append(dest)
                        logger.info(f"Downloaded: {filename} ({len(content)} bytes)")
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")

        return downloaded

    async def health_check(self) -> ConnectorHealth:
        """Check if the source is accessible."""
        session = await self._get_session()
        try:
            async with session.get(self.base_url) as resp:
                return ConnectorHealth(
                    source=self.source_name,
                    is_healthy=resp.status == 200,
                )
        except Exception as e:
            return ConnectorHealth(
                source=self.source_name,
                is_healthy=False,
                last_error=str(e),
            )

    def __repr__(self):
        return f"<{self.__class__.__name__} source={self.source_name}>"
