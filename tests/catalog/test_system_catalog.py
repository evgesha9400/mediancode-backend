# tests/catalog/test_system_catalog.py
"""Integration tests: live HTTP catalog endpoints vs seed migration constants."""

import pytest
from httpx import AsyncClient

from support.catalog_contract import (
    CONSTRAINTS_DATA,
    EXPECTED_CONSTRAINT_NAMES,
    EXPECTED_FV_TEMPLATE_NAMES,
    EXPECTED_MV_TEMPLATE_NAMES,
    EXPECTED_TYPE_NAMES,
    FIELD_VALIDATOR_TEMPLATES_DATA,
    MODEL_VALIDATOR_TEMPLATES_DATA,
    TYPES_DATA,
)

TEST_CLERK_ID = "test_user_catalog"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]

_TYPES_BY_NAME = {t["name"]: t for t in TYPES_DATA}
_CONSTRAINTS_BY_NAME = {c["name"]: c for c in CONSTRAINTS_DATA}
_FV_BY_NAME = {t["name"]: t for t in FIELD_VALIDATOR_TEMPLATES_DATA}
_MV_BY_NAME = {t["name"]: t for t in MODEL_VALIDATOR_TEMPLATES_DATA}


class TestTypeCatalog:
    """GET /types matches seed ``TYPES_DATA``."""

    async def test_exact_count_matches_seed(self, client: AsyncClient) -> None:
        resp = await client.get("/types")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == len(TYPES_DATA) == 11

    async def test_every_expected_type_name_present(self, client: AsyncClient) -> None:
        resp = await client.get("/types")
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()}
        assert names == set(EXPECTED_TYPE_NAMES)

    @pytest.mark.parametrize(
        "type_name",
        ["str", "datetime", "EmailStr", "Decimal", "date"],
    )
    async def test_type_full_shape_spot_check(
        self, client: AsyncClient, type_name: str
    ) -> None:
        seed = _TYPES_BY_NAME[type_name]
        resp = await client.get("/types")
        assert resp.status_code == 200
        row = next(t for t in resp.json() if t["name"] == type_name)

        assert row["id"] == str(seed["id"])
        assert row["namespaceId"] == str(seed["namespace_id"])
        assert row["name"] == seed["name"]
        assert row["pythonType"] == seed["python_type"]
        assert row["description"] == seed["description"]
        assert row["importPath"] == seed["import_path"]
        expected_parent = (
            str(seed["parent_type_id"]) if seed["parent_type_id"] is not None else None
        )
        assert row["parentTypeId"] == expected_parent
        assert isinstance(row["usedInFields"], int)
        assert row["usedInFields"] >= 0


