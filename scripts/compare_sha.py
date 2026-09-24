#!/usr/bin/env python3
"""Print a compact Markdown changelog between two GitHub revisions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Protocol, TypedDict, cast


class _CommitInner(TypedDict):
    message: str


class _Commit(TypedDict):
    sha: str
    commit: _CommitInner


class _CompareResponse(TypedDict):
    commits: list[_Commit]


class _CompareArgs(Protocol):
    repository: str
    previous: str
    current: str


def compare(repository: str, previous: str, current: str) -> str:
    if not previous or previous == current:
        return ""

    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/compare/{previous}...{current}"],
        check=True,
        capture_output=True,
        text=True,
    )
    raw_data = cast(_CompareResponse, json.loads(result.stdout))
    commits: list[_Commit] = raw_data.get("commits", [])
    return "\n".join(
        f"- [{commit['sha'][:7]}](https://github.com/{repository}/commit/{commit['sha']}) {commit['commit']['message'].splitlines()[0]}"
        for commit in commits
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("repository")
    _ = parser.add_argument("previous")
    _ = parser.add_argument("current")
    args = parser.parse_args()
    args_typed = cast(_CompareArgs, cast(object, args))

    try:
        print(compare(args_typed.repository, args_typed.previous, args_typed.current))
    except subprocess.CalledProcessError as error:
        err = cast(str | None, cast(object, error.stderr))
        if err is not None:
            print(err, file=sys.stderr, end="")
        return error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
