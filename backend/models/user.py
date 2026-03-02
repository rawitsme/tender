"""User, Organization, and Subscription models."""

import enum
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Enum, Integer, Numeric,
    ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database import Base


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    OPERATOR = "operator"  # Human verification staff


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    gstin = Column(String(20))
    address = Column(Text)
    phone = Column(String(20))
    email = Column(String(300))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="organization")
    subscription = relationship("Subscription", back_populates="organization", uselist=False)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(300), unique=True, nullable=False, index=True)
    hashed_password = Column(String(500), nullable=False)
    full_name = Column(String(300))
    phone = Column(String(20))
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    organization = relationship("Organization", back_populates="users")
    
    # Preferences
    preferred_states = Column(JSONB, default=list)  # ["UP", "MH", ...]
    preferred_categories = Column(JSONB, default=list)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    saved_searches = relationship("SavedSearch", back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), unique=True)
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)
    
    # Limits
    max_saved_searches = Column(Integer, default=3)
    max_document_downloads_per_day = Column(Integer, default=10)
    max_alerts_per_day = Column(Integer, default=5)
    
    # Billing
    amount = Column(Numeric(10, 2), default=0)
    billing_cycle = Column(String(20), default="monthly")  # monthly, quarterly, annual
    
    starts_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="subscription")
