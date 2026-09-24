#!/usr/bin/env python3
"""Update a Homebrew cask from a published GitHub release asset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol, TypedDict, cast
from urllib.parse import quote

CASK_TEMPLATE = Path(__file__).with_name("cask.rb.template")


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
    return subprocess.run(
        command, check=True, cwd=cwd, env=env, capture_output=True, text=True
    ).stdout.strip()


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


def generate_cask_content(
    cask_token: str,
    version: str,
    checksum: str,
    archive_url: str,
    description: str,
    repo: str,
    is_nightly: bool,
) -> str:
    """Generate RuboCop-compliant Cask file content."""
    sha256_stanza = "sha256 :no_check" if is_nightly else f'sha256 "{checksum}"'

    return CASK_TEMPLATE.read_text(encoding="utf-8").format(
        cask_token=cask_token,
        version=version,
        sha256_stanza=sha256_stanza,
        archive_url=archive_url,
        description=description,
        repo=repo,
    )


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

    tap_repo = os.getenv("TAP_REPO") or "Justin24506/homebrew-tap"
    archive_url = release_asset_url(args_typed.release_tag)
    checksum, metadata = verified_release_assets(args_typed.release_tag, args_typed.sha256)

    is_nightly: bool = args_typed.cask == "nightly"

    if is_nightly:
        cask_path = Path("Casks/mpv@nightly.rb")
        cask_token = "mpv@nightly"
        description = "Media player (nightly build)"
        workflow_number = metadata["workflow_number"]
        version = f"nightly-{workflow_number}"
        commit_subject = "Nightly cask update"
    else:
        cask_path = Path("Casks/mpv.rb")
        cask_token = "mpv"
        description = "Media player"
        version = args_typed.release_tag.removeprefix("v")
        commit_subject = f"Update mpv cask to {args_typed.release_tag}"

    github_repo = os.environ["GITHUB_REPOSITORY"]
    cask_content = generate_cask_content(
        cask_token, version, checksum, archive_url, description, github_repo, is_nightly
    )

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
        cask_file.parent.mkdir(parents=True, exist_ok=True)
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
        pr_url = run(
            [
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
            ],
            cwd=tap_directory,
            env=clone_env,
        )

    write_output("tap_pr_url", pr_url)
    print(f"tap_pr_url={pr_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
