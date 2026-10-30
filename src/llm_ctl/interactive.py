"""
Modern, keyboard-navigable interactive terminal UI with arrow-key controls and strict exit lifecycle.
Strict Rule: Only Ctrl+C or Ctrl+D terminates the CLI. All other keys navigate or stay within the app.
"""

import sys
import time
import subprocess
from .terminal import (
    read_key, clear_screen, hide_cursor, show_cursor,
    BOLD, DIM, RESET, CYAN, BRIGHT_CYAN, GREEN, BRIGHT_GREEN,
    YELLOW, BRIGHT_YELLOW, RED, BRIGHT_RED, WHITE, BRIGHT_WHITE
)
from .banner import render_dashboard_header
from .hardware import get_gpu_stats, get_system_ram, get_loaded_models, get_installed_models
from .orchestrator import get_active_model, switch_model, free_vram
from .hub import HUB_MODELS, pull_model_stream, get_vram_badge

def select_from_menu(title: str, options: list[dict], default_index: int = 0) -> int | None:
    """
    Arrow-key navigable menu.
    - Up/Down or k/j: Navigate options.
    - Enter or Space: Confirm selection.
    - Esc, q, Left, Backspace: Return to main menu (does NOT quit app).
    - Ctrl+C, Ctrl+D: Clean exit from whole program.
    """
    selected = default_index
    hide_cursor()
    try:
        while True:
            sys.stdout.write("\033[H")  # Move to top-left
            sys.stdout.write(f"\n  {BOLD}{BRIGHT_WHITE}{title}{RESET}\n")
            sys.stdout.write(f"  {DIM}Navigate: ↑/↓ or j/k · Select: Enter/Space · Back: Esc/q · Quit: Ctrl+C{RESET}\n\n")

            for idx, opt in enumerate(options):
                is_selected = (idx == selected)
                label = opt.get("label", "")
                desc = opt.get("desc", "")
                badge = opt.get("badge", "")

                if is_selected:
                    pointer = f"{BRIGHT_CYAN}{BOLD}❯{RESET}"
                    label_str = f"{BRIGHT_CYAN}{BOLD}{label}{RESET}"
                    desc_str = f"{WHITE}{desc}{RESET}"
                    line = f"  {pointer} {label_str:<32} {desc_str} {badge}\033[K"
                else:
                    pointer = " "
                    label_str = f"{WHITE}{label}{RESET}"
                    desc_str = f"{DIM}{desc}{RESET}"
                    line = f"  {pointer} {label_str:<32} {desc_str} {badge}\033[K"

                sys.stdout.write(f"{line}\n")

            sys.stdout.write("\033[J")
            sys.stdout.flush()

            key = read_key()
            if key in ('CTRL_C', 'CTRL_D'):
                clear_screen()
                print(f"  {DIM}llm-ctl exited via interrupt. Background services remain active.{RESET}\n")
                sys.exit(0)
            elif key in ('UP', 'k'):
                selected = (selected - 1) % len(options)
            elif key in ('DOWN', 'j'):
                selected = (selected + 1) % len(options)
            elif key in ('ENTER', 'SPACE'):
                return selected
            elif key in ('ESC', 'q', 'LEFT', 'BACKSPACE'):
                return None  # Return to main dashboard
            elif key in [str(i) for i in range(1, len(options) + 1)]:
                return int(key) - 1
    finally:
        show_cursor()

def ui_switch_model():
    """Interactive model switcher with arrow-key navigation."""
    installed = get_installed_models()
    if not installed:
        clear_screen()
        print(f"\n  {RED}No local models found! Pull one from the Model Hub first.{RESET}")
        time.sleep(1.5)
        return

    active = get_active_model()
    options = []
    default_idx = 0

    for idx, m in enumerate(installed):
        name = m.get("name", "")
        size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
        details = m.get("details", {})
        param = details.get("parameter_size", "")
        quant = details.get("quantization_level", "")
        is_active = name.startswith(active)
        if is_active:
            default_idx = idx

        badge = f"{BRIGHT_GREEN}[ACTIVE]{RESET}" if is_active else ""
        options.append({
            "label": f"★ {name}" if is_active else f"• {name}",
            "desc": f"({size_gb:.2f} GB · {param} · {quant})",
            "badge": badge,
            "target": name
        })

    clear_screen()
    choice = select_from_menu("Select Active Model for RTX 3050 GPU:", options, default_index=default_idx)
    if choice is not None:
        target = options[choice]["target"]
        clear_screen()
        switch_model(target)
        time.sleep(1.2)

