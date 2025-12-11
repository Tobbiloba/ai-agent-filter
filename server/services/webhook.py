"""Webhook service for sending notifications on blocked actions."""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Prometheus metrics for webhooks
WEBHOOK_SENT_TOTAL = Counter(
    "webhook_sent_total",
    "Total webhooks sent",
    ["project_id", "success"],
)


class WebhookService:
    """Service for sending webhook notifications."""

    def __init__(self, timeout: float | None = None, max_retries: int = 3):
        """Initialize the webhook service.

        Args:
            timeout: HTTP request timeout in seconds (default: from config)
            max_retries: Maximum number of retry attempts
        """
        from server.config import get_settings

        settings = get_settings()
        self.timeout = timeout if timeout is not None else settings.webhook_timeout
        self.max_retries = max_retries

    async def send_blocked_action_webhook(
        self,
        webhook_url: str,
        action_id: str,
        project_id: str,
        agent_name: str,
        action_type: str,
        params: dict,
        reason: str,
    ) -> bool:
        """Send webhook notification for blocked action.

        Args:
            webhook_url: URL to send the webhook to
            action_id: Unique identifier for the action
            project_id: Project identifier
            agent_name: Name of the agent that attempted the action
            action_type: Type of action that was blocked
            params: Parameters of the blocked action
            reason: Reason the action was blocked

        Returns:
            True if webhook was sent successfully, False otherwise
        """
        payload = self._build_payload(
            action_id, project_id, agent_name, action_type, params, reason
        )

        # Detect webhook type and format accordingly
        if "hooks.slack.com" in webhook_url:
            payload = self._format_slack(payload)
        elif "discord.com/api/webhooks" in webhook_url:
            payload = self._format_discord(payload)

        success = await self._send_with_retry(webhook_url, payload, project_id)

        # Record metrics
        WEBHOOK_SENT_TOTAL.labels(
            project_id=project_id,
            success="true" if success else "false",
        ).inc()

        return success

    def _build_payload(
        self,
        action_id: str,
        project_id: str,
        agent_name: str,
        action_type: str,
        params: dict,
        reason: str,
    ) -> dict:
        """Build the standard webhook payload."""
        return {
            "event": "action_blocked",
            "action_id": action_id,
            "project_id": project_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "params": params,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _format_slack(self, payload: dict) -> dict:
        """Format payload for Slack incoming webhooks."""
        return {
            "text": ":no_entry: Action Blocked",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":no_entry: Action Blocked",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Agent:*\n{payload['agent_name']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Action:*\n{payload['action_type']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Project:*\n{payload['project_id']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Action ID:*\n`{payload['action_id'][:8]}...`",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Reason:*\n{payload['reason']}",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Blocked at {payload['timestamp']}",
                        },
                    ],
                },
            ],
        }

    def _format_discord(self, payload: dict) -> dict:
        """Format payload for Discord webhooks."""
        return {
            "embeds": [
                {
                    "title": ":no_entry: Action Blocked",
                    "color": 15158332,  # Red color
                    "fields": [
                        {
                            "name": "Agent",
                            "value": payload["agent_name"],
                            "inline": True,
                        },
                        {
                            "name": "Action",
                            "value": payload["action_type"],
                            "inline": True,
                        },
                        {
                            "name": "Project",
                            "value": payload["project_id"],
                            "inline": True,
                        },
                        {
                            "name": "Reason",
                            "value": payload["reason"],
                            "inline": False,
                        },
                    ],
                    "footer": {
                        "text": f"Action ID: {payload['action_id'][:8]}...",
                    },
                    "timestamp": payload["timestamp"],
                }
            ]
        }

    async def _send_with_retry(
        self, url: str, payload: dict, project_id: str
    ) -> bool:
        """Send webhook with exponential backoff retry.

        Args:
            url: Webhook URL
            payload: JSON payload to send
            project_id: Project ID for logging

        Returns:
            True if successful, False otherwise
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(url, json=payload)

                    if response.status_code < 300:
                        logger.info(
                            "Webhook sent successfully",
                            extra={
                                "project_id": project_id,
                                "url_preview": url[:50] + "...",
                                "status_code": response.status_code,
                            },
                        )
                        return True

                    logger.warning(
                        "Webhook returned non-success status",
                        extra={
                            "project_id": project_id,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                        },
                    )

                except httpx.TimeoutException:
                    logger.warning(
                        "Webhook request timed out",
                        extra={
                            "project_id": project_id,
                            "attempt": attempt + 1,
                            "timeout": self.timeout,
                        },
                    )
                except httpx.RequestError as e:
                    logger.warning(
                        "Webhook request failed",
                        extra={
                            "project_id": project_id,
                            "attempt": attempt + 1,
                            "error": str(e),
                        },
                    )

                # Exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = 1 * (2**attempt)  # 1s, 2s, 4s
                    await asyncio.sleep(wait_time)

        logger.error(
            "Webhook failed after all retries",
            extra={
                "project_id": project_id,
                "max_retries": self.max_retries,
            },
        )
        return False


# Global webhook service instance
_webhook_service: WebhookService | None = None


def get_webhook_service() -> WebhookService:
    """Get or create the webhook service singleton."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service
