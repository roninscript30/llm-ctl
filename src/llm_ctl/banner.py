"""
Minimalist, high-aesthetic header and telemetry gauge rendering for llm-ctl.
"""

from .terminal import (
    BOLD, DIM, RESET, CYAN, BRIGHT_CYAN, GREEN, BRIGHT_GREEN,
    YELLOW, BRIGHT_YELLOW, RED, BRIGHT_RED, WHITE, BRIGHT_WHITE, ITALIC
)

# Sleek minimalist ASCII brand logo
ASCII_LOGO = f"""
  {BRIGHT_CYAN}█░░ █░░ █▀▄▀█ {DIM}▄▄{RESET} {BRIGHT_CYAN}█▀▀ ▀█▀ █░░{RESET}
  {CYAN}█░░ █░░ █░▀░█ {DIM}░░{RESET} {CYAN}█▄▄ ░█░ █▄▄{RESET} {DIM}v0.3.0 · Local LLM Orchestrator{RESET}
"""

def render_gauge_bar(used: float, total: float, width: int = 20) -> str:
    """Renders a sleek colored progress bar with smooth block characters."""
    pct = (used / total * 100.0) if total > 0 else 0.0
    filled = int(round(width * (pct / 100.0)))
    empty = width - filled

    if pct >= 88:
        color = BRIGHT_RED
    elif pct >= 70:
        color = BRIGHT_YELLOW
    else:
        color = BRIGHT_GREEN

    bar = f"{color}{'━' * filled}{DIM}{'─' * empty}{RESET}"
    return f"[{bar}] {color}{pct:4.1f}%{RESET}"

def render_dashboard_header(active_model: str, gpu_info: dict | None, ram_info: dict, loaded_models: list) -> str:
    """Generates the sleek top telemetry header."""
    lines = []
    lines.append(ASCII_LOGO.strip("\n"))
    lines.append(f"  {DIM}────────────────────────────────────────────────────────────────────────{RESET}")

    # Service & Active Model Line
    service_badge = f"{BRIGHT_GREEN}● Active{RESET}"
    lines.append(f"  {BOLD}Service:{RESET} {service_badge} {DIM}(127.0.0.1:11434){RESET}  │  {BOLD}Active Model:{RESET} {BRIGHT_GREEN}{active_model}{RESET}")

    # GPU VRAM Line
    if gpu_info:
        gpu_used = gpu_info["used_mb"] / 1024.0
        gpu_total = gpu_info["total_mb"] / 1024.0
        gpu_bar = render_gauge_bar(gpu_info["used_mb"], gpu_info["total_mb"], width=18)
        lines.append(f"  {BOLD}GPU VRAM:{RESET} {gpu_bar} {DIM}({gpu_used:.2f}/{gpu_total:.1f} GB · {gpu_info['temp_c']}°C · {gpu_info['power_w']}W · {gpu_info['name']}){RESET}")
    else:
        lines.append(f"  {BOLD}GPU VRAM:{RESET} {DIM}No NVIDIA GPU detected{RESET}")

    # System RAM Line
    ram_bar = render_gauge_bar(ram_info["used_gb"], ram_info["total_gb"], width=18)
    lines.append(f"  {BOLD}Host RAM:{RESET} {ram_bar} {DIM}({ram_info['used_gb']:.1f}/{ram_info['total_gb']:.1f} GB · {ram_info['free_gb']:.1f} GB free){RESET}")

    # Loaded in VRAM Status
    if loaded_models:
        loaded_str = ", ".join([f"{BRIGHT_GREEN}▶ {m['name']}{RESET} {DIM}({m['size']}, {m['processor']}){RESET}" for m in loaded_models])
        lines.append(f"  {BOLD}In VRAM:{RESET}  {loaded_str}  {BRIGHT_GREEN}(100% Dedicated){RESET}")
    else:
        lines.append(f"  {BOLD}In VRAM:{RESET}  {DIM}None loaded (GPU memory is 100% idle & free for system){RESET}")

    lines.append(f"  {DIM}────────────────────────────────────────────────────────────────────────{RESET}\n")
    return "\n".join(lines)
