#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fileinput
import os
import re
import shutil
import subprocess
from typing import Protocol, cast

import dylib_unhell


class _BundleArgs(Protocol):
    binary_name: str
    src_path: str
    category: str
    deps: bool


def bundle_path(binary_name: str) -> str:
    return f"{binary_name}.app"


def bundle_name(binary_name: str) -> str:
    return os.path.basename(bundle_path(binary_name))


def target_plist(binary_name: str) -> str:
    return os.path.join(bundle_path(binary_name), "Contents", "Info.plist")


def target_directory(binary_name: str) -> str:
    return os.path.join(bundle_path(binary_name), "Contents", "MacOS")


def target_binary(binary_name: str) -> str:
    return os.path.join(target_directory(binary_name), os.path.basename(binary_name))


def copy_bundle(binary_name: str, src_path: str) -> None:
    if os.path.isdir(bundle_path(binary_name)):
        shutil.rmtree(bundle_path(binary_name))

    _ = shutil.copytree(
        os.path.join(src_path, "TOOLS", "osxbundle", bundle_name(binary_name)),
        bundle_path(binary_name),
    )

    os.makedirs(target_directory(binary_name), exist_ok=True)


def copy_binary(binary_name: str) -> None:
    os.makedirs(target_directory(binary_name), exist_ok=True)
    _ = shutil.copy(binary_name, target_binary(binary_name))


def apply_plist_template(plist_file: str, version: str, category: str) -> None:
    print(">> setting bundle category to " + category)
    for line in fileinput.input(plist_file, inplace=True):
        print(
            line.rstrip()
            .replace("${VERSION}", version)
            .replace("${CATEGORY}", category)
        )


def sign_bundle(binary_name: str) -> None:
    sign_directories: list[str] = ["Contents/Frameworks", "Contents/MacOS"]
    for sign_dir in sign_directories:
        resolved_dir: str = os.path.join(bundle_path(binary_name), sign_dir)
        for root, _dirs, files in os.walk(resolved_dir):
            for f in files:
                path: str = os.path.join(root, f)
                _ = subprocess.run(["codesign", "--force", "-s", "-", path])
    _ = subprocess.run(["codesign", "--force", "-s", "-", bundle_path(binary_name)])


def bundle_version(build_path: str) -> str:
    version: str = "UNKNOWN"
    version_h_path: str = os.path.join(build_path, "common", "version.h")
    if os.path.exists(version_h_path):
        with open(version_h_path, encoding="utf-8") as x:
            content: str = x.read()
            matches: list[str] = re.findall(r"#define\s+VERSION\s+\"v(.+)\"", content)
            if matches:
                version = matches[0]
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description="Create macOS application bundle")
    _ = parser.add_argument("binary_name", help="path to mpv binary")
    _ = parser.add_argument("src_path", nargs="?", default=".", help="mpv source path")
    _ = parser.add_argument(
        "-s",
        "--skip-deps",
        dest="deps",
        action="store_false",
        default=True,
        help="don't bundle the dependencies",
    )
    _ = parser.add_argument(
        "-c",
        "--category",
        choices=["video", "games"],
        default="video",
        help="sets bundle category",
    )
    args = parser.parse_args()
    args_typed = cast(_BundleArgs, cast(object, args))

    binary_name: str = args_typed.binary_name
    build_path: str = os.path.dirname(binary_name)
    src_path: str = args_typed.src_path

    version: str = bundle_version(build_path).rstrip()

    print(f"Creating macOS application bundle (version: {version})...")
    print("> copying bundle skeleton")
    copy_bundle(binary_name, src_path)
    print("> copying binary")
    copy_binary(binary_name)
    print("> generating Info.plist")
    category: str = args_typed.category
    apply_plist_template(target_plist(binary_name), version, category)

    deps: bool = args_typed.deps
    if deps:
        print("> bundling dependencies")
        dylib_unhell.process(target_binary(binary_name))

    print("> signing bundle with ad-hoc pseudo identity")
    sign_bundle(binary_name)

    print("done.")


if __name__ == "__main__":
    main()
