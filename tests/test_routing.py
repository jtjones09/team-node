"""Tests that the orchestrator routes and doesn't answer domain questions."""

import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import crewai  # noqa: F401
    import langchain_anthropic  # noqa: F401
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "crewai/langchain-anthropic not installed")
class TestOrchestratorRouting(unittest.TestCase):
    """Verify the orchestrator is configured as a pure router."""

    @patch("agents.orchestrator.ChatAnthropic")
    def test_orchestrator_allows_delegation(self, mock_llm_cls):
        from agents.orchestrator import create_orchestrator
        agent = create_orchestrator()
        self.assertTrue(agent.allow_delegation)

    @patch("agents.orchestrator.ChatAnthropic")
    def test_orchestrator_has_no_domain_tools(self, mock_llm_cls):
        from agents.orchestrator import create_orchestrator
        agent = create_orchestrator()
        self.assertEqual(len(agent.tools), 0)

    @patch("agents.orchestrator.ChatAnthropic")
    def test_orchestrator_backstory_is_routing_focused(self, mock_llm_cls):
        from agents.orchestrator import create_orchestrator, ORCHESTRATOR_BACKSTORY
        self.assertIn("route", ORCHESTRATOR_BACKSTORY.lower())
        self.assertIn("do NOT", ORCHESTRATOR_BACKSTORY)
        self.assertIn("Answer domain questions yourself", ORCHESTRATOR_BACKSTORY)

    @patch("agents.orchestrator.ChatAnthropic")
    def test_orchestrator_backstory_lists_all_agents(self, mock_llm_cls):
        from agents.orchestrator import ORCHESTRATOR_BACKSTORY
        for agent_name in ["Marketing", "Sales", "Engineer", "Architect",
                           "Security", "Data/Analytics", "Planner/Researcher"]:
            self.assertIn(agent_name, ORCHESTRATOR_BACKSTORY,
                          f"Orchestrator backstory missing agent: {agent_name}")


if __name__ == "__main__":
    unittest.main()
