#!/usr/bin/env bash
set -euo pipefail

# Reuse the preconfigured Rust toolchain and Cargo cache when nothing changed.
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"

# The workflow caches this directory via actions/cache so reruns can reuse Cargo and libdovi artifacts.
cache_dir="${CACHE_DIR:-$HOME/.cache/mpv-builder}"
mkdir -p "$cache_dir"
state_file="$cache_dir/libdovi.state"

# Keep the current versions of the dependency sources for a quick decision.
current_key="$(rustc --version 2>/dev/null || echo rust-unknown)"
current_key+="|$(cargo --version 2>/dev/null || echo cargo-unknown)"
current_key+="|$(git ls-remote https://github.com/quietvoid/dovi_tool.git HEAD 2>/dev/null | awk '{print $1}' || echo dovi-unknown)"

if [[ ! -f "$state_file" ]] || [[ "$(cat "$state_file" 2>/dev/null || true)" != "$current_key" ]]; then
  if ! cargo cinstall --help >/dev/null 2>&1; then
    cargo install cargo-c --locked
  fi

  rm -rf "$cache_dir/dovi_tool"
  git clone --depth=1 https://github.com/quietvoid/dovi_tool.git "$cache_dir/dovi_tool"
  pushd "$cache_dir/dovi_tool/dolby_vision" >/dev/null
  cargo cinstall --release --prefix /opt/homebrew
  popd >/dev/null

  printf '%s\n' "$current_key" > "$state_file"
else
  echo "libdovi and cargo-c are already up to date for the current state; skipping rebuild"
fi
