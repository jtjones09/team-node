"""Configuration for TeamNode — 7-agent heterogeneous fabric team."""

import json
import os
from pathlib import Path


# --- Persistent API Key ---
CONFIG_DIR = Path.home() / ".config" / "teamnode"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_api_key() -> str:
    """Get Anthropic API key from environment or persistent config.

    Priority:
    1. ANTHROPIC_API_KEY environment variable
    2. ~/.config/teamnode/config.json
    3. Empty string (not found)
    """
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
MODEL_SONNET = "anthropic/claude-sonnet-4-20250514"
MODEL_OPUS = "anthropic/claude-opus-4-20250514"

# Routing model (orchestrator only)
ROUTING_MODEL = MODEL_SONNET
# Domain agent model
AGENT_MODEL = MODEL_SONNET
# Deep reasoning model (planner/researcher)
REASONING_MODEL = MODEL_OPUS

# --- Ollama Settings ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

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
PROJECTS_DIR = DATA_DIR / "projects"
FABRIC_BINARY = os.environ.get("ECPHORY_BINARY", str(Path.home() / "intent-node" / "target" / "release" / "intent"))

# Legacy flat paths (used when no --project is specified)
FABRIC_DATA_FILE = DATA_DIR / "fabric.json"
LOG_DIR = DATA_DIR / "logs"

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
    return {
        "fabric_file": project_dir / "fabric.json",
        "log_dir": logs_dir,
        "project_dir": project_dir,
    }


def list_projects() -> list[str]:
    """List all available projects."""
    if not PROJECTS_DIR.exists():
        return []
    return sorted(
        d.name for d in PROJECTS_DIR.iterdir()
        if d.is_dir() and (d / "fabric.json").exists()
    )
