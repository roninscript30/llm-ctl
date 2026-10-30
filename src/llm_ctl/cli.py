"""
Main CLI router and subcommand dispatcher for llm-ctl.
"""

import sys
import os
import json
import subprocess
from rich.console import Console
from rich.table import Table

from .banner import render_banner, render_telemetry_panel
from .hardware import get_gpu_stats, get_system_ram, get_loaded_models, get_installed_models, OLLAMA_HOST
from .orchestrator import get_active_model, switch_model, free_vram, sync_all_configs
from .hub import HUB_MODELS, render_hub_table, pull_model_stream
from .interactive import run_interactive_dashboard

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

    console.print(render_banner(active_model=active))
    console.print(render_telemetry_panel(gpu, ram, loaded))

    table = Table(title="[bold bright_white]Installed Local Models[/bold bright_white]", border_style="cyan", header_style="bold white")
    table.add_column("Model Name", style="bold green", width=26)
    table.add_column("Size", width=12)
    table.add_column("Parameters", width=14)
    table.add_column("Quant", width=10)
    table.add_column("Active", width=12)

    for m in installed:
        name = m.get("name", "")
        size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
        details = m.get("details", {})
        param = details.get("parameter_size", "unknown")
        quant = details.get("quantization_level", "unknown")
        is_active = "[bold bright_green]★ ACTIVE[/bold bright_green]" if name.startswith(active) else ""
        table.add_row(name, f"{size_gb:.2f} GB", param, quant, is_active)

    console.print(table)
    console.print(f"\n[dim]Run 'llm --help' for CLI commands or 'llm' without args for the interactive dashboard.[/dim]\n")

def cmd_ps(json_output: bool = False):
    """Displays models currently occupying GPU/system RAM."""
    loaded = get_loaded_models()
    if json_output:
        print(json.dumps(loaded, indent=2))
        return

    if not loaded:
        console.print("[bold green]✔ GPU VRAM is completely idle (0 MB allocated).[/bold green]")
        return

    table = Table(title="[bold bright_white]Models Currently in VRAM / RAM[/bold bright_white]", border_style="cyan")
    table.add_column("Model Name", style="bold green", width=28)
    table.add_column("Memory Allocated", width=16)
    table.add_column("Processor Type", style="cyan", width=16)

    for m in loaded:
        table.add_row(m["name"], m["size"], m["processor"])
    console.print(table)

def cmd_ls(json_output: bool = False):
    """Lists all installed models."""
    installed = get_installed_models()
    if json_output:
        print(json.dumps(installed, indent=2))
        return

    table = Table(title="[bold bright_white]Local Model Repository[/bold bright_white]", border_style="cyan")
    table.add_column("Name", style="bold green", width=28)
    table.add_column("Disk Size", width=12)
    table.add_column("Parameters", width=14)
    table.add_column("Quantization", width=14)

    for m in installed:
        name = m.get("name", "")
        size_gb = m.get("size", 0) / (1024 * 1024 * 1024)
        details = m.get("details", {})
        table.add_row(name, f"{size_gb:.2f} GB", details.get("parameter_size", "-"), details.get("quantization_level", "-"))
    console.print(table)

def cmd_launch(args: list[str]):
    """Launches one of the coding agent clients."""
    if not args:
        console.print("[bold yellow]Usage:[/bold yellow] llm launch <claude|opencode|dsh> [extra_args...]")
        return

    target = args[0].lower()
    extra = args[1:]
    active = get_active_model()

    if target in ("claude", "cc"):
        console.print(f"\n[bold cyan]Starting Claude Code with active model:[/bold cyan] [bold bright_green]{active}[/bold bright_green]")
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = OLLAMA_HOST
        env["ANTHROPIC_API_KEY"] = "ollama"
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = active
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = active
        subprocess.run(["claude", "--model", active] + extra, env=env)
    elif target in ("opencode", "oc"):
        console.print(f"\n[bold cyan]Starting OpenCode with active model:[/bold cyan] [bold bright_green]ollama/{active}[/bold bright_green]")
        subprocess.run(["opencode", "--model", f"ollama/{active}"] + extra)
    elif target in ("dsh", "deepseek"):
        mode = extra[0] if extra else "web"
        if mode in ("web", "ui"):
            console.print(f"\n[bold cyan]Starting DeepSeek Harness Web UI at http://127.0.0.1:3080...[/bold cyan]")
            subprocess.run(["dsh", "web"])
        else:
            subprocess.run(["dsh", "headless"] + extra)
    else:
        console.print(f"[bold red]Unknown agent client:[/bold red] '{target}'. Available: claude, opencode, dsh")

def cmd_bench():
    """Prints benchmark report."""
    if not os.path.exists(BENCHMARK_RESULTS):
        console.print(f"[bold yellow]No benchmark results found at {BENCHMARK_RESULTS}.[/bold yellow]")
        return
    try:
        with open(BENCHMARK_RESULTS) as f:
            data = json.load(f)
        table = Table(title="[bold bright_white]Hardware LLM Inference Benchmarks[/bold bright_white]", border_style="cyan")
        table.add_column("Model", style="bold cyan", width=22)
        table.add_column("Tokens/sec", style="bold green", width=12)
        table.add_column("TTFT (s)", width=10)
        table.add_column("VRAM Used", width=12)
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
    except Exception as e:
        console.print(f"[bold red]Error loading benchmarks:[/bold red] {e}")

