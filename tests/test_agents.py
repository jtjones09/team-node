"""Tests that each agent stays in its lane — correct config, tools, and isolation."""

import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set a fake key so LLM objects can be constructed without a real API key
os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-for-tests")

try:
    import crewai  # noqa: F401
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

from config import TEMPERATURES, MODEL_SONNET, MODEL_OPUS


@unittest.skipUnless(HAS_DEPS, "crewai not installed")
class TestAgentConfiguration(unittest.TestCase):
    """Verify agent temperature, model, and tool assignments."""

    def _mock_lens_and_logger(self, domain: str):
        lens = MagicMock()
        lens.domain = domain
        lens.retrieve.return_value = []
        lens.store.return_value = "mock-id"
        logger = MagicMock()
        return lens, logger

    def test_orchestrator_has_no_tools(self):
        from agents.orchestrator import create_orchestrator
        agent = create_orchestrator()
        self.assertEqual(agent.tools, [])
        self.assertEqual(agent.role, "Orchestrator")

    def test_orchestrator_uses_sonnet(self):
        from agents.orchestrator import create_orchestrator
        agent = create_orchestrator()
        self.assertIn("claude-sonnet", agent.llm.model)

    def test_marketing_has_voice_in_backstory(self):
        from agents.marketing import create_marketing_agent
        lens, logger = self._mock_lens_and_logger("marketing")
        agent = create_marketing_agent(lens, logger)
        self.assertIn("Voice Constraints", agent.backstory)
        self.assertIn("No em dashes", agent.backstory)

    def test_sales_has_voice_in_backstory(self):
        from agents.sales import create_sales_agent
        lens, logger = self._mock_lens_and_logger("sales")
        agent = create_sales_agent(lens, logger)
        self.assertIn("Voice Constraints", agent.backstory)

    def test_engineer_has_code_tools(self):
        from agents.engineer import create_engineer_agent
        lens, logger = self._mock_lens_and_logger("engineer")
        agent = create_engineer_agent(lens, logger)
        tool_names = [t.name for t in agent.tools]
        self.assertIn("Run Python Code", tool_names)
        self.assertIn("Analyze Code File", tool_names)

    def test_engineer_uses_low_temperature(self):
        from agents.engineer import create_engineer_agent
        lens, logger = self._mock_lens_and_logger("engineer")
        agent = create_engineer_agent(lens, logger)
        self.assertAlmostEqual(agent.llm.temperature, 0.2)

    def test_security_has_code_review_tools(self):
        from agents.security import create_security_agent
        lens, logger = self._mock_lens_and_logger("security")
        agent = create_security_agent(lens, logger)
        tool_names = [t.name for t in agent.tools]
        self.assertIn("Analyze Code File", tool_names)
        self.assertIn("Web Search", tool_names)

    def test_planner_uses_opus(self):
        from agents.planner_researcher import create_planner_researcher_agent
        lens, logger = self._mock_lens_and_logger("planner_researcher")
        agent = create_planner_researcher_agent(lens, logger)
        self.assertIn("claude-opus", agent.llm.model)
        self.assertAlmostEqual(agent.llm.temperature, 0.5)

    def test_data_analytics_has_python_execution(self):
        from agents.data_analytics import create_data_analytics_agent
        lens, logger = self._mock_lens_and_logger("data_analytics")
        agent = create_data_analytics_agent(lens, logger)
        tool_names = [t.name for t in agent.tools]
        self.assertIn("Run Python Code", tool_names)


if __name__ == "__main__":
    unittest.main()