def ui_model_hub():
    """Interactive Ollama Model Hub with arrow-key navigation."""
    installed = get_installed_models()
    installed_ids = {m.get("name", "") for m in installed}
    gpu = get_gpu_stats()
    gpu_total = gpu["total_mb"] if gpu else 4096.0

    options = []
    for m in HUB_MODELS:
        is_installed = any(m["id"] in ins or ins.startswith(m["id"]) for ins in installed_ids)
        badge = f"{BRIGHT_GREEN}✔ Installed{RESET}" if is_installed else f"{DIM}Available{RESET}"
        fit_badge = get_vram_badge(m["est_vram_mb"], gpu_total)

        options.append({
            "label": m["id"],
            "desc": f"{m['size_gb']:.1f} GB  {fit_badge}  {DIM}{m['description'][:38]}{RESET}",
            "badge": badge,
            "id": m["id"]
        })

    options.append({
        "label": "[Custom Model]",
        "desc": "Enter custom model tag or HuggingFace GGUF",
        "badge": "",
        "id": "CUSTOM"
    })

    clear_screen()
    choice = select_from_menu("Ollama Model Hub — Browse & Pull Models:", options)
    if choice is not None:
        target_id = options[choice]["id"]
        clear_screen()
        if target_id == "CUSTOM":
            show_cursor()
            custom = input(f"\n  {BOLD}{CYAN}Enter model name to pull (e.g. qwen2.5-coder:1.5b): {RESET}").strip()
            if custom:
                pull_model_stream(custom)
                input(f"\n  {DIM}Press Enter to return to Hub...{RESET}")
        else:
            pull_model_stream(target_id)
            input(f"\n  {DIM}Press Enter to return to Hub...{RESET}")

def ui_launch_agent():
    """Interactive agent client launcher with arrow-key selection."""
    active = get_active_model()
    options = [
        {
            "label": "󰌌  Claude Code",
            "desc": f"Wired to local {active} via Anthropic Messages endpoint",
            "badge": "",
            "action": "claude"
        },
        {
            "label": "󰊠  OpenCode CLI",
            "desc": f"Wired to ollama/{active}",
            "badge": "",
            "action": "opencode"
        },
        {
            "label": "󰒋  DeepSeek Harness (Web)",
            "desc": "Launch browser interface at http://127.0.0.1:3080",
            "badge": "",
            "action": "dsh_web"
        },
        {
            "label": "󰒋  DeepSeek Harness (CLI)",
            "desc": "Run headless prompt from terminal",
            "badge": "",
            "action": "dsh_cli"
        }
    ]

    clear_screen()
    choice = select_from_menu(f"Launch Coding Agent (Active Model: {active}):", options)
    if choice is not None:
        act = options[choice]["action"]
        clear_screen()
        if act == "claude":
            subprocess.run(["claude", "--model", active])
        elif act == "opencode":
            subprocess.run(["opencode", "--model", f"ollama/{active}"])
        elif act == "dsh_web":
            print(f"\n  {CYAN}Starting DeepSeek Harness Web UI...{RESET}")
            subprocess.run(["dsh", "web"])
            input(f"\n  {DIM}Press Enter to return...{RESET}")
        elif act == "dsh_cli":
            show_cursor()
            prompt = input(f"\n  {BOLD}{CYAN}Enter prompt for DSH: {RESET}").strip()
            if prompt:
                subprocess.run(["dsh", "headless", prompt])
                input(f"\n  {DIM}Press Enter to return...{RESET}")

def ui_service_control():
    """Interactive service control menu."""
    options = [
        {"label": "▶  Start Service", "desc": "systemctl --user start ollama", "action": "start"},
        {"label": "■  Stop Service", "desc": "systemctl --user stop ollama", "action": "stop"},
        {"label": "↺  Restart Service", "desc": "systemctl --user restart ollama", "action": "restart"},
        {"label": "📋 View Service Logs", "desc": "journalctl recent 35 lines", "action": "logs"},
    ]

    clear_screen()
    choice = select_from_menu("Ollama Background Service Management:", options)
    if choice is not None:
        action = options[choice]["action"]
        clear_screen()
        if action in ("start", "stop", "restart"):
            print(f"\n  {CYAN}Executing: systemctl --user {action} ollama...{RESET}")
            subprocess.run(["systemctl", "--user", action, "ollama"])
            time.sleep(0.8)
        elif action == "logs":
            subprocess.run(["journalctl", "--user", "-u", "ollama", "-n", "35", "--no-pager"])
            input(f"\n  {DIM}Press Enter to return to Hub...{RESET}")

