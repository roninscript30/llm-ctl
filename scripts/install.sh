#!/usr/bin/env bash
# ==============================================================================
# LLM-CTL — Linux V1 User-Level Installer
# Installs llm-ctl and llm commands into ~/.local/bin without root privileges.
# Compatible with Ubuntu, Debian, Fedora, Arch, and POSIX Linux environments.
# ==============================================================================

set -euo pipefail

# ANSI Styling
BOLD="\033[1m"
GREEN="\033[92m"
YELLOW="\033[93m"
CYAN="\033[96m"
RED="\033[91m"
DIM="\033[2m"
RESET="\033[0m"

REPO_URL="https://github.com/roninscript30/llm-ctl.git"
INSTALL_DIR="$HOME/.local/share/llm-ctl"
BIN_DIR="$HOME/.local/bin"

echo -e "\n${BOLD}${CYAN}LLM-CTL — Linux V1 Installer${RESET}"
echo -e "${DIM}Lightweight Local LLM Control Hub & VRAM Orchestration CLI${RESET}\n"

# 1. Prerequisite Checks
echo -e "  ${DIM}Checking prerequisites...${RESET}"

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "  ${RED}✖ Error: Python 3 is not installed or not in PATH.${RESET}"
    echo -e "  ${YELLOW}Actionable fix (Ubuntu/Debian):${RESET} sudo apt update && sudo apt install -y python3 python3-pip"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    echo -e "  ${RED}✖ Error: Python 3.9+ is required (found Python $PY_VERSION).${RESET}"
    echo -e "  ${YELLOW}Please upgrade Python to 3.9 or newer.${RESET}"
    exit 1
fi
echo -e "  ${GREEN}✔${RESET} Python $PY_VERSION detected"

# Check rich dependency
if ! python3 -c "import rich" >/dev/null 2>&1; then
    echo -e "  ${YELLOW}Notice: 'rich' package not detected in current Python environment.${RESET}"
    if command -v pip3 >/dev/null 2>&1; then
        echo -e "  ${DIM}Installing user dependency 'rich>=13.0.0'...${RESET}"
        pip3 install --user --quiet "rich>=13.0.0" || {
            echo -e "  ${YELLOW}⚠ Could not install rich automatically. Try: pip3 install --user rich${RESET}"
        }
    elif python3 -m pip --version >/dev/null 2>&1; then
        echo -e "  ${DIM}Installing user dependency 'rich>=13.0.0'...${RESET}"
        python3 -m pip install --user --quiet "rich>=13.0.0" || {
            echo -e "  ${YELLOW}⚠ Could not install rich automatically. Try: python3 -m pip install --user rich${RESET}"
        }
    else
        echo -e "  ${YELLOW}⚠ python3-pip not found. Please install python3-pip or ensure 'rich' is available.${RESET}"
    fi
else
    echo -e "  ${GREEN}✔${RESET} Dependency 'rich' verified"
fi

# 2. Determine Source Directory
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    POTENTIAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    if [ -f "$POTENTIAL_DIR/pyproject.toml" ] && [ -d "$POTENTIAL_DIR/src/llm_ctl" ]; then
        SCRIPT_DIR="$POTENTIAL_DIR"
    fi
fi

mkdir -p "$BIN_DIR"

if [ -n "$SCRIPT_DIR" ]; then
    # Running from a cloned local repository
    echo -e "  ${GREEN}✔${RESET} Installing from local repository: ${DIM}$SCRIPT_DIR${RESET}"
    TARGET_SRC="$SCRIPT_DIR/src"
else
    # Running via piped curl: download/clone into ~/.local/share/llm-ctl
    echo -e "  ${DIM}Fetching package into $INSTALL_DIR...${RESET}"
    if [ -d "$INSTALL_DIR/.git" ]; then
        git -C "$INSTALL_DIR" pull --quiet origin main || true
    else
        rm -rf "$INSTALL_DIR"
        mkdir -p "$INSTALL_DIR"
        if command -v git >/dev/null 2>&1; then
            git clone --depth 1 --quiet "$REPO_URL" "$INSTALL_DIR"
        else
            echo -e "  ${RED}✖ Error: 'git' is required for remote curl installation.${RESET}"
            echo -e "  ${YELLOW}Actionable fix:${RESET} sudo apt install -y git"
            exit 1
        fi
    fi
    TARGET_SRC="$INSTALL_DIR/src"
fi

# 3. Create Executable Launcher
LAUNCHER="$BIN_DIR/llm-ctl"
rm -f "$LAUNCHER" "$BIN_DIR/llm"
cat << EOF > "$LAUNCHER"
#!/usr/bin/env python3
import sys
import os

# Safe user-level module resolution
sys.path.insert(0, "$TARGET_SRC")
from llm_ctl.cli import main

if __name__ == "__main__":
    main()
EOF

chmod +x "$LAUNCHER"
ln -sf "$LAUNCHER" "$BIN_DIR/llm"

echo -e "  ${GREEN}✔${RESET} Created launcher: ${BOLD}$LAUNCHER${RESET}"
echo -e "  ${GREEN}✔${RESET} Created convenience alias: ${BOLD}$BIN_DIR/llm${RESET}"

# 4. PATH Check
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\n  ${YELLOW}⚠ PATH Warning:${RESET} $BIN_DIR is not currently in your \$PATH."
    echo -e "  Add it to your shell configuration by running:"
    echo -e "    ${CYAN}echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc${RESET}"
    echo -e "    ${CYAN}source ~/.bashrc${RESET}"
fi

echo -e "\n${BOLD}${GREEN}✔ Installation Complete!${RESET}"
echo -e "Run ${BOLD}llm-ctl${RESET} or ${BOLD}llm${RESET} to launch the interactive shell."
echo -e "Run ${BOLD}llm --help${RESET} for non-interactive scripting options.\n"
