"""
Tool Definitions for LangChain Agent

These are the tools that the agent can use. Each tool represents
an action that will be validated by the AI Firewall before execution.
"""

from typing import Optional


# Simulated backend systems
_paid_invoices = []
_sent_emails = []
_database = {
    "customers": [
        {"id": 1, "name": "Acme Corp", "balance": 15000},
        {"id": 2, "name": "TechStart Inc", "balance": 8500},
        {"id": 3, "name": "Global Services", "balance": 22000},
    ],
    "invoices": [
        {"id": "INV-001", "vendor": "SupplyChain Co", "amount": 5000, "status": "pending"},
        {"id": "INV-002", "vendor": "CloudHost Inc", "amount": 1200, "status": "pending"},
        {"id": "INV-003", "vendor": "Marketing Pro", "amount": 15000, "status": "pending"},
    ]
}


def pay_invoice(
    invoice_id: str,
    vendor: str,
    amount: float,
    currency: str = "USD"
) -> str:
    """
    Pay an invoice to a vendor.

    Args:
        invoice_id: The invoice ID (e.g., INV-001)
        vendor: The vendor name
        amount: The payment amount
        currency: Currency code (USD, EUR, GBP)

    Returns:
        Confirmation message
    """
    # Check if already paid
    if invoice_id in _paid_invoices:
        return f"Error: Invoice {invoice_id} has already been paid"

    # Simulate payment
    _paid_invoices.append(invoice_id)

    return (
        f"✅ Payment successful!\n"
        f"   Invoice: {invoice_id}\n"
        f"   Vendor: {vendor}\n"
        f"   Amount: {amount} {currency}\n"
        f"   Reference: PAY-{len(_paid_invoices):04d}"
    )


def send_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None
) -> str:
    """
    Send an email to a recipient.

    Args:
        to: Email address of recipient
        subject: Email subject line
        body: Email body content
        cc: Optional CC recipient

    Returns:
        Confirmation message
    """
    email_record = {
        "to": to,
        "subject": subject,
        "body": body,
        "cc": cc
    }
    _sent_emails.append(email_record)

    result = (
        f"📧 Email sent!\n"
        f"   To: {to}\n"
        f"   Subject: {subject}"
    )
    if cc:
        result += f"\n   CC: {cc}"

    return result


def search_database(
    table: str,
    query: Optional[str] = None
) -> str:
    """
    Search the database for records.

    Args:
        table: Table name to search (customers, invoices)
        query: Optional search query

    Returns:
        Search results
    """
    if table not in _database:
        return f"Error: Table '{table}' not found. Available: {list(_database.keys())}"

    records = _database[table]

    if query:
        # Simple text search
        query_lower = query.lower()
        records = [
            r for r in records
            if any(query_lower in str(v).lower() for v in r.values())
        ]

    if not records:
        return f"No records found in {table}" + (f" matching '{query}'" if query else "")

    result = f"Found {len(records)} record(s) in {table}:\n"
    for record in records:
        result += f"  - {record}\n"

    return result


def execute_sql(query: str) -> str:
    """
    Execute a raw SQL query on the database.

    Args:
        query: SQL query to execute

    Returns:
        Query results

    Note: This action should be blocked by the firewall policy!
    """
    # This should never execute if firewall is working
    return f"DANGER: Executed SQL: {query}"


# For testing: reset state
def reset_state():
    """Reset the simulated backend state."""
    global _paid_invoices, _sent_emails
    _paid_invoices = []
    _sent_emails = []


def get_state():
    """Get current state for inspection."""
    return {
        "paid_invoices": _paid_invoices.copy(),
        "sent_emails": _sent_emails.copy(),
    }
