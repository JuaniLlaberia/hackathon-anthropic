"""
Webhook receiver para eventos de Kapso WhatsApp.

Kapso envia un POST con:
- X-Webhook-Event: tipo de evento (ej: "whatsapp.message.received")
- X-Webhook-Signature: HMAC-SHA256 del body
- X-Idempotency-Key: para deduplicacion
- X-Webhook-Batch: presente si hay multiples eventos agrupados
"""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.shared.deps import get_db
from app.shared.kapso import KapsoClient, KapsoError
from .dispatcher import dispatch_message
from app.onboarding.service import OnboardingService
from app.publication.service import PublicationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])

settings = get_settings()


def _get_kapso_client() -> KapsoClient:
    return KapsoClient(
        api_key=settings.KAPSO_API_KEY,
        phone_number_id=settings.KAPSO_PHONE_NUMBER_ID,
    )


def _verify_signature(payload: bytes, signature: str) -> bool:
    """Verifica la firma HMAC-SHA256 enviada por Kapso."""
    if not settings.KAPSO_WEBHOOK_SECRET:
        return True
    expected = hmac.new(
        settings.KAPSO_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_phone_and_text(data: dict) -> tuple[str, str] | None:
    """Extrae phone y texto de un evento whatsapp.message.received de Kapso."""
    msg = data.get("message", {})

    # Payload real de Kapso: phone viene en message.from, no en contact
    phone = msg.get("from") or data.get("conversation", {}).get("phone_number")
    if not phone:
        return None

    msg_type = msg.get("type", "")
    if msg_type == "text":
        text = msg.get("text", {}).get("body", "")
    elif msg_type == "button":
        text = msg.get("button", {}).get("text", "")
    else:
        logger.info(f"Mensaje tipo '{msg_type}' de {phone} - no procesado")
        return None

    return phone, text


@router.post("")
@router.post("/")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_event: str | None = Header(default=None),
    x_webhook_signature: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
    x_webhook_batch: str | None = Header(default=None),
):
    raw_body = await request.body()

    # Verificar firma HMAC
    if x_webhook_signature:
        if not _verify_signature(raw_body, x_webhook_signature):
            logger.warning(f"Firma invalida | idempotency_key={x_idempotency_key}")
            raise HTTPException(status_code=401, detail="Firma invalida")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Body no es JSON valido")

    # Soporte batch
    events = body if (x_webhook_batch and isinstance(body, list)) else [body]

    for event_data in events:
        event_type = x_webhook_event or event_data.get("event")
        logger.info(f"Evento: {event_type} | idempotency_key={x_idempotency_key}")

        if event_type != "whatsapp.message.received":
            continue

        extracted = _extract_phone_and_text(event_data)
        if not extracted:
            continue

        phone, text = extracted
        logger.info(f"Mensaje de {phone}: {text!r}")

        # Reset command — always handled by onboarding, regardless of user state
        if text.strip().lower() in {"reiniciar", "reset", "/reiniciar", "/reset"}:
            service = OnboardingService(db)
            response = await service.process_step(phone, text)
        else:
            # Dispatcher decide: onboarding o publication
            result = await dispatch_message(phone, text, db)

            if result["module"] == "onboarding":
                service = OnboardingService(db)
                response = await service.process_step(phone, text)
            else:
                service = PublicationService(db)
                response = await service.process_message(result["user"].id, text)

        # Enviar respuesta al usuario via WhatsApp
        response_text = response.get("response", "")
        if response_text and settings.KAPSO_API_KEY and settings.KAPSO_PHONE_NUMBER_ID:
            try:
                kapso = _get_kapso_client()
                kapso.send_text(to=phone, body=response_text)
                logger.info(f"Respuesta enviada a {phone}")
            except KapsoError as e:
                logger.error(f"Error enviando respuesta a {phone}: {e}")

    # Kapso requiere 200 OK en menos de 10 segundos
    return {"status": "ok"}
