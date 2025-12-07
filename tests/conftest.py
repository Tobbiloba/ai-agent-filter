"""
Shared pytest fixtures for AI Firewall tests.
"""

import json
import pytest
import sys
from pathlib import Path

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.policy_engine import PolicyEngine


@pytest.fixture
def policy_engine():
    """Fresh policy engine instance for each test."""
    engine = PolicyEngine()
    yield engine
    engine.clear_rate_limits()


@pytest.fixture
def base_policy():
    """Base policy structure for building test policies."""
    return {
        "name": "test-policy",
        "version": "1.0",
        "default": "block",
        "rules": []
    }


def make_policy_json(rules: list, default: str = "block") -> str:
    """Helper to create policy JSON from rules."""
    policy = {
        "name": "test-policy",
        "version": "1.0",
        "default": default,
        "rules": rules
    }
    return json.dumps(policy)
