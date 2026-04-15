"""
Configuration for the MCP-in-Skills POC.
Loads settings from .env file and provides defaults.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).parent
load_dotenv(_project_root / ".env")

# ─── OpenRouter ───────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku")

# ─── MCP Server Definitions ──────────────────────────────────
# Each entry: { "name": str, "command": str, "args": list[str] }
# These are the MCP servers that the Skill can discover and use.
MCP_SERVERS = [
    {
        "name": "math",
        "description": "Mathematical operations: add, multiply, fibonacci",
        "command": sys.executable,
        "args": [str(_project_root / "mcp_servers" / "server_math.py")],
    },
    {
        "name": "filesystem",
        "description": "Read-only filesystem access: list directory, read file, file info",
        "command": sys.executable,
        "args": [str(_project_root / "mcp_servers" / "server_filesystem.py")],
    },
]

# ─── Skill Config ─────────────────────────────────────────────
SKILL_DIR = _project_root / "skills" / "use-mcp"
SKILL_MD_PATH = SKILL_DIR / "SKILL.md"

# ─── Logging ──────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ─── Safety ──────────────────────────────────────────────────
# Tool name patterns that require user confirmation before execution
DESTRUCTIVE_PATTERNS = ["delete", "remove", "drop", "write", "update", "create"]
