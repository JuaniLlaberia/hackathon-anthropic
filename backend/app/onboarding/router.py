from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.shared.deps import get_db
from app.shared.schemas.user import UserResponse
from app.shared.models.user import User
from .service import OnboardingService
from .schemas import OnboardingStepRequest, OnboardingStatusResponse

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.post("/step")
async def process_step(request: OnboardingStepRequest, db: Session = Depends(get_db)):
    service = OnboardingService(db)
    result = await service.process_step(request.phone, request.message)
    return result


@router.get("/status/{phone}", response_model=OnboardingStatusResponse)
async def get_status(phone: str, db: Session = Depends(get_db)):
    service = OnboardingService(db)
    return service.get_status(phone)


@router.get("/users", response_model=list[UserResponse])
async def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    return user
