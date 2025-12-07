"""
Simulated Payment System

This represents your actual payment backend. In a real system,
this would connect to Stripe, bank APIs, or internal payment processing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib


@dataclass
class PaymentResult:
    """Result of a payment attempt."""
    success: bool
    transaction_id: Optional[str] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PaymentSystem:
    """Simulated payment processing system."""

    def __init__(self):
        # Track paid invoices to detect duplicates
        self._paid_invoices: set[str] = set()
        self._transactions: list[dict] = []

    def _generate_invoice_hash(self, vendor: str, amount: float, invoice_id: str) -> str:
        """Generate a unique hash for an invoice."""
        data = f"{vendor}:{amount}:{invoice_id}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def is_duplicate(self, vendor: str, amount: float, invoice_id: str) -> bool:
        """Check if this invoice has already been paid."""
        invoice_hash = self._generate_invoice_hash(vendor, amount, invoice_id)
        return invoice_hash in self._paid_invoices

    def process_payment(
        self,
        vendor: str,
        amount: float,
        invoice_id: str,
        currency: str = "USD",
    ) -> PaymentResult:
        """
        Process a payment to a vendor.

        In a real system, this would:
        1. Connect to payment gateway
        2. Initiate transfer
        3. Wait for confirmation
        4. Record in accounting system
        """
        # Check for duplicate
        invoice_hash = self._generate_invoice_hash(vendor, amount, invoice_id)
        if invoice_hash in self._paid_invoices:
            return PaymentResult(
                success=False,
                message=f"Duplicate payment: Invoice {invoice_id} already paid",
            )

        # Simulate payment processing
        transaction_id = f"TXN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{invoice_hash[:8]}"

        # Record the payment
        self._paid_invoices.add(invoice_hash)
        self._transactions.append({
            "transaction_id": transaction_id,
            "vendor": vendor,
            "amount": amount,
            "currency": currency,
            "invoice_id": invoice_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return PaymentResult(
            success=True,
            transaction_id=transaction_id,
            message=f"Payment of ${amount:.2f} {currency} to {vendor} processed successfully",
        )

    def get_transaction_history(self) -> list[dict]:
        """Get all processed transactions."""
        return self._transactions.copy()

    def get_total_paid(self) -> float:
        """Get total amount paid."""
        return sum(t["amount"] for t in self._transactions)

    def reset(self):
        """Reset the payment system (for testing)."""
        self._paid_invoices.clear()
        self._transactions.clear()
