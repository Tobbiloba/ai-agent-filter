"""Unit tests for structured logging module."""

import json
import logging
import io

import pytest
from pythonjsonlogger.json import JsonFormatter as BaseJsonFormatter

from server.logging_config import (
    correlation_id,
    CorrelationIdFilter,
    CustomJsonFormatter,
    setup_logging,
    get_logger,
)


class TestCorrelationIdContextVar:
    """Test correlation ID context variable."""

    def test_default_value(self):
        """Default correlation ID should be '-'."""
        # Reset to default
        token = correlation_id.set("-")
        correlation_id.reset(token)
        assert correlation_id.get() == "-"

    def test_set_and_get(self):
        """Should be able to set and get correlation ID."""
        token = correlation_id.set("test-123")
        try:
            assert correlation_id.get() == "test-123"
        finally:
            correlation_id.reset(token)

    def test_reset_restores_previous(self):
        """Reset should restore the previous value."""
        original = correlation_id.get()
        token = correlation_id.set("new-value")
        correlation_id.reset(token)
        assert correlation_id.get() == original


class TestCorrelationIdFilter:
    """Test the correlation ID logging filter."""

    def test_adds_correlation_id_to_record(self):
        """Filter should add correlation_id attribute to log records."""
        filter_instance = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        token = correlation_id.set("filter-test-123")
        try:
            result = filter_instance.filter(record)
            assert result is True
            assert hasattr(record, "correlation_id")
            assert record.correlation_id == "filter-test-123"
        finally:
            correlation_id.reset(token)

    def test_filter_always_returns_true(self):
        """Filter should always return True (don't suppress logs)."""
        filter_instance = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is True


class TestCustomJsonFormatter:
    """Test the custom JSON formatter."""

    def test_produces_valid_json(self):
        """Formatter should produce valid JSON."""
        formatter = CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "json-test-123"

        output = formatter.format(record)
        # Should be valid JSON
        parsed = json.loads(output)
        assert "message" in parsed
        assert parsed["message"] == "test message"

    def test_renames_timestamp_field(self):
        """Should rename asctime to timestamp."""
        formatter = CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test"

        output = formatter.format(record)
        parsed = json.loads(output)
        assert "timestamp" in parsed
        assert "asctime" not in parsed

    def test_renames_level_field(self):
        """Should rename levelname to level."""
        formatter = CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test"

        output = formatter.format(record)
        parsed = json.loads(output)
        assert "level" in parsed
        assert parsed["level"] == "WARNING"
        assert "levelname" not in parsed

    def test_includes_correlation_id(self):
        """Should include correlation_id in output."""
        formatter = CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(correlation_id)s %(message)s"
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "corr-456"

        output = formatter.format(record)
        parsed = json.loads(output)
        assert "correlation_id" in parsed
        assert parsed["correlation_id"] == "corr-456"

    def test_includes_extra_fields(self):
        """Should include extra fields from log record."""
        formatter = CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(message)s"
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "test"
        record.custom_field = "custom_value"
        record.method = "POST"
        record.status_code = 200

        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed.get("custom_field") == "custom_value"
        assert parsed.get("method") == "POST"
        assert parsed.get("status_code") == 200


class TestSetupLogging:
    """Test the setup_logging function."""

    def test_configures_root_logger(self):
        """Should configure the root logger by default."""
        setup_logging(log_level="DEBUG", json_format=True)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) > 0

    def test_json_format_uses_json_formatter(self):
        """Should use JSON formatter when json_format=True."""
        setup_logging(log_level="INFO", json_format=True)
        root = logging.getLogger()
        handler = root.handlers[0]
        assert isinstance(handler.formatter, CustomJsonFormatter)

    def test_non_json_format_uses_standard_formatter(self):
        """Should use standard formatter when json_format=False."""
        setup_logging(log_level="INFO", json_format=False)
        root = logging.getLogger()
        handler = root.handlers[0]
        assert isinstance(handler.formatter, logging.Formatter)
        assert not isinstance(handler.formatter, CustomJsonFormatter)

    def test_adds_correlation_filter(self):
        """Should add CorrelationIdFilter to handler."""
        setup_logging(log_level="INFO", json_format=True)
        root = logging.getLogger()
        handler = root.handlers[0]
        filters = handler.filters
        assert any(isinstance(f, CorrelationIdFilter) for f in filters)

    def test_clears_existing_handlers(self):
        """Should clear existing handlers before adding new one."""
        # Add some handlers first
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())
        initial_count = len(root.handlers)

        setup_logging(log_level="INFO", json_format=True)
        # Should have exactly 1 handler after setup
        assert len(root.handlers) == 1

    def test_named_logger_configuration(self):
        """Should configure specific logger when name provided."""
        setup_logging(log_level="WARNING", json_format=True, logger_name="test.specific")
        logger = logging.getLogger("test.specific")
        assert logger.level == logging.WARNING
        assert len(logger.handlers) == 1
        assert logger.propagate is False


class TestGetLogger:
    """Test the get_logger convenience function."""

    def test_returns_logger(self):
        """Should return a logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_same_name_returns_same_logger(self):
        """Same name should return the same logger instance."""
        logger1 = get_logger("same.logger")
        logger2 = get_logger("same.logger")
        assert logger1 is logger2


class TestLogOutputIntegration:
    """Integration tests for actual log output."""

    def test_json_log_output_is_parseable(self):
        """Logged messages should produce parseable JSON."""
        # Set up a string stream to capture output
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(CorrelationIdFilter())

        logger = logging.getLogger("test.json.output")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        token = correlation_id.set("integration-test-abc")
        try:
            logger.info("Test log message", extra={"key": "value"})
        finally:
            correlation_id.reset(token)

        output = stream.getvalue()
        parsed = json.loads(output)

        assert parsed["message"] == "Test log message"
        assert parsed["correlation_id"] == "integration-test-abc"
        assert parsed["key"] == "value"
        assert "timestamp" in parsed
        assert parsed["level"] == "INFO"
