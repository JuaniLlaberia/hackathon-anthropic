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

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.shared.deps import get_db
from app.shared.kapso import KapsoClient, KapsoError
from .dispatcher import dispatch_message
from app.onboarding.service import OnboardingService
from app.publication.service import PublicationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])

settings = get_settings()

# Deduplication: track recently processed idempotency keys
_processed_keys: set[str] = set()
_MAX_KEYS = 1000


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


async def _process_message_and_reply(phone: str, text: str, image_url: str | None, user_id=None, module: str = "onboarding"):
    """Process message in background and send reply via Kapso."""
    db = SessionLocal()
    try:
        if module == "onboarding" or module == "needs_ml":
            service = OnboardingService(db)
            response = await service.process_step(phone, text)
        else:
            service = PublicationService(db)
            response = await service.process_message(user_id, text, image_url=image_url)

        response_text = response.get("response", "")
        print(f"[WEBHOOK] Response to send: {response_text[:200]!r}", flush=True)
        if response_text and settings.KAPSO_API_KEY and settings.KAPSO_PHONE_NUMBER_ID:
            try:
                kapso = _get_kapso_client()
                kapso.send_text(to=phone, body=response_text)
                print(f"[WEBHOOK] Sent to {phone}", flush=True)
            except KapsoError as e:
                print(f"[WEBHOOK] Kapso send error: {e}", flush=True)
    except Exception as e:
        print(f"[WEBHOOK] Background error: {e}", flush=True)
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

    # Deduplication via idempotency key
    if x_idempotency_key:
        if x_idempotency_key in _processed_keys:
            print(f"[WEBHOOK] Duplicado ignorado: {x_idempotency_key}", flush=True)
            return {"status": "ok"}
        _processed_keys.add(x_idempotency_key)
        if len(_processed_keys) > _MAX_KEYS:
            _processed_keys.clear()

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

        # Determine module
        if text.strip().lower() in {"reiniciar", "reset", "/reiniciar", "/reset"}:
            module = "onboarding"
            user_id = None
        else:
            result = await dispatch_message(phone, text, db)
            module = result["module"]
            user_id = result["user"].id if result.get("user") else None

        # Process in background so we return 200 to Kapso immediately
        asyncio.create_task(
            _process_message_and_reply(phone, text, image_url, user_id, module)
        )

    # Return 200 immediately — Kapso requires response in <10 seconds
    return {"status": "ok"}
