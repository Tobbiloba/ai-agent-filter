"""Backwards Compatibility Tests.

Compares the current OpenAPI schema against a baseline snapshot
to detect breaking changes.
"""

import re

import pytest


class TestBackwardsCompatibility:
    """Tests for backwards compatibility against baseline schema."""

    def test_no_endpoints_removed(self, openapi_schema, baseline_schema):
        """No endpoints have been removed from baseline."""
        baseline_paths = set(baseline_schema.get("paths", {}).keys())
        current_paths = set(openapi_schema.get("paths", {}).keys())

        removed = baseline_paths - current_paths
        assert not removed, f"Breaking change: Endpoints removed: {removed}"

    def test_no_http_methods_removed(self, openapi_schema, baseline_schema):
        """No HTTP methods removed from existing endpoints."""
        http_methods = {"get", "post", "put", "delete", "patch", "options", "head"}
        removed_methods = []

        for path in baseline_schema.get("paths", {}):
            if path not in openapi_schema.get("paths", {}):
                continue  # Caught by test_no_endpoints_removed

            baseline_methods = set(baseline_schema["paths"][path].keys()) & http_methods
            current_methods = set(openapi_schema["paths"][path].keys()) & http_methods

            removed = baseline_methods - current_methods
            if removed:
                removed_methods.append(f"{path}: {removed}")

        assert not removed_methods, f"Breaking change: Methods removed: {removed_methods}"

    def test_no_required_fields_removed(self, openapi_schema, baseline_schema):
        """No required fields removed from response schemas."""
        baseline_schemas = baseline_schema.get("components", {}).get("schemas", {})
        current_schemas = openapi_schema.get("components", {}).get("schemas", {})

        removed_fields = []

        for schema_name, baseline_def in baseline_schemas.items():
            if schema_name not in current_schemas:
                continue  # Caught by test_no_schemas_removed

            baseline_required = set(baseline_def.get("required", []))
            current_props = set(current_schemas[schema_name].get("properties", {}).keys())

            # Fields that were required but are now removed
            removed_from_required = baseline_required - current_props
            if removed_from_required:
                removed_fields.append(f"{schema_name}: {removed_from_required}")

        assert not removed_fields, f"Breaking change: Required fields removed: {removed_fields}"

    def test_no_response_schemas_removed(self, openapi_schema, baseline_schema):
        """No response schemas have been removed."""
        baseline_schemas = set(baseline_schema.get("components", {}).get("schemas", {}).keys())
        current_schemas = set(openapi_schema.get("components", {}).get("schemas", {}).keys())

        # Exclude validation error schemas which can change
        exclude = {"HTTPValidationError", "ValidationError"}
        baseline_schemas -= exclude
        current_schemas -= exclude

        removed = baseline_schemas - current_schemas
        assert not removed, f"Breaking change: Schemas removed: {removed}"

    def test_no_breaking_type_changes(self, openapi_schema, baseline_schema):
        """Field types have not changed incompatibly."""
        baseline_schemas = baseline_schema.get("components", {}).get("schemas", {})
        current_schemas = openapi_schema.get("components", {}).get("schemas", {})

        type_changes = []

        for schema_name, baseline_def in baseline_schemas.items():
            if schema_name not in current_schemas:
                continue

            baseline_props = baseline_def.get("properties", {})
            current_props = current_schemas[schema_name].get("properties", {})

            for prop_name, baseline_prop in baseline_props.items():
                if prop_name not in current_props:
                    continue

                current_prop = current_props[prop_name]

                # Check type changes (but allow for $ref vs inline)
                baseline_type = baseline_prop.get("type")
                current_type = current_prop.get("type")

                if baseline_type and current_type and baseline_type != current_type:
                    type_changes.append(
                        f"{schema_name}.{prop_name}: {baseline_type} -> {current_type}"
                    )

        assert not type_changes, f"Breaking change: Type changes detected: {type_changes}"

    def test_no_required_params_added(self, openapi_schema, baseline_schema):
        """No new required parameters added to existing endpoints."""
        new_required_params = []

        for path, methods in baseline_schema.get("paths", {}).items():
            if path not in openapi_schema.get("paths", {}):
                continue

            for method, baseline_details in methods.items():
                if method not in openapi_schema["paths"][path]:
                    continue

                current_details = openapi_schema["paths"][path][method]

                baseline_params = {
                    p["name"]: p.get("required", False)
                    for p in baseline_details.get("parameters", [])
                }
                current_params = {
                    p["name"]: p.get("required", False)
                    for p in current_details.get("parameters", [])
                }

                for param_name, is_required in current_params.items():
                    if param_name not in baseline_params and is_required:
                        new_required_params.append(
                            f"{method.upper()} {path}: {param_name}"
                        )

        assert not new_required_params, \
            f"Breaking change: New required params: {new_required_params}"

    def test_response_codes_preserved(self, openapi_schema, baseline_schema):
        """Success response codes (2xx) not removed from endpoints."""
        removed_codes = []

        for path, methods in baseline_schema.get("paths", {}).items():
            if path not in openapi_schema.get("paths", {}):
                continue

            for method, baseline_details in methods.items():
                if method not in openapi_schema["paths"][path]:
                    continue

                current_details = openapi_schema["paths"][path][method]

                baseline_responses = set(baseline_details.get("responses", {}).keys())
                current_responses = set(current_details.get("responses", {}).keys())

                # Only check 2xx codes
                baseline_2xx = {c for c in baseline_responses if c.startswith("2")}
                current_2xx = {c for c in current_responses if c.startswith("2")}

                removed = baseline_2xx - current_2xx
                if removed:
                    removed_codes.append(f"{method.upper()} {path}: {removed}")

        assert not removed_codes, f"Breaking change: Response codes removed: {removed_codes}"

    def test_version_follows_semver(self, openapi_schema):
        """Version follows semantic versioning pattern."""
        version = openapi_schema["info"]["version"]
        semver_pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
        assert re.match(semver_pattern, version), \
            f"Version '{version}' does not follow semver pattern"
