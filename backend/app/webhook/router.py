from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.shared.deps import get_db
from app.config import get_settings
from .dispatcher import dispatch_message
from app.onboarding.service import OnboardingService
from app.publication.service import PublicationService

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])

settings = get_settings()


class WebhookPayload(BaseModel):
    phone: str
    message: str
    webhook_secret: str | None = None


@router.post("")
async def receive_webhook(payload: WebhookPayload, db: Session = Depends(get_db)):
    # Validar secret si esta configurado
    if settings.KAPSO_WEBHOOK_SECRET:
        if payload.webhook_secret != settings.KAPSO_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Webhook secret invalido")

    result = await dispatch_message(payload.phone, payload.message, db)

    if result["module"] == "onboarding":
        service = OnboardingService(db)
        response = await service.process_step(payload.phone, payload.message)
    else:
        service = PublicationService(db)
        response = await service.process_message(result["user"].id, payload.message)

    return response
