"""
LangChain Callback Handler with AI Firewall Protection

This module provides a callback handler that intercepts all LangChain tool
executions and validates them through the AI Firewall before they run.

This is the most comprehensive approach - it automatically protects ALL
tools used by an agent without modifying each tool individually.

Usage:
    from callback_handler import FirewallCallbackHandler
    from ai_firewall import AIFirewall

    fw = AIFirewall(api_key="...", project_id="...")
    handler = FirewallCallbackHandler(fw, agent_name="my_agent")

    # Use with any LangChain component
    result = agent.invoke({"input": "..."}, config={"callbacks": [handler]})
"""

import json
from typing import Any, Dict, Optional, Union

from ai_firewall import AIFirewall


class FirewallCallbackHandler:
    """
    LangChain callback handler that validates tool calls through AI Firewall.

    This handler intercepts tool executions before they run and validates
    them against your firewall policies. If an action is blocked, it raises
    a PermissionError that the agent can catch and handle.

    Attributes:
        firewall: AIFirewall client instance
        agent_name: Name of the agent (used in audit logs)
        raise_on_block: Whether to raise exception on blocked actions
        blocked_actions: List of blocked action details (for inspection)

    Example:
        fw = AIFirewall(api_key="...", project_id="...")
        handler = FirewallCallbackHandler(fw, "invoice_agent")

        # With AgentExecutor
        agent_executor = AgentExecutor(agent=agent, tools=tools)
        result = agent_executor.invoke(
            {"input": "Pay invoice #123"},
            config={"callbacks": [handler]}
        )

        # Check blocked actions
        for action in handler.blocked_actions:
            print(f"Blocked: {action['tool']} - {action['reason']}")
    """

    def __init__(
        self,
        firewall: AIFirewall,
        agent_name: str = "langchain_agent",
        raise_on_block: bool = True,
    ):
        """
        Initialize the callback handler.

        Args:
            firewall: AIFirewall client instance
            agent_name: Name of the agent for audit logging
            raise_on_block: If True, raises PermissionError on blocked actions.
                           If False, logs the block but allows execution to continue.
        """
        self.firewall = firewall
        self.agent_name = agent_name
        self.raise_on_block = raise_on_block
        self.blocked_actions: list[Dict[str, Any]] = []
        self._allowed_actions: list[Dict[str, Any]] = []

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Optional[Any] = None,
        parent_run_id: Optional[Any] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Called when a tool starts running.

        This method validates the tool execution through the AI Firewall.
        If the action is blocked, it raises a PermissionError (if raise_on_block=True)
        or logs the block and continues (if raise_on_block=False).

        Args:
            serialized: Serialized tool information including name
            input_str: String representation of tool input
            run_id: Unique identifier for this run
            parent_run_id: Parent run identifier
            tags: Tags associated with this run
            metadata: Additional metadata
            inputs: Structured input dictionary (preferred over input_str)
            **kwargs: Additional keyword arguments
        """
        tool_name = serialized.get("name", "unknown_tool")

        # Build params from inputs or parse input_str
        params = self._extract_params(input_str, inputs)

        # Validate with firewall
        result = self.firewall.execute(
            agent_name=self.agent_name,
            action_type=tool_name,
            params=params,
        )

        action_info = {
            "tool": tool_name,
            "params": params,
            "action_id": result.action_id,
            "allowed": result.allowed,
            "reason": result.reason,
        }

        if not result.allowed:
            self.blocked_actions.append(action_info)

            if self.raise_on_block:
                raise PermissionError(
                    f"Action blocked by AI Firewall: {result.reason} "
                    f"(action_id: {result.action_id})"
                )
        else:
            self._allowed_actions.append(action_info)

    def _extract_params(
        self,
        input_str: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract parameters from tool input.

        Tries to parse structured inputs first, falls back to input_str.

        Args:
            input_str: String representation of input
            inputs: Structured input dictionary

        Returns:
            Dictionary of parameters
        """
        # Prefer structured inputs
        if inputs:
            return dict(inputs)

        # Try to parse input_str as JSON
        try:
            parsed = json.loads(input_str)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        # Fall back to wrapping the string
        return {"input": input_str}

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Optional[Any] = None,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool ends. No validation needed here."""
        pass

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: Optional[Any] = None,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool errors. Log if it was a firewall block."""
        pass

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all validated actions.

        Returns:
            Dictionary with allowed and blocked action counts and details
        """
        return {
            "total_actions": len(self._allowed_actions) + len(self.blocked_actions),
            "allowed_count": len(self._allowed_actions),
            "blocked_count": len(self.blocked_actions),
            "allowed_actions": self._allowed_actions,
            "blocked_actions": self.blocked_actions,
        }

    def reset(self) -> None:
        """Reset the tracked actions."""
        self.blocked_actions = []
        self._allowed_actions = []


# For compatibility with LangChain's callback system
try:
    from langchain_core.callbacks import BaseCallbackHandler

    class LangChainFirewallHandler(BaseCallbackHandler, FirewallCallbackHandler):
        """
        Full LangChain-compatible callback handler with AI Firewall protection.

        This class inherits from both BaseCallbackHandler (for LangChain compatibility)
        and FirewallCallbackHandler (for firewall logic).

        Usage:
            from callback_handler import LangChainFirewallHandler
            from ai_firewall import AIFirewall

            fw = AIFirewall(api_key="...", project_id="...")
            handler = LangChainFirewallHandler(fw, "my_agent")

            result = agent.invoke({"input": "..."}, config={"callbacks": [handler]})
        """

        def __init__(
            self,
            firewall: AIFirewall,
            agent_name: str = "langchain_agent",
            raise_on_block: bool = True,
        ):
            BaseCallbackHandler.__init__(self)
            FirewallCallbackHandler.__init__(self, firewall, agent_name, raise_on_block)

except ImportError:
    # LangChain not installed, only basic handler available
    LangChainFirewallHandler = None  # type: ignore
