"""
Standardized Linux XDG storage path definitions for LLM-CTL.
Separates application code, user configuration, state/history, and cache.
"""

import os
import shutil

XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
XDG_STATE_HOME = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
XDG_CACHE_HOME = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")

CONFIG_DIR = os.path.join(XDG_CONFIG_HOME, "llm-ctl")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

STATE_DIR = os.path.join(XDG_STATE_HOME, "llm-ctl")
HISTORY_FILE = os.path.join(STATE_DIR, "history")
LOGS_DIR = os.path.join(STATE_DIR, "logs")

CACHE_DIR = os.path.join(XDG_CACHE_HOME, "llm-ctl")

def ensure_directories():
    """Ensures XDG user directories exist and migrates legacy history if needed."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Migrate legacy history file from ~/.config/llm-ctl/history to ~/.local/state/llm-ctl/history
    legacy_history = os.path.join(CONFIG_DIR, "history")
    if os.path.exists(legacy_history) and not os.path.exists(HISTORY_FILE):
        try:
            shutil.move(legacy_history, HISTORY_FILE)
        except Exception:
            pass
