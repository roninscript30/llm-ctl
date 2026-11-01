"""
Unit tests for paths, runtime server management, shell scripts, and completions.
Covers:
- src/llm_ctl/paths.py (XDG overrides, directory creation, legacy migration)
- src/llm_ctl/runtime.py (server start/stop/restart, model unload, eviction, deletion)
- scripts/install.sh, scripts/uninstall.sh, install.sh syntax & safety
- completions/llm.bash, completions/llm.zsh, completions/llm.fish completeness
"""

import sys
import os
import shutil
import tempfile
import importlib
import subprocess
import unittest
from unittest.mock import patch, MagicMock

# Ensure src/ is on Python path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

import llm_ctl.paths as paths
import llm_ctl.runtime as runtime


class TestPaths(unittest.TestCase):
    """Tests for XDG path resolution, directory creation, and legacy migration."""

    def tearDown(self):
        # Always reload paths to clean default state after test mutations
        importlib.reload(paths)

    def test_xdg_defaults(self):
        """Verifies default paths when XDG environment variables are absent."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure no XDG vars
            os.environ.pop("XDG_CONFIG_HOME", None)
            os.environ.pop("XDG_STATE_HOME", None)
            os.environ.pop("XDG_CACHE_HOME", None)
            importlib.reload(paths)

            home = os.path.expanduser("~")
            self.assertEqual(paths.XDG_CONFIG_HOME, os.path.join(home, ".config"))
            self.assertEqual(paths.XDG_STATE_HOME, os.path.join(home, ".local/state"))
            self.assertEqual(paths.XDG_CACHE_HOME, os.path.join(home, ".cache"))

            self.assertEqual(paths.CONFIG_DIR, os.path.join(home, ".config/llm-ctl"))
            self.assertEqual(paths.CONFIG_FILE, os.path.join(home, ".config/llm-ctl/config.json"))
            self.assertEqual(paths.STATE_DIR, os.path.join(home, ".local/state/llm-ctl"))
            self.assertEqual(paths.HISTORY_FILE, os.path.join(home, ".local/state/llm-ctl/history"))
            self.assertEqual(paths.LOGS_DIR, os.path.join(home, ".local/state/llm-ctl/logs"))
            self.assertEqual(paths.CACHE_DIR, os.path.join(home, ".cache/llm-ctl"))

    def test_xdg_overrides(self):
        """Verifies that XDG_CONFIG_HOME, XDG_STATE_HOME, XDG_CACHE_HOME are respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_cfg = os.path.join(tmpdir, "custom_config")
            custom_state = os.path.join(tmpdir, "custom_state")
            custom_cache = os.path.join(tmpdir, "custom_cache")

            with patch.dict(os.environ, {
                "XDG_CONFIG_HOME": custom_cfg,
                "XDG_STATE_HOME": custom_state,
                "XDG_CACHE_HOME": custom_cache,
            }):
                importlib.reload(paths)

                self.assertEqual(paths.XDG_CONFIG_HOME, custom_cfg)
                self.assertEqual(paths.XDG_STATE_HOME, custom_state)
                self.assertEqual(paths.XDG_CACHE_HOME, custom_cache)

                self.assertEqual(paths.CONFIG_DIR, os.path.join(custom_cfg, "llm-ctl"))
                self.assertEqual(paths.CONFIG_FILE, os.path.join(custom_cfg, "llm-ctl", "config.json"))
                self.assertEqual(paths.STATE_DIR, os.path.join(custom_state, "llm-ctl"))
                self.assertEqual(paths.HISTORY_FILE, os.path.join(custom_state, "llm-ctl", "history"))
                self.assertEqual(paths.LOGS_DIR, os.path.join(custom_state, "llm-ctl", "logs"))
                self.assertEqual(paths.CACHE_DIR, os.path.join(custom_cache, "llm-ctl"))

    def test_ensure_directories_creation(self):
        """Verifies that ensure_directories() creates all required folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_dir = os.path.join(tmpdir, "config", "llm-ctl")
            s_dir = os.path.join(tmpdir, "state", "llm-ctl")
            l_dir = os.path.join(tmpdir, "state", "llm-ctl", "logs")
            ca_dir = os.path.join(tmpdir, "cache", "llm-ctl")
            h_file = os.path.join(s_dir, "history")

            with patch.object(paths, "CONFIG_DIR", c_dir), \
                 patch.object(paths, "STATE_DIR", s_dir), \
                 patch.object(paths, "LOGS_DIR", l_dir), \
                 patch.object(paths, "CACHE_DIR", ca_dir), \
                 patch.object(paths, "HISTORY_FILE", h_file):

                self.assertFalse(os.path.exists(c_dir))
                self.assertFalse(os.path.exists(s_dir))
                self.assertFalse(os.path.exists(l_dir))
                self.assertFalse(os.path.exists(ca_dir))

                paths.ensure_directories()

                self.assertTrue(os.path.isdir(c_dir))
                self.assertTrue(os.path.isdir(s_dir))
                self.assertTrue(os.path.isdir(l_dir))
                self.assertTrue(os.path.isdir(ca_dir))

    def test_ensure_directories_legacy_migration(self):
        """Verifies migration of legacy history from CONFIG_DIR/history to HISTORY_FILE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_dir = os.path.join(tmpdir, "config", "llm-ctl")
            s_dir = os.path.join(tmpdir, "state", "llm-ctl")
            l_dir = os.path.join(tmpdir, "state", "llm-ctl", "logs")
            ca_dir = os.path.join(tmpdir, "cache", "llm-ctl")
            h_file = os.path.join(s_dir, "history")

            os.makedirs(c_dir, exist_ok=True)
            legacy_file = os.path.join(c_dir, "history")
            with open(legacy_file, "w", encoding="utf-8") as f:
                f.write("legacy_command_1\nlegacy_command_2\n")

            with patch.object(paths, "CONFIG_DIR", c_dir), \
                 patch.object(paths, "STATE_DIR", s_dir), \
                 patch.object(paths, "LOGS_DIR", l_dir), \
                 patch.object(paths, "CACHE_DIR", ca_dir), \
                 patch.object(paths, "HISTORY_FILE", h_file):

                self.assertTrue(os.path.exists(legacy_file))
                self.assertFalse(os.path.exists(h_file))

                paths.ensure_directories()

                self.assertFalse(os.path.exists(legacy_file))
                self.assertTrue(os.path.exists(h_file))
                with open(h_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("legacy_command_1", content)

    def test_ensure_directories_migration_skipped_if_target_exists(self):
        """Verifies that legacy history is not moved if target HISTORY_FILE already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_dir = os.path.join(tmpdir, "config", "llm-ctl")
            s_dir = os.path.join(tmpdir, "state", "llm-ctl")
            l_dir = os.path.join(tmpdir, "state", "llm-ctl", "logs")
            ca_dir = os.path.join(tmpdir, "cache", "llm-ctl")
            h_file = os.path.join(s_dir, "history")

            os.makedirs(c_dir, exist_ok=True)
            os.makedirs(s_dir, exist_ok=True)
            legacy_file = os.path.join(c_dir, "history")
            with open(legacy_file, "w", encoding="utf-8") as f:
                f.write("old_data\n")
            with open(h_file, "w", encoding="utf-8") as f:
                f.write("new_data\n")

            with patch.object(paths, "CONFIG_DIR", c_dir), \
                 patch.object(paths, "STATE_DIR", s_dir), \
                 patch.object(paths, "LOGS_DIR", l_dir), \
                 patch.object(paths, "CACHE_DIR", ca_dir), \
                 patch.object(paths, "HISTORY_FILE", h_file):

                paths.ensure_directories()

                # Both should still exist, target remains untampered
                self.assertTrue(os.path.exists(legacy_file))
                self.assertTrue(os.path.exists(h_file))
                with open(h_file, "r", encoding="utf-8") as f:
                    self.assertEqual(f.read(), "new_data\n")

    def test_ensure_directories_handles_move_exception(self):
        """Verifies exception handling during legacy migration does not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            c_dir = os.path.join(tmpdir, "config", "llm-ctl")
            s_dir = os.path.join(tmpdir, "state", "llm-ctl")
            h_file = os.path.join(s_dir, "history")

            os.makedirs(c_dir, exist_ok=True)
            legacy_file = os.path.join(c_dir, "history")
            with open(legacy_file, "w", encoding="utf-8") as f:
                f.write("dummy\n")

            with patch.object(paths, "CONFIG_DIR", c_dir), \
                 patch.object(paths, "STATE_DIR", s_dir), \
                 patch.object(paths, "LOGS_DIR", os.path.join(s_dir, "logs")), \
                 patch.object(paths, "CACHE_DIR", os.path.join(tmpdir, "cache")), \
                 patch.object(paths, "HISTORY_FILE", h_file), \
                 patch("shutil.move", side_effect=OSError("Permission denied")):

                # Should not raise exception
                paths.ensure_directories()


class TestRuntime(unittest.TestCase):
    """Tests for Ollama server and model lifecycle management in runtime.py."""

    @patch("urllib.request.urlopen")
    def test_get_server_version(self, mock_urlopen):
        """Verifies server version extraction from REST endpoint."""
        # Success case
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"version": "0.5.1"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ver = runtime.get_server_version()
        self.assertEqual(ver, "0.5.1")

        # Failure / exception case
        mock_urlopen.side_effect = Exception("Connection refused")
        self.assertIsNone(runtime.get_server_version())

    @patch("llm_ctl.runtime.get_server_version")
    @patch("llm_ctl.runtime.get_service_status")
    def test_start_server_already_active(self, mock_status, mock_ver):
        """Verifies start_server() when server is already active."""
        mock_status.return_value = True
        mock_ver.return_value = "0.5.1"

        ok, msg = runtime.start_server()
        self.assertTrue(ok)
        self.assertIn("already active", msg)
        self.assertIn("v0.5.1", msg)

        # Without version string
        mock_ver.return_value = None
        ok, msg = runtime.start_server()
        self.assertTrue(ok)
        self.assertIn("already active", msg)

    @patch("time.sleep")
    @patch("llm_ctl.runtime.get_server_version")
    @patch("llm_ctl.runtime.get_service_status")
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_start_server_via_systemctl(self, mock_run, mock_which, mock_status, mock_ver, mock_sleep):
        """Verifies start_server() flow using systemctl user unit."""
        mock_which.side_effect = lambda cmd: "/bin/systemctl" if cmd == "systemctl" else None
        mock_status.side_effect = [False, True]
        mock_run.return_value = MagicMock(returncode=0)
        mock_ver.return_value = "0.5.2"

        ok, msg = runtime.start_server()
        self.assertTrue(ok)
        self.assertIn("Successfully started Ollama service via systemd", msg)
        self.assertIn("v0.5.2", msg)
        mock_run.assert_called_with(
            ["systemctl", "--user", "start", "ollama"],
            capture_output=True, text=True, timeout=5.0
        )

    @patch("time.sleep")
    @patch("llm_ctl.runtime.get_server_version")
    @patch("llm_ctl.runtime.get_service_status")
    @patch("shutil.which")
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_start_server_fallback_popen(self, mock_run, mock_popen, mock_which, mock_status, mock_ver, mock_sleep):
        """Verifies fallback to 'ollama serve' background process when systemctl fails."""
        # systemctl fails or is not present, ollama binary is present
        mock_which.side_effect = lambda cmd: "/usr/bin/ollama" if cmd == "ollama" else None
        mock_status.side_effect = [False, True]
        mock_ver.return_value = "0.5.3"

        ok, msg = runtime.start_server()
        self.assertTrue(ok)
        self.assertIn("Started Ollama daemon process", msg)
        self.assertIn("v0.5.3", msg)
        mock_popen.assert_called_once()

    @patch("llm_ctl.runtime.get_service_status")
    @patch("shutil.which")
    def test_start_server_no_ollama_failure(self, mock_which, mock_status):
        """Verifies start_server() failure when neither systemctl nor ollama is found."""
        mock_status.return_value = False
        mock_which.return_value = None

        ok, msg = runtime.start_server()
        self.assertFalse(ok)
        self.assertIn("Could not start Ollama", msg)

    @patch("time.sleep")
    @patch("llm_ctl.runtime.get_service_status")
    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_start_server_popen_exception(self, mock_popen, mock_which, mock_status, mock_sleep):
        """Verifies start_server() failure when subprocess.Popen throws an error."""
        mock_status.return_value = False
        mock_which.side_effect = lambda cmd: "/usr/bin/ollama" if cmd == "ollama" else None
        mock_popen.side_effect = OSError("Exec format error")

        ok, msg = runtime.start_server()
        self.assertFalse(ok)
        self.assertIn("Failed starting 'ollama serve'", msg)

    @patch("llm_ctl.runtime.get_service_status")
    def test_stop_server_already_offline(self, mock_status):
        """Verifies stop_server() when service is already offline."""
        mock_status.return_value = False

        ok, msg = runtime.stop_server()
        self.assertTrue(ok)
        self.assertIn("already stopped", msg)

    @patch("time.sleep")
    @patch("llm_ctl.runtime.unload_all_models")
    @patch("llm_ctl.runtime.get_service_status")
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_stop_server_via_systemctl(self, mock_run, mock_which, mock_status, mock_unload, mock_sleep):
        """Verifies stop_server() when systemctl stop succeeds."""
        mock_status.side_effect = [True, False, False]
        mock_which.side_effect = lambda cmd: "/bin/systemctl" if cmd == "systemctl" else None
        mock_run.return_value = MagicMock(returncode=0)

        ok, msg = runtime.stop_server()
        self.assertTrue(ok)
        self.assertIn("stopped successfully", msg)
        mock_unload.assert_called_once()
        mock_run.assert_called_with(
            ["systemctl", "--user", "stop", "ollama"],
            capture_output=True, text=True, timeout=5.0
        )

    @patch("time.sleep")
    @patch("llm_ctl.runtime.unload_all_models")
    @patch("llm_ctl.runtime.get_service_status")
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_stop_server_via_pkill_fallback(self, mock_run, mock_which, mock_status, mock_unload, mock_sleep):
        """Verifies stop_server() fallback to pkill when systemctl fails."""
        mock_status.side_effect = [True, True, False, False]
        mock_which.side_effect = lambda cmd: "/usr/bin/pkill" if cmd == "pkill" else None
        mock_run.return_value = MagicMock(returncode=0)

        ok, msg = runtime.stop_server()
        self.assertTrue(ok)
        self.assertIn("stopped successfully", msg)
        mock_run.assert_called_with(["pkill", "-f", "ollama serve"], capture_output=True, timeout=3.0)

    @patch("time.sleep")
    @patch("llm_ctl.runtime.unload_all_models")
    @patch("llm_ctl.runtime.get_service_status")
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_stop_server_failure(self, mock_run, mock_which, mock_status, mock_unload, mock_sleep):
        """Verifies stop_server() returns error when service fails to terminate."""
        mock_status.return_value = True  # Server remains active
        mock_which.side_effect = lambda cmd: "/bin/systemctl" if cmd == "systemctl" else "/bin/pkill"
        mock_run.return_value = MagicMock(returncode=1)

        ok, msg = runtime.stop_server()
        self.assertFalse(ok)
        self.assertIn("Failed to stop Ollama server gracefully", msg)

    @patch("time.sleep")
    @patch("llm_ctl.runtime.get_server_version")
    @patch("llm_ctl.runtime.get_service_status")
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_restart_server_systemctl(self, mock_run, mock_which, mock_status, mock_ver, mock_sleep):
        """Verifies restart_server() execution using systemctl."""
        mock_which.return_value = "/bin/systemctl"
        mock_run.return_value = MagicMock(returncode=0)
        mock_status.return_value = True
        mock_ver.return_value = "0.5.1"

        ok, msg = runtime.restart_server()
        self.assertTrue(ok)
        self.assertIn("restarted successfully", msg)
        self.assertIn("v0.5.1", msg)
        mock_run.assert_called_with(
            ["systemctl", "--user", "restart", "ollama"],
            capture_output=True, text=True, timeout=8.0
        )

    @patch("time.sleep")
    @patch("llm_ctl.runtime.start_server")
    @patch("llm_ctl.runtime.stop_server")
    @patch("shutil.which")
    def test_restart_server_fallback(self, mock_which, mock_stop, mock_start, mock_sleep):
        """Verifies restart_server() fallback to sequential stop and start."""
        mock_which.return_value = None  # No systemctl
        mock_stop.return_value = (True, "stopped")
        mock_start.return_value = (True, "started")

        ok, msg = runtime.restart_server()
        self.assertTrue(ok)
        self.assertIn("restarted successfully", msg)
        mock_stop.assert_called_once()
        mock_start.assert_called_once()

    @patch("time.sleep")
    @patch("llm_ctl.runtime.start_server")
    @patch("llm_ctl.runtime.stop_server")
    @patch("shutil.which")
    def test_restart_server_fallback_failure(self, mock_which, mock_stop, mock_start, mock_sleep):
        """Verifies restart_server() handles start failure in fallback sequence."""
        mock_which.return_value = None
        mock_stop.return_value = (True, "stopped")
        mock_start.return_value = (False, "port busy")

        ok, msg = runtime.restart_server()
        self.assertFalse(ok)
        self.assertIn("Failed restarting Ollama server: port busy", msg)

    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_model_service_offline(self, mock_status):
        """Verifies unload_model() fails if server is offline."""
        mock_status.return_value = False

        ok, msg = runtime.unload_model("qwen2.5-coder:3b")
        self.assertFalse(ok)
        self.assertIn("Ollama service is offline", msg)

    @patch("llm_ctl.runtime.get_loaded_models")
    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_model_not_loaded(self, mock_status, mock_loaded):
        """Verifies unload_model() succeeds early if model is not currently loaded."""
        mock_status.return_value = True
        mock_loaded.return_value = [{"name": "llama3.2:1b"}]

        ok, msg = runtime.unload_model("qwen2.5-coder:3b")
        self.assertTrue(ok)
        self.assertIn("not currently loaded in memory", msg)

    @patch("subprocess.run")
    @patch("llm_ctl.runtime.get_loaded_models")
    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_model_loaded_cli_success(self, mock_status, mock_loaded, mock_run):
        """Verifies unload_model() succeeds via 'ollama stop'."""
        mock_status.return_value = True
        mock_loaded.return_value = [{"name": "qwen2.5-coder:3b"}]
        mock_run.return_value = MagicMock(returncode=0)

        ok, msg = runtime.unload_model("qwen2.5-coder:3b")
        self.assertTrue(ok)
        self.assertIn("Successfully unloaded 'qwen2.5-coder:3b'", msg)
        mock_run.assert_called_with(
            ["ollama", "stop", "qwen2.5-coder:3b"],
            capture_output=True, text=True, timeout=5.0
        )

    @patch("subprocess.run")
    @patch("llm_ctl.runtime.get_loaded_models")
    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_model_prefix_match(self, mock_status, mock_loaded, mock_run):
        """Verifies unload_model() matches prefix to full model tag."""
        mock_status.return_value = True
        mock_loaded.return_value = [{"name": "qwen2.5-coder:3b"}]
        mock_run.return_value = MagicMock(returncode=0)

        ok, msg = runtime.unload_model("qwen2.5-coder")
        self.assertTrue(ok)
        self.assertIn("Successfully unloaded 'qwen2.5-coder:3b'", msg)

    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    @patch("llm_ctl.runtime.get_loaded_models")
    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_model_api_fallback(self, mock_status, mock_loaded, mock_run, mock_urlopen):
        """Verifies unload_model() falls back to API keep_alive=0 when CLI stop fails."""
        mock_status.return_value = True
        mock_loaded.return_value = [{"name": "qwen2.5-coder:3b"}]
        mock_run.return_value = MagicMock(returncode=1)

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, msg = runtime.unload_model("qwen2.5-coder:3b")
        self.assertTrue(ok)
        self.assertIn("Successfully unloaded 'qwen2.5-coder:3b' from memory via API", msg)

    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    @patch("llm_ctl.runtime.get_loaded_models")
    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_model_both_fail(self, mock_status, mock_loaded, mock_run, mock_urlopen):
        """Verifies unload_model() returns failure when both CLI and API fail."""
        mock_status.return_value = True
        mock_loaded.return_value = [{"name": "qwen2.5-coder:3b"}]
        mock_run.return_value = MagicMock(returncode=1)
        mock_urlopen.side_effect = Exception("HTTP 500")

        ok, msg = runtime.unload_model("qwen2.5-coder:3b")
        self.assertFalse(ok)
        self.assertIn("Failed unloading model", msg)

    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_all_models_offline(self, mock_status):
        """Verifies unload_all_models() returns empty list when offline."""
        mock_status.return_value = False
        evicted = runtime.unload_all_models()
        self.assertEqual(evicted, [])

    @patch("llm_ctl.runtime.get_loaded_models")
    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_all_models_none_loaded(self, mock_status, mock_loaded):
        """Verifies unload_all_models() when no models are in VRAM."""
        mock_status.return_value = True
        mock_loaded.return_value = []
        evicted = runtime.unload_all_models()
        self.assertEqual(evicted, [])

    @patch("subprocess.run")
    @patch("llm_ctl.runtime.get_loaded_models")
    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_all_models_with_loaded(self, mock_status, mock_loaded, mock_run):
        """Verifies unload_all_models() evicts each model in VRAM."""
        mock_status.return_value = True
        mock_loaded.return_value = [
            {"name": "qwen2.5-coder:3b"},
            {"name": "deepseek-coder:1.3b"}
        ]
        mock_run.return_value = MagicMock(returncode=0)

        evicted = runtime.unload_all_models()
        self.assertEqual(evicted, ["qwen2.5-coder:3b", "deepseek-coder:1.3b"])
        self.assertEqual(mock_run.call_count, 2)

    @patch("subprocess.run")
    @patch("llm_ctl.runtime.get_loaded_models")
    @patch("llm_ctl.runtime.get_service_status")
    def test_unload_all_models_partial_error(self, mock_status, mock_loaded, mock_run):
        """Verifies unload_all_models() continues even if one model throws error."""
        mock_status.return_value = True
        mock_loaded.return_value = [
            {"name": "model-1"},
            {"name": "model-2"}
        ]
        mock_run.side_effect = [Exception("error"), MagicMock(returncode=0)]

        evicted = runtime.unload_all_models()
        self.assertEqual(evicted, ["model-2"])

    @patch("shutil.which")
    def test_remove_model_no_ollama(self, mock_which):
        """Verifies remove_model() fails if ollama binary is missing."""
        mock_which.return_value = None

        ok, msg = runtime.remove_model("test-model")
        self.assertFalse(ok)
        self.assertIn("Ollama executable not found", msg)

    @patch("llm_ctl.runtime.unload_model")
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_remove_model_success(self, mock_which, mock_run, mock_unload):
        """Verifies remove_model() successfully invokes 'ollama rm' after unloading."""
        mock_which.return_value = "/usr/bin/ollama"
        mock_unload.return_value = (True, "unloaded")
        mock_run.return_value = MagicMock(returncode=0)

        ok, msg = runtime.remove_model("qwen2.5-coder:3b")
        self.assertTrue(ok)
        self.assertIn("Permanently removed model 'qwen2.5-coder:3b'", msg)
        mock_unload.assert_called_with("qwen2.5-coder:3b")
        mock_run.assert_called_with(
            ["ollama", "rm", "qwen2.5-coder:3b"],
            capture_output=True, text=True, timeout=10.0
        )

    @patch("llm_ctl.runtime.unload_model")
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_remove_model_failure(self, mock_which, mock_run, mock_unload):
        """Verifies remove_model() handles failure and returns stderr."""
        mock_which.return_value = "/usr/bin/ollama"
        mock_unload.return_value = (True, "unloaded")
        mock_run.return_value = MagicMock(returncode=1, stderr="Error: model not found")

        ok, msg = runtime.remove_model("invalid-model")
        self.assertFalse(ok)
        self.assertIn("Error: model not found", msg)

    @patch("llm_ctl.runtime.unload_model")
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_remove_model_exception(self, mock_which, mock_run, mock_unload):
        """Verifies remove_model() catches unexpected exceptions safely."""
        mock_which.return_value = "/usr/bin/ollama"
        mock_unload.return_value = (True, "unloaded")
        mock_run.side_effect = OSError("IO Error")

        ok, msg = runtime.remove_model("qwen2.5-coder:3b")
        self.assertFalse(ok)
        self.assertIn("Error executing model deletion", msg)


class TestScriptsAndCompletions(unittest.TestCase):
    """Tests for installation scripts and shell completions."""

    def test_install_scripts_syntax(self):
        """Verifies syntax of scripts/install.sh, scripts/uninstall.sh, and install.sh via bash -n."""
        scripts = [
            os.path.join(REPO_ROOT, "scripts", "install.sh"),
            os.path.join(REPO_ROOT, "scripts", "uninstall.sh"),
            os.path.join(REPO_ROOT, "install.sh")
        ]
        for script in scripts:
            self.assertTrue(os.path.isfile(script), f"Script {script} not found")
            res = subprocess.run(["bash", "-n", script], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Syntax error in {script}: {res.stderr}")

    def test_script_safety_flags(self):
        """Verifies that install and uninstall scripts use set -euo pipefail."""
        for name in ["install.sh", "uninstall.sh"]:
            path = os.path.join(REPO_ROOT, "scripts", name)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("set -euo pipefail", content, f"{name} is missing 'set -euo pipefail'")

    def test_uninstall_purge_safety(self):
        """Verifies uninstall script preserves user configuration by default."""
        uninstall_path = os.path.join(REPO_ROOT, "scripts", "uninstall.sh")
        with open(uninstall_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("PURGE_USER_DATA=false", content)
        self.assertIn("--purge", content)
        self.assertIn("Preserved user configuration", content)

    def test_completion_files_syntax(self):
        """Verifies syntax for bash, zsh, and fish completion files."""
        bash_comp = os.path.join(REPO_ROOT, "completions", "llm.bash")
        zsh_comp = os.path.join(REPO_ROOT, "completions", "llm.zsh")
        fish_comp = os.path.join(REPO_ROOT, "completions", "llm.fish")

        # bash -n
        res_bash = subprocess.run(["bash", "-n", bash_comp], capture_output=True, text=True)
        self.assertEqual(res_bash.returncode, 0, f"Bash completion syntax error: {res_bash.stderr}")

        # zsh -n
        if shutil.which("zsh"):
            res_zsh = subprocess.run(["zsh", "-n", zsh_comp], capture_output=True, text=True)
            self.assertEqual(res_zsh.returncode, 0, f"Zsh completion syntax error: {res_zsh.stderr}")

        # fish -n
        if shutil.which("fish"):
            res_fish = subprocess.run(["fish", "-n", fish_comp], capture_output=True, text=True)
            self.assertEqual(res_fish.returncode, 0, f"Fish completion syntax error: {res_fish.stderr}")

    def test_completion_commands_coverage(self):
        """
        Verifies that bash, zsh, and fish completions include all required commands,
        aliases, and support both 'llm' and 'llm-ctl'.
        """
        required_commands = [
            "status", "models", "ls", "switch", "use", "pull", "chat",
            "start", "run", "stop", "restart", "unload", "free",
            "remove", "rm", "delete", "agents", "pi", "doctor", "config", "help"
        ]

        # Check completions/llm.bash
        bash_path = os.path.join(REPO_ROOT, "completions", "llm.bash")
        with open(bash_path, "r", encoding="utf-8") as f:
            bash_content = f.read()
        for cmd in required_commands:
            self.assertIn(cmd, bash_content, f"Bash completion missing '{cmd}'")
        self.assertIn("complete -F _llm_completion llm", bash_content)
        self.assertIn("complete -F _llm_completion llm-ctl", bash_content)

        # Check completions/llm.zsh
        zsh_path = os.path.join(REPO_ROOT, "completions", "llm.zsh")
        with open(zsh_path, "r", encoding="utf-8") as f:
            zsh_content = f.read()
        for cmd in required_commands:
            self.assertIn(f"'{cmd}:", zsh_content, f"Zsh completion missing '{cmd}'")
        self.assertIn("#compdef llm llm-ctl", zsh_content)

        # Check completions/llm.fish
        fish_path = os.path.join(REPO_ROOT, "completions", "llm.fish")
        with open(fish_path, "r", encoding="utf-8") as f:
            fish_content = f.read()
        for cmd in required_commands:
            self.assertIn(f"-a {cmd}", fish_content, f"Fish completion missing '{cmd}'")
        self.assertIn("for cmd in llm llm-ctl", fish_content)


if __name__ == "__main__":
    unittest.main()
