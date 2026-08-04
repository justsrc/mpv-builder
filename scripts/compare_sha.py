#!/usr/bin/env python3
"""Print a compact Markdown changelog between two GitHub revisions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def compare(repository: str, previous: str, current: str) -> str:
    if not previous or previous == current:
        return ""

    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/compare/{previous}...{current}"],
        check=True,
        capture_output=True,
        text=True,
    )
    commits = json.loads(result.stdout).get("commits", [])
    return "\n".join(
        f"- [{commit['sha'][:7]}](https://github.com/{repository}/commit/{commit['sha']}) "
        f"{commit['commit']['message'].splitlines()[0]}"
        for commit in commits
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("previous")
    parser.add_argument("current")
    args = parser.parse_args()

    try:
        print(compare(args.repository, args.previous, args.current))
    except subprocess.CalledProcessError as error:
        print(error.stderr, file=sys.stderr, end="")
        return error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
