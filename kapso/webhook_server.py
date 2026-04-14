"""
Servidor FastAPI para recibir webhooks de Kapso WhatsApp.

Uso:
    uvicorn kapso.webhook_server:app --host 0.0.0.0 --port 8000

Para testing local con ngrok:
    ngrok http 8000
    # Luego registrar la URL publica en Kapso via create_webhook()
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Kapso Webhook Server")

WEBHOOK_SECRET = os.getenv("KAPSO_WEBHOOK_SECRET", "")


# ------------------------------------------------------------------
# Verificacion de firma
# ------------------------------------------------------------------

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verifica la firma HMAC-SHA256 enviada por Kapso en el header
    X-Webhook-Signature.

    Kapso firma el body JSON crudo con tu secret_key usando HMAC-SHA256.
    Siempre usar comparacion en tiempo constante para evitar timing attacks.
    """
    if not secret:
        logger.warning("KAPSO_WEBHOOK_SECRET no configurado, saltando verificacion de firma")
        return True

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ------------------------------------------------------------------
# Handlers por tipo de evento
# ------------------------------------------------------------------

def handle_message_received(data: dict) -> None:
    """Mensaje entrante de un usuario."""
    msg = data.get("message", {})
    contact = data.get("contact", {})
    phone = contact.get("phone_number") or contact.get("wa_id", "desconocido")

    msg_type = msg.get("type", "unknown")
    if msg_type == "text":
        text = msg.get("text", {}).get("body", "")
        logger.info(f"Mensaje de {phone}: {text!r}")
    else:
        logger.info(f"Mensaje tipo '{msg_type}' de {phone}")


def handle_message_delivered(data: dict) -> None:
    wamid = data.get("message", {}).get("id")
    logger.info(f"Mensaje entregado: {wamid}")


def handle_message_read(data: dict) -> None:
    wamid = data.get("message", {}).get("id")
    logger.info(f"Mensaje leido: {wamid}")


def handle_conversation_created(data: dict) -> None:
    conv_id = data.get("conversation", {}).get("id")
    logger.info(f"Nueva conversacion: {conv_id}")


def handle_conversation_ended(data: dict) -> None:
    conv_id = data.get("conversation", {}).get("id")
    logger.info(f"Conversacion cerrada: {conv_id}")


EVENT_HANDLERS: dict[str, Any] = {
    "whatsapp.message.received": handle_message_received,
    "whatsapp.message.delivered": handle_message_delivered,
    "whatsapp.message.read": handle_message_read,
    "whatsapp.conversation.created": handle_conversation_created,
    "whatsapp.conversation.ended": handle_conversation_ended,
}


# ------------------------------------------------------------------
# Endpoint principal
# ------------------------------------------------------------------

@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_webhook_event: str | None = Header(default=None),
    x_webhook_signature: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
    x_webhook_batch: str | None = Header(default=None),
) -> dict:
    """
    Recibe eventos de Kapso.

    Kapso envia un POST con:
    - X-Webhook-Event: tipo de evento (ej: "whatsapp.message.received")
    - X-Webhook-Signature: HMAC-SHA256 del body con tu secret
    - X-Idempotency-Key: para deduplicacion
    - X-Webhook-Batch / X-Batch-Size: presente si hay multiples eventos agrupados
    """
    raw_body = await request.body()

    # Verificar firma
    if x_webhook_signature:
        if not verify_signature(raw_body, x_webhook_signature, WEBHOOK_SECRET):
            logger.warning(f"Firma invalida para idempotency_key={x_idempotency_key}")
            raise HTTPException(status_code=401, detail="Firma invalida")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Body no es JSON valido")

    # Soporte para batch de eventos (X-Webhook-Batch presente)
    if x_webhook_batch:
        events = body if isinstance(body, list) else [body]
    else:
        events = [body]

    for event_data in events:
        event_type = x_webhook_event or event_data.get("event")
        logger.info(f"Evento recibido: {event_type} | idempotency_key={x_idempotency_key}")

        handler = EVENT_HANDLERS.get(event_type)
        if handler:
            try:
                handler(event_data)
            except Exception as exc:
                logger.error(f"Error procesando evento {event_type}: {exc}", exc_info=True)
        else:
            logger.info(f"Evento sin handler: {event_type}")
            logger.debug(f"Payload: {json.dumps(event_data, indent=2)}")

    # Kapso requiere 200 OK en menos de 10 segundos
    return {"status": "ok"}


@app.get("/health")
async def health() -> dict:
    """Endpoint de health check."""
    return {"status": "ok"}
