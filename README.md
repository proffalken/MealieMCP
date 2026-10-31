# mealie-mcp

An [MCP](https://modelcontextprotocol.io) server for a [Mealie](https://mealie.io) instance. It lets Claude search, create and update recipes and manage the meal plan.

## Tools

| Tool | What it does |
|---|---|
| `search_recipes` | Search recipes by name or ingredient |
| `get_recipe` | Full recipe, including ingredients and steps |
| `create_recipe` | New recipe with description, ingredients, method steps, notes and source URL |
| `update_recipe` | Change any of the above on an existing recipe (lists are replaced, not appended) |
| `create_recipe_from_url` | Import from a URL; falls back to a stub linking to the URL if scraping fails |
| `get_meal_plan` / `add_to_meal_plan` / `remove_from_meal_plan` | Meal plan management |

Every recipe returned (including those inside meal plan entries) has a `url` field pointing at its page in the Mealie web UI (`<MEALIE_URI>/g/<group>/r/<slug>`).

## Configuration

Set `MEALIE_URI` (e.g. `https://meals.example.com`) and `MEALIE_API_TOKEN`, either in the environment or in a `.env` file.

## Running

```sh
uv sync
uv run mealie-mcp
```

Claude Desktop config:

```json
"mealie": {
  "command": "/path/to/MealieMCP/.venv/bin/mealie-mcp",
  "env": { "MEALIE_URI": "...", "MEALIE_API_TOKEN": "..." }
}
```

## Tests

```sh
uv run pytest
```

## Licence

MIT. See [LICENSE](LICENSE).
