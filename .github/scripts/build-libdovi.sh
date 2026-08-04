#!/usr/bin/env bash
set -euo pipefail

# Install the Rust toolchain once, then keep the cargo-c and libdovi setup in one place.
rustup toolchain install stable --profile minimal
rustup default stable

if ! cargo cinstall --help >/dev/null 2>&1; then
  cargo install cargo-c --locked
fi

# Build the libdovi C library that mpv links against.
rm -rf dovi_tool
git clone --depth=1 https://github.com/quietvoid/dovi_tool.git
pushd dovi_tool/dolby_vision >/dev/null
cargo cinstall --release --prefix /opt/homebrew
popd >/dev/null
