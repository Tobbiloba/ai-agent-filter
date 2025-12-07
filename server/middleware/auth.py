"""Authentication middleware for API key validation."""

from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import get_settings
from server.database import get_db
from server.models import Project

settings = get_settings()

api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)


async def get_project_by_api_key(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Validate API key and return the associated project."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include it in the X-API-Key header.",
        )

    # Look up project by API key
    stmt = select(Project).where(Project.api_key == api_key).where(Project.is_active == True)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key or project is inactive.",
        )

    return project


async def verify_project_access(
    project_id: str,
    project: Project = Depends(get_project_by_api_key),
) -> Project:
    """Verify the API key has access to the specified project."""
    if project.id != project_id:
        raise HTTPException(
            status_code=403,
            detail="API key does not have access to this project.",
        )
    return project
