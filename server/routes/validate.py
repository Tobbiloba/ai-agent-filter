"""Validation endpoint - the core action validation API."""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import get_settings
from server.database import get_db
from server.metrics import record_validation_metrics
from server.middleware.auth import get_project_by_api_key
from server.models import Project
from server.schemas import ActionRequest, ActionResponse
from server.services import ValidatorService
from server.services.webhook import get_webhook_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Validation"])


@router.post("/validate_action", response_model=ActionResponse)
async def validate_action(
    request: ActionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_project_by_api_key),
):
    """
    Validate an AI agent action against the project's policy.

    This is the main endpoint for the firewall. Call this before executing
    any agent action to check if it's allowed.

    Returns:
    - **allowed**: True if the action can proceed, False if blocked
    - **action_id**: Unique identifier for this validation (for audit purposes)
    - **reason**: Explanation if the action was blocked
    """
    settings = get_settings()

    # Verify the project_id in request matches the authenticated project
    if request.project_id != project.id:
        raise HTTPException(
            status_code=403,
            detail=f"API key is for project '{project.id}', not '{request.project_id}'",
        )

    try:
        validator = ValidatorService(db)
        result = await validator.validate_action(
            project_id=request.project_id,
            agent_name=request.agent_name,
            action_type=request.action_type,
            params=request.params,
        )
    except HTTPException:
        # Don't catch HTTP exceptions - these are intentional responses (401, 403, etc.)
        raise
    except Exception as e:
        # Fail-closed mode: block action on any service error
        if settings.fail_closed:
            logger.error(f"Fail-closed: blocking action due to error: {e}")
            return ActionResponse(
                allowed=False,
                action_id=f"fail-closed-{uuid.uuid4().hex[:8]}",
                timestamp=datetime.utcnow(),
                reason=settings.fail_closed_reason,
            )
        # Default: re-raise exception (fail-open)
        raise

    # Record validation metrics
    record_validation_metrics(
        project_id=request.project_id,
        allowed=result.allowed,
        duration_ms=result.execution_time_ms or 0,
    )

    # Send webhook if action blocked and webhook configured
    if not result.allowed and project.webhook_enabled and project.webhook_url:
        webhook_service = get_webhook_service()
        background_tasks.add_task(
            webhook_service.send_blocked_action_webhook,
            webhook_url=project.webhook_url,
            action_id=result.action_id,
            project_id=request.project_id,
            agent_name=request.agent_name,
            action_type=request.action_type,
            params=request.params,
            reason=result.reason or "Action blocked by policy",
        )

    return ActionResponse(
        allowed=result.allowed,
        action_id=result.action_id,
        timestamp=result.timestamp,
        reason=result.reason,
        execution_time_ms=result.execution_time_ms,
    )
