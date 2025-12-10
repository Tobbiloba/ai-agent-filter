"""Policy templates endpoints."""

from fastapi import APIRouter, HTTPException

from server.templates.loader import list_templates, get_template

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("")
async def get_templates():
    """List all available policy templates.

    Returns template metadata (id, name, description) without the full policy.
    Use GET /templates/{template_id} to get the full template with policy.
    """
    return {"templates": list_templates()}


@router.get("/{template_id}")
async def get_template_detail(template_id: str):
    """Get full template details including policy rules.

    Returns the complete template with all policy rules that can be
    used to create a new policy.
    """
    template = get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_id}' not found. Available templates: finance, healthcare, general",
        )
    return template
