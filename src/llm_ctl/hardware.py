"""
Hardware telemetry, memory tracking, and Ollama service inspection.
"""

import os
import json
import subprocess
import urllib.request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

def get_service_status() -> bool:
    """Checks if Ollama systemd user service or process is active."""
    try:
        out = subprocess.check_output(
            ["systemctl", "--user", "is-active", "ollama"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        if out == "active":
            return True
    except Exception:
        pass

    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/version")
        with urllib.request.urlopen(req, timeout=1):
            return True
    except Exception:
        return False

def get_gpu_stats() -> dict | None:
    """Queries NVIDIA GPU VRAM, temperature, power, and model name."""
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"
            ],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        return {
            "name": parts[0],
            "used_mb": float(parts[1]),
            "total_mb": float(parts[2]),
            "temp_c": parts[3],
            "power_w": parts[4]
        }
    except Exception:
        return None

def get_system_ram() -> dict:
    """Reads Linux /proc/meminfo to get system memory stats in GB."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        info = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                info[parts[0].strip()] = float(parts[1].split()[0])
        total_gb = info.get("MemTotal", 0) / (1024 * 1024)
        avail_gb = info.get("MemAvailable", 0) / (1024 * 1024)
        used_gb = total_gb - avail_gb
        return {
            "used_gb": used_gb,
            "total_gb": total_gb,
            "free_gb": avail_gb
        }
    except Exception:
        return {"used_gb": 0.0, "total_gb": 0.0, "free_gb": 0.0}

def get_loaded_models() -> list[dict]:
    """Retrieves list of models currently loaded into GPU/system memory."""
    try:
        out = subprocess.check_output(["ollama", "ps"], text=True, stderr=subprocess.DEVNULL).strip()
        lines = out.splitlines()
        if len(lines) <= 1:
            return []
        loaded = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                loaded.append({
                    "name": parts[0],
                    "size": parts[2] if len(parts) > 2 else "unknown",
                    "processor": parts[3] if len(parts) > 3 else "unknown"
                })
        return loaded
    except Exception:
        return []

def get_installed_models() -> list[dict]:
    """Queries Ollama for all downloaded models."""
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data.get("models", [])
    except Exception:
        return []
