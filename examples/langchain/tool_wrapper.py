"""
LangChain Tool Wrapper with AI Firewall Protection

This module provides a decorator to wrap LangChain tools with AI Firewall
validation, ensuring actions are checked against policies before execution.

Usage:
    from tool_wrapper import protected_tool
    from ai_firewall import AIFirewall

    fw = AIFirewall(api_key="...", project_id="...")

    @protected_tool(fw, "my_agent")
    def send_email(to: str, subject: str, body: str) -> str:
        '''Send an email to a recipient.'''
        # This only runs if firewall allows
        return f"Email sent to {to}"
"""

from functools import wraps
from typing import Any, Callable, Optional

from ai_firewall import AIFirewall


def protected_tool(
    firewall: AIFirewall,
    agent_name: str,
    action_type: Optional[str] = None,
):
    """
    Decorator factory to wrap LangChain tools with AI Firewall protection.

    Args:
        firewall: AIFirewall client instance
        agent_name: Name of the agent performing the action
        action_type: Optional override for action type (defaults to function name)

    Returns:
        Decorator that wraps the function with firewall validation

    Example:
        @protected_tool(fw, "invoice_agent")
        def pay_invoice(vendor: str, amount: float) -> str:
            '''Pay an invoice to a vendor.'''
            return f"Paid ${amount} to {vendor}"

        # With custom action type
        @protected_tool(fw, "email_agent", action_type="send_notification")
        def send_email(to: str, message: str) -> str:
            '''Send an email notification.'''
            return f"Sent to {to}"
    """

    def decorator(func: Callable) -> Callable:
        # Use function name as action_type if not specified
        tool_action_type = action_type or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Build params from kwargs (LangChain typically passes kwargs)
            params = kwargs.copy()

            # If positional args, try to map them to function parameters
            if args:
                import inspect

                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        params[param_names[i]] = arg

            # Validate with firewall
            result = firewall.execute(
                agent_name=agent_name,
                action_type=tool_action_type,
                params=params,
            )

            if not result.allowed:
                # Return blocked message (agent can see this)
                return f"Action blocked by policy: {result.reason}"

            # Execute the original function
            return func(*args, **kwargs)

        # Preserve function metadata for LangChain
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    return decorator


def create_protected_tool(
    firewall: AIFirewall,
    agent_name: str,
    func: Callable,
    action_type: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
):
    """
    Create a LangChain Tool with AI Firewall protection.

    This function wraps an existing function and returns a LangChain Tool
    that validates actions through the firewall before execution.

    Args:
        firewall: AIFirewall client instance
        agent_name: Name of the agent performing the action
        func: The function to wrap
        action_type: Optional override for action type (defaults to function name)
        name: Optional tool name (defaults to function name)
        description: Optional description (defaults to function docstring)

    Returns:
        A LangChain Tool with firewall protection

    Example:
        def pay_invoice(vendor: str, amount: float) -> str:
            return f"Paid ${amount} to {vendor}"

        tool = create_protected_tool(
            firewall=fw,
            agent_name="invoice_agent",
            func=pay_invoice,
            description="Pay an invoice to a vendor"
        )
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        raise ImportError(
            "langchain-core is required. Install with: pip install langchain-core"
        )

    tool_name = name or func.__name__
    tool_description = description or func.__doc__ or f"Execute {tool_name}"
    tool_action_type = action_type or tool_name

    @wraps(func)
    def protected_func(*args, **kwargs) -> Any:
        # Build params
        params = kwargs.copy()
        if args:
            import inspect

            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())
            for i, arg in enumerate(args):
                if i < len(param_names):
                    params[param_names[i]] = arg

        # Validate
        result = firewall.execute(
            agent_name=agent_name,
            action_type=tool_action_type,
            params=params,
        )

        if not result.allowed:
            return f"Action blocked by policy: {result.reason}"

        return func(*args, **kwargs)

    return StructuredTool.from_function(
        func=protected_func,
        name=tool_name,
        description=tool_description,
    )
