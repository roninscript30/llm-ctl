#!/usr/bin/env bash
# llm-ctl local installation script
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$BIN_DIR"

echo "Installing llm-ctl to $BIN_DIR..."

cat << EOF > "$BIN_DIR/llm"
#!/usr/bin/env python3
import sys
import os

# Add package source to path
sys.path.insert(0, "$REPO_DIR/src")
from llm_ctl.cli import main

if __name__ == "__main__":
    main()
EOF

chmod +x "$BIN_DIR/llm"
ln -sf "$BIN_DIR/llm" "$BIN_DIR/llm-ctl"

echo "✔ Successfully installed 'llm' and 'llm-ctl' to $BIN_DIR"
echo "Run 'llm' for the interactive terminal dashboard or 'llm --help' for CLI commands."
