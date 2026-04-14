"""
Servicio que conecta la conversacion de WhatsApp con un agente de Claude
usando la Managed Agents API de Anthropic.

Cada usuario tiene una session persistente. El agente guia al usuario
para crear una publicacion en Mercado Libre.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

import anthropic
from sqlalchemy.orm import Session as DBSession

from app.config import get_settings
from .ml_tools import TOOL_HANDLERS

logger = logging.getLogger(__name__)

settings = get_settings()

AGENT_SYSTEM_PROMPT = """You are an expert Mercado Libre Argentina assistant that helps people create product listings via WhatsApp.

## Your role
Guide the user step by step to build an optimized Mercado Libre listing. Be friendly, concise (it's WhatsApp, not email), and knowledgeable about ML best practices. Always respond in informal Argentinian Spanish (vos, che, dale).

## Workflow
1. If the user sends a photo, analyze it to identify the product, brand, model, and apparent condition
2. Use the search_ml_category tool to find the correct ML category
3. Use search_similar_products to research reference prices
4. Use get_category_attributes to know which attributes are mandatory
5. Ask the user for anything you can't infer: price, condition (new/used), stock, shipping preference
6. Generate an optimized ML title (max 60 chars, format: Product + Brand + Model + Specs)
7. Generate an attractive and complete description
8. Show a final summary and ask for confirmation

## Rules
- ALWAYS respond in informal Argentinian Spanish (vos, che, dale)
- Keep messages short and clear — it's WhatsApp
- If the user sends a photo, start by analyzing it
- If there's no photo, ask what they want to sell
- Suggest prices based on similar product search results
- The title must follow ML format: Product Brand Model Specs
- Never invent product information — ask if you don't know
- When you have all the info, show the summary like this:

*Resumen de tu publicacion*
Titulo: ...
Categoria: ...
Precio: $...
Condicion: ...
Descripcion: ...

Confirmas? (si/no)
"""

CUSTOM_TOOLS = [
    {
        "type": "custom",
        "name": "search_ml_category",
        "description": "Search for the most appropriate Mercado Libre category for a product. Use this to classify the user's product.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product name or description (e.g. 'samsung galaxy s24 128gb')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "type": "custom",
        "name": "get_category_attributes",
        "description": "Get required and optional attributes for a Mercado Libre category. Use after finding the category to know what data to ask the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category_id": {
                    "type": "string",
                    "description": "ML category ID (e.g. 'MLA1055')",
                },
            },
            "required": ["category_id"],
        },
    },
    {
        "type": "custom",
        "name": "search_similar_products",
        "description": "Search similar products on Mercado Libre to get reference prices. Use this to suggest a competitive price to the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product search query (e.g. 'samsung galaxy s24 nuevo')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]


class AgentService:
    """
    Manages Anthropic Managed Agent sessions for the publication flow.
    """

    def __init__(self, db: DBSession):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._agent_id: str | None = None
        self._environment_id: str | None = None

    def _get_or_create_agent(self) -> str:
        if self._agent_id:
            return self._agent_id

        agent = self.client.beta.agents.create(
            name="ML Listing Assistant",
            model="claude-sonnet-4-6",
            system=AGENT_SYSTEM_PROMPT,
            tools=[
                {
                    "type": "agent_toolset_20260401",
                    "default_config": {"enabled": False},
                    "configs": [
                        {"name": "web_search", "enabled": True},
                        {"name": "web_fetch", "enabled": True},
                    ],
                },
                *CUSTOM_TOOLS,
            ],
        )
        self._agent_id = agent.id
        return agent.id

    def _get_or_create_environment(self) -> str:
        if self._environment_id:
            return self._environment_id

        env = self.client.beta.environments.create(
            name="publication-env",
            config={
                "type": "cloud",
                "networking": {"type": "unrestricted"},
            },
        )
        self._environment_id = env.id
        return env.id

    def _create_session(self) -> str:
        agent_id = self._get_or_create_agent()
        env_id = self._get_or_create_environment()

        session = self.client.beta.sessions.create(
            agent=agent_id,
            environment_id=env_id,
            title="ML Publication",
        )
        return session.id

    async def process_message(
        self,
        user_id: UUID,
        session_id: str | None,
        message: str,
        image_url: str | None = None,
    ) -> dict:
        """
        Send a user message to the agent and return the response.

        Returns:
            {"response": str, "session_id": str, "completed": bool}
        """
        if not session_id:
            session_id = self._create_session()

        # Build message content
        content = []
        if image_url:
            content.append({
                "type": "image",
                "source": {"type": "url", "url": image_url},
            })
        if message:
            content.append({"type": "text", "text": message})
        if not content:
            content.append({"type": "text", "text": "(empty message)"})

        # Send message and process response
        response_text = ""
        completed = False

        with self.client.beta.sessions.events.stream(session_id) as stream:
            self.client.beta.sessions.events.send(
                session_id,
                events=[{"type": "user.message", "content": content}],
            )

            for event in stream:
                if event.type == "agent.message":
                    for block in event.content:
                        if hasattr(block, "text"):
                            response_text += block.text

                elif event.type == "agent.custom_tool_use":
                    await self._handle_custom_tool(
                        session_id, event.id, event.name, event.input
                    )

                elif event.type == "session.status_idle":
                    break

                elif event.type == "session.status_terminated":
                    logger.error(f"Session {session_id} terminated")
                    break

        return {
            "response": response_text.strip(),
            "session_id": session_id,
            "completed": completed,
        }

    async def _handle_custom_tool(
        self,
        session_id: str,
        tool_use_id: str,
        tool_name: str,
        tool_input: dict,
    ) -> None:
        """Execute a custom tool and send the result back to the agent."""
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            result = {"error": f"Tool '{tool_name}' not found"}
        else:
            try:
                result = await handler(**tool_input)
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                result = {"error": str(e)}

        self.client.beta.sessions.events.send(
            session_id,
            events=[
                {
                    "type": "user.custom_tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(result, ensure_ascii=False),
                },
            ],
        )
