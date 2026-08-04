#!/usr/bin/env bash
set -euo pipefail

# Resolve the current upstream heads for the two repositories this project tracks.
mpv_sha="$(git ls-remote https://github.com/mpv-player/mpv.git HEAD | awk '{print $1}')"
mpv_build_sha="$(git ls-remote https://github.com/mpv-player/mpv-build.git HEAD | awk '{print $1}')"
build_stamp="$(date -u +'%Y.%m.%d-%H%M')"
nightly_title="mpv-nightly-v${build_stamp} UTC"

# Default to rebuilding when there is no previous nightly release or the notes are malformed.
should_build=true

# Read the last nightly release body so we can skip work when nothing upstream changed.
previous_body=""
if previous_body="$(gh release view nightly --json body --jq '.body' 2>/dev/null)"; then
  previous_mpv_sha="$(printf '%s\n' "$previous_body" | awk '$1 == "mpv:" {print $2; exit}' | tr -d '\r`')"
  previous_mpv_build_sha="$(printf '%s\n' "$previous_body" | awk '$1 == "mpv-build:" {print $2; exit}' | tr -d '\r`')"

  if [[ "$previous_mpv_sha" == "$mpv_sha" && "$previous_mpv_build_sha" == "$mpv_build_sha" ]]; then
    should_build=false
  fi
fi

# Publish outputs for the workflow graph.
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

printf 'mpv_sha=%s\n' "$mpv_sha"
printf 'mpv_build_sha=%s\n' "$mpv_build_sha"
printf 'previous_mpv_sha=%s\n' "${previous_mpv_sha:-}"
printf 'previous_mpv_build_sha=%s\n' "${previous_mpv_build_sha:-}"
printf 'nightly_title=%s\n' "$nightly_title"
printf 'build_stamp=%s\n' "$build_stamp"
printf 'should_build=%s\n' "$should_build"
