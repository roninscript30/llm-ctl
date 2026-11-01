"""
Main CLI router and subcommand dispatcher for llm-ctl.
Optimized for SpaceMono-Regular font and matches the refined terminal design.
Provides full non-interactive scripting, JSON output, and robust runtime controls.
"""

import sys
import os
import json
import shutil
import subprocess
import time

from .banner import (
    render_reference_banner,
    render_reference_status_card,
    render_reference_quick_commands
)
from .hardware import (
    get_service_status, get_gpu_stats, get_system_ram,
    get_loaded_models, get_installed_models, OLLAMA_HOST
)
from .orchestrator import (
    get_active_model, save_active_model, switch_model,
    sync_all_configs, sync_opencode, sync_pi,
    get_model_status, CONFIG_FILE
)
from .runtime import (
    start_server, stop_server, restart_server,
    unload_model, unload_all_models, remove_model,
    get_server_version
)
from .hub import HUB_MODELS, render_hub_table, pull_model_stream
from .interactive import run_interactive_repl
from .doctor import run_doctor
from .paths import ensure_directories
from .terminal import BOLD, DIM, RESET, BRIGHT_GREEN, CYAN, WHITE, YELLOW, RED

ensure_directories()

def print_status(json_output: bool = False):
    """Outputs current hardware status, active model, and loaded VRAM models."""
    active = get_active_model()
    is_active = get_service_status()
    gpu = get_gpu_stats()
    ram = get_system_ram()
    loaded = get_loaded_models()
    installed = get_installed_models()
    version = get_server_version() if is_active else None

    if json_output:
        data = {
            "active_model": active,
            "active_model_status": get_model_status(active),
            "endpoint": OLLAMA_HOST,
            "service_active": is_active,
            "version": version,
            "gpu": gpu,
            "system_ram": ram,
            "loaded_models": loaded,
            "installed_models_count": len(installed)
        }
        print(json.dumps(data, indent=2))
        return

    # Render clean terminal layout
    print()
    print(render_reference_banner())
    print()
    print(render_reference_status_card(is_active, OLLAMA_HOST, gpu, ram, active, loaded, installed, version_str=version))
    print()
    print(render_reference_quick_commands())
    print()

def cmd_models(json_output: bool = False):
    """Lists installed models in a clean aligned list or JSON."""
    installed = get_installed_models()
    active = get_active_model()
    loaded = get_loaded_models()
    loaded_names = [m.get("name", "") for m in loaded]

    if json_output:
        output_list = []
        for m in installed:
            name = m.get("name", "")
            output_list.append({
                "name": name,
                "size_bytes": m.get("size", 0),
                "details": m.get("details", {}),
                "is_active": (name == active or name.startswith(active)),
                "is_loaded": any(name == ln or name.startswith(ln) for ln in loaded_names),
                "status": get_model_status(name)
            })
        print(json.dumps(output_list, indent=2))
        return

    print(f"\n  {BOLD}{WHITE}Installed Local Models ({len(installed)}):{RESET}")
    if not installed:
        print(f"  {DIM}No models installed. Type 'llm pull <model>' to download one.{RESET}\n")
        return

    for idx, m in enumerate(installed, 1):
        name = m.get("name", "")
        size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
        details = m.get("details", {})
        param = details.get("parameter_size", "-")
        quant = details.get("quantization_level", "-")

        is_active = (name == active or name.startswith(active))
        is_loaded = any(name == ln or name.startswith(ln) for ln in loaded_names)

        if is_loaded:
            mark = f" {BRIGHT_GREEN}★ [IN VRAM]{RESET}"
        elif is_active:
            mark = f" {CYAN}◈ [ACTIVE]{RESET}"
        else:
            mark = f" {DIM}[STORED]{RESET}"

        print(f"  • {CYAN}{name:<26}{RESET} {DIM}({size_gb:.2f} GB · {param} · {quant}){RESET}{mark}")
    print()

