"""Project management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.models import Project
from server.schemas import ProjectCreate, ProjectResponse

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
            detail=f"Project with ID '{project_data.id}' already exists",
        )

    # Create project
    project = Project(
        id=project_data.id,
        name=project_data.name,
    )
    db.add(project)
    await db.flush()

    return ProjectResponse(
        id=project.id,
        name=project.name,
        api_key=project.api_key,
        is_active=project.is_active,
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
            detail=f"Project '{project_id}' not found",
        )

    return {
        "id": project.id,
        "name": project.name,
        "api_key_preview": project.api_key[:10] + "...",
        "is_active": project.is_active,
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
            detail=f"Project '{project_id}' not found",
        )

    project.is_active = False
    await db.flush()

    return {"message": f"Project '{project_id}' has been deactivated"}
