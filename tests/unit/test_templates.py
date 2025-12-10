"""Unit tests for policy templates loader."""

import pytest

from server.templates.loader import (
    load_templates,
    get_template,
    list_templates,
    clear_cache,
)


class TestLoadTemplates:
    """Tests for load_templates function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_load_templates_returns_dict(self):
        """load_templates should return a dictionary."""
        templates = load_templates()
        assert isinstance(templates, dict)

    def test_load_templates_returns_three_templates(self):
        """load_templates should return exactly 3 templates."""
        templates = load_templates()
        assert len(templates) == 3

    def test_load_templates_contains_expected_ids(self):
        """load_templates should contain finance, healthcare, and general."""
        templates = load_templates()
        assert "finance" in templates
        assert "healthcare" in templates
        assert "general" in templates

    def test_load_templates_caches_results(self):
        """load_templates should cache results on subsequent calls."""
        templates1 = load_templates()
        templates2 = load_templates()
        # Should be the same object (cached)
        assert templates1 is templates2


class TestGetTemplate:
    """Tests for get_template function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_get_template_finance_returns_correct_template(self):
        """get_template('finance') should return finance template."""
        template = get_template("finance")
        assert template is not None
        assert template["id"] == "finance"
        assert template["name"] == "Finance & Payments"

    def test_get_template_healthcare_returns_correct_template(self):
        """get_template('healthcare') should return healthcare template."""
        template = get_template("healthcare")
        assert template is not None
        assert template["id"] == "healthcare"
        assert template["name"] == "Healthcare & PII Protection"

    def test_get_template_general_returns_correct_template(self):
        """get_template('general') should return general template."""
        template = get_template("general")
        assert template is not None
        assert template["id"] == "general"
        assert template["name"] == "General Purpose"

    def test_get_template_invalid_returns_none(self):
        """get_template('invalid') should return None."""
        template = get_template("invalid")
        assert template is None

    def test_get_template_empty_string_returns_none(self):
        """get_template('') should return None."""
        template = get_template("")
        assert template is None


class TestListTemplates:
    """Tests for list_templates function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_list_templates_returns_list(self):
        """list_templates should return a list."""
        templates = list_templates()
        assert isinstance(templates, list)

    def test_list_templates_returns_three_items(self):
        """list_templates should return 3 items."""
        templates = list_templates()
        assert len(templates) == 3

    def test_list_templates_contains_only_metadata(self):
        """list_templates should only contain id, name, description."""
        templates = list_templates()
        for template in templates:
            assert set(template.keys()) == {"id", "name", "description"}
            # Should NOT contain full policy
            assert "policy" not in template

    def test_list_templates_metadata_is_correct(self):
        """list_templates metadata should match full templates."""
        templates = list_templates()
        template_ids = {t["id"] for t in templates}
        assert template_ids == {"finance", "healthcare", "general"}


class TestTemplateStructure:
    """Tests for template structure validity."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_cache()

    def test_finance_template_has_policy(self):
        """Finance template should have policy with rules."""
        template = get_template("finance")
        assert "policy" in template
        assert "rules" in template["policy"]
        assert len(template["policy"]["rules"]) > 0

    def test_healthcare_template_has_policy(self):
        """Healthcare template should have policy with rules."""
        template = get_template("healthcare")
        assert "policy" in template
        assert "rules" in template["policy"]
        assert len(template["policy"]["rules"]) > 0

    def test_general_template_has_policy(self):
        """General template should have policy with rules."""
        template = get_template("general")
        assert "policy" in template
        assert "rules" in template["policy"]
        assert len(template["policy"]["rules"]) > 0

    def test_finance_template_has_amount_constraints(self):
        """Finance template should have amount constraints."""
        template = get_template("finance")
        rules = template["policy"]["rules"]
        # Check that at least one rule has amount constraint
        has_amount = any(
            "amount" in rule.get("constraints", {})
            for rule in rules
        )
        assert has_amount

    def test_healthcare_template_has_not_pattern_constraint(self):
        """Healthcare template should have not_pattern constraints for SSN."""
        template = get_template("healthcare")
        rules = template["policy"]["rules"]
        # Check that at least one rule has not_pattern constraint
        has_not_pattern = any(
            any("not_pattern" in str(v) for v in rule.get("constraints", {}).values())
            for rule in rules
        )
        assert has_not_pattern

    def test_general_template_has_wildcard_rule(self):
        """General template should have wildcard rule."""
        template = get_template("general")
        rules = template["policy"]["rules"]
        has_wildcard = any(rule.get("action") == "*" for rule in rules)
        assert has_wildcard

    def test_all_templates_have_default_action(self):
        """All templates should have default action."""
        for template_id in ["finance", "healthcare", "general"]:
            template = get_template(template_id)
            assert "default" in template["policy"]
            assert template["policy"]["default"] in ["allow", "block"]


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clear_cache_resets_cache(self):
        """clear_cache should reset the cache."""
        # Load templates to populate cache
        templates1 = load_templates()

        # Clear cache
        clear_cache()

        # Load again - should be a new object
        templates2 = load_templates()

        # Should NOT be the same object (cache was cleared)
        assert templates1 is not templates2
