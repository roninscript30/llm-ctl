#!/usr/bin/env bash
# LLM-CTL root installation wrapper
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/scripts/install.sh" "$@"
