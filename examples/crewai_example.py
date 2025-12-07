"""
CrewAI Integration Example with AI Firewall

This example shows how to wrap CrewAI agent actions with the AI Firewall
to validate actions before execution.

Prerequisites:
    pip install crewai ai-firewall

Usage:
    1. Start the AI Firewall server
    2. Create a project and get your API key
    3. Set up a policy for your project
    4. Run this script
"""

from functools import wraps
from typing import Callable, Any

# Note: Uncomment these when you have crewai installed
# from crewai import Agent, Task, Crew

from ai_firewall import AIFirewall, ActionBlockedError


# ============================================================================
# Option 1: Decorator Pattern (Recommended)
# ============================================================================

def firewall_guard(
    firewall: AIFirewall,
    agent_name: str,
    action_type: str,
):
    """
    Decorator that validates actions through AI Firewall before execution.

    Usage:
        @firewall_guard(fw, "invoice_agent", "pay_invoice")
        def pay_invoice(vendor: str, amount: float, currency: str):
            # This only runs if firewall allows
            process_payment(vendor, amount, currency)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Extract params from function arguments
            params = kwargs.copy()

            # Validate with firewall
            result = firewall.execute(agent_name, action_type, params)

            if not result.allowed:
                print(f"🚫 Action blocked: {result.reason}")
                print(f"   Action ID: {result.action_id}")
                return None

            print(f"✅ Action allowed (ID: {result.action_id})")
            return func(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# Option 2: Context Manager Pattern
# ============================================================================

class GuardedAction:
    """
    Context manager for validating actions.

    Usage:
        with GuardedAction(fw, "agent", "action", params) as guard:
            if guard.allowed:
                do_something()
    """

    def __init__(
        self,
        firewall: AIFirewall,
        agent_name: str,
        action_type: str,
        params: dict,
    ):
        self.firewall = firewall
        self.agent_name = agent_name
        self.action_type = action_type
        self.params = params
        self.result = None

    def __enter__(self):
        self.result = self.firewall.execute(
            self.agent_name,
            self.action_type,
            self.params,
        )
        return self

    def __exit__(self, *args):
        pass

    @property
    def allowed(self) -> bool:
        return self.result.allowed if self.result else False

    @property
    def reason(self) -> str | None:
        return self.result.reason if self.result else None

    @property
    def action_id(self) -> str | None:
        return self.result.action_id if self.result else None


# ============================================================================
# Option 3: Wrapper Function Pattern
# ============================================================================

def guarded_execute(
    firewall: AIFirewall,
    agent_name: str,
    action_type: str,
    params: dict,
    action_fn: Callable,
) -> Any:
    """
    Validate an action and execute if allowed.

    Args:
        firewall: AI Firewall client
        agent_name: Name of the agent
        action_type: Type of action
        params: Action parameters
        action_fn: Function to call if action is allowed

    Returns:
        Result of action_fn if allowed, None if blocked
    """
    result = firewall.execute(agent_name, action_type, params)

    if result.allowed:
        print(f"✅ Action allowed (ID: {result.action_id})")
        return action_fn(params)
    else:
        print(f"🚫 Action blocked: {result.reason}")
        return None


# ============================================================================
# Example: CrewAI Finance Bot with Firewall Protection
# ============================================================================

def main():
    """Demo of AI Firewall with a simulated finance agent."""

    # Initialize firewall client
    # Replace with your actual credentials
    fw = AIFirewall(
        api_key="af_your_api_key_here",
        project_id="finbot-prod",
        base_url="http://localhost:8000",
    )

    # Example 1: Using decorator pattern
    print("\n" + "=" * 60)
    print("Example 1: Decorator Pattern")
    print("=" * 60)

    @firewall_guard(fw, "invoice_agent", "pay_invoice")
    def pay_invoice(vendor: str, amount: float, currency: str = "USD"):
        """Process an invoice payment."""
        print(f"   💰 Processing payment: ${amount} {currency} to {vendor}")
        return {"status": "paid", "vendor": vendor, "amount": amount}

    # This should be allowed (amount under limit)
    pay_invoice(vendor="Acme Corp", amount=5000, currency="USD")

    # This might be blocked (amount over limit, depending on your policy)
    pay_invoice(vendor="Big Vendor", amount=50000, currency="USD")

    # Example 2: Using context manager
    print("\n" + "=" * 60)
    print("Example 2: Context Manager Pattern")
    print("=" * 60)

    transfer_params = {
        "from_account": "checking",
        "to_account": "savings",
        "amount": 1000,
    }

    with GuardedAction(fw, "transfer_agent", "internal_transfer", transfer_params) as guard:
        if guard.allowed:
            print(f"   💸 Transferring ${transfer_params['amount']}")
            print(f"   Action ID: {guard.action_id}")
        else:
            print(f"   Transfer blocked: {guard.reason}")

    # Example 3: Using wrapper function
    print("\n" + "=" * 60)
    print("Example 3: Wrapper Function Pattern")
    print("=" * 60)

    def send_email(params):
        print(f"   📧 Sending email to {params['recipient']}")
        return {"sent": True}

    guarded_execute(
        firewall=fw,
        agent_name="notification_agent",
        action_type="send_email",
        params={"recipient": "user@example.com", "subject": "Report Ready"},
        action_fn=send_email,
    )

    # Example 4: Strict mode (raises exception)
    print("\n" + "=" * 60)
    print("Example 4: Strict Mode")
    print("=" * 60)

    fw_strict = AIFirewall(
        api_key="af_your_api_key_here",
        project_id="finbot-prod",
        base_url="http://localhost:8000",
        strict=True,
    )

    try:
        # This will raise ActionBlockedError if blocked
        result = fw_strict.execute(
            "invoice_agent",
            "pay_invoice",
            {"vendor": "Risky Vendor", "amount": 100000},
        )
        print(f"   Action allowed: {result.action_id}")
    except ActionBlockedError as e:
        print(f"   ⚠️  Caught blocked action: {e.reason}")

    # Cleanup
    fw.close()
    fw_strict.close()


# ============================================================================
# CrewAI-Specific Integration (when crewai is installed)
# ============================================================================

"""
# Uncomment this section when using with actual CrewAI

