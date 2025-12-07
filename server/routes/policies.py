"""Policy management endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.middleware.auth import verify_project_access
from server.models import Policy, Project
from server.schemas import PolicyCreate, PolicyResponse

router = APIRouter(prefix="/policies", tags=["Policies"])


@router.get("/{project_id}", response_model=PolicyResponse)
async def get_policy(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(verify_project_access),
):
    """
    Get the active policy for a project.

    Returns the currently active policy rules that will be used
    for action validation.
    """
    stmt = (
        select(Policy)
        .where(Policy.project_id == project_id)
        .where(Policy.is_active == True)
        .order_by(Policy.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=404,
            detail=f"No active policy found for project '{project_id}'",
        )

    return PolicyResponse(
        id=policy.id,
        project_id=policy.project_id,
        name=policy.name,
        version=policy.version,
        rules=json.loads(policy.rules),
        is_active=policy.is_active,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.post("/{project_id}", response_model=PolicyResponse)
async def create_or_update_policy(
    project_id: str,
    policy_data: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(verify_project_access),
):
    """
    Create or update a policy for a project.

    This will deactivate any existing active policy and create
    a new one with the provided rules.
    """
    # Deactivate existing active policies
    stmt = (
        select(Policy)
        .where(Policy.project_id == project_id)
        .where(Policy.is_active == True)
    )
    result = await db.execute(stmt)
    existing_policies = result.scalars().all()
    for existing in existing_policies:
        existing.is_active = False

    # Create the policy rules JSON
    rules_json = {
        "version": policy_data.version,
        "default": policy_data.default,
        "rules": [rule.model_dump(exclude_none=True) for rule in policy_data.rules],
    }

    # Create new policy
    policy = Policy(
        project_id=project_id,
        name=policy_data.name,
        version=policy_data.version,
        rules=json.dumps(rules_json),
        is_active=True,
    )
    db.add(policy)
    await db.flush()

    return PolicyResponse(
        id=policy.id,
        project_id=policy.project_id,
        name=policy.name,
        version=policy.version,
        rules=rules_json,
        is_active=policy.is_active,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get("/{project_id}/history", response_model=list[PolicyResponse])
async def get_policy_history(
    project_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(verify_project_access),
):
    """
    Get policy version history for a project.

    Returns all policies (active and inactive) in reverse chronological order.
    """
    stmt = (
        select(Policy)
        .where(Policy.project_id == project_id)
        .order_by(Policy.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    policies = result.scalars().all()

    return [
        PolicyResponse(
            id=p.id,
            project_id=p.project_id,
            name=p.name,
            version=p.version,
            rules=json.loads(p.rules),
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in policies
    ]
