"""
High-aesthetic visual branding, isometric 3D wireframe art, and status cards.
Optimized for SpaceMono-Regular (11pt) font and matches the exact reference design.
"""

import re
from .terminal import (
    BOLD, DIM, RESET, CYAN, BRIGHT_CYAN, GREEN, BRIGHT_GREEN,
    YELLOW, BRIGHT_YELLOW, RED, BRIGHT_RED, WHITE, BRIGHT_WHITE
)

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

def visible_len(s: str) -> int:
    """Computes the visible width of a string ignoring ANSI color codes."""
    return len(ANSI_RE.sub('', s))

def ansi_ljust(s: str, width: int) -> str:
    """Left-justifies a string based on visible length without breaking ANSI formatting."""
    vlen = visible_len(s)
    if vlen < width:
        return s + (" " * (width - vlen))
    return s

def render_reference_banner() -> str:
    """
    Renders the exact hero section matching the reference design:
    Left: 3D block LLM-CTL title + subtitle
    Right: Isometric wireframe processor cube with circuit routes
    """
    left_lines = [
        f"{BRIGHT_CYAN}  ██╗     ██╗     ███╗   ███╗     ██████╗████████╗██╗     {RESET}",
        f"{BRIGHT_CYAN}  ██║     ██║     ████╗ ████║    ██╔════╝╚══██╔══╝██║     {RESET}",
        f"{BRIGHT_CYAN}  ██║     ██║     ██╔████╔██║▄▄▄▄██║        ██║   ██║     {RESET}",
        f"{BRIGHT_CYAN}  ██║     ██║     ██║╚██╔╝██║    ██║        ██║   ██║     {RESET}",
        f"{BRIGHT_CYAN}  ███████╗███████╗██║ ╚═╝ ██║    ╚██████╗   ██║   ███████╗{RESET}",
        f"{BRIGHT_CYAN}  ╚══════╝╚══════╝╚═╝     ╚═╝     ╚═════╝   ╚═╝   ╚══════╝{RESET}",
        f"       {DIM}────────{RESET} {BOLD}{WHITE}LOCAL  MODEL  CONTROL{RESET} {DIM}────────{RESET}        ",
        f"   {DIM}Manage  ·  Switch  ·  Run  ·  Integrate  ·  Your Local Models{RESET}  "
    ]

    right_lines = [
        f"         {CYAN}┌─────────┐{RESET}        ",
        f"        {CYAN}/         /│{RESET}       {DIM}───{RESET} {WHITE}Ollama{RESET}",
        f"       {CYAN}/         / │{RESET}       {DIM}───{RESET} {WHITE}Local Models{RESET}",
        f"      {CYAN}┌─────────┐  │  ┌───{RESET} {DIM}───{RESET} {WHITE}Coding Agents{RESET}",
        f"      {CYAN}│         │  │  │{RESET}    {DIM}───{RESET} {WHITE}GPU / VRAM{RESET}",
        f"      {CYAN}│         │  ├──┘{RESET}    {DIM}───{RESET} {WHITE}Terminal First{RESET}",
        f"      {CYAN}│         │ /{RESET}         ",
        f"      {CYAN}└─────────┘{RESET}           "
    ]

    combined = []
    for l, r in zip(left_lines, right_lines):
        combined.append(f"{ansi_ljust(l, 60)} {r}")
    return "\n".join(combined)

