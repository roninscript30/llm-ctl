"""
Terminal visual identity, 3D ASCII branding, and horizontal status card.
Tailored for monospace displays (SpaceMono-Regular 11pt) and 80-column safe layout.
"""

import re
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
    Strictly clamps strings exceeding width to guarantee vertical terminal borders never blow out.
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
    Renders 4-column rounded horizontal status card:
    [ Ollama Status | RAM Gauge | GPU Telemetry | Active Model & State ]
    Guarantees strict boundary constraints so borders never blow out.
    """
    col1_w = 21
    col2_w = 15
    col3_w = 17
    col4_w = 19
    inner_width = col1_w + col2_w + col3_w + col4_w + 3  # 75 chars inner, 79 chars total with borders & indent

    # 1. Column 1: Ollama Status
    if is_active:
        srv_status = f"{BRIGHT_GREEN}●{RESET} {BOLD}{WHITE}Ollama: Connected{RESET}"
    else:
        srv_status = f"{RED}○{RESET} {BOLD}{WHITE}Ollama: Offline{RESET}"
    r1_c1 = ansi_ljust(f" {srv_status}", col1_w)

    host_clean = host.replace("http://", "").replace("https://", "").rstrip("/")
    r2_c1 = ansi_ljust(f"   {DIM}{truncate_str(host_clean, col1_w - 4)}{RESET}", col1_w)

    if is_active:
        ver = version_str or "API v1 │ HTTP"
        r3_c1 = ansi_ljust(f"   {DIM}{truncate_str(ver, col1_w - 4)}{RESET}", col1_w)
    else:
        r3_c1 = ansi_ljust(f"   {DIM}Service Offline{RESET}", col1_w)

    # 2. Column 2: RAM Gauge
    r1_c2 = ansi_ljust(f" {CYAN}◈{RESET} {BOLD}{WHITE}RAM{RESET}", col2_w)

    ram_used = ram_info.get("used_gb", 0.0)
    ram_total = ram_info.get("total_gb", 0.0)
    r2_c2 = ansi_ljust(f"  {WHITE}{ram_used:.1f} / {ram_total:.1f} GiB{RESET}", col2_w)

    ram_pct = (ram_used / ram_total) if ram_total > 0 else 0.0
    bar_w = 10
    filled = int(round(bar_w * max(0.0, min(1.0, ram_pct))))
    empty = bar_w - filled
    bar_color = BRIGHT_RED if ram_pct >= 0.9 else (BRIGHT_YELLOW if ram_pct >= 0.75 else BRIGHT_GREEN)
    ram_bar = f"{bar_color}{'█' * filled}{DIM}{'░' * empty}{RESET}"
    r3_c2 = ansi_ljust(f"  [{ram_bar}]", col2_w)

    # 3. Column 3: GPU Telemetry
    r1_c3 = ansi_ljust(f" {CYAN}◈{RESET} {BOLD}{WHITE}GPU{RESET}", col3_w)

    if gpu_info:
        total_mb = gpu_info.get("total_mb", 0.0)
        used_mb = gpu_info.get("used_mb", 0.0)
        vram_pct = (used_mb / total_mb * 100) if total_mb > 0 else 0.0
        r2_c3 = ansi_ljust(f"  {WHITE}{vram_pct:.0f}% │ {int(used_mb)}/{int(total_mb)} MiB{RESET}", col3_w)

        temp = gpu_info.get("temp_c")
        power = gpu_info.get("power_w")
        gpu_name = gpu_info.get("name")
        if temp and power:
            try:
                r3_c3 = ansi_ljust(f"  {DIM}{temp}°C │ {float(power):.1f}W{RESET}", col3_w)
            except Exception:
                r3_c3 = ansi_ljust(f"  {DIM}{temp}°C │ {power}W{RESET}", col3_w)
        elif gpu_name:
            short_name = truncate_str(gpu_name.replace("NVIDIA GeForce ", "").replace(" GPU", ""), col3_w - 3)
            r3_c3 = ansi_ljust(f"  {DIM}{short_name}{RESET}", col3_w)
        else:
            r3_c3 = ansi_ljust(f"  {DIM}Online │ Active{RESET}", col3_w)
    else:
        r2_c3 = ansi_ljust(f"  {YELLOW}No GPU detected{RESET}", col3_w)
        r3_c3 = ansi_ljust(f"  {DIM}CPU fallback{RESET}", col3_w)

    # 4. Column 4: Active Model & State Badge
    r1_c4 = ansi_ljust(f" {CYAN}◈{RESET} {BOLD}{WHITE}Active Model{RESET}", col4_w)

    model_clean = truncate_str(active_model or "(none)", col4_w - 3)
    r2_c4 = ansi_ljust(f"  {BRIGHT_WHITE}{model_clean}{RESET}", col4_w)

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
    r3_c4 = ansi_ljust(f"  {badge}", col4_w)

    # Assemble Card with Rounded Borders
    top_border = f"  {CYAN}╭" + ("─" * inner_width) + f"╮{RESET}"
    bottom_border = f"  {CYAN}╰" + ("─" * inner_width) + f"╯{RESET}"

    row1 = f"  {CYAN}│{RESET}{r1_c1}{CYAN}│{RESET}{r1_c2}{CYAN}│{RESET}{r1_c3}{CYAN}│{RESET}{r1_c4}{CYAN}│{RESET}"
    row2 = f"  {CYAN}│{RESET}{r2_c1}{CYAN}│{RESET}{r2_c2}{CYAN}│{RESET}{r2_c3}{CYAN}│{RESET}{r2_c4}{CYAN}│{RESET}"
    row3 = f"  {CYAN}│{RESET}{r3_c1}{CYAN}│{RESET}{r3_c2}{CYAN}│{RESET}{r3_c3}{CYAN}│{RESET}{r3_c4}{CYAN}│{RESET}"

    return f"{top_border}\n{row1}\n{row2}\n{row3}\n{bottom_border}"

def render_reference_quick_commands() -> str:
    """
    Renders 2-column matrix of frequently used commands.
    """
    left_cmds = [
        ("models", "List installed models"),
        ("switch", "Switch active model"),
        ("chat",   "Start interactive chat"),
        ("agents", "Manage coding agents"),
        ("status", "Show system & model status"),
        ("doctor", "Diagnose setup & health"),
    ]
    right_cmds = [
        ("pull",   "Download a model"),
        ("remove", "Remove a model"),
        ("run",    "Start local server"),
        ("config", "Edit configuration"),
        ("help",   "Show all commands"),
        ("", ""),
    ]

    lines = [f"  {BOLD}{BRIGHT_CYAN}Quick Commands:{RESET}"]
    for (cmd1, desc1), (cmd2, desc2) in zip(left_cmds, right_cmds):
        c1 = f"{BRIGHT_GREEN}{cmd1:<8}{RESET}{WHITE}{desc1:<30}{RESET}" if cmd1 else " " * 38
        c2 = f"{BRIGHT_GREEN}{cmd2:<8}{RESET}{WHITE}{desc2}{RESET}" if cmd2 else ""
        lines.append(f"    {c1}  {c2}")
    return "\n".join(lines)
