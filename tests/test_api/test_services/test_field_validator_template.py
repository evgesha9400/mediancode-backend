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
    """All 9 seeded field validator templates are returned."""
    service = FieldValidatorTemplateService(db_session)
    templates = await service.list_all()
    assert len(templates) == 9
    names = {t.name for t in templates}
    assert "Strip & Normalize Case" in names
    assert "Normalize Whitespace" in names
    assert "Default If Empty" in names
    assert "Trim To Length" in names
    assert "Strip HTML Tags" in names
    assert "Round Decimal" in names
    assert "Slug Format" in names
    assert "Future Date Only" in names
    assert "Past Date Only" in names


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
