"""
Webhook receiver para eventos de Kapso WhatsApp.

Kapso envia un POST con:
- X-Webhook-Event: tipo de evento (ej: "whatsapp.message.received")
- X-Webhook-Signature: HMAC-SHA256 del body
- X-Idempotency-Key: para deduplicacion
- X-Webhook-Batch: presente si hay multiples eventos agrupados
"""

import asyncio
import hashlib
import hmac
import json
import logging
from collections import OrderedDict

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.shared.deps import get_db
from app.shared.kapso import KapsoClient, KapsoError
from .dispatcher import dispatch_message
from app.onboarding.service import OnboardingService
from app.publication.service import PublicationService
from app.shared.models.user import User
from app.publication.models import AgentSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])

settings = get_settings()

# Dedup: track recently processed idempotency keys to ignore Kapso retries
_processed_keys: OrderedDict[str, bool] = OrderedDict()
_MAX_PROCESSED_KEYS = 200


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


def _extract_message(data: dict) -> dict | None:
    """
    Extrae phone, texto e imagen de un evento whatsapp.message.received de Kapso.
    Retorna: {"phone": str, "text": str, "image_url": str | None} o None.
    """
    msg = data.get("message", {})

    phone = msg.get("from") or data.get("conversation", {}).get("phone_number")
    if not phone:
        return None

    msg_type = msg.get("type", "")

    if msg_type == "text":
        return {"phone": phone, "text": msg.get("text", {}).get("body", ""), "image_url": None}
    elif msg_type == "button":
        return {"phone": phone, "text": msg.get("button", {}).get("text", ""), "image_url": None}
    elif msg_type == "image":
        image = msg.get("image", {})
        caption = image.get("caption", "")
        image_url = image.get("link") or image.get("url") or msg.get("kapso", {}).get("media_url")
        return {"phone": phone, "text": caption, "image_url": image_url}
    else:
        logger.info(f"Mensaje tipo '{msg_type}' de {phone} - no procesado")
        return None


def _send_reply(phone: str, text: str):
    """Send a WhatsApp reply via Kapso."""
    if not text or not settings.KAPSO_API_KEY or not settings.KAPSO_PHONE_NUMBER_ID:
        return
    try:
        kapso = _get_kapso_client()
        kapso.send_text(to=phone, body=text)
        print(f"[WEBHOOK] Sent to {phone}", flush=True)
    except KapsoError as e:
        print(f"[WEBHOOK] Kapso send error: {e}", flush=True)


async def _process_publication_background(user_id, phone: str, text: str, image_url: str | None):
    """Process publication agent in background with its own DB session."""
    # Send immediate feedback for images so the user knows we're working
    if image_url:
        _send_reply(phone, "📸 Recibí tu foto, la estoy analizando...")

    db = SessionLocal()
    try:
        service = PublicationService(db)
        response = await service.process_message(user_id, text, image_url=image_url)
        response_text = response.get("response", "")
        print(f"[WEBHOOK] Agent response: {response_text[:200]!r}", flush=True)
        _send_reply(phone, response_text)
    except Exception as e:
        print(f"[WEBHOOK] Background publication error: {e}", flush=True)
        _send_reply(phone, "Hubo un error procesando tu mensaje. Intentá de nuevo.")
    finally:
        db.close()


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

    # Dedup: ignore Kapso retries for the same event
    if x_idempotency_key:
        if x_idempotency_key in _processed_keys:
            print(f"[WEBHOOK] Dedup: ignoring retry {x_idempotency_key}", flush=True)
            return {"status": "ok"}
        _processed_keys[x_idempotency_key] = True
        if len(_processed_keys) > _MAX_PROCESSED_KEYS:
            _processed_keys.popitem(last=False)

    # Soporte batch
    events = body if (x_webhook_batch and isinstance(body, list)) else [body]

    for event_data in events:
        event_type = x_webhook_event or event_data.get("event")
        print(f"[WEBHOOK] Evento: {event_type}", flush=True)

        if event_type != "whatsapp.message.received":
            continue

        extracted = _extract_message(event_data)
        if not extracted:
            print(f"[WEBHOOK] No se pudo extraer mensaje", flush=True)
            continue

        phone = extracted["phone"]
        text = extracted["text"]
        image_url = extracted["image_url"]
        print(f"[WEBHOOK] Mensaje de {phone}: {text!r} image={image_url}", flush=True)

        # Reset command — reset onboarding + agent sessions
        if text.strip().lower() in {"reiniciar", "reset", "/reiniciar", "/reset"}:
            service = OnboardingService(db)
            response = await service.process_step(phone, text)
            # Also clear agent sessions so publication starts fresh
            user = db.query(User).filter(User.phone == phone).first()
            if user:
                db.query(AgentSession).filter(
                    AgentSession.user_id == user.id,
                    AgentSession.completed == False,
                ).update({"completed": True})
                db.commit()
            _send_reply(phone, response.get("response", ""))
        else:
            # Dispatcher decide: onboarding o publication
            result = await dispatch_message(phone, text, db)

            if result["module"] == "onboarding":
                # Onboarding is fast (single Haiku call) — process inline
                service = OnboardingService(db)
                response = await service.process_step(phone, text)
                _send_reply(phone, response.get("response", ""))
            else:
                # Publication agent is slow — process in background
                # Return 200 OK to Kapso immediately, send reply when agent finishes
                asyncio.create_task(
                    _process_publication_background(
                        result["user"].id, phone, text, image_url
                    )
                )

    # Return 200 OK immediately — Kapso requires this within 10 seconds
    return {"status": "ok"}
