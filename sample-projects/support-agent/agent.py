"""
Customer Support Response Agent

An AI agent that handles customer support tickets.
Uses Ollama (local LLM) to generate responses and decide actions.
All actions are validated through the AI Firewall before execution.
"""

import json
import re
import httpx
from dataclasses import dataclass
from typing import Optional

from ai_firewall import AIFirewall, ActionBlockedError
from ticket_system import TicketSystem, Ticket, TicketStatus, ActionResult


@dataclass
class AgentResponse:
    """Response from the agent."""
    action: str
    allowed: bool
    executed: bool
    message: str
    details: Optional[dict] = None


class SupportAgent:
    """
    AI-powered customer support agent using Ollama.

    This agent:
    1. Receives a support ticket
    2. Uses local LLM (Ollama) to decide action and generate response
    3. Validates the action through AI Firewall
    4. Executes if allowed, logs if blocked
    """

    SYSTEM_PROMPT = """You are a customer support AI agent. Your job is to handle support tickets by responding to customers and managing ticket status.

You can perform these actions:
1. send_response - Send a response to the customer
2. close_ticket - Close the ticket (only if issue is resolved)
3. escalate - Escalate to a human agent

When you decide on an action, respond with ONLY a JSON object:

For sending a response:
{"action": "send_response", "response": "<your response to the customer>", "reason": "<brief reason>"}

For closing a ticket:
{"action": "close_ticket", "resolution": "<brief resolution summary>", "reason": "<why closing>"}

For escalating:
{"action": "escalate", "reason": "<why escalating>"}

IMPORTANT RULES:
- Be helpful and professional
- NEVER include sensitive customer data like SSN, credit card numbers, or full email addresses in responses
- If the customer provides sensitive info, acknowledge receipt but don't repeat it back
- Only close tickets when the issue is clearly resolved

Respond with ONLY the JSON object, no explanations."""

    def __init__(
        self,
        firewall: AIFirewall,
        ticket_system: TicketSystem,
        ollama_model: str = "llama3.2:3b",
        ollama_url: str = "http://localhost:11434",
    ):
        self.firewall = firewall
        self.ticket_system = ticket_system
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self._client = httpx.Client(timeout=60)

    def _get_ai_decision(self, ticket: Ticket) -> dict:
        """Get AI decision for a ticket using Ollama."""
        # Build context with ticket info
        tags_str = ", ".join(ticket.tags) if ticket.tags else "none"
        responses_str = ""
        if ticket.responses:
            for r in ticket.responses[-3:]:  # Last 3 responses
                responses_str += f"\n- {r['text'][:200]}"

        user_message = f"""Handle this support ticket:

Ticket ID: {ticket.id}
Subject: {ticket.subject}
Status: {ticket.status.value}
Priority: {ticket.priority.value}
Tags: {tags_str}

Customer Message:
{ticket.description}

Previous Responses:{responses_str if responses_str else " None"}

Decide what action to take and respond with JSON only."""

        try:
            response = self._client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": f"{self.SYSTEM_PROMPT}\n\nUser: {user_message}\n\nAssistant:",
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                    }
                },
            )
            response.raise_for_status()
            content = response.json()["response"]
            return self._parse_json_response(content, ticket)

        except httpx.ConnectError:
            print("   ERROR: Cannot connect to Ollama. Is it running?")
            return self._fallback_decision(ticket)
        except Exception as e:
            print(f"   ERROR: Ollama error: {e}")
            return self._fallback_decision(ticket)

    def _parse_json_response(self, content: str, ticket: Ticket) -> dict:
        """Parse JSON from LLM response."""
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, IndexError):
            pass

        # Try to find JSON object
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        print("   WARNING: Could not parse LLM response, using fallback")
        return self._fallback_decision(ticket)

    def _fallback_decision(self, ticket: Ticket) -> dict:
        """Fallback decision when LLM fails."""
        return {
            "action": "send_response",
            "response": f"Thank you for contacting support regarding '{ticket.subject}'. A team member will review your request shortly.",
            "reason": "Auto-response (LLM unavailable)",
        }

    def _contains_pii(self, text: str) -> tuple[bool, str]:
        """Check if text contains PII patterns."""
        # SSN pattern: XXX-XX-XXXX
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        if re.search(ssn_pattern, text):
            return True, "SSN detected"

        # Credit card pattern: 16 digits with optional spaces/dashes
        cc_pattern = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
        if re.search(cc_pattern, text):
            return True, "Credit card number detected"

        # Email in response (we shouldn't echo back emails)
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, text):
            return True, "Email address detected"

        return False, ""

    def handle_ticket(self, ticket: Ticket) -> AgentResponse:
        """
        Process a support ticket through the agent.

        Flow:
        1. AI decides action (using Ollama)
        2. Firewall validates
        3. Execute if allowed
        """
        print(f"\n{'=' * 60}")
        print(f" HANDLING TICKET: {ticket.id}")
        print(f"{'=' * 60}")
        print(f"  Subject: {ticket.subject}")
        print(f"  Status: {ticket.status.value}")
        print(f"  Tags: {ticket.tags}")
        print(f"  Customer: {ticket.customer_email[:3]}***@***")

        # Step 1: Get AI decision
        print(f"\n[1] AI Decision (using {self.ollama_model})...")
        decision = self._get_ai_decision(ticket)
        action = decision.get("action", "unknown")
        print(f"    Action: {action}")
        print(f"    Reason: {decision.get('reason', 'No reason given')}")

        # Step 2: Validate through firewall
        print(f"\n[2] Firewall Validation...")

        if action == "send_response":
            response_text = decision.get("response", "")

            # Build params for firewall
            params = {
                "ticket_id": ticket.id,
                "response_text": response_text,
                "ticket_status": ticket.status.value,
                "ticket_tags": ticket.tags,
            }

            try:
                result = self.firewall.execute(
                    agent_name="support_agent",
                    action_type="send_response",
                    params=params,
                )

                if result.allowed:
                    print(f"    ALLOWED (action_id: {result.action_id})")

                    # Execute the action
                    print(f"\n[3] Sending Response...")
                    action_result = self.ticket_system.add_response(
                        ticket_id=ticket.id,
                        response_text=response_text,
                    )

                    if action_result.success:
                        print(f"    SUCCESS: Response sent")
                        print(f"    Response preview: {response_text[:100]}...")
                        return AgentResponse(
                            action=action,
                            allowed=True,
                            executed=True,
                            message=action_result.message,
                            details={"response_preview": response_text[:100]},
                        )
                else:
                    print(f"    BLOCKED: {result.reason}")
                    return AgentResponse(
                        action=action,
                        allowed=False,
                        executed=False,
                        message=f"Blocked: {result.reason}",
                        details={"action_id": result.action_id},
                    )

            except ActionBlockedError as e:
                print(f"    BLOCKED (exception): {e.reason}")
                return AgentResponse(
                    action=action,
                    allowed=False,
                    executed=False,
                    message=f"Blocked: {e.reason}",
                )

        elif action == "close_ticket":
            resolution = decision.get("resolution", "Issue resolved")

            # Build params for firewall - include tag info
            params = {
                "ticket_id": ticket.id,
                "resolution": resolution,
                "ticket_status": ticket.status.value,
                "ticket_tags": ticket.tags,
                "has_reviewed_tag": ticket.has_tag("reviewed"),
            }

            try:
                result = self.firewall.execute(
                    agent_name="support_agent",
                    action_type="close_ticket",
                    params=params,
                )

                if result.allowed:
                    print(f"    ALLOWED (action_id: {result.action_id})")

                    # Execute the close
                    print(f"\n[3] Closing Ticket...")
                    action_result = self.ticket_system.close_ticket(
                        ticket_id=ticket.id,
                        resolution_note=resolution,
                    )

                    if action_result.success:
                        print(f"    SUCCESS: Ticket closed")
                        return AgentResponse(
                            action=action,
                            allowed=True,
                            executed=True,
                            message=action_result.message,
                            details={"resolution": resolution},
                        )
                else:
                    print(f"    BLOCKED: {result.reason}")
                    return AgentResponse(
                        action=action,
                        allowed=False,
                        executed=False,
                        message=f"Blocked: {result.reason}",
                        details={"action_id": result.action_id},
                    )

            except ActionBlockedError as e:
                print(f"    BLOCKED (exception): {e.reason}")
                return AgentResponse(
                    action=action,
                    allowed=False,
                    executed=False,
                    message=f"Blocked: {e.reason}",
                )

        elif action == "escalate":
            print("    Escalation doesn't require firewall approval")
            return AgentResponse(
                action=action,
                allowed=True,
                executed=True,
                message=f"Ticket escalated: {decision.get('reason', 'No reason')}",
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

    def close(self):
        """Close the agent."""
        self._client.close()
        self.firewall.close()
