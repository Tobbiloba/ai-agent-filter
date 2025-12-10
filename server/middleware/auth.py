"""Authentication middleware for API key validation."""

from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import get_settings
from server.database import get_db
from server.models import Project
from server.cache import get_cache
from server.errors import ErrorCode, make_error

settings = get_settings()

api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)


def _project_from_cache(data: dict) -> Project:
    """Reconstruct Project object from cached data."""
    project = Project(
        id=data["id"],
        name=data["name"],
        api_key=data["api_key"],
        is_active=data["is_active"],
        webhook_url=data.get("webhook_url"),
        webhook_enabled=data.get("webhook_enabled", False),
    )
    return project


async def get_project_by_api_key(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Validate API key and return the associated project (with caching)."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail=make_error(ErrorCode.MISSING_API_KEY),
        )

    cache = get_cache()

    # Try cache first
    cached = await cache.get_project_by_api_key(api_key)
    if cached:
        return _project_from_cache(cached)

    # Cache miss - look up project by API key
    stmt = select(Project).where(Project.api_key == api_key).where(Project.is_active == True)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=403,
            detail=make_error(ErrorCode.INVALID_API_KEY),
        )

    # Cache the result
    await cache.set_project_by_api_key(api_key, {
        "id": project.id,
        "name": project.name,
        "api_key": project.api_key,
        "is_active": project.is_active,
        "webhook_url": project.webhook_url,
        "webhook_enabled": project.webhook_enabled,
    })

    return project


async def verify_project_access(
    project_id: str,
    project: Project = Depends(get_project_by_api_key),
) -> Project:
    """Verify the API key has access to the specified project."""
    if project.id != project_id:
        raise HTTPException(
            status_code=403,
            detail=make_error(ErrorCode.PROJECT_MISMATCH),
        )
    return project
