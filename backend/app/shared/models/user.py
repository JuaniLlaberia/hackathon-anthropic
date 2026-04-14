import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    email = Column(String(150), nullable=True)
    is_verified = Column(Boolean, default=False)
    is_onboarded = Column(Boolean, default=False)
    role = Column(String(20), default="user")  # user | admin | moderator

    # MercadoLibre OAuth
    ml_user_id = Column(String(50), nullable=True)
    ml_access_token = Column(Text, nullable=True)
    ml_refresh_token = Column(Text, nullable=True)
    ml_token_expires_at = Column(DateTime, nullable=True)
    ml_connected = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
