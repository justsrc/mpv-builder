#!/usr/bin/env bash
set -euo pipefail

notes_path="${1:-${RELEASE_NOTES_PATH:-}}"
if [[ -z "$notes_path" ]]; then
  echo "An output path is required" >&2
  exit 1
fi

release_tag="${RELEASE_TAG:-nightly}"
release_title="${RELEASE_TITLE:-$release_tag}"
mpv_sha="${MPV_SHA:-unknown}"
mpv_build_sha="${MPV_BUILD_SHA:-unknown}"
previous_mpv_sha="${PREVIOUS_MPV_SHA:-}"
previous_mpv_build_sha="${PREVIOUS_MPV_BUILD_SHA:-}"
build_stamp="${BUILD_STAMP:-$(date -u +'%Y.%m.%d-%H%M UTC')}"
repository="${GITHUB_REPOSITORY:-Justin24506/mpv-builder}"
build_time="$(date -u +'%Y-%m-%d %H:%M:%S UTC')"

cat > "$notes_path" <<NOTES
## ${release_title}

Tag: ${release_tag}
Build stamp: ${build_stamp}
Built: ${build_time}
Repository: ${repository}

mpv: ${mpv_sha}
mpv-build: ${mpv_build_sha}

## Assets

- ZIP archive
- SHA256 checksum
NOTES

append_compare_section() {
  local upstream_repository="$1"
  local previous_sha="$2"
  local current_sha="$3"

  if [[ -z "$previous_sha" || -z "$current_sha" || "$previous_sha" == "$current_sha" ]]; then
    return
  fi

  {
    printf '\n## %s upstream changes\n\n' "$upstream_repository"
    printf 'Compare: [%s](https://github.com/%s/compare/%s...%s)\n\n' \
      "$previous_sha...$current_sha" "$upstream_repository" "$previous_sha" "$current_sha"
    gh api "repos/${upstream_repository}/compare/${previous_sha}...${current_sha}" --jq '
      .commits[]
      | "- [" + (.sha[0:7]) + "](https://github.com/'"$upstream_repository"'/commit/" + .sha + ") " + (.commit.message | split("\n")[0])
    '
  } >> "$notes_path"
}

append_compare_section "mpv-player/mpv" "$previous_mpv_sha" "$mpv_sha"
append_compare_section "mpv-player/mpv-build" "$previous_mpv_build_sha" "$mpv_build_sha"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'release_notes_path=%s\n' "$notes_path" >> "$GITHUB_OUTPUT"
fi
