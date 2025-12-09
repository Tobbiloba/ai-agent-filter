"""Unit tests for aggregate service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import json


class TestAggregateServiceWindowCalculation:
    """Tests for window start time calculation."""

    def test_window_start_hourly(self):
        """Hourly window starts at the current hour."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch("server.services.aggregate.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 15, 14, 35, 45)
            result = service._get_window_start("hourly")
            assert result == datetime(2024, 1, 15, 14, 0, 0)

    def test_window_start_daily(self):
        """Daily window starts at midnight UTC."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch("server.services.aggregate.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 15, 14, 35, 45)
            result = service._get_window_start("daily")
            assert result == datetime(2024, 1, 15, 0, 0, 0)

    def test_window_start_weekly_monday(self):
        """Weekly window starts on Monday midnight UTC."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch("server.services.aggregate.datetime") as mock_dt:
            # Wednesday, Jan 17, 2024
            mock_dt.utcnow.return_value = datetime(2024, 1, 17, 14, 35, 45)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = service._get_window_start("weekly")
            # Should be Monday, Jan 15, 2024
            assert result.weekday() == 0  # Monday
            assert result.hour == 0
            assert result.minute == 0

    def test_window_start_rolling_hours(self):
        """Rolling hours window starts N hours ago."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch("server.services.aggregate.datetime") as mock_dt:
            now = datetime(2024, 1, 15, 14, 35, 45)
            mock_dt.utcnow.return_value = now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = service._get_window_start("rolling_hours:24")
            expected = now - timedelta(hours=24)
            assert result == expected

    def test_window_start_rolling_hours_invalid(self):
        """Invalid rolling hours format falls back to daily."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch("server.services.aggregate.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 15, 14, 35, 45)
            result = service._get_window_start("rolling_hours:invalid")
            # Should fall back to daily
            assert result == datetime(2024, 1, 15, 0, 0, 0)

    def test_window_start_unknown_defaults_daily(self):
        """Unknown window type defaults to daily."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch("server.services.aggregate.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 15, 14, 35, 45)
            result = service._get_window_start("unknown_window")
            assert result == datetime(2024, 1, 15, 0, 0, 0)


class TestAggregateServiceCacheKey:
    """Tests for cache key building."""

    def test_cache_key_scope_agent(self):
        """Agent scope includes project, agent, action, and window in key."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch.object(service, "_get_window_start") as mock_window:
            mock_window.return_value = datetime(2024, 1, 15, 0, 0, 0)
            key = service._build_cache_key(
                "proj-123", "invoice_agent", "pay_invoice", "daily", "agent"
            )
            assert key == "agg:proj-123:invoice_agent:pay_invoice:20240115"

    def test_cache_key_scope_action(self):
        """Action scope includes project, action, and window (no agent)."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch.object(service, "_get_window_start") as mock_window:
            mock_window.return_value = datetime(2024, 1, 15, 0, 0, 0)
            key = service._build_cache_key(
                "proj-123", "invoice_agent", "pay_invoice", "daily", "action"
            )
            assert key == "agg:proj-123:pay_invoice:20240115"

    def test_cache_key_scope_project(self):
        """Project scope includes only project and window."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch.object(service, "_get_window_start") as mock_window:
            mock_window.return_value = datetime(2024, 1, 15, 0, 0, 0)
            key = service._build_cache_key(
                "proj-123", "invoice_agent", "pay_invoice", "daily", "project"
            )
            assert key == "agg:proj-123:20240115"

    def test_cache_key_hourly_includes_hour(self):
        """Hourly window key includes hour precision."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())

        with patch.object(service, "_get_window_start") as mock_window:
            mock_window.return_value = datetime(2024, 1, 15, 14, 0, 0)
            key = service._build_cache_key(
                "proj-123", "agent", "action", "hourly", "agent"
            )
            assert "2024011514" in key


class TestAggregateServiceParamExtraction:
    """Tests for parameter value extraction."""

    def test_extract_param_path_simple(self):
        """Extract simple param like 'amount'."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())
        result = service._extract_param_value('{"amount": 100.50}', "amount")
        assert result == 100.50

    def test_extract_param_path_nested(self):
        """Extract nested param like 'data.amount'."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())
        result = service._extract_param_value(
            '{"data": {"amount": 250.00}}', "data.amount"
        )
        assert result == 250.00

    def test_extract_param_path_deeply_nested(self):
        """Extract deeply nested param."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())
        result = service._extract_param_value(
            '{"invoice": {"payment": {"amount": 999.99}}}',
            "invoice.payment.amount"
        )
        assert result == 999.99

    def test_extract_param_path_missing_returns_none(self):
        """Missing param path returns None."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())
        result = service._extract_param_value('{"amount": 100}', "missing")
        assert result is None

    def test_extract_param_path_invalid_json_returns_none(self):
        """Invalid JSON returns None."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())
        result = service._extract_param_value("not valid json", "amount")
        assert result is None

    def test_extract_param_path_non_numeric_returns_none(self):
        """Non-numeric value returns None."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())
        result = service._extract_param_value('{"amount": "not a number"}', "amount")
        assert result is None

    def test_extract_param_path_from_dict(self):
        """Can extract from dict (not just JSON string)."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())
        result = service._extract_param_value({"amount": 500}, "amount")
        assert result == 500.0

    def test_extract_param_path_integer_converts_to_float(self):
        """Integer values are converted to float."""
        from server.services.aggregate import AggregateService

        service = AggregateService(MagicMock())
        result = service._extract_param_value('{"count": 42}', "count")
        assert result == 42.0
        assert isinstance(result, float)


