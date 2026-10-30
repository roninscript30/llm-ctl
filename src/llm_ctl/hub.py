"""
Ollama Model Hub: curated directory, VRAM feasibility scoring, and model puller.
"""

import os
import json
import urllib.request
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn

console = Console()
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# Curated catalog of top open-weights models categorized for local developer machines
HUB_MODELS = [
    {
        "id": "qwen2.5-coder:1.5b",
        "name": "Qwen 2.5 Coder 1.5B",
        "category": "Coding",
        "size_gb": 0.98,
        "est_vram_mb": 1400,
        "description": "Ultra-fast code auto-complete and scripts (~95 tok/s)",
    },
    {
        "id": "qwen2.5-coder:3b",
        "name": "Qwen 2.5 Coder 3B",
        "category": "Coding",
        "size_gb": 1.90,
        "est_vram_mb": 2600,
        "description": "Best overall balance: full coding agent schemas & speed (~72 tok/s)",
    },
    {
        "id": "qwen2.5-coder:7b",
        "name": "Qwen 2.5 Coder 7B",
        "category": "Coding",
        "size_gb": 4.50,
        "est_vram_mb": 5200,
        "description": "High-capability coding & complex refactors (hybrid VRAM/RAM)",
    },
    {
        "id": "deepseek-r1:1.5b",
        "name": "DeepSeek R1 1.5B",
        "category": "Reasoning",
        "size_gb": 1.10,
        "est_vram_mb": 1600,
        "description": "DeepSeek reasoning monologue with internal <think> (~25 tok/s)",
    },
    {
        "id": "deepseek-r1:7b",
        "name": "DeepSeek R1 7B",
        "category": "Reasoning",
        "size_gb": 4.70,
        "est_vram_mb": 5500,
        "description": "Advanced reasoning, logic, and math (hybrid VRAM/RAM)",
    },
    {
        "id": "deepseek-r1:8b",
        "name": "DeepSeek R1 8B (Llama)",
        "category": "Reasoning",
        "size_gb": 4.90,
        "est_vram_mb": 5800,
        "description": "Llama 3.1 based DeepSeek distillation",
    },
    {
        "id": "llama3.2:1b",
        "name": "Llama 3.2 1B",
        "category": "General",
        "size_gb": 1.30,
        "est_vram_mb": 1500,
        "description": "Ultra-compact assistant for lightweight text operations",
    },
    {
        "id": "llama3.2:3b",
        "name": "Llama 3.2 3B",
        "category": "General",
        "size_gb": 2.00,
        "est_vram_mb": 2700,
        "description": "Fast multilingual instruction model",
    },
    {
        "id": "glm-edge-chat:1.5b",
        "name": "GLM Edge Chat 1.5B",
        "category": "General",
        "size_gb": 1.10,
        "est_vram_mb": 1500,
        "description": "Zhipu AI lightweight conversational edge model",
    },
    {
        "id": "codellama:7b",
        "name": "CodeLlama 7B",
        "category": "Coding",
        "size_gb": 3.80,
        "est_vram_mb": 4600,
        "description": "Meta CodeLlama foundation model",
    }
]

def get_vram_badge(est_vram_mb: int, gpu_total_mb: float = 4096.0) -> str:
    """Computes hardware feasibility badge for RTX 3050 (4 GB VRAM)."""
    if est_vram_mb <= (gpu_total_mb * 0.85):
        return "[bold bright_green]🟢 100% GPU[/bold bright_green]"
    elif est_vram_mb <= (gpu_total_mb * 1.3):
        return "[bold bright_yellow]🟡 Hybrid (RAM/GPU)[/bold bright_yellow]"
    else:
        return "[bold bright_red]🔴 Heavy (>5 GB)[/bold bright_red]"

def render_hub_table(installed_ids: set[str], gpu_total_mb: float = 4096.0) -> Table:
    """Generates an aesthetic Rich table of available Hub models."""
    table = Table(
        title="[bold bright_cyan]Ollama Model Hub — Curated Developer Directory[/bold bright_cyan]",
        border_style="cyan",
        header_style="bold bright_white",
        expand=True
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Model ID", style="bold cyan", width=22)
    table.add_column("Category", style="magenta", width=12)
    table.add_column("Disk Size", style="white", width=10)
    table.add_column("VRAM Fit (RTX 3050)", width=22)
    table.add_column("Description", style="dim white")
    table.add_column("Status", width=12)

    for idx, m in enumerate(HUB_MODELS, 1):
        is_installed = any(m["id"] in ins or ins.startswith(m["id"]) for ins in installed_ids)
        status = "[bold green]✔ Installed[/bold green]" if is_installed else "[dim]Available[/dim]"
        badge = get_vram_badge(m["est_vram_mb"], gpu_total_mb)

        table.add_row(
            str(idx),
            m["id"],
            m["category"],
            f"{m['size_gb']:.1f} GB",
            badge,
            m["description"],
            status
        )

    return table

def pull_model_stream(model_id: str) -> bool:
    """Pulls a model from Ollama with real-time streaming progress bars."""
    console.print(f"\n[bold cyan]Connecting to Ollama Hub to pull:[/bold cyan] [bold bright_green]{model_id}[/bold bright_green]")
    url = f"{OLLAMA_HOST}/api/pull"
    payload = json.dumps({"name": model_id, "stream": True}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req) as resp:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}[/bold cyan]"),
                BarColumn(complete_style="bright_green", finished_style="green"),
                DownloadColumn(),
                TransferSpeedColumn(),
                console=console
            ) as progress:
                tasks = {}
                for line in resp:
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                        status = data.get("status", "")
                        total = data.get("total", 0)
                        completed = data.get("completed", 0)
                        digest = data.get("digest", "main")

                        if status == "success":
                            console.print(f"\n[bold green]✔ Successfully pulled {model_id}![/bold green]")
                            return True

                        if total > 0:
                            if digest not in tasks:
                                tasks[digest] = progress.add_task(f"{status} ({digest[:10]})", total=total)
                            progress.update(tasks[digest], completed=completed, total=total, description=status)
                        else:
                            if "main" not in tasks:
                                tasks["main"] = progress.add_task(status, total=None)
                            progress.update(tasks["main"], description=status)
                    except json.JSONDecodeError:
                        continue
        return True
    except Exception as e:
        console.print(f"\n[bold red]Error pulling model {model_id}:[/bold red] {e}")
        return False
