"""
Comprehensive tests for telemetry, hardware inspection, and orchestration.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from llm_ctl.hardware import (
    get_service_status,
    get_gpu_stats,
    get_system_ram,
    get_loaded_models,
    get_installed_models,
)
from llm_ctl.orchestrator import (
    get_model_status,
    resolve_model_target,
    switch_model,
    free_vram,
    sync_claude_code,
    sync_opencode,
    sync_dsh,
    save_active_model,
    get_active_model,
)

class TestHardwareTelemetry(unittest.TestCase):

    @patch("llm_ctl.hardware.urllib.request.urlopen")
    def test_get_service_status_rest_ok(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        self.assertTrue(get_service_status())

    @patch("llm_ctl.hardware.urllib.request.urlopen", side_effect=Exception("Connection refused"))
    @patch("llm_ctl.hardware.subprocess.run")
    def test_get_service_status_systemctl_fallback(self, mock_run, mock_urlopen):
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")
        self.assertTrue(get_service_status())

    @patch("llm_ctl.hardware.urllib.request.urlopen", side_effect=Exception("Connection refused"))
    @patch("llm_ctl.hardware.subprocess.run", side_effect=Exception("Failed"))
    def test_get_service_status_offline(self, mock_run, mock_urlopen):
        self.assertFalse(get_service_status())

    @patch("llm_ctl.hardware.shutil.which", return_value="/usr/bin/nvidia-smi")
    @patch("llm_ctl.hardware.subprocess.run")
    def test_get_gpu_stats_success(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NVIDIA GeForce RTX 3050 Laptop GPU, 1024, 4096, 0, 52, 12.50\n"
        )
        stats = get_gpu_stats()
        self.assertIsNotNone(stats)
        self.assertEqual(stats["name"], "NVIDIA GeForce RTX 3050 Laptop GPU")
        self.assertEqual(stats["used_mb"], 1024.0)
        self.assertEqual(stats["total_mb"], 4096.0)
        self.assertEqual(stats["util_pct"], 0.0)
        self.assertEqual(stats["temp_c"], "52")
        self.assertEqual(stats["power_w"], "12.50")

    @patch("llm_ctl.hardware.shutil.which", return_value=None)
    def test_get_gpu_stats_no_nvidia_smi(self, mock_which):
        self.assertIsNone(get_gpu_stats())

    @patch("llm_ctl.hardware.shutil.which", return_value="/usr/bin/nvidia-smi")
    @patch("llm_ctl.hardware.subprocess.run")
    def test_get_gpu_stats_command_failure(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        self.assertIsNone(get_gpu_stats())

    @patch("os.path.exists", return_value=True)
    def test_get_system_ram_calculation(self, mock_exists):
        fake_meminfo = (
            "MemTotal:        8388608 kB\n"
            "MemFree:         1048576 kB\n"
            "MemAvailable:    4194304 kB\n"
        )
        with patch("builtins.open", unittest.mock.mock_open(read_data=fake_meminfo)):
            ram = get_system_ram()
            self.assertEqual(ram["total_gb"], 8.0)
            self.assertEqual(ram["free_gb"], 4.0)
            self.assertEqual(ram["used_gb"], 4.0)
            self.assertEqual(ram["pct"], 50.0)

    @patch("os.path.exists", return_value=False)
    def test_get_system_ram_missing_file(self, mock_exists):
        ram = get_system_ram()
        self.assertEqual(ram["total_gb"], 0.0)
        self.assertEqual(ram["used_gb"], 0.0)
        self.assertEqual(ram["pct"], 0.0)

    @patch("llm_ctl.hardware.urllib.request.urlopen")
    def test_get_loaded_models_api(self, mock_urlopen):
        raw_json = json.dumps({
            "models": [
                {
                    "name": "qwen2.5-coder:3b",
                    "size": 2000000000,
                    "size_vram": 2000000000,
                    "details": {"format": "gguf"}
                }
            ]
        }).encode()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = raw_json
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        loaded = get_loaded_models()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["name"], "qwen2.5-coder:3b")
        self.assertEqual(loaded[0]["size"], 2000000000)
        self.assertEqual(loaded[0]["size_vram"], 2000000000)
        self.assertEqual(loaded[0]["processor"], "100% GPU")

    @patch("llm_ctl.hardware.urllib.request.urlopen", side_effect=Exception("API down"))
    @patch("llm_ctl.hardware.subprocess.run")
    def test_get_loaded_models_fallback_subprocess(self, mock_run, mock_urlopen):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NAME    ID    SIZE    PROCESSOR    CONTEXT    UNTIL\ndeepseek-r1:1.5b  abc  1.1 GB  100% GPU  4096  4 min\n"
        )
        loaded = get_loaded_models()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["name"], "deepseek-r1:1.5b")
        self.assertEqual(loaded[0]["processor"], "100% GPU")

class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        self.sample_installed = [
            {"name": "deepseek-r1:7b", "size": 4683075440},
            {"name": "deepseek-r1:1.5b", "size": 1117322768},
            {"name": "qwen2.5-coder:3b", "size": 1929912626},
        ]

    def test_resolve_model_target(self):
        # Index matching (1-based)
        self.assertEqual(resolve_model_target("1", self.sample_installed), "deepseek-r1:7b")
        self.assertEqual(resolve_model_target("3", self.sample_installed), "qwen2.5-coder:3b")
        self.assertIsNone(resolve_model_target("99", self.sample_installed))

        # Full match
        self.assertEqual(resolve_model_target("qwen2.5-coder:3b", self.sample_installed), "qwen2.5-coder:3b")

        # Name before tag
        self.assertEqual(resolve_model_target("qwen2.5-coder", self.sample_installed), "qwen2.5-coder:3b")

        # Tag match
        self.assertEqual(resolve_model_target("1.5b", self.sample_installed), "deepseek-r1:1.5b")
        self.assertEqual(resolve_model_target(":1.5b", self.sample_installed), "deepseek-r1:1.5b")

        # Prefix
        self.assertEqual(resolve_model_target("deepseek", self.sample_installed), "deepseek-r1:7b")

        # Substring
        self.assertEqual(resolve_model_target("coder", self.sample_installed), "qwen2.5-coder:3b")

        # Not found
        self.assertIsNone(resolve_model_target("llama3:8b", self.sample_installed))

    @patch("llm_ctl.orchestrator.get_loaded_models")
    @patch("llm_ctl.orchestrator.get_installed_models")
    def test_get_model_status(self, mock_installed, mock_loaded):
        mock_loaded.return_value = [{"name": "qwen2.5-coder:3b"}]
        mock_installed.return_value = [
            {"name": "deepseek-r1:1.5b"},
            {"name": "qwen2.5-coder:3b"}
        ]

        self.assertEqual(get_model_status("qwen2.5-coder:3b"), "IN_VRAM")
        self.assertEqual(get_model_status("qwen2.5-coder"), "IN_VRAM")
        self.assertEqual(get_model_status("deepseek-r1:1.5b"), "STANDBY")
        self.assertEqual(get_model_status("deepseek-r1"), "STANDBY")
        self.assertEqual(get_model_status("phi3:mini"), "NOT_INSTALLED")

    @patch("llm_ctl.orchestrator.get_service_status", return_value=False)
    def test_switch_model_offline(self, mock_status):
        result = switch_model("qwen2.5-coder:3b", quiet=True)
        self.assertFalse(result)

    @patch("llm_ctl.orchestrator.get_service_status", return_value=True)
    @patch("llm_ctl.orchestrator.get_installed_models")
    def test_switch_model_not_installed(self, mock_installed, mock_status):
        mock_installed.return_value = self.sample_installed
        result = switch_model("llama3:latest", quiet=True)
        self.assertFalse(result)

    @patch("llm_ctl.orchestrator.get_service_status", return_value=True)
    @patch("llm_ctl.orchestrator.get_installed_models")
    @patch("llm_ctl.orchestrator.get_loaded_models")
    @patch("llm_ctl.orchestrator.save_active_model")
    @patch("llm_ctl.orchestrator.sync_all_configs")
    @patch("llm_ctl.orchestrator.urllib.request.urlopen")
    @patch("llm_ctl.orchestrator.subprocess.run")
    def test_switch_model_success(self, mock_run, mock_urlopen, mock_sync, mock_save, mock_loaded, mock_installed, mock_status):
        mock_installed.return_value = self.sample_installed
        mock_loaded.return_value = [{"name": "deepseek-r1:1.5b"}]

        result = switch_model("3", quiet=True)
        self.assertTrue(result)
        mock_save.assert_called_with("qwen2.5-coder:3b")
        mock_sync.assert_called_with("qwen2.5-coder:3b")

    @patch("llm_ctl.orchestrator.get_loaded_models")
    @patch("llm_ctl.orchestrator.subprocess.run")
    def test_free_vram(self, mock_run, mock_loaded):
        mock_loaded.side_effect = [
            [{"name": "deepseek-r1:1.5b"}, {"name": "qwen2.5-coder:3b"}],
            [] # after clearance
        ]
        evicted = free_vram()
        self.assertEqual(len(evicted), 2)
        self.assertIn("deepseek-r1:1.5b", evicted)
        self.assertIn("qwen2.5-coder:3b", evicted)

    def test_config_sync_safe_writes(self):
        test_dir = "/tmp/llm_ctl_test_sync"
        claude_path = os.path.join(test_dir, ".claude", "settings.json")
        opencode_path = os.path.join(test_dir, ".config", "opencode", "opencode.jsonc")

        with patch("os.path.expanduser", side_effect=lambda p: p.replace("~/.claude/settings.json", claude_path).replace("~/.config/opencode/opencode.jsonc", opencode_path)):
            # Sync claude
            res_c = sync_claude_code("qwen2.5-coder:3b")
            self.assertTrue(res_c)
            self.assertTrue(os.path.exists(claude_path))
            with open(claude_path) as f:
                c_data = json.load(f)
                self.assertEqual(c_data["model"], "qwen2.5-coder:3b")
                self.assertEqual(c_data["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"], "qwen2.5-coder:3b")

            # Sync opencode
            res_o = sync_opencode("qwen2.5-coder:3b")
            self.assertTrue(res_o)
            self.assertTrue(os.path.exists(opencode_path))
            with open(opencode_path) as f:
                o_data = json.load(f)
                self.assertEqual(o_data["model"], "ollama/qwen2.5-coder:3b")

if __name__ == "__main__":
    unittest.main()
