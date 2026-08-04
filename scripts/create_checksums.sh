#!/usr/bin/env bash
set -euo pipefail

bundle_path="${BUNDLE_PATH:?BUNDLE_PATH is required}"
archive_path="${ARCHIVE_PATH:?ARCHIVE_PATH is required}"
checksums_path="${CHECKSUMS_PATH:?CHECKSUMS_PATH is required}"
metadata_path="${METADATA_PATH:?METADATA_PATH is required}"
source_date_epoch="${SOURCE_DATE_EPOCH:?SOURCE_DATE_EPOCH is required}"

archive_timestamp="$(date -u -r "$source_date_epoch" +%Y%m%d%H%M.%S)"
find "$bundle_path" -depth -exec touch -h -t "$archive_timestamp" {} +
COPYFILE_DISABLE=1 ditto -c -k --keepParent "$bundle_path" "$archive_path"

archive_name="$(basename "$archive_path")"
sha256="$(shasum -a 256 "$archive_path" | awk '{print $1}')"
printf '%s  %s\n' "$sha256" "$archive_name" > "$checksums_path"

finished_epoch="$(date +%s)"
duration_seconds="$((finished_epoch - BUILD_STARTED_EPOCH))"
artifact_size_bytes="$(stat -f %z "$archive_path")"
export archive_name sha256 duration_seconds artifact_size_bytes finished_epoch

python3 - "$metadata_path" <<'PY'
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime

compiler = subprocess.run(["clang", "--version"], check=True, capture_output=True, text=True)
metadata = {
    "artifact": os.environ["archive_name"],
    "artifact_size_bytes": int(os.environ["artifact_size_bytes"]),
    "architecture": platform.machine(),
    "build_finished_at": datetime.fromtimestamp(int(os.environ["finished_epoch"]), UTC).isoformat(),
    "build_started_at": os.environ["BUILD_STARTED_AT"],
    "build_duration_seconds": int(os.environ["duration_seconds"]),
    "compiler": compiler.stdout.splitlines()[0],
    "github_actions_run_url": os.environ["GITHUB_RUN_URL"],
    "libdovi_sha": os.environ["LIBDOVI_SHA"],
    "macos_version": subprocess.run(["sw_vers", "-productVersion"], check=True, capture_output=True, text=True).stdout.strip(),
    "mpv_build_sha": os.environ["MPV_BUILD_SHA"],
    "mpv_sha": os.environ["MPV_SHA"],
    "sha256": os.environ["sha256"],
    "source_date_epoch": int(os.environ["SOURCE_DATE_EPOCH"]),
    "workflow_number": os.environ["GITHUB_RUN_NUMBER"],
}
with open(sys.argv[1], "w", encoding="utf-8") as output:
    json.dump(metadata, output, indent=2, sort_keys=True)
    output.write("\n")
PY

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    printf 'archive_path=%s\n' "$archive_path"
    printf 'checksums_path=%s\n' "$checksums_path"
    printf 'metadata_path=%s\n' "$metadata_path"
    printf 'sha256=%s\n' "$sha256"
    printf 'duration_seconds=%s\n' "$duration_seconds"
    printf 'artifact_size_bytes=%s\n' "$artifact_size_bytes"
  } >> "$GITHUB_OUTPUT"
fi
