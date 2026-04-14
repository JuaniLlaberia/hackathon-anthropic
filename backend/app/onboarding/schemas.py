from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class OnboardingStepRequest(BaseModel):
    phone: str
    message: str


class OnboardingStatusResponse(BaseModel):
    phone: str
    current_step: int
    total_steps: int
    completed: bool
    data: dict

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    city: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: dict = {}

    model_config = {"from_attributes": True}
