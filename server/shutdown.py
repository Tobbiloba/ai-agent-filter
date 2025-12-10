"""Graceful shutdown state management."""

import logging

logger = logging.getLogger(__name__)

_shutting_down: bool = False


def is_shutting_down() -> bool:
    """Check if shutdown is in progress."""
    return _shutting_down


def set_shutting_down() -> None:
    """Mark server as shutting down."""
    global _shutting_down
    _shutting_down = True
    logger.info("Graceful shutdown initiated")


def reset_shutdown_state() -> None:
    """Reset shutdown state. Used for testing."""
    global _shutting_down
    _shutting_down = False
