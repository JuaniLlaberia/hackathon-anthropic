"""
Funciones para interactuar con la API de Mercado Libre.

publish_listing() es la unica funcion expuesta al agente.
Internamente: busca categoria → resuelve atributos → sube imagen → crea listing.
"""

from __future__ import annotations

import httpx
import logging

logger = logging.getLogger(__name__)

ML_BASE_URL = "https://api.mercadolibre.com"
ML_SITE = "MLA"  # Argentina


# ── Public: price estimate (exposed to agent) ──


async def get_price_estimate(query: str) -> dict:
    """Search ML for similar products and return a price range."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{ML_BASE_URL}/sites/{ML_SITE}/search",
            params={"q": query, "limit": 10},
        )
    if resp.is_error:
        return {"error": "No pude buscar precios de referencia, pedile al usuario que sugiera un precio."}

    results = resp.json().get("results", [])
    prices = [r["price"] for r in results if r.get("price")]
    if not prices:
        return {"error": "No encontré productos similares para estimar precio."}

    return {
        "min": min(prices),
        "max": max(prices),
        "avg": round(sum(prices) / len(prices)),
        "count": len(prices),
        "suggestion": f"Productos similares se venden entre ${min(prices):,.0f} y ${max(prices):,.0f} (promedio ${round(sum(prices) / len(prices)):,.0f})",
    }


# ── Internal helpers (NOT exposed to the agent) ──


async def _search_category(query: str) -> str | None:
    """Return the best category_id for a product query, or None."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{ML_BASE_URL}/sites/{ML_SITE}/domain_discovery/search",
            params={"q": query},
        )
    if resp.is_error or not resp.json():
        return None
    return resp.json()[0].get("category_id")


async def _get_required_attribute_ids(category_id: str) -> list[str]:
    """Return list of required attribute IDs for a category."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{ML_BASE_URL}/categories/{category_id}/attributes")
    if resp.is_error:
        return ["BRAND", "MODEL"]  # safe fallback
    attrs = resp.json()
    required = []
    for attr in attrs:
        tags = attr.get("tags", {})
        if tags.get("required") or tags.get("catalog_required"):
            required.append(attr["id"])
    return required if required else ["BRAND", "MODEL"]


async def _find_gtin(brand: str, model: str) -> str | None:
    """Search UPC Item DB for the product's GTIN/EAN barcode."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.upcitemdb.com/prod/trial/search",
                params={"s": f"{brand} {model}", "type": "product"},
                headers={"Accept": "application/json"},
            )
        if resp.is_error:
            print(f"[GTIN] UPC DB error: {resp.status_code}", flush=True)
            return None

        items = resp.json().get("items", [])
        if not items:
            print(f"[GTIN] No results for {brand} {model}", flush=True)
            return None

        # Return the first EAN/UPC found
        ean = items[0].get("ean") or items[0].get("upc")
        print(f"[GTIN] Found: {ean} for {brand} {model}", flush=True)
        return ean
    except Exception as e:
        print(f"[GTIN] Error: {e}", flush=True)
        return None


async def _upload_image(access_token: str, image_url: str) -> str | None:
    """Download image from URL and upload to ML. Returns picture_id or None."""
    # Download (Kapso URLs are temporary redirects)
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        dl = await client.get(image_url)
    if dl.is_error:
        logger.warning(f"Failed to download image: {dl.status_code}")
        return None

    content_type = dl.headers.get("content-type", "image/jpeg")
    ext = "jpg" if "jpeg" in content_type or "jpg" in content_type else "png"

    # Upload as multipart to ML
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ML_BASE_URL}/pictures/items/upload",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"file": (f"image.{ext}", dl.content, content_type)},
        )
    if resp.is_error:
        logger.warning(f"Failed to upload image to ML: {resp.status_code}")
        return None

    return resp.json().get("id")


# ── Public function (exposed to the agent as a tool) ──


async def publish_listing(
    access_token: str,
    image_url: str | None,
    brand: str,
    model: str,
    title: str,
    price: float,
    condition: str,
    description: str,
) -> dict:
    """
    Full publication pipeline:
    1. Search ML category from title
    2. Get required attributes and build them
    3. Upload image if available
    4. Create listing with correct payload
    """
    print(f"[PUBLISH] Starting: {title} | {brand} {model} | ${price}", flush=True)

    # 1. Find category
    category_id = await _search_category(f"{brand} {model}")
    if not category_id:
        category_id = await _search_category(title)
    if not category_id:
        return {"error": "No se encontró una categoría de MercadoLibre para este producto."}

    print(f"[PUBLISH] Category: {category_id}", flush=True)

    # 2. Build attributes — always include BRAND and MODEL, plus any other required
    required_ids = await _get_required_attribute_ids(category_id)
    attributes = [
        {"id": "BRAND", "value_name": brand},
        {"id": "MODEL", "value_name": model},
    ]
    # Add ITEM_CONDITION if required (separate from the top-level "condition")
    if "ITEM_CONDITION" in required_ids:
        condition_value = "Nuevo" if condition == "new" else "Usado"
        attributes.append({"id": "ITEM_CONDITION", "value_name": condition_value})

    # Find GTIN automatically
    gtin = await _find_gtin(brand, model)
    if gtin:
        attributes.append({"id": "GTIN", "value_name": gtin})

    print(f"[PUBLISH] Attributes: {attributes}", flush=True)

    # 3. Upload image
    pictures = []
    if image_url and access_token:
        picture_id = await _upload_image(access_token, image_url)
        if picture_id:
            pictures.append({"id": picture_id})
            print(f"[PUBLISH] Image uploaded: {picture_id}", flush=True)
        else:
            print(f"[PUBLISH] Image upload failed, continuing without image", flush=True)

    # 4. Create listing
    payload = {
        "title": title[:60],  # ML max 60 chars
        "category_id": category_id,
        "price": price,
        "currency_id": "ARS",
        "available_quantity": 1,
        "buying_mode": "buy_it_now",
        "condition": condition,
        "listing_type_id": "gold_special",
        "attributes": attributes,
    }
    if pictures:
        payload["pictures"] = pictures

    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ML_BASE_URL}/items",
            json=payload,
            headers=headers,
        )

    if resp.is_error:
        error_data = resp.json() if "application/json" in resp.headers.get("content-type", "") else resp.text
        logger.error(f"ML create listing failed: {resp.status_code} - {error_data}")

        # Extract human-readable error causes
        causes = []
        if isinstance(error_data, dict):
            for cause in error_data.get("cause", []):
                if cause.get("type") == "error":
                    causes.append(cause.get("message", ""))
        cause_text = "; ".join(causes) if causes else str(error_data)
        return {"error": f"Error al crear la publicación ({resp.status_code}): {cause_text}"}

    item = resp.json()
    item_id = item.get("id")

    # 5. Add description (separate ML API call)
    if description and item_id:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                f"{ML_BASE_URL}/items/{item_id}/description",
                json={"plain_text": description},
                headers=headers,
            )

    print(f"[PUBLISH] Success! {item.get('permalink')}", flush=True)

    return {
        "success": True,
        "item_id": item_id,
        "title": item.get("title"),
        "price": item.get("price"),
        "permalink": item.get("permalink"),
        "status": item.get("status"),
    }
