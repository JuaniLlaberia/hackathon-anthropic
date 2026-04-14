from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class UserBase(BaseModel):
    phone: str
    name: Optional[str] = None
    email: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: UUID
    is_verified: bool
    is_onboarded: bool
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
