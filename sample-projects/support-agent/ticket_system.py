"""
Simulated Ticket System

Represents a real customer support ticketing system like Zendesk, Freshdesk, etc.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class TicketStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Ticket:
    """Represents a customer support ticket."""
    id: str
    customer_email: str
    subject: str
    description: str
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM
    tags: list[str] = field(default_factory=list)
    responses: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def has_tag(self, tag: str) -> bool:
        return tag.lower() in [t.lower() for t in self.tags]

    def add_tag(self, tag: str):
        if not self.has_tag(tag):
            self.tags.append(tag)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_email": self.customer_email,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "tags": self.tags,
            "response_count": len(self.responses),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ActionResult:
    """Result of a ticket action."""
    success: bool
    message: str
    ticket_id: Optional[str] = None
    action: Optional[str] = None


class TicketSystem:
    """Simulated ticket management system."""

    def __init__(self):
        self._tickets: dict[str, Ticket] = {}
        self._action_log: list[dict] = []

    def create_ticket(self, ticket: Ticket) -> None:
        """Add a ticket to the system."""
        self._tickets[ticket.id] = ticket

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        return self._tickets.get(ticket_id)

    def update_ticket_status(
        self,
        ticket_id: str,
        new_status: TicketStatus,
        agent_note: str = ""
    ) -> ActionResult:
        """Update a ticket's status."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return ActionResult(
                success=False,
                message=f"Ticket {ticket_id} not found",
                ticket_id=ticket_id,
                action="update_status"
            )

        old_status = ticket.status
        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()

        self._action_log.append({
            "action": "update_status",
            "ticket_id": ticket_id,
            "old_status": old_status.value,
            "new_status": new_status.value,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return ActionResult(
            success=True,
            message=f"Ticket {ticket_id} status changed from {old_status.value} to {new_status.value}",
            ticket_id=ticket_id,
            action="update_status"
        )

    def add_response(
        self,
        ticket_id: str,
        response_text: str,
        is_internal: bool = False
    ) -> ActionResult:
        """Add a response to a ticket."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return ActionResult(
                success=False,
                message=f"Ticket {ticket_id} not found",
                ticket_id=ticket_id,
                action="add_response"
            )

        response = {
            "text": response_text,
            "is_internal": is_internal,
            "timestamp": datetime.utcnow().isoformat(),
            "author": "ai_support_agent",
        }
        ticket.responses.append(response)
        ticket.updated_at = datetime.utcnow()

        self._action_log.append({
            "action": "add_response",
            "ticket_id": ticket_id,
            "response_length": len(response_text),
            "is_internal": is_internal,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return ActionResult(
            success=True,
            message=f"Response added to ticket {ticket_id}" + (" (internal note)" if is_internal else ""),
            ticket_id=ticket_id,
            action="add_response"
        )

    def close_ticket(self, ticket_id: str, resolution_note: str = "") -> ActionResult:
        """Close a ticket."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return ActionResult(
                success=False,
                message=f"Ticket {ticket_id} not found",
                ticket_id=ticket_id,
                action="close_ticket"
            )

        ticket.status = TicketStatus.CLOSED
        ticket.updated_at = datetime.utcnow()
        if resolution_note:
            ticket.responses.append({
                "text": f"[CLOSED] {resolution_note}",
                "is_internal": True,
                "timestamp": datetime.utcnow().isoformat(),
                "author": "ai_support_agent",
            })

        self._action_log.append({
            "action": "close_ticket",
            "ticket_id": ticket_id,
            "resolution_note": resolution_note,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return ActionResult(
            success=True,
            message=f"Ticket {ticket_id} has been closed",
            ticket_id=ticket_id,
            action="close_ticket"
        )

    def add_tag(self, ticket_id: str, tag: str) -> ActionResult:
        """Add a tag to a ticket."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return ActionResult(
                success=False,
                message=f"Ticket {ticket_id} not found",
                ticket_id=ticket_id,
                action="add_tag"
            )

        ticket.add_tag(tag)
        ticket.updated_at = datetime.utcnow()

        self._action_log.append({
            "action": "add_tag",
            "ticket_id": ticket_id,
            "tag": tag,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return ActionResult(
            success=True,
            message=f"Tag '{tag}' added to ticket {ticket_id}",
            ticket_id=ticket_id,
            action="add_tag"
        )

    def get_action_log(self) -> list[dict]:
        """Get all actions performed."""
        return self._action_log.copy()

    def get_all_tickets(self) -> list[Ticket]:
        """Get all tickets."""
        return list(self._tickets.values())
