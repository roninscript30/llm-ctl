"""
Interactive REPL Shell matching the reference visual design.
Provides prompt navigation, tab-completion, and command execution.
"""

import sys
import os
import readline
import subprocess
import time
from .terminal import (
    clear_screen, BOLD, DIM, RESET, CYAN, BRIGHT_CYAN,
    GREEN, BRIGHT_GREEN, YELLOW, RED, WHITE, BRIGHT_WHITE
)
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
from .hub import HUB_MODELS, pull_model_stream

class Completer:
    """Tab-completion for the interactive llm> REPL."""
    def __init__(self, commands: list[str]):
        self.commands = commands

    def complete(self, text: str, state: int):
        buffer = readline.get_line_buffer().lstrip()
        parts = buffer.split()

        # Command completion
        if len(parts) <= 1 and not buffer.endswith(" "):
            options = [c for c in self.commands if c.startswith(text)]
            return options[state] if state < len(options) else None

        # Model argument completion for switch, pull, remove, chat
        if parts and parts[0] in ("switch", "use", "remove", "rm", "chat", "models"):
            installed = get_installed_models()
            model_names = [m.get("name", "") for m in installed]
            options = [m for m in model_names if m.startswith(text)]
            return options[state] if state < len(options) else None

        # Agent argument completion
        if parts and parts[0] == "agents":
            agent_names = ["claude", "opencode", "dsh"]
            options = [a for a in agent_names if a.startswith(text)]
            return options[state] if state < len(options) else None

        return None

def display_reference_screen():
    """Renders the complete reference screen layout."""
    clear_screen()
    active = get_active_model()
    is_active = get_service_status()
    gpu = get_gpu_stats()
    ram = get_system_ram()

    # 1. Hero 3D Banner
    print()
    print(render_reference_banner())
    print()

    # 2. Horizontal Status Card
    print(render_reference_status_card(is_active, OLLAMA_HOST, gpu, ram, active))
    print()

    # 3. Quick Commands Matrix
    print(render_reference_quick_commands())
    print()

def run_interactive_repl():
    """
    Main interactive REPL shell.
    Prompts with 'llm> ' and executes commands without quitting unless Ctrl+C / Ctrl+D / exit is used.
    """
    commands = [
        "models", "switch", "chat", "agents", "status",
        "pull", "remove", "run", "config", "help",
        "free", "purge", "bench", "clear", "exit", "quit"
    ]

    # Setup readline auto-completion
    readline.set_completer(Completer(commands).complete)
    readline.set_completer_delims(" \t\n")
    readline.parse_and_bind("tab: complete")

    display_reference_screen()

    while True:
        try:
            prompt = f"  {BRIGHT_GREEN}llm>{RESET} "
            user_input = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {DIM}Exiting llm-ctl. Service remains active on :11434.{RESET}\n")
            sys.exit(0)

        if not user_input:
            continue

        parts = user_input.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit", "q"):
            print(f"\n  {DIM}Exiting llm-ctl. Service remains active on :11434.{RESET}\n")
            sys.exit(0)

        elif cmd in ("clear", "cls"):
            display_reference_screen()

        elif cmd in ("models", "ls", "list"):
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
                print(f"  • {BRIGHT_CYAN}{name:<26}{RESET} {DIM}({size_gb:.2f} GB · {param} · {quant}){RESET}{mark}")
            print()

        elif cmd in ("switch", "use"):
            if not args:
                installed = get_installed_models()
                print(f"\n  {BOLD}{WHITE}Available models to switch to:{RESET}")
                for idx, m in enumerate(installed, 1):
                    print(f"    [{idx}] {m.get('name', '')}")
                choice = input(f"\n  {CYAN}Enter model name or number: {RESET}").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(installed):
                    target = installed[int(choice) - 1]["name"]
                else:
                    target = choice
            else:
                target = args[0]

            if target:
                switch_model(target)
                display_reference_screen()

        elif cmd == "chat":
            active = args[0] if args else get_active_model()
            print(f"\n  {BOLD}{CYAN}Connecting to {active}... (Type '/bye' to return to llm> prompt){RESET}\n")
            subprocess.run(["ollama", "run", active])
            display_reference_screen()

        elif cmd in ("agents", "launch"):
            active = get_active_model()
            if not args:
                print(f"\n  {BOLD}{WHITE}Launch Coding Agent (Active Model: {active}):{RESET}")
                print(f"    [1] Claude Code       {DIM}(claude --model {active}){RESET}")
                print(f"    [2] OpenCode CLI      {DIM}(opencode --model ollama/{active}){RESET}")
                print(f"    [3] DeepSeek Harness  {DIM}(dsh web on http://127.0.0.1:3080){RESET}")
                choice = input(f"\n  {CYAN}Select agent [1-3, or Enter to cancel]: {RESET}").strip()
                if choice == "1":
                    subprocess.run(["claude", "--model", active])
                elif choice == "2":
                    subprocess.run(["opencode", "--model", f"ollama/{active}"])
                elif choice == "3":
                    print(f"\n  {CYAN}Starting DeepSeek Harness Web UI...{RESET}")
                    subprocess.run(["dsh", "web"])
                display_reference_screen()
            else:
                target = args[0].lower()
                if target in ("claude", "cc"):
                    subprocess.run(["claude", "--model", active])
                elif target in ("opencode", "oc"):
                    subprocess.run(["opencode", "--model", f"ollama/{active}"])
                elif target in ("dsh", "deepseek"):
                    subprocess.run(["dsh", "web"])
                display_reference_screen()

        elif cmd == "status":
            display_reference_screen()

        elif cmd == "pull":
            if not args:
                print(f"\n  {YELLOW}Usage: pull <model_name>{RESET} (e.g. pull qwen2.5-coder:1.5b)\n")
            else:
                pull_model_stream(args[0])
                display_reference_screen()

        elif cmd in ("remove", "rm", "delete"):
            if not args:
                print(f"\n  {YELLOW}Usage: remove <model_name>{RESET}\n")
            else:
                subprocess.run(["ollama", "rm", args[0]])
                print(f"  {BRIGHT_GREEN}✔ Removed {args[0]}{RESET}\n")

        elif cmd == "run":
            print(f"\n  {CYAN}Starting Ollama systemd background service...{RESET}")
            subprocess.run(["systemctl", "--user", "start", "ollama"])
            time.sleep(0.5)
            display_reference_screen()

        elif cmd in ("free", "purge", "unload"):
            evicted = free_vram()
            print(f"\n  {BRIGHT_GREEN}✔ Evicted {len(evicted)} model(s). GPU VRAM is 100% free!{RESET}\n")
            display_reference_screen()

        elif cmd == "config":
            cfg_path = os.path.expanduser("~/.config/llm-ctl/config.json")
            print(f"\n  {BOLD}{WHITE}Configuration:{RESET} {DIM}{cfg_path}{RESET}")
            if os.path.exists(cfg_path):
                with open(cfg_path) as f:
                    print(f"  {f.read().strip()}")
            print()

        elif cmd in ("help", "?"):
            print()
            print(render_reference_quick_commands())
            print()

        else:
            print(f"\n  {RED}Unknown command:{RESET} '{cmd}'. Type {BRIGHT_GREEN}help{RESET} for available commands.\n")
