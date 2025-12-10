"""Structured JSON logging configuration with correlation ID support."""

import logging
import sys
from contextvars import ContextVar
from typing import Optional

from pythonjsonlogger.json import JsonFormatter as BaseJsonFormatter

# Context variable for correlation ID - thread-safe for async operations
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation_id to all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id attribute to the log record."""
        record.correlation_id = correlation_id.get()
        return True


class CustomJsonFormatter(BaseJsonFormatter):
    """Custom JSON formatter with consistent field naming."""

    def add_fields(
        self,
        log_record: dict,
        record: logging.LogRecord,
        message_dict: dict,
    ) -> None:
        """Add custom fields to the JSON log record."""
        super().add_fields(log_record, record, message_dict)

        # Rename fields for consistency with log aggregators
        if "asctime" in log_record:
            log_record["timestamp"] = log_record.pop("asctime")
        if "levelname" in log_record:
            log_record["level"] = log_record.pop("levelname")

        # Ensure correlation_id is always present
        if "correlation_id" not in log_record:
            log_record["correlation_id"] = correlation_id.get()


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    logger_name: Optional[str] = None,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, output JSON; if False, output human-readable format
        logger_name: If provided, configure only this logger; otherwise configure root
    """
    # Get the target logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level.upper())

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level.upper())

    if json_format:
        # JSON format for production - compatible with ELK, Datadog, Splunk
        formatter = CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())
    logger.addHandler(handler)

    # Prevent propagation to root logger if configuring a specific logger
    if logger_name:
        logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the correlation ID filter.

    This is a convenience function to get loggers that will
    automatically include the correlation ID in their output.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
