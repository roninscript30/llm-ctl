# LLM-CTL Documentation Assets & Images

This directory stores visual assets and screenshots referenced in the `llm-ctl` documentation and repository `README.md`.

## Expected Visual Assets

### `llm-ctl-terminal.png`
* **Purpose**: Primary terminal preview displaying the interactive TUI / dashboard and real-time telemetry card.
* **Referenced in**: `README.md` under the *Terminal Preview* section.
* **Content captured**:
  - The live ASCII logo banner (`LLM-CTL`).
  - Active model indicator and model status badge (`◈ [ACTIVE]`, `★ [IN VRAM]`, or `[READY]`).
  - Real-time hardware telemetry: Ollama service connection state, NVIDIA GPU VRAM gauge with temperature and power metrics, and Linux system RAM usage.
  - Interactive quick-command keys (`[s] Switch`, `[p] Pull`, `[u] Unload`, `[c] Chat`, `[d] Doctor`, `[a] Agents`, `[q] Quit`).
* **Recommended capture settings**:
  - Font: SpaceMono Regular (or monospace developer font).
  - Terminal size: Standard 80–90 columns by 24–30 rows.
  - Color palette: Truecolor dark theme matching the ANSI styling (bright cyan, green, yellow, red, white).
  - Recommended resolution: 1600 × 900 or 1920 × 1080 (lossless PNG).

> **Note for Contributors**: Do not commit mock or low-resolution generated images. Capture live terminal screenshots using Linux utilities such as `flameshot`, `gnome-screenshot`, or terminal recorder tools like `vhs`.
