"""MCP server exposing Mealie recipes and meal plans as tools."""

import os
from functools import cache
from typing import Annotated, Any, Literal

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from mealie_mcp.client import MealieClient, MealieError

mcp = MCPServer("mealie-mcp")


@cache
def get_client() -> MealieClient:
    url = os.getenv("MEALIE_URI")
    token = os.getenv("MEALIE_API_TOKEN")
    if not url or not token:
        raise MealieError("MEALIE_URI and MEALIE_API_TOKEN must be set")
    return MealieClient(url, token)


async def _call(method: str, *args, **kwargs) -> Any:
    # ToolError messages are shown to the model; other exceptions are hidden by mcp.
    try:
        client = get_client()
        return await getattr(client, method)(*args, **kwargs)
    except MealieError as e:
        raise ToolError(str(e)) from e


Steps = Annotated[
    list[str] | None,
    Field(description="Method steps in order, one string per step (no numbering needed)"),
]
Ingredients = Annotated[
    list[str] | None,
    Field(description="Ingredients as written, one per string (e.g. '200g flour')"),
]
Date = Annotated[str, Field(description="Date in YYYY-MM-DD format")]


@mcp.tool()
async def search_recipes(
    query: Annotated[str, Field(description="Text to search recipe names and ingredients for")],
) -> Any:
    """Search for recipes by name or ingredients."""
    return await _call("search_recipes", query)


@mcp.tool()
async def get_recipe(
    recipe_id: Annotated[str, Field(description="The recipe slug or ID")],
) -> Any:
    """Get full details of a recipe including all ingredients and instructions."""
    return await _call("get_recipe", recipe_id)


@mcp.tool()
async def create_recipe(
    name: Annotated[str, Field(description="The recipe name")],
    description: Annotated[str | None, Field(description="A short description")] = None,
    ingredients: Ingredients = None,
    instructions: Steps = None,
    notes: Annotated[str | None, Field(description="Extra notes (not the method)")] = None,
    source_url: Annotated[str | None, Field(description="Original recipe URL")] = None,
) -> Any:
    """Create a new recipe in Mealie with ingredients and method steps.

    Put the method in `instructions`, not `notes`.
    """
    return await _call(
        "create_recipe",
        name,
        description=description,
        ingredients=ingredients,
        instructions=instructions,
        notes=notes,
        source_url=source_url,
    )


@mcp.tool()
async def update_recipe(
    recipe_id: Annotated[str, Field(description="The recipe slug or ID")],
    name: Annotated[str | None, Field(description="New name")] = None,
    description: Annotated[str | None, Field(description="New description")] = None,
    ingredients: Annotated[
        list[str] | None,
        Field(description="Replaces ALL ingredients, one per string"),
    ] = None,
    instructions: Annotated[
        list[str] | None,
        Field(description="Replaces ALL method steps, in order, one per string"),
    ] = None,
    notes: Annotated[
        str | None, Field(description="Replaces the notes; empty string clears them")
    ] = None,
    source_url: Annotated[str | None, Field(description="Original recipe URL")] = None,
) -> Any:
    """Update an existing recipe. Only the fields you give are changed."""
    return await _call(
        "update_recipe",
        recipe_id,
        name=name,
        description=description,
        ingredients=ingredients,
        instructions=instructions,
        notes=notes,
        source_url=source_url,
    )


@mcp.tool()
async def create_recipe_from_url(
    url: Annotated[str, Field(description="The URL of the recipe to import")],
    name: Annotated[str | None, Field(description="Name to use if scraping fails")] = None,
    description: Annotated[
        str | None, Field(description="Description to use if scraping fails")
    ] = None,
) -> Any:
    """Scrape and import a recipe from a URL.

    If the site can't be scraped, creates a stub recipe linking to the URL.
    """
    return await _call("create_recipe_from_url", url, name=name, description=description)


@mcp.tool()
async def get_meal_plan(start_date: Date, end_date: Date) -> Any:
    """Get the meal plan for a date range."""
    return await _call("get_meal_plan", start_date, end_date)


@mcp.tool()
async def add_to_meal_plan(
    recipe_id: Annotated[str, Field(description="The recipe ID to add")],
    date: Date,
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"],
) -> Any:
    """Add a recipe to the meal plan for a date and meal."""
    return await _call("add_to_meal_plan", recipe_id, date, meal_type)


@mcp.tool()
async def remove_from_meal_plan(
    plan_entry_id: Annotated[
        int, Field(description="Meal plan entry ID (from get_meal_plan), not the recipe ID")
    ],
) -> str:
    """Remove a single entry from the meal plan."""
    await _call("remove_from_meal_plan", plan_entry_id)
    return f"Meal plan entry {plan_entry_id} removed."


def main() -> None:
    load_dotenv()
    mcp.run("stdio")


if __name__ == "__main__":
    main()
