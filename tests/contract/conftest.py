"""Shared fixtures for contract tests."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import app


SNAPSHOT_DIR = Path(__file__).parent / "snapshots"
BASELINE_SCHEMA_PATH = SNAPSHOT_DIR / "openapi_v0.1.0.json"


@pytest.fixture(scope="module")
def client():
    """TestClient for the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def openapi_schema(client):
    """Fetch and cache the OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def baseline_schema():
    """Load the baseline schema snapshot."""
    if not BASELINE_SCHEMA_PATH.exists():
        pytest.skip("Baseline schema not found. Run with --create-baseline first.")
    with open(BASELINE_SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def create_test_project(client):
    """Factory fixture to create test projects."""
    def _create(suffix=""):
        project_id = f"contract-{int(time.time() * 1000)}{suffix}"
        response = client.post("/projects", json={
            "id": project_id,
            "name": f"Contract Test {suffix}"
        })
        assert response.status_code == 200
        data = response.json()
        return data["id"], data["api_key"]
    return _create


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--create-baseline",
        action="store_true",
        default=False,
        help="Create baseline schema snapshot"
    )


def pytest_configure(config):
    """Handle custom options before test collection."""
    if config.getoption("--create-baseline"):
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

        with TestClient(app) as client:
            response = client.get("/openapi.json")
            schema = response.json()

        with open(BASELINE_SCHEMA_PATH, "w") as f:
            json.dump(schema, f, indent=2)

        print(f"\nBaseline snapshot created at: {BASELINE_SCHEMA_PATH}")