def render_reference_status_card(is_active: bool, host: str, gpu_info: dict | None, ram_info: dict, active_model: str) -> str:
    """
    Renders the exact 4-column rounded horizontal status card:
    [ Connected | RAM gauge | GPU VRAM | Active Model READY ]
    """
    col1_w = 23
    col2_w = 23
    col3_w = 24
    col4_w = 26
    inner_width = col1_w + col2_w + col3_w + col4_w + 3  # for 3 dividers

    # RAM gauge bar
    ram_used = ram_info.get("used_gb", 0.0)
    ram_total = ram_info.get("total_gb", 7.1)
    ram_pct = (ram_used / ram_total) if ram_total > 0 else 0.0
    bar_width = 10
    filled = int(round(bar_width * ram_pct))
    empty = bar_width - filled
    ram_bar = f"{BRIGHT_GREEN}{'█' * filled}{DIM}{'░' * empty}{RESET}"

    # Status Strings
    srv_status = f"{BRIGHT_GREEN}● Ollama: Connected{RESET}" if is_active else f"{RED}○ Ollama: Offline{RESET}"
    host_display = host.replace("http://", "")

    if gpu_info:
        vram_pct = (gpu_info["used_mb"] / gpu_info["total_mb"] * 100) if gpu_info["total_mb"] > 0 else 0
        gpu_display = f"{vram_pct:1.0f}% │ {gpu_info['used_mb']:1.0f} / {gpu_info['total_mb']:1.0f} MiB"
    else:
        gpu_display = "No GPU detected"

    ready_badge = f"{BRIGHT_GREEN}[READY]{RESET}"

    # Borders
    top_border = f"  {CYAN}╭" + "─" * inner_width + f"╮{RESET}"
    bottom_border = f"  {CYAN}╰" + "─" * inner_width + f"╯{RESET}"

    # Row 1 (Category Headers)
    r1_c1 = ansi_ljust(f" {srv_status}", col1_w)
    r1_c2 = ansi_ljust(f" {CYAN}󰍛{RESET} {BOLD}{WHITE}RAM{RESET}", col2_w)
    r1_c3 = ansi_ljust(f" {CYAN}󰢮{RESET} {BOLD}{WHITE}GPU{RESET}", col3_w)
    r1_c4 = ansi_ljust(f" {CYAN}󰆍{RESET} {BOLD}{WHITE}Active Model{RESET}", col4_w)
    row1 = f"  {CYAN}│{RESET}{r1_c1}{CYAN}│{RESET}{r1_c2}{CYAN}│{RESET}{r1_c3}{CYAN}│{RESET}{r1_c4}{CYAN}│{RESET}"

    # Row 2 (Values)
    r2_c1 = ansi_ljust(f"   {DIM}{host_display}{RESET}", col1_w)
    r2_c2 = ansi_ljust(f"   {WHITE}{ram_used:.1f} / {ram_total:.1f} GiB{RESET}", col2_w)
    r2_c3 = ansi_ljust(f"   {WHITE}{gpu_display}{RESET}", col3_w)
    r2_c4 = ansi_ljust(f"   {BRIGHT_WHITE}{active_model}{RESET} {ready_badge}", col4_w)
    row2 = f"  {CYAN}│{RESET}{r2_c1}{CYAN}│{RESET}{r2_c2}{CYAN}│{RESET}{r2_c3}{CYAN}│{RESET}{r2_c4}{CYAN}│{RESET}"

    # Row 3 (RAM bar row)
    r3_c1 = ansi_ljust(" ", col1_w)
    r3_c2 = ansi_ljust(f"   [{ram_bar}]", col2_w)
    r3_c3 = ansi_ljust(" ", col3_w)
    r3_c4 = ansi_ljust(" ", col4_w)
    row3 = f"  {CYAN}│{RESET}{r3_c1}{CYAN}│{RESET}{r3_c2}{CYAN}│{RESET}{r3_c3}{CYAN}│{RESET}{r3_c4}{CYAN}│{RESET}"

    return f"{top_border}\n{row1}\n{row2}\n{row3}\n{bottom_border}"

def render_reference_quick_commands() -> str:
    """
    Renders the Quick Commands table matching the reference design.
    """
    lines = [
        f"  {BOLD}{BRIGHT_CYAN}Quick Commands:{RESET}",
        f"    {BRIGHT_GREEN}models{RESET}       {WHITE}List installed models{RESET}             {BRIGHT_GREEN}pull{RESET}         {WHITE}Download a model{RESET}",
        f"    {BRIGHT_GREEN}switch{RESET}       {WHITE}Switch active model{RESET}               {BRIGHT_GREEN}remove{RESET}       {WHITE}Remove a model{RESET}",
        f"    {BRIGHT_GREEN}chat{RESET}         {WHITE}Start interactive chat{RESET}            {BRIGHT_GREEN}run{RESET}          {WHITE}Start local server (if needed){RESET}",
        f"    {BRIGHT_GREEN}agents{RESET}       {WHITE}Manage coding agents{RESET}              {BRIGHT_GREEN}config{RESET}       {WHITE}Edit configuration{RESET}",
        f"    {BRIGHT_GREEN}status{RESET}       {WHITE}Show system & model status{RESET}        {BRIGHT_GREEN}help{RESET}         {WHITE}Show all commands{RESET}"
    ]
    return "\n".join(lines)