def run_interactive_dashboard():
    """
    Main interactive dashboard loop.
    STRICT RULE: Only Ctrl+C or Ctrl+D exits this program.
    Any other key navigates or maintains the dashboard loop.
    """
    selected_idx = 0
    main_options = [
        {"label": "󰒋  Switch Model", "desc": "Hot-swap active weights on RTX 3050 GPU", "key": "switch"},
        {"label": "󰊠  Model Hub", "desc": "Browse curated Ollama models with VRAM badges", "key": "hub"},
        {"label": "󰌌  Launch Agent", "desc": "Claude Code, OpenCode, DeepSeek Harness", "key": "launch"},
        {"label": "󰓅  Purge VRAM", "desc": "Instantly free 100% GPU memory (0 MB allocated)", "key": "free"},
        {"label": "󰭹  Direct Chat", "desc": "Direct interactive terminal session with active model", "key": "chat"},
        {"label": "󰐥  Service Control", "desc": "Manage Ollama systemd background service", "key": "service"},
    ]

    clear_screen()
    hide_cursor()
    status_msg = ""

    try:
        while True:
            active = get_active_model()
            gpu = get_gpu_stats()
            ram = get_system_ram()
            loaded = get_loaded_models()

            # Render top header
            sys.stdout.write("\033[H")
            header = render_dashboard_header(active, gpu, ram, loaded)
            sys.stdout.write(header)

            if status_msg:
                sys.stdout.write(f"  {status_msg}\033[K\n\n")
                status_msg = ""
            else:
                sys.stdout.write(f"  {DIM}Navigate: ↑/↓ or j/k · Select: Enter/Space · Quick keys: 1-6 · {BOLD}Exit: Ctrl+C / Ctrl+D only{RESET}\033[K\n\n")

            # Render menu options
            for idx, opt in enumerate(main_options):
                is_selected = (idx == selected_idx)
                label = opt["label"]
                desc = opt["desc"]

                if is_selected:
                    pointer = f"{BRIGHT_CYAN}{BOLD}❯{RESET}"
                    label_str = f"{BRIGHT_CYAN}{BOLD}{label}{RESET}"
                    desc_str = f"{WHITE}{desc}{RESET}"
                    line = f"  {pointer} {label_str:<30} {desc_str}\033[K"
                else:
                    pointer = " "
                    label_str = f"{WHITE}{label}{RESET}"
                    desc_str = f"{DIM}{desc}{RESET}"
                    line = f"  {pointer} {label_str:<30} {desc_str}\033[K"

                sys.stdout.write(f"{line}\n")

            sys.stdout.write("\033[J")
            sys.stdout.flush()

            # Read key safely
            try:
                key = read_key()
            except (KeyboardInterrupt, EOFError):
                clear_screen()
                print(f"  {DIM}llm-ctl exited via interrupt. Background services remain active.{RESET}\n")
                sys.exit(0)

            # STRICT EXIT: Only Ctrl+C or Ctrl+D exits the program!
            if key in ('CTRL_C', 'CTRL_D'):
                clear_screen()
                print(f"  {DIM}llm-ctl exited via interrupt. Background services remain active.{RESET}\n")
                sys.exit(0)

            # Navigation
            elif key in ('UP', 'k'):
                selected_idx = (selected_idx - 1) % len(main_options)
            elif key in ('DOWN', 'j'):
                selected_idx = (selected_idx + 1) % len(main_options)

            # Trigger Action on ENTER or SPACE
            elif key in ('ENTER', 'SPACE'):
                action_key = main_options[selected_idx]["key"]
                if action_key == "switch":
                    ui_switch_model()
                    clear_screen()
                elif action_key == "hub":
                    ui_model_hub()
                    clear_screen()
                elif action_key == "launch":
                    ui_launch_agent()
                    clear_screen()
                elif action_key == "free":
                    evicted = free_vram()
                    status_msg = f"{BRIGHT_GREEN}✔ Evicted {len(evicted)} model(s). GPU VRAM is 100% free!{RESET}"
                elif action_key == "chat":
                    clear_screen()
                    show_cursor()
                    print(f"\n  {BOLD}{CYAN}Connecting to {active}... (Type '/bye' to exit chat and return to Hub){RESET}\n")
                    subprocess.run(["ollama", "run", active])
                    clear_screen()
                    hide_cursor()
                elif action_key == "service":
                    ui_service_control()
                    clear_screen()

            # Direct Number Shortcuts
            elif key in ('s', '1'):
                ui_switch_model()
                clear_screen()
            elif key in ('h', '2'):
                ui_model_hub()
                clear_screen()
            elif key in ('l', '3'):
                ui_launch_agent()
                clear_screen()
            elif key in ('f', '4'):
                evicted = free_vram()
                status_msg = f"{BRIGHT_GREEN}✔ Evicted {len(evicted)} model(s). GPU VRAM is 100% free!{RESET}"
            elif key in ('c', '5'):
                clear_screen()
                show_cursor()
                print(f"\n  {BOLD}{CYAN}Connecting to {active}... (Type '/bye' to exit chat and return to Hub){RESET}\n")
                subprocess.run(["ollama", "run", active])
                clear_screen()
                hide_cursor()
            elif key in ('6',):
                ui_service_control()
                clear_screen()

            # If user presses Esc or q in main menu: DO NOT QUIT! Show reminder.
            elif key in ('ESC', 'q'):
                status_msg = f"{YELLOW}ℹ To exit llm-ctl, press Ctrl+C or Ctrl+D.{RESET}"

            # Any other unknown key: DO NOT QUIT! Just ignore.
            else:
                continue
    finally:
        show_cursor()
