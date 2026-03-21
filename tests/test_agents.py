"""Tests that each agent stays in its lane — correct config, tools, and isolation."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import crewai  # noqa: F401
    import langchain_anthropic  # noqa: F401
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

from config import TEMPERATURES, MODEL_SONNET, MODEL_OPUS


@unittest.skipUnless(HAS_DEPS, "crewai/langchain-anthropic not installed")
class TestAgentConfiguration(unittest.TestCase):
    """Verify agent temperature, model, and tool assignments."""

    def _mock_lens_and_logger(self, domain: str):
        lens = MagicMock()
        lens.domain = domain
        lens.retrieve.return_value = []
        lens.store.return_value = "mock-id"
        logger = MagicMock()
        return lens, logger

    @patch("agents.orchestrator.ChatAnthropic")
    def test_orchestrator_has_no_tools(self, mock_llm_cls):
        from agents.orchestrator import create_orchestrator
        agent = create_orchestrator()
        self.assertEqual(agent.tools, [])
        self.assertEqual(agent.role, "Orchestrator")

    @patch("agents.orchestrator.ChatAnthropic")
    def test_orchestrator_uses_sonnet(self, mock_llm_cls):
        from agents.orchestrator import create_orchestrator
        create_orchestrator()
        call_kwargs = mock_llm_cls.call_args[1]
        self.assertEqual(call_kwargs["model"], MODEL_SONNET)
        self.assertAlmostEqual(call_kwargs["temperature"], TEMPERATURES["orchestrator"])

    @patch("agents.marketing.ChatAnthropic")
    def test_marketing_has_voice_in_backstory(self, mock_llm_cls):
        from agents.marketing import create_marketing_agent
        lens, logger = self._mock_lens_and_logger("marketing")
        agent = create_marketing_agent(lens, logger)
        self.assertIn("Voice Constraints", agent.backstory)
        self.assertIn("No em dashes", agent.backstory)

    @patch("agents.sales.ChatAnthropic")
    def test_sales_has_voice_in_backstory(self, mock_llm_cls):
        from agents.sales import create_sales_agent
        lens, logger = self._mock_lens_and_logger("sales")
        agent = create_sales_agent(lens, logger)
        self.assertIn("Voice Constraints", agent.backstory)

    @patch("agents.engineer.ChatAnthropic")
    def test_engineer_has_code_tools(self, mock_llm_cls):
        from agents.engineer import create_engineer_agent
        lens, logger = self._mock_lens_and_logger("engineer")
        agent = create_engineer_agent(lens, logger)
        tool_names = [t.name for t in agent.tools]
        self.assertIn("Run Python Code", tool_names)
        self.assertIn("Analyze Code File", tool_names)

    @patch("agents.engineer.ChatAnthropic")
    def test_engineer_uses_low_temperature(self, mock_llm_cls):
        from agents.engineer import create_engineer_agent
        lens, logger = self._mock_lens_and_logger("engineer")
        create_engineer_agent(lens, logger)
        call_kwargs = mock_llm_cls.call_args[1]
        self.assertAlmostEqual(call_kwargs["temperature"], 0.2)

    @patch("agents.security.ChatAnthropic")
    def test_security_has_code_review_tools(self, mock_llm_cls):
        from agents.security import create_security_agent
        lens, logger = self._mock_lens_and_logger("security")
        agent = create_security_agent(lens, logger)
        tool_names = [t.name for t in agent.tools]
        self.assertIn("Analyze Code File", tool_names)
        self.assertIn("Web Search", tool_names)

    @patch("agents.planner_researcher.ChatAnthropic")
    def test_planner_uses_opus(self, mock_llm_cls):
        from agents.planner_researcher import create_planner_researcher_agent
        lens, logger = self._mock_lens_and_logger("planner_researcher")
        create_planner_researcher_agent(lens, logger)
        call_kwargs = mock_llm_cls.call_args[1]
        self.assertEqual(call_kwargs["model"], MODEL_OPUS)
        self.assertAlmostEqual(call_kwargs["temperature"], 0.5)

    @patch("agents.data_analytics.ChatAnthropic")
    def test_data_analytics_has_python_execution(self, mock_llm_cls):
        from agents.data_analytics import create_data_analytics_agent
        lens, logger = self._mock_lens_and_logger("data_analytics")
        agent = create_data_analytics_agent(lens, logger)
        tool_names = [t.name for t in agent.tools]
        self.assertIn("Run Python Code", tool_names)


if __name__ == "__main__":
    unittest.main()
