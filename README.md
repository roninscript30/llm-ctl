# llm-ctl ⚡

> **Native Local LLM Control Hub, VRAM Orchestrator & Model Discovery CLI**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)](pyproject.toml)
[![Architecture: Native Linux/UNIX](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-orange.svg)]()
[![Hardware: RTX 3050 Optimized](https://img.shields.io/badge/VRAM-4GB%20Laptop%20Tuned-cyan.svg)]()

```
 █░░ █░░ █▀▄▀█ ▄▄ █▀▀ ▀█▀ █░░
 █░░ █░░ █░▀░█ ░░ █▄▄ ░█░ █▄▄
 Native Local LLM Control Hub & VRAM Orchestrator
```

`llm-ctl` (invoked as `llm` or `llm-ctl`) is a high-aesthetic, lightning-fast CLI designed to manage local LLMs (via Ollama) with strict hardware boundary isolation (tuned for 4 GB VRAM / 8 GB RAM machines) and automatic configuration synchronization across developer coding agents (**Claude Code**, **OpenCode**, and **DeepSeek Harness**).

---

## ✨ Features

- **Claude-Style Visual Aesthetic**: Clean Rich terminal interface with real-time ASCII logo, system telemetry gauges (GPU VRAM, temperature, power, host RAM), and single-keypress navigation.
- **Strict VRAM Isolation (Single-Model Focus)**: Ensures only the requested model occupies GPU VRAM while other models remain idle on disk to prevent RAM exhaustion.
- **Instant Hot-Swapping**: Switch weights in seconds (`llm use <model>`) with automatic VRAM eviction and GPU pre-warming.
- **Curated Ollama Model Hub**: Browse, inspect parameter counts, verify VRAM feasibility badges (`🟢 100% GPU`, `🟡 Hybrid`, `🔴 Heavy`), and pull models with live streaming progress bars.
- **Multi-Agent Sync**: Automatically updates configuration profiles for **Claude Code** (`~/.claude/settings.json`), **OpenCode** (`~/.config/opencode/opencode.jsonc`), and **DeepSeek Harness** (`cordis.patch.yml`).
- **Automation Ready**: First-class `--json` flag on status and process commands for easy integration with shell scripts, tmux, and status bars.

---

## 🚀 Quickstart

### 1. Installation

Clone and install into your local user environment:

```bash
git clone https://github.com/your-username/llm-ctl.git ~/REPOS/llm-ctl
cd ~/REPOS/llm-ctl
./install.sh
```

Ensure `~/.local/bin` is in your `$PATH`.

### 2. Launch Interactive Dashboard

Simply run `llm` in your terminal:

```bash
llm
```

You can navigate with instant single keystrokes:
- `[s]` — Switch active model
- `[h]` — Browse Model Hub & pull models
- `[f]` — Free GPU VRAM (purge to 0 MB)
- `[c]` — Direct terminal chat
- `[l]` — Launch coding agent (Claude Code / OpenCode / DSH)
- `[q]` — Exit dashboard

---

## 🛠️ CLI Command Reference

`llm-ctl` also works as a standard UNIX-style command-line utility for scripts and fast terminal workflows:

### Model & Memory Management
```bash
# View active model, GPU VRAM bar, and host memory
llm status

# View structured JSON output for scripts
llm status --json

# Inspect models currently occupying GPU VRAM
llm ps

# Hot-swap active model (syncs Claude Code, OpenCode & DSH)
llm use deepseek-r1:1.5b

# Evict all models from GPU VRAM (instant 100% free memory)
llm free

# List all downloaded local models
llm ls
```

### Model Discovery & Hub
```bash
# Browse curated Ollama Model Hub with VRAM badges
llm hub

# Download model with real-time progress bar
llm pull qwen2.5-coder:1.5b

# Remove an installed model
llm rm <model_name>
```

### Agent Launchers & Systemd
```bash
# Launch Claude Code wired to local model
llm launch claude

# Launch OpenCode CLI
llm launch opencode

# Launch DeepSeek Harness Web UI
llm launch dsh

# Start direct CLI chat
llm chat

# Force re-sync client configs
llm sync

# Ollama service control
llm service start
llm service status
llm service logs
```

---

## 🏗️ Architecture

```
                  ┌────────────────────────┐
                  │      llm / llm-ctl     │
                  └───────────┬────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          ▼                                       ▼
  [Interactive TUI]                       [UNIX Subcommands]
   • ASCII Banner                          • llm status / ps
   • Telemetry Cards                       • llm use <model>
   • Model Hub Browser                     • llm free
   • Single-Key Nav                        • llm launch <agent>
          │                                       │
          └───────────────────┬───────────────────┘
                              ▼
                 ┌─────────────────────────┐
                 │    Local Orchestrator   │
                 └────────────┬────────────┘
                              │
     ┌────────────────────────┼────────────────────────┐
     ▼                        ▼                        ▼
[Ollama Engine]         [Claude Code]             [OpenCode]
  • RTX 3050 VRAM         • ~/.claude/             • opencode.jsonc
  • Eviction / Pre-warm     settings.json          • model sync
```

---

## 📄 License

MIT © Marudhu
