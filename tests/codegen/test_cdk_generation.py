# tests/codegen/test_cdk_generation.py
"""Tests for CDK infrastructure file generation."""

import json
from pathlib import Path

import pytest

from api_craft.main import APIGenerator
from api_craft.models.input import (
    InputAPI,
    InputApiConfig,
    InputCdkConfig,
    InputDatabaseConfig,
    InputEndpoint,
    InputField,
    InputModel,
)

pytestmark = pytest.mark.codegen

_MINIMAL_ENDPOINT = InputEndpoint(name="GetHealth", path="/health", method="GET")

_MINIMAL_OBJECT = InputModel(
    name="Item",
    fields=[
        InputField(name="id", type="int", pk=True, exposure="read_only"),
        InputField(name="title", type="str"),
    ],
)


def _make_api(cdk_config: InputCdkConfig, db_enabled: bool = False) -> InputAPI:
    return InputAPI(
        name="ShopApi",
        endpoints=[_MINIMAL_ENDPOINT],
        objects=[_MINIMAL_OBJECT] if db_enabled else [],
        config=InputApiConfig(
            cdk=cdk_config,
            database=InputDatabaseConfig(enabled=db_enabled),
        ),
    )


# ---------------------------------------------------------------------------
# No CDK by default
# ---------------------------------------------------------------------------


class TestNoCdkByDefault:
    def test_no_infra_directory(self, tmp_path: Path):
        api = _make_api(InputCdkConfig())  # enabled=False
        APIGenerator().generate(api, path=str(tmp_path))
        assert not (tmp_path / "shop-api" / "infra").exists()


# ---------------------------------------------------------------------------
# Fixtures — one per combination
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lambda_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("lambda_no_db")
    api = _make_api(InputCdkConfig(enabled=True, compute="lambda"))
    APIGenerator().generate(api, path=str(tmp))
    return tmp / "shop-api"


@pytest.fixture(scope="module")
def lambda_db_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("lambda_db")
    api = _make_api(InputCdkConfig(enabled=True, compute="lambda"), db_enabled=True)
    APIGenerator().generate(api, path=str(tmp))
    return tmp / "shop-api"


@pytest.fixture(scope="module")
def ecs_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("ecs_no_db")
    api = _make_api(InputCdkConfig(enabled=True, compute="ecs"))
    APIGenerator().generate(api, path=str(tmp))
    return tmp / "shop-api"


@pytest.fixture(scope="module")
def ecs_db_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("ecs_db")
    api = _make_api(InputCdkConfig(enabled=True, compute="ecs"), db_enabled=True)
    APIGenerator().generate(api, path=str(tmp))
    return tmp / "shop-api"


# ---------------------------------------------------------------------------
# Common structure — platform always present
# ---------------------------------------------------------------------------


class TestPlatformAlwaysPresent:
    @pytest.mark.parametrize("fixture_name", [
        "lambda_project", "lambda_db_project", "ecs_project", "ecs_db_project"
    ])
    def test_platform_directory_exists(self, fixture_name: str, request):
        project = request.getfixturevalue(fixture_name)
        assert (project / "infra" / "platform").exists()

    @pytest.mark.parametrize("fixture_name", [
        "lambda_project", "lambda_db_project", "ecs_project", "ecs_db_project"
    ])
    def test_platform_network_stack_exists(self, fixture_name: str, request):
        project = request.getfixturevalue(fixture_name)
        assert (project / "infra" / "platform" / "stacks" / "network.py").exists()

    @pytest.mark.parametrize("fixture_name", [
        "lambda_project", "lambda_db_project", "ecs_project", "ecs_db_project"
    ])
    def test_platform_creates_new_vpc(self, fixture_name: str, request):
        project = request.getfixturevalue(fixture_name)
        content = (project / "infra" / "platform" / "stacks" / "network.py").read_text()
        assert "ec2.Vpc(" in content


# ---------------------------------------------------------------------------
# cdk.json
# ---------------------------------------------------------------------------


class TestCdkJson:
    @pytest.mark.parametrize("subdir", ["platform", "app"])
    def test_cdk_json_has_correct_project_name(self, lambda_project: Path, subdir: str):
        data = json.loads((lambda_project / "infra" / subdir / "cdk.json").read_text())
        assert data["context"]["project"] == "shop-api"

    def test_cdk_json_has_app_entry(self, lambda_project: Path):
        data = json.loads((lambda_project / "infra" / "app" / "cdk.json").read_text())
        assert data["app"] == "python3 app.py"


# ---------------------------------------------------------------------------
# Lambda (no DB)
# ---------------------------------------------------------------------------


class TestLambdaNoDb:
    def test_app_directory_exists(self, lambda_project: Path):
        assert (lambda_project / "infra" / "app").exists()

    def test_compute_stack_exists(self, lambda_project: Path):
        assert (lambda_project / "infra" / "app" / "stacks" / "compute.py").exists()

    def test_no_database_stack(self, lambda_project: Path):
        assert not (lambda_project / "infra" / "app" / "stacks" / "database.py").exists()

    def test_compute_uses_lambda(self, lambda_project: Path):
        content = (lambda_project / "infra" / "app" / "stacks" / "compute.py").read_text()
        assert "lambda_.Function(" in content

    def test_requirements_txt_exists(self, lambda_project: Path):
        assert (lambda_project / "infra" / "app" / "requirements.txt").exists()


# ---------------------------------------------------------------------------
# Lambda + DB
# ---------------------------------------------------------------------------


class TestLambdaDb:
    def test_database_stack_exists(self, lambda_db_project: Path):
        assert (lambda_db_project / "infra" / "app" / "stacks" / "database.py").exists()

    def test_compute_stack_exists(self, lambda_db_project: Path):
        assert (lambda_db_project / "infra" / "app" / "stacks" / "compute.py").exists()

    def test_database_stack_has_rds(self, lambda_db_project: Path):
        content = (lambda_db_project / "infra" / "app" / "stacks" / "database.py").read_text()
        assert "rds.DatabaseInstance(" in content

    def test_compute_uses_lambda(self, lambda_db_project: Path):
        content = (lambda_db_project / "infra" / "app" / "stacks" / "compute.py").read_text()
        assert "lambda_.Function(" in content


# ---------------------------------------------------------------------------
# ECS (no DB)
# ---------------------------------------------------------------------------


class TestEcsNoDb:
    def test_compute_stack_uses_fargate(self, ecs_project: Path):
        content = (ecs_project / "infra" / "app" / "stacks" / "compute.py").read_text()
        assert "ApplicationLoadBalancedFargateService" in content

    def test_no_database_stack(self, ecs_project: Path):
        assert not (ecs_project / "infra" / "app" / "stacks" / "database.py").exists()


# ---------------------------------------------------------------------------
# ECS + DB
# ---------------------------------------------------------------------------


class TestEcsDb:
    def test_database_stack_exists(self, ecs_db_project: Path):
        assert (ecs_db_project / "infra" / "app" / "stacks" / "database.py").exists()

    def test_compute_stack_uses_fargate(self, ecs_db_project: Path):
        content = (ecs_db_project / "infra" / "app" / "stacks" / "compute.py").read_text()
        assert "ApplicationLoadBalancedFargateService" in content

    def test_database_stack_has_rds(self, ecs_db_project: Path):
        content = (ecs_db_project / "infra" / "app" / "stacks" / "database.py").read_text()
        assert "rds.DatabaseInstance(" in content
