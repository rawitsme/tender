"""Pydantic schemas for saved searches and alerts."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel


class SavedSearchCreate(BaseModel):
    name: str
    criteria: dict  # {"keywords": "...", "states": [...], "categories": [...], ...}
    alert_enabled: bool = True
    alert_channels: List[str] = ["email"]
    alert_frequency: str = "instant"


class SavedSearchResponse(BaseModel):
    id: UUID
    name: str
    criteria: dict
    alert_enabled: bool
    alert_channels: list
    alert_frequency: str
    is_active: bool
    match_count: str
    last_matched_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: UUID
    trigger: str
    tender_id: Optional[UUID] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: UUID
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent: bool
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
