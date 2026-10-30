"""
Main CLI router and subcommand dispatcher for llm-ctl.
"""

import sys
import os
import json
import subprocess
from rich.console import Console
from rich.table import Table

from .banner import render_dashboard_header
from .hardware import get_gpu_stats, get_system_ram, get_loaded_models, get_installed_models, OLLAMA_HOST
from .orchestrator import get_active_model, switch_model, free_vram, sync_all_configs
from .hub import HUB_MODELS, render_hub_table, pull_model_stream
from .interactive import run_interactive_dashboard
from .terminal import BOLD, DIM, RESET, BRIGHT_GREEN, CYAN, WHITE

console = Console()
BENCHMARK_RESULTS = os.path.expanduser("~/REPOS/dev-env/llm-experiments/results.json")

def print_status(json_output: bool = False):
    """Outputs current hardware status, active model, and loaded VRAM models."""
    active = get_active_model()
    gpu = get_gpu_stats()
    ram = get_system_ram()
    loaded = get_loaded_models()
    installed = get_installed_models()

    if json_output:
        data = {
            "active_model": active,
            "endpoint": OLLAMA_HOST,
            "gpu": gpu,
            "system_ram": ram,
            "loaded_models": loaded,
            "installed_models_count": len(installed)
        }
        print(json.dumps(data, indent=2))
        return

    # Print sleek Claude-style header
    print(render_dashboard_header(active, gpu, ram, loaded))

    # Print clean local models table
    table = Table(
        title="[bold bright_white]Installed Local Models[/bold bright_white]",
        border_style="cyan",
        header_style="bold bright_white",
        box=None,
        padding=(0, 2)
    )
    table.add_column("Model", style="bold green", width=26)
    table.add_column("Size", width=12)
    table.add_column("Parameters", width=14)
    table.add_column("Quantization", width=14)
    table.add_column("State", width=12)

    for m in installed:
        name = m.get("name", "")
        size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
        details = m.get("details", {})
        param = details.get("parameter_size", "unknown")
        quant = details.get("quantization_level", "unknown")
        is_active = "[bold bright_green]★ ACTIVE[/bold bright_green]" if name.startswith(active) else ""
        table.add_row(name, f"{size_gb:.2f} GB", param, quant, is_active)

    console.print(table)
    print(f"\n  {DIM}Run 'llm' for arrow-key interactive dashboard or 'llm --help' for CLI commands.{RESET}\n")

def cmd_ps(json_output: bool = False):
    """Displays models currently occupying GPU/system RAM."""
    loaded = get_loaded_models()
    if json_output:
        print(json.dumps(loaded, indent=2))
        return

    if not loaded:
        print(f"\n  {BRIGHT_GREEN}✔ GPU VRAM is completely idle (0 MB allocated).{RESET}\n")
        return

    table = Table(
        title="[bold bright_white]Models Currently in VRAM / RAM[/bold bright_white]",
        border_style="cyan",
        box=None,
        padding=(0, 2)
    )
    table.add_column("Model Name", style="bold green", width=28)
    table.add_column("Memory Allocated", width=18)
    table.add_column("Processor Type", style="cyan", width=16)

    for m in loaded:
        table.add_row(m["name"], m["size"], m["processor"])
    console.print(table)
    print()

def cmd_ls(json_output: bool = False):
    """Lists all installed models."""
    installed = get_installed_models()
    if json_output:
        print(json.dumps(installed, indent=2))
        return

    table = Table(
        title="[bold bright_white]Local Model Repository[/bold bright_white]",
        border_style="cyan",
        box=None,
        padding=(0, 2)
    )
    table.add_column("Model Name", style="bold green", width=28)
    table.add_column("Disk Size", width=12)
    table.add_column("Parameters", width=14)
    table.add_column("Quantization", width=14)

    for m in installed:
        name = m.get("name", "")
        size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
        details = m.get("details", {})
        table.add_row(name, f"{size_gb:.2f} GB", details.get("parameter_size", "-"), details.get("quantization_level", "-"))
    console.print(table)
    print()

