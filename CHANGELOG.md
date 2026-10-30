# Changelog

All notable changes to the **LLM-CTL** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-30

### Initial Linux V1 Release

LLM-CTL V1 is a lightweight, command-driven Linux CLI and interactive TUI built for local LLM lifecycle management, VRAM orchestration on resource-constrained hardware (tuned for 4 GB VRAM / 8 GB RAM machines), and seamless configuration synchronization across developer coding agents.

### Added

- **Interactive Terminal Dashboard (TUI)**:
  - Real-time ASCII banner and system status card formatted for SpaceMono terminals.
  - Single-keypress shortcuts for rapid switching, model pulling, VRAM clearing, chat, and agent launches.
  - Integrated readline-driven command REPL with persistent history support.

- **System & GPU Telemetry Engine**:
  - Live NVIDIA GPU telemetry: VRAM consumption, utilization percentage, temperature, and power draw queried via `nvidia-smi`.
  - Host RAM telemetry: Total, used, and available headroom queried via `/proc/meminfo`.
  - Ollama daemon connection state and REST API version detection.
  - Non-interactive `--json` output flag on `status`, `models`, and `config` commands for script, tmux, and status bar integration.

- **Runtime Server Lifecycle Management**:
  - `llm start` / `llm run`: Starts the local Ollama daemon via `systemctl --user start ollama` with automatic fallback to background `ollama serve`.
  - `llm stop`: Gracefully flushes active models from VRAM before shutting down the server daemon.
  - `llm restart`: Safely cycles the server process and re-establishes socket availability.

- **Strict VRAM Orchestration & Memory Lifecycle**:
  - `llm unload` / `llm free`: Explicitly purges active models from GPU VRAM back to 0 MB without deleting model weights from disk storage.
  - Single-model focus design to prevent out-of-memory (OOM) kernel kills on systems with 4 GB VRAM or 8 GB host RAM.

- **Model Discovery & Hot-Swapping**:
  - `llm switch <model>` / `llm use`: Instantly switches the active model, evicts obsolete weights from VRAM, synchronizes agent configuration profiles, and pre-warms the target model.
  - `llm models` / `llm ls`: Aligns installed models with parameter size, quantization level, disk footprint, and loaded VRAM indicators (`★ [IN VRAM]`, `◈ [ACTIVE]`, `[STORED]`).
  - `llm pull <model>`: Curated model catalog with live streaming download progress bars and VRAM feasibility badges (`🟢 100% GPU`, `🟡 Hybrid`, `🔴 Heavy`).
  - `llm remove <model>` / `llm rm`: Permanently deletes model weights from disk with confirmation prompt and `-y` flag for scripts.
  - `llm chat [model]`: Direct terminal chat session connected to the active or requested model.

- **Atomic Multi-Agent Configuration Synchronization**:
  - Automatically updates configuration profiles whenever the active model is switched:
    - **Claude Code**: Updates `~/.claude/settings.json` (`env.ANTHROPIC_BASE_URL`, `model`).
    - **OpenCode CLI**: Updates `~/.config/opencode/opencode.jsonc` (`model: "ollama/<model>"`).
    - **DeepSeek Harness**: Patches `cordis.patch.yml` for local endpoint coordination.
  - Safe atomic file writes using temporary files and filesystem synchronization (`os.fsync`) to prevent corrupted config files.
  - `llm agents <claude|opencode|dsh>` launcher with pre-configured local environment variables.

- **System Diagnostics (`llm doctor`)**:
  - Comprehensive health auditing: Ollama service reachability, NVIDIA GPU/CUDA drivers, system RAM headroom, active model validation, installed coding agent binaries, and config file permissions.
  - Actionable remediation suggestions for every failing diagnostic check.

- **Standards Compliance & Shell Integration**:
  - Full XDG Base Directory specification compliance:
    - Configuration: `~/.config/llm-ctl/config.json`
    - State & History: `~/.local/state/llm-ctl/history`
    - Cache: `~/.cache/llm-ctl/`
  - Automated migration of legacy configuration and history files.
  - Native shell completion scripts for **Bash** (`completions/llm.bash`), **Zsh** (`completions/llm.zsh`), and **Fish** (`completions/llm.fish`).
  - Dual binary entry points: `llm-ctl` and `llm`.

- **User-Space Installation & Packaging**:
  - Zero-root curl installer (`scripts/install.sh`) supporting Ubuntu, Debian, Fedora, Arch, and generic POSIX Linux.
  - Safe uninstaller (`scripts/uninstall.sh`) preserving user configurations and model weights by default, with an optional `--purge` flag.
  - Standard Python packaging (`pyproject.toml`) targeting Python >= 3.9 with minimal dependencies (`rich>=13.0.0`).
  - Comprehensive unit test suite covering telemetry, banner rendering, model hub feasibility calculations, and CLI dispatcher.
