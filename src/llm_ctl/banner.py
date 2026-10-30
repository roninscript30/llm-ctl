"""
Terminal banner, ASCII branding, and visual status cards for llm-ctl.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# Modern, clean ASCII art banner
ASCII_LOGO = r"""
 █░░ █░░ █▀▄▀█ ▄▄ █▀▀ ▀█▀ █░░
 █░░ █░░ █░▀░█ ░░ █▄▄ ░█░ █▄▄
"""

TAGLINE = "Native Local LLM Control Hub & VRAM Orchestrator"

def render_banner(active_model: str = "None", endpoint: str = "http://127.0.0.1:11434") -> Panel:
    """Renders the aesthetic header panel with logo and metadata."""
    logo_text = Text(ASCII_LOGO, style="bold cyan")
    
    meta_table = Table.grid(padding=(0, 2))
    meta_table.add_column(style="bold white")
    meta_table.add_column(style="cyan")
    
    meta_table.add_row("⚡ Service:", f"[green]● Active[/green] ({endpoint})")
    meta_table.add_row("★ Active Model:", f"[bold bright_green]{active_model}[/bold bright_green]")

    content = Table.grid(padding=(0, 1))
    content.add_row(logo_text)
    content.add_row(Text(f" {TAGLINE}", style="dim italic white"))
    content.add_row(Text(""))
    content.add_row(meta_table)

    return Panel(
        content,
        border_style="bright_blue",
        padding=(0, 1),
    )

def render_gauge(used: float, total: float, unit: str = "MiB", width: int = 18) -> Text:
    """Renders a colored progress gauge bar."""
    pct = (used / total * 100.0) if total > 0 else 0.0
    filled = int(round(width * (pct / 100.0)))
    empty = width - filled
    
    if pct >= 90:
        color = "bright_red"
    elif pct >= 75:
        color = "bright_yellow"
    else:
        color = "bright_green"

    bar = f"[{'█' * filled}{'░' * empty}]"
    return Text.from_markup(f"[{color}]{bar}[/{color}] {used:4.0f}/{total:4.0f} {unit} ({pct:4.1f}%)")

def render_telemetry_panel(gpu_info: dict, ram_info: dict, loaded_models: list) -> Panel:
    """Renders the hardware telemetry card."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Metric", style="bold white", width=12)
    table.add_column("Gauge", width=36)
    table.add_column("Stats", style="dim")

    # GPU Row
    if gpu_info:
        gpu_gauge = render_gauge(gpu_info["used_mb"], gpu_info["total_mb"], "MiB")
        gpu_stats = f"{gpu_info['temp_c']}°C | {gpu_info['power_w']}W ({gpu_info['name']})"
        table.add_row("GPU VRAM:", gpu_gauge, gpu_stats)
    else:
        table.add_row("GPU VRAM:", "[dim]No NVIDIA GPU detected[/dim]", "")

    # RAM Row
    if ram_info:
        ram_gauge = render_gauge(ram_info["used_gb"] * 1024, ram_info["total_gb"] * 1024, "MiB")
        ram_stats = f"{ram_info['free_gb']:.1f} GB Free (System Total: {ram_info['total_gb']:.1f} GB)"
        table.add_row("System RAM:", ram_gauge, ram_stats)

    # In VRAM Status
    if loaded_models:
        loaded_str = ", ".join([f"[bold green]▶ {m['name']}[/bold green] ([dim]{m['size']}, {m['processor']}[/dim])" for m in loaded_models])
        table.add_row("In VRAM:", Text.from_markup(loaded_str), "[bold green]100% Dedicated[/bold green]")
    else:
        table.add_row("In VRAM:", "[dim green]GPU memory idle & 100% free for host system[/dim green]", "")

    return Panel(
        table,
        title="[bold bright_white]Hardware Telemetry[/bold bright_white]",
        border_style="cyan",
        padding=(0, 1)
    )
