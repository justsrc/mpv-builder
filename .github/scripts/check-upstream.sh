#!/usr/bin/env bash
set -euo pipefail

mpv_sha="$(git ls-remote https://github.com/mpv-player/mpv.git HEAD | awk 'NR == 1 { print $1 }')"
mpv_build_sha="$(git ls-remote https://github.com/mpv-player/mpv-build.git HEAD | awk 'NR == 1 { print $1 }')"

if [[ -z "$mpv_sha" || -z "$mpv_build_sha" ]]; then
  echo "Could not resolve an upstream revision" >&2
  exit 1
fi

build_stamp="$(date -u +'%Y.%m.%d-%H%M')"
nightly_title="mpv-nightly-v${build_stamp} UTC"
should_build=true

if previous_body="$(gh release view nightly --json body --jq '.body' 2>/dev/null)"; then
  previous_mpv_sha="$(printf '%s\n' "$previous_body" | awk '$1 == "mpv:" { print $2; exit }' | tr -d '\r`')"
  previous_mpv_build_sha="$(printf '%s\n' "$previous_body" | awk '$1 == "mpv-build:" { print $2; exit }' | tr -d '\r`')"

  if [[ "$previous_mpv_sha" == "$mpv_sha" && "$previous_mpv_build_sha" == "$mpv_build_sha" ]]; then
    should_build=false
  fi
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    printf 'should_build=%s\n' "$should_build"
    printf 'mpv_sha=%s\n' "$mpv_sha"
    printf 'mpv_build_sha=%s\n' "$mpv_build_sha"
    printf 'previous_mpv_sha=%s\n' "${previous_mpv_sha:-}"
    printf 'previous_mpv_build_sha=%s\n' "${previous_mpv_build_sha:-}"
    printf 'nightly_title=%s\n' "$nightly_title"
    printf 'build_stamp=%s\n' "$build_stamp"
  } >> "$GITHUB_OUTPUT"
fi

printf 'should_build=%s\n' "$should_build"
printf 'mpv_sha=%s\n' "$mpv_sha"
printf 'mpv_build_sha=%s\n' "$mpv_build_sha"
