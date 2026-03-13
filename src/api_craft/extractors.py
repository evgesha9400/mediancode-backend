import re

from api_craft.models.template import (
    TemplateAPI,
    TemplateModel,
    TemplateORMModel,
    TemplatePathParam,
    TemplateQueryParam,
)

# Mapping of module.Type patterns to their import statements
MODULE_TYPE_IMPORTS = {
    "datetime": "import datetime",
    "uuid": "import uuid",
    "decimal": "import decimal",
    "pathlib": "from pathlib import Path",
    "enum": "from enum import Enum",
}

# Mapping of standalone pydantic types to their import statements
PYDANTIC_TYPE_IMPORTS = {
    "EmailStr": "from pydantic import EmailStr",
    "HttpUrl": "from pydantic import HttpUrl",
}

# Mapping of types to extra pip dependencies they require
TYPE_EXTRA_DEPENDENCIES = {
    "EmailStr": "email-validator (>=2.0.0,<3.0.0)",
}

# Mapping of typing generics to their import from typing module
TYPING_GENERICS = {
    "List",
    "Dict",
    "Set",
    "Tuple",
    "Optional",
    "Union",
    "Any",
    "Callable",
    "Sequence",
    "Mapping",
    "Iterable",
    "Iterator",
    "Type",
    "Literal",
}


def collect_imports(types: list[str]) -> set[str]:
    """Collect required import statements for a list of type strings.

    This function analyzes type strings and determines which imports are needed.
    It handles:
    - Module-qualified types (e.g., 'datetime.datetime', 'uuid.UUID')
    - Typing generics (e.g., 'List[str]', 'Optional[int]')
    - Nested generics (e.g., 'Optional[List[datetime.datetime]]')

    :param types: List of type strings (e.g., ["datetime.datetime", "List[str]", "Optional[int]"])
    :returns: Set of import statements (e.g., {"import datetime", "from typing import List, Optional"})
    """
    imports = set()
    typing_imports = set()

    for type_str in types:
        # Find all module.Type patterns (e.g., datetime.datetime, uuid.UUID)
        module_patterns = re.findall(r"(\w+)\.\w+", type_str)
        for module in module_patterns:
            if module in MODULE_TYPE_IMPORTS:
                imports.add(MODULE_TYPE_IMPORTS[module])

        # Find all typing generics (e.g., List, Optional, Dict)
        # Match word characters followed by [ to identify generics
        generic_patterns = re.findall(r"(\w+)\[", type_str)
        for generic in generic_patterns:
            if generic in TYPING_GENERICS:
                typing_imports.add(generic)

        # Also check for standalone typing types (like Any, which doesn't use [])
        words = re.findall(r"\b(\w+)\b", type_str)
        for word in words:
            if word in TYPING_GENERICS and word not in generic_patterns:
                typing_imports.add(word)
            elif word in PYDANTIC_TYPE_IMPORTS:
                imports.add(PYDANTIC_TYPE_IMPORTS[word])

    # Combine typing imports into a single import statement if any exist
    if typing_imports:
        sorted_typing = sorted(typing_imports)
        imports.add(f"from typing import {', '.join(sorted_typing)}")

    return imports


def collect_model_imports(models: list[TemplateModel]) -> set[str]:
    """Collect all required imports for the generated models.

    :param models: Collection of template-ready models.
    :returns: Set of import statements needed for the models.
    """
    types = []
    for model in models:
        for field in model.fields:
            types.append(field.type)
    return collect_imports(types)


def collect_path_params_imports(path_params: list[TemplatePathParam]) -> set[str]:
    """Collect all required imports for path parameters.

    :param path_params: Collection of path parameters.
    :returns: Set of import statements needed for the path parameters.
    """
    types = [param.type for param in path_params]
    return collect_imports(types)


def collect_query_params_imports(query_params: list[TemplateQueryParam]) -> set[str]:
    """Collect all required imports for query parameters.

    :param query_params: Collection of query parameters.
    :returns: Set of import statements needed for the query parameters.
    """
    types = [param.type for param in query_params]
    return collect_imports(types)


