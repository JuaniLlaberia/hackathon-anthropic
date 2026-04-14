"""
Agente de publicacion usando Messages API con tool use.
Conversa con el usuario, recolecta datos, y publica en ML.
"""

from __future__ import annotations

import json
import logging

import anthropic
import httpx

from app.config import get_settings
from .ml_tools import publish_listing, get_price_estimate

logger = logging.getLogger(__name__)

settings = get_settings()

SYSTEM_PROMPT = """\
Sos un asistente de WhatsApp que ayuda a publicar productos en MercadoLibre Argentina.
Hablás en español argentino informal (vos, che, dale). Mensajes cortos — es WhatsApp.

## Flujo
1. El usuario manda una foto → identificá marca, modelo y condición
2. Llamá a get_price_estimate para obtener rango de precios
3. En UN mensaje preguntá: precio (sugiriendo el rango) y confirmá si es nuevo o usado
4. Con esos datos, armá el resumen y pedí confirmación:

*Resumen*
Título: [vos lo generás, máx 60 chars]
Marca: ...
Modelo: ...
Precio: $...
Condición: Nuevo/Usado

¿Confirmás? (sí/no)

5. Si confirma → llamá publish_listing
6. Si publish_listing da error → mostrá los datos para que publique manual en mercadolibre.com.ar/publicar

## Reglas
- Vos generás título y descripción, NO se los pidas al usuario
- Solo preguntá precio y condición (si no es obvia)
- Si no podés identificar marca/modelo de la foto, preguntá
- Máximo 2-3 oraciones por mensaje
"""

TOOLS = [
    {
        "name": "get_price_estimate",
        "description": "Busca productos similares en MercadoLibre y devuelve rango de precios. Usalo antes de preguntar el precio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Nombre del producto (ej: 'mouse logitech M720')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "publish_listing",
        "description": "Publica en MercadoLibre. Solo usar después de que el usuario confirme.",
        "input_schema": {
            "type": "object",
            "properties": {
                "brand": {"type": "string"},
                "model": {"type": "string"},
                "title": {"type": "string", "description": "Máx 60 chars"},
                "price": {"type": "number"},
                "condition": {"type": "string", "enum": ["new", "used"]},
                "description": {"type": "string"},
            },
            "required": ["brand", "model", "title", "price", "condition", "description"],
        },
    },
]

MAX_TOOL_ROUNDS = 5
MAX_HISTORY_MESSAGES = 30


class AgentService:

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def process_message(
        self,
        message: str,
        image_url: str | None = None,
        access_token: str | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        self._access_token = access_token
        self._image_url = image_url

        messages = list(history) if history else []

        content = []
        if image_url:
            content.append({"type": "image", "source": {"type": "url", "url": image_url}})
        if message:
            content.append({"type": "text", "text": message})
        if not content:
            content.append({"type": "text", "text": "(mensaje vacío)"})

        messages.append({"role": "user", "content": content})

        if len(messages) > MAX_HISTORY_MESSAGES:
            messages = messages[-MAX_HISTORY_MESSAGES:]

        try:
            response_text = await self._tool_loop(messages)
        except Exception as e:
            print(f"[AGENT] Error: {e}", flush=True)
            return {
                "response": "Hubo un error. Intentá de nuevo.",
                "messages": messages,
                "completed": False,
            }

        return {
            "response": response_text.strip(),
            "messages": messages,
            "completed": False,
        }

    async def _tool_loop(self, messages: list[dict]) -> str:
        for round_num in range(MAX_TOOL_ROUNDS):
            print(f"[AGENT] Round {round_num + 1}", flush=True)

            response = await self.client.messages.create(
                model="claude-sonnet-4-6",
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
                max_tokens=1024,
            )

            print(f"[AGENT] Stop reason: {response.stop_reason}", flush=True)

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                text = "".join(b.text for b in response.content if hasattr(b, "text"))
                messages.append({"role": "assistant", "content": self._serialize(response.content)})
                return text

            messages.append({"role": "assistant", "content": self._serialize(response.content)})

            tool_results = []
            for tu in tool_uses:
                print(f"[AGENT] Tool: {tu.name}({tu.input})", flush=True)
                result = await self._run_tool(tu.name, tu.input)
                print(f"[AGENT] Result: {str(result)[:300]}", flush=True)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            messages.append({"role": "user", "content": tool_results})

        return "Hubo un problema. Intentá de nuevo."

    async def _run_tool(self, name: str, input: dict) -> dict:
        if name == "get_price_estimate":
            try:
                return await get_price_estimate(**input)
            except Exception as e:
                return {"error": str(e)}

        if name == "publish_listing":
            if not self._access_token:
                return {"error": "No hay token de MercadoLibre. Reconectá tu cuenta con /reset."}
            try:
                return await publish_listing(
                    access_token=self._access_token,
                    image_url=self._image_url,
                    **input,
                )
            except Exception as e:
                print(f"[AGENT] Publish error: {e}", flush=True)
                return {"error": str(e)}

        return {"error": f"Tool '{name}' no existe"}

    @staticmethod
    def _serialize(content_blocks) -> list[dict]:
        result = []
        for block in content_blocks:
            if block.type == "text":
                result.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                result.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        return result
