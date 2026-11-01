#!/usr/bin/env bash
# ==============================================================================
# LLM-CTL — Linux Installation Script
# Supported: curl -fsSL https://raw.githubusercontent.com/roninscript30/llm-ctl/main/scripts/install.sh | bash
# Or locally: ./install.sh / bash scripts/install.sh
# ==============================================================================
set -euo pipefail

REPO="${LLM_CTL_REPO:-roninscript30/llm-ctl}"
REPO_URL="${LLM_CTL_REPO_URL:-https://github.com/${REPO}.git}"
BRANCH="${LLM_CTL_BRANCH:-main}"
BIN_DIR="${LLM_CTL_BIN_DIR:-${HOME}/.local/bin}"

# ANSI color codes
BOLD="\033[1m"
GREEN="\033[1;32m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

log_info() {
  printf "${CYAN}==>${RESET} ${BOLD}%s${RESET}\n" "$1"
}

log_success() {
  printf "${GREEN}==>${RESET} ${BOLD}%s${RESET}\n" "$1"
}

log_warn() {
  printf "${YELLOW}Warning:${RESET} %s\n" "$1"
}

log_err() {
  printf "${RED}Error:${RESET} %s\n" "$1" >&2
}

# 1. Platform & Architecture Check
OS="$(uname -s)"
ARCH="$(uname -m)"

if [[ "$OS" != "Linux" ]]; then
  log_err "LLM-CTL currently targets Linux only (detected: $OS)."
  exit 1
fi

case "$ARCH" in
  x86_64|amd64)
    ARCH_TARGET="x86_64"
    ;;
  aarch64|arm64)
    ARCH_TARGET="aarch64"
    ;;
  *)
    log_warn "Architecture '$ARCH' not officially pre-packaged; will compile from source."
    ARCH_TARGET="$ARCH"
    ;;
esac

log_info "Installing LLM-CTL for Linux (${ARCH_TARGET})..."

# 2. Check if running from an existing repository checkout
LOCAL_SRC=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "${SCRIPT_DIR}/../Cargo.toml" ]]; then
    LOCAL_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
  elif [[ -f "${SCRIPT_DIR}/Cargo.toml" ]]; then
    LOCAL_SRC="${SCRIPT_DIR}"
  fi
fi

# 3. Strategy: Try Release Binary First, Fallback to Source Build
try_prebuilt_binary() {
  # If user explicitly requested source build or we are in a local checkout, skip
  if [[ "${LLM_CTL_BUILD_FROM_SOURCE:-0}" == "1" || -n "${LOCAL_SRC}" ]]; then
    return 1
  fi

  local tarball="llm-ctl-linux-${ARCH_TARGET}.tar.gz"
  local release_url="${LLM_CTL_RELEASE_URL:-https://github.com/${REPO}/releases/latest/download/${tarball}}"
  local tmp_dir
  tmp_dir="$(mktemp -d -t llm-ctl-install-XXXXXX)"

  log_info "Checking for pre-compiled release binary..."
  if curl --connect-timeout 3 --max-time 30 -fsSL -o "${tmp_dir}/${tarball}" "${release_url}" 2>/dev/null; then
    log_info "Found pre-compiled binary. Extracting..."
    if tar -xzf "${tmp_dir}/${tarball}" -C "${tmp_dir}" 2>/dev/null && [[ -f "${tmp_dir}/llm" ]]; then
      mkdir -p "${BIN_DIR}"
      install -m 0755 "${tmp_dir}/llm" "${BIN_DIR}/llm"
      ln -sfn "${BIN_DIR}/llm" "${BIN_DIR}/llm-ctl"
      rm -rf "${tmp_dir}"
      return 0
    fi
  fi
  rm -rf "${tmp_dir}"
  return 1
}

build_from_source() {
  # Ensure Cargo & Rust are in PATH
  if [[ -f "${HOME}/.cargo/env" ]]; then
    # shellcheck source=/dev/null
    . "${HOME}/.cargo/env"
  elif [[ -d "${HOME}/.cargo/bin" ]]; then
    export PATH="${HOME}/.cargo/bin:${PATH}"
  fi

  if ! command -v cargo >/dev/null 2>&1; then
    log_err "Rust and Cargo are required to compile LLM-CTL from source."
    printf "Install stable Rust with:\n" >&2
    printf "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh\n" >&2
    exit 1
  fi

  local src_dir="${LOCAL_SRC}"
  if [[ -z "${src_dir}" || ! -f "${src_dir}/Cargo.toml" ]]; then
    src_dir="${HOME}/.local/share/llm-ctl"
    mkdir -p "$(dirname "${src_dir}")"
    if [[ -d "${src_dir}/.git" ]]; then
      log_info "Updating repository in ${src_dir}..."
      git -C "${src_dir}" pull --quiet || true
    else
      log_info "Cloning ${REPO_URL} into ${src_dir}..."
      if ! git clone --depth 1 -b "${BRANCH}" "${REPO_URL}" "${src_dir}" 2>/dev/null; then
        git clone --depth 1 "${REPO_URL}" "${src_dir}" || {
          log_err "Failed to clone repository from ${REPO_URL}."
          exit 1
        }
      fi
    fi
  fi

  log_info "Building optimized release binary with Cargo..."
  cargo build --release --manifest-path "${src_dir}/Cargo.toml"

  mkdir -p "${BIN_DIR}"
  install -m 0755 "${src_dir}/target/release/llm" "${BIN_DIR}/llm"
  ln -sfn "${BIN_DIR}/llm" "${BIN_DIR}/llm-ctl"

  # Install shell completions if available
  local comp_dir="${src_dir}/completions"
  if [[ -d "${comp_dir}" ]]; then
    local bash_comp_dest="${HOME}/.local/share/bash-completion/completions"
    mkdir -p "${bash_comp_dest}" 2>/dev/null || true
    cp -f "${comp_dir}/llm.bash" "${bash_comp_dest}/llm" 2>/dev/null || true
  fi
}

if try_prebuilt_binary; then
  log_success "Installed pre-built binary directly."
else
  log_info "Compiling from source via Cargo..."
  build_from_source
fi

# 4. Audit & Verification
if [[ -x "${BIN_DIR}/llm" && -x "${BIN_DIR}/llm-ctl" ]]; then
  VERSION="$("${BIN_DIR}/llm" --version 2>/dev/null || echo "llm 2.0.0")"
  log_success "LLM-CTL (${VERSION}) installed successfully to ${BIN_DIR}!"

  if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
    printf "\n"
    log_warn "${BIN_DIR} is not currently in your PATH."
    printf "Add it to your shell configuration file (~/.bashrc or ~/.zshrc):\n"
    printf "  ${CYAN}export PATH=\"%s:\$PATH\"${RESET}\n\n" "${BIN_DIR}"
  fi

  printf "\nQuick start:\n"
  printf "  ${BOLD}llm${RESET}         Interactive control dashboard\n"
  printf "  ${BOLD}llm status${RESET}  Hardware & runtime telemetry\n"
  printf "  ${BOLD}llm doctor${RESET}  Diagnose setup & coding agents\n"
  printf "  ${BOLD}llm help${RESET}    List all commands\n\n"
else
  log_err "Installation failed: executable not found at ${BIN_DIR}/llm"
  exit 1
fi
