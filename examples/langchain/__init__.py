"""
LangChain Integration for AI Firewall

This package provides multiple patterns for integrating AI Firewall
with LangChain agents.

Patterns:
    - tool_wrapper: Decorator to protect individual tools
    - callback_handler: Intercept all tool calls
    - protected_agent: Wrap entire AgentExecutor

Usage:
    from examples.langchain.tool_wrapper import protected_tool
    from examples.langchain.callback_handler import FirewallCallbackHandler
    from examples.langchain.protected_agent import ProtectedAgentExecutor
"""

from .tool_wrapper import protected_tool, create_protected_tool
from .callback_handler import FirewallCallbackHandler

try:
    from .callback_handler import LangChainFirewallHandler
except ImportError:
    LangChainFirewallHandler = None

from .protected_agent import ProtectedAgentExecutor, create_protected_agent

__all__ = [
    "protected_tool",
    "create_protected_tool",
    "FirewallCallbackHandler",
    "LangChainFirewallHandler",
    "ProtectedAgentExecutor",
    "create_protected_agent",
]
