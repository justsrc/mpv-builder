#!/usr/bin/env bash
set -euo pipefail

notes_path="${1:-${RELEASE_NOTES_PATH:-}}"
if [[ -z "$notes_path" ]]; then
  echo "release-notes.sh requires an output path" >&2
  exit 1
fi

release_kind="${RELEASE_KIND:-nightly}"
release_tag="${RELEASE_TAG:-$release_kind}"
release_title="${RELEASE_TITLE:-$release_tag}"
mpv_sha="${MPV_SHA:-unknown}"
mpv_build_sha="${MPV_BUILD_SHA:-unknown}"
previous_mpv_sha="${PREVIOUS_MPV_SHA:-}"
previous_mpv_build_sha="${PREVIOUS_MPV_BUILD_SHA:-}"
build_stamp="${BUILD_STAMP:-$(date -u +'%Y.%m.%d-%H%M UTC')}"
workflow_name="${GITHUB_WORKFLOW:-unknown workflow}"
run_id="${GITHUB_RUN_ID:-unknown}"
run_attempt="${GITHUB_RUN_ATTEMPT:-unknown}"
repository="${GITHUB_REPOSITORY:-Justin24506/mpv-builder}"
build_time="$(date -u +'%Y-%m-%d %H:%M:%S UTC')"

# Keep the release notes human-readable while leaving the SHAs easy to parse later.
cat > "$notes_path" <<EOF
## ${release_title}

Tag: ${release_tag}
Build stamp: ${build_stamp}
Built: ${build_time}
Workflow: ${workflow_name} #${run_id}.${run_attempt}
Repository: ${repository}

mpv: ${mpv_sha}
mpv-build: ${mpv_build_sha}

## Assets

- ZIP archive
- SHA256 checksum
EOF

append_compare_section() {
  local repo_name="$1"
  local previous_sha="$2"
  local current_sha="$3"

  if [[ -z "$previous_sha" || -z "$current_sha" || "$previous_sha" == "$current_sha" ]]; then
    return 0
  fi

  local compare_url="https://github.com/${repo_name}/compare/${previous_sha}...${current_sha}"
  {
    printf '\n## %s upstream changes\n\n' "$repo_name"
    printf 'Compare: [%s](%s)\n\n' "$previous_sha...$current_sha" "$compare_url"
    gh api "repos/${repo_name}/compare/${previous_sha}...${current_sha}" --jq '
      .commits[]
      | "- [" + (.sha[0:7]) + "](https://github.com/'"${repo_name}"'/commit/" + .sha + ") " + (.commit.message | split("\n")[0])
    '
  } >> "$notes_path"
}

append_compare_section "mpv-player/mpv" "$previous_mpv_sha" "$mpv_sha"
append_compare_section "mpv-player/mpv-build" "$previous_mpv_build_sha" "$mpv_build_sha"

# Return the notes path to workflow steps that want to reuse it.
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'release_notes_path=%s\n' "$notes_path" >> "$GITHUB_OUTPUT"
fi

printf 'release_notes_path=%s\n' "$notes_path"
