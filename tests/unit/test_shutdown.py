"""Unit tests for graceful shutdown module."""

import pytest

from server.shutdown import (
    is_shutting_down,
    set_shutting_down,
    reset_shutdown_state,
)


class TestShutdownState:
    """Test shutdown state management."""

    def setup_method(self):
        """Reset shutdown state before each test."""
        reset_shutdown_state()

    def teardown_method(self):
        """Reset shutdown state after each test."""
        reset_shutdown_state()

    def test_initial_state_not_shutting_down(self):
        """Initially, the server should not be shutting down."""
        assert is_shutting_down() is False

    def test_set_shutting_down_changes_state(self):
        """set_shutting_down should mark server as shutting down."""
        assert is_shutting_down() is False
        set_shutting_down()
        assert is_shutting_down() is True

    def test_reset_shutdown_state_clears_state(self):
        """reset_shutdown_state should clear the shutting down flag."""
        set_shutting_down()
        assert is_shutting_down() is True
        reset_shutdown_state()
        assert is_shutting_down() is False

    def test_multiple_set_calls_are_idempotent(self):
        """Multiple calls to set_shutting_down should be safe."""
        set_shutting_down()
        set_shutting_down()
        set_shutting_down()
        assert is_shutting_down() is True

    def test_state_persists_across_calls(self):
        """Shutdown state should persist until reset."""
        set_shutting_down()
        # Multiple checks should all return True
        assert is_shutting_down() is True
        assert is_shutting_down() is True
        assert is_shutting_down() is True
