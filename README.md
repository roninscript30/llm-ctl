# LLM-CTL

> **Lightweight, native Linux CLI and terminal controller for local LLM lifecycle management, hardware telemetry, VRAM orchestration, and coding-agent integration.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)](pyproject.toml)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20(Ubuntu%20%7C%20Debian%20%7C%20Fedora%20%7C%20Arch)-orange.svg)]()
[![Hardware: RTX 3050 Optimized](https://img.shields.io/badge/VRAM-4GB%20GPU%20%2F%208GB%20RAM%20Tuned-cyan.svg)]()
[![CI](https://github.com/roninscript30/llm-ctl/actions/workflows/ci.yml/badge.svg)](https://github.com/roninscript30/llm-ctl/actions/workflows/ci.yml)

---

![LLM-CTL Terminal Preview](docs/images/llm-ctl-terminal.png)

---

## What is LLM-CTL?

`llm-ctl` (invoked as `llm` or `llm-ctl`) is a fast, zero-sudo Linux terminal tool and interactive shell designed to give developers full control over local large language models (powered by [Ollama](https://ollama.com)).

It delivers live hardware telemetry, single-model VRAM isolation, instant model hot-swapping, server lifecycle control, and automated configuration synchronization with AI coding assistants like **Claude Code**, **OpenCode**, **Pi Coding Agent**, and **DeepSeek Harness**.

---

## Why It's For: The Problems It Solves

Running local LLMs alongside web browsers, IDEs, Docker containers, and compilers on typical developer hardware—especially laptops with **4 GB VRAM (e.g. NVIDIA RTX 3050) and 8 GB to 16 GB of system RAM**—presents serious challenges:

### 1. VRAM Contention and Out-Of-Memory (OOM) Freezes
Default local runtimes often leave multiple models memory-mapped simultaneously in GPU memory or spill layers uncontrollably into system RAM. On budget or laptop GPUs, this causes Linux kernel OOM kills, dropped frames, desktop freezing, or aborted compilation jobs.
* **LLM-CTL Solution**: Enforces a strict **single-model VRAM isolation policy**. Only one model is allowed to occupy GPU memory at a time. When switching models, previous weights are evicted before new weights are loaded. A dedicated `llm unload` command instantly purges VRAM back to 0 MB whenever you need GPU memory for other tasks.

### 2. Manual Coding-Agent Configuration Drift
Switching models (such as jumping from `qwen2.5-coder:3b` for routine autocomplete to `deepseek-r1:1.5b` for complex logic) usually requires hunting down and manually editing JSON and YAML configuration files for each developer agent.
* **LLM-CTL Solution**: Performs **atomic multi-agent configuration sync**. One command (`llm switch <model>`) automatically rewrites model identifiers and local endpoint URLs for **Claude Code** (`~/.claude/settings.json`), **OpenCode** (`~/.config/opencode/opencode.jsonc`), **Pi Coding Agent** (`~/.pi/agent/models.json` & `settings.json`), and **DeepSeek Harness** (`cordis.patch.yml`).

### 3. Lack of Clear Lifecycle Controls
Developers frequently confuse stopping the Ollama daemon, unloading a model from GPU memory, and deleting model weights from disk.
* **LLM-CTL Solution**: Provides distinct, explicit commands:
  - `llm stop`: Shuts down the background daemon.
  - `llm unload`: Clears GPU memory to 0 MB while keeping model weights safely on disk.
  - `llm remove`: Deletes model weights from disk storage only after explicit user confirmation.

### 4. Telemetry Blindness
Standard local setups offer no visibility into whether a model is active in VRAM, running on CPU fallback, or how much RAM headroom remains before an OOM crash.
* **LLM-CTL Solution**: Real-time telemetry monitoring displaying GPU VRAM, utilization percentage, temperature, wattage, and host RAM headroom with clear visual status indicators.

---

## How It Works

LLM-CTL operates entirely in user space as a lightweight orchestration and control layer on top of Linux system utilities and the Ollama runtime:

1. **Hardware Telemetry Engine**:
   - Queries `nvidia-smi` for GPU VRAM allocation, core load, operating temperature, and power draw.
   - Parses `/proc/meminfo` directly for accurate host RAM usage and available headroom without spawning heavy subprocesses.
   - Detects when no GPU is present and gracefully transitions to CPU fallback mode.

2. **Single-Model Memory Lifecycle**:
   - When switching models, LLM-CTL issues an eviction call (`keep_alive: 0` via the Ollama REST API and `ollama stop <model>`) to free existing VRAM.
   - Pre-warms the target model to ensure immediate responsiveness.

3. **Runtime Server Management**:
   - Manages the Ollama daemon using systemd user services (`systemctl --user start/stop/restart ollama`) with an automatic fallback to background daemon management (`ollama serve`) on non-systemd environments.
   - Checks socket availability on port 11434 with bounded timeouts.

4. **Atomic Configuration Synchronization**:
   - Updates coding-assistant config files atomically using temporary files (`.tmp.<pid>`) and filesystem syncing (`os.fsync`) to prevent file corruption during sudden terminations.

5. **XDG Compliance**:
   - Adheres strictly to the XDG Base Directory specification: configuration in `~/.config/llm-ctl/`, interactive command history in `~/.local/state/llm-ctl/`, and temporary runtime data in `~/.cache/llm-ctl/`.

---

## Installation

### Method 1: Quick Install (Recommended)

Run the automated user-level installer (no root or `sudo` required):

```bash
curl -fsSL https://raw.githubusercontent.com/roninscript30/llm-ctl/main/scripts/install.sh | bash
```

Ensure `~/.local/bin` is in your `$PATH`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Method 2: Manual Clone

```bash
git clone https://github.com/roninscript30/llm-ctl.git ~/REPOS/llm-ctl
cd ~/REPOS/llm-ctl
./install.sh
```

### Method 3: Development / Python Editable Install

```bash
cd ~/REPOS/llm-ctl
pip install --user -e .
```

### Prerequisites
- **Linux Distribution**: Ubuntu (20.04+), Debian, Fedora, Arch Linux, or WSL2.
- **Python**: Version 3.9 or higher.
- **Runtime**: [Ollama](https://ollama.com) (`curl -fsSL https://ollama.com/install.sh | sh`).
- **Hardware**: Any Linux machine. Tuned for NVIDIA GPUs (e.g. RTX 3050 4GB VRAM) with proprietary NVIDIA drivers (`nvidia-smi`), with automatic CPU fallback.

### Shell Completions

Tab-completion scripts are included for Bash, Zsh, and Fish:

* **Bash**:
  ```bash
  mkdir -p ~/.local/share/bash-completion/completions
  cp completions/llm.bash ~/.local/share/bash-completion/completions/llm
  source ~/.local/share/bash-completion/completions/llm
  ```
* **Zsh**:
  ```bash
  mkdir -p ~/.zfunc
  cp completions/llm.zsh ~/.zfunc/_llm
  # Add fpath=(~/.zfunc $fpath) to ~/.zshrc if not already present
  ```
* **Fish**:
  ```bash
  mkdir -p ~/.config/fish/completions
  cp completions/llm.fish ~/.config/fish/completions/llm.fish
  ```

---

## Quick-Start Guide

### 1. Launch Interactive Shell
Run `llm` or `llm-ctl` to launch the interactive terminal interface:
```bash
llm
```

### 2. Verify System Health with `doctor`
Run diagnostic checks on your environment, drivers, server, and coding agents:
```bash
llm doctor
```

### 3. Start the Server
Start the local Ollama daemon if it is not currently running:
```bash
llm start
```

### 4. Pull a Model
Download a model suitable for your hardware with streaming progress:
```bash
llm pull qwen2.5-coder:3b
```

### 5. Switch Active Model
Switch to the new model, pre-warm VRAM, and sync your coding assistants:
```bash
llm switch qwen2.5-coder:3b
```

### 6. Free VRAM when Done
Unload the model to free GPU memory back to 0 MB:
```bash
llm unload
```

---

## Command Reference

Both `llm` and `llm-ctl` can be used interchangeably.

| Command | Aliases | Description |
| :--- | :--- | :--- |
| `llm` | `llm-ctl` | Launches the interactive terminal shell with live telemetry and arrow prompt. |
| `llm status` | `info` | Displays live telemetry, GPU/RAM usage, server status, and active model. Supports `--json`. |
| `llm models` | `ls`, `list` | Lists all installed models with parameter count, size, quantization, and loaded status. Supports `--json`. |
| `llm switch <model>` | `use` | Switches the active model, evicts previous VRAM weights, syncs agent configs, and warms the target model. |
| `llm chat [model]` | — | Starts an interactive chat session with the specified or active model. |
| `llm pull [model]` | — | Downloads model weights with a live progress bar. Calling without arguments opens the curated hub. |
| `llm unload [model]` | `free`, `evict` | Flushes models from GPU VRAM back to 0 MB without deleting model files from disk. |
| `llm remove <model>` | `rm`, `delete` | Permanently removes model weights from disk storage (supports `-y` to skip confirmation). |
| `llm start` | `run` | Starts the local Ollama daemon via systemd user unit or background process fallback. |
| `llm stop` | — | Gracefully flushes active models from VRAM and stops the Ollama daemon. |
| `llm restart` | — | Cycles the local server daemon and re-verifies socket availability. |
| `llm agents <name>` | `launch` | Launches a coding agent (`claude`, `opencode`, `pi`, `dsh`) pre-wired to the active local model. |
| `llm doctor` | — | Diagnoses runtime reachability, NVIDIA drivers, RAM headroom, agent binaries, and configuration integrity. |
| `llm config [show\|path\|set]` | — | Inspects or updates configuration values. Supports `--json`. |
| `llm help` | `-h`, `--help` | Displays command reference and usage examples. |

---

## Model Lifecycle & Memory Distinction

| Operation | Command | Target | Effect on Memory | Effect on Disk |
| :--- | :--- | :--- | :--- | :--- |
| **Stop Server** | `llm stop` | Ollama Daemon | Frees all VRAM; halts background service | Files remain intact |
| **Unload Model** | `llm unload` | GPU VRAM / Host RAM | Purges model weights back to 0 MB | Files remain intact |
| **Remove Model** | `llm remove <model>` | Disk Storage | Purges model from VRAM if loaded | Permanently deletes model weights |

---

## Configuration & Storage (XDG Standard)

LLM-CTL stores all data according to the XDG Base Directory specification:

| File / Directory | Default Path | Environment Override | Purpose |
| :--- | :--- | :--- | :--- |
| **Configuration** | `~/.config/llm-ctl/config.json` | `$XDG_CONFIG_HOME/llm-ctl/` | Active model selection, host endpoint, agent settings |
| **Command History** | `~/.local/state/llm-ctl/history` | `$XDG_STATE_HOME/llm-ctl/` | Readline command history for interactive shell |
| **Logs** | `~/.local/state/llm-ctl/logs/` | `$XDG_STATE_HOME/llm-ctl/` | Diagnostic logs and command event records |
| **Cache** | `~/.cache/llm-ctl/` | `$XDG_CACHE_HOME/llm-ctl/` | Session cache and transient runtime files |
| **Binaries** | `~/.local/bin/llm-ctl`, `~/.local/bin/llm` | Standard user `$PATH` | Executable launchers |

---

## Troubleshooting & Diagnostics

Run `llm doctor` at any time to inspect your setup:
```bash
llm doctor
```

### Common Fixes

* **"Cannot connect to Ollama at http://127.0.0.1:11434"**:
  Run `llm start` to boot the daemon, or check status with `systemctl --user status ollama`.
* **"Command not found: llm"**:
  Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc` or `~/.zshrc` and run `source ~/.bashrc`.
* **"No dedicated NVIDIA GPU detected"**:
  LLM-CTL automatically operates in CPU mode. Use compact models like `qwen2.5-coder:1.5b` or `deepseek-r1:1.5b` for fast CPU inference.
* **Low System RAM Warning (< 1.0 GiB available)**:
  Run `llm unload` to release memory, or close memory-heavy applications before launching large models.

---

## Uninstallation

To cleanly remove LLM-CTL while preserving your downloaded Ollama models and configuration:
```bash
./scripts/uninstall.sh
```

To purge all configuration files, logs, and command history as well:
```bash
./scripts/uninstall.sh --purge
```

---

## Future Plans

- [x] **v1.0.0 (Linux V1 Release)**: Polished arrow prompt, compact telemetry layout, single-model VRAM isolation, server lifecycle controls, multi-agent config sync, doctor diagnostics, and XDG compliance.
- [ ] **v1.1 (Multi-GPU Selection)**: Support for multi-GPU indexing (`--gpu <id>`) and heterogeneous GPU monitoring.
- [ ] **v1.2 (Alternative Backends)**: Direct connectivity to standalone `llama.cpp` (`llama-server`) and `vLLM` endpoints.
- [ ] **v1.3 (Benchmarking Suite)**: Built-in `llm bench <model>` command measuring tokens/sec and Time-To-First-Token (TTFT) on your hardware.
- [ ] **v2.0 (Dynamic VRAM Autoscaler)**: Background daemon with configurable idle timeouts to automatically hibernate models back to 0 MB VRAM when coding agents are inactive.

---

## License & Contributing

Distributed under the [MIT License](LICENSE). Contributions, bug reports, and suggestions are welcome via [GitHub Issues](https://github.com/roninscript30/llm-ctl/issues) and Pull Requests.
