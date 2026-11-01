#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/roninscript30/llm-ctl.git"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"

if [[ -f "${HOME}/.cargo/env" ]]; then
  # shellcheck source=/dev/null
  . "${HOME}/.cargo/env"
elif [[ -d "${HOME}/.cargo/bin" ]]; then
  export PATH="${HOME}/.cargo/bin:${PATH}"
fi

if ! command -v cargo >/dev/null 2>&1; then
  printf 'Rust and Cargo are required. Install stable Rust with https://rustup.rs/\n' >&2
  exit 1
fi

if [[ ! -f "${SOURCE_DIR}/Cargo.toml" ]]; then
  SOURCE_DIR="${HOME}/.local/share/llm-ctl"
  if [[ ! -d "${SOURCE_DIR}/.git" ]]; then
    mkdir -p "$(dirname "${SOURCE_DIR}")"
    git clone --depth 1 "${REPO_URL}" "${SOURCE_DIR}"
  fi
fi

printf 'Building LLM-CTL from %s\n' "${SOURCE_DIR}"
cargo build --release --manifest-path "${SOURCE_DIR}/Cargo.toml"
mkdir -p "${BIN_DIR}"
install -m 0755 "${SOURCE_DIR}/target/release/llm" "${BIN_DIR}/llm"
ln -sfn "${BIN_DIR}/llm" "${BIN_DIR}/llm-ctl"

printf 'Installed llm and llm-ctl in %s\n' "${BIN_DIR}"
if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
  printf 'Add this to your shell profile: export PATH="$HOME/.local/bin:$PATH"\n'
fi