def cmd_service(action: str):
    """Controls the Ollama systemd user service."""
    if action == "status":
        subprocess.run(["systemctl", "--user", "status", "ollama", "--no-pager"])
    elif action in ("start", "stop", "restart"):
        console.print(f"[cyan]Executing: systemctl --user {action} ollama...[/cyan]")
        subprocess.run(["systemctl", "--user", action, "ollama"])
    elif action in ("logs", "journal"):
        subprocess.run(["journalctl", "--user", "-u", "ollama", "-n", "35", "--no-pager"])
    else:
        console.print("[bold yellow]Usage:[/bold yellow] llm service <start|stop|restart|status|logs>")

def print_help():
    """Prints sleek help message."""
    help_text = """
[bold bright_cyan]llm-ctl[/bold bright_cyan] — Modern Developer CLI for Local LLM Management & VRAM Orchestration

[bold white]USAGE:[/bold white]
    llm                        [dim]Launch interactive terminal dashboard (single-key UI)[/dim]
    llm <command> [options]    [dim]Execute non-interactive CLI command directly[/dim]

[bold white]CORE COMMANDS:[/bold white]
    [bold bright_green]status[/bold bright_green]                 Show active model, GPU VRAM gauge & host memory
    [bold bright_green]use <model>[/bold bright_green]            Hot-swap active model, evict old VRAM & pre-warm
    [bold bright_green]free[/bold bright_green]                   Evict all loaded models (purges GPU VRAM to 0 MB)
    [bold bright_green]ps[/bold bright_green]                     Display models currently occupying VRAM
    [bold bright_green]ls[/bold bright_green]                     List all installed models with parameters & quantization

[bold white]MODEL DISCOVERY & HUB:[/bold white]
    [bold bright_green]hub[/bold bright_green]                    Browse curated Ollama Model Hub with VRAM badges
    [bold bright_green]pull <model>[/bold bright_green]           Download model from Ollama registry with live progress
    [bold bright_green]rm <model>[/bold bright_green]             Delete an installed model
    [bold bright_green]bench[/bold bright_green]                  View hardware tok/s benchmarks for your GPU

[bold white]AGENT LAUNCHERS & CHAT:[/bold white]
    [bold bright_green]launch claude[/bold bright_green]          Launch Claude Code wired to active local model
    [bold bright_green]launch opencode[/bold bright_green]        Launch OpenCode wired to active local model
    [bold bright_green]launch dsh [web|cli][/bold bright_green]   Launch DeepSeek Harness Web UI or CLI
    [bold bright_green]chat [model][/bold bright_green]           Start direct interactive terminal chat
    [bold bright_green]sync[/bold bright_green]                   Force sync configs across Claude, OpenCode & DSH
    [bold bright_green]service <action>[/bold bright_green]       Control Ollama systemd service (start, stop, logs)

[bold white]FLAGS:[/bold white]
    [bold cyan]--json[/bold cyan]                 Output responses in structured JSON for automation
    [bold cyan]-h, --help[/bold cyan]             Show this help screen
"""
    console.print(help_text)

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
            console.print("[bold red]Usage:[/bold red] llm use <model_name>")
            sys.exit(1)
        switch_model(rest[0])
    elif cmd in ("free", "unload", "clear"):
        evicted = free_vram()
        console.print(f"[bold green]✔ Evicted {len(evicted)} models. 100% GPU VRAM is free![/bold green]")
    elif cmd == "hub":
        installed = get_installed_models()
        installed_ids = {m.get("name", "") for m in installed}
        gpu = get_gpu_stats()
        console.print(render_hub_table(installed_ids, gpu["total_mb"] if gpu else 4096.0))
    elif cmd == "pull":
        if not rest:
            console.print("[bold red]Usage:[/bold red] llm pull <model_name>")
            sys.exit(1)
        pull_model_stream(rest[0])
    elif cmd in ("rm", "delete"):
        if not rest:
            console.print("[bold red]Usage:[/bold red] llm rm <model_name>")
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
        console.print(f"[bold cyan]Connecting to {active}... (Type '/bye' to exit)[/bold cyan]\n")
        subprocess.run(["ollama", "run", active])
    elif cmd == "sync":
        active = get_active_model()
        sync_all_configs(active)
        console.print(f"[bold green]✔ Synchronized configs for Claude Code, OpenCode & DSH to: {active}[/bold green]")
    elif cmd == "bench":
        cmd_bench()
    elif cmd == "service":
        cmd_service(rest[0] if rest else "status")
    elif cmd in ("-h", "--help", "help"):
        print_help()
    else:
        console.print(f"[bold red]Unknown command:[/bold red] '{cmd}'. Run 'llm --help' for available commands.")

if __name__ == "__main__":
    main()
