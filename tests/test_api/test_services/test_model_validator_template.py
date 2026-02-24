# tests/test_api/test_services/test_model_validator_template.py
"""Integration tests for model validator template catalogue."""

import pytest

pytestmark = pytest.mark.integration

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Namespace
from api.services.model_validator_template import ModelValidatorTemplateService


@pytest.mark.asyncio
async def test_list_all_returns_seeded_templates(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """All 6 seeded model validator templates are returned."""
    service = ModelValidatorTemplateService(db_session)
    templates = await service.list_all()
    assert len(templates) == 6
    names = {t.name for t in templates}
    assert "Password Confirmation" in names
    assert "Date Range" in names
    assert "Mutual Exclusivity" in names
    assert "Conditional Required" in names
    assert "Numeric Comparison" in names
    assert "At Least One Required" in names


@pytest.mark.asyncio
async def test_templates_have_correct_structure(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Templates have all required fields populated."""
    service = ModelValidatorTemplateService(db_session)
    templates = await service.list_all()
    for t in templates:
        assert t.id is not None
        assert t.name
        assert t.description
        assert t.mode in ("before", "after")
        assert isinstance(t.parameters, list)
        assert isinstance(t.field_mappings, list)
        assert t.body_template


@pytest.mark.asyncio
async def test_templates_ordered_by_name(
    db_session: AsyncSession,
    provisioned_namespace: Namespace,
):
    """Templates are returned in alphabetical order by name."""
    service = ModelValidatorTemplateService(db_session)
    templates = await service.list_all()
    names = [t.name for t in templates]
    assert names == sorted(names)
