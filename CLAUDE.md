# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Median Code Backend consists of two packages:

- **api_craft**: Code generation library that transforms JSON API specifications into FastAPI project scaffolds
- **api**: FastAPI service exposing REST endpoints (wraps api_craft)

**Python 3.13+ required.**

## Package Structure

```
src/
├── api_craft/          # Code generation library
│   ├── main.py         # APIGenerator class, generate_fastapi()
│   ├── models/         # Pydantic models (input.py, template.py, types.py)
│   ├── templates/      # Mako templates (*.mako)
│   ├── transformers.py
│   ├── extractors.py
│   └── renderers.py
└── api/                # FastAPI service
    └── ...
```

## Commands

```bash
# Install dependencies
poetry install

# Run all tests
make test
# Or: poetry run pytest tests/ -v

# Run a single test
poetry run pytest tests/test_e2e.py::TestItemsAPI::test_list_items -v

# Format code
poetry run black src/

# Clean caches and test output
make clean
```

## api_craft Architecture

### Generation Pipeline

```
InputAPI (JSON) → Transform → Extract → Render → Write
```

1. **Transform** (`transformers.py`): Converts `InputAPI` models to `TemplateAPI` models with computed name variants
2. **Extract** (`extractors.py`): Pulls models, views, path/query parameters from transformed API
3. **Render** (`renderers.py`): Applies Mako templates to extracted components
4. **Write** (`main.py`): Outputs generated project files to filesystem

### Generated Output Structure

```
{api-name}/
├── src/
│   ├── models.py      # Pydantic models
│   ├── views.py       # FastAPI routes
│   ├── main.py        # FastAPI app
│   ├── path.py        # Path parameter validators (if needed)
│   └── query.py       # Query parameter validators (if needed)
├── pyproject.toml
├── Makefile
├── Dockerfile
└── swagger.py
```

## Naming Convention

All user-provided names in input JSON must be **PascalCase**. The `Name` type automatically provides:
- `.snake_name` → snake_case
- `.camel_name` → camelCase
- `.kebab_name` → kebab-case

## Adding Generation Features

To extend api_craft:
1. Add input fields to `api_craft/models/input.py`
2. Add template fields to `api_craft/models/template.py`
3. Update `transformers.py` to convert input → template format
4. Update `extractors.py` to extract new components
5. Create/modify Mako templates in `templates/`
6. Update `renderers.py` and `main.py` to render and write new files

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) as specified in `docs/COMMIT_MESSAGE_STANDARD.md`. Use scopes: `api`, `generation`, `models`, `config`, `deps`. Body must be sequential bullet points. Do NOT include Co-Authored-By lines.
