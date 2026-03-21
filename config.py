"""Configuration for TeamNode — 7-agent heterogeneous fabric team."""

import os
from pathlib import Path

# --- API Keys ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# --- Model Settings ---
MODEL_SONNET = "claude-sonnet-4-20250514"
MODEL_OPUS = "claude-opus-4-20250514"

# Routing model (orchestrator only)
ROUTING_MODEL = MODEL_SONNET
# Domain agent model
AGENT_MODEL = MODEL_SONNET
# Deep reasoning model (planner/researcher)
REASONING_MODEL = MODEL_OPUS

# --- Temperature Settings ---
TEMPERATURES = {
    "orchestrator": 0.1,
    "engineer": 0.2,
    "architect": 0.2,
    "security": 0.2,
    "data_analytics": 0.2,
    "marketing": 0.3,
    "sales": 0.3,
    "planner_researcher": 0.5,
}

# --- Paths ---
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_PERSIST_DIR = DATA_DIR / "chroma"
FABRIC_BINARY = os.environ.get("ECPHORY_BINARY", "ecphory")
FABRIC_DATA_FILE = DATA_DIR / "fabric.json"
LOG_DIR = DATA_DIR / "logs"

# Ensure data directories exist
DATA_DIR.mkdir(exist_ok=True)
CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