def cmd_launch(args: list[str]):
    """Launches one of the coding agent clients."""
    if not args:
        print(f"\n  {BOLD}{YELLOW}Usage:{RESET} llm launch <claude|opencode|dsh> [extra_args...]\n")
        return

    target = args[0].lower()
    extra = args[1:]
    active = get_active_model()

    if target in ("claude", "cc"):
        print(f"\n  {BOLD}{CYAN}Starting Claude Code with active model:{RESET} {BRIGHT_GREEN}{active}{RESET}\n")
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = OLLAMA_HOST
        env["ANTHROPIC_API_KEY"] = "ollama"
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = active
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = active
        subprocess.run(["claude", "--model", active] + extra, env=env)
    elif target in ("opencode", "oc"):
        print(f"\n  {BOLD}{CYAN}Starting OpenCode with active model:{RESET} {BRIGHT_GREEN}ollama/{active}{RESET}\n")
        subprocess.run(["opencode", "--model", f"ollama/{active}"] + extra)
    elif target in ("dsh", "deepseek"):
        mode = extra[0] if extra else "web"
        if mode in ("web", "ui"):
            print(f"\n  {BOLD}{CYAN}Starting DeepSeek Harness Web UI at http://127.0.0.1:3080...{RESET}\n")
            subprocess.run(["dsh", "web"])
        else:
            subprocess.run(["dsh", "headless"] + extra)
    else:
        print(f"\n  {BOLD}{RED}Unknown agent client:{RESET} '{target}'. Available: claude, opencode, dsh\n")

def cmd_bench():
    """Prints benchmark report."""
    if not os.path.exists(BENCHMARK_RESULTS):
        print(f"\n  {YELLOW}No benchmark results found at {BENCHMARK_RESULTS}.{RESET}\n")
        return
    try:
        with open(BENCHMARK_RESULTS) as f:
            data = json.load(f)
        table = Table(
            title="[bold bright_white]Hardware LLM Inference Benchmarks[/bold bright_white]",
            border_style="cyan",
            box=None,
            padding=(0, 2)
        )
        table.add_column("Model", style="bold cyan", width=22)
        table.add_column("Tokens/sec", style="bold green", width=14)
        table.add_column("TTFT (s)", width=12)
        table.add_column("VRAM Used", width=14)
        table.add_column("Status", width=10)

        for r in data.get("results", []):
            st = "[bold green]PASS[/bold green]" if r.get("success") else "[bold red]FAIL[/bold red]"
            table.add_row(
                r.get("model", ""),
                f"{r.get('tokens_per_second', 0):.1f} tok/s",
                f"{r.get('time_to_first_token_sec', 0):.2f} s",
                f"{r.get('vram_used_mb', 0):.0f} MiB",
                st
            )
        console.print(table)
        print()
    except Exception as e:
        print(f"\n  {RED}Error loading benchmarks:{RESET} {e}\n")

def cmd_service(action: str):
    """Controls the Ollama systemd user service."""
    if action == "status":
        subprocess.run(["systemctl", "--user", "status", "ollama", "--no-pager"])
    elif action in ("start", "stop", "restart"):
        print(f"\n  {CYAN}Executing: systemctl --user {action} ollama...{RESET}")
        subprocess.run(["systemctl", "--user", action, "ollama"])
    elif action in ("logs", "journal"):
        subprocess.run(["journalctl", "--user", "-u", "ollama", "-n", "35", "--no-pager"])
    else:
        print(f"\n  {YELLOW}Usage:{RESET} llm service <start|stop|restart|status|logs>\n")

