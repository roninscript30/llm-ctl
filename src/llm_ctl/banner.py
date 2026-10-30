"""
Terminal visual identity, 3D ASCII branding, and natural status summary.
Tailored for monospace displays (SpaceMono-Regular 11pt) and 80-column safe layout.
"""

import re
import shutil
from .terminal import (
    BOLD, DIM, RESET, CYAN, BRIGHT_CYAN, GREEN, BRIGHT_GREEN,
    YELLOW, BRIGHT_YELLOW, RED, BRIGHT_RED, WHITE, BRIGHT_WHITE
)

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

def visible_len(s: str) -> int:
    """Computes the visible width of a string ignoring ANSI color and escape sequences."""
    return len(ANSI_RE.sub('', s))

def ansi_ljust(s: str, width: int) -> str:
    """
    Left-justifies a string based on visible length without breaking ANSI formatting.
    Strictly clamps strings exceeding width to guarantee vertical terminal alignment.
    """
    vlen = visible_len(s)
    if vlen < width:
        return s + (" " * (width - vlen))
    elif vlen > width:
        out = []
        cur_vlen = 0
        pos = 0
        while pos < len(s) and cur_vlen < width:
            m = ANSI_RE.match(s, pos)
            if m:
                out.append(m.group(0))
                pos = m.end()
            else:
                out.append(s[pos])
                cur_vlen += 1
                pos += 1
        out.append(RESET)
        return "".join(out)
    return s

def truncate_str(s: str, max_w: int) -> str:
    """Safely truncates string with ellipsis if exceeding max visible width."""
    if len(s) <= max_w:
        return s
    if max_w <= 3:
        return s[:max_w]
    return s[:max_w - 3] + "..."

def _colorize_logo(text: str) -> str:
    """
    Applies layered 3D depth to ASCII block letters:
    - Face blocks (█, ▄, ▀, ▌, ▐): BRIGHT_CYAN
    - Bevels / edges / shadows (╗, ║, ╚, ═, ╝, ╔, etc.): CYAN (slate dark cyan)
    """
    res = []
    in_face = None
    for ch in text:
        if ch in ("█", "▄", "▀", "▌", "▐"):
            if in_face is not True:
                res.append(BRIGHT_CYAN)
                in_face = True
        elif ch in ("╗", "║", "╚", "═", "╝", "╔", "─", "│", "┌", "┐", "└", "┘"):
            if in_face is not False:
                res.append(CYAN)
                in_face = False
        else:
            if in_face is not None:
                res.append(RESET)
                in_face = None
        res.append(ch)
    if in_face is not None:
        res.append(RESET)
    return "".join(res)

def render_reference_banner() -> str:
    """
    Renders refined 3D ASCII identity logo:
    - Prominent bold block letters 'LLM' and 'CTL' separated by a centered 3D block dash.
    - Subtle 3D depth with bright cyan face and muted slate cyan shadows/bevels.
    - Centered framed subtitle 'LOCAL MODEL CONTROL'.
    - Centered muted tagline 'Manage · Switch · Run · Integrate · Your Local Models'.
    - Monospace alignment calibrated for SpaceMono-Regular (11pt).
    """
    llm_blocks = [
        "██╗     ██╗     ███╗   ███╗",
        "██║     ██║     ████╗ ████║",
        "██║     ██║     ██╔████╔██║",
        "██║     ██║     ██║╚██╔╝██║",
        "███████╗███████╗██║ ╚═╝ ██║",
        "╚══════╝╚══════╝╚═╝     ╚═╝",
    ]

    dash_blocks = [
        "             ",
        "             ",
        "  ████████╗  ",
        "  ╚═══════╝  ",
        "             ",
        "             ",
    ]

    ctl_blocks = [
        " ██████╗ ████████╗ ██╗     ",
        "██╔════╝ ╚══██╔══╝ ██║     ",
        "██║         ██║    ██║     ",
        "██║         ██║    ██║     ",
        "╚██████╗    ██║    ███████╗",
        " ╚═════╝    ╚═╝    ╚══════╝",
    ]

    lines = []
    for l, d, c in zip(llm_blocks, dash_blocks, ctl_blocks):
        raw = f"      {l}{d}{c}"
        lines.append(_colorize_logo(raw))

    # Centered subtitle and tagline aligned to column 39.5
    sub = f"          {DIM}───────────────────{RESET} {BOLD}{WHITE}LOCAL MODEL CONTROL{RESET} {DIM}───────────────────{RESET}"
    tag = f"             {DIM}Manage · Switch · Run · Integrate · Your Local Models{RESET}"

    lines.append(sub)
    lines.append(tag)
    return "\n".join(lines)

