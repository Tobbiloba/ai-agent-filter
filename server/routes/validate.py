"""Validation endpoint - the core action validation API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.middleware.auth import get_project_by_api_key
from server.models import Project
from server.schemas import ActionRequest, ActionResponse
from server.services import ValidatorService

router = APIRouter(tags=["Validation"])


@router.post("/validate_action", response_model=ActionResponse)
async def validate_action(
    request: ActionRequest,
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
    # Verify the project_id in request matches the authenticated project
    if request.project_id != project.id:
        raise HTTPException(
            status_code=403,
            detail=f"API key is for project '{project.id}', not '{request.project_id}'",
        )

    validator = ValidatorService(db)
    result = await validator.validate_action(
        project_id=request.project_id,
        agent_name=request.agent_name,
        action_type=request.action_type,
        params=request.params,
    )

    return ActionResponse(
        allowed=result.allowed,
        action_id=result.action_id,
        timestamp=result.timestamp,
        reason=result.reason,
        execution_time_ms=result.execution_time_ms,
    )
