"""
Firewall Setup for Support Agent

Creates the project and policy in the AI Firewall for the Support Agent.
"""

import httpx
import sys

FIREWALL_URL = "http://localhost:8000"
PROJECT_ID = "support-agent-demo"
PROJECT_NAME = "Customer Support Agent Demo"


def setup_firewall() -> tuple[str, str]:
    """
    Set up the firewall project and policy.

    Returns (project_id, api_key).
    """
    client = httpx.Client(base_url=FIREWALL_URL, timeout=10)

    # Check if firewall is running
    try:
        resp = client.get("/health")
        if resp.status_code != 200:
            print("ERROR: Firewall server is not healthy")
            sys.exit(1)
        print(f"Firewall server is running (v{resp.json()['version']})")
    except httpx.ConnectError:
        print("ERROR: Cannot connect to firewall server at", FIREWALL_URL)
        print("Make sure the server is running: uvicorn server.app:app --port 8000")
        sys.exit(1)

    # Create project with timestamp to avoid conflicts
    import time
    project_id = f"{PROJECT_ID}-{int(time.time())}"

    print(f"\nCreating project: {project_id}")
    resp = client.post("/projects", json={
        "id": project_id,
        "name": PROJECT_NAME,
    })

    if resp.status_code != 200:
        print(f"Failed to create project: {resp.text}")
        sys.exit(1)

    project = resp.json()
    api_key = project["api_key"]
    print(f"Project created!")
    print(f"API Key: {api_key}")

    # Create policy with support agent rules
    print(f"\nSetting up policy...")

    # PII patterns to block
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    credit_card_pattern = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    policy = {
        "name": "support-agent-policy",
        "version": "1.0",
        "default": "block",
        "rules": [
            # Rule 1: Send response - block PII in response text
            {
                "action_type": "send_response",
                "constraints": {
                    # Block SSN in responses
                    "params.response_text": {
                        "not_pattern": ssn_pattern,
                        "reason": "Response contains SSN - PII not allowed"
                    },
                },
                "allowed_agents": ["support_agent"],
                "rate_limit": {"max_requests": 50, "window_seconds": 60}
            },
            # Rule 2: Close ticket - require reviewed tag
            {
                "action_type": "close_ticket",
                "constraints": {
                    # Must have reviewed tag
                    "params.has_reviewed_tag": {"equals": True},
                },
                "allowed_agents": ["support_agent"],
            },
            # Rule 3: Add internal note (allowed)
            {
                "action_type": "add_internal_note",
                "allowed_agents": ["support_agent"],
            },
        ]
    }

    headers = {"X-API-Key": api_key}
    resp = client.post(f"/policies/{project_id}", json=policy, headers=headers)

    if resp.status_code != 200:
        print(f"Failed to create policy: {resp.status_code} - {resp.text}")
        sys.exit(1)

    policy_resp = resp.json()
    print(f"Policy created: {policy_resp['name']} v{policy_resp['version']}")

    client.close()

    # Summary
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print(f"Project ID: {project_id}")
    print(f"API Key: {api_key}")
    print(f"\nPolicy Rules:")
    print(f"  1. send_response:")
    print(f"     - Block if response contains SSN")
    print(f"     - Rate limit: 50 per minute")
    print(f"  2. close_ticket:")
    print(f"     - REQUIRES 'reviewed' tag on ticket")
    print(f"  3. Default: BLOCK all other actions")
    print("=" * 60)

    return project_id, api_key


if __name__ == "__main__":
    project_id, api_key = setup_firewall()
    print(f"\nTo run the demo:")
    print(f"export FIREWALL_API_KEY='{api_key}'")
    print(f"export FIREWALL_PROJECT_ID='{project_id}'")
    print(f"python3 demo.py")