def print_help():
    """Prints sleek help message."""
    help_text = f"""
  {BOLD}{BRIGHT_CYAN}llm-ctl{RESET} — Modern Developer CLI for Local LLM Management & VRAM Orchestration

  {BOLD}{WHITE}USAGE:{RESET}
    llm                        {DIM}Launch interactive arrow-key dashboard{RESET}
    llm <command> [options]    {DIM}Execute non-interactive CLI command directly{RESET}

  {BOLD}{WHITE}CORE COMMANDS:{RESET}
    {BRIGHT_GREEN}status{RESET}                 Show active model, GPU VRAM gauge & host memory
    {BRIGHT_GREEN}use <model>{RESET}            Hot-swap active model, evict old VRAM & pre-warm
    {BRIGHT_GREEN}free{RESET}                   Evict all loaded models (purges GPU VRAM to 0 MB)
    {BRIGHT_GREEN}ps{RESET}                     Display models currently occupying VRAM
    {BRIGHT_GREEN}ls{RESET}                     List all installed models with parameters & quantization

  {BOLD}{WHITE}MODEL DISCOVERY & HUB:{RESET}
    {BRIGHT_GREEN}hub{RESET}                    Browse curated Ollama Model Hub with VRAM badges
    {BRIGHT_GREEN}pull <model>{RESET}           Download model from Ollama registry with live progress
    {BRIGHT_GREEN}rm <model>{RESET}             Delete an installed model
    {BRIGHT_GREEN}bench{RESET}                  View hardware tok/s benchmarks for your GPU

  {BOLD}{WHITE}AGENT LAUNCHERS & CHAT:{RESET}
    {BRIGHT_GREEN}launch claude{RESET}          Launch Claude Code wired to active local model
    {BRIGHT_GREEN}launch opencode{RESET}        Launch OpenCode wired to active local model
    {BRIGHT_GREEN}launch dsh [web|cli]{RESET}   Launch DeepSeek Harness Web UI or CLI
    {BRIGHT_GREEN}chat [model]{RESET}           Start direct interactive terminal chat
    {BRIGHT_GREEN}sync{RESET}                   Force sync configs across Claude, OpenCode & DSH
    {BRIGHT_GREEN}service <action>{RESET}       Control Ollama systemd service (start, stop, logs)

  {BOLD}{WHITE}FLAGS:{RESET}
    {CYAN}--json{RESET}                 Output responses in structured JSON for automation
    {CYAN}-h, --help{RESET}             Show this help screen
"""
    print(help_text)

def main():
    args = sys.argv[1:]
    is_json = "--json" in args
    filtered_args = [a for a in args if a != "--json"]

    if not filtered_args:
        if sys.stdin.isatty():
            run_interactive_dashboard()
        else:
            print_status(json_output=is_json)
        return

    cmd = filtered_args[0].lower()
    rest = filtered_args[1:]

    if cmd in ("status", "info"):
        print_status(json_output=is_json)
    elif cmd in ("ps", "top"):
        cmd_ps(json_output=is_json)
    elif cmd in ("ls", "list", "models"):
        cmd_ls(json_output=is_json)
    elif cmd in ("use", "switch"):
        if not rest:
            print(f"\n  {RED}Usage:{RESET} llm use <model_name>\n")
            sys.exit(1)
        switch_model(rest[0])
    elif cmd in ("free", "unload", "clear"):
        evicted = free_vram()
        print(f"\n  {BRIGHT_GREEN}✔ Evicted {len(evicted)} model(s). 100% GPU VRAM is free!{RESET}\n")
    elif cmd == "hub":
        installed = get_installed_models()
        installed_ids = {m.get("name", "") for m in installed}
        gpu = get_gpu_stats()
        console.print(render_hub_table(installed_ids, gpu["total_mb"] if gpu else 4096.0))
    elif cmd == "pull":
        if not rest:
            print(f"\n  {RED}Usage:{RESET} llm pull <model_name>\n")
            sys.exit(1)
        pull_model_stream(rest[0])
    elif cmd in ("rm", "delete"):
        if not rest:
            print(f"\n  {RED}Usage:{RESET} llm rm <model_name>\n")
            sys.exit(1)
        subprocess.run(["ollama", "rm", rest[0]])
    elif cmd == "launch":
        cmd_launch(rest)
    elif cmd in ("claude", "cc"):
        cmd_launch(["claude"] + rest)
    elif cmd in ("opencode", "oc"):
        cmd_launch(["opencode"] + rest)
    elif cmd in ("dsh", "deepseek"):
        cmd_launch(["dsh"] + rest)
    elif cmd == "chat":
        active = rest[0] if rest else get_active_model()
        print(f"\n  {BOLD}{CYAN}Connecting to {active}... (Type '/bye' to exit){RESET}\n")
        subprocess.run(["ollama", "run", active])
    elif cmd == "sync":
        active = get_active_model()
        sync_all_configs(active)
        print(f"\n  {BRIGHT_GREEN}✔ Synchronized configs for Claude Code, OpenCode & DSH to: {active}{RESET}\n")
    elif cmd == "bench":
        cmd_bench()
    elif cmd == "service":
        cmd_service(rest[0] if rest else "status")
    elif cmd in ("-h", "--help", "help"):
        print_help()
    else:
        print(f"\n  {RED}Unknown command:{RESET} '{cmd}'. Run 'llm --help' for available commands.\n")

if __name__ == "__main__":
    main()