from crewai import Agent, Task, Crew

class FirewallProtectedAgent:
    '''
    Wrapper around CrewAI Agent that validates actions through AI Firewall.
    '''

    def __init__(self, agent: Agent, firewall: AIFirewall):
        self.agent = agent
        self.firewall = firewall

    def execute_task(self, task: Task, action_type: str, params: dict) -> Any:
        '''Execute a task with firewall validation.'''
        result = self.firewall.execute(
            agent_name=self.agent.role,
            action_type=action_type,
            params=params,
        )

        if not result.allowed:
            raise ActionBlockedError(result.reason, result.action_id)

        # Execute the actual CrewAI task
        return self.agent.execute_task(task)


# Example CrewAI setup with firewall
def create_protected_crew():
    fw = AIFirewall(api_key="...", project_id="...")

    # Create agents
    researcher = Agent(
        role="Researcher",
        goal="Research financial data",
        backstory="Expert financial analyst",
    )

    writer = Agent(
        role="Writer",
        goal="Write financial reports",
        backstory="Expert technical writer",
    )

    # Wrap with firewall protection
    protected_researcher = FirewallProtectedAgent(researcher, fw)
    protected_writer = FirewallProtectedAgent(writer, fw)

    # Create tasks and crew as usual
    # ...
"""


if __name__ == "__main__":
    print("AI Firewall + CrewAI Integration Examples")
    print("=" * 60)
    print("Note: Update the API key and project_id before running")
    print("=" * 60)

    # Uncomment to run examples (requires server running + valid credentials)
    # main()

    print("\nSee the code for integration patterns:")
    print("1. Decorator pattern - @firewall_guard")
    print("2. Context manager - GuardedAction")
    print("3. Wrapper function - guarded_execute")
    print("4. Strict mode - raises ActionBlockedError")
