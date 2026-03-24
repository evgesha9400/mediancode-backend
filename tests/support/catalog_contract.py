# tests/support/catalog_contract.py
"""Source-of-truth catalog constants imported from the seed migration.

Every catalog-contract test compares live HTTP responses against
these constants.  If the seed migration changes, the tests break
immediately — that is the point.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SEED_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "api"
    / "migrations"
    / "versions"
    / "b1a2c3d4e5f6_seed_system_data.py"
)

_spec = importlib.util.spec_from_file_location("_seed_system_data", _SEED_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

TYPES_DATA: list[dict] = _mod.TYPES_DATA
CONSTRAINTS_DATA: list[dict] = _mod.CONSTRAINTS_DATA
FIELD_VALIDATOR_TEMPLATES_DATA: list[dict] = _mod.FIELD_VALIDATOR_TEMPLATES_DATA
MODEL_VALIDATOR_TEMPLATES_DATA: list[dict] = _mod.MODEL_VALIDATOR_TEMPLATES_DATA

EXPECTED_TYPE_NAMES = sorted(t["name"] for t in TYPES_DATA)
EXPECTED_CONSTRAINT_NAMES = sorted(c["name"] for c in CONSTRAINTS_DATA)
EXPECTED_FV_TEMPLATE_NAMES = sorted(t["name"] for t in FIELD_VALIDATOR_TEMPLATES_DATA)
EXPECTED_MV_TEMPLATE_NAMES = sorted(t["name"] for t in MODEL_VALIDATOR_TEMPLATES_DATA)
