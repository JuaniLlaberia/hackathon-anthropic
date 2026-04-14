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
    """
    Cliente para interactuar con la API de Kapso.

    Args:
        api_key: API key del proyecto (Sidebar > API keys en el dashboard).
        phone_number_id: ID del phone number a usar por defecto.
    """

    def __init__(self, api_key: str, phone_number_id: str | None = None) -> None:
        self.phone_number_id = phone_number_id
        self._headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _whatsapp_url(self, phone_number_id: str, path: str) -> str:
        return f"{WHATSAPP_BASE_URL}/{phone_number_id}/{path.lstrip('/')}"

    def _platform_url(self, path: str) -> str:
        return f"{PLATFORM_BASE_URL}/{path.lstrip('/')}"

    def _resolve_phone_id(self, phone_number_id: str | None) -> str:
        pid = phone_number_id or self.phone_number_id
        if not pid:
            raise ValueError(
                "phone_number_id requerido: pasalo como argumento o configuralo en KapsoClient"
            )
        return pid

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_error:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise KapsoError(response.status_code, str(detail))

    # ------------------------------------------------------------------
    # Phone Numbers
    # ------------------------------------------------------------------

    def list_phone_numbers(self, **params: Any) -> dict:
        """Lista todos los phone numbers del proyecto."""
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url("whatsapp/phone_numbers"),
                params=params,
            )
        self._raise_for_status(response)
        return response.json()

    def get_phone_number(self, phone_number_id: str | None = None) -> dict:
        """Obtiene los detalles de un phone number."""
        pid = self._resolve_phone_id(phone_number_id)
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url(f"whatsapp/phone_numbers/{pid}")
            )
        self._raise_for_status(response)
        return response.json()

    def check_phone_health(self, phone_number_id: str | None = None) -> dict:
        """Health check en vivo del phone number via Meta APIs y servicios de Kapso."""
        pid = self._resolve_phone_id(phone_number_id)
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url(f"whatsapp/phone_numbers/{pid}/health")
            )
        self._raise_for_status(response)
        return response.json()

    # ------------------------------------------------------------------
    # Mensajes
    # ------------------------------------------------------------------

    def send_text(
        self,
        to: str,
        body: str,
        phone_number_id: str | None = None,
        preview_url: bool = False,
    ) -> dict:
        """
        Envia un mensaje de texto por WhatsApp.

        Args:
            to: Numero del destinatario (ej: "5491112345678").
            body: Texto del mensaje.
            phone_number_id: Override del phone number ID configurado.
            preview_url: Si mostrar preview de URLs en el mensaje.

        Nota: Solo funciona dentro de la ventana de 24 horas de conversacion.
              Fuera de esa ventana, usar send_template().
        """
        pid = self._resolve_phone_id(phone_number_id)
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {
                "body": body,
                "preview_url": preview_url,
            },
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
        """
        Envia cualquier tipo de mensaje. Util para tipos avanzados
        (imagen, video, template, interactivo, etc).

        Args:
            to: Numero del destinatario.
            message: Payload del mensaje sin el campo "to" ni "messaging_product".
            phone_number_id: Override del phone number ID configurado.
        """
        pid = self._resolve_phone_id(phone_number_id)
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            **message,
        }
        with httpx.Client(headers=self._headers) as client:
            response = client.post(
                self._whatsapp_url(pid, "messages"),
                json=payload,
            )
        self._raise_for_status(response)
        return response.json()

    def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "es",
        components: list | None = None,
        phone_number_id: str | None = None,
    ) -> dict:
        """
        Envia un mensaje usando un template aprobado.
        Sirve para iniciar conversaciones fuera de la ventana de 24 horas.

        Args:
            to: Numero del destinatario.
            template_name: Nombre del template en Kapso.
            language_code: Codigo de idioma (ej: "es", "en").
            components: Lista de componentes con parametros del template.
        """
        pid = self._resolve_phone_id(phone_number_id)
        template: dict = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template,
        }
        with httpx.Client(headers=self._headers) as client:
            response = client.post(
                self._whatsapp_url(pid, "messages"),
                json=payload,
            )
        self._raise_for_status(response)
        return response.json()

    def mark_as_read(
        self,
        message_id: str,
        phone_number_id: str | None = None,
    ) -> dict:
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

    def list_messages(
        self,
        phone_number_id: str | None = None,
        direction: str | None = None,
        limit: int = 20,
        **params: Any,
    ) -> dict:
        """
        Lista mensajes de un phone number.

        Args:
            direction: "inbound" o "outbound". None para ambos.
            limit: Cantidad maxima de resultados.
        """
        pid = self._resolve_phone_id(phone_number_id)
        query = {"limit": limit, **params}
        if direction:
            query["direction"] = direction
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url(f"whatsapp/phone_numbers/{pid}/messages"),
                params=query,
            )
        self._raise_for_status(response)
        return response.json()

    def get_message(self, wamid: str) -> dict:
        """Obtiene un mensaje por su WhatsApp Message ID (WAMID)."""
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url(f"whatsapp/messages/{wamid}")
            )
        self._raise_for_status(response)
        return response.json()

    # ------------------------------------------------------------------
    # Conversaciones
    # ------------------------------------------------------------------

    def list_conversations(
        self,
        phone_number_id: str | None = None,
        limit: int = 20,
        **params: Any,
    ) -> dict:
        """Lista conversaciones del phone number."""
        pid = self._resolve_phone_id(phone_number_id)
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url(f"whatsapp/phone_numbers/{pid}/conversations"),
                params={"limit": limit, **params},
            )
        self._raise_for_status(response)
        return response.json()

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def create_webhook(
        self,
        url: str,
        events: list[str],
        secret_key: str,
        phone_number_id: str | None = None,
        kind: str = "kapso",
        active: bool = True,
        buffer_enabled: bool = False,
        buffer_window_seconds: int = 3,
    ) -> dict:
        """
        Crea un webhook para recibir eventos de WhatsApp.

        Args:
            url: URL publica donde se enviaran los eventos (debe responder 200 en < 10s).
            events: Lista de eventos a suscribir.
                    Ej: ["whatsapp.message.received", "whatsapp.message.delivered"]
            secret_key: Secret para verificar la firma HMAC-SHA256.
            phone_number_id: Si se pasa, el webhook es scoped al numero.
                             Si no, es project-scoped (todos los numeros).
            kind: "kapso" (payloads estructurados) o "meta" (raw Meta payloads).
            active: Si el webhook esta activo desde el inicio.
            buffer_enabled: Agrupa multiples mensajes en un solo request.
            buffer_window_seconds: Ventana de tiempo para el buffer (segundos).
        """
        payload: dict = {
            "url": url,
            "kind": kind,
            "events": events,
            "secret_key": secret_key,
            "active": active,
        }
        if buffer_enabled:
            payload["buffer_enabled"] = True
            payload["buffer_window_seconds"] = buffer_window_seconds
        if phone_number_id:
            payload["phone_number_id"] = phone_number_id

        with httpx.Client(headers=self._headers) as client:
            response = client.post(
                self._platform_url("whatsapp/webhooks"),
                json=payload,
            )
        self._raise_for_status(response)
        return response.json()

    def list_webhooks(self, phone_number_id: str | None = None) -> dict:
        """Lista los webhooks del proyecto o de un phone number especifico."""
        params = {}
        if phone_number_id:
            params["phone_number_id"] = phone_number_id
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url("whatsapp/webhooks"),
                params=params,
            )
        self._raise_for_status(response)
        return response.json()

    def delete_webhook(self, webhook_id: str) -> None:
        """Elimina un webhook."""
        with httpx.Client(headers=self._headers) as client:
            response = client.delete(
                self._platform_url(f"whatsapp/webhooks/{webhook_id}")
            )
        self._raise_for_status(response)

    # ------------------------------------------------------------------
    # Contactos
    # ------------------------------------------------------------------

    def get_contact(self, contact_id: str) -> dict:
        """Obtiene un contacto por UUID o numero de telefono."""
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url(f"whatsapp/contacts/{contact_id}")
            )
        self._raise_for_status(response)
        return response.json()

    def list_contacts(self, limit: int = 20, **params: Any) -> dict:
        """Lista contactos del proyecto."""
        with httpx.Client(headers=self._headers) as client:
            response = client.get(
                self._platform_url("whatsapp/contacts"),
                params={"limit": limit, **params},
            )
        self._raise_for_status(response)
        return response.json()
