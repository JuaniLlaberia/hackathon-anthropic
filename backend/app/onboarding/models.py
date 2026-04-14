import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.shared.models.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    city = Column(String(100))
    bio = Column(String(500))
    avatar_url = Column(String(500))
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    current_step = Column(Integer, default=0)  # kept for migration compat
    state = Column(String(30), default="welcome")  # welcome | account_check | oauth_pending | registration_pending | completed
    data = Column(JSON, default=dict)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
