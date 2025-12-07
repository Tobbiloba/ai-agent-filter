"""Audit log endpoints."""

import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.middleware.auth import verify_project_access
from server.models import AuditLog, Project
from server.schemas import AuditLogResponse, AuditLogList

router = APIRouter(prefix="/logs", tags=["Audit Logs"])


@router.get("/{project_id}", response_model=AuditLogList)
async def get_logs(
    project_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    agent_name: str | None = Query(None, description="Filter by agent name"),
    action_type: str | None = Query(None, description="Filter by action type"),
    allowed: bool | None = Query(None, description="Filter by allowed status"),
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(verify_project_access),
):
    """
    Get audit logs for a project with pagination and filters.

    Returns all action validation attempts, both allowed and blocked.
    """
    # Build base query
    base_query = select(AuditLog).where(AuditLog.project_id == project_id)

    # Apply filters
    if agent_name:
        base_query = base_query.where(AuditLog.agent_name == agent_name)
    if action_type:
        base_query = base_query.where(AuditLog.action_type == action_type)
    if allowed is not None:
        base_query = base_query.where(AuditLog.allowed == allowed)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    offset = (page - 1) * page_size
    query = (
        base_query
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    items = [
        AuditLogResponse(
            action_id=log.action_id,
            project_id=log.project_id,
            agent_name=log.agent_name,
            action_type=log.action_type,
            params=json.loads(log.params),
            allowed=log.allowed,
            reason=log.reason,
            policy_version=log.policy_version,
            execution_time_ms=log.execution_time_ms,
            timestamp=log.timestamp,
        )
        for log in logs
    ]

    return AuditLogList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


@router.get("/{project_id}/stats")
async def get_log_stats(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(verify_project_access),
):
    """
    Get summary statistics for audit logs.

    Returns counts of allowed vs blocked actions, most common action types, etc.
    """
    # Total actions
    total_query = select(func.count()).where(AuditLog.project_id == project_id)
    total_result = await db.execute(total_query)
    total = total_result.scalar()

    # Allowed count
    allowed_query = (
        select(func.count())
        .where(AuditLog.project_id == project_id)
        .where(AuditLog.allowed == True)
    )
    allowed_result = await db.execute(allowed_query)
    allowed = allowed_result.scalar()

    # Blocked count
    blocked = total - allowed

    # Most common action types
    action_types_query = (
        select(AuditLog.action_type, func.count().label("count"))
        .where(AuditLog.project_id == project_id)
        .group_by(AuditLog.action_type)
        .order_by(func.count().desc())
        .limit(10)
    )
    action_types_result = await db.execute(action_types_query)
    action_types = [
        {"action_type": row[0], "count": row[1]}
        for row in action_types_result.all()
    ]

    # Most active agents
    agents_query = (
        select(AuditLog.agent_name, func.count().label("count"))
        .where(AuditLog.project_id == project_id)
        .group_by(AuditLog.agent_name)
        .order_by(func.count().desc())
        .limit(10)
    )
    agents_result = await db.execute(agents_query)
    agents = [
        {"agent_name": row[0], "count": row[1]} for row in agents_result.all()
    ]

    return {
        "total_actions": total,
        "allowed": allowed,
        "blocked": blocked,
        "block_rate": round(blocked / total * 100, 2) if total > 0 else 0,
        "top_action_types": action_types,
        "top_agents": agents,
    }
