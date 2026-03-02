"""Saved searches, alerts, and notification models."""

import enum
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Enum, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database import Base


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"
    IN_APP = "in_app"


class AlertTrigger(str, enum.Enum):
    NEW_TENDER = "new_tender"
    CORRIGENDUM = "corrigendum"
    DEADLINE_APPROACHING = "deadline_approaching"
    AWARD_RESULT = "award_result"
    EXTENSION = "extension"


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(300), nullable=False)
    
    # Search criteria stored as JSON
    criteria = Column(JSONB, nullable=False)
    # Example: {"keywords": "road construction", "states": ["UP", "MH"], 
    #           "categories": ["civil"], "min_value": 1000000, "tender_types": ["open_tender"]}
    
    # Alert settings
    alert_enabled = Column(Boolean, default=True)
    alert_channels = Column(JSONB, default=["email"])  # ["email", "whatsapp", "sms"]
    alert_frequency = Column(String(50), default="instant")  # instant, daily_digest, weekly_digest
    
    is_active = Column(Boolean, default=True)
    last_matched_at = Column(DateTime(timezone=True))
    match_count = Column(String(20), default="0")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="saved_searches")
    alerts = relationship("Alert", back_populates="saved_search", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    saved_search_id = Column(UUID(as_uuid=True), ForeignKey("saved_searches.id", ondelete="CASCADE"))
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"))
    
    trigger = Column(Enum(AlertTrigger), nullable=False)
    is_read = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    saved_search = relationship("SavedSearch", back_populates="alerts")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"))
    
    channel = Column(Enum(NotificationChannel), nullable=False)
    subject = Column(String(500))
    body = Column(Text)
    
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True))
    error = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
