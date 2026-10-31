"""Thin async wrapper around the parts of the Mealie REST API we use."""

from typing import Any

import httpx


class MealieError(Exception):
    """Mealie returned an error response."""


def _steps(instructions: list[str]) -> list[dict[str, Any]]:
    return [
        {"title": "", "summary": "", "text": text, "ingredientReferences": []}
        for text in instructions
    ]


def _recipe_patch(
    *,
    name: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    ingredients: list[str] | None = None,
    instructions: list[str] | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Build a PATCH body containing only the fields that were given.

    An empty notes string clears the notes.
    """
    patch: dict[str, Any] = {}
    if name is not None:
        patch["name"] = name
    if description is not None:
        patch["description"] = description
    if notes is not None:
        patch["notes"] = [{"title": "", "text": notes}] if notes else []
    if ingredients is not None:
        patch["recipeIngredient"] = [{"note": i} for i in ingredients]
    if instructions is not None:
        patch["recipeInstructions"] = _steps(instructions)
    if source_url is not None:
        patch["orgURL"] = source_url
    return patch


class MealieClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
            transport=transport,
        )

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise MealieError(f"Could not reach Mealie ({method} {path}): {e}") from e
        if response.is_error:
            raise MealieError(
                f"Mealie {method} {path} failed: {response.status_code} {response.text}"
            )
        return response.json() if response.content else None

    # Recipes

    async def search_recipes(self, query: str) -> Any:
        return await self._request("GET", "/api/recipes", params={"search": query})

    async def get_recipe(self, slug: str) -> Any:
        return await self._request("GET", f"/api/recipes/{slug}")

    async def create_recipe(self, name: str, **fields) -> Any:
        slug = await self._request("POST", "/api/recipes", json={"name": name})
        patch = _recipe_patch(**fields)
        if patch:
            await self._request("PATCH", f"/api/recipes/{slug}", json=patch)
        return await self.get_recipe(slug)

    async def update_recipe(self, slug: str, **fields) -> Any:
        patch = _recipe_patch(**fields)
        if not patch:
            raise MealieError("Nothing to update: give at least one field to change.")
        await self._request("PATCH", f"/api/recipes/{slug}", json=patch)
        return await self.get_recipe(slug)

    async def create_recipe_from_url(
        self, url: str, name: str | None = None, description: str | None = None
    ) -> Any:
        try:
            slug = await self._request(
                "POST", "/api/recipes/create/url", json={"url": url}
            )
        except MealieError:
            # Scraping failed: keep a stub so the link isn't lost.
            return await self.create_recipe(
                name or url, description=description, source_url=url
            )
        return await self.get_recipe(slug)

    # Meal plans

    async def get_meal_plan(self, start_date: str, end_date: str) -> Any:
        return await self._request(
            "GET",
            "/api/households/mealplans",
            params={"start_date": start_date, "end_date": end_date},
        )

    async def add_to_meal_plan(self, recipe_id: str, date: str, meal_type: str) -> Any:
        return await self._request(
            "POST",
            "/api/households/mealplans",
            json={"date": date, "entryType": meal_type, "recipeId": recipe_id},
        )

    async def remove_from_meal_plan(self, plan_entry_id: int) -> Any:
        return await self._request(
            "DELETE", f"/api/households/mealplans/{plan_entry_id}"
        )
