"""
Main CLI router and subcommand dispatcher for llm-ctl.
Optimized for SpaceMono-Regular font and matches the reference design.
"""

import sys
import os
import json
import subprocess

from .banner import (
    render_reference_banner,
    render_reference_status_card,
    render_reference_quick_commands
)
from .hardware import (
    get_service_status, get_gpu_stats, get_system_ram,
    get_loaded_models, get_installed_models, OLLAMA_HOST
)
from .orchestrator import get_active_model, switch_model, free_vram, sync_all_configs
from .hub import HUB_MODELS, render_hub_table, pull_model_stream
from .interactive import run_interactive_repl
from .terminal import BOLD, DIM, RESET, BRIGHT_GREEN, CYAN, WHITE, YELLOW, RED

BENCHMARK_RESULTS = os.path.expanduser("~/REPOS/dev-env/llm-experiments/results.json")

def print_status(json_output: bool = False):
    """Outputs current hardware status, active model, and loaded VRAM models."""
    active = get_active_model()
    is_active = get_service_status()
    gpu = get_gpu_stats()
    ram = get_system_ram()
    loaded = get_loaded_models()
    installed = get_installed_models()

    if json_output:
        data = {
            "active_model": active,
            "endpoint": OLLAMA_HOST,
            "service_active": is_active,
            "gpu": gpu,
            "system_ram": ram,
            "loaded_models": loaded,
            "installed_models_count": len(installed)
        }
        print(json.dumps(data, indent=2))
        return

    # Render reference screen layout
    print()
    print(render_reference_banner())
    print()
    print(render_reference_status_card(is_active, OLLAMA_HOST, gpu, ram, active))
    print()
    print(render_reference_quick_commands())
    print()

def cmd_models():
    """Lists installed models in a clean aligned list."""
    installed = get_installed_models()
    active = get_active_model()
    print(f"\n  {BOLD}{WHITE}Installed Local Models ({len(installed)}):{RESET}")
    for m in installed:
        name = m.get("name", "")
        size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
        details = m.get("details", {})
        param = details.get("parameter_size", "-")
        quant = details.get("quantization_level", "-")
        mark = f" {BRIGHT_GREEN}★ [ACTIVE]{RESET}" if name.startswith(active) else ""
        print(f"  • {CYAN}{name:<26}{RESET} {DIM}({size_gb:.2f} GB · {param} · {quant}){RESET}{mark}")
    print()

def cmd_launch(args: list[str]):
    """Launches one of the coding agent clients."""
    if not args:
        print(f"\n  {BOLD}{YELLOW}Usage:{RESET} llm agents <claude|opencode|dsh>\n")
        return

    target = args[0].lower()
    extra = args[1:]
    active = get_active_model()

    if target in ("claude", "cc"):
        print(f"\n  {BOLD}{CYAN}Starting Claude Code with active model:{RESET} {BRIGHT_GREEN}{active}{RESET}\n")
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = OLLAMA_HOST
        env["ANTHROPIC_API_KEY"] = "ollama"
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = active
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = active
        subprocess.run(["claude", "--model", active] + extra, env=env)
    elif target in ("opencode", "oc"):
        print(f"\n  {BOLD}{CYAN}Starting OpenCode with active model:{RESET} {BRIGHT_GREEN}ollama/{active}{RESET}\n")
        subprocess.run(["opencode", "--model", f"ollama/{active}"] + extra)
    elif target in ("dsh", "deepseek"):
        mode = extra[0] if extra else "web"
        if mode in ("web", "ui"):
            print(f"\n  {BOLD}{CYAN}Starting DeepSeek Harness Web UI at http://127.0.0.1:3080...{RESET}\n")
            subprocess.run(["dsh", "web"])
        else:
            subprocess.run(["dsh", "headless"] + extra)
    else:
        print(f"\n  {BOLD}{RED}Unknown agent client:{RESET} '{target}'. Available: claude, opencode, dsh\n")

def print_help():
    """Prints help message."""
    print()
    print(render_reference_quick_commands())
    print()

def main():
    args = sys.argv[1:]
    is_json = "--json" in args
    filtered_args = [a for a in args if a != "--json"]

    if not filtered_args:
        if sys.stdin.isatty():
            run_interactive_repl()
        else:
            print_status(json_output=is_json)
        return

    cmd = filtered_args[0].lower()
    rest = filtered_args[1:]

    if cmd in ("status", "info"):
        print_status(json_output=is_json)
    elif cmd in ("models", "ls", "list"):
        cmd_models()
    elif cmd in ("switch", "use"):
        if not rest:
            cmd_models()
            choice = input(f"  {CYAN}Enter model to switch to: {RESET}").strip()
            if choice:
                switch_model(choice)
        else:
            switch_model(rest[0])
    elif cmd == "pull":
        if not rest:
            print(f"\n  {RED}Usage:{RESET} llm pull <model_name>\n")
            sys.exit(1)
        pull_model_stream(rest[0])
    elif cmd in ("remove", "rm", "delete"):
        if not rest:
            print(f"\n  {RED}Usage:{RESET} llm remove <model_name>\n")
            sys.exit(1)
        subprocess.run(["ollama", "rm", rest[0]])
        print(f"  {BRIGHT_GREEN}✔ Removed {rest[0]}{RESET}\n")
    elif cmd in ("free", "purge", "unload"):
        evicted = free_vram()
        print(f"\n  {BRIGHT_GREEN}✔ Evicted {len(evicted)} model(s). 100% GPU VRAM is free!{RESET}\n")
    elif cmd == "chat":
        active = rest[0] if rest else get_active_model()
        print(f"\n  {BOLD}{CYAN}Connecting to {active}... (Type '/bye' to exit){RESET}\n")
        subprocess.run(["ollama", "run", active])
    elif cmd in ("agents", "launch"):
        cmd_launch(rest)
    elif cmd in ("claude", "cc"):
        cmd_launch(["claude"] + rest)
    elif cmd in ("opencode", "oc"):
        cmd_launch(["opencode"] + rest)
    elif cmd in ("dsh", "deepseek"):
        cmd_launch(["dsh"] + rest)
    elif cmd == "run":
        print(f"\n  {CYAN}Starting Ollama systemd background service...{RESET}")
        subprocess.run(["systemctl", "--user", "start", "ollama"])
        time.sleep(0.5)
        print(f"  {BRIGHT_GREEN}✔ Ollama service active{RESET}\n")
    elif cmd == "config":
        cfg_path = os.path.expanduser("~/.config/llm-ctl/config.json")
        print(f"\n  {BOLD}{WHITE}Configuration:{RESET} {DIM}{cfg_path}{RESET}")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                print(f"  {f.read().strip()}")
        print()
    elif cmd in ("-h", "--help", "help"):
        print_help()
    else:
        print(f"\n  {RED}Unknown command:{RESET} '{cmd}'. Run 'llm help' for available commands.\n")

if __name__ == "__main__":
    main()
