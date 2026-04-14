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
from app.shared.models.user import User
from .ml_tools import TOOL_HANDLERS, create_ml_listing

logger = logging.getLogger(__name__)

settings = get_settings()

AGENT_SYSTEM_PROMPT = """You are an expert Mercado Libre Argentina assistant that helps people create product listings via WhatsApp.

## Your role
Help users create optimized Mercado Libre listings. Be friendly, concise (it's WhatsApp), and knowledgeable about ML best practices. Always respond in informal Argentinian Spanish (vos, che, dale).

## STEP 1: When user sends a photo or describes a product
- Use search_ml_category to find the correct ML category
- Use web_search to find reference prices (search "precio [product] mercadolibre argentina")
- Use get_category_attributes to know mandatory attributes
- After ALL tools return, write ONE message with the complete draft:

*Tu publicacion esta lista!*

*Titulo:* [optimized title, max 60 chars, format: Product Brand Model Specs]
*Categoria:* [category name]
*Condicion:* [Nuevo/Usado]
*Precio sugerido:* $[price] (basado en publicaciones similares entre $X y $Y)
*Envio:* Mercado Envios
*Stock:* 1

*Descripcion:*
[generated description]

Podes decirme si queres cambiar algo (precio, titulo, descripcion) o escribi *publicar* para publicarlo en Mercado Libre.

## STEP 2: When user confirms with "publicar", "si", "dale", "confirmo"
- Call the create_ml_listing tool with ALL the listing data
- After the tool returns, tell the user the result:
  - If success: share the permalink URL
  - If error: explain what went wrong

## Rules
- ALWAYS respond in informal Argentinian Spanish (vos, che, dale)
- After using tools, ALWAYS write a message to the user. NEVER end your turn silently after tools.
- If you can't determine something from the photo, ask the user
- Suggest price based on web search, not invented
- ONLY call create_ml_listing when the user explicitly confirms
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
        "name": "create_ml_listing",
        "description": "Create and publish a listing on Mercado Libre. Call this ONLY after the user explicitly confirms the listing. This will publish the product live on ML.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Product title (max 60 chars, ML format: Product Brand Model Specs)",
                },
                "category_id": {
                    "type": "string",
                    "description": "ML category ID (e.g. 'MLA1055')",
                },
                "price": {
                    "type": "number",
                    "description": "Price in ARS",
                },
                "condition": {
                    "type": "string",
                    "enum": ["new", "used"],
                    "description": "Product condition",
                },
                "description": {
                    "type": "string",
                    "description": "Full product description (plain text)",
                },
                "available_quantity": {
                    "type": "integer",
                    "description": "Stock quantity (default 1)",
                    "default": 1,
                },
                "listing_type_id": {
                    "type": "string",
                    "enum": ["free", "gold_special", "gold_pro"],
                    "description": "Listing type: free (Gratuita), gold_special (Clasica), gold_pro (Premium). Default: gold_special",
                    "default": "gold_special",
                },
                "attributes": {
                    "type": "array",
                    "description": "Category-specific attributes array (e.g. [{id: 'BRAND', value_name: 'Logitech'}])",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "value_name": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["title", "category_id", "price", "condition", "description"],
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
        self._current_user_id: UUID | None = None
        self._current_image_url: str | None = None
        self._agent_id: str | None = None
        self._environment_id: str | None = None

    def _get_or_create_agent(self) -> str:
        if self._agent_id:
            return self._agent_id

        agent = self.client.beta.agents.create(
            name="ML Listing Assistant",
            model="claude-haiku-4-5",
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
        self._current_user_id = user_id
        if image_url:
            self._current_image_url = image_url
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

        # Send message and collect response
        response_text = ""
        last_message_text = ""
        completed = False
        has_pending_builtin_tool = False

        try:
            # Try sending message; if session is stuck waiting for tool results,
            # interrupt first and retry with a new session
            try:
                self.client.beta.sessions.events.send(
                    session_id,
                    events=[{"type": "user.message", "content": content}],
                )
            except anthropic.BadRequestError as e:
                if "waiting on responses to events" in str(e):
                    print(f"[AGENT] Session stuck, creating new one", flush=True)
                    session_id = self._create_session()
                    self.client.beta.sessions.events.send(
                        session_id,
                        events=[{"type": "user.message", "content": content}],
                    )
                else:
                    raise

            with self.client.beta.sessions.events.stream(session_id) as stream:

                for event in stream:
                    print(f"[AGENT] Event: {event.type}", flush=True)

                    if event.type == "agent.message":
                        msg_text = ""
                        for block in event.content:
                            if hasattr(block, "text"):
                                msg_text += block.text
                        if msg_text.strip():
                            last_message_text = msg_text
                        response_text += msg_text

                    elif event.type == "agent.custom_tool_use":
                        tool_use_id = event.id
                        tool_name = event.name
                        tool_input = event.input if hasattr(event, "input") else {}
                        print(f"[AGENT] Tool call: {tool_name}({tool_input})", flush=True)
                        await self._handle_custom_tool(
                            session_id, tool_use_id, tool_name, tool_input
                        )

                    elif event.type == "agent.tool_use":
                        # Built-in tool (web_search, etc.) — Anthropic executes it
                        has_pending_builtin_tool = True
                        print(f"[AGENT] Built-in tool: {getattr(event, 'name', '?')}", flush=True)

                    elif event.type == "agent.tool_result":
                        # Built-in tool finished
                        has_pending_builtin_tool = False
                        print(f"[AGENT] Built-in tool result received", flush=True)

                    elif event.type == "session.status_idle":
                        if has_pending_builtin_tool:
                            # Built-in tool still running, keep listening
                            print(f"[AGENT] Idle but waiting for built-in tool...", flush=True)
                            has_pending_builtin_tool = False
                            continue
                        print(f"[AGENT] Session idle", flush=True)
                        break

                    elif event.type == "session.error":
                        error_msg = getattr(event, 'error', getattr(event, 'message', str(event)))
                        print(f"[AGENT] Session error: {error_msg}", flush=True)

                    elif event.type == "session.status_terminated":
                        print(f"[AGENT] Session terminated", flush=True)
                        completed = True
                        break

        except Exception as e:
            print(f"[AGENT] Error: {e}", flush=True)
            # If session is stuck, mark as completed so a new one is created next time
            return {
                "response": "Hubo un error procesando tu mensaje. Intenta de nuevo.",
                "session_id": session_id,
                "completed": True,
            }

        # Use last non-empty message (the final complete response after all tools)
        final_text = last_message_text.strip() or response_text.strip()
        return {
            "response": final_text,
            "session_id": session_id,
            "completed": completed,
        }

    async def _handle_create_listing(self, tool_input: dict) -> dict:
        """Handle create_ml_listing tool: get user's ML token and create the listing."""
        if not self._current_user_id:
            return {"error": "No user context available"}

        user = self.db.query(User).filter(User.id == self._current_user_id).first()
        if not user or not user.ml_access_token:
            return {"error": "User has no ML access token. They need to connect their ML account first."}

        try:
            result = await create_ml_listing(
                access_token=user.ml_access_token,
                title=tool_input.get("title", ""),
                category_id=tool_input.get("category_id", ""),
                price=tool_input.get("price", 0),
                condition=tool_input.get("condition", "used"),
                description=tool_input.get("description", ""),
                available_quantity=tool_input.get("available_quantity", 1),
                listing_type_id=tool_input.get("listing_type_id", "free"),
                attributes=tool_input.get("attributes"),
                picture_url=self._current_image_url,
            )
            return result
        except Exception as e:
            print(f"[AGENT] Error creating ML listing: {e}", flush=True)
            return {"error": str(e)}

    async def _handle_custom_tool(
        self,
        session_id: str,
        tool_use_id: str,
        tool_name: str,
        tool_input: dict,
    ) -> None:
        """Execute a custom tool and send the result back to the agent."""
        if tool_name == "create_ml_listing":
            result = await self._handle_create_listing(tool_input)
        else:
            handler = TOOL_HANDLERS.get(tool_name)
            if not handler:
                result = {"error": f"Tool '{tool_name}' not found"}
            else:
                try:
                    result = await handler(**tool_input)
                except Exception as e:
                    print(f"[AGENT] Tool error for {tool_name}: {e}", flush=True)
                    result = {"error": str(e)}
        print(f"[AGENT] Tool result for {tool_name}: {str(result)[:500]}", flush=True)

        self.client.beta.sessions.events.send(
            session_id,
            events=[
                {
                    "type": "user.custom_tool_result",
                    "custom_tool_use_id": tool_use_id,
                    "content": [
                        {"type": "text", "text": json.dumps(result, ensure_ascii=False)},
                    ],
                },
            ],
        )
