#!/usr/bin/env bash
set -euo pipefail

if ! cargo cinstall --help >/dev/null 2>&1; then
  cargo install cargo-c --locked
fi

source_root="${RUNNER_TEMP:-$PWD}/dovi_tool"
git clone --depth=1 https://github.com/quietvoid/dovi_tool.git "$source_root"

pushd "$source_root/dolby_vision" >/dev/null
cargo cinstall --release --prefix /opt/homebrew
popd >/dev/null
