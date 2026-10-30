#!/usr/bin/env bash
# ==============================================================================
# LLM-CTL — Linux V1 Safe Uninstaller
# Removes LLM-CTL binaries and application cache without touching:
# - Ollama service or Ollama model weights
# - User configuration (~/.config/llm-ctl) unless --purge is explicitly passed
# ==============================================================================

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[92m"
YELLOW="\033[93m"
RED="\033[91m"
CYAN="\033[96m"
DIM="\033[2m"
RESET="\033[0m"

BIN_DIR="$HOME/.local/bin"
INSTALL_DIR="$HOME/.local/share/llm-ctl"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/llm-ctl"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/llm-ctl"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/llm-ctl"

PURGE_USER_DATA=false
if [ "${1:-}" = "--purge" ] || [ "${1:-}" = "-p" ]; then
    PURGE_USER_DATA=true
fi

echo -e "\n${BOLD}${CYAN}LLM-CTL — Uninstaller${RESET}\n"

# 1. Remove Launchers
if [ -f "$BIN_DIR/llm-ctl" ] || [ -L "$BIN_DIR/llm-ctl" ]; then
    rm -f "$BIN_DIR/llm-ctl"
    echo -e "  ${GREEN}✔${RESET} Removed $BIN_DIR/llm-ctl"
fi

if [ -f "$BIN_DIR/llm" ] || [ -L "$BIN_DIR/llm" ]; then
    rm -f "$BIN_DIR/llm"
    echo -e "  ${GREEN}✔${RESET} Removed $BIN_DIR/llm"
fi

# 2. Remove Shared Application Source if installed remotely
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "  ${GREEN}✔${RESET} Removed $INSTALL_DIR"
fi

# 3. Remove Cache
if [ -d "$CACHE_DIR" ]; then
    rm -rf "$CACHE_DIR"
    echo -e "  ${GREEN}✔${RESET} Removed cache: $CACHE_DIR"
fi

# 4. Handle State & Config
if [ "$PURGE_USER_DATA" = true ]; then
    if [ -d "$STATE_DIR" ]; then
        rm -rf "$STATE_DIR"
        echo -e "  ${GREEN}✔${RESET} Purged state/history: $STATE_DIR"
    fi
    if [ -d "$CONFIG_DIR" ]; then
        rm -rf "$CONFIG_DIR"
        echo -e "  ${GREEN}✔${RESET} Purged user configuration: $CONFIG_DIR"
    fi
else
    echo -e "  ${DIM}Preserved user configuration at: $CONFIG_DIR${RESET}"
    echo -e "  ${DIM}Preserved user state/history at: $STATE_DIR${RESET}"
    echo -e "  ${DIM}(To remove configuration as well, run: ./scripts/uninstall.sh --purge)${RESET}"
fi

echo -e "\n${BOLD}${GREEN}✔ LLM-CTL has been uninstalled.${RESET}"
echo -e "${DIM}Note: Ollama and all downloaded model weights were untouched.${RESET}\n"
