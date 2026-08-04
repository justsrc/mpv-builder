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
from urllib.parse import quote


def run(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> str:
    return subprocess.run(
        command, check=True, cwd=cwd, env=env, capture_output=True, text=True
    ).stdout.strip()


def release_asset_url(release_tag: str) -> str:
    release = json.loads(
        run(
            [
                "gh",
                "api",
                f"repos/{os.environ['GITHUB_REPOSITORY']}/releases/tags/{release_tag}",
            ]
        )
    )
    for asset in release["assets"]:
        if asset["name"] == "mpv-macos-arm64.zip":
            return asset["browser_download_url"]
    raise RuntimeError(f"mpv-macos-arm64.zip is missing from release {release_tag}")


def verified_release_assets(
    release_tag: str, expected_checksum: str | None
) -> tuple[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as directory:
        run(
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
        run(
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
        run(
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
        metadata = json.loads(
            Path(directory, "build-metadata.json").read_text(encoding="utf-8")
        )
        return checksum, metadata


def write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--cask", choices=("nightly", "release"), required=True)
    parser.add_argument("--sha256")
    parser.add_argument("--mpv-sha", default="")
    parser.add_argument("--mpv-build-sha", default="")
    args = parser.parse_args()

    token = os.getenv("HOMEBREW_TAP_TOKEN")
    if not token:
        print("HOMEBREW_TAP_TOKEN is not configured; skipping Homebrew update.")
        return 0

    tap_repo = os.getenv("TAP_REPO") or "Justin24506/homebrew-tap"
    archive_url = release_asset_url(args.release_tag)
    checksum, metadata = verified_release_assets(args.release_tag, args.sha256)

    if args.cask == "nightly":
        cask_path = Path("Casks/mpv@nightly.rb")
        cask_token = "mpv@nightly"
        description = "Rolling nightly build of mpv"
        version = f"nightly-{metadata['workflow_number']}"
        commit_subject = "Nightly cask update"
    else:
        cask_path = Path("Casks/mpv.rb")
        cask_token = "mpv"
        description = "Custom mpv release"
        version = args.release_tag.removeprefix("v")
        commit_subject = f"Update mpv cask to {args.release_tag}"

    with tempfile.TemporaryDirectory() as directory:
        tap_directory = Path(directory, "tap")
        clone_env = os.environ | {"GH_TOKEN": token}
        run(["gh", "repo", "clone", tap_repo, str(tap_directory)], env=clone_env)
        run(
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
        cask_file.write_text(
            f'''cask "{cask_token}" do
  version "{version}"
  sha256 "{checksum}"

  url "{archive_url}"
  name "mpv"
  desc "{description}"
  homepage "https://github.com/{os.environ["GITHUB_REPOSITORY"]}"

  depends_on arch: :arm64

  app "mpv.app"
end
''',
            encoding="utf-8",
        )

        run(["git", "add", str(cask_path)], cwd=tap_directory)

        changed = (
            subprocess.run(
                ["git", "diff", "--cached", "--quiet"], cwd=tap_directory
            ).returncode
            != 0
        )
        if not changed:
            print("Homebrew cask already matches the release.")
            return 0

        run(["git", "config", "user.name", "github-actions[bot]"], cwd=tap_directory)
        run(
            [
                "git",
                "config",
                "user.email",
                "github-actions[bot]@users.noreply.github.com",
            ],
            cwd=tap_directory,
        )
        message = ["git", "commit", "-m", commit_subject]
        if args.mpv_sha and args.mpv_build_sha:
            message.extend(
                ["-m", f"mpv: {args.mpv_sha}\nmpv-build: {args.mpv_build_sha}"]
            )
        run(message, cwd=tap_directory)
        commit_sha = run(["git", "rev-parse", "HEAD"], cwd=tap_directory)
        run(["git", "push", "origin", "HEAD"], cwd=tap_directory)

    commit_url = f"https://github.com/{tap_repo}/commit/{commit_sha}"
    write_output("tap_commit_url", commit_url)
    print(f"tap_commit_url={commit_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
