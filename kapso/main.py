"""
Script principal para probar la integracion con Kapso en modo sandbox.

Uso:
    # 1. Copiar .env.example a .env y completar las variables
    cp .env.example .env

    # 2. Instalar dependencias
    uv sync

    # 3. Correr este script
    uv run python -m kapso.main

    # 4. Para el servidor de webhooks (en otra terminal)
    uv run uvicorn kapso.webhook_server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

from kapso.client import KapsoClient, KapsoError

load_dotenv()


def pretty(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    api_key = os.getenv("KAPSO_API_KEY")
    phone_number_id = os.getenv("KAPSO_PHONE_NUMBER_ID")

    if not api_key:
        print("ERROR: Falta KAPSO_API_KEY en .env")
        sys.exit(1)

    client = KapsoClient(api_key=api_key, phone_number_id=phone_number_id)

    # ------------------------------------------------------------------
    # 1. Listar phone numbers del proyecto
    # ------------------------------------------------------------------
    print("\n=== Phone Numbers del proyecto ===")
    try:
        numbers = client.list_phone_numbers()
        pretty(numbers)
    except KapsoError as e:
        print(f"Error: {e}")

    if not phone_number_id:
        print("\nConfigura KAPSO_PHONE_NUMBER_ID en .env para enviar mensajes.")
        return

    # ------------------------------------------------------------------
    # 2. Verificar salud del phone number
    # ------------------------------------------------------------------
    print("\n=== Health check del phone number ===")
    try:
        health = client.check_phone_health()
        pretty(health)
    except KapsoError as e:
        print(f"Error: {e}")

    # ------------------------------------------------------------------
    # 3. Enviar mensaje de texto (sandbox)
    # ------------------------------------------------------------------
    # En sandbox: el destinatario debe haberse registrado primero enviando
    # el codigo de activacion al numero sandbox de Kapso.
    destination = input("\nNumero de destino para enviar mensaje (ej: 5491112345678): ").strip()
    if not destination:
        print("Sin destino, saltando envio de mensaje.")
        return

    print(f"\n=== Enviando mensaje de texto a {destination} ===")
    try:
        result = client.send_text(
            to=destination,
            body="Hola! Este es un mensaje de prueba desde la integracion Kapso en sandbox.",
        )
        pretty(result)
    except KapsoError as e:
        print(f"Error al enviar: {e}")

    # ------------------------------------------------------------------
    # 4. Listar conversaciones
    # ------------------------------------------------------------------
    print("\n=== Ultimas conversaciones ===")
    try:
        conversations = client.list_conversations(limit=5)
        pretty(conversations)
    except KapsoError as e:
        print(f"Error: {e}")

    # ------------------------------------------------------------------
    # 5. Setup de webhook (opcional)
    # ------------------------------------------------------------------
    webhook_url = os.getenv("KAPSO_WEBHOOK_URL", "")
    webhook_secret = os.getenv("KAPSO_WEBHOOK_SECRET", "")

    if webhook_url and webhook_secret:
        print(f"\n=== Creando webhook en {webhook_url} ===")
        try:
            webhook = client.create_webhook(
                url=f"{webhook_url}/webhook",
                events=[
                    "whatsapp.message.received",
                    "whatsapp.message.delivered",
                    "whatsapp.message.read",
                    "whatsapp.conversation.created",
                ],
                secret_key=webhook_secret,
                phone_number_id=phone_number_id,
            )
            pretty(webhook)
        except KapsoError as e:
            print(f"Error al crear webhook: {e}")
    else:
        print("\nTip: Agrega KAPSO_WEBHOOK_URL y KAPSO_WEBHOOK_SECRET en .env para registrar el webhook automaticamente.")
        print("     Para testing local usa ngrok: ngrok http 8000")


if __name__ == "__main__":
    main()
