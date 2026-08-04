#!/usr/bin/env python3
"""Resolve upstream revisions and decide whether the rolling nightly is stale."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime


UPSTREAMS = {
    "mpv": "https://github.com/mpv-player/mpv.git",
    "mpv_build": "https://github.com/mpv-player/mpv-build.git",
    "libdovi": "https://github.com/quietvoid/dovi_tool.git",
    "cargo_c": "https://github.com/lu-zero/cargo-c.git",
}


def head_sha(repository: str) -> str:
    result = subprocess.run(
        ["git", "ls-remote", repository, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    sha = result.stdout.split("\t", maxsplit=1)[0].strip()
    if not sha:
        raise RuntimeError(f"Could not resolve {repository}")
    return sha


def previous_nightly_body() -> str:
    result = subprocess.run(
        ["gh", "release", "view", "nightly", "--json", "body", "--jq", ".body"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else ""


def recorded_sha(body: str, name: str) -> str:
    match = re.search(rf"^\s*(?:[-*]\s+)?{re.escape(name)} SHA:\s*([0-9a-f]+)\s*$", body, re.MULTILINE)
    return match.group(1) if match else ""


def write_outputs(outputs: dict[str, str]) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            for key, value in outputs.items():
                output.write(f"{key}={value}\n")


def main() -> int:
    try:
        with ThreadPoolExecutor(max_workers=len(UPSTREAMS)) as executor:
            revisions = {name: executor.submit(head_sha, url) for name, url in UPSTREAMS.items()}
            current = {name: revision.result() for name, revision in revisions.items()}
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        return 1

    body = previous_nightly_body()
    previous_mpv = recorded_sha(body, "mpv")
    previous_mpv_build = recorded_sha(body, "mpv-build")
    changed = current["mpv"] != previous_mpv or current["mpv_build"] != previous_mpv_build
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    outputs = {
        "should_build": str(changed).lower(),
        "mpv_sha": current["mpv"],
        "mpv_build_sha": current["mpv_build"],
        "libdovi_sha": current["libdovi"],
        "cargo_c_sha": current["cargo_c"],
        "previous_mpv_sha": previous_mpv,
        "previous_mpv_build_sha": previous_mpv_build,
        "checked_at": timestamp,
    }
    write_outputs(outputs)
    for key, value in outputs.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
