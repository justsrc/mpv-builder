#!/usr/bin/env python3
"""Create release notes from build metadata and upstream commit comparisons."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Protocol, TypedDict, cast


class _BuildMetadata(TypedDict):
    mpv_sha: str
    mpv_build_sha: str
    libdovi_sha: str
    cargo_c_sha: str
    build_finished_at: str
    workflow_number: str | int
    github_actions_run_url: str
    build_duration_seconds: str | int
    artifact: str
    sha256: str


class _ReleaseNotesArgs(Protocol):
    metadata: Path
    output: Path
    title: str
    previous_mpv: str
    previous_mpv_build: str
    custom_notes: str


def changelog(repository: str, previous: str, current: str) -> str:
    if not previous or previous == current:
        return "No changes recorded."

    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("compare_sha.py")), repository, previous, current],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "No commits returned by GitHub."


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--metadata", required=True, type=Path)
    _ = parser.add_argument("--output", required=True, type=Path)
    _ = parser.add_argument("--title", required=True)
    _ = parser.add_argument("--previous-mpv", default="")
    _ = parser.add_argument("--previous-mpv-build", default="")
    _ = parser.add_argument("--custom-notes", default="")
    args = parser.parse_args()
    args_typed = cast(_ReleaseNotesArgs, cast(object, args))

    metadata_text: str = args_typed.metadata.read_text(encoding="utf-8")
    metadata: _BuildMetadata = cast(_BuildMetadata, json.loads(metadata_text))
    try:
        mpv_changes = changelog("mpv-player/mpv", args_typed.previous_mpv, metadata["mpv_sha"])
        mpv_build_changes = changelog(
            "mpv-player/mpv-build", args_typed.previous_mpv_build, metadata["mpv_build_sha"]
        )
    except subprocess.CalledProcessError as error:
        err = cast(str | None, cast(object, error.stderr))
        if err is not None:
            print(err, file=sys.stderr, end="")
        return error.returncode

    notes = f"""## {args_typed.title}

- Build timestamp: {metadata['build_finished_at']}
- Workflow number: {metadata['workflow_number']}
- GitHub Actions run: {metadata['github_actions_run_url']}
- Build duration: {metadata['build_duration_seconds']} seconds
- mpv SHA: {metadata['mpv_sha']}
- mpv-build SHA: {metadata['mpv_build_sha']}
- libdovi SHA: {metadata['libdovi_sha']}
- cargo-c SHA: {metadata['cargo_c_sha']}
- SHA256 (`{metadata['artifact']}`): `{metadata['sha256']}`

## mpv upstream changes

{mpv_changes}

## mpv-build upstream changes

{mpv_build_changes}
"""
    if args_typed.custom_notes.strip():
        notes += f"\n## Release notes\n\n{args_typed.custom_notes.strip()}\n"
    _ = args_typed.output.write_text(notes, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
