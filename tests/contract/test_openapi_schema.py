"""OpenAPI Schema Validation Tests.

Validates that the FastAPI-generated OpenAPI schema is valid and complete.
"""

import pytest
from openapi_spec_validator import validate
from openapi_spec_validator.exceptions import OpenAPISpecValidatorError


class TestOpenAPISchemaValidity:
    """Tests for OpenAPI schema validity."""

    def test_schema_is_valid_openapi_3(self, openapi_schema):
        """Schema conforms to OpenAPI 3.x specification."""
        try:
            validate(openapi_schema)
        except OpenAPISpecValidatorError as e:
            pytest.fail(f"OpenAPI schema validation failed: {e}")

    def test_schema_has_required_info(self, openapi_schema):
        """Schema has required info section with title and version."""
        assert "info" in openapi_schema
        assert "title" in openapi_schema["info"]
        assert "version" in openapi_schema["info"]
        assert openapi_schema["info"]["title"] == "AI Agent Safety Filter"
        assert openapi_schema["info"]["version"] == "0.1.0"

    def test_all_endpoints_documented(self, openapi_schema):
        """All expected endpoints are present in schema."""
        expected_paths = [
            "/",
            "/health",
            "/projects",
            "/projects/{project_id}",
            "/validate_action",
            "/policies/{project_id}",
            "/policies/{project_id}/history",
            "/logs/{project_id}",
            "/logs/{project_id}/stats",
        ]
        paths = openapi_schema.get("paths", {})
        for expected in expected_paths:
            assert expected in paths, f"Missing endpoint: {expected}"

    def test_endpoints_have_operation_ids(self, openapi_schema):
        """All operations have unique operationIds."""
        operation_ids = set()
        for path, methods in openapi_schema.get("paths", {}).items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    op_id = details.get("operationId")
                    assert op_id, f"Missing operationId for {method.upper()} {path}"
                    assert op_id not in operation_ids, f"Duplicate operationId: {op_id}"
                    operation_ids.add(op_id)

    def test_post_endpoints_have_request_body(self, openapi_schema):
        """POST endpoints define their request body schemas."""
        post_endpoints = [
            "/projects",
            "/validate_action",
            "/policies/{project_id}",
        ]
        for endpoint in post_endpoints:
            path_info = openapi_schema["paths"].get(endpoint, {})
            post_info = path_info.get("post", {})
            assert "requestBody" in post_info, f"Missing requestBody for POST {endpoint}"
            assert "content" in post_info["requestBody"]
            assert "application/json" in post_info["requestBody"]["content"]

    def test_endpoints_have_response_schemas(self, openapi_schema):
        """All endpoints define their response schemas."""
        for path, methods in openapi_schema.get("paths", {}).items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "delete", "patch"]:
                    responses = details.get("responses", {})
                    has_success = any(code.startswith("2") for code in responses.keys())
                    assert has_success, f"Missing success response for {method.upper()} {path}"

    def test_schema_component_definitions(self, openapi_schema):
        """Required schema components are defined."""
        expected_schemas = [
            "ActionRequest",
            "ActionResponse",
            "PolicyCreate",
            "PolicyResponse",
            "ProjectCreate",
            "ProjectResponse",
            "AuditLogResponse",
            "AuditLogList",
            "HTTPValidationError",
        ]
        schemas = openapi_schema.get("components", {}).get("schemas", {})
        for expected in expected_schemas:
            assert expected in schemas, f"Missing schema definition: {expected}"

    def test_action_request_schema_complete(self, openapi_schema):
        """ActionRequest schema has all required fields."""
        schemas = openapi_schema.get("components", {}).get("schemas", {})
        action_request = schemas.get("ActionRequest", {})
        properties = action_request.get("properties", {})

        required_fields = ["project_id", "agent_name", "action_type"]
        for field in required_fields:
            assert field in properties, f"ActionRequest missing field: {field}"

        # params is optional but should be defined
        assert "params" in properties

    def test_action_response_schema_complete(self, openapi_schema):
        """ActionResponse schema has all required fields."""
        schemas = openapi_schema.get("components", {}).get("schemas", {})
        action_response = schemas.get("ActionResponse", {})
        properties = action_response.get("properties", {})

        required_fields = ["allowed", "action_id", "timestamp"]
        for field in required_fields:
            assert field in properties, f"ActionResponse missing field: {field}"

        # Optional fields
        assert "reason" in properties
        assert "execution_time_ms" in properties

    def test_policy_response_schema_complete(self, openapi_schema):
        """PolicyResponse schema has all required fields."""
        schemas = openapi_schema.get("components", {}).get("schemas", {})
        policy_response = schemas.get("PolicyResponse", {})
        properties = policy_response.get("properties", {})

        required_fields = ["id", "project_id", "name", "version", "rules", "is_active"]
        for field in required_fields:
            assert field in properties, f"PolicyResponse missing field: {field}"

    def test_audit_log_schema_complete(self, openapi_schema):
        """AuditLogResponse schema has all required fields."""
        schemas = openapi_schema.get("components", {}).get("schemas", {})
        audit_log = schemas.get("AuditLogResponse", {})
        properties = audit_log.get("properties", {})

        required_fields = [
            "action_id", "project_id", "agent_name", "action_type",
            "params", "allowed", "timestamp"
        ]
        for field in required_fields:
            assert field in properties, f"AuditLogResponse missing field: {field}"

    def test_error_schemas_defined(self, openapi_schema):
        """Error schemas are properly defined."""
        schemas = openapi_schema.get("components", {}).get("schemas", {})

        # HTTPValidationError for 422 responses
        assert "HTTPValidationError" in schemas
        validation_error = schemas["HTTPValidationError"]
        assert "properties" in validation_error
        assert "detail" in validation_error["properties"]
