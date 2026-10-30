"""
Hardware telemetry, memory tracking, and Ollama service inspection.
"""

import os
import json
import shutil
import subprocess
import urllib.request
import urllib.error

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

def get_service_status() -> bool:
    """Checks if Ollama REST API or systemd user service is active with bounded timeouts."""
    # 1. Direct REST ping to /api/version (bounded 1.0s)
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/version")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    # 2. Check systemctl --user is-active ollama (bounded 1.0s)
    try:
        res = subprocess.run(
            ["systemctl", "--user", "is-active", "ollama"],
            capture_output=True, text=True, timeout=1.0
        )
        if res.returncode == 0 and res.stdout.strip() == "active":
            return True
    except Exception:
        pass

    return False

def get_gpu_stats() -> dict | None:
    """Queries NVIDIA GPU VRAM, utilization, temperature, power, and model name.

    Uses nvidia-smi with query fields:
    name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw.
    Distinguishes unavailable GPU / missing nvidia-smi from genuine 0 values.
    Returns None if GPU is not present or command fails.
    """
    if not shutil.which("nvidia-smi"):
        return None

    try:
        res = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True, text=True, timeout=2.0
        )
        if res.returncode != 0:
            return None

        raw = res.stdout.strip()
        if not raw:
            return None

        first_line = raw.splitlines()[0]
        parts = [p.strip() for p in first_line.split(",")]
        if len(parts) < 6:
            return None

        def _safe_float(val: str, default: float = 0.0) -> float:
            try:
                return float(val.strip())
            except (ValueError, TypeError):
                return default

        name = parts[0]
        used_mb = _safe_float(parts[1])
        total_mb = _safe_float(parts[2])
        util_pct = _safe_float(parts[3])
        temp_c = parts[4]
        power_w = parts[5]

        return {
            "name": name,
            "used_mb": used_mb,
            "total_mb": total_mb,
            "util_pct": util_pct,
            "temp_c": temp_c,
            "power_w": power_w
        }
    except Exception:
        return None

def get_system_ram() -> dict:
    """Reads Linux /proc/meminfo to get system memory stats in GB.

    Parses MemTotal and MemAvailable, accurately calculates used_gb,
    total_gb, free_gb, and pct. Handles missing file cleanly.
    """
    fallback = {"used_gb": 0.0, "total_gb": 0.0, "free_gb": 0.0, "pct": 0.0}
    try:
        if not os.path.exists("/proc/meminfo"):
            return fallback

        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            lines = f.readlines()

        info: dict[str, float] = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                field = parts[0].strip()
                val_parts = parts[1].split()
                if val_parts:
                    try:
                        info[field] = float(val_parts[0])
                    except ValueError:
                        pass

        if "MemTotal" not in info or "MemAvailable" not in info:
            return fallback

        mem_total_kb = info["MemTotal"]
        mem_avail_kb = info["MemAvailable"]

        total_gb = mem_total_kb / (1024.0 * 1024.0)
        free_gb = mem_avail_kb / (1024.0 * 1024.0)
        used_gb = max(0.0, total_gb - free_gb)
        pct = (used_gb / total_gb * 100.0) if total_gb > 0.0 else 0.0

        return {
            "used_gb": round(used_gb, 2),
            "total_gb": round(total_gb, 2),
            "free_gb": round(free_gb, 2),
            "pct": round(pct, 1)
        }
    except Exception:
        return fallback

def get_loaded_models() -> list[dict]:
    """Retrieves list of models currently loaded into GPU/system memory.

    Queries direct /api/ps endpoint with bounded timeout (1.5s),
    extracting model names, size, and size_vram.
    Falls back to 'ollama ps' subprocess if needed.
    """
    # 1. Direct REST /api/ps endpoint
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/ps")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                raw_models = data.get("models", [])
                loaded = []
                for m in raw_models:
                    name = m.get("name") or m.get("model", "")
                    size = m.get("size", 0)
                    size_vram = m.get("size_vram", 0)
                    if size > 0 and size_vram >= size:
                        processor = "100% GPU"
                    elif size_vram > 0:
                        gpu_pct = int(round((size_vram / size) * 100))
                        processor = f"{gpu_pct}% GPU"
                    else:
                        processor = "CPU"
                    loaded.append({
                        "name": name,
                        "size": size,
                        "size_vram": size_vram,
                        "processor": processor,
                        "details": m.get("details", {}),
                        "expires_at": m.get("expires_at", "")
                    })
                return loaded
    except Exception:
        pass

    # 2. Subprocess fallback: ollama ps
    try:
        res = subprocess.run(
            ["ollama", "ps"],
            capture_output=True, text=True, timeout=1.5
        )
        if res.returncode != 0:
            return []

        lines = res.stdout.strip().splitlines()
        if len(lines) <= 1:
            return []

        loaded = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0]
                if len(parts) > 3 and parts[3].upper() in ("GB", "MB", "KB", "B", "GIB", "MIB"):
                    size_str = f"{parts[2]} {parts[3]}"
                    proc_idx = 4
                else:
                    size_str = parts[2]
                    proc_idx = 3

                if len(parts) > proc_idx + 1 and ("%" in parts[proc_idx] or parts[proc_idx + 1].upper() in ("GPU", "CPU")):
                    proc = f"{parts[proc_idx]} {parts[proc_idx + 1]}"
                elif len(parts) > proc_idx:
                    proc = parts[proc_idx]
                else:
                    proc = "unknown"

                loaded.append({
                    "name": name,
                    "size": size_str,
                    "size_vram": 0,
                    "processor": proc
                })
        return loaded
    except Exception:
        return []

def get_installed_models() -> list[dict]:
    """Queries Ollama for all downloaded models via direct /api/tags endpoint with bounded timeout (2.0s)."""
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                return data.get("models", [])
    except Exception:
        pass
    return []
