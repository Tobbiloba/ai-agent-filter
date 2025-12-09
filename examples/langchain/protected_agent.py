"""
Protected Agent Executor with AI Firewall

This module provides a wrapper around LangChain's AgentExecutor that
automatically validates all tool calls through the AI Firewall.

This is the highest-level integration - wrap your entire agent once
and all tool calls are automatically protected.

Usage:
    from protected_agent import ProtectedAgentExecutor
    from ai_firewall import AIFirewall

    fw = AIFirewall(api_key="...", project_id="...")

    # Create your normal agent
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools)

    # Wrap with firewall protection
    protected = ProtectedAgentExecutor(agent_executor, fw, "my_agent")

    # Use normally - all tool calls are now validated
    result = protected.invoke({"input": "Pay invoice #123 for $500"})
"""

from typing import Any, Dict, List, Optional

from ai_firewall import AIFirewall

from .callback_handler import FirewallCallbackHandler


class ProtectedAgentExecutor:
    """
    Wrapper around LangChain AgentExecutor with AI Firewall protection.

    This class wraps an existing AgentExecutor and injects a firewall
    callback handler that validates all tool calls before execution.

    Attributes:
        executor: The wrapped AgentExecutor
        firewall: AIFirewall client instance
        agent_name: Name of the agent for audit logging
        handler: The FirewallCallbackHandler instance

    Example:
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain_openai import ChatOpenAI
        from ai_firewall import AIFirewall

        # Create your agent normally
        llm = ChatOpenAI(model="gpt-4")
        agent = create_react_agent(llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools)

        # Wrap with firewall
        fw = AIFirewall(api_key="...", project_id="...")
        protected = ProtectedAgentExecutor(executor, fw, "finance_agent")

        # Use normally
        result = protected.invoke({"input": "Process payment of $500"})

        # Check what was blocked
        print(protected.handler.blocked_actions)
    """

    def __init__(
        self,
        executor: Any,  # AgentExecutor type, but avoiding import
        firewall: AIFirewall,
        agent_name: str = "langchain_agent",
        raise_on_block: bool = True,
    ):
        """
        Initialize the protected agent executor.

        Args:
            executor: LangChain AgentExecutor instance
            firewall: AIFirewall client instance
            agent_name: Name for audit logging
            raise_on_block: If True, blocked actions raise PermissionError
        """
        self.executor = executor
        self.firewall = firewall
        self.agent_name = agent_name
        self.raise_on_block = raise_on_block
        self.handler = FirewallCallbackHandler(
            firewall=firewall,
            agent_name=agent_name,
            raise_on_block=raise_on_block,
        )

    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Invoke the agent with firewall protection.

        All tool calls will be validated through the AI Firewall
        before execution.

        Args:
            input: Input dictionary (e.g., {"input": "user message"})
            config: Optional config dictionary
            **kwargs: Additional arguments passed to executor

        Returns:
            Agent output dictionary

        Raises:
            PermissionError: If a tool call is blocked (when raise_on_block=True)
        """
        # Reset handler for fresh tracking
        self.handler.reset()

        # Merge our handler with any existing callbacks
        config = config or {}
        existing_callbacks = config.get("callbacks", [])
        config["callbacks"] = existing_callbacks + [self.handler]

        return self.executor.invoke(input, config=config, **kwargs)

    async def ainvoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Async invoke the agent with firewall protection.

        Args:
            input: Input dictionary
            config: Optional config dictionary
            **kwargs: Additional arguments

        Returns:
            Agent output dictionary
        """
        self.handler.reset()
        config = config or {}
        existing_callbacks = config.get("callbacks", [])
        config["callbacks"] = existing_callbacks + [self.handler]

        return await self.executor.ainvoke(input, config=config, **kwargs)

    def stream(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """
        Stream agent output with firewall protection.

        Args:
            input: Input dictionary
            config: Optional config dictionary
            **kwargs: Additional arguments

        Yields:
            Agent output chunks
        """
        self.handler.reset()
        config = config or {}
        existing_callbacks = config.get("callbacks", [])
        config["callbacks"] = existing_callbacks + [self.handler]

        yield from self.executor.stream(input, config=config, **kwargs)

    def get_blocked_actions(self) -> List[Dict[str, Any]]:
        """Get list of blocked actions from the last invocation."""
        return self.handler.blocked_actions

    def get_allowed_actions(self) -> List[Dict[str, Any]]:
        """Get list of allowed actions from the last invocation."""
        return self.handler._allowed_actions

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all validated actions from the last invocation."""
        return self.handler.get_summary()


def create_protected_agent(
    agent: Any,
    tools: List[Any],
    firewall: AIFirewall,
    agent_name: str = "langchain_agent",
    raise_on_block: bool = True,
    verbose: bool = False,
    **executor_kwargs: Any,
) -> ProtectedAgentExecutor:
    """
    Create a protected agent executor in one step.

    This is a convenience function that creates an AgentExecutor and
    wraps it with firewall protection.

    Args:
        agent: LangChain agent (e.g., from create_react_agent)
        tools: List of tools for the agent
        firewall: AIFirewall client instance
        agent_name: Name for audit logging
        raise_on_block: If True, blocked actions raise PermissionError
        verbose: Whether to enable verbose output
        **executor_kwargs: Additional kwargs for AgentExecutor

    Returns:
        ProtectedAgentExecutor instance

    Example:
        from langchain.agents import create_react_agent
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4")
        agent = create_react_agent(llm, tools, prompt)

        fw = AIFirewall(api_key="...", project_id="...")
        protected = create_protected_agent(
            agent=agent,
            tools=tools,
            firewall=fw,
            agent_name="finance_agent",
            verbose=True
        )

        result = protected.invoke({"input": "Process payment"})
    """
    try:
        from langchain.agents import AgentExecutor
    except ImportError:
        raise ImportError(
            "langchain is required. Install with: pip install langchain"
        )

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        **executor_kwargs,
    )

    return ProtectedAgentExecutor(
        executor=executor,
        firewall=firewall,
        agent_name=agent_name,
        raise_on_block=raise_on_block,
    )
