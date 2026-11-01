"""
Diagnostic health checks and system audit for LLM-CTL.
Inspects Ollama connectivity, GPU/VRAM health, memory limits, coding agent binaries,
and configuration consistency, presenting actionable remediation steps.
"""

import os
import shutil
import urllib.request
import json
import subprocess
from .terminal import (
    BOLD, DIM, RESET, CYAN, BRIGHT_CYAN, GREEN, BRIGHT_GREEN,
    YELLOW, BRIGHT_YELLOW, RED, BRIGHT_RED, WHITE, BRIGHT_WHITE
)
from .hardware import (
    get_service_status, get_gpu_stats, get_system_ram,
    get_installed_models, get_loaded_models, OLLAMA_HOST
)
from .orchestrator import get_active_model, CONFIG_FILE

def check_ollama() -> tuple[bool, str, str]:
    """Checks Ollama REST API and systemd status."""
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/version")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode())
            version = data.get("version", "unknown")
            return True, f"Ollama v{version} reachable at {OLLAMA_HOST}", ""
    except Exception as e:
        return False, f"Cannot connect to Ollama at {OLLAMA_HOST}", "Run 'systemctl --user start ollama' or 'ollama serve'"

def check_gpu() -> tuple[bool, str, str]:
    """Inspects NVIDIA GPU status and VRAM capacity."""
    stats = get_gpu_stats()
    if stats:
        name = stats.get("name", "NVIDIA GPU")
        vram_total = stats.get("total_mb", 0)
        vram_used = stats.get("used_mb", 0)
        temp = stats.get("temp_c", "N/A")
        util = stats.get("util_pct", 0)
        return True, f"{name} ({vram_used:.0f}/{vram_total:.0f} MiB VRAM, util: {util}%, temp: {temp}°C)", ""
    
    # Check if nvidia-smi exists but failed
    if shutil.which("nvidia-smi"):
        return False, "nvidia-smi detected but failed to query GPU metrics", "Check NVIDIA driver installation (nvidia-smi)"
    return False, "No dedicated NVIDIA GPU detected (Running in CPU mode)", "Local models will run on CPU / RAM. Consider smaller quantized models (1B-3B)."

def check_ram() -> tuple[bool, str, str]:
    """Inspects Linux system RAM and available headroom."""
    ram = get_system_ram()
    total = ram.get("total_gb", 0)
    avail = ram.get("free_gb", 0)
    used = ram.get("used_gb", 0)
    if total > 0:
        if avail < 1.0:
            return False, f"{used:.1f}/{total:.1f} GiB used (Warning: <1 GiB available)", "Free up system RAM before loading large 7B+ models to prevent OOM kills."
        return True, f"{used:.1f}/{total:.1f} GiB system memory ({avail:.1f} GiB available)", ""
    return False, "Unable to inspect /proc/meminfo", "Ensure /proc filesystem is mounted."

def check_active_model() -> tuple[bool, str, str]:
    """Checks active model configuration against installed local models."""
    active = get_active_model()
    installed = get_installed_models()
    names = [m.get("name", "") for m in installed]
    
    if not installed:
        return False, f"Active model is '{active}' but no models are installed locally", "Run 'llm pull qwen2.5-coder:3b' to download your first model."
    
    matched = any(active == n or active == n.split(":")[0] or n.startswith(active) for n in names)
    if matched:
        # Check if loaded into VRAM
        loaded = get_loaded_models()
        is_loaded = any(active in m.get("name", "") for m in loaded)
        state_str = "loaded in VRAM" if is_loaded else "stored on disk (ready on query)"
        return True, f"Active model '{active}' is verified installed ({state_str})", ""
    return False, f"Active model '{active}' is NOT found among installed models", f"Installed models: {', '.join(names[:4])}. Run 'llm switch <model>' to select an installed model."

def check_coding_agents() -> list[tuple[str, bool, str]]:
    """Checks installed status of supported coding agents: Claude Code, OpenCode, Pi, DSH."""
    agents = [
        ("Claude Code", "claude", "npm i -g @anthropic-ai/claude-code"),
        ("OpenCode CLI", "opencode", "curl -fsSL https://opencode.ai/install.sh | bash"),
        ("Pi Coding Agent", "pi", "npm i -g @earendil-works/pi-coding-agent"),
        ("DeepSeek Harness", "dsh", "npm i -g deepseek-harness")
    ]
    results = []
    for name, binary, install_hint in agents:
        found = shutil.which(binary) is not None
        if found:
            results.append((name, True, f"Binary '{binary}' detected in PATH"))
        else:
            results.append((name, False, f"Not installed. Install via: {install_hint}"))
    return results

def check_config_file() -> tuple[bool, str, str]:
    """Inspects configuration file and permissions."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            if "active_model" in data:
                return True, f"Configuration valid at {CONFIG_FILE}", ""
            return False, f"Configuration at {CONFIG_FILE} missing 'active_model' key", "Run 'llm switch <model>' to re-write configuration."
        except Exception as e:
            return False, f"Failed parsing {CONFIG_FILE}: {e}", "Remove or repair ~/.config/llm-ctl/config.json"
    return True, f"Configuration will be initialized at {CONFIG_FILE} on first switch", ""

def run_doctor():
    """Runs all health checks and prints a formatted diagnostic report."""
    print(f"\n  {BOLD}{BRIGHT_CYAN}LLM-CTL Diagnostic Doctor{RESET}")
    print(f"  {DIM}Inspecting local runtime, drivers, memory headroom, and agent hooks...{RESET}\n")

    checks = [
        ("Ollama Service", check_ollama()),
        ("NVIDIA GPU / VRAM", check_gpu()),
        ("System Memory", check_ram()),
        ("Active Model State", check_active_model()),
        ("Config Integrity", check_config_file())
    ]

    all_passed = True
    issues = []

    for label, (passed, msg, hint) in checks:
        if passed:
            print(f"  {BRIGHT_GREEN}✔{RESET} {BOLD}{WHITE}{label:<22}{RESET} {DIM}{msg}{RESET}")
        else:
            all_passed = False
            print(f"  {BRIGHT_RED}✖{RESET} {BOLD}{WHITE}{label:<22}{RESET} {YELLOW}{msg}{RESET}")
            if hint:
                issues.append((label, hint))

    print(f"\n  {BOLD}{WHITE}Coding Agent Integrations:{RESET}")
    agent_results = check_coding_agents()
    for name, found, msg in agent_results:
        mark = f"{BRIGHT_GREEN}✔{RESET}" if found else f"{DIM}○{RESET}"
        status_text = f"{WHITE}Detected{RESET}" if found else f"{DIM}Optional / Not Found{RESET}"
        print(f"    {mark} {name:<18} [{status_text}] {DIM}{msg}{RESET}")

    if issues:
        print(f"\n  {BOLD}{YELLOW}Actionable Remediation Steps:{RESET}")
        for label, hint in issues:
            print(f"    • {BOLD}{label}:{RESET} {hint}")
    else:
        print(f"\n  {BRIGHT_GREEN}✔ All core systems operational! Local LLM runtime is healthy.{RESET}")

    print()