def cmd_launch(args: list[str]):
    """Launches one of the coding agent clients."""
    if not args:
        print(f"\n  {BOLD}{YELLOW}Usage:{RESET} llm agents <claude|opencode|pi|dsh>\n")
        return

    target = args[0].lower()
    extra = args[1:]
    active = get_active_model()

    if target in ("claude", "cc"):
        if not shutil.which("claude"):
            print(f"\n  {RED}Error: 'claude' CLI is not found in PATH.{RESET}")
            print(f"  {DIM}Install via: npm i -g @anthropic-ai/claude-code{RESET}\n")
            sys.exit(1)
        print(f"\n  {BOLD}{CYAN}Starting Claude Code with active model:{RESET} {BRIGHT_GREEN}{active}{RESET}\n")
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = OLLAMA_HOST
        env["ANTHROPIC_API_KEY"] = "ollama"
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = active
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = active
        subprocess.run(["claude", "--model", active] + extra, env=env)

    elif target in ("opencode", "oc"):
        if not shutil.which("opencode"):
            print(f"\n  {RED}Error: 'opencode' CLI is not found in PATH.{RESET}")
            print(f"  {DIM}Install via: curl -fsSL https://opencode.ai/install.sh | bash{RESET}\n")
            sys.exit(1)
        sync_opencode(active)
        print(f"\n  {BOLD}{CYAN}Starting OpenCode with active model:{RESET} {BRIGHT_GREEN}ollama/{active}{RESET}\n")
        subprocess.run(["opencode", "--model", f"ollama/{active}"] + extra)

    elif target in ("pi",):
        if not shutil.which("pi"):
            print(f"\n  {RED}Error: 'pi' CLI is not found in PATH.{RESET}")
            print(f"  {DIM}Install via: npm i -g @earendil-works/pi-coding-agent{RESET}\n")
            sys.exit(1)
        sync_pi(active)
        print(f"\n  {BOLD}{CYAN}Starting Pi Coding Agent with active model:{RESET} {BRIGHT_GREEN}ollama/{active}{RESET}\n")
        subprocess.run(["pi", "--provider", "ollama", "--model", active] + extra)

    elif target in ("dsh", "deepseek"):
        if not shutil.which("dsh"):
            print(f"\n  {RED}Error: 'dsh' CLI is not found in PATH.{RESET}")
            print(f"  {DIM}Install via: npm i -g deepseek-harness{RESET}\n")
            sys.exit(1)
        mode = extra[0] if extra else "web"
        if mode in ("web", "ui"):
            print(f"\n  {BOLD}{CYAN}Starting DeepSeek Harness Web UI at http://127.0.0.1:3080...{RESET}\n")
            subprocess.run(["dsh", "web"])
        else:
            subprocess.run(["dsh", "headless"] + extra)

    else:
        print(f"\n  {BOLD}{RED}Unknown agent client:{RESET} '{target}'. Available: claude, opencode, pi, dsh\n")
        sys.exit(1)

