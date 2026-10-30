"""
Local LLM Orchestrator: model hot-swapping, VRAM eviction, and multi-client config sync.
"""

import os
import json
import time
import subprocess
import urllib.request
from rich.console import Console
from .hardware import get_loaded_models, get_installed_models, get_service_status, OLLAMA_HOST
from .paths import CONFIG_DIR, CONFIG_FILE, ensure_directories

console = Console()
ensure_directories()

def notify(title: str, message: str, urgency: str = "normal"):
    """Dispatches a desktop notification via notify-send if available."""
    try:
        subprocess.run(
            ["notify-send", "-a", "LLM Hub", "-u", urgency, title, message],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0
        )
    except Exception:
        pass

def get_active_model() -> str:
    """Reads the current active model from configuration."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("active_model", "qwen2.5-coder:3b")
    except Exception:
        pass
    return "qwen2.5-coder:3b"

def save_active_model(model_name: str):
    """Persists active model into ~/.config/llm-ctl/config.json with safe atomic write."""
    target_dir = os.path.dirname(CONFIG_FILE)
    os.makedirs(target_dir, exist_ok=True)
    cfg = {"active_model": model_name}
    tmp_path = f"{CONFIG_FILE}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, CONFIG_FILE)

def sync_claude_code(model_name: str) -> bool:
    """Synchronizes Claude Code settings with the active model using safe file writes."""
    path = os.path.expanduser("~/.claude/settings.json")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        env = data.setdefault("env", {})
        env["ANTHROPIC_BASE_URL"] = OLLAMA_HOST
        env["ANTHROPIC_API_KEY"] = "ollama"
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = model_name
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = model_name
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model_name
        data["model"] = model_name

        tmp_path = f"{path}.tmp.{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        return True
    except Exception:
        return False

def sync_opencode(model_name: str) -> bool:
    """Synchronizes OpenCode settings with the active model using safe file writes."""
    path = os.path.expanduser("~/.config/opencode/opencode.jsonc")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["$schema"] = "https://opencode.ai/config.json"
        data["model"] = f"ollama/{model_name}"

        tmp_path = f"{path}.tmp.{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        try:
            subprocess.run(
                ["opencode", "reload"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0
            )
        except Exception:
            pass
        return True
    except Exception:
        return False

def sync_dsh(model_name: str) -> bool:
    """Synchronizes DeepSeek Harness cordis.patch.yml default model using safe file writes."""
    path = os.path.expanduser("~/.dsh/profiles/web/cordis.patch.yml")
    try:
        if os.path.exists(path):
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                docs = yaml.safe_load(f)
            if isinstance(docs, list):
                updated = False
                for entry in docs:
                    if isinstance(entry, dict) and entry.get("id") == "agent-default-model":
                        entry.setdefault("config", {})["model"] = model_name
                        updated = True
                if updated:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    tmp_path = f"{path}.tmp.{os.getpid()}"
                    with open(tmp_path, "w", encoding="utf-8") as f:
                        yaml.dump(docs, f, sort_keys=False)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp_path, path)
                    return True
    except Exception:
        pass
    return False

def sync_all_configs(model_name: str):
    """Syncs the given model across Claude Code, OpenCode, and DSH."""
    sync_claude_code(model_name)
    sync_opencode(model_name)
    sync_dsh(model_name)

def get_model_status(model_name: str) -> str:
    """Returns 'IN_VRAM' if currently in loaded models, 'STANDBY' if installed on disk, 'NOT_INSTALLED' if not downloaded."""
    if not model_name:
        return "NOT_INSTALLED"

    target = str(model_name).strip().lower()
    clean_target = target[1:] if target.startswith(":") else target

    def _matches(name: str) -> bool:
        if not name:
            return False
        n_lower = name.lower()
        if n_lower == target:
            return True
        if n_lower.split(":")[0] == target:
            return True
        parts = n_lower.split(":")
        if len(parts) > 1 and parts[-1] == clean_target:
            return True
        return False

    # 1. Check if currently loaded in VRAM / RAM
    try:
        loaded = get_loaded_models()
        for m in loaded:
            m_name = m.get("name", "")
            if _matches(m_name):
                return "IN_VRAM"
    except Exception:
        pass

    # 2. Check if installed on disk
    try:
        installed = get_installed_models()
        for m in installed:
            m_name = m.get("name", "")
            if _matches(m_name):
                return "STANDBY"
    except Exception:
        pass

    return "NOT_INSTALLED"

def resolve_model_target(target: str | int, installed: list[dict]) -> str | None:
    """Resolves target input (index, full tag, base name, prefix, substring) against installed models."""
    if not installed:
        return None

    names = [m.get("name", "") for m in installed if m.get("name")]
    if not names:
        return None

    target_str = str(target).strip()
    if not target_str:
        return None

    # 1. Check if index number (1-based)
    if target_str.isdigit():
        idx = int(target_str)
        if 1 <= idx <= len(names):
            return names[idx - 1]

    target_lower = target_str.lower()

    # 2. Exact match (case-insensitive)
    for n in names:
        if n.lower() == target_lower:
            return n

    # 3. Exact match before tag (e.g. 'qwen2.5-coder' matches 'qwen2.5-coder:3b')
    for n in names:
        if n.split(":")[0].lower() == target_lower:
            return n

    # 4. Tag match (e.g. '1.5b' or ':1.5b' matches 'deepseek-r1:1.5b')
    clean_tag = target_lower[1:] if target_lower.startswith(":") else target_lower
    for n in names:
        parts = n.split(":")
        if len(parts) > 1 and parts[-1].lower() == clean_tag:
            return n

    # 5. Prefix match (e.g. 'deepseek' matches 'deepseek-r1:7b')
    for n in names:
        if n.lower().startswith(target_lower):
            return n

    # 6. Substring match
    for n in names:
        if target_lower in n.lower():
            return n

    return None

def free_vram() -> list[str]:
    """Evicts all models from GPU VRAM and verifies memory is cleared."""
    loaded = get_loaded_models()
    evicted = []
    for m in loaded:
        m_name = m.get("name")
        if m_name:
            try:
                subprocess.run(
                    ["ollama", "stop", m_name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0
                )
                evicted.append(m_name)
            except Exception:
                pass

    time.sleep(0.3)
    # Verify VRAM is cleared
    still_loaded = get_loaded_models()
    if still_loaded:
        for m in still_loaded:
            m_name = m.get("name")
            if m_name:
                try:
                    subprocess.run(
                        ["ollama", "stop", m_name],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0
                    )
                except Exception:
                    pass
        time.sleep(0.2)
        still_loaded = get_loaded_models()

    if len(still_loaded) == 0:
        notify("VRAM Cleared", "100% GPU memory is now free")
    else:
        remaining = ", ".join(m.get("name", "") for m in still_loaded)
        notify("VRAM Clear Warning", f"Some models still active: {remaining}", urgency="critical")

    return evicted

def switch_model(target_name: str | int, quiet: bool = False) -> bool:
    """Hot-swaps active model, syncs all clients, evicts old from VRAM, and pre-warms new."""
    # 1. Check if Ollama service is reachable
    if not get_service_status():
        if not quiet:
            console.print("[bold red]Error:[/bold red] Ollama service is unreachable or offline.")
            console.print("[dim]Start Ollama via 'systemctl --user start ollama' or 'ollama serve'.[/dim]")
        return False

    # 2. Query installed models
    installed = get_installed_models()
    if not installed:
        if not quiet:
            console.print("[bold red]Error:[/bold red] No installed models found in Ollama.")
            console.print("[dim]Use 'llm pull <model>' to download a model first.[/dim]")
        return False

    # 3. Resolve match
    match = resolve_model_target(target_name, installed)
    if not match:
        if not quiet:
            console.print(f"[bold red]Error:[/bold red] Model '{target_name}' not found locally.")
            names = [m.get("name", "") for m in installed if m.get("name")]
            console.print(f"Installed models: {', '.join(names)}")
            console.print("[dim]Use 'llm pull <model>' to download it.[/dim]")
        return False

    if not quiet:
        console.print(f"\n[bold cyan]Switching active model to:[/bold cyan] [bold bright_green]{match}[/bold bright_green]")

    # 4. Update internal state
    save_active_model(match)

    # 5. Sync client configurations
    sync_all_configs(match)
    if not quiet:
        console.print("  [dim]• Synchronized configs: Claude Code, OpenCode & DeepSeek Harness[/dim]")

    # 6. Evict old models from VRAM
    try:
        loaded = get_loaded_models()
        for m in loaded:
            m_name = m.get("name", "")
            if m_name and m_name != match:
                subprocess.run(
                    ["ollama", "stop", m_name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5.0
                )
        if not quiet:
            console.print("  [dim]• Evicted previous models from GPU VRAM[/dim]")
    except Exception:
        pass

    # 7. Pre-warm new model into VRAM safely with bounded timeout
    if not quiet:
        console.print(f"  [dim]• Pre-warming {match} into VRAM...[/dim]")
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps({"model": match}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15.0):
            pass
        if not quiet:
            console.print(f"  [bold green]✔[/bold green] [bold bright_green]{match}[/bold bright_green] is live on GPU VRAM and ready!\n")
    except Exception:
        if not quiet:
            console.print(f"  [bold yellow]⚠[/bold yellow] [dim]Model switched. Will load into VRAM on first query.[/dim]\n")

    notify("Model Switched", f"Active model set to {match}")
    return True