class TestAggregateServiceGetTotal:
    """Tests for get_current_total method."""

    @pytest.mark.asyncio
    async def test_get_total_uses_cache_when_available(self):
        """Uses cached value when available."""
        from server.services.aggregate import AggregateService

        mock_db = MagicMock()
        service = AggregateService(mock_db)

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value="12345.67")

        with patch.object(service, "cache", mock_cache):
            result = await service.get_current_total(
                "proj-123", "agent", "action",
                {"window": "daily", "scope": "agent"}
            )
            assert result == 12345.67
            mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_total_calculates_from_db_on_cache_miss(self):
        """Calculates from DB when cache misses."""
        from server.services.aggregate import AggregateService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = AggregateService(mock_db)

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)

        with patch.object(service, "cache", mock_cache):
            result = await service.get_current_total(
                "proj-123", "agent", "action",
                {"window": "daily", "scope": "agent"}
            )
            assert result == 0.0
            mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_total_rolling_window_skips_cache(self):
        """Rolling windows skip cache for accuracy."""
        from server.services.aggregate import AggregateService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = AggregateService(mock_db)

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value="100")  # Even with cached value

        with patch.object(service, "cache", mock_cache):
            result = await service.get_current_total(
                "proj-123", "agent", "action",
                {"window": "rolling_hours:24", "scope": "agent"}
            )
            # Should query DB even though cache has value
            mock_db.execute.assert_called_once()


