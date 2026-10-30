"""
Interactive REPL Shell matching the refined terminal design.
Provides prompt navigation, persistent history, tab-completion, and full runtime controls.
Strict quit policy: only exits on explicit exit/quit command or Ctrl+C / Ctrl+D.
"""

import sys
import os
import atexit
import shutil
import readline
import subprocess
import time
import json

from .terminal import (
    clear_screen, BOLD, DIM, RESET, CYAN, BRIGHT_CYAN,
    GREEN, BRIGHT_GREEN, YELLOW, BRIGHT_YELLOW, RED, BRIGHT_RED,
    WHITE, BRIGHT_WHITE
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
from .orchestrator import (
    get_active_model, save_active_model, switch_model,
    sync_all_configs, get_model_status, CONFIG_FILE
)
from .runtime import (
    start_server, stop_server, restart_server,
    unload_model, unload_all_models, remove_model,
    get_server_version
)
from .hub import HUB_MODELS, render_hub_table, pull_model_stream
from .doctor import run_doctor
from .paths import HISTORY_FILE, ensure_directories

def init_history():
    """Initializes persistent command history in ~/.local/state/llm-ctl/history."""
    ensure_directories()
    try:
        if os.path.exists(HISTORY_FILE):
            readline.read_history_file(HISTORY_FILE)
    except Exception:
        pass

    def save_history():
        try:
            readline.set_history_length(1000)
            readline.write_history_file(HISTORY_FILE)
        except Exception:
            pass

    atexit.register(save_history)

class Completer:
    """Contextual Tab-completion for the interactive REPL."""
    def __init__(self, commands: list[str]):
        self.commands = commands

    def complete(self, text: str, state: int):
        buffer = readline.get_line_buffer().lstrip()
        parts = buffer.split()

        # Command completion
        if len(parts) <= 1 and not buffer.endswith(" "):
            options = [c for c in self.commands if c.startswith(text)]
            return options[state] if state < len(options) else None

        # Model argument completion for switch, pull, remove, unload, chat
        if parts and parts[0] in ("switch", "use", "remove", "rm", "delete", "unload", "free", "chat"):
            installed = get_installed_models()
            model_names = [m.get("name", "") for m in installed if m.get("name")]
            options = [m for m in model_names if m.startswith(text)]
            return options[state] if state < len(options) else None

        # Pull suggestion from Hub catalog
        if parts and parts[0] == "pull":
            hub_names = [m["id"] for m in HUB_MODELS]
            options = [m for m in hub_names if m.startswith(text)]
            return options[state] if state < len(options) else None

        # Agent argument completion
        if parts and parts[0] in ("agents", "launch"):
            agent_names = ["claude", "opencode", "dsh"]
            options = [a for a in agent_names if a.startswith(text)]
            return options[state] if state < len(options) else None

        # Config argument completion
        if parts and parts[0] == "config":
            cfg_cmds = ["show", "path", "set"]
            options = [c for c in cfg_cmds if c.startswith(text)]
            return options[state] if state < len(options) else None

        return None

def display_reference_screen():
    """Renders the complete reference screen layout."""
    clear_screen()
    active = get_active_model()
    is_active = get_service_status()
    gpu = get_gpu_stats()
    ram = get_system_ram()
    loaded = get_loaded_models()
    installed = get_installed_models()
    version = get_server_version() if is_active else None

    # 1. Hero 3D Banner
    print()
    print(render_reference_banner())
    print()

    # 2. Compact Status Summary
    print(render_reference_status_card(is_active, OLLAMA_HOST, gpu, ram, active, loaded, installed, version_str=version))
    print()

    # 3. Quick Commands Matrix
    print(render_reference_quick_commands())
    print()

def run_interactive_repl():
    """
    Main interactive REPL shell.
    Prompts with 'llm ❯ ' and executes commands without quitting unless Ctrl+C / Ctrl+D / exit is used.
    """
    commands = [
        "models", "switch", "chat", "pull", "unload", "remove",
        "start", "stop", "restart", "run", "agents", "status",
        "doctor", "config", "help", "clear", "exit", "quit"
    ]

    init_history()

    # Setup readline auto-completion
    readline.set_completer(Completer(commands).complete)
    readline.set_completer_delims(" \t\n")
    readline.parse_and_bind("tab: complete")

    display_reference_screen()

    while True:
        try:
            prompt = f"  {BOLD}{BRIGHT_CYAN}llm-ctl{RESET} {BRIGHT_GREEN}❯{RESET} "
            user_input = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {DIM}Exiting llm-ctl. Service state preserved.{RESET}\n")
            sys.exit(0)

        if not user_input:
            continue

        parts = user_input.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit", "q"):
            print(f"\n  {DIM}Exiting llm-ctl. Service state preserved.{RESET}\n")
            sys.exit(0)

        elif cmd in ("clear", "cls"):
            display_reference_screen()

        elif cmd in ("status", "info"):
            display_reference_screen()

        elif cmd in ("models", "ls", "list"):
            installed = get_installed_models()
            loaded = get_loaded_models()
            active = get_active_model()
            loaded_names = [m.get("name", "") for m in loaded]

            print(f"\n  {BOLD}{WHITE}Installed Local Models ({len(installed)}):{RESET}")
            if not installed:
                print(f"  {DIM}No models installed. Type 'pull' to browse and download models.{RESET}\n")
            else:
                for idx, m in enumerate(installed, 1):
                    name = m.get("name", "")
                    size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
                    details = m.get("details", {})
                    param = details.get("parameter_size", "-")
                    quant = details.get("quantization_level", "-")

                    is_active = (name == active or name.startswith(active))
                    is_loaded = any(name == ln or name.startswith(ln) for ln in loaded_names)

                    if is_loaded:
                        badge = f" {BRIGHT_GREEN}★ [IN VRAM]{RESET}"
                    elif is_active:
                        badge = f" {CYAN}◈ [ACTIVE]{RESET}"
                    else:
                        badge = f" {DIM}[STORED]{RESET}"

                    print(f"  [{idx}] {BRIGHT_CYAN}{name:<24}{RESET} {DIM}({size_gb:.2f} GB · {param} · {quant}){RESET}{badge}")
                print()

        elif cmd in ("switch", "use"):
            if not args:
                installed = get_installed_models()
                if not installed:
                    print(f"\n  {YELLOW}No installed models to switch to. Run 'pull <model>' first.{RESET}\n")
                    continue
                print(f"\n  {BOLD}{WHITE}Available models to switch to:{RESET}")
                for idx, m in enumerate(installed, 1):
                    m_name = m.get("name", "")
                    status = get_model_status(m_name)
                    status_badge = f"{BRIGHT_GREEN}[IN VRAM]{RESET}" if status == "IN_VRAM" else f"{DIM}[STANDBY]{RESET}"
                    print(f"    [{idx}] {m_name:<24} {status_badge}")
                choice = input(f"\n  {CYAN}Enter model name or number: {RESET}").strip()
                target = choice
            else:
                target = args[0]

            if target:
                success = switch_model(target)
                if success:
                    display_reference_screen()

        elif cmd == "chat":
            if not get_service_status():
                print(f"\n  {RED}Error: Ollama service is offline.{RESET}")
                print(f"  {DIM}Type 'start' to start the local Ollama background service.{RESET}\n")
                continue

            active = args[0] if args else get_active_model()
            print(f"\n  {BOLD}{CYAN}Connecting to {active}... (Type '/bye' to return to prompt){RESET}\n")
            try:
                subprocess.run(["ollama", "run", active])
            except Exception as e:
                print(f"  {RED}Error launching chat session:{RESET} {e}\n")
            display_reference_screen()

        elif cmd in ("start", "run"):
            print(f"\n  {CYAN}Starting Ollama server...{RESET}")
            ok, msg = start_server()
            if ok:
                print(f"  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
            else:
                print(f"  {RED}✖ {msg}{RESET}\n")
            display_reference_screen()

        elif cmd == "stop":
            print(f"\n  {YELLOW}Stopping Ollama server...{RESET}")
            ok, msg = stop_server()
            if ok:
                print(f"  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
            else:
                print(f"  {RED}✖ {msg}{RESET}\n")
            display_reference_screen()

        elif cmd == "restart":
            print(f"\n  {CYAN}Restarting Ollama server...{RESET}")
            ok, msg = restart_server()
            if ok:
                print(f"  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
            else:
                print(f"  {RED}✖ {msg}{RESET}\n")
            display_reference_screen()

        elif cmd in ("unload", "free", "evict"):
            if args:
                target_m = args[0]
                ok, msg = unload_model(target_m)
                if ok:
                    print(f"\n  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
                else:
                    print(f"\n  {RED}✖ {msg}{RESET}\n")
            else:
                evicted = unload_all_models()
                if evicted:
                    print(f"\n  {BRIGHT_GREEN}✔ Unloaded {len(evicted)} model(s): {', '.join(evicted)}. VRAM is 100% free!{RESET}\n")
                else:
                    print(f"\n  {BRIGHT_GREEN}✔ VRAM is completely free (0 models loaded in memory).{RESET}\n")
            display_reference_screen()

        elif cmd in ("remove", "rm", "delete"):
            if not args:
                installed = get_installed_models()
                if not installed:
                    print(f"\n  {DIM}No installed models to remove.{RESET}\n")
                    continue
                print(f"\n  {BOLD}{WHITE}Installed models on disk:{RESET}")
                for idx, m in enumerate(installed, 1):
                    print(f"    [{idx}] {m.get('name', '')}")
                target_del = input(f"\n  {YELLOW}Enter model name or # to remove: {RESET}").strip()
                if target_del.isdigit() and 1 <= int(target_del) <= len(installed):
                    target_del = installed[int(target_del) - 1]["name"]
            else:
                target_del = args[0]

            if target_del:
                confirm = input(f"  {BOLD}{YELLOW}Are you sure you want to permanently delete model weights for '{target_del}'? [y/N]: {RESET}").strip().lower()
                if confirm in ("y", "yes"):
                    ok, msg = remove_model(target_del)
                    if ok:
                        print(f"  {BRIGHT_GREEN}✔ {msg}{RESET}\n")
                    else:
                        print(f"  {RED}✖ {msg}{RESET}\n")
                    display_reference_screen()
                else:
                    print(f"  {DIM}Deletion cancelled.{RESET}\n")

        elif cmd in ("agents", "launch"):
            active = get_active_model()
            if not args:
                print(f"\n  {BOLD}{WHITE}Launch Coding Agent (Active Model: {active}):{RESET}")
                claude_ok = shutil.which("claude") is not None
                opencode_ok = shutil.which("opencode") is not None
                dsh_ok = shutil.which("dsh") is not None

                c1 = f"{BRIGHT_GREEN}Ready{RESET}" if claude_ok else f"{YELLOW}Not Installed{RESET}"
                c2 = f"{BRIGHT_GREEN}Ready{RESET}" if opencode_ok else f"{YELLOW}Not Installed{RESET}"
                c3 = f"{BRIGHT_GREEN}Ready{RESET}" if dsh_ok else f"{YELLOW}Not Installed{RESET}"

                print(f"    [1] Claude Code       {DIM}(claude --model {active}){RESET} [{c1}]")
                print(f"    [2] OpenCode CLI      {DIM}(opencode --model ollama/{active}){RESET} [{c2}]")
                print(f"    [3] DeepSeek Harness  {DIM}(dsh web on :3080){RESET} [{c3}]")
                choice = input(f"\n  {CYAN}Select agent [1-3, or Enter to cancel]: {RESET}").strip()

                if choice == "1":
                    target_agent = "claude"
                elif choice == "2":
                    target_agent = "opencode"
                elif choice == "3":
                    target_agent = "dsh"
                else:
                    target_agent = None
            else:
                target_agent = args[0].lower()

            if target_agent in ("claude", "cc"):
                if not shutil.which("claude"):
                    print(f"\n  {RED}Claude Code is not installed in PATH.{RESET}")
                    print(f"  {DIM}Install via: npm install -g @anthropic-ai/claude-code{RESET}\n")
                else:
                    env = os.environ.copy()
                    env["ANTHROPIC_BASE_URL"] = OLLAMA_HOST
                    env["ANTHROPIC_API_KEY"] = "ollama"
                    env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = active
                    env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = active
                    subprocess.run(["claude", "--model", active], env=env)
                    display_reference_screen()

            elif target_agent in ("opencode", "oc"):
                if not shutil.which("opencode"):
                    print(f"\n  {RED}OpenCode CLI is not installed in PATH.{RESET}")
                    print(f"  {DIM}Install via: curl -fsSL https://opencode.ai/install.sh | bash{RESET}\n")
                else:
                    subprocess.run(["opencode", "--model", f"ollama/{active}"])
                    display_reference_screen()

            elif target_agent in ("dsh", "deepseek"):
                if not shutil.which("dsh"):
                    print(f"\n  {RED}DeepSeek Harness (dsh) is not installed in PATH.{RESET}")
                    print(f"  {DIM}Install via: npm install -g deepseek-harness{RESET}\n")
                else:
                    print(f"\n  {CYAN}Starting DeepSeek Harness Web UI...{RESET}")
                    subprocess.run(["dsh", "web"])
                    display_reference_screen()

        elif cmd == "doctor":
            run_doctor()

        elif cmd == "pull":
            if not args:
                installed = get_installed_models()
                installed_ids = {m.get("name", "") for m in installed}
                print()
                print(render_hub_table(installed_ids))
                choice = input(f"\n  {CYAN}Enter model name or # to download (or Enter to cancel): {RESET}").strip()
                if not choice:
                    continue
                if choice.isdigit() and 1 <= int(choice) <= len(HUB_MODELS):
                    target_pull = HUB_MODELS[int(choice) - 1]["id"]
                else:
                    target_pull = choice
            else:
                target_pull = args[0]

            if target_pull:
                pull_model_stream(target_pull)
                display_reference_screen()

        elif cmd == "config":
            if not args or args[0] in ("show", "view"):
                print(f"\n  {BOLD}{WHITE}Configuration:{RESET} {DIM}{CONFIG_FILE}{RESET}")
                if os.path.exists(CONFIG_FILE):
                    try:
                        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            print(f"  {json.dumps(data, indent=2)}")
                    except Exception as e:
                        print(f"  {RED}Error reading config:{RESET} {e}")
                else:
                    print(f"  {DIM}No config file found. Default model: {get_active_model()}{RESET}")
                print()
            elif args[0] == "path":
                print(f"  {CONFIG_FILE}\n")
            elif args[0] == "set" and len(args) >= 3:
                key = args[1]
                val = args[2]
                if key == "active_model":
                    save_active_model(val)
                    sync_all_configs(val)
                    print(f"  {BRIGHT_GREEN}✔ Set active_model to {val}{RESET}\n")
                else:
                    print(f"  {YELLOW}Unknown config key:{RESET} {key}\n")
            else:
                print(f"\n  {YELLOW}Usage:{RESET} config [show|path|set active_model <name>]\n")

        elif cmd in ("help", "?"):
            print()
            print(render_reference_quick_commands())
            print(f"\n  {DIM}Commands:{RESET}")
            print(f"    {WHITE}Server controls:{RESET}  start, stop, restart")
            print(f"    {WHITE}Model controls:{RESET}   models, switch <model>, unload [model], remove <model>, pull <model>, chat [model]")
            print(f"    {WHITE}System & config:{RESET}  status, doctor, agents, config, clear, help, exit")
            print(f"  {DIM}Navigation: [Tab] auto-completes, [Up]/[Down] browses history.{RESET}")
            print(f"  {DIM}Exit: 'exit', 'quit', Ctrl+C, or Ctrl+D.{RESET}\n")

        else:
            print(f"\n  {RED}Unknown command:{RESET} '{cmd}'. Type {BRIGHT_GREEN}help{RESET} for available commands.\n")
