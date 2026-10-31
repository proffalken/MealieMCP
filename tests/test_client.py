import json

import httpx
import pytest

from mealie_mcp.client import MealieClient, MealieError


class FakeMealie:
    """Records requests and replies with canned responses keyed by (method, path)."""

    def __init__(self, responses=None):
        self.requests: list[httpx.Request] = []
        self.responses = responses or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = (request.method, request.url.path)
        status, body = self.responses.get(key, (200, {}))
        return httpx.Response(status, json=body)

    def bodies(self, method, path):
        return [
            json.loads(r.content)
            for r in self.requests
            if r.method == method and r.url.path == path
        ]


def make_client(fake: FakeMealie) -> MealieClient:
    return MealieClient(
        "https://mealie.test", "tok", transport=httpx.MockTransport(fake)
    )


async def test_sends_bearer_token():
    fake = FakeMealie()
    await make_client(fake).search_recipes("pie")
    assert fake.requests[0].headers["Authorization"] == "Bearer tok"


async def test_create_recipe_saves_instruction_steps():
    fake = FakeMealie(
        {
            ("POST", "/api/recipes"): (201, "beef-pies"),
            ("GET", "/api/recipes/beef-pies"): (200, {"slug": "beef-pies"}),
        }
    )
    await make_client(fake).create_recipe(
        name="Beef pies",
        instructions=["Preheat the oven.", "Bake for 20 minutes."],
    )
    [patch] = fake.bodies("PATCH", "/api/recipes/beef-pies")
    assert patch["recipeInstructions"] == [
        {"title": "", "summary": "", "text": "Preheat the oven.", "ingredientReferences": []},
        {"title": "", "summary": "", "text": "Bake for 20 minutes.", "ingredientReferences": []},
    ]


async def test_create_recipe_maps_all_fields():
    fake = FakeMealie(
        {
            ("POST", "/api/recipes"): (201, "beef-pies"),
            ("GET", "/api/recipes/beef-pies"): (200, {"slug": "beef-pies"}),
        }
    )
    result = await make_client(fake).create_recipe(
        name="Beef pies",
        description="Cosy",
        notes="Freezes well",
        ingredients=["200g flour"],
        source_url="https://example.com/x",
    )
    assert fake.bodies("POST", "/api/recipes") == [{"name": "Beef pies"}]
    [patch] = fake.bodies("PATCH", "/api/recipes/beef-pies")
    assert patch == {
        "description": "Cosy",
        "notes": [{"title": "", "text": "Freezes well"}],
        "recipeIngredient": [{"note": "200g flour"}],
        "orgURL": "https://example.com/x",
    }
    assert result == {"slug": "beef-pies"}


async def test_create_recipe_skips_patch_when_only_name():
    fake = FakeMealie(
        {
            ("POST", "/api/recipes"): (201, "plain"),
            ("GET", "/api/recipes/plain"): (200, {"slug": "plain"}),
        }
    )
    await make_client(fake).create_recipe(name="Plain")
    assert fake.bodies("PATCH", "/api/recipes/plain") == []


async def test_failed_patch_raises_instead_of_silently_succeeding():
    fake = FakeMealie(
        {
            ("POST", "/api/recipes"): (201, "beef-pies"),
            ("PATCH", "/api/recipes/beef-pies"): (422, {"detail": "bad step"}),
        }
    )
    with pytest.raises(MealieError, match="422"):
        await make_client(fake).create_recipe(name="Beef pies", instructions=["x"])


async def test_update_recipe_only_sends_given_fields():
    fake = FakeMealie(
        {("GET", "/api/recipes/beef-pies"): (200, {"slug": "beef-pies"})}
    )
    await make_client(fake).update_recipe(
        "beef-pies", instructions=["Step one"], notes=""
    )
    [patch] = fake.bodies("PATCH", "/api/recipes/beef-pies")
    assert patch == {
        "recipeInstructions": [
            {"title": "", "summary": "", "text": "Step one", "ingredientReferences": []}
        ],
        "notes": [],
    }


async def test_update_recipe_with_no_changes_raises():
    with pytest.raises(MealieError, match="Nothing to update"):
        await make_client(FakeMealie()).update_recipe("beef-pies")


async def test_create_from_url_falls_back_to_stub():
    fake = FakeMealie(
        {
            ("POST", "/api/recipes/create/url"): (400, {"detail": "no"}),
            ("POST", "/api/recipes"): (201, "stub"),
            ("GET", "/api/recipes/stub"): (200, {"slug": "stub"}),
        }
    )
    await make_client(fake).create_recipe_from_url(
        "https://insta.test/p/1", name="Pies", description="From insta"
    )
    assert fake.bodies("POST", "/api/recipes") == [{"name": "Pies"}]
    [patch] = fake.bodies("PATCH", "/api/recipes/stub")
    assert patch == {"description": "From insta", "orgURL": "https://insta.test/p/1"}


async def test_remove_meal_plan_entry():
    fake = FakeMealie()
    await make_client(fake).remove_from_meal_plan(42)
    assert fake.requests[0].method == "DELETE"
    assert fake.requests[0].url.path == "/api/households/mealplans/42"


async def test_network_failure_becomes_mealie_error():
    def boom(request):
        raise httpx.ConnectError("connection refused")

    client = MealieClient("https://mealie.test", "tok", transport=httpx.MockTransport(boom))
    with pytest.raises(MealieError, match="connection refused"):
        await client.get_recipe("x")
