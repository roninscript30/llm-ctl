"""
Unit and integration tests for llm-ctl.
"""

import sys
import os
import unittest
from unittest.mock import patch

# Ensure src/ is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from llm_ctl.hub import get_vram_badge, HUB_MODELS
from llm_ctl.orchestrator import get_active_model, save_active_model
from llm_ctl.banner import (
    visible_len, ansi_ljust,
    render_reference_banner,
    render_reference_status_card,
    render_reference_quick_commands
)

class TestLlmCtl(unittest.TestCase):

    def test_hub_vram_badge(self):
        badge_green = get_vram_badge(1400, 4096.0)
        self.assertIn("100% GPU", badge_green)

        badge_yellow = get_vram_badge(4600, 4096.0)
        self.assertIn("Hybrid", badge_yellow)

        badge_red = get_vram_badge(6000, 4096.0)
        self.assertIn("Heavy", badge_red)

    def test_hub_catalog_structure(self):
        self.assertGreater(len(HUB_MODELS), 5)
        for m in HUB_MODELS:
            self.assertIn("id", m)
            self.assertIn("size_gb", m)
            self.assertIn("est_vram_mb", m)
            self.assertIn("category", m)

    def test_status_card_rendering(self):
        card = render_reference_status_card(
            True, "http://127.0.0.1:11434",
            {"used_mb": 2.0, "total_mb": 4096.0},
            {"used_gb": 4.1, "total_gb": 7.1},
            "qwen2.5-coder:3b"
        )
        self.assertIn("Ollama: Connected", card)
        self.assertIn("qwen2.5-coder:3b", card)
        self.assertIn("[READY]", card)

        # Check all lines fit comfortably within standard terminal width (<= 85 chars)
        lines = card.splitlines()
        for l in lines:
            self.assertLessEqual(visible_len(l), 85)

    def test_status_card_in_vram_and_fallback(self):
        # Test in VRAM badge
        card_vram = render_reference_status_card(
            True, "http://127.0.0.1:11434",
            None,
            {"used_gb": 4.0, "total_gb": 8.0},
            "qwen2.5-coder:3b",
            loaded_models=[{"name": "qwen2.5-coder:3b"}]
        )
        self.assertIn("[IN VRAM]", card_vram)
        self.assertIn("No GPU detected", card_vram)
        self.assertIn("CPU fallback", card_vram)

        # Test long model name clamp
        long_model = "deepseek-r1:32b-q4_k_m-extra-long-name-here"
        card_long = render_reference_status_card(
            True, "http://127.0.0.1:11434",
            None,
            {"used_gb": 4.0, "total_gb": 8.0},
            long_model
        )
        lines = card_long.splitlines()
        for l in lines:
            self.assertLessEqual(visible_len(l), 120)

    def test_banner_and_quick_commands(self):
        banner = render_reference_banner()
        self.assertIn("LOCAL MODEL CONTROL", banner)
        self.assertIn("Manage · Switch · Run · Integrate · Your Local Models", banner)
        # Ensure side cube connector wires were removed
        self.assertNotIn("─── Ollama", banner)
        self.assertNotIn("─── Local Models", banner)

        cmds = render_reference_quick_commands()
        for cmd in ["models", "switch", "chat", "pull", "unload", "remove", "start", "stop", "restart", "status", "doctor", "help"]:
            self.assertIn(cmd, cmds)

    def test_ansi_ljust_and_visible_len(self):
        raw = "\033[96mHello \033[1;92mWorld\033[0m"
        self.assertEqual(visible_len(raw), 11)
        padded = ansi_ljust(raw, 20)
        self.assertEqual(visible_len(padded), 20)
        clamped = ansi_ljust(raw, 5)
        self.assertEqual(visible_len(clamped), 5)

    @patch("llm_ctl.orchestrator.CONFIG_FILE", "/tmp/test_llm_ctl_config.json")
    def test_active_model_persistence(self):
        save_active_model("test-model:latest")
        self.assertEqual(get_active_model(), "test-model:latest")

    def test_doctor_diagnostics(self):
        from llm_ctl.doctor import check_gpu, check_ram, check_config_file, check_coding_agents
        gpu_ok, gpu_msg, _ = check_gpu()
        self.assertIsInstance(gpu_ok, bool)
        self.assertIsInstance(gpu_msg, str)

        ram_ok, ram_msg, _ = check_ram()
        self.assertIsInstance(ram_ok, bool)
        self.assertIn("GiB", ram_msg)

        agents = check_coding_agents()
        self.assertEqual(len(agents), 3)

    def test_interactive_completer(self):
        from llm_ctl.interactive import Completer
        completer = Completer(["models", "switch", "chat", "doctor", "help"])
        # Test command prefix
        self.assertEqual(completer.complete("do", 0), "doctor")
        self.assertEqual(completer.complete("sw", 0), "switch")
        self.assertEqual(completer.complete("nonexistent", 0), None)

if __name__ == "__main__":
    unittest.main()