class TestAggregateServiceCalculateFromDb:
    """Tests for database calculation."""

    @pytest.mark.asyncio
    async def test_calculate_count_measure(self):
        """Count measure returns number of logs."""
        from server.services.aggregate import AggregateService
        from server.models.audit_log import AuditLog

        mock_db = AsyncMock()

        # Create mock audit logs
        mock_logs = [MagicMock(), MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = AggregateService(mock_db)

        result = await service._calculate_from_db(
            "proj-123", "agent", "action",
            datetime.utcnow(), "agent", "amount", "count"
        )
        assert result == 3.0

    @pytest.mark.asyncio
    async def test_calculate_sum_measure(self):
        """Sum measure returns sum of param values."""
        from server.services.aggregate import AggregateService

        mock_db = AsyncMock()

        # Create mock audit logs with params
        mock_log1 = MagicMock()
        mock_log1.params = '{"amount": 100}'
        mock_log2 = MagicMock()
        mock_log2.params = '{"amount": 250}'
        mock_log3 = MagicMock()
        mock_log3.params = '{"amount": 150}'

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            mock_log1, mock_log2, mock_log3
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = AggregateService(mock_db)

        result = await service._calculate_from_db(
            "proj-123", "agent", "action",
            datetime.utcnow(), "agent", "amount", "sum"
        )
        assert result == 500.0

    @pytest.mark.asyncio
    async def test_calculate_sum_ignores_missing_values(self):
        """Sum ignores logs with missing param values."""
        from server.services.aggregate import AggregateService

        mock_db = AsyncMock()

        mock_log1 = MagicMock()
        mock_log1.params = '{"amount": 100}'
        mock_log2 = MagicMock()
        mock_log2.params = '{"other": "value"}'  # Missing amount
        mock_log3 = MagicMock()
        mock_log3.params = '{"amount": 200}'

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            mock_log1, mock_log2, mock_log3
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = AggregateService(mock_db)

        result = await service._calculate_from_db(
            "proj-123", "agent", "action",
            datetime.utcnow(), "agent", "amount", "sum"
        )
        assert result == 300.0


class TestAggregateServiceInvalidateCache:
    """Tests for cache invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_cache_deletes_pattern(self):
        """Invalidate deletes all project aggregate keys."""
        from server.services.aggregate import AggregateService

        mock_db = MagicMock()
        service = AggregateService(mock_db)

        mock_cache = AsyncMock()
        mock_cache.delete_pattern = AsyncMock(return_value=5)

        with patch.object(service, "cache", mock_cache):
            await service.invalidate_cache("proj-123", "agent", "action")
            mock_cache.delete_pattern.assert_called_once_with("agg:proj-123:*")


class TestValidatorAggregateLimitCheck:
    """Tests for aggregate limit checking in ValidatorService."""

    def test_extract_param_value_simple(self):
        """ValidatorService can extract simple param values."""
        from server.services.validator import ValidatorService

        service = ValidatorService(MagicMock())
        result = service._extract_param_value({"amount": 100}, "amount")
        assert result == 100.0

    def test_extract_param_value_nested(self):
        """ValidatorService can extract nested param values."""
        from server.services.validator import ValidatorService

        service = ValidatorService(MagicMock())
        result = service._extract_param_value(
            {"invoice": {"amount": 500}}, "invoice.amount"
        )
        assert result == 500.0

    def test_extract_param_value_missing(self):
        """ValidatorService returns None for missing params."""
        from server.services.validator import ValidatorService

        service = ValidatorService(MagicMock())
        result = service._extract_param_value({"other": 100}, "amount")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_aggregate_limits_no_limits(self):
        """Returns allowed when no aggregate limits configured."""
        from server.services.validator import ValidatorService

        mock_db = MagicMock()
        service = ValidatorService(mock_db)

        policy_json = json.dumps({
            "version": "1.0",
            "default": "allow",
            "rules": [{"action_type": "pay_invoice"}]
        })

        result = await service._check_aggregate_limits(
            policy_json, "proj-123", "agent", "pay_invoice", {"amount": 100}
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_aggregate_limits_under_limit(self):
        """Returns allowed when under aggregate limit."""
        from server.services.validator import ValidatorService

        mock_db = MagicMock()
        service = ValidatorService(mock_db)

        # Mock aggregate service to return 0 (no previous actions)
        mock_agg = AsyncMock()
        mock_agg.get_current_total = AsyncMock(return_value=0)
        service.aggregate_service = mock_agg

        policy_json = json.dumps({
            "version": "1.0",
            "default": "allow",
            "rules": [{
                "action_type": "pay_invoice",
                "aggregate_limit": {
                    "max_value": 1000,
                    "window": "daily",
                    "param_path": "amount"
                }
            }]
        })

        result = await service._check_aggregate_limits(
            policy_json, "proj-123", "agent", "pay_invoice", {"amount": 100}
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_aggregate_limits_exceeds_limit(self):
        """Returns blocked when exceeds aggregate limit."""
        from server.services.validator import ValidatorService

        mock_db = MagicMock()
        service = ValidatorService(mock_db)

        # Mock aggregate service to return 950 (near limit)
        mock_agg = AsyncMock()
        mock_agg.get_current_total = AsyncMock(return_value=950)
        service.aggregate_service = mock_agg

        policy_json = json.dumps({
            "version": "1.0",
            "default": "allow",
            "rules": [{
                "action_type": "pay_invoice",
                "aggregate_limit": {
                    "max_value": 1000,
                    "window": "daily",
                    "param_path": "amount"
                }
            }]
        })

        result = await service._check_aggregate_limits(
            policy_json, "proj-123", "agent", "pay_invoice", {"amount": 100}
        )
        assert result.allowed is False
        assert "Aggregate limit exceeded" in result.reason
        assert "1050.00 > 1000.00" in result.reason

    @pytest.mark.asyncio
    async def test_check_aggregate_limits_count_measure(self):
        """Count measure adds 1 instead of param value."""
        from server.services.validator import ValidatorService

        mock_db = MagicMock()
        service = ValidatorService(mock_db)

        # Mock aggregate service to return 99 actions
        mock_agg = AsyncMock()
        mock_agg.get_current_total = AsyncMock(return_value=99)
        service.aggregate_service = mock_agg

        policy_json = json.dumps({
            "version": "1.0",
            "default": "allow",
            "rules": [{
                "action_type": "send_email",
                "aggregate_limit": {
                    "max_value": 100,
                    "window": "hourly",
                    "measure": "count"
                }
            }]
        })

        # Should allow (99 + 1 = 100, equal to limit)
        result = await service._check_aggregate_limits(
            policy_json, "proj-123", "agent", "send_email", {}
        )
        assert result.allowed is True

        # Now at limit, next should block
        mock_agg.get_current_total = AsyncMock(return_value=100)
        result = await service._check_aggregate_limits(
            policy_json, "proj-123", "agent", "send_email", {}
        )
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_check_aggregate_limits_wildcard_rule(self):
        """Wildcard rules apply to all action types."""
        from server.services.validator import ValidatorService

        mock_db = MagicMock()
        service = ValidatorService(mock_db)

        mock_agg = AsyncMock()
        mock_agg.get_current_total = AsyncMock(return_value=500)
        service.aggregate_service = mock_agg

        policy_json = json.dumps({
            "version": "1.0",
            "default": "allow",
            "rules": [{
                "action_type": "*",
                "aggregate_limit": {
                    "max_value": 1000,
                    "window": "daily",
                    "param_path": "amount"
                }
            }]
        })

        result = await service._check_aggregate_limits(
            policy_json, "proj-123", "agent", "any_action", {"amount": 600}
        )
        assert result.allowed is False


class TestPolicyRuleSchema:
    """Tests for PolicyRule schema with aggregate_limit."""

    def test_policy_rule_accepts_aggregate_limit(self):
        """PolicyRule schema accepts aggregate_limit field."""
        from server.schemas.policy import PolicyRule

        rule = PolicyRule(
            action_type="pay_invoice",
            aggregate_limit={
                "max_value": 50000,
                "window": "daily",
                "param_path": "amount",
                "measure": "sum",
                "scope": "agent"
            }
        )
        assert rule.aggregate_limit is not None
        assert rule.aggregate_limit["max_value"] == 50000
        assert rule.aggregate_limit["window"] == "daily"

    def test_policy_rule_aggregate_limit_optional(self):
        """aggregate_limit is optional in PolicyRule."""
        from server.schemas.policy import PolicyRule

        rule = PolicyRule(action_type="pay_invoice")
        assert rule.aggregate_limit is None

    def test_policy_create_with_aggregate_limit(self):
        """PolicyCreate accepts rules with aggregate_limit."""
        from server.schemas.policy import PolicyCreate

        policy = PolicyCreate(
            name="test-policy",
            rules=[
                {
                    "action_type": "pay_invoice",
                    "aggregate_limit": {
                        "max_value": 10000,
                        "window": "daily"
                    }
                }
            ]
        )
        assert len(policy.rules) == 1
        assert policy.rules[0].aggregate_limit["max_value"] == 10000
