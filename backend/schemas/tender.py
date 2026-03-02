"""Pydantic schemas for tender API."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class TenderBase(BaseModel):
    title: str
    description: Optional[str] = None
    department: Optional[str] = None
    organization: Optional[str] = None
    state: Optional[str] = None
    category: Optional[str] = None
    tender_type: Optional[str] = "open_tender"
    tender_value_estimated: Optional[Decimal] = None
    emd_amount: Optional[Decimal] = None
    document_fee: Optional[Decimal] = None
    bid_close_date: Optional[datetime] = None


class TenderCreate(TenderBase):
    source: str
    source_url: Optional[str] = None
    source_id: Optional[str] = None
    tender_id: Optional[str] = None


class TenderResponse(TenderBase):
    id: UUID
    source: str
    source_url: Optional[str] = None
    source_id: Optional[str] = None
    tender_id: Optional[str] = None
    publication_date: Optional[datetime] = None
    bid_open_date: Optional[datetime] = None
    pre_bid_meeting_date: Optional[datetime] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    eligibility_criteria: Optional[dict] = None
    status: str = "active"
    parsed_quality_score: Optional[float] = None
    human_verified: bool = False
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenderListResponse(BaseModel):
    tenders: List[TenderResponse]
    total: int
    page: int
    page_size: int


class TenderSearchRequest(BaseModel):
    query: Optional[str] = None
    states: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    departments: Optional[List[str]] = None
    tender_types: Optional[List[str]] = None
    status: Optional[List[str]] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    bid_close_from: Optional[datetime] = None
    bid_close_to: Optional[datetime] = None
    published_from: Optional[datetime] = None
    published_to: Optional[datetime] = None
    closing_within: Optional[str] = None  # today, 3days, 7days, 30days
    department: Optional[str] = None  # text search
    category: Optional[str] = None  # text search
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = "publication_date"
    sort_order: str = "desc"


class BOQItemResponse(BaseModel):
    id: UUID
    item_number: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    estimated_rate: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None

    class Config:
        from_attributes = True


class TenderDetailResponse(TenderResponse):
    raw_text: Optional[str] = None
    documents: List[dict] = []
    boq_items: List[BOQItemResponse] = []
    corrigenda: List[dict] = []
    result: Optional[dict] = None


class TenderStatsResponse(BaseModel):
    total_tenders: int
    active_tenders: int
    tenders_by_source: dict
    tenders_by_state: dict
    avg_tender_value: Optional[float] = None
    tenders_closing_this_week: int
    tenders_by_department: Optional[dict] = None
    tenders_by_organization: Optional[dict] = None
