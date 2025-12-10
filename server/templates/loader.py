"""Load and manage policy templates."""

import json
from pathlib import Path
from typing import Dict, List, Optional

TEMPLATES_DIR = Path(__file__).parent

_templates_cache: Optional[Dict[str, dict]] = None


def load_templates() -> Dict[str, dict]:
    """Load all templates from JSON files.

    Returns:
        Dictionary mapping template ID to full template data.
    """
    global _templates_cache
    if _templates_cache is not None:
        return _templates_cache

    templates = {}
    for file in TEMPLATES_DIR.glob("*.json"):
        with open(file) as f:
            template = json.load(f)
            templates[template["id"]] = template

    _templates_cache = templates
    return templates


def get_template(template_id: str) -> Optional[dict]:
    """Get a specific template by ID.

    Args:
        template_id: The template identifier (e.g., 'finance', 'healthcare')

    Returns:
        Full template dict if found, None otherwise.
    """
    return load_templates().get(template_id)


def list_templates() -> List[dict]:
    """List all available templates with metadata only.

    Returns:
        List of template metadata (id, name, description) without full policy.
    """
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"]
        }
        for t in load_templates().values()
    ]


def clear_cache() -> None:
    """Clear the templates cache. Useful for testing."""
    global _templates_cache
    _templates_cache = None
