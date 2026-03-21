"""End-to-end tests — verify full crew assembly and configuration."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ANTHROPIC_API_KEY", "fake-key-for-tests")

try:
    import crewai  # noqa: F401
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "crewai not installed")
class TestCrewAssembly(unittest.TestCase):
    """Test that the crew assembles correctly with all agents."""

    @patch("crew.ChromaFallback")
    def test_crew_has_eight_agents(self, chroma_mock):
        from crew import build_crew
        chroma_instance = MagicMock()
        chroma_instance.retrieve.return_value = []
        chroma_instance.store.return_value = "mock-id"
        chroma_mock.return_value = chroma_instance

        crew = build_crew("test goal")
        # 7 domain agents in agents list (orchestrator is manager_agent, separate)
        self.assertEqual(len(crew.agents), 7)

    @patch("crew.ChromaFallback")
    def test_crew_agent_roles(self, chroma_mock):
        from crew import build_crew
        chroma_instance = MagicMock()
        chroma_instance.retrieve.return_value = []
        chroma_instance.store.return_value = "mock-id"
        chroma_mock.return_value = chroma_instance

        crew = build_crew("test goal")
        roles = [a.role for a in crew.agents]
        # Orchestrator is manager_agent, not in agents list
        self.assertEqual(crew.manager_agent.role, "Orchestrator")
        expected_roles = [
            "Marketing Specialist",
            "Sales Specialist",
            "Engineer",
            "Architect",
            "Planner/Researcher",
            "Security Specialist",
            "Data/Analytics Specialist",
        ]
        for role in expected_roles:
            self.assertIn(role, roles, f"Missing agent role: {role}")


class TestVoiceConstraints(unittest.TestCase):
    """Verify voice constraints are applied to outward-facing agents."""

    def test_voice_prompt_contains_key_rules(self):
        from voice.jeremy_voice import get_voice_prompt
        voice = get_voice_prompt()
        self.assertIn("No em dashes", voice)
        self.assertIn("No AI filler", voice)
        self.assertIn("LinkedIn", voice)
        self.assertIn("rewrite it", voice.lower())

    def test_voice_prompt_bans_corporate_speak(self):
        from voice.jeremy_voice import get_voice_prompt
        voice = get_voice_prompt()
        self.assertIn("leverage", voice.lower())
        self.assertIn("synergize", voice.lower())


class TestConfig(unittest.TestCase):
    """Verify configuration values match the spec."""

    def test_temperature_values(self):
        from config import TEMPERATURES
        self.assertEqual(TEMPERATURES["orchestrator"], 0.1)
        self.assertEqual(TEMPERATURES["engineer"], 0.2)
        self.assertEqual(TEMPERATURES["marketing"], 0.3)
        self.assertEqual(TEMPERATURES["planner_researcher"], 0.5)

    def test_model_assignments(self):
        from config import MODEL_SONNET, MODEL_OPUS, ROUTING_MODEL, AGENT_MODEL, REASONING_MODEL
        self.assertEqual(ROUTING_MODEL, MODEL_SONNET)
        self.assertEqual(AGENT_MODEL, MODEL_SONNET)
        self.assertEqual(REASONING_MODEL, MODEL_OPUS)


if __name__ == "__main__":
    unittest.main()
