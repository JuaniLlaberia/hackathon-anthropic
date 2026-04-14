from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PublicationCreate(BaseModel):
    user_id: UUID
    category_id: Optional[UUID] = None
    title: str
    body: str


class MediaResponse(BaseModel):
    id: UUID
    url: str
    media_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicationResponse(BaseModel):
    id: UUID
    user_id: UUID
    category_id: Optional[UUID] = None
    title: str
    body: str
    status: str
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    media: list[MediaResponse] = []

    model_config = {"from_attributes": True}


class ModerationAction(BaseModel):
    action: str  # approve | reject
    reason: Optional[str] = None


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class PublicationBotMessage(BaseModel):
    phone: str
    message: str
