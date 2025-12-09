"""
LangChain Agent with AI Firewall Protection

This module creates a LangChain agent that uses tools protected
by the AI Firewall. All tool executions are validated against
policies before running.
"""

import os
import sys
from typing import List, Optional

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ai_firewall import AIFirewall

# Import our integration modules
from examples.langchain.tool_wrapper import create_protected_tool
from examples.langchain.callback_handler import LangChainFirewallHandler
from examples.langchain.protected_agent import ProtectedAgentExecutor

# Import tool functions
from tools import pay_invoice, send_email, search_database, execute_sql


def create_firewall_client(
    api_key: Optional[str] = None,
    project_id: Optional[str] = None,
    base_url: Optional[str] = None,
) -> AIFirewall:
    """Create an AI Firewall client from environment or parameters."""
    return AIFirewall(
        api_key=api_key or os.getenv("FIREWALL_API_KEY", ""),
        project_id=project_id or os.getenv("FIREWALL_PROJECT_ID", "langchain-demo"),
        base_url=base_url or os.getenv("FIREWALL_URL", "http://localhost:8000"),
    )


def create_protected_tools(firewall: AIFirewall, agent_name: str = "langchain_agent"):
    """
    Create LangChain tools wrapped with firewall protection.

    This uses Pattern 1: Tool Wrapper
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        raise ImportError("langchain-core required. Install: pip install langchain-core")

    tools = [
        create_protected_tool(
            firewall=firewall,
            agent_name=agent_name,
            func=pay_invoice,
            name="pay_invoice",
            description="Pay an invoice to a vendor. Requires invoice_id, vendor, amount, and currency."
        ),
        create_protected_tool(
            firewall=firewall,
            agent_name=agent_name,
            func=send_email,
            name="send_email",
            description="Send an email. Requires to, subject, and body. Optional cc."
        ),
        create_protected_tool(
            firewall=firewall,
            agent_name=agent_name,
            func=search_database,
            name="search_database",
            description="Search the database. Requires table name (customers or invoices). Optional query."
        ),
        create_protected_tool(
            firewall=firewall,
            agent_name=agent_name,
            func=execute_sql,
            name="execute_sql",
            description="Execute raw SQL query. DANGEROUS - should be blocked by firewall."
        ),
    ]

    return tools


def create_agent_with_callback(
    firewall: AIFirewall,
    agent_name: str = "langchain_agent",
    model: str = "gpt-4",
):
    """
    Create a LangChain agent using Pattern 2: Callback Handler.

    The callback handler intercepts all tool calls and validates
    them through the firewall.
    """
    try:
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_tool_calling_agent, AgentExecutor
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as e:
        raise ImportError(f"LangChain dependencies required: {e}")

    # Create regular tools (not wrapped)
    @tool
    def pay_invoice_tool(invoice_id: str, vendor: str, amount: float, currency: str = "USD") -> str:
        """Pay an invoice to a vendor."""
        return pay_invoice(invoice_id, vendor, amount, currency)

    @tool
    def send_email_tool(to: str, subject: str, body: str, cc: str = None) -> str:
        """Send an email to a recipient."""
        return send_email(to, subject, body, cc)

    @tool
    def search_database_tool(table: str, query: str = None) -> str:
        """Search the database for records."""
        return search_database(table, query)

    @tool
    def execute_sql_tool(query: str) -> str:
        """Execute a raw SQL query. DANGEROUS."""
        return execute_sql(query)

    tools = [pay_invoice_tool, send_email_tool, search_database_tool, execute_sql_tool]

    # Create LLM and agent
    llm = ChatOpenAI(model=model, temperature=0)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful finance assistant that can:
- Pay invoices (pay_invoice)
- Send emails (send_email)
- Search the database (search_database)
- Execute SQL queries (execute_sql) - but this should be avoided

Always confirm actions before taking them. If an action is blocked,
explain why and suggest alternatives."""),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # Create firewall callback handler
    handler = LangChainFirewallHandler(firewall, agent_name=agent_name)

    return executor, handler


def create_protected_agent(
    firewall: AIFirewall,
    agent_name: str = "langchain_agent",
    model: str = "gpt-4",
) -> ProtectedAgentExecutor:
    """
    Create a LangChain agent using Pattern 3: Protected Executor.

    This wraps the entire AgentExecutor for automatic protection.
    """
    executor, _ = create_agent_with_callback(firewall, agent_name, model)

    return ProtectedAgentExecutor(
        executor=executor,
        firewall=firewall,
        agent_name=agent_name,
        raise_on_block=True,
    )


# For running standalone
if __name__ == "__main__":
    print("LangChain Agent with AI Firewall")
    print("=" * 50)
    print()
    print("This module provides functions to create protected agents.")
    print("See demo.py for usage examples.")
    print()
    print("Available functions:")
    print("  - create_firewall_client(): Create AIFirewall client")
    print("  - create_protected_tools(): Create tools with Pattern 1")
    print("  - create_agent_with_callback(): Create agent with Pattern 2")
    print("  - create_protected_agent(): Create agent with Pattern 3")
