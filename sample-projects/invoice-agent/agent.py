"""
Invoice Payment Agent

An AI agent that processes invoice payment requests.
Uses Ollama (local LLM) to understand requests and decide on actions.
All actions are validated through the AI Firewall before execution.
"""

import json
import httpx
from dataclasses import dataclass
from typing import Optional

from ai_firewall import AIFirewall, ActionBlockedError
from payment_system import PaymentSystem, PaymentResult


@dataclass
class Invoice:
    """Represents an invoice to be processed."""
    id: str
    vendor: str
    amount: float
    description: str
    currency: str = "USD"


@dataclass
class AgentResponse:
    """Response from the agent."""
    action: str
    allowed: bool
    executed: bool
    message: str
    details: Optional[dict] = None


class InvoiceAgent:
    """
    AI-powered invoice payment agent using Ollama.

    This agent:
    1. Receives invoice data or natural language requests
    2. Uses local LLM (Ollama) to decide what action to take
    3. Validates the action through AI Firewall
    4. Executes if allowed, logs if blocked
    """

    SYSTEM_PROMPT = """You are an invoice payment agent. Your job is to process invoices and decide whether to pay them.

You can perform these actions:
1. pay_invoice - Pay an invoice to a vendor
2. reject_invoice - Reject an invoice (won't pay)

When asked to pay an invoice, you MUST respond with ONLY a JSON object, no other text:
{"action": "pay_invoice", "vendor": "<vendor name>", "amount": <amount as number>, "invoice_id": "<invoice id>", "reason": "<brief reason>"}

If you decide NOT to pay, respond with ONLY:
{"action": "reject_invoice", "vendor": "<vendor name>", "amount": <amount>, "invoice_id": "<invoice id>", "reason": "<brief reason>"}

IMPORTANT: Respond with ONLY the JSON object, no explanations or other text."""

    def __init__(
        self,
        firewall: AIFirewall,
        payment_system: PaymentSystem,
        ollama_model: str = "llama3.2:3b",
        ollama_url: str = "http://localhost:11434",
    ):
        self.firewall = firewall
        self.payment_system = payment_system
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self._client = httpx.Client(timeout=60)

    def _get_ai_decision(self, invoice: Invoice) -> dict:
        """Get AI decision for an invoice using Ollama."""
        user_message = f"""Process this invoice and respond with JSON only:
- Invoice ID: {invoice.id}
- Vendor: {invoice.vendor}
- Amount: ${invoice.amount:.2f} {invoice.currency}
- Description: {invoice.description}

Respond with JSON to pay or reject this invoice."""

        try:
            response = self._client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": f"{self.SYSTEM_PROMPT}\n\nUser: {user_message}\n\nAssistant:",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                    }
                },
            )
            response.raise_for_status()
            content = response.json()["response"]

            # Extract JSON from response
            return self._parse_json_response(content, invoice)

        except httpx.ConnectError:
            print("   ERROR: Cannot connect to Ollama. Is it running?")
            print("   Run: ollama serve")
            return self._fallback_decision(invoice)
        except Exception as e:
            print(f"   ERROR: Ollama error: {e}")
            return self._fallback_decision(invoice)

    def _parse_json_response(self, content: str, invoice: Invoice) -> dict:
        """Parse JSON from LLM response."""
        try:
            # Try direct parse first
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, IndexError):
            pass

        # Try to find JSON object in the text
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Fallback
        print("   WARNING: Could not parse LLM response, using fallback")
        return self._fallback_decision(invoice)

    def _fallback_decision(self, invoice: Invoice) -> dict:
        """Fallback decision when LLM fails."""
        return {
            "action": "pay_invoice",
            "vendor": invoice.vendor,
            "amount": invoice.amount,
            "invoice_id": invoice.id,
            "reason": f"Auto-approved: {invoice.description}",
        }

    def process_invoice(self, invoice: Invoice) -> AgentResponse:
        """
        Process an invoice through the agent.

        Flow:
        1. AI decides action (using Ollama)
        2. Firewall validates
        3. Execute if allowed
        """
        print(f"\n{'='*60}")
        print(f" PROCESSING INVOICE: {invoice.id}")
        print(f"{'='*60}")
        print(f"  Vendor: {invoice.vendor}")
        print(f"  Amount: ${invoice.amount:.2f} {invoice.currency}")
        print(f"  Description: {invoice.description}")

        # Step 1: Get AI decision
        print(f"\n[1] AI Decision (using {self.ollama_model})...")
        decision = self._get_ai_decision(invoice)
        action = decision.get("action", "unknown")
        print(f"    Action: {action}")
        print(f"    Reason: {decision.get('reason', 'No reason given')}")

        # Step 2: Validate through firewall
        print(f"\n[2] Firewall Validation...")

        if action == "pay_invoice":
            # Check for duplicate first
            if self.payment_system.is_duplicate(
                invoice.vendor, invoice.amount, invoice.id
            ):
                print("    BLOCKED: Duplicate invoice detected")
                return AgentResponse(
                    action=action,
                    allowed=False,
                    executed=False,
                    message="Duplicate invoice - already paid",
                    details={"invoice_id": invoice.id, "reason": "duplicate"},
                )

            # Validate with firewall
            try:
                result = self.firewall.execute(
                    agent_name="invoice_agent",
                    action_type="pay_invoice",
                    params={
                        "vendor": invoice.vendor,
                        "amount": invoice.amount,
                        "invoice_id": invoice.id,
                        "currency": invoice.currency,
                    },
                )

                if result.allowed:
                    print(f"    ALLOWED (action_id: {result.action_id})")

                    # Step 3: Execute payment
                    print(f"\n[3] Executing Payment...")
                    payment_result = self.payment_system.process_payment(
                        vendor=invoice.vendor,
                        amount=invoice.amount,
                        invoice_id=invoice.id,
                        currency=invoice.currency,
                    )

                    if payment_result.success:
                        print(f"    SUCCESS: {payment_result.message}")
                        return AgentResponse(
                            action=action,
                            allowed=True,
                            executed=True,
                            message=payment_result.message,
                            details={
                                "transaction_id": payment_result.transaction_id,
                                "action_id": result.action_id,
                            },
                        )
                    else:
                        print(f"    FAILED: {payment_result.message}")
                        return AgentResponse(
                            action=action,
                            allowed=True,
                            executed=False,
                            message=payment_result.message,
                        )
                else:
                    print(f"    BLOCKED: {result.reason}")
                    return AgentResponse(
                        action=action,
                        allowed=False,
                        executed=False,
                        message=f"Blocked by firewall: {result.reason}",
                        details={"action_id": result.action_id, "reason": result.reason},
                    )

            except ActionBlockedError as e:
                print(f"    BLOCKED (exception): {e.reason}")
                return AgentResponse(
                    action=action,
                    allowed=False,
                    executed=False,
                    message=f"Blocked: {e.reason}",
                    details={"action_id": e.action_id},
                )

        elif action == "reject_invoice":
            print("    AI rejected the invoice (no firewall needed)")
            return AgentResponse(
                action=action,
                allowed=True,
                executed=True,
                message=f"Invoice rejected: {decision.get('reason', 'No reason')}",
            )

        else:
            print(f"    Unknown action: {action}")
            return AgentResponse(
                action=action,
                allowed=False,
                executed=False,
                message=f"Unknown action: {action}",
            )

    def get_stats(self) -> dict:
        """Get agent statistics from firewall."""
        return self.firewall.get_stats()

    def get_payment_history(self) -> list[dict]:
        """Get payment transaction history."""
        return self.payment_system.get_transaction_history()

    def close(self):
        """Close the agent."""
        self._client.close()
        self.firewall.close()
