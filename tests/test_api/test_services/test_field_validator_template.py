# tests/test_api/test_services/test_field_validator_template.py
"""Integration tests for field validator template catalogue."""

import pytest

pytestmark = pytest.mark.integration

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace
from api.services.field_validator_template import FieldValidatorTemplateService


@pytest.mark.asyncio
async def test_list_all_returns_seeded_templates(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """All 10 seeded field validator templates are returned."""
    service = FieldValidatorTemplateService(db_session)
    templates = await service.list_all()
    assert len(templates) == 10
    names = {t.name for t in templates}
    assert "Trim" in names
    assert "Normalize Case" in names
    assert "Normalize Whitespace" in names
    assert "Trim To Length" in names
    assert "Round Decimal" in names
    assert "Empty String to None" in names
    assert "Clamp to Range" in names
    assert "Strip Characters" in names
    assert "Replace Substring" in names
    assert "Regex Replace" in names


@pytest.mark.asyncio
async def test_templates_have_correct_structure(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Templates have all required fields populated."""
    service = FieldValidatorTemplateService(db_session)
    templates = await service.list_all()
    for t in templates:
        assert t.id is not None
        assert t.name
        assert t.description
        assert t.mode in ("before", "after")
        assert isinstance(t.compatible_types, list)
        assert len(t.compatible_types) > 0
        assert isinstance(t.parameters, list)
        assert t.body_template


@pytest.mark.asyncio
async def test_templates_ordered_by_name(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Templates are returned in alphabetical order by name."""
    service = FieldValidatorTemplateService(db_session)
    templates = await service.list_all()
    names = [t.name for t in templates]
    assert names == sorted(names)
