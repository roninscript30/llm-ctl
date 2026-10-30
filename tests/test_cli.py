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
from llm_ctl.banner import render_gauge_bar

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

    def test_gauge_bar_rendering(self):
        gauge = render_gauge_bar(2048.0, 4096.0, width=10)
        self.assertIn("50.0%", gauge)

    @patch("llm_ctl.orchestrator.CONFIG_FILE", "/tmp/test_llm_ctl_config.json")
    def test_active_model_persistence(self):
        save_active_model("test-model:latest")
        self.assertEqual(get_active_model(), "test-model:latest")

if __name__ == "__main__":
    unittest.main()