class TestConstraintCatalog:
    """GET /field-constraints matches seed ``CONSTRAINTS_DATA``."""

    async def test_exact_count_matches_seed(self, client: AsyncClient) -> None:
        resp = await client.get("/field-constraints")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == len(CONSTRAINTS_DATA) == 8

    async def test_every_expected_constraint_name_present(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/field-constraints")
        assert resp.status_code == 200
        names = {c["name"] for c in resp.json()}
        assert names == set(EXPECTED_CONSTRAINT_NAMES)

    @pytest.mark.parametrize(
        "constraint_name",
        ["max_length", "gt", "multiple_of", "pattern"],
    )
    async def test_constraint_full_shape_spot_check(
        self, client: AsyncClient, constraint_name: str
    ) -> None:
        seed = _CONSTRAINTS_BY_NAME[constraint_name]
        resp = await client.get("/field-constraints")
        assert resp.status_code == 200
        row = next(c for c in resp.json() if c["name"] == constraint_name)

        assert row["id"] == str(seed["id"])
        assert row["namespaceId"] == str(seed["namespace_id"])
        assert row["name"] == seed["name"]
        assert row["description"] == seed["description"]
        assert row["parameterTypes"] == seed["parameter_types"]
        assert row["docsUrl"] == seed["docs_url"]
        assert row["compatibleTypes"] == seed["compatible_types"]
        assert isinstance(row["usedInFields"], int)
        assert row["usedInFields"] >= 0


class TestFieldValidatorTemplateCatalog:
    """GET /field-validator-templates matches seed ``FIELD_VALIDATOR_TEMPLATES_DATA``."""

    async def test_exact_count_is_ten(self, client: AsyncClient) -> None:
        resp = await client.get("/field-validator-templates")
        assert resp.status_code == 200
        assert len(resp.json()) == len(FIELD_VALIDATOR_TEMPLATES_DATA) == 10

    async def test_all_template_names_including_previously_untested_four(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/field-validator-templates")
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()}
        assert names == set(EXPECTED_FV_TEMPLATE_NAMES)
        for required in (
            "Empty String to None",
            "Strip Characters",
            "Replace Substring",
            "Regex Replace",
        ):
            assert required in names

    @pytest.mark.parametrize(
        "template_name",
        [
            "Trim",
            "Normalize Case",
            "Normalize Whitespace",
            "Trim To Length",
            "Round Decimal",
            "Empty String to None",
            "Clamp to Range",
            "Strip Characters",
            "Replace Substring",
            "Regex Replace",
        ],
    )
    async def test_fv_template_shape_spot_check(
        self, client: AsyncClient, template_name: str
    ) -> None:
        seed = _FV_BY_NAME[template_name]
        resp = await client.get("/field-validator-templates")
        assert resp.status_code == 200
        row = next(t for t in resp.json() if t["name"] == template_name)

        assert row["id"] == str(seed["id"])
        assert row["name"] == seed["name"]
        assert row["description"] == seed["description"]
        assert row["compatibleTypes"] == seed["compatible_types"]
        assert row["mode"] == seed["mode"]
        assert row["bodyTemplate"] == seed["body_template"]

        params = row["parameters"]
        assert isinstance(params, list)
        assert len(params) == len(seed["parameters"])
        for i, p in enumerate(params):
            s = seed["parameters"][i]
            assert p["key"] == s["key"]
            assert p["label"] == s["label"]
            assert p["type"] == s["type"]
            assert p["required"] == s["required"]
            if "placeholder" in s:
                assert p["placeholder"] == s["placeholder"]
            if "options" in s:
                assert p["options"] == s["options"]

        assert isinstance(row["bodyTemplate"], str)
        assert len(row["bodyTemplate"]) > 0


class TestModelValidatorTemplateCatalog:
    """GET /model-validator-templates matches seed ``MODEL_VALIDATOR_TEMPLATES_DATA``."""

    async def test_exact_count_is_five(self, client: AsyncClient) -> None:
        resp = await client.get("/model-validator-templates")
        assert resp.status_code == 200
        assert len(resp.json()) == len(MODEL_VALIDATOR_TEMPLATES_DATA) == 5

    async def test_all_template_names_present(self, client: AsyncClient) -> None:
        resp = await client.get("/model-validator-templates")
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()}
        assert names == set(EXPECTED_MV_TEMPLATE_NAMES)

    @pytest.mark.parametrize(
        "template_name",
        [
            "Field Comparison",
            "Mutual Exclusivity",
            "At Least One Required",
            "All Or None",
            "Conditional Required",
        ],
    )
    async def test_mv_template_shape_spot_check(
        self, client: AsyncClient, template_name: str
    ) -> None:
        seed = _MV_BY_NAME[template_name]
        resp = await client.get("/model-validator-templates")
        assert resp.status_code == 200
        row = next(t for t in resp.json() if t["name"] == template_name)

        assert row["id"] == str(seed["id"])
        assert row["name"] == seed["name"]
        assert row["description"] == seed["description"]
        assert row["mode"] == seed["mode"]
        assert row["bodyTemplate"] == seed["body_template"]

        params = row["parameters"]
        assert isinstance(params, list)
        assert len(params) == len(seed["parameters"])
        for i, p in enumerate(params):
            s = seed["parameters"][i]
            assert p["key"] == s["key"]
            assert p["label"] == s["label"]
            assert p["type"] == s["type"]
            assert p["required"] == s["required"]
            if "placeholder" in s:
                assert p["placeholder"] == s["placeholder"]
            if "options" in s:
                assert p["options"] == s["options"]

        mappings = row["fieldMappings"]
        assert isinstance(mappings, list)
        assert len(mappings) == len(seed["field_mappings"])
        for i, m in enumerate(mappings):
            s = seed["field_mappings"][i]
            assert m["key"] == s["key"]
            assert m["label"] == s["label"]
            assert m["compatibleTypes"] == s["compatibleTypes"]
            assert m["required"] == s["required"]

        assert isinstance(row["bodyTemplate"], str)
        assert len(row["bodyTemplate"]) > 0