def extract_path_parameters(template_api: TemplateAPI) -> list[TemplatePathParam]:
    """Extracts and returns a list of unique TemplatePathParams from the views of the TemplateAPI instance."""
    path_param_names = set()
    path_params = []
    for view in template_api.views:
        for param in view.path_params:
            if param.snake_name not in path_param_names:
                path_params.append(param)
                path_param_names.add(param.snake_name)
    return path_params


def extract_query_parameters(template_api: TemplateAPI) -> list[TemplateQueryParam]:
    """Extracts and returns a list of unique TemplateQueryParams from the views of the TemplateAPI instance."""
    query_param_names = set()
    query_params = []
    for view in template_api.views:
        for param in view.query_params:
            if param.snake_name not in query_param_names:
                query_params.append(param)
                query_param_names.add(param.snake_name)
    return query_params


def collect_extra_dependencies(types: list[str]) -> list[str]:
    """Collect extra pip dependencies required by the given types.

    :param types: List of type strings used in models.
    :returns: Sorted list of pip dependency strings.
    """
    deps = set()
    for type_str in types:
        words = re.findall(r"\b(\w+)\b", type_str)
        for word in words:
            if word in TYPE_EXTRA_DEPENDENCIES:
                deps.add(TYPE_EXTRA_DEPENDENCIES[word])
    return sorted(deps)


def collect_model_extra_dependencies(models: list[TemplateModel]) -> list[str]:
    """Collect extra pip dependencies required by model field types.

    :param models: Collection of template-ready models.
    :returns: Sorted list of pip dependency strings.
    """
    types = []
    for model in models:
        for field in model.fields:
            types.append(field.type)
    return collect_extra_dependencies(types)


def collect_orm_imports(orm_models: list[TemplateORMModel]) -> list[str]:
    """Collect SQLAlchemy column type imports needed by ORM models.

    :param orm_models: Collection of ORM models.
    :returns: Deduplicated list of SQLAlchemy type names to import.
    """
    imports = set()
    for model in orm_models:
        for field in model.fields:
            # Normalize parameterized types: String(N) → String, DateTime(timezone=True) → DateTime
            col_type = field.column_type
            if "(" in col_type:
                imports.add(col_type.split("(")[0])
            else:
                imports.add(col_type)

    return sorted(imports)


def collect_association_tables(orm_models: list[TemplateORMModel]) -> list[dict]:
    """Collect unique many_to_many association table definitions.

    :param orm_models: Collection of ORM models.
    :returns: List of association table definition dicts (deduplicated by name).
    """
    seen: set[str] = set()
    tables: list[dict] = []

    # Build a quick lookup: class_name -> (table_name, pk_column_name)
    model_lookup: dict[str, tuple[str, str]] = {}
    for m in orm_models:
        pk_fields = [f for f in m.fields if f.primary_key]
        if pk_fields:
            model_lookup[m.source_model] = (m.table_name, pk_fields[0].name)

    for model in orm_models:
        for rel in model.relationships:
            if rel.cardinality != "many_to_many" or not rel.association_table:
                continue
            if rel.association_table in seen:
                continue
            seen.add(rel.association_table)

            target_info = model_lookup.get(rel.target_model)
            source_info = model_lookup.get(model.source_model)
            if not target_info or not source_info:
                continue

            source_table, source_pk = source_info
            target_table, target_pk = target_info

            tables.append(
                {
                    "name": rel.association_table,
                    "left_table": source_table,
                    "left_pk": source_pk,
                    "left_fk_col": f"{source_table.rstrip('s')}_id",
                    "right_table": target_table,
                    "right_pk": target_pk,
                    "right_fk_col": f"{target_table.rstrip('s')}_id",
                }
            )

    return tables


def collect_database_dependencies() -> list[str]:
    """Return pip dependencies for database support.

    :returns: List of pip dependency strings.
    """
    return [
        "sqlalchemy[asyncio] (>=2.0.0,<3.0.0)",
        "greenlet (>=3.0.0,<4.0.0)",
        "asyncpg (>=0.31.0,<1.0.0)",
        "alembic (>=1.18.0,<2.0.0)",
    ]
