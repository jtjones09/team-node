"""Configuration for TeamNode — 7-agent heterogeneous fabric team."""

import json
import os
from pathlib import Path


# --- Persistent API Key ---
CONFIG_DIR = Path.home() / ".config" / "teamnode"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_api_key() -> str:
    """Get Anthropic API key from environment or persistent config."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        return config.get("anthropic_api_key", "")
    return ""


def save_api_key(key: str) -> Path:
    """Save API key to ~/.config/teamnode/config.json with 0600 permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    config["anthropic_api_key"] = key
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    CONFIG_FILE.chmod(0o600)
    return CONFIG_FILE


ANTHROPIC_API_KEY = get_api_key()

# --- Model Settings ---
# Cost tiers (March 2026):
#   Haiku:  $0.25/$1.25 per MTok (input/output)
#   Sonnet: $3/$15 per MTok
#   Opus:   $15/$75 per MTok
#
# Models are selected dynamically by the router (routing/model_router.py)
# based on task complexity. These are the available models:
MODEL_HAIKU = "anthropic/claude-haiku-4-5-20251001"
MODEL_SONNET = "anthropic/claude-sonnet-4-20250514"
MODEL_OPUS = "anthropic/claude-opus-4-20250514"

# Override defaults via env vars if needed
DEFAULT_AGENT_MODEL = os.environ.get("TEAMNODE_AGENT_MODEL", MODEL_SONNET)
DEFAULT_PLANNER_MODEL = os.environ.get("TEAMNODE_PLANNER_MODEL", MODEL_SONNET)

# --- Ollama Settings ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

# Hybrid model routing: local Ollama for FAST/STANDARD, API for PREMIUM
OLLAMA_URL = os.environ.get("OLLAMA_URL", OLLAMA_BASE_URL)
OLLAMA_FAST_MODEL = os.environ.get("OLLAMA_FAST_MODEL", "qwen2.5:32b")
OLLAMA_STANDARD_MODEL = os.environ.get("OLLAMA_STANDARD_MODEL", "llama3.3:70b")
ANTHROPIC_PREMIUM = os.environ.get("ANTHROPIC_PREMIUM", "true").lower() in ("true", "1", "yes")

# --- Temperature Settings (per agent domain) ---
TEMPERATURES = {
    "engineer": 0.2,
    "architect": 0.2,
    "security": 0.2,
    "data_analytics": 0.2,
    "marketing": 0.3,
    "sales": 0.3,
    "planner_researcher": 0.3,
}

# --- CrewAI Limits ---
MAX_ITER = int(os.environ.get("TEAMNODE_MAX_ITER", "15"))
MAX_RPM = int(os.environ.get("TEAMNODE_MAX_RPM", "10"))

# --- Paths ---
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
PROJECTS_DIR = DATA_DIR / "projects"
LOG_DIR = DATA_DIR / "logs"

FABRIC_BINARY = os.environ.get(
    "ECPHORY_BINARY",
    str(Path.home() / "projects" / "ecphory" / "target" / "release" / "intent")
)

# Ensure data directories exist
DATA_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_project_paths(project: str) -> dict[str, Path]:
    """Get scoped paths for a specific project."""
    project_dir = PROJECTS_DIR / project
    project_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = project_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    return {"log_dir": logs_dir, "project_dir": project_dir}


def list_projects() -> list[str]:
    """List all available projects."""
    if not PROJECTS_DIR.exists():
        return []
    return sorted(d.name for d in PROJECTS_DIR.iterdir() if d.is_dir())