def print_help():
    """Prints help message."""
    print()
    print(render_reference_quick_commands())
    print(f"\n  {BOLD}Usage:{RESET} llm-ctl <command> [options]")
    print(f"\n  {BOLD}Runtime Server Controls:{RESET}")
    print(f"    start / run        Start local Ollama server")
    print(f"    stop               Stop local Ollama server gracefully")
    print(f"    restart            Restart local Ollama server")
    print(f"\n  {BOLD}Model Management:{RESET}")
    print(f"    models / ls        List installed models (supports --json)")
    print(f"    switch <model>     Switch active model and pre-warm into VRAM")
    print(f"    pull <model>       Download model weights from hub with progress")
    print(f"    unload [model]     Unload model(s) from VRAM without deleting files")
    print(f"    remove <model>     Permanently delete model from disk (-y to skip prompt)")
    print(f"    chat [model]       Start interactive chat with local model")
    print(f"\n  {BOLD}Integrations & Diagnostics:{RESET}")
    print(f"    status             Show system & model status (supports --json)")
    print(f"    doctor             Diagnose environment, drivers, agents, config")
    print(f"    agents <name>      Launch coding agent (claude, opencode, pi, dsh)")
    print(f"    config [show|set]  Inspect or edit configuration (supports --json)")
    print(f"    help               Show this command reference")
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
        cmd_models(json_output=is_json)

    elif cmd in ("switch", "use"):
        if not rest:
            cmd_models()
            choice = input(f"  {CYAN}Enter model to switch to: {RESET}").strip()
            if choice:
                ok = switch_model(choice)
                if not ok:
                    sys.exit(1)
        else:
            ok = switch_model(rest[0])
            if not ok:
                sys.exit(1)

    elif cmd == "pull":
        if not rest:
            installed = get_installed_models()
            installed_ids = {m.get("name", "") for m in installed}
            print()
            print(render_hub_table(installed_ids))
            print(f"\n  {YELLOW}Usage:{RESET} llm pull <model_name>\n")
            sys.exit(1)
        success = pull_model_stream(rest[0])
        if not success:
            sys.exit(1)

    elif cmd in ("start", "run"):
        print(f"\n  {CYAN}Starting Ollama server...{RESET}")
        ok, msg = start_server()
        if ok:
            print(f"  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
        else:
            print(f"  {RED}✖ {msg}{RESET}\n")
            sys.exit(1)

    elif cmd == "stop":
        print(f"\n  {YELLOW}Stopping Ollama server...{RESET}")
        ok, msg = stop_server()
        if ok:
            print(f"  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
        else:
            print(f"  {RED}✖ {msg}{RESET}\n")
            sys.exit(1)

    elif cmd == "restart":
        print(f"\n  {CYAN}Restarting Ollama server...{RESET}")
        ok, msg = restart_server()
        if ok:
            print(f"  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
        else:
            print(f"  {RED}✖ {msg}{RESET}\n")
            sys.exit(1)

    elif cmd in ("unload", "free", "evict"):
        if rest:
            ok, msg = unload_model(rest[0])
            if ok:
                print(f"\n  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
            else:
                print(f"\n  {RED}✖ {msg}{RESET}\n")
                sys.exit(1)
        else:
            evicted = unload_all_models()
            if evicted:
                print(f"\n  {BRIGHT_GREEN}✔ Unloaded {len(evicted)} model(s): {', '.join(evicted)}. GPU VRAM is 100% free!{RESET}\n")
            else:
                print(f"\n  {BRIGHT_GREEN}✔ GPU VRAM is completely free (0 models loaded).{RESET}\n")

    elif cmd in ("remove", "rm", "delete"):
        if not rest:
            print(f"\n  {RED}Usage:{RESET} llm remove <model_name> [-y]\n")
            sys.exit(1)
        target = rest[0]
        force = "-y" in rest or "--yes" in rest
        if not force:
            confirm = input(f"  {YELLOW}Are you sure you want to permanently delete model weights for '{target}'? [y/N]: {RESET}").strip().lower()
            if confirm not in ("y", "yes"):
                print(f"  {DIM}Operation cancelled.{RESET}\n")
                return

        ok, msg = remove_model(target)
        if ok:
            print(f"  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
        else:
            print(f"  {RED}✖ {msg}{RESET}\n")
            sys.exit(1)

    elif cmd == "doctor":
        run_doctor()

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

    elif cmd in ("pi",):
        cmd_launch(["pi"] + rest)

    elif cmd in ("dsh", "deepseek"):
        cmd_launch(["dsh"] + rest)

    elif cmd == "config":
        if is_json:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    print(f.read().strip())
            else:
                print(json.dumps({"active_model": get_active_model()}, indent=2))
            return

        if not rest or rest[0] in ("show", "view"):
            print(f"\n  {BOLD}{WHITE}Configuration:{RESET} {DIM}{CONFIG_FILE}{RESET}")
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    print(f"  {f.read().strip()}")
            else:
                print(f"  {DIM}No config file found. Default model: {get_active_model()}{RESET}")
            print()
        elif rest[0] == "path":
            print(CONFIG_FILE)
        elif rest[0] == "set" and len(rest) >= 3:
            key, val = rest[1], rest[2]
            if key == "active_model":
                save_active_model(val)
                sync_all_configs(val)
                print(f"  {BRIGHT_GREEN}✔ Set active_model to {val}{RESET}\n")
            else:
                print(f"  {YELLOW}Unknown config key:{RESET} {key}\n")
                sys.exit(1)
        else:
            print(f"\n  {YELLOW}Usage:{RESET} llm config [show|path|set active_model <name>]\n")

    elif cmd in ("-h", "--help", "help"):
        print_help()

    else:
        print(f"\n  {RED}Unknown command:{RESET} '{cmd}'. Run 'llm help' for available commands.\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
