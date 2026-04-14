"""
Cliente Anthropic para interpretar intenciones del usuario en el chat.
Clasifica intención (yes/no/question/problem/other) y genera respuestas
conversacionales cuando el usuario pregunta o reporta un problema.
"""

from __future__ import annotations

import json
import logging

import anthropic
import httpx

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 150
CLIENT_TIMEOUT = httpx.Timeout(8.0, connect=3.0)

STATE_DESCRIPTIONS = {
    "account_check": "Le preguntamos si ya tiene cuenta en MercadoLibre.",
    "oauth_pending": "Le mandamos un link de autorización OAuth para conectar su cuenta de MercadoLibre y estamos esperando que lo complete.",
    "registration_pending": "Le dijimos que cree una cuenta en MercadoLibre y estamos esperando que lo haga.",
}

PENDING_QUESTIONS = {
    "account_check": "¿Ya tenés una cuenta en MercadoLibre? Respondé *sí* o *no*.",
    "oauth_pending": "Usá el link que te mandé para autorizar tu cuenta.",
    "registration_pending": "¿Ya creaste tu cuenta en MercadoLibre?",
}

SYSTEM_PROMPT_TEMPLATE = """\
Sos el asistente de un bot de WhatsApp que ayuda a usuarios a vender en MercadoLibre.
El bot guía al usuario para conectar su cuenta de MercadoLibre con nuestra app.

Estado actual: {state_description}
Lo que el bot le preguntó al usuario: "{pending_question}"

Tu tarea:
1. Clasificar la intención del mensaje del usuario en UNA de estas categorías:
   - "yes": respuesta afirmativa (sí, dale, claro, ya lo hice, tengo, etc.)
   - "no": respuesta negativa (no, todavía no, no tengo, etc.)
   - "question": el usuario hace una pregunta o pide aclaración sobre el proceso
   - "problem": el usuario reporta un error, problema técnico o dificultad
   - "other": no se puede determinar la intención

2. Si la intención es "question" o "problem", escribir una respuesta breve y útil en español (máximo 2 oraciones). Sé amigable y claro.
   Si la pregunta no tiene que ver con MercadoLibre o con este proceso de conexión de cuenta, respondé brevemente que solo podés ayudar con eso.
   Para "yes", "no" y "other", dejá response como cadena vacía.

Respondé SOLO con JSON válido, sin markdown ni backticks:
{{"intent": "...", "response": "..."}}"""


class ClaudeClient:
    def __init__(self, api_key: str) -> None:
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=CLIENT_TIMEOUT,
        )

    async def classify_and_respond(
        self,
        user_message: str,
        state: str,
        pending_question: str | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        """Classify user intent and optionally generate a conversational response.

        Returns dict with:
            intent: "yes" | "no" | "question" | "problem" | "other"
            response: str (populated for question/problem, empty otherwise)
        """
        state_desc = STATE_DESCRIPTIONS.get(state, "Onboarding en curso.")
        pending_q = pending_question or PENDING_QUESTIONS.get(state, "")

        system = SYSTEM_PROMPT_TEMPLATE.format(
            state_description=state_desc,
            pending_question=pending_q,
        )

        # Build messages with conversation history for context
        messages = []
        if history:
            for entry in history[-4:]:
                messages.append({"role": "user", "content": entry["user"]})
                messages.append({"role": "assistant", "content": entry["assistant"]})
        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
            )
            raw = response.content[0].text.strip()
            return self._parse_response(raw)
        except Exception:
            logger.exception("Error calling Claude for classify_and_respond")
            return {"intent": "other", "response": ""}

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """Parse Claude's JSON response with fallback for malformed output."""
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            intent = data.get("intent", "other")
            if intent not in ("yes", "no", "question", "problem", "other"):
                intent = "other"
            return {
                "intent": intent,
                "response": data.get("response", ""),
            }
        except (json.JSONDecodeError, AttributeError):
            logger.warning(f"Failed to parse Claude JSON response: {raw!r}")
            # Fallback: try keyword detection
            lower = raw.lower()
            if '"yes"' in lower:
                return {"intent": "yes", "response": ""}
            if '"no"' in lower:
                return {"intent": "no", "response": ""}
            return {"intent": "other", "response": ""}
