"""
Runtime server and model lifecycle management.
Provides explicit, distinct operations for:
1. Server controls: start, stop, restart Ollama local server
2. Model memory controls: unload loaded models from GPU/system RAM
3. Model storage controls: delete downloaded models from disk
"""

import time
import shutil
import subprocess
import urllib.request
import json
from .hardware import get_service_status, get_loaded_models, get_installed_models, OLLAMA_HOST

def get_server_version() -> str | None:
    """Queries Ollama server version via REST API."""
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/version")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("version")
    except Exception:
        return None

def start_server() -> tuple[bool, str]:
    """
    Starts the local Ollama server.
    First tries systemd user service ('systemctl --user start ollama').
    Falls back to starting 'ollama serve' in background if systemd is unavailable.
    """
    if get_service_status():
        ver = get_server_version()
        ver_str = f" (v{ver})" if ver else ""
        return True, f"Ollama service is already active on {OLLAMA_HOST}{ver_str}"

    # Try systemd user service first
    if shutil.which("systemctl"):
        try:
            res = subprocess.run(
                ["systemctl", "--user", "start", "ollama"],
                capture_output=True, text=True, timeout=5.0
            )
            if res.returncode == 0:
                for _ in range(10):
                    time.sleep(0.3)
                    if get_service_status():
                        ver = get_server_version()
                        ver_str = f" (v{ver})" if ver else ""
                        return True, f"Successfully started Ollama service via systemd{ver_str}"
        except Exception:
            pass

    # Fallback to direct 'ollama serve' background process if binary exists
    if shutil.which("ollama"):
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            for _ in range(10):
                time.sleep(0.3)
                if get_service_status():
                    ver = get_server_version()
                    ver_str = f" (v{ver})" if ver else ""
                    return True, f"Started Ollama daemon process{ver_str}"
        except Exception as e:
            return False, f"Failed starting 'ollama serve': {e}"

    return False, "Could not start Ollama. Ensure 'ollama' is installed and in PATH."

def stop_server() -> tuple[bool, str]:
    """
    Gracefully stops the Ollama server.
    First unloads any active models to flush GPU memory, then stops the service.
    """
    if not get_service_status():
        return True, "Ollama server is already stopped (offline)."

    # Unload loaded models before stopping to release VRAM cleanly
    unload_all_models()

    stopped = False
    if shutil.which("systemctl"):
        try:
            res = subprocess.run(
                ["systemctl", "--user", "stop", "ollama"],
                capture_output=True, text=True, timeout=5.0
            )
            if res.returncode == 0:
                for _ in range(10):
                    time.sleep(0.2)
                    if not get_service_status():
                        stopped = True
                        break
        except Exception:
            pass

    if not stopped and shutil.which("pkill"):
        try:
            subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True, timeout=3.0)
            time.sleep(0.5)
            if not get_service_status():
                stopped = True
        except Exception:
            pass

    if not get_service_status():
        return True, "Ollama server stopped successfully. Port 11434 and GPU memory released."
    return False, "Failed to stop Ollama server gracefully. Check 'systemctl --user status ollama'."

def restart_server() -> tuple[bool, str]:
    """Gracefully restarts the local Ollama server."""
    if shutil.which("systemctl"):
        try:
            res = subprocess.run(
                ["systemctl", "--user", "restart", "ollama"],
                capture_output=True, text=True, timeout=8.0
            )
            if res.returncode == 0:
                for _ in range(10):
                    time.sleep(0.3)
                    if get_service_status():
                        ver = get_server_version()
                        ver_str = f" (v{ver})" if ver else ""
                        return True, f"Ollama server restarted successfully{ver_str}"
        except Exception:
            pass

    # Stop then start
    stop_ok, _ = stop_server()
    time.sleep(0.5)
    start_ok, msg = start_server()
    if start_ok:
        return True, "Ollama server restarted successfully."
    return False, f"Failed restarting Ollama server: {msg}"

def unload_model(model_name: str) -> tuple[bool, str]:
    """
    Unloads a specific model from GPU/system memory without deleting it from disk.
    Uses 'ollama stop <model_name>' or REST API keep_alive=0.
    """
    if not get_service_status():
        return False, "Cannot unload model: Ollama service is offline."

    loaded = get_loaded_models()
    loaded_names = [m.get("name", "") for m in loaded]

    matched = None
    for ln in loaded_names:
        if model_name == ln or ln.startswith(model_name):
            matched = ln
            break

    if not matched:
        return True, f"Model '{model_name}' is not currently loaded in memory."

    try:
        res = subprocess.run(
            ["ollama", "stop", matched],
            capture_output=True, text=True, timeout=5.0
        )
        if res.returncode == 0:
            return True, f"Successfully unloaded '{matched}' from memory."
    except Exception:
        pass

    # Try REST API keep_alive = 0
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps({"model": matched, "keep_alive": 0}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5.0):
            return True, f"Successfully unloaded '{matched}' from memory via API."
    except Exception as e:
        return False, f"Failed unloading model '{matched}': {e}"

def unload_all_models() -> list[str]:
    """Unloads all models currently occupying GPU/system RAM."""
    if not get_service_status():
        return []

    loaded = get_loaded_models()
    evicted = []
    for m in loaded:
        name = m.get("name")
        if name:
            try:
                subprocess.run(
                    ["ollama", "stop", name],
                    capture_output=True, timeout=5.0
                )
                evicted.append(name)
            except Exception:
                pass
    return evicted

def remove_model(model_name: str) -> tuple[bool, str]:
    """
    Permanently deletes a downloaded model's weights from disk storage.
    Note: Must be preceded by explicit confirmation.
    """
    if not shutil.which("ollama"):
        return False, "Ollama executable not found in PATH."

    try:
        # First ensure it is unloaded from VRAM
        unload_model(model_name)

        res = subprocess.run(
            ["ollama", "rm", model_name],
            capture_output=True, text=True, timeout=10.0
        )
        if res.returncode == 0:
            return True, f"Permanently removed model '{model_name}' from disk storage."
        else:
            return False, res.stderr.strip() or f"Failed removing model '{model_name}'."
    except Exception as e:
        return False, f"Error executing model deletion: {e}"
