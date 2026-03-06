"""Core tender data models."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Text, Numeric, Boolean, DateTime, Enum, Float,
    ForeignKey, Index, Integer, func, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from backend.database import Base


class TenderSource(str, enum.Enum):
    CPPP = "cppp"
    GEM = "gem"
    UP = "up"
    MAHARASHTRA = "maharashtra"
    UTTARAKHAND = "uttarakhand"
    HARYANA = "haryana"
    MP = "mp"


class TenderType(str, enum.Enum):
    OPEN_TENDER = "open_tender"
    NIT = "nit"
    RFP = "rfp"
    EOI = "eoi"
    AUCTION = "auction"
    RFQ = "rfq"
    LIMITED_TENDER = "limited_tender"
    OTHER = "other"


class TenderStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    AWARDED = "awarded"
    CANCELLED = "cancelled"
    CORRIGENDUM = "corrigendum"


class TenderStage(str, enum.Enum):
    BIDDING = "bidding"
    TECHNICAL_BID_OPENING = "technical_bid_opening"
    TECHNICAL_EVALUATION = "technical_evaluation"
    FINANCIAL_BID_OPENING = "financial_bid_opening"
    FINANCIAL_EVALUATION = "financial_evaluation"
    AWARDED = "awarded"
    CANCELLED = "cancelled"


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Source tracking
    source = Column(Enum(TenderSource), nullable=False, index=True)
    source_url = Column(Text)
    source_id = Column(String(500))  # ID on the source platform
    
    # Core fields
    tender_id = Column(String(500), index=True)  # NIT number
    title = Column(Text, nullable=False)
    description = Column(Text)
    
    # Organization
    department = Column(String(500), index=True)
    organization = Column(String(500))
    state = Column(String(100), index=True)
    
    # Classification
    category = Column(String(500))
    procurement_category = Column(String(500))
    tender_type = Column(Enum(TenderType), default=TenderType.OPEN_TENDER)
    
    # Financial
    tender_value_estimated = Column(Numeric(18, 2))
    emd_amount = Column(Numeric(18, 2))
    document_fee = Column(Numeric(18, 2))
    
    # Dates
    publication_date = Column(DateTime(timezone=True))
    bid_open_date = Column(DateTime(timezone=True))
    bid_close_date = Column(DateTime(timezone=True), index=True)
    pre_bid_meeting_date = Column(DateTime(timezone=True))
    pre_bid_meeting_venue = Column(Text)
    
    # Contact
    contact_person = Column(String(300))
    contact_email = Column(String(300))
    contact_phone = Column(String(50))
    
    # Structured data
    eligibility_criteria = Column(JSONB, default=dict)
    
    # Status & quality
    status = Column(Enum(TenderStatus), default=TenderStatus.ACTIVE, index=True)
    raw_text = Column(Text)  # Full extracted text for FTS
    fingerprint = Column(String(128), unique=True, index=True)  # Dedup hash
    parsed_quality_score = Column(Float, default=0.0)
    human_verified = Column(Boolean, default=False)
    tender_stage = Column(
        Enum(
            'bidding', 'technical_bid_opening', 'technical_evaluation',
            'financial_bid_opening', 'financial_evaluation', 'awarded', 'cancelled',
            name='tenderstage', create_type=False
        ),
        default='bidding'
    )
    
    # Archive flag – closed/expired tenders get archived but remain searchable
    is_archived = Column(Boolean, default=False, nullable=False, server_default=text("false"), index=True)

    # Full-text search vector
    search_vector = Column(TSVECTOR)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    documents = relationship("TenderDocument", back_populates="tender", cascade="all, delete-orphan")
    boq_items = relationship("BOQItem", back_populates="tender", cascade="all, delete-orphan")
    corrigenda = relationship("Corrigendum", back_populates="tender", cascade="all, delete-orphan")
    result = relationship("TenderResult", back_populates="tender", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tenders_source_source_id", "source", "source_id", unique=True),
        Index("ix_tenders_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_tenders_bid_close_status", "bid_close_date", "status"),
        Index("ix_tenders_state_category", "state", "category"),
    )


class TenderDocument(Base):
    __tablename__ = "tender_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    ocr_text = Column(Text)
    downloaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    tender = relationship("Tender", back_populates="documents")


class BOQItem(Base):
    __tablename__ = "boq_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    item_number = Column(Integer)
    description = Column(Text)
    quantity = Column(Numeric(18, 4))
    unit = Column(String(50))
    estimated_rate = Column(Numeric(18, 2))
    total_amount = Column(Numeric(18, 2))
    
    tender = relationship("Tender", back_populates="boq_items")


class Corrigendum(Base):
    __tablename__ = "corrigenda"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    corrigendum_number = Column(Integer)
    published_date = Column(DateTime(timezone=True))
    description = Column(Text)
    document_path = Column(Text)
    
    tender = relationship("Tender", back_populates="corrigenda")


class TenderResult(Base):
    __tablename__ = "tender_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, unique=True)
    winner_name = Column(String(500))
    winner_org = Column(String(500))
    award_value = Column(Numeric(18, 2))
    award_date = Column(DateTime(timezone=True))
    
    tender = relationship("Tender", back_populates="result")
