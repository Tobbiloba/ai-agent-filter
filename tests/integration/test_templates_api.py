"""Integration tests for policy templates API."""

import uuid
import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.templates.loader import clear_cache


@pytest.fixture
def client():
    """Create TestClient for each test."""
    clear_cache()
    with TestClient(app) as c:
        yield c


def unique_id() -> str:
    """Generate a short unique ID for test isolation."""
    return str(uuid.uuid4())[:8]


class TestTemplatesListEndpoint:
    """Tests for GET /templates endpoint."""

    def test_get_templates_returns_200(self, client):
        """GET /templates should return 200."""
        response = client.get("/templates")
        assert response.status_code == 200

    def test_get_templates_returns_list(self, client):
        """GET /templates should return templates list."""
        response = client.get("/templates")
        data = response.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)

    def test_get_templates_returns_three_templates(self, client):
        """GET /templates should return 3 templates."""
        response = client.get("/templates")
        data = response.json()
        assert len(data["templates"]) == 3

    def test_get_templates_contains_expected_ids(self, client):
        """GET /templates should contain finance, healthcare, general."""
        response = client.get("/templates")
        data = response.json()
        ids = {t["id"] for t in data["templates"]}
        assert ids == {"finance", "healthcare", "general"}

    def test_get_templates_only_metadata(self, client):
        """GET /templates should only return metadata, not full policy."""
        response = client.get("/templates")
        data = response.json()
        for template in data["templates"]:
            assert "id" in template
            assert "name" in template
            assert "description" in template
            # Should NOT include full policy
            assert "policy" not in template


class TestTemplateDetailEndpoint:
    """Tests for GET /templates/{template_id} endpoint."""

    def test_get_finance_template_returns_200(self, client):
        """GET /templates/finance should return 200."""
        response = client.get("/templates/finance")
        assert response.status_code == 200

    def test_get_finance_template_returns_full_template(self, client):
        """GET /templates/finance should return full template with policy."""
        response = client.get("/templates/finance")
        data = response.json()
        assert data["id"] == "finance"
        assert data["name"] == "Finance & Payments"
        assert "policy" in data
        assert "rules" in data["policy"]

    def test_get_healthcare_template_returns_200(self, client):
        """GET /templates/healthcare should return 200."""
        response = client.get("/templates/healthcare")
        assert response.status_code == 200

    def test_get_general_template_returns_200(self, client):
        """GET /templates/general should return 200."""
        response = client.get("/templates/general")
        assert response.status_code == 200

    def test_get_invalid_template_returns_404(self, client):
        """GET /templates/invalid should return 404."""
        response = client.get("/templates/invalid")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_template_content_type_is_json(self, client):
        """GET /templates/{id} should return JSON content type."""
        response = client.get("/templates/finance")
        assert "application/json" in response.headers["content-type"]


class TestCreatePolicyFromTemplate:
    """Tests for POST /policies/{project_id}/from-template/{template_id} endpoint."""

    @pytest.fixture
    def project_with_api_key(self, client):
        """Create a project and return project_id and api_key."""
        project_id = f"tpl-test-{unique_id()}"
        response = client.post(
            "/projects",
            json={"id": project_id, "name": "Template Test"},
        )
        data = response.json()
        return data["id"], data["api_key"]

    def test_create_policy_from_finance_template(self, client, project_with_api_key):
        """POST /policies/{project}/from-template/finance should create policy."""
        project_id, api_key = project_with_api_key
        response = client.post(
            f"/policies/{project_id}/from-template/finance",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Finance Policy"
        assert data["is_active"] is True
        assert "rules" in data

    def test_create_policy_from_healthcare_template(self, client, project_with_api_key):
        """POST /policies/{project}/from-template/healthcare should create policy."""
        project_id, api_key = project_with_api_key
        response = client.post(
            f"/policies/{project_id}/from-template/healthcare",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Healthcare Policy"

    def test_create_policy_from_general_template(self, client, project_with_api_key):
        """POST /policies/{project}/from-template/general should create policy."""
        project_id, api_key = project_with_api_key
        response = client.post(
            f"/policies/{project_id}/from-template/general",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "General Policy"

    def test_create_policy_with_custom_name(self, client, project_with_api_key):
        """POST /policies/{project}/from-template/{id}?name=Custom should use custom name."""
        project_id, api_key = project_with_api_key
        response = client.post(
            f"/policies/{project_id}/from-template/finance?name=My Custom Policy",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Custom Policy"

    def test_create_policy_from_invalid_template_returns_404(self, client, project_with_api_key):
        """POST /policies/{project}/from-template/invalid should return 404."""
        project_id, api_key = project_with_api_key
        response = client.post(
            f"/policies/{project_id}/from-template/invalid",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_create_policy_without_api_key_returns_401(self, client, project_with_api_key):
        """POST /policies/{project}/from-template/{id} without API key should return 401."""
        project_id, _ = project_with_api_key
        response = client.post(f"/policies/{project_id}/from-template/finance")
        assert response.status_code == 401

    def test_created_policy_can_be_retrieved(self, client, project_with_api_key):
        """Policy created from template should be retrievable."""
        project_id, api_key = project_with_api_key

        # Create policy from template
        client.post(
            f"/policies/{project_id}/from-template/finance",
            headers={"X-API-Key": api_key},
        )

        # Retrieve policy
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Finance Policy"
        assert data["is_active"] is True


class TestPolicyFromTemplateValidation:
    """Tests that policies from templates work for validation."""

    @pytest.fixture
    def project_with_general_policy(self, client):
        """Create project with general policy from template."""
        project_id = f"gen-val-{unique_id()}"

        # Create project
        response = client.post(
            "/projects",
            json={"id": project_id, "name": "General Test"},
        )
        data = response.json()
        project_id = data["id"]
        api_key = data["api_key"]

        # Create policy from general template (simpler - allows by default)
        client.post(
            f"/policies/{project_id}/from-template/general",
            headers={"X-API-Key": api_key},
        )

        return project_id, api_key

    def test_general_policy_allows_actions(self, client, project_with_general_policy):
        """General policy should allow actions by default."""
        project_id, api_key = project_with_general_policy
        response = client.post(
            "/validate_action",
            headers={"X-API-Key": api_key},
            json={
                "project_id": project_id,
                "agent_name": "test-agent",
                "action_type": "any_action",
                "params": {"key": "value"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True

    def test_general_policy_returns_validation_response(self, client, project_with_general_policy):
        """General policy should return proper validation response."""
        project_id, api_key = project_with_general_policy
        response = client.post(
            "/validate_action",
            headers={"X-API-Key": api_key},
            json={
                "project_id": project_id,
                "agent_name": "test-agent",
                "action_type": "test_action",
                "params": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should have proper structure
        assert "allowed" in data
        assert "action_id" in data
        assert "timestamp" in data

    def test_validation_endpoint_works_with_template_policy(self, client, project_with_general_policy):
        """Validation endpoint should work with template-created policies."""
        project_id, api_key = project_with_general_policy
        # Make multiple requests to verify policy is active
        for i in range(3):
            response = client.post(
                "/validate_action",
                headers={"X-API-Key": api_key},
                json={
                    "project_id": project_id,
                    "agent_name": f"agent-{i}",
                    "action_type": "test_action",
                    "params": {"iteration": i},
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["allowed"] is True
