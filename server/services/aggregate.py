"""Aggregate limit tracking service.

Tracks cumulative values across actions within time windows.
Supports rolling windows (hourly, daily, weekly) and measures (sum, count).
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.audit_log import AuditLog
from server.cache import get_cache

logger = logging.getLogger(__name__)


class AggregateService:
    """Track cumulative values across actions for aggregate limits."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.cache = get_cache()

    def _get_window_start(self, window: str) -> datetime:
        """Calculate window start time based on window type.

        Supported windows:
        - "hourly": Current hour (resets at :00)
        - "daily": Current day (resets at midnight UTC)
        - "weekly": Current week (resets Monday midnight UTC)
        - "rolling_hours:N": Last N hours from now
        """
        now = datetime.utcnow()

        if window == "hourly":
            return now.replace(minute=0, second=0, microsecond=0)
        elif window == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif window == "weekly":
            days_since_monday = now.weekday()
            start = now - timedelta(days=days_since_monday)
            return start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif window.startswith("rolling_hours:"):
            try:
                hours = int(window.split(":")[1])
                return now - timedelta(hours=hours)
            except (ValueError, IndexError):
                logger.warning(f"Invalid rolling_hours format: {window}, using daily")
                return now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Default to daily
            logger.warning(f"Unknown window type: {window}, using daily")
            return now.replace(hour=0, minute=0, second=0, microsecond=0)

    def _build_cache_key(
        self,
        project_id: str,
        agent_name: str,
        action_type: str,
        window: str,
        scope: str,
    ) -> str:
        """Build cache key for aggregate total.

        Key format varies by scope:
        - agent: agg:{project_id}:{agent_name}:{action_type}:{window_id}
        - action: agg:{project_id}:{action_type}:{window_id}
        - project: agg:{project_id}:{window_id}
        """
        # For rolling windows, use a more frequent bucket
        if window.startswith("rolling_hours:"):
            # Use hour precision for rolling windows
            window_id = self._get_window_start(window).strftime("%Y%m%d%H")
        elif window == "hourly":
            window_id = self._get_window_start(window).strftime("%Y%m%d%H")
        elif window == "weekly":
            window_id = self._get_window_start(window).strftime("%Y%W")
        else:
            # daily and default
            window_id = self._get_window_start(window).strftime("%Y%m%d")

        if scope == "project":
            return f"agg:{project_id}:{window_id}"
        elif scope == "action":
            return f"agg:{project_id}:{action_type}:{window_id}"
        else:  # agent (default)
            return f"agg:{project_id}:{agent_name}:{action_type}:{window_id}"

    async def get_current_total(
        self,
        project_id: str,
        agent_name: str,
        action_type: str,
        config: dict[str, Any],
    ) -> float:
        """Get current aggregate total for the specified window.

        Args:
            project_id: Project identifier
            agent_name: Agent name
            action_type: Action type
            config: Aggregate limit configuration with keys:
                - window: "hourly" | "daily" | "weekly" | "rolling_hours:N"
                - scope: "agent" | "action" | "project"
                - param_path: Path to value in params (e.g., "amount")
                - measure: "sum" | "count"

        Returns:
            Current aggregate total for the window
        """
        window = config.get("window", "daily")
        scope = config.get("scope", "agent")
        param_path = config.get("param_path", "amount")
        measure = config.get("measure", "sum")

        # Try cache first (not for rolling windows - they need DB accuracy)
        if not window.startswith("rolling_hours:"):
            cache_key = self._build_cache_key(
                project_id, agent_name, action_type, window, scope
            )
            cached = await self.cache.get(cache_key)
            if cached is not None:
                try:
                    return float(cached)
                except ValueError:
                    pass  # Invalid cache, recalculate

        # Calculate from database
        window_start = self._get_window_start(window)
        total = await self._calculate_from_db(
            project_id, agent_name, action_type,
            window_start, scope, param_path, measure
        )

        # Cache result (TTL based on window type)
        # Don't cache rolling windows (need real-time accuracy)
        if not window.startswith("rolling_hours:"):
            cache_key = self._build_cache_key(
                project_id, agent_name, action_type, window, scope
            )
            ttl = 60 if window == "hourly" else 300  # 1 min or 5 min
            await self.cache.set(cache_key, str(total), ttl)

        return total

    async def _calculate_from_db(
        self,
        project_id: str,
        agent_name: str,
        action_type: str,
        window_start: datetime,
        scope: str,
        param_path: str,
        measure: str,
    ) -> float:
        """Calculate aggregate from audit logs in database."""
        # Build query - only count allowed actions
        stmt = (
            select(AuditLog)
            .where(AuditLog.project_id == project_id)
            .where(AuditLog.allowed == True)
            .where(AuditLog.timestamp >= window_start)
        )

        # Apply scope filters
        if scope == "agent":
            stmt = stmt.where(AuditLog.agent_name == agent_name)
            stmt = stmt.where(AuditLog.action_type == action_type)
        elif scope == "action":
            stmt = stmt.where(AuditLog.action_type == action_type)
        # scope == "project" has no additional filters

        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        # Calculate total based on measure type
        if measure == "count":
            return float(len(logs))

        # measure == "sum" (default)
        total = 0.0
        for log in logs:
            value = self._extract_param_value(log.params, param_path)
            if value is not None:
                total += value

        return total

    def _extract_param_value(self, params_json: str, path: str) -> Optional[float]:
        """Extract numeric value from params JSON using dot notation path.

        Args:
            params_json: JSON string of params
            path: Dot-notation path like "amount" or "data.total"

        Returns:
            Extracted float value, or None if not found/invalid
        """
        try:
            params = json.loads(params_json) if isinstance(params_json, str) else params_json
            parts = path.split(".")
            value = params
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            if value is None:
                return None
            return float(value)
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    async def invalidate_cache(
        self,
        project_id: str,
        agent_name: str,
        action_type: str,
    ) -> None:
        """Invalidate aggregate cache after action is allowed.

        Called when a new action is approved to ensure next check
        recalculates the total from database.
        """
        # Delete all aggregate cache keys for this project
        # This is a broad invalidation but ensures consistency
        pattern = f"agg:{project_id}:*"
        await self.cache.delete_pattern(pattern)


async def get_aggregate_service(db: AsyncSession) -> AggregateService:
    """Factory function to create an aggregate service."""
    return AggregateService(db)
