"""
Firewall Setup for LangChain Agent

This script sets up the AI Firewall project and policy for the LangChain demo.
Run this once before running the agent.
"""

import httpx
import json


def setup_firewall(base_url: str = None):
    """Set up the firewall project and policy."""
    import os
    base_url = base_url or os.getenv("FIREWALL_URL", "http://localhost:8000")

    print("Setting up AI Firewall for LangChain Agent...")
    print("=" * 50)

    # 1. Create project
    print("\n1. Creating project...")
    try:
        response = httpx.post(
            f"{base_url}/projects",
            json={
                "id": "langchain-demo",
                "name": "LangChain Demo Agent"
            }
        )

        if response.status_code == 200:
            data = response.json()
            api_key = data["api_key"]
            print(f"   ✅ Project created!")
            print(f"   API Key: {api_key}")
            print(f"   ⚠️  Save this key - you won't see it again!")
        elif response.status_code == 409:
            print("   ℹ️  Project already exists")
            print("   You'll need to use your existing API key")
            api_key = input("   Enter your API key: ").strip()
        else:
            print(f"   ❌ Error: {response.text}")
            return None
    except httpx.ConnectError:
        print(f"   ❌ Cannot connect to {base_url}")
        print("   Make sure the AI Firewall server is running:")
        print("   uvicorn server.app:app --reload")
        return None

    # 2. Create policy
    print("\n2. Creating policy...")

    policy = {
        "name": "langchain-agent-policy",
        "version": "1.0",
        "default": "block",
        "rules": [
            {
                "action_type": "pay_invoice",
                "constraints": {
                    "params.amount": {"max": 10000, "min": 1},
                    "params.currency": {"in": ["USD", "EUR", "GBP"]}
                },
                "rate_limit": {"max_requests": 5, "window_seconds": 60}
            },
            {
                "action_type": "send_email",
                "constraints": {
                    "params.to": {"pattern": ".*@(company\\.com|example\\.com)$"}
                }
            },
            {
                "action_type": "search_database"
                # Allowed without constraints
            }
            # execute_sql is NOT listed, so it's blocked by default: "block"
        ]
    }

    response = httpx.post(
        f"{base_url}/policies/langchain-demo",
        json=policy,
        headers={"X-API-Key": api_key}
    )

    if response.status_code == 200:
        print("   ✅ Policy created!")
        print(f"\n   Policy summary:")
        print(f"   - pay_invoice: max $10,000, USD/EUR/GBP only, 5/min rate limit")
        print(f"   - send_email: only to @company.com or @example.com")
        print(f"   - search_database: allowed")
        print(f"   - execute_sql: blocked for all agents")
    else:
        print(f"   ❌ Error: {response.text}")
        return None

    print("\n" + "=" * 50)
    print("Setup complete!")
    print(f"\nAdd this to your .env file:")
    print(f"FIREWALL_API_KEY={api_key}")
    print(f"FIREWALL_PROJECT_ID=langchain-demo")
    print(f"FIREWALL_URL={base_url}")

    return api_key


if __name__ == "__main__":
    setup_firewall()
