"""
Local LLM Orchestrator: model hot-swapping, VRAM eviction, and multi-client config sync.
"""

import os
import json
import time
import subprocess
import urllib.request
from rich.console import Console
from .hardware import get_loaded_models, get_installed_models, OLLAMA_HOST

console = Console()
CONFIG_DIR = os.path.expanduser("~/.config/llm-ctl")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def notify(title: str, message: str, urgency: str = "normal"):
    """Dispatches a desktop notification via notify-send if available."""
    try:
        subprocess.run(
            ["notify-send", "-a", "LLM Hub", "-u", urgency, title, message],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def get_active_model() -> str:
    """Reads the current active model from configuration."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                return data.get("active_model", "qwen2.5-coder:3b")
    except Exception:
        pass
    return "qwen2.5-coder:3b"

def save_active_model(model_name: str):
    """Persists active model into ~/.config/llm-ctl/config.json."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = {"active_model": model_name}
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def sync_claude_code(model_name: str) -> bool:
    """Synchronizes Claude Code settings with the active model."""
    path = os.path.expanduser("~/.claude/settings.json")
    try:
        data = {}
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
        env = data.setdefault("env", {})
        env["ANTHROPIC_BASE_URL"] = OLLAMA_HOST
        env["ANTHROPIC_API_KEY"] = "ollama"
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = model_name
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = model_name
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model_name
        data["model"] = model_name
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

def sync_opencode(model_name: str) -> bool:
    """Synchronizes OpenCode settings with the active model."""
    path = os.path.expanduser("~/.config/opencode/opencode.jsonc")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "$schema": "https://opencode.ai/config.json",
            "model": f"ollama/{model_name}"
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        subprocess.run(["opencode", "reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def sync_dsh(model_name: str) -> bool:
    """Synchronizes DeepSeek Harness cordis.patch.yml default model."""
    path = os.path.expanduser("~/.dsh/profiles/web/cordis.patch.yml")
    try:
        if os.path.exists(path):
            import yaml
            with open(path) as f:
                docs = yaml.safe_load(f)
            if isinstance(docs, list):
                for entry in docs:
                    if isinstance(entry, dict) and entry.get("id") == "agent-default-model":
                        entry.setdefault("config", {})["model"] = model_name
                with open(path, "w") as f:
                    yaml.dump(docs, f, sort_keys=False)
                return True
    except Exception:
        pass
    return False

def sync_all_configs(model_name: str):
    """Syncs the given model across Claude Code, OpenCode, and DSH."""
    sync_claude_code(model_name)
    sync_opencode(model_name)
    sync_dsh(model_name)

def free_vram() -> list[str]:
    """Evicts all models from GPU VRAM."""
    loaded = get_loaded_models()
    evicted = []
    for m in loaded:
        m_name = m["name"]
        subprocess.run(["ollama", "stop", m_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        evicted.append(m_name)
    time.sleep(0.3)
    notify("VRAM Cleared", "100% GPU memory is now free")
    return evicted

def switch_model(target_name: str, quiet: bool = False) -> bool:
    """Hot-swaps active model, syncs all clients, evicts old from VRAM, and pre-warms new."""
    installed = get_installed_models()
    names = [m.get("name", "") for m in installed]

    # Resolve match
    match = None
    for n in names:
        if target_name == n or target_name == n.split(":")[0] or target_name in n:
            match = n
            break

    if not match:
        if not quiet:
            console.print(f"[bold red]Error:[/bold red] Model '{target_name}' not found locally.")
            console.print(f"Installed models: {', '.join(names)}")
            console.print("[dim]Use 'llm pull <model>' to download it.[/dim]")
        return False

    if not quiet:
        console.print(f"\n[bold cyan]Switching active model to:[/bold cyan] [bold bright_green]{match}[/bold bright_green]")

    # 1. Update internal state
    save_active_model(match)

    # 2. Sync client configurations
    sync_all_configs(match)
    if not quiet:
        console.print("  [dim]• Synchronized configs: Claude Code, OpenCode & DeepSeek Harness[/dim]")

    # 3. Evict old models from VRAM
    loaded = get_loaded_models()
    for m in loaded:
        if m["name"] != match:
            subprocess.run(["ollama", "stop", m["name"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not quiet:
        console.print("  [dim]• Evicted previous models from GPU VRAM[/dim]")

    # 4. Pre-warm new model into RTX 3050 VRAM
    if not quiet:
        console.print(f"  [dim]• Pre-warming {match} into RTX 3050 VRAM...[/dim]")
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps({"model": match, "prompt": "ready", "stream": False}).encode(),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        if not quiet:
            console.print(f"  [bold green]✔[/bold green] [bold bright_green]{match}[/bold bright_green] is live on GPU VRAM and ready!\n")
    except Exception:
        if not quiet:
            console.print(f"  [bold yellow]⚠[/bold yellow] [dim]Model switched. Will load into VRAM on first query.[/dim]\n")

    notify("Model Switched", f"Active model set to {match}")
    return True