def render_reference_status_card(
    is_active: bool,
    host: str,
    gpu_info: dict | None,
    ram_info: dict,
    active_model: str,
    loaded_models: list[dict] | None = None,
    installed_models: list[dict] | None = None,
    version_str: str | None = None
) -> str:
    """
    Renders compact, naturally aligned hardware and runtime telemetry.
    Eliminates enclosing box borders in favor of a clean, terminal-first presentation.
    """
    host_clean = host.replace("http://", "").replace("https://", "").rstrip("/")

    # 1. Ollama status
    if is_active:
        ver_text = f" · v{version_str}" if version_str else ""
        srv_text = f"{BRIGHT_GREEN}●{RESET} {BOLD}{WHITE}Ollama: Connected{RESET} {DIM}({host_clean}{ver_text}){RESET}"
    else:
        srv_text = f"{RED}○{RESET} {BOLD}{WHITE}Ollama: Offline{RESET} {DIM}({host_clean}){RESET}"

    # 2. RAM
    ram_used = ram_info.get("used_gb", 0.0)
    ram_total = ram_info.get("total_gb", 0.0)
    if ram_total > 0:
        ram_pct = (ram_used / ram_total)
        bar_w = 6
        filled = int(round(bar_w * max(0.0, min(1.0, ram_pct))))
        empty = bar_w - filled
        bar_color = BRIGHT_RED if ram_pct >= 0.9 else (BRIGHT_YELLOW if ram_pct >= 0.75 else BRIGHT_GREEN)
        ram_bar = f"{bar_color}{'█' * filled}{DIM}{'░' * empty}{RESET}"
        ram_text = f"{CYAN}◈{RESET} {BOLD}{WHITE}RAM:{RESET} {ram_used:.1f}/{ram_total:.1f} GiB [{ram_bar}] {DIM}{int(ram_pct*100)}%{RESET}"
    else:
        ram_text = f"{CYAN}◈{RESET} {BOLD}{WHITE}RAM:{RESET} {DIM}N/A{RESET}"

    # 3. GPU Telemetry
    if gpu_info:
        total_mb = gpu_info.get("total_mb", 0.0)
        used_mb = gpu_info.get("used_mb", 0.0)
        util = gpu_info.get("util_pct", 0.0)
        raw_name = gpu_info.get("name", "GPU")
        short_name = raw_name.replace("NVIDIA GeForce ", "").replace(" Laptop GPU", "").replace(" GPU", "").strip()
        gpu_text = f"{CYAN}◈{RESET} {BOLD}{WHITE}GPU:{RESET} {short_name} · {util:.0f}% · {int(used_mb)}/{int(total_mb)} MiB"
    else:
        gpu_text = f"{CYAN}◈{RESET} {BOLD}{WHITE}GPU:{RESET} {YELLOW}No GPU detected{RESET} {DIM}(CPU fallback){RESET}"

    # 4. Active Model & State Badge
    model_name = active_model or "(none)"
    if not active_model or active_model == "(none)":
        badge = f"{DIM}[STANDBY]{RESET}"
    elif not is_active:
        badge = f"{RED}[OFFLINE]{RESET}"
    elif loaded_models is not None and any(m.get("name") == active_model for m in loaded_models):
        badge = f"{BRIGHT_GREEN}[IN VRAM]{RESET}"
    elif installed_models is not None and not any(
        m.get("name") == active_model or m.get("model") == active_model for m in installed_models
    ):
        badge = f"{RED}[NOT INSTALLED]{RESET}"
    else:
        badge = f"{BRIGHT_GREEN}[READY]{RESET}"

    model_text = f"{CYAN}◈{RESET} {BOLD}{WHITE}Model:{RESET} {BRIGHT_WHITE}{model_name}{RESET} {badge}"

    # Width-aware formatting
    term_cols = shutil.get_terminal_size(fallback=(80, 24)).columns
    if term_cols >= 75:
        col_w = 40
        row1 = f"  {ansi_ljust(srv_text, col_w)} {ram_text}"
        row2 = f"  {ansi_ljust(gpu_text, col_w)} {model_text}"
        return f"{row1}\n{row2}"
    else:
        return f"  {srv_text}\n  {ram_text}\n  {gpu_text}\n  {model_text}"

def render_reference_quick_commands() -> str:
    """
    Renders 2-column matrix of frequently used commands.
    """
    left_cmds = [
        ("models",  "List installed models"),
        ("switch",  "Switch active model"),
        ("chat",    "Start interactive chat"),
        ("pull",    "Download model from hub"),
        ("unload",  "Unload model from VRAM"),
        ("remove",  "Remove model from disk"),
    ]
    right_cmds = [
        ("start",   "Start local server"),
        ("stop",    "Stop local server"),
        ("restart", "Restart local server"),
        ("status",  "Show system & model status"),
        ("doctor",  "Diagnose health & setup"),
        ("help",    "Show all commands"),
    ]

    lines = [f"  {BOLD}{BRIGHT_CYAN}Quick Commands:{RESET}"]
    for (cmd1, desc1), (cmd2, desc2) in zip(left_cmds, right_cmds):
        c1 = f"{BRIGHT_GREEN}{cmd1:<9}{RESET}{WHITE}{desc1:<27}{RESET}"
        c2 = f"{BRIGHT_GREEN}{cmd2:<9}{RESET}{WHITE}{desc2}{RESET}"
        lines.append(f"    {c1}  {c2}")
    return "\n".join(lines)
