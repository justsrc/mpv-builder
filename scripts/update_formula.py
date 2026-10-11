#!/usr/bin/env python3
"""Update a Homebrew cask from a published GitHub release asset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol, TypedDict, cast
from urllib.parse import quote

VERSION_STANZA = re.compile(r'^([ \t]*)version[ \t]+["\'][^"\']*["\'].*$', re.MULTILINE)
SHA256_STANZA = re.compile(
    r'^([ \t]*)sha256[ \t]+(?::no_check|["\'][^"\']*["\']).*$', re.MULTILINE
)


class _Asset(TypedDict):
    name: str
    browser_download_url: str


class _ReleaseData(TypedDict):
    assets: list[_Asset]


class _BuildMetadata(TypedDict):
    workflow_number: str | int


class _UpdateFormulaArgs(Protocol):
    release_tag: str
    cask: str
    sha256: str | None
    mpv_sha: str
    mpv_build_sha: str


def run(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> str:
    result = subprocess.run(
        command, check=False, cwd=cwd, env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, flush=True)
        raise subprocess.CalledProcessError(
            result.returncode, command, output=result.stdout, stderr=result.stderr
        )
    return result.stdout.strip()


def release_asset_url(release_tag: str) -> str:
    release_data = cast(_ReleaseData, json.loads(run(
            [
                "gh",
                "api",
                f"repos/{os.environ['GITHUB_REPOSITORY']}/releases/tags/{release_tag}",
            ]
        )))
    assets: list[_Asset] = release_data.get("assets", [])
    for asset in assets:
        if asset.get("name") == "mpv-macos-arm64.zip":
            return asset["browser_download_url"]
    raise RuntimeError(f"mpv-macos-arm64.zip is missing from release {release_tag}")


def verified_release_assets(
    release_tag: str, expected_checksum: str | None
) -> tuple[str, _BuildMetadata]:
    with tempfile.TemporaryDirectory() as directory:
        _ = run(
            [
                "gh",
                "release",
                "download",
                release_tag,
                "--pattern",
                "SHA256SUMS.txt",
                "--dir",
                directory,
            ]
        )
        _ = run(
            [
                "gh",
                "release",
                "download",
                release_tag,
                "--pattern",
                "mpv-macos-arm64.zip",
                "--dir",
                directory,
            ]
        )
        _ = run(
            [
                "gh",
                "release",
                "download",
                release_tag,
                "--pattern",
                "build-metadata.json",
                "--dir",
                directory,
            ]
        )
        checksum_file = Path(directory, "SHA256SUMS.txt")
        recorded_checksum = checksum_file.read_text(encoding="utf-8").split()[0]
        checksum = expected_checksum or recorded_checksum
        if checksum != recorded_checksum:
            raise RuntimeError("The supplied SHA256 does not match SHA256SUMS.txt")

        digest = hashlib.sha256()
        with Path(directory, "mpv-macos-arm64.zip").open("rb") as archive:
            for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != checksum:
            raise RuntimeError(
                "Downloaded mpv-macos-arm64.zip failed SHA256 verification"
            )
        metadata_text = Path(directory, "build-metadata.json").read_text(encoding="utf-8")
        metadata = cast(_BuildMetadata, json.loads(metadata_text))
        return checksum, metadata


def write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            _ = output.write(f"{name}={value}\n")


def update_cask_content(cask_content: str, version: str, checksum: str, is_nightly: bool) -> str:
    """Rewrite only the `version` and `sha256` stanzas of an existing cask.

    The rest of the file is left byte for byte alone so hand edits to the tap,
    such as a zap stanza that needs `brew generate-zap` to discover, survive
    later updates.
    """
    sha256_stanza = "sha256 :no_check" if is_nightly else f'sha256 "{checksum}"'

    updated, version_count = VERSION_STANZA.subn(
        lambda match: f'{match.group(1)}version "{version}"', cask_content, count=1
    )
    if version_count == 0:
        raise RuntimeError("The cask has no version stanza to update")

    updated, sha256_count = SHA256_STANZA.subn(
        lambda match: f"{match.group(1)}{sha256_stanza}", updated, count=1
    )
    if sha256_count == 0:
        raise RuntimeError("The cask has no sha256 stanza to update")

    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--release-tag", required=True)
    _ = parser.add_argument("--cask", choices=("nightly", "release"), required=True)
    _ = parser.add_argument("--sha256")
    _ = parser.add_argument("--mpv-sha", default="")
    _ = parser.add_argument("--mpv-build-sha", default="")
    args = parser.parse_args()
    args_typed = cast(_UpdateFormulaArgs, cast(object, args))

    token = os.getenv("HOMEBREW_TAP_TOKEN")
    if not token:
        print("HOMEBREW_TAP_TOKEN is not configured; skipping Homebrew update.")
        return 0

    tap_repo = os.getenv("TAP_REPO") or "justsrc/homebrew-tap"
    _ = release_asset_url(args_typed.release_tag)
    checksum, metadata = verified_release_assets(args_typed.release_tag, args_typed.sha256)

    is_nightly: bool = args_typed.cask == "nightly"

    if is_nightly:
        cask_path = Path("Casks/mpv@nightly.rb")
        cask_token = "mpv@nightly"
        workflow_number = metadata["workflow_number"]
        version = f"nightly-{workflow_number}"
        commit_subject = f"{cask_token} {version}"
    else:
        cask_path = Path("Casks/mpv.rb")
        cask_token = "mpv"
        version = args_typed.release_tag.removeprefix("v")
        commit_subject = f"{cask_token} {version}"

    with tempfile.TemporaryDirectory() as directory:
        tap_directory = Path(directory, "tap")
        clone_env = os.environ | {"GH_TOKEN": token}
        _ = run(["gh", "repo", "clone", tap_repo, str(tap_directory)], env=clone_env)
        _ = run(
            [
                "git",
                "remote",
                "set-url",
                "origin",
                f"https://x-access-token:{quote(token)}@github.com/{tap_repo}.git",
            ],
            cwd=tap_directory,
        )
        cask_file = tap_directory / cask_path
        # The tap owns the cask. Only the version and sha256 stanzas are
        # rewritten, so anything hand written there survives later runs. A
        # missing cask has to be created in the tap, not regenerated here,
        # because there is no template to regenerate from.
        if not cask_file.exists():
            raise RuntimeError(
                f"{cask_path} does not exist in {tap_repo}; add the cask to the tap first"
            )
        cask_content = update_cask_content(
            cask_file.read_text(encoding="utf-8"), version, checksum, is_nightly
        )
        _ = cask_file.write_text(cask_content, encoding="utf-8")

        _ = run(["git", "add", str(cask_path)], cwd=tap_directory)

        changed = (
            subprocess.run(
                ["git", "diff", "--cached", "--quiet"], cwd=tap_directory
            ).returncode
            != 0
        )
        if not changed:
            print("Homebrew cask already matches the release.")
            return 0

        base_branch = run(
            [
                "gh",
                "repo",
                "view",
                tap_repo,
                "--json",
                "defaultBranchRef",
                "--jq",
                ".defaultBranchRef.name",
            ],
            env=clone_env,
        )
        branch_name = f"cask/{version}"
        _ = run(["git", "switch", "-c", branch_name], cwd=tap_directory)
        _ = run(["git", "config", "user.name", "github-actions[bot]"], cwd=tap_directory)
        _ = run(
            [
                "git",
                "config",
                "user.email",
                "github-actions[bot]@users.noreply.github.com",
            ],
            cwd=tap_directory,
        )
        message = ["git", "commit", "-m", commit_subject]
        build_info = ""
        if args_typed.mpv_sha and args_typed.mpv_build_sha:
            build_info = (
                f"Upstream revisions:\n\nmpv: {args_typed.mpv_sha}\n"
                f"mpv-build: {args_typed.mpv_build_sha}"
            )
            message.extend(["-m", build_info])
        _ = run(message, cwd=tap_directory)
        _ = run(["git", "push", "-u", "origin", branch_name], cwd=tap_directory)

        pr_body = build_info or f"Update the `{cask_token}` cask to `{version}`."
        pr_args = [
            "gh",
            "pr",
            "create",
            "--repo",
            tap_repo,
            "--base",
            base_branch,
            "--head",
            branch_name,
            "--title",
            commit_subject,
            "--body",
            pr_body,
        ]
        try:
            pr_url = run(pr_args, cwd=tap_directory, env=clone_env)
        except subprocess.CalledProcessError:
            existing_pr = run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    tap_repo,
                    "--head",
                    branch_name,
                    "--state",
                    "open",
                    "--json",
                    "url",
                    "--jq",
                    ".[0].url // empty",
                ],
                cwd=tap_directory,
                env=clone_env,
            )
            if not existing_pr:
                raise
            pr_url = existing_pr

    write_output("tap_pr_url", pr_url)
    print(f"tap_pr_url={pr_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
