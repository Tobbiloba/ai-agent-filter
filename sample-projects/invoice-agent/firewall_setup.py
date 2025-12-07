"""
Firewall Setup

Creates the project and policy in the AI Firewall for the Invoice Agent.
Run this once before running the agent.
"""

import httpx
import json
import sys

FIREWALL_URL = "http://localhost:8000"
PROJECT_ID = "invoice-agent-demo"
PROJECT_NAME = "Invoice Payment Agent Demo"


def setup_firewall() -> str:
    """
    Set up the firewall project and policy.

    Returns the API key for the project.
    """
    global PROJECT_ID
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

    # Create project (or get existing API key)
    print(f"\nCreating project: {PROJECT_ID}")
    resp = client.post("/projects", json={
        "id": PROJECT_ID,
        "name": PROJECT_NAME,
    })

    if resp.status_code == 200:
        project = resp.json()
        api_key = project["api_key"]
        print(f"Project created successfully!")
        print(f"API Key: {api_key}")
    elif resp.status_code == 409:
        print("Project already exists. You'll need the existing API key.")
        print("To get a new key, delete the project first or use a different project ID.")
        # For demo purposes, we'll create a new project with timestamp
        import time
        new_project_id = f"{PROJECT_ID}-{int(time.time())}"
        resp = client.post("/projects", json={
            "id": new_project_id,
            "name": PROJECT_NAME,
        })
        if resp.status_code != 200:
            print(f"Failed to create project: {resp.text}")
            sys.exit(1)
        project = resp.json()
        api_key = project["api_key"]
        print(f"Created new project: {new_project_id}")
        print(f"API Key: {api_key}")
        PROJECT_ID = new_project_id
    else:
        print(f"Failed to create project: {resp.status_code} - {resp.text}")
        sys.exit(1)

    # Create policy
    print(f"\nSetting up policy...")
    policy = {
        "name": "invoice-payment-policy",
        "version": "1.0",
        "default": "block",
        "rules": [
            {
                "action_type": "pay_invoice",
                "constraints": {
                    "params.amount": {"max": 500, "min": 1},
                    "params.vendor": {"in": ["VendorA", "VendorB", "VendorC"]}
                },
                "allowed_agents": ["invoice_agent"],
                "rate_limit": {"max_requests": 10, "window_seconds": 60}
            },
            {
                "action_type": "check_balance",
                "allowed_agents": ["invoice_agent"]
            },
            {
                "action_type": "list_pending_invoices",
                "allowed_agents": ["invoice_agent"]
            }
        ]
    }

    headers = {"X-API-Key": api_key}
    resp = client.post(f"/policies/{project['id']}", json=policy, headers=headers)

    if resp.status_code != 200:
        print(f"Failed to create policy: {resp.status_code} - {resp.text}")
        sys.exit(1)

    policy_resp = resp.json()
    print(f"Policy created: {policy_resp['name']} v{policy_resp['version']}")
    print(f"Rules:")
    for rule in policy_resp["rules"]["rules"]:
        print(f"  - {rule['action_type']}")

    client.close()

    # Summary
    print("\n" + "="*50)
    print("SETUP COMPLETE")
    print("="*50)
    print(f"Project ID: {project['id']}")
    print(f"API Key: {api_key}")
    print(f"\nPolicy Rules:")
    print(f"  - pay_invoice: max $500, vendors [VendorA, VendorB, VendorC]")
    print(f"  - Rate limit: 10 requests per minute")
    print(f"  - Default: BLOCK all other actions")
    print("="*50)

    return api_key


if __name__ == "__main__":
    api_key = setup_firewall()
    print(f"\nSave this API key to use in your agent:")
    print(f"export FIREWALL_API_KEY='{api_key}'")
