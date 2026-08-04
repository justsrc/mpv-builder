#!/usr/bin/env bash
set -euo pipefail

if ! cargo cinstall --help >/dev/null 2>&1; then
  cargo install cargo-c --locked
fi

cache_dir="${CACHE_DIR:-$HOME/.cache/mpv-builder}"
source_root="$cache_dir/dovi_tool"
upstream_sha="$(git ls-remote https://github.com/quietvoid/dovi_tool.git HEAD | awk 'NR == 1 { print $1 }')"

if [[ -z "$upstream_sha" ]]; then
  echo "Could not resolve the dovi_tool revision" >&2
  exit 1
fi

if [[ ! -d "$source_root/.git" ]] || [[ "$(git -C "$source_root" rev-parse HEAD)" != "$upstream_sha" ]]; then
  rm -rf "$source_root"
  mkdir -p "$cache_dir"
  git clone --depth=1 https://github.com/quietvoid/dovi_tool.git "$source_root"
fi

pushd "$source_root/dolby_vision" >/dev/null
# The cache preserves Cargo downloads and this source tree, but /opt/homebrew is
# fresh on every hosted runner, so libdovi must still be installed each time.
cargo cinstall --release --prefix /opt/homebrew
popd >/dev/null
