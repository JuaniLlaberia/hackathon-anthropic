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


async def search_similar_products(query: str, limit: int = 5) -> dict:
    """
    Busca productos similares en ML para referencia de precios.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ML_BASE_URL}/sites/{ML_SITE}/search",
            params={"q": query, "limit": limit},
        )
    if response.is_error:
        return {"error": f"ML API error: {response.status_code}"}

    data = response.json()
    results = data.get("results", [])

    products = []
    for item in results:
        products.append({
            "title": item.get("title"),
            "price": item.get("price"),
            "currency": item.get("currency_id"),
            "condition": item.get("condition"),
            "sold_quantity": item.get("sold_quantity", 0),
            "permalink": item.get("permalink"),
        })

    prices = [p["price"] for p in products if p["price"]]
    price_summary = {}
    if prices:
        price_summary = {
            "min": min(prices),
            "max": max(prices),
            "avg": round(sum(prices) / len(prices)),
        }

    return {"products": products, "price_summary": price_summary}


# Mapa de funciones para resolver custom tool calls del agente
TOOL_HANDLERS = {
    "search_ml_category": search_ml_category,
    "get_category_attributes": get_category_attributes,
    "search_similar_products": search_similar_products,
}
