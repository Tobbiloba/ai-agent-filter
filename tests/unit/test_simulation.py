"""
Unit tests for policy simulation (what-if mode).

Tests that simulation mode:
- Returns correct validation results
- Does NOT create audit log entries
- Does NOT invalidate caches
- Does NOT trigger webhooks
- Returns simulated=True in response
- Returns action_id=None for simulations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.services.validator import ValidatorService, ActionValidationResult
from server.services.policy_engine import ValidationResult


class TestSimulationMode:
    """Unit tests for simulation mode in ValidatorService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def validator(self, mock_db):
        """Create a ValidatorService with mocked dependencies."""
        return ValidatorService(mock_db)

    @pytest.mark.asyncio
    async def test_simulation_returns_simulated_true(self, validator, mock_db):
        """Simulation should return simulated=True in result."""
        # Mock policy lookup
        with patch.object(validator, '_get_active_policy', return_value=None):
            result = await validator.validate_action(
                project_id="test-project",
                agent_name="test-agent",
                action_type="test-action",
                params={},
                simulate=True,
            )

        assert result.simulated is True

    @pytest.mark.asyncio
    async def test_simulation_returns_none_action_id(self, validator, mock_db):
        """Simulation should return action_id=None."""
        with patch.object(validator, '_get_active_policy', return_value=None):
            result = await validator.validate_action(
                project_id="test-project",
                agent_name="test-agent",
                action_type="test-action",
                params={},
                simulate=True,
            )

        assert result.action_id is None

    @pytest.mark.asyncio
    async def test_simulation_does_not_create_audit_log(self, validator, mock_db):
        """Simulation should NOT add audit log to database."""
        with patch.object(validator, '_get_active_policy', return_value=None):
            await validator.validate_action(
                project_id="test-project",
                agent_name="test-agent",
                action_type="test-action",
                params={},
                simulate=True,
            )

        # db.add should not be called for simulations
        mock_db.add.assert_not_called()
        mock_db.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_simulation_does_not_invalidate_cache(self, validator, mock_db):
        """Simulation should NOT invalidate aggregate cache."""
        with patch.object(validator, '_get_active_policy', return_value=None):
            with patch.object(
                validator.aggregate_service, 'invalidate_cache', new_callable=AsyncMock
            ) as mock_invalidate:
                await validator.validate_action(
                    project_id="test-project",
                    agent_name="test-agent",
                    action_type="test-action",
                    params={},
                    simulate=True,
                )

                mock_invalidate.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_simulation_creates_audit_log(self, validator, mock_db):
        """Non-simulation should create audit log."""
        # Create a mock audit log with action_id
        mock_audit_log = MagicMock()
        mock_audit_log.action_id = "act_123"
        mock_audit_log.timestamp = MagicMock()

        with patch.object(validator, '_get_active_policy', return_value=None):
            with patch('server.services.validator.AuditLog', return_value=mock_audit_log):
                await validator.validate_action(
                    project_id="test-project",
                    agent_name="test-agent",
                    action_type="test-action",
                    params={},
                    simulate=False,
                )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_simulation_returns_simulated_false(self, validator, mock_db):
        """Non-simulation should return simulated=False."""
        mock_audit_log = MagicMock()
        mock_audit_log.action_id = "act_123"
        mock_audit_log.timestamp = MagicMock()

        with patch.object(validator, '_get_active_policy', return_value=None):
            with patch('server.services.validator.AuditLog', return_value=mock_audit_log):
                result = await validator.validate_action(
                    project_id="test-project",
                    agent_name="test-agent",
                    action_type="test-action",
                    params={},
                    simulate=False,
                )

        assert result.simulated is False

    @pytest.mark.asyncio
    async def test_simulation_validates_policy_correctly(self, validator, mock_db):
        """Simulation should still validate against policy rules."""
        # Create a mock policy that blocks the action
        mock_policy = MagicMock()
        mock_policy.version = "1.0"
        mock_policy.rules = json.dumps({
            "default": "block",
            "rules": [
                {
                    "action_type": "test-action",
                    "constraints": {
                        "params.amount": {"max": 100}
                    }
                }
            ]
        })

        with patch.object(validator, '_get_active_policy', return_value=mock_policy):
            # Test with amount exceeding limit
            result = await validator.validate_action(
                project_id="test-project",
                agent_name="test-agent",
                action_type="test-action",
                params={"amount": 200},  # Exceeds max of 100
                simulate=True,
            )

        assert result.allowed is False
        assert result.simulated is True
        assert "exceeds maximum" in result.reason

    @pytest.mark.asyncio
    async def test_simulation_allowed_action(self, validator, mock_db):
        """Simulation should correctly identify allowed actions."""
        mock_policy = MagicMock()
        mock_policy.version = "1.0"
        mock_policy.rules = json.dumps({
            "default": "allow",
            "rules": []
        })

        with patch.object(validator, '_get_active_policy', return_value=mock_policy):
            result = await validator.validate_action(
                project_id="test-project",
                agent_name="test-agent",
                action_type="test-action",
                params={},
                simulate=True,
            )

        assert result.allowed is True
        assert result.simulated is True


class TestActionValidationResultDataclass:
    """Tests for ActionValidationResult dataclass."""

    def test_to_dict_includes_simulated(self):
        """to_dict should include simulated field."""
        result = ActionValidationResult(
            allowed=True,
            action_id=None,
            reason=None,
            simulated=True,
        )
        data = result.to_dict()
        assert data["simulated"] is True

    def test_to_dict_simulated_false(self):
        """to_dict should include simulated=False for non-simulations."""
        result = ActionValidationResult(
            allowed=True,
            action_id="act_123",
            reason=None,
            simulated=False,
        )
        data = result.to_dict()
        assert data["simulated"] is False
        assert data["action_id"] == "act_123"
