"""
Invoice Agent Demo

Runs the AI-powered invoice agent with Ollama and the AI Firewall.
"""

import os
import sys

# Add parent directory for ai_firewall import
sys.path.insert(0, "../../sdk/python")

from ai_firewall import AIFirewall
from payment_system import PaymentSystem
from agent import InvoiceAgent, Invoice


def main():
    # Get configuration
    api_key = os.environ.get("FIREWALL_API_KEY")
    if not api_key:
        print("ERROR: FIREWALL_API_KEY environment variable not set")
        print("Run: python3 firewall_setup.py")
        print("Then: export FIREWALL_API_KEY='your-key'")
        sys.exit(1)

    firewall_url = os.environ.get("FIREWALL_URL", "http://localhost:8000")
    project_id = os.environ.get("FIREWALL_PROJECT_ID", "invoice-agent-demo-1765137203")

    # Try to find the right project ID from the API key
    # The setup script creates timestamped projects, so we extract from key creation
    import httpx
    try:
        # List projects to find one that matches our key
        client = httpx.Client(base_url=firewall_url, timeout=10)
        resp = client.get("/health")
        if resp.status_code != 200:
            print("ERROR: Firewall server not healthy")
            sys.exit(1)
        client.close()
    except httpx.ConnectError:
        print("ERROR: Cannot connect to firewall at", firewall_url)
        print("Make sure the server is running")
        sys.exit(1)

    print("=" * 60)
    print(" INVOICE PAYMENT AGENT DEMO")
    print(" Using Ollama (llama3.2:3b) + AI Firewall")
    print("=" * 60)

    # Initialize components
    firewall = AIFirewall(
        api_key=api_key,
        project_id=project_id,
        base_url=firewall_url,
    )
    payment_system = PaymentSystem()
    agent = InvoiceAgent(
        firewall=firewall,
        payment_system=payment_system,
        ollama_model="llama3.2:3b",
    )

    # Test invoices
    invoices = [
        Invoice(
            id="INV-2024-001",
            vendor="VendorA",
            amount=450.00,
            description="Monthly office supplies",
        ),
        Invoice(
            id="INV-2024-002",
            vendor="VendorA",
            amount=600.00,
            description="Premium equipment purchase",
        ),
        Invoice(
            id="INV-2024-003",
            vendor="UnknownCorp",
            amount=100.00,
            description="Consulting services",
        ),
        Invoice(
            id="INV-2024-004",
            vendor="VendorB",
            amount=250.00,
            description="Software licenses",
        ),
    ]

    print(f"\nProcessing {len(invoices)} invoices...\n")

    # Process each invoice
    for invoice in invoices:
        response = agent.process_invoice(invoice)
        print(f"\n{'=' * 60}")

    # Summary
    print("\n" + "=" * 60)
    print(" DEMO SUMMARY")
    print("=" * 60)

    # Payment history
    history = agent.get_payment_history()
    print(f"\nPayments Executed: {len(history)}")
    for txn in history:
        print(f"  - {txn['transaction_id']}: ${txn['amount']:.2f} to {txn['vendor']}")

    if history:
        total = sum(t["amount"] for t in history)
        print(f"\nTotal Paid: ${total:.2f}")

    # Firewall stats
    stats = agent.get_stats()
    print(f"\nFirewall Stats:")
    print(f"  Total Actions: {stats['total_actions']}")
    print(f"  Allowed: {stats['allowed']}")
    print(f"  Blocked: {stats['blocked']}")
    print(f"  Block Rate: {stats['block_rate']}%")

    # Cleanup
    agent.close()

    print("\n" + "=" * 60)
    print(" Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
