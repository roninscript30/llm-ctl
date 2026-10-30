"""
Main CLI router and subcommand dispatcher for llm-ctl.
Optimized for SpaceMono-Regular font and matches the reference design.
Provides full non-interactive scripting, JSON output, and robust error handling.
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
    free_vram, sync_all_configs, get_model_status, CONFIG_FILE
)
from .hub import HUB_MODELS, render_hub_table, pull_model_stream
from .interactive import run_interactive_repl
from .doctor import run_doctor
from .terminal import BOLD, DIM, RESET, BRIGHT_GREEN, CYAN, WHITE, YELLOW, RED

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
            "active_model_status": get_model_status(active),
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
    print(render_reference_status_card(is_active, OLLAMA_HOST, gpu, ram, active, loaded, installed))
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
        print(f"\n  {BOLD}{YELLOW}Usage:{RESET} llm agents <claude|opencode|dsh>\n")
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
        print(f"\n  {BOLD}{CYAN}Starting OpenCode with active model:{RESET} {BRIGHT_GREEN}ollama/{active}{RESET}\n")
        subprocess.run(["opencode", "--model", f"ollama/{active}"] + extra)

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
        print(f"\n  {BOLD}{RED}Unknown agent client:{RESET} '{target}'. Available: claude, opencode, dsh\n")
        sys.exit(1)

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

    elif cmd in ("remove", "rm", "delete"):
        if not rest:
            print(f"\n  {RED}Usage:{RESET} llm remove <model_name> [-y]\n")
            sys.exit(1)
        target = rest[0]
        force = "-y" in rest or "--yes" in rest
        if not force:
            confirm = input(f"  {YELLOW}Are you sure you want to remove model '{target}'? [y/N]: {RESET}").strip().lower()
            if confirm not in ("y", "yes"):
                print(f"  {DIM}Operation cancelled.{RESET}\n")
                return

        res = subprocess.run(["ollama", "rm", target], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  {BRIGHT_GREEN}✔ Removed {target}{RESET}\n")
        else:
            print(f"  {RED}Failed to remove {target}:{RESET} {res.stderr.strip()}\n")
            sys.exit(1)

    elif cmd in ("free", "purge", "unload"):
        evicted = free_vram()
        if evicted:
            print(f"\n  {BRIGHT_GREEN}✔ Evicted {len(evicted)} model(s): {', '.join(evicted)}. GPU VRAM is 100% free!{RESET}\n")
        else:
            print(f"\n  {BRIGHT_GREEN}✔ GPU VRAM is completely free (0 models loaded).{RESET}\n")

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

    elif cmd in ("dsh", "deepseek"):
        cmd_launch(["dsh"] + rest)

    elif cmd == "run":
        print(f"\n  {CYAN}Starting Ollama systemd background service...{RESET}")
        res = subprocess.run(["systemctl", "--user", "start", "ollama"], capture_output=True, text=True)
        time.sleep(0.5)
        if get_service_status():
            print(f"  {BRIGHT_GREEN}✔ Ollama service active{RESET}\n")
        else:
            print(f"  {YELLOW}Ollama service failed to start via systemd:{RESET} {res.stderr.strip()}\n")
            print(f"  {DIM}Try running manually: 'ollama serve'{RESET}\n")
            sys.exit(1)

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
