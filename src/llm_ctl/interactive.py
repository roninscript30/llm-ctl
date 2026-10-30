"""
Interactive single-keypress terminal dashboard and keyboard-navigable UI.
"""

import sys
import tty
import termios
import subprocess
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .banner import render_banner, render_telemetry_panel
from .hardware import get_gpu_stats, get_system_ram, get_loaded_models, get_installed_models
from .orchestrator import get_active_model, switch_model, free_vram
from .hub import HUB_MODELS, render_hub_table, pull_model_stream

console = Console()

def get_char() -> str:
    """Reads a single character from stdin without requiring Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # Escape sequence
            # Non-blocking read for arrow keys
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            return f"\x1b{ch2}{ch3}"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def render_actions_panel() -> Panel:
    """Renders the hotkey action bar."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="white")
    table.add_column(style="bold cyan")
    table.add_column(style="white")

    table.add_row(
        "[s] Switch Model", "[dim]Hot-swap VRAM weights[/dim]",
        "[h] Model Hub", "[dim]Discover & pull models[/dim]"
    )
    table.add_row(
        "[f] Free VRAM", "[dim]Purge GPU memory to 0 MB[/dim]",
        "[c] CLI Chat", "[dim]Direct terminal session[/dim]"
    )
    table.add_row(
        "[l] Launch Agent", "[dim]Claude Code / OpenCode / DSH[/dim]",
        "[r] Refresh", "[dim]Update live telemetry[/dim]"
    )

    return Panel(
        table,
        title="[bold bright_white]Keyboard Controls[/bold bright_white]",
        border_style="bright_blue",
        padding=(0, 1)
    )

def ui_switch_model():
    """Interactive model switch menu."""
    installed = get_installed_models()
    if not installed:
        console.print("[bold red]No local models found! Pull a model using the Model Hub [h].[/bold red]")
        console.input("\n[dim]Press Enter to continue...[/dim]")
        return

    active = get_active_model()
    console.clear()
    console.print(Panel("[bold bright_cyan]Select Model to Activate on RTX 3050 GPU[/bold bright_cyan]", border_style="cyan"))

    table = Table(border_style="cyan", header_style="bold white", expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Model Name", style="bold green", width=26)
    table.add_column("Size", width=12)
    table.add_column("Parameters", width=14)
    table.add_column("Quant", width=10)
    table.add_column("Active", width=12)

    for idx, m in enumerate(installed, 1):
        name = m.get("name", "")
        size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
        details = m.get("details", {})
        param = details.get("parameter_size", "unknown")
        quant = details.get("quantization_level", "unknown")
        is_active = "[bold bright_green]★ ACTIVE[/bold bright_green]" if name.startswith(active) else ""

        table.add_row(str(idx), name, f"{size_gb:.2f} GB", param, quant, is_active)

    console.print(table)
    console.print("\n[bold cyan]Press number key to activate, or [q] to cancel:[/bold cyan] ", end="")
    
    ch = get_char().strip().lower()
    if ch in ("q", "\x1b"):
        return
    try:
        idx = int(ch) - 1
        if 0 <= idx < len(installed):
            target = installed[idx]["name"]
            switch_model(target)
            console.input("[dim]Press Enter to return to Hub...[/dim]")
    except ValueError:
        pass

def ui_model_hub():
    """Interactive Ollama Model Hub browser."""
    console.clear()
    installed = get_installed_models()
    installed_ids = {m.get("name", "") for m in installed}
    gpu = get_gpu_stats()
    gpu_total = gpu["total_mb"] if gpu else 4096.0

    table = render_hub_table(installed_ids, gpu_total)
    console.print(table)
    console.print("\n[bold cyan]Select model # to pull, [c] for custom name, or [q] to return:[/bold cyan] ", end="")

    ch = get_char().strip().lower()
    if ch in ("q", "\x1b"):
        return
    elif ch == "c":
        console.print()
        custom = console.input("[bold cyan]Enter model identifier or GGUF (e.g. qwen2.5-coder:1.5b): [/bold cyan]").strip()
        if custom:
            pull_model_stream(custom)
            console.input("\n[dim]Press Enter to return...[/dim]")
    else:
        try:
            idx = int(ch) - 1
            if 0 <= idx < len(HUB_MODELS):
                target = HUB_MODELS[idx]["id"]
                pull_model_stream(target)
                console.input("\n[dim]Press Enter to return...[/dim]")
        except ValueError:
            pass

def ui_launch_agent():
    """Interactive agent launcher menu."""
    console.clear()
    active = get_active_model()
    console.print(Panel(f"[bold bright_cyan]Launch Coding Agent with Active Model: [bold green]{active}[/bold green][/bold bright_cyan]", border_style="cyan"))

    table = Table.grid(padding=(1, 2))
    table.add_column(style="bold bright_green")
    table.add_column(style="bold white")
    table.add_column(style="dim")

    table.add_row("[1]", "Claude Code (claude)", f"Runs native Claude Code wired to local {active}")
    table.add_row("[2]", "OpenCode CLI (opencode)", f"Runs OpenCode terminal agent on ollama/{active}")
    table.add_row("[3]", "DeepSeek Harness Web (dsh web)", "Launches browser UI at http://127.0.0.1:3080")
    table.add_row("[q]", "Cancel", "Return to main dashboard")

    console.print(table)
    console.print("\n[bold cyan]Press key [1-3, q]:[/bold cyan] ", end="")
    ch = get_char().strip().lower()

    if ch == "1":
        console.clear()
        subprocess.run(["claude", "--model", active])
    elif ch == "2":
        console.clear()
        subprocess.run(["opencode", "--model", f"ollama/{active}"])
    elif ch == "3":
        console.print("\n[cyan]Starting DeepSeek Harness Web UI...[/cyan]")
        subprocess.run(["dsh", "web"])
        console.input("[dim]Press Enter to return...[/dim]")

def run_interactive_dashboard():
    """Main loop for the interactive terminal dashboard."""
    while True:
        console.clear()
        active = get_active_model()
        gpu = get_gpu_stats()
        ram = get_system_ram()
        loaded = get_loaded_models()

        # Render Banner & Hardware Cards
        console.print(render_banner(active_model=active))
        console.print(render_telemetry_panel(gpu, ram, loaded))
        console.print(render_actions_panel())
        console.print("\n[dim]Press [q] or [Ctrl+C] to exit[/dim] | [bold cyan]Input:[/bold cyan] ", end="")

        try:
            ch = get_char().strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Exited llm-ctl. Service remains active.[/dim]")
            sys.exit(0)

        if ch in ("q", "\x03", "\x1b"):
            console.print("\n[dim]Exited llm-ctl. Service remains active.[/dim]")
            sys.exit(0)
        elif ch in ("s", "1"):
            ui_switch_model()
        elif ch in ("h", "2"):
            ui_model_hub()
        elif ch in ("f", "3"):
            evicted = free_vram()
            console.print(f"\n[bold green]✔ Evicted {len(evicted)} models. 100% GPU VRAM is free![/bold green]")
            import time
            time.sleep(1)
        elif ch in ("c", "4"):
            console.clear()
            console.print(f"[bold cyan]Connecting to {active}... (Type '/bye' to exit)[/bold cyan]\n")
            subprocess.run(["ollama", "run", active])
        elif ch in ("l", "5"):
            ui_launch_agent()
        elif ch == "r":
            continue
