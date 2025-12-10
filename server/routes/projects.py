"""Project management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.middleware.auth import get_project_by_api_key
from server.models import Project
from server.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from server.errors import ErrorCode, make_error

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project.

    Returns the project details including the generated API key.
    **Important**: Store the API key securely - it cannot be retrieved again.
    """
    # Check if project ID already exists
    stmt = select(Project).where(Project.id == project_data.id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=make_error(ErrorCode.PROJECT_EXISTS),
        )

    # Create project
    project = Project(
        id=project_data.id,
        name=project_data.name,
        webhook_url=project_data.webhook_url,
        webhook_enabled=project_data.webhook_enabled,
    )
    db.add(project)
    await db.flush()

    return ProjectResponse(
        id=project.id,
        name=project.name,
        api_key=project.api_key,
        is_active=project.is_active,
        webhook_url=project.webhook_url,
        webhook_enabled=project.webhook_enabled,
        created_at=project.created_at,
    )


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get project details (without full API key).

    Use this to verify a project exists and check its status.
    """
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=404,
            detail=make_error(ErrorCode.PROJECT_NOT_FOUND),
        )

    return {
        "id": project.id,
        "name": project.name,
        "api_key_preview": project.api_key[:10] + "...",
        "is_active": project.is_active,
        "webhook_url": project.webhook_url,
        "webhook_enabled": project.webhook_enabled,
        "created_at": project.created_at,
    }


@router.delete("/{project_id}")
async def deactivate_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate a project.

    This will prevent any further API calls for this project.
    The project and its data are retained for audit purposes.
    """
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=404,
            detail=make_error(ErrorCode.PROJECT_NOT_FOUND),
        )

    project.is_active = False
    await db.flush()

    return {"message": f"Project '{project_id}' has been deactivated"}


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    updates: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_project_by_api_key),
):
    """
    Update project settings.

    Use this to configure webhook notifications and other project settings.
    Requires API key authentication.
    """
    # Verify the API key matches the project being updated
    if project.id != project_id:
        raise HTTPException(
            status_code=403,
            detail=make_error(ErrorCode.PROJECT_MISMATCH),
        )

    # Apply updates
    if updates.name is not None:
        project.name = updates.name
    if updates.webhook_url is not None:
        project.webhook_url = updates.webhook_url
    if updates.webhook_enabled is not None:
        project.webhook_enabled = updates.webhook_enabled

    await db.flush()

    return ProjectResponse(
        id=project.id,
        name=project.name,
        api_key=project.api_key,
        is_active=project.is_active,
        webhook_url=project.webhook_url,
        webhook_enabled=project.webhook_enabled,
        created_at=project.created_at,
    )
