#!/usr/bin/env bash
set -euo pipefail
BIN_DIR="${HOME}/.local/bin"
rm -f "${BIN_DIR}/llm" "${BIN_DIR}/llm-ctl"
rm -f "${HOME}/.local/share/bash-completion/completions/llm"

if [[ "${1:-}" == "--purge" || "${1:-}" == "-p" ]]; then
  CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/llm-ctl"
  STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/llm-ctl"
  CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/llm-ctl"
  DATA_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/llm-ctl"
  rm -rf -- "${CONFIG_DIR}" "${STATE_DIR}" "${CACHE_DIR}" "${DATA_DIR}"
  printf 'Removed LLM-CTL binaries and user data. Ollama models were untouched.\n'
else
  printf 'Removed LLM-CTL binaries. Configuration and history were preserved.\n'
  printf 'Use --purge to also remove LLM-CTL configuration, history, and cache.\n'
fi
