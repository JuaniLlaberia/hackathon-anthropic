"""
Custom tools para que el agente de Claude interactue con la API de Mercado Libre.
Estas funciones se ejecutan cuando el agente llama a un custom tool.
"""

from __future__ import annotations

import httpx
import logging

logger = logging.getLogger(__name__)

ML_BASE_URL = "https://api.mercadolibre.com"
ML_SITE = "MLA"  # Argentina


async def search_ml_category(query: str) -> dict:
    """
    Predice la categoria de Mercado Libre para un producto.
    Usa el domain_discovery endpoint de ML.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ML_BASE_URL}/sites/{ML_SITE}/domain_discovery/search",
            params={"q": query},
        )
    if response.is_error:
        return {"error": f"ML API error: {response.status_code}"}

    results = response.json()
    if not results:
        return {"error": "No se encontraron categorias para ese producto"}

    # Devolver las primeras 3 sugerencias
    categories = []
    for r in results[:3]:
        categories.append({
            "category_id": r.get("category_id"),
            "category_name": r.get("category_name"),
            "domain_name": r.get("domain_name"),
        })
    return {"categories": categories}


async def get_category_attributes(category_id: str) -> dict:
    """
    Obtiene los atributos requeridos para una categoria de ML.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ML_BASE_URL}/categories/{category_id}/attributes"
        )
    if response.is_error:
        return {"error": f"ML API error: {response.status_code}"}

    attributes = response.json()

    # Filtrar solo los requeridos y relevantes
    required = []
    optional = []
    for attr in attributes:
        tags = attr.get("tags", {})
        info = {
            "id": attr["id"],
            "name": attr["name"],
            "type": attr.get("value_type", "string"),
        }
        # Incluir valores permitidos si existen
        values = attr.get("values", [])
        if values and len(values) <= 20:
            info["allowed_values"] = [
                {"id": v["id"], "name": v["name"]} for v in values
            ]

        if tags.get("required") or tags.get("catalog_required"):
            required.append(info)
        elif attr.get("relevance", 0) >= 1:
            optional.append(info)

    return {"required_attributes": required, "optional_attributes": optional[:10]}


async def create_ml_listing(
    access_token: str,
    title: str,
    category_id: str,
    price: float,
    condition: str,
    description: str,
    currency_id: str = "ARS",
    available_quantity: int = 1,
    buying_mode: str = "buy_it_now",
    listing_type_id: str = "free",
    attributes: list | None = None,
    picture_url: str | None = None,
) -> dict:
    """
    Crea una publicacion en Mercado Libre.
    Primero crea el item, luego agrega la descripcion (endpoint separado).
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Build item payload
    item_payload = {
        "title": title[:60],
        "category_id": category_id,
        "price": price,
        "currency_id": currency_id,
        "available_quantity": available_quantity,
        "buying_mode": buying_mode,
        "condition": condition,
        "listing_type_id": "free",  # Force free listing (no photos required)
    }

    # Ensure attributes list exists and add GTIN if missing (required by many categories)
    attrs = list(attributes) if attributes else []
    attr_ids = {a.get("id") for a in attrs}
    if "GTIN" not in attr_ids:
        attrs.append({"id": "GTIN", "value_name": "Does not apply"})
    if "ITEM_CONDITION" not in attr_ids:
        attrs.append({"id": "ITEM_CONDITION", "value_name": "Usado" if condition == "used" else "Nuevo"})
    item_payload["attributes"] = attrs

    if picture_url:
        item_payload["pictures"] = [{"source": picture_url}]

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create item
        response = await client.post(
            f"{ML_BASE_URL}/items",
            headers=headers,
            json=item_payload,
        )

    if response.is_error:
        error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        return {"error": f"Error creando item: {response.status_code}", "detail": str(error_detail)[:500]}

    item = response.json()
    item_id = item.get("id")
    permalink = item.get("permalink")

    # Add description (separate endpoint)
    if description and item_id:
        async with httpx.AsyncClient(timeout=15.0) as client:
            desc_response = await client.post(
                f"{ML_BASE_URL}/items/{item_id}/description",
                headers=headers,
                json={"plain_text": description},
            )
        if desc_response.is_error:
            logger.warning(f"Error agregando descripcion a {item_id}: {desc_response.status_code}")

    return {
        "success": True,
        "item_id": item_id,
        "permalink": permalink,
        "status": item.get("status"),
        "title": item.get("title"),
    }


# Mapa de funciones para resolver custom tool calls del agente
# create_ml_listing NO se incluye aca porque necesita access_token del usuario
TOOL_HANDLERS = {
    "search_ml_category": search_ml_category,
    "get_category_attributes": get_category_attributes,
}
