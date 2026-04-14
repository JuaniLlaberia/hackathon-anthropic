"""
Cliente Anthropic para interpretar intenciones del usuario en el chat.
Usa Haiku para latencia baja y bajo costo.
"""

from __future__ import annotations

import logging

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"


class ClaudeClient:
    def __init__(self, api_key: str) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)

    def interpret_yes_no(self, user_message: str) -> bool | None:
        """Interpret whether a user message means yes or no.

        Returns True for yes, False for no, None if unclear.
        """
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=10,
                system=(
                    "Sos un clasificador. El usuario responde a la pregunta "
                    "'¿Tenés cuenta en MercadoLibre?'. "
                    "Respondé SOLO con 'yes', 'no', o 'unclear'. "
                    "Nada más."
                ),
                messages=[{"role": "user", "content": user_message}],
            )
            answer = response.content[0].text.strip().lower()
            if answer == "yes":
                return True
            if answer == "no":
                return False
            return None
        except Exception:
            logger.exception("Error calling Claude for yes/no interpretation")
            return None
