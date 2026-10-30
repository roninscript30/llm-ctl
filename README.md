# LLM-CTL ⚡

> **Native Linux CLI & TUI Hub for Local LLM Lifecycle Management, VRAM Orchestration & Coding-Agent Config Sync**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)](pyproject.toml)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20(Ubuntu%20%7C%20Debian%20%7C%20Fedora%20%7C%20Arch)-orange.svg)]()
[![Hardware: RTX 3050 Optimized](https://img.shields.io/badge/VRAM-4GB%20GPU%20%2F%208GB%20RAM%20Tuned-cyan.svg)]()
[![CI](https://github.com/roninscript30/llm-ctl/actions/workflows/ci.yml/badge.svg)](https://github.com/roninscript30/llm-ctl/actions/workflows/ci.yml)

```text
 █░░ █░░ █▀▄▀█ ▄▄ █▀▀ ▀█▀ █░░
 █░░ █░░ █░▀░█ ░░ █▄▄ ░█░ █▄▄
 Native Local LLM Control Hub & VRAM Orchestrator
```

`llm-ctl` (invoked seamlessly as either `llm` or `llm-ctl`) is an ultra-fast, user-space Linux utility and interactive terminal dashboard designed to give developers frictionless control over local language models (powered by [Ollama](https://ollama.com)). It enforces strict hardware isolation on resource-constrained development machines (such as 4 GB VRAM laptops and 8 GB RAM workstations) while keeping modern AI coding agents (**Claude Code**, **OpenCode**, and **DeepSeek Harness**) in lockstep with the currently active model.

---

## 📋 Table of Contents

- [1. What LLM-CTL Does & Problems It Solves](#1-what-llm-ctl-does--problems-it-solves)
- [2. V1 Release Status & Scope](#2-v1-release-status--scope)
- [3. Key Features](#3-key-features)
- [4. Terminal Preview](#4-terminal-preview)
- [5. Supported Linux Environments & Prerequisites](#5-supported-linux-environments--prerequisites)
- [6. Installation (Quick Curl Installer)](#6-installation-quick-curl-installer)
- [7. Alternative & Development Installation](#7-alternative--development-installation)
- [8. Quick-Start Guide](#8-quick-start-guide)
- [9. Complete Command Reference](#9-complete-command-reference)
- [10. Runtime Controls & Model Lifecycle Explained](#10-runtime-controls--model-lifecycle-explained)
- [11. Configuration & Storage Locations (XDG Compliance)](#11-configuration--storage-locations-xdg-compliance)
- [12. Troubleshooting & `doctor` Diagnostics](#12-troubleshooting--doctor-diagnostics)
- [13. Security Considerations & Uninstallation](#13-security-considerations--uninstallation)
- [14. Known Limitations](#14-known-limitations)
- [15. Roadmap](#15-roadmap)
- [16. License & Contributing](#16-license--contributing)

---

## 1. What LLM-CTL Does & Problems It Solves

Running local LLMs alongside heavy developer tools, compilers, and browser tabs often results in performance bottlenecks and memory contention. `llm-ctl` directly tackles three core pain points:

### 1. Unmanaged VRAM Consumption & OOM Crashes
When multiple local models are queried sequentially, Ollama may keep multiple models memory-mapped in GPU VRAM or spill layers into system RAM. On budget laptops (e.g., NVIDIA GeForce RTX 3050 Laptop GPU with 4 GB VRAM and 8 GB host RAM), this quickly triggers Linux Out-Of-Memory (OOM) kernel kills, frozen display servers, or sudden process termination. 
- **The Solution**: `llm-ctl` enforces a **single-model VRAM isolation policy**. Switching models automatically evicts stale weights before pre-warming the target model, and a dedicated `llm unload` command guarantees 0 MB VRAM footprint when you return to heavy compiling.

### 2. Manual Coding-Agent Configuration Drift
Switching between models (e.g. going from `qwen2.5-coder:3b` for quick scaffolding to `deepseek-r1:1.5b` for complex algorithmic reasoning) usually requires manually finding and editing disparate configuration files for each coding assistant.
- **The Solution**: `llm-ctl` provides **atomic multi-agent configuration synchronization**. When you switch active models via `llm switch <model>`, `llm-ctl` instantly writes the updated model identifiers and local endpoint URLs into Claude Code (`~/.claude/settings.json`), OpenCode (`~/.config/opencode/opencode.jsonc`), and DeepSeek Harness (`cordis.patch.yml`).

### 3. Opaque Server and Model Lifecycles
Many developers struggle to discern whether a model is simply stored on disk, active in configuration, resident in GPU VRAM, or whether the Ollama daemon itself is running or unresponsive.
- **The Solution**: `llm-ctl` cleanly separates server lifecycle (`start` / `stop` / `restart`), memory residence (`unload` / `free`), and disk footprint (`remove` / `pull`), presenting real-time telemetry gauges in a beautiful terminal UI.

---

## 2. V1 Release Status & Scope

- **Status**: Production-ready Linux V1 release (`v1.0.0`).
- **Core Technology**: 100% native Python 3 (Python >= 3.9) with minimal dependency overhead (only `rich>=13.0.0`).
- **Operating Scope**: Runs entirely in Linux user-space without requiring `sudo` or root privileges.
- **Target Backend**: Ollama local REST engine (`http://127.0.0.1:11434`) via systemd user services or daemon fallback.
- **Primary Hardware Baseline**: Tested and tuned for single-GPU NVIDIA setups (e.g., RTX 3050 4GB) paired with 8GB–16GB system RAM, with automatic fallback for CPU-only systems.

---

## 3. Key Features

- **Real-Time Telemetry Dashboard**: Live GPU VRAM capacity bar, GPU temperature, power wattage, utilization percentage (via `nvidia-smi`), and system RAM headroom (via `/proc/meminfo`).
- **Single-Keypress Interactive TUI**: Launch with `llm` to enter an interactive dashboard with single-keystroke commands (`[s]` switch, `[p]` pull, `[u]` unload, `[c]` chat, `[d]` doctor, `[a]` launch agent, `[q]` quit).
- **Runtime Server Management**: Seamlessly start, gracefully stop, and restart local Ollama servers with automated systemd user-unit integration (`systemctl --user`) and process daemon fallback.
- **Instant Model Hot-Swapping**: Switch active models in seconds (`llm switch <model>`); stale weights are purged from VRAM and new weights are immediately warmed into memory.
- **Curated Model Hub with Hardware Badging**: Browse recommended developer models tagged with parameter counts, disk requirements, and real-time hardware feasibility badges:
  - `🟢 100% GPU`: Runs entirely in 4 GB VRAM with maximal inference speed.
  - `🟡 Hybrid`: Splits layers between GPU VRAM and host RAM.
  - `🔴 Heavy`: Primarily CPU/RAM execution; expect slower token generation.
- **Deep Coding-Agent Integration**: Instantly wire and launch Claude Code (`llm agents claude`), OpenCode (`llm agents opencode`), and DeepSeek Harness (`llm agents dsh`).
- **Automated Diagnostic Doctor (`llm doctor`)**: Self-auditing suite checking REST API connectivity, NVIDIA drivers, RAM headroom, model presence, agent binaries, and config file health with actionable fixes.
- **Automation & Scripting Friendly**: Full `--json` flag support across `status`, `models`, and `config` commands for script automation, Polybar, Waybar, or tmux status bars.
- **XDG Standards Compliant**: Strictly follows XDG Base Directory specifications, keeping user config, state history, and temporary cache cleanly segregated.

---

## 4. Terminal Preview

Below is a preview of the `llm-ctl` interactive status screen and telemetry overview:

```text
┌────────────────────────────────────────────────────────────────────────┐
│  █░░ █░░ █▀▄▀█ ▄▄ █▀▀ ▀█▀ █░░                                         │
│  █░░ █░░ █░▀░█ ░░ █▄▄ ░█░ █▄▄   v1.0.0 (Linux x86_64)                 │
│  Native Local LLM Control Hub & VRAM Orchestrator                      │
├────────────────────────────────────────────────────────────────────────┤
│  STATUS & TELEMETRY                                                    │
│  • Ollama Service: Connected (http://127.0.0.1:11434 · v0.5.12)        │
│  • NVIDIA GPU:     NVIDIA GeForce RTX 3050 Laptop GPU                  │
│    VRAM: [████████████████████░░░░░░░░░░] 2150 / 4096 MiB (52%)       │
│    Metrics: 58°C · 38W · 14% Core Load                                 │
│  • System RAM:    [████████████░░░░░░░░░░░░] 4.6 / 7.8 GiB (3.2G Free) │
│                                                                        │
│  ACTIVE MODEL                                                          │
│  • Model:          qwen2.5-coder:3b ★ [IN VRAM]                        │
│  • Parameters:     3.09 B · Quantization: Q4_K_M                       │
│  • Agent Sync:     Claude Code ✔ | OpenCode ✔ | DSH ✔                  │
├────────────────────────────────────────────────────────────────────────┤
│  QUICK ACTIONS                                                         │
│  [s] Switch Model    [p] Pull from Hub    [u] Unload VRAM              │
│  [c] Chat Terminal   [d] Run Doctor       [a] Launch Agent   [q] Quit  │
└────────────────────────────────────────────────────────────────────────┘
```

![LLM-CTL Terminal Preview](docs/images/llm-ctl-terminal.png)

> [!NOTE]
> *Live terminal session of LLM-CTL v1.0.0 displaying real-time Ollama daemon telemetry, NVIDIA RTX GPU status, host RAM usage, and active model state.*

---

## 5. Supported Linux Environments & Prerequisites

### Supported Distributions
- **Ubuntu**: 20.04 LTS, 22.04 LTS, 24.04 LTS (Primary tested platform)
- **Debian**: 11 (Bullseye), 12 (Bookworm), testing/sid
- **Fedora**: 38, 39, 40+
- **Arch Linux / Manjaro**: Rolling releases
- **POSIX Linux / WSL2**: Any Linux distribution with Python 3.9+ and systemd or standard process management

### Prerequisites
1. **Python**: Python `>= 3.9` (`python3 --version`).
2. **Ollama**: Local Ollama runtime installed (`curl -fsSL https://ollama.com/install.sh | sh`).
3. **Hardware (Recommended)**:
   - **GPU**: NVIDIA GPU (e.g. RTX 3050 / RTX 3060 / GTX 1650) with proprietary NVIDIA drivers (`nvidia-smi`).
   - **RAM**: Minimum 8 GB system RAM.
   - *CPU Fallback*: Systems without an NVIDIA GPU automatically fall back to CPU and system RAM monitoring.
4. **Coding Agents (Optional)**:
   - Claude Code (`npm i -g @anthropic-ai/claude-code`)
   - OpenCode CLI (`curl -fsSL https://opencode.ai/install.sh | bash`)
   - DeepSeek Harness (`npm i -g deepseek-harness`)

---

## 6. Installation (Quick Curl Installer)

Install `llm-ctl` directly into your user environment without root or sudo:

```bash
curl -fsSL https://raw.githubusercontent.com/roninscript30/llm-ctl/main/scripts/install.sh | bash
```

### What the Installer Does
1. Verifies Python `>= 3.9` is present.
2. Ensures the lightweight dependency `rich>=13.0.0` is available in your user Python environment.
3. Clones or updates the repository to `~/.local/share/llm-ctl`.
4. Creates executable launchers in `~/.local/bin/llm-ctl` and `~/.local/bin/llm`.
5. Verifies that `~/.local/bin` is in your shell `$PATH` and gives you the exact line to add to `~/.bashrc` or `~/.zshrc` if needed.

> [!TIP]
> After running the installer, ensure `~/.local/bin` is loaded in your current shell:
> ```bash
> source ~/.bashrc   # or source ~/.zshrc
> ```

---

## 7. Alternative & Development Installation

### Option A: Install from Local Git Clone

If you prefer to clone the repository manually:

```bash
git clone https://github.com/roninscript30/llm-ctl.git ~/REPOS/llm-ctl
cd ~/REPOS/llm-ctl
./scripts/install.sh
```

### Option B: Python Editable / User Install

For local development or packaging:

```bash
cd ~/REPOS/llm-ctl
pip install --user -e .
```

This installs the console scripts `llm` and `llm-ctl` directly using `setuptools`.

### Shell Autocompletion Setup

`llm-ctl` includes tab-completion definitions for Bash, Zsh, and Fish:

#### Bash
```bash
mkdir -p ~/.local/share/bash-completion/completions
cp completions/llm.bash ~/.local/share/bash-completion/completions/llm
# Re-source completions
source ~/.local/share/bash-completion/completions/llm
```

#### Zsh
```bash
mkdir -p ~/.zfunc
cp completions/llm.zsh ~/.zfunc/_llm
# Ensure fpath=(~/.zfunc $fpath) and autoload -Uz compinit && compinit are in ~/.zshrc
```

#### Fish
```bash
mkdir -p ~/.config/fish/completions
cp completions/llm.fish ~/.config/fish/completions/llm.fish
```

---

## 8. Quick-Start Guide

### 1. Launch the Interactive Dashboard
Type `llm` in your terminal to view system health and interact via hotkeys:
```bash
llm
```

### 2. Verify System Health with `doctor`
Run diagnostics to verify Ollama, drivers, and agents:
```bash
llm doctor
```

### 3. Start or Inspect the Ollama Server
If Ollama is stopped, start it with one command:
```bash
llm start
llm status
```

### 4. Download a Feasible Model
Browse the hub and download a coding model tuned for 4 GB VRAM:
```bash
llm pull qwen2.5-coder:3b
```

### 5. Hot-Swap & Sync Coding Agents
Switch active model to the new model (syncing Claude Code and OpenCode automatically):
```bash
llm switch qwen2.5-coder:3b
```

### 6. Free VRAM when Done
Evict the model from GPU memory to 0 MB before starting heavy compilations:
```bash
llm unload
```

---

## 9. Complete Command Reference

`llm-ctl` can be invoked as `llm` or `llm-ctl`. Every command is designed to be fast, predictable, and scriptable:

| Command | Aliases | Description |
|:---|:---|:---|
| `llm status` | `info` | Displays live telemetry card, GPU VRAM bar, RAM headroom, and active model. Supports `--json`. |
| `llm models` | `ls`, `list` | Lists all downloaded local models with sizes, parameter counts, quantization, and loaded status. Supports `--json`. |
| `llm switch <model>` | `use` | Hot-swaps the active model, purges VRAM, syncs coding-agent configs, and pre-warms target weights. |
| `llm chat [model]` | — | Starts an immediate interactive CLI chat session with the active or specified local model. |
| `llm pull [model]` | — | Downloads model weights with live streaming progress bar. When called without args, displays the curated model hub. |
| `llm unload [model]` | `free`, `evict` | Flushes models from GPU VRAM back to 0 MB without deleting model weights from disk. |
| `llm remove <model>` | `rm`, `delete` | Permanently deletes model weights from disk storage. Use `-y` or `--yes` to bypass prompt. |
| `llm start` | `run` | Starts local Ollama server (via `systemctl --user start ollama` or background process fallback). |
| `llm stop` | — | Gracefully flushes active models from VRAM and stops the Ollama daemon. |
| `llm restart` | — | Restarts the local Ollama server process cleanly. |
| `llm agents <name>` | `launch` | Launches specified coding agent (`claude`, `opencode`, `dsh`) pre-wired to the active local model. |
| `llm doctor` | — | Executes comprehensive diagnostic checks across system drivers, Ollama API, RAM, and agent binaries. |
| `llm config [show\|path\|set]` | — | Inspects or updates configuration keys (e.g. `llm config set active_model <name>`). Supports `--json`. |
| `llm help` | `-h`, `--help` | Prints concise command reference, flags, and usage examples. |

### Command Examples & Usage Flags

#### Structured JSON Telemetry
Integrate live telemetry into tmux status bars, Polybar, or bash scripts:
```bash
# Get complete machine & model state as JSON
llm status --json

# List installed models in JSON
llm models --json
```

#### Launching Coding Assistants
Launch agents wired to your active local model without manually exporting environment variables:
```bash
# Launch Claude Code configured for local Ollama
llm agents claude

# Launch OpenCode CLI
llm agents opencode

# Launch DeepSeek Harness Web UI
llm agents dsh
```

---

## 10. Runtime Controls & Model Lifecycle Explained

To ensure reliable memory management, `llm-ctl` makes a strict conceptual and operational distinction between **stopping the server**, **unloading a model from memory**, and **removing a model from disk**:

```text
                         ┌──────────────────────────────┐
                         │   Ollama Server (Daemon)     │
                         │   State: RUNNING / STOPPED   │
                         └──────────────┬───────────────┘
                                        │
           ┌────────────────────────────┴────────────────────────────┐
           ▼                                                         ▼
┌─────────────────────────────┐                           ┌─────────────────────┐
│    GPU VRAM / Host RAM      │                           │    Disk Storage     │
│  (Active Inference Memory)  │                           │ (~/.ollama/models/) │
├─────────────────────────────┤                           ├─────────────────────┤
│ • Model weights loaded      │      llm unload/free      │ • Model blobs saved │
│ • Occupies 2GB–4GB VRAM     │ ────────────────────────> │ • 0 MB VRAM used    │
│ • Instant response time     │ <──────────────────────── │ • Persisted on disk │
└─────────────────────────────┘      llm switch/chat      └──────────┬──────────┘
                                                                     │
                                                                     │ llm remove
                                                                     ▼
                                                          ┌─────────────────────┐
                                                          │ Permanently Deleted │
                                                          │ (Reclaims disk space)│
                                                          └─────────────────────┘
```

### 1. Stopping the Server (`llm stop`)
* **What it does**: Shuts down the local Ollama process daemon (`systemctl --user stop ollama` or kills the background daemon).
* **When to use**: When you are completely done using local LLMs for the day and want to ensure zero background CPU, system sockets, or services are active.
* **Effect on models**: `llm-ctl` automatically evicts any loaded models from VRAM before stopping the daemon so that GPU memory is cleanly recovered.

### 2. Unloading from Memory (`llm unload` or `llm free`)
* **What it does**: Sends an eviction request (`keep_alive: 0`) to Ollama to unload model weights from GPU VRAM and host RAM immediately.
* **When to use**: When you need your GPU VRAM freed to 0 MB (e.g. before launching a 3D game, opening Blender, training a neural net, or compiling a massive Rust project), but you want to keep the model files on disk for later use.
* **Effect on models**: **Zero files are deleted.** The model remains installed and ready. The moment you run `llm chat` or invoke a coding agent, Ollama simply reloads it from disk.

### 3. Removing from Disk (`llm remove <model>`)
* **What it does**: Permanently deletes the model files and weight manifests from `~/.ollama/models/` filesystem storage.
* **When to use**: When you are running low on SSD disk space and no longer need that specific model.
* **Effect on models**: Model weights are unlinked from disk. To use the model again in the future, you must re-download it via `llm pull <model>`.

---

## 11. Configuration & Storage Locations (XDG Compliance)

`llm-ctl` strictly follows the **XDG Base Directory Specification** to keep your Linux `$HOME` tidy and prevent hardcoded directory pollution:

| Component | Standard Path | Environment Variable Override | Purpose |
|:---|:---|:---|:---|
| **Configuration** | `~/.config/llm-ctl/config.json` | `$XDG_CONFIG_HOME/llm-ctl/config.json` | Active model selection, endpoint host, and user preferences. |
| **State / History** | `~/.local/state/llm-ctl/history` | `$XDG_STATE_HOME/llm-ctl/history` | Interactive shell readline command history. |
| **Logs** | `~/.local/state/llm-ctl/logs/` | `$XDG_STATE_HOME/llm-ctl/logs/` | Subcommand execution and service event logs. |
| **Cache** | `~/.cache/llm-ctl/` | `$XDG_CACHE_HOME/llm-ctl/` | Temporary runtime session data. |
| **Executable Launchers** | `~/.local/bin/llm-ctl`<br>`~/.local/bin/llm` | Standard user binary path | Zero-privilege user launchers. |
| **Installed Source** | `~/.local/share/llm-ctl/` | `$HOME/.local/share/llm-ctl/` | Repository source when installed via curl. |

### Inspecting Configuration via CLI
```bash
# Print configuration file contents
llm config show

# Print configuration file absolute path
llm config path

# Set active model directly
llm config set active_model qwen2.5-coder:1.5b
```

---

## 12. Troubleshooting & `doctor` Diagnostics

`llm-ctl` includes a built-in diagnostic auditor that verifies your system stack in seconds:

```bash
llm doctor
```

### What `doctor` Inspects:
1. **Ollama Service Health**: Tests REST reachability at `http://127.0.0.1:11434/api/version`.
2. **NVIDIA GPU & Drivers**: Checks `nvidia-smi` accessibility, VRAM allocation, GPU core temperature, and power consumption.
3. **System RAM Headroom**: Inspects `/proc/meminfo` and alerts if available memory drops below 1.0 GiB to prevent OOM panics.
4. **Active Model Validation**: Verifies whether the configured active model is actually downloaded and ready, and checks if it is currently memory-mapped in VRAM.
5. **Coding Agent Binaries**: Verifies presence of `claude`, `opencode`, and `dsh` in `$PATH`.
6. **Configuration Integrity**: Validates read/write permissions and JSON syntax of `~/.config/llm-ctl/config.json`.

### Common Issues & Remediation

#### 1. "Cannot connect to Ollama at http://127.0.0.1:11434"
- **Cause**: Ollama service is stopped or not installed.
- **Fix**: Run `llm start` or start Ollama directly:
  ```bash
  systemctl --user start ollama   # If running systemd unit
  ollama serve                    # Direct terminal daemon
  ```

#### 2. "nvidia-smi detected but failed to query GPU metrics"
- **Cause**: Kernel module mismatch after an Ubuntu kernel update.
- **Fix**: Re-check driver status with `nvidia-smi`. A reboot or running `sudo systemctl restart systemd-modules-load` may be required.

#### 3. "No dedicated NVIDIA GPU detected (Running in CPU mode)"
- **Cause**: Running on an Intel/AMD iGPU machine or inside a virtual machine without GPU passthrough.
- **Fix**: `llm-ctl` continues to work normally using CPU inference. For optimal speed on CPU, stick with smaller quantized models like `qwen2.5-coder:1.5b` or `deepseek-r1:1.5b`.

#### 4. "Command not found: llm"
- **Cause**: `~/.local/bin` is missing from your `$PATH`.
- **Fix**: Add the following to `~/.bashrc` (or `~/.zshrc`):
  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```
  Then reload your shell: `source ~/.bashrc`.

---

## 13. Security Considerations & Uninstallation

### Security Model
- **User-Space Exclusivity**: `llm-ctl` requires no root or `sudo` permissions to install or execute.
- **Localhost Loopback Only**: Connects exclusively to the local Ollama loopback socket (`127.0.0.1:11434`). It never sends model queries, prompts, or telemetry to external cloud servers.
- **Atomic File Operations**: All config synchronization writes to temporary files first (`.tmp.<pid>`) and executes `os.fsync` before renaming into place, preventing file corruption if interrupted.

### Clean Uninstallation

`llm-ctl` ships with a dedicated uninstaller that safely removes binaries while preserving your downloaded models and user settings:

#### Standard Uninstall (Preserves Models and Configs)
```bash
./scripts/uninstall.sh
```
This removes:
- `~/.local/bin/llm-ctl` and `~/.local/bin/llm`
- `~/.local/share/llm-ctl` (if installed via curl)
- `~/.cache/llm-ctl`

> [!NOTE]
> Your Ollama daemon, installed model weights (`~/.ollama/`), and custom configs (`~/.config/llm-ctl/`) are left completely intact.

#### Complete Purge (Removes Configuration and State)
To remove user configurations and history as well:
```bash
./scripts/uninstall.sh --purge
```

---

## 14. Known Limitations

- **Ollama Backend Focus**: V1 is purpose-built to orchestrate Ollama. Native support for standalone llama.cpp server and vLLM is scheduled for subsequent minor releases.
- **Single-GPU Optimization**: Telemetry and VRAM calculations are currently focused on primary GPU index 0 (optimized for single-GPU laptops such as the NVIDIA RTX 3050). Multi-GPU tensor parallelism selection will be expanded in V2.
- **Default Agent Config Paths**: Configuration synchronization expects standard user paths (`~/.claude/settings.json` and `~/.config/opencode/opencode.jsonc`). Custom multi-tenant path overrides can be set directly in `config.json`.

---

## 15. Roadmap

- [x] **Linux V1 Release (`v1.0.0`)**: Real-time TUI, single-model VRAM isolation, server lifecycle controls, multi-agent config sync, doctor diagnostics, and XDG compliance.
- [ ] **v1.1 (Multi-GPU Selection)**: Support for selecting specific GPU indexes (`--gpu 1`) and monitoring multi-GPU heterogeneous setups.
- [ ] **v1.2 (Alternative Inference Backends)**: Connect directly to `llama.cpp` server (`llama-server`) and `vLLM` endpoints.
- [ ] **v1.3 (Automated Token Benchmarking)**: Built-in `llm bench <model>` tool measuring tokens/sec and Time-To-First-Token (TTFT) on your hardware.
- [ ] **v2.0 (Dynamic VRAM Autoscaler)**: Background daemon with configurable inactivity timeouts that automatically hibernates models to 0 MB VRAM when coding agents are idle.

---

## 16. License & Contributing

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

### Contributing
Contributions, issue reports, and feedback are welcome!
1. Fork the repository on GitHub.
2. Create a descriptive feature branch (`git checkout -b feat/telemetry-upgrade`).
3. Run test suite: `PYTHONPATH=src python3 -m unittest discover -s tests`.
4. Submit a pull request.
