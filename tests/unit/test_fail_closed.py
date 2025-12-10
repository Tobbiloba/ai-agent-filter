"""Unit tests for fail-closed mode functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from server.config import Settings


class TestFailClosedConfig:
    """Test fail-closed configuration settings."""

    def test_fail_closed_default_disabled(self):
        """Fail-closed should be disabled by default."""
        settings = Settings()
        assert settings.fail_closed is False

    def test_fail_closed_default_reason(self):
        """Default reason message should be set."""
        settings = Settings()
        assert settings.fail_closed_reason == "Service unavailable - fail-closed mode active"

    def test_fail_closed_can_be_enabled(self):
        """Fail-closed can be enabled via settings."""
        settings = Settings(fail_closed=True)
        assert settings.fail_closed is True

    def test_fail_closed_custom_reason(self):
        """Custom reason message can be set."""
        custom_reason = "Security mode: service temporarily unavailable"
        settings = Settings(fail_closed_reason=custom_reason)
        assert settings.fail_closed_reason == custom_reason


class TestFailClosedEndpoint:
    """Test fail-closed behavior in validation endpoint."""

    @pytest.fixture
    def mock_settings_fail_closed_enabled(self):
        """Mock settings with fail-closed enabled."""
        return Settings(fail_closed=True)

    @pytest.fixture
    def mock_settings_fail_closed_disabled(self):
        """Mock settings with fail-closed disabled."""
        return Settings(fail_closed=False)

    @pytest.mark.asyncio
    async def test_fail_closed_disabled_raises_on_error(self):
        """When fail-closed is disabled, errors should propagate."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=False)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Database error")
                )

                with pytest.raises(Exception, match="Database error"):
                    await validate_action(request, mock_background_tasks, mock_db, mock_project)

    @pytest.mark.asyncio
    async def test_fail_closed_enabled_blocks_on_error(self):
        """When fail-closed is enabled, errors should return blocked response."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Database error")
                )

                response = await validate_action(request, mock_background_tasks, mock_db, mock_project)

                assert response.allowed is False
                assert response.action_id.startswith("fail-closed-")
                assert response.reason == "Service unavailable - fail-closed mode active"

    @pytest.mark.asyncio
    async def test_fail_closed_custom_reason_in_response(self):
        """Custom reason should appear in fail-closed response."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        custom_reason = "Custom security message"
        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(
                fail_closed=True,
                fail_closed_reason=custom_reason
            )

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Error")
                )

                response = await validate_action(request, mock_background_tasks, mock_db, mock_project)

                assert response.reason == custom_reason

    @pytest.mark.asyncio
    async def test_fail_closed_response_has_timestamp(self):
        """Fail-closed response should include timestamp."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest
        from datetime import datetime

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Error")
                )

                response = await validate_action(request, mock_background_tasks, mock_db, mock_project)

                assert response.timestamp is not None
                assert isinstance(response.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_fail_closed_action_id_format(self):
        """Fail-closed action_id should follow expected format."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Error")
                )

                response = await validate_action(request, mock_background_tasks, mock_db, mock_project)

                # Format: fail-closed-{8 hex chars}
                assert response.action_id.startswith("fail-closed-")
                hex_part = response.action_id.split("-")[-1]
                assert len(hex_part) == 8
                # Verify it's valid hex
                int(hex_part, 16)

    @pytest.mark.asyncio
    async def test_normal_operation_unaffected_when_fail_closed_enabled(self):
        """Normal successful validation should work when fail-closed is enabled."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest
        from server.services.validator import ActionValidationResult
        from datetime import datetime

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_project.webhook_enabled = False
        mock_project.webhook_url = None
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        mock_result = ActionValidationResult(
            allowed=True,
            action_id="test-action-123",
            timestamp=datetime.utcnow(),
            execution_time_ms=5
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    return_value=mock_result
                )

                with patch("server.routes.validate.record_validation_metrics"):
                    response = await validate_action(request, mock_background_tasks, mock_db, mock_project)

                assert response.allowed is True
                assert response.action_id == "test-action-123"


class TestFailClosedWithDifferentErrors:
    """Test fail-closed handles various error types."""

    @pytest.mark.asyncio
    async def test_fail_closed_on_db_connection_error(self):
        """Fail-closed should trigger on database connection errors."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest
        from sqlalchemy.exc import OperationalError

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=OperationalError("statement", {}, Exception("Connection refused"))
                )

                response = await validate_action(request, mock_background_tasks, mock_db, mock_project)

                assert response.allowed is False
                assert "fail-closed" in response.action_id

    @pytest.mark.asyncio
    async def test_fail_closed_on_timeout_error(self):
        """Fail-closed should trigger on timeout errors."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest
        import asyncio

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=asyncio.TimeoutError("Query timeout")
                )

                response = await validate_action(request, mock_background_tasks, mock_db, mock_project)

                assert response.allowed is False

    @pytest.mark.asyncio
    async def test_fail_closed_on_unexpected_error(self):
        """Fail-closed should trigger on any unexpected error."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=RuntimeError("Unexpected internal error")
                )

                response = await validate_action(request, mock_background_tasks, mock_db, mock_project)

                assert response.allowed is False


class TestFailClosedHTTPExceptionHandling:
    """Test that HTTPExceptions are NOT caught by fail-closed."""

    @pytest.mark.asyncio
    async def test_http_exception_not_caught_by_fail_closed(self):
        """HTTPException should propagate even when fail-closed is enabled."""
        from fastapi import HTTPException
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                # Simulate an HTTPException being raised from within the validator
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=HTTPException(status_code=403, detail="Forbidden")
                )

                # HTTPException should NOT be caught by fail-closed
                with pytest.raises(HTTPException) as exc_info:
                    await validate_action(request, mock_background_tasks, mock_db, mock_project)

                assert exc_info.value.status_code == 403
                assert exc_info.value.detail == "Forbidden"

    @pytest.mark.asyncio
    async def test_project_id_mismatch_raises_403_not_fail_closed(self):
        """Project ID mismatch should raise 403, not trigger fail-closed."""
        from fastapi import HTTPException
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "project-A"  # Different from request
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="project-B",  # Mismatched
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            # Should raise HTTPException, not return fail-closed response
            with pytest.raises(HTTPException) as exc_info:
                await validate_action(request, mock_background_tasks, mock_db, mock_project)

            assert exc_info.value.status_code == 403
            assert "project" in exc_info.value.detail.lower()


class TestFailClosedActionIdUniqueness:
    """Test that fail-closed action IDs are unique."""

    @pytest.mark.asyncio
    async def test_action_ids_are_unique_across_calls(self):
        """Multiple fail-closed responses should have unique action_ids."""
        from server.routes.validate import validate_action
        from server.schemas import ActionRequest

        mock_db = AsyncMock()
        mock_project = MagicMock()
        mock_project.id = "test-project"
        mock_background_tasks = MagicMock(spec=BackgroundTasks)

        request = ActionRequest(
            project_id="test-project",
            agent_name="test-agent",
            action_type="test-action",
            params={}
        )

        action_ids = set()

        with patch("server.routes.validate.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Error")
                )

                # Make 100 calls and collect action_ids
                for _ in range(100):
                    response = await validate_action(request, mock_background_tasks, mock_db, mock_project)
                    action_ids.add(response.action_id)

        # All 100 should be unique
        assert len(action_ids) == 100
