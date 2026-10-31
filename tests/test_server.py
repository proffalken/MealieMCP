from unittest.mock import AsyncMock

import pytest

from mealie_mcp import server


EXPECTED_TOOLS = {
    "search_recipes",
    "get_recipe",
    "create_recipe",
    "update_recipe",
    "create_recipe_from_url",
    "get_meal_plan",
    "add_to_meal_plan",
    "remove_from_meal_plan",
}


async def test_all_tools_registered():
    tools = await server.mcp.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS


async def test_create_recipe_schema_exposes_instructions():
    tools = {t.name: t for t in await server.mcp.list_tools()}
    props = tools["create_recipe"].input_schema["properties"]
    assert "instructions" in props
    assert tools["create_recipe"].input_schema["required"] == ["name"]


async def test_create_recipe_tool_passes_steps_to_client(monkeypatch):
    fake = AsyncMock()
    fake.create_recipe.return_value = {"slug": "pies"}
    monkeypatch.setattr(server, "get_client", lambda: fake)

    await server.mcp.call_tool(
        "create_recipe", {"name": "Pies", "instructions": ["a", "b"]}
    )

    fake.create_recipe.assert_awaited_once()
    assert fake.create_recipe.await_args.kwargs["instructions"] == ["a", "b"]


async def test_mealie_errors_surface_as_tool_errors(monkeypatch):
    from mealie_mcp.client import MealieError

    fake = AsyncMock()
    fake.get_recipe.side_effect = MealieError("404: not found")
    monkeypatch.setattr(server, "get_client", lambda: fake)

    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="404"):
        await server.mcp.call_tool("get_recipe", {"recipe_id": "nope"})


async def test_missing_config_reaches_the_model(monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    monkeypatch.delenv("MEALIE_URI", raising=False)
    monkeypatch.delenv("MEALIE_API_TOKEN", raising=False)
    server.get_client.cache_clear()
    with pytest.raises(ToolError, match="MEALIE_URI"):
        await server.mcp.call_tool("get_recipe", {"recipe_id": "x"})
