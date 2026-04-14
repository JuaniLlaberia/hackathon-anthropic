"""
Cliente HTTP para la API de Kapso WhatsApp.
Docs: https://docs.kapso.ai/docs/introduction
"""

from __future__ import annotations

import httpx
from typing import Any


WHATSAPP_BASE_URL = "https://api.kapso.ai/meta/whatsapp/v24.0"
PLATFORM_BASE_URL = "https://api.kapso.ai/platform/v1"


class KapsoError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"[{status_code}] {message}")


class KapsoClient:
    def __init__(self, api_key: str, phone_number_id: str | None = None) -> None:
        self.phone_number_id = phone_number_id
        self._headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

    def _whatsapp_url(self, phone_number_id: str, path: str) -> str:
        return f"{WHATSAPP_BASE_URL}/{phone_number_id}/{path.lstrip('/')}"

    def _platform_url(self, path: str) -> str:
        return f"{PLATFORM_BASE_URL}/{path.lstrip('/')}"

    def _resolve_phone_id(self, phone_number_id: str | None) -> str:
        pid = phone_number_id or self.phone_number_id
        if not pid:
            raise ValueError("phone_number_id requerido")
        return pid

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_error:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise KapsoError(response.status_code, str(detail))

    def send_text(
        self,
        to: str,
        body: str,
        phone_number_id: str | None = None,
    ) -> dict:
        """Envia un mensaje de texto por WhatsApp."""
        pid = self._resolve_phone_id(phone_number_id)
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        with httpx.Client(headers=self._headers) as client:
            response = client.post(
                self._whatsapp_url(pid, "messages"),
                json=payload,
            )
        self._raise_for_status(response)
        return response.json()

    def send_message(
        self,
        to: str,
        message: dict,
        phone_number_id: str | None = None,
    ) -> dict:
        """Envia cualquier tipo de mensaje (imagen, video, template, interactivo, etc)."""
        pid = self._resolve_phone_id(phone_number_id)
        payload = {"messaging_product": "whatsapp", "to": to, **message}
        with httpx.Client(headers=self._headers) as client:
            response = client.post(
                self._whatsapp_url(pid, "messages"),
                json=payload,
            )
        self._raise_for_status(response)
        return response.json()

    def mark_as_read(self, message_id: str, phone_number_id: str | None = None) -> dict:
        """Marca un mensaje como leido."""
        pid = self._resolve_phone_id(phone_number_id)
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        with httpx.Client(headers=self._headers) as client:
            response = client.post(
                self._whatsapp_url(pid, "messages"),
                json=payload,
            )
        self._raise_for_status(response)
        return response.json()

    def list_phone_numbers(self, **params: Any) -> dict:
        """Lista todos los phone numbers del proyecto."""
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url("whatsapp/phone_numbers"),
                params=params,
            )
        self._raise_for_status(response)
        return response.json()

    def create_webhook(
        self,
        url: str,
        events: list[str],
        secret_key: str,
        phone_number_id: str | None = None,
    ) -> dict:
        """Crea un webhook para recibir eventos de WhatsApp."""
        inner: dict = {
            "url": url,
            "kind": "kapso",
            "events": events,
            "secret_key": secret_key,
            "active": True,
        }
        if phone_number_id:
            inner["phone_number_id"] = phone_number_id
        with httpx.Client(headers=self._headers) as client:
            response = client.post(
                self._platform_url("whatsapp/webhooks"),
                json={"whatsapp_webhook": inner},
            )
        self._raise_for_status(response)
        return response.json()

    def list_webhooks(self) -> dict:
        """Lista los webhooks del proyecto."""
        with httpx.Client(headers=self._headers) as client:
            response = client.get(self._platform_url("whatsapp/webhooks"))
        self._raise_for_status(response)
        return response.json()
