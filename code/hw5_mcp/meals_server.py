"""STDIO MCP server for the public TheMealDB API."""

from __future__ import annotations

import logging
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)
mcp = FastMCP("meals")
BASE_URL = "https://www.themealdb.com/api/json/v1/1"


async def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{BASE_URL}/{path}", params=params)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.error("TheMealDB request failed: %s", exc)
        raise RuntimeError(f"TheMealDB request failed: {exc}") from exc


@mcp.tool()
async def search_meals_by_name(query: str, limit: int = 5) -> dict[str, Any]:
    """Search meals by name and return compact recipe cards."""
    if not query.strip() or not 1 <= limit <= 25:
        raise ValueError("query must be non-empty and limit must be from 1 through 25")
    payload = await _get("search.php", {"s": query.strip()})
    meals = payload.get("meals") or []
    if not meals:
        return {"meals": [], "message": "no matches"}
    return {
        "meals": [
            {"id": item.get("idMeal"), "name": item.get("strMeal"), "area": item.get("strArea"), "category": item.get("strCategory"), "thumb": item.get("strMealThumb")}
            for item in meals[:limit]
        ]
    }


@mcp.tool()
async def meals_by_ingredient(ingredient: str, limit: int = 12) -> dict[str, Any]:
    """Return compact cards for meals filtered by main ingredient."""
    if not ingredient.strip() or not 1 <= limit <= 25:
        raise ValueError("ingredient must be non-empty and limit must be from 1 through 25")
    payload = await _get("filter.php", {"i": ingredient.strip()})
    meals = payload.get("meals") or []
    if not meals:
        return {"meals": [], "message": "no matches"}
    return {"meals": [{"id": item.get("idMeal"), "name": item.get("strMeal"), "thumb": item.get("strMealThumb")} for item in meals[:limit]]}


def _details(item: dict[str, Any]) -> dict[str, Any]:
    ingredients = []
    for index in range(1, 21):
        name = (item.get(f"strIngredient{index}") or "").strip()
        measure = (item.get(f"strMeasure{index}") or "").strip()
        if name:
            ingredients.append({"name": name, "measure": measure})
    return {
        "id": item.get("idMeal"), "name": item.get("strMeal"), "category": item.get("strCategory"),
        "area": item.get("strArea"), "instructions": item.get("strInstructions"),
        "image": item.get("strMealThumb"), "source": item.get("strSource"),
        "youtube": item.get("strYoutube"), "ingredients": ingredients,
    }


async def _one(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = await _get(path, params)
    meals = payload.get("meals") or []
    if not meals:
        return {"error": "no matches"}
    return _details(meals[0])


@mcp.tool()
async def meal_details(id: str | int) -> dict[str, Any]:
    """Return the complete recipe details for one meal ID."""
    return await _one("lookup.php", {"i": str(id)})


@mcp.tool()
async def random_meal() -> dict[str, Any]:
    """Return one random meal and its complete recipe details."""
    return await _one("random.php")


if __name__ == "__main__":
    mcp.run(transport="stdio")

