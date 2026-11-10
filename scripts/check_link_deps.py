#!/usr/bin/env python3
"""Verify that the libraries referenced by generated pkg-config files can be linked.

mpv is linked with the flags pkg-config produces for the .pc files the build
installs (ffmpeg's libav*.pc plus libplacebo.pc and libass.pc). Those flags can
contain bare "-lfoo" entries whose search path is not part of the .pc file, so
a mismatch between the flags and the libraries present on the runner only
surfaces as an opaque linker error at the very end of the build:

    ld: library 'snappy' not found

This script resolves the same flags with pkg-config and checks that every -L
path exists and every -l library is present in one of the search paths the
linker would use, so a broken dependency is reported by name.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys

# Directories meson adds to every link, on top of the ones named in the flags.
FALLBACK_DIRS = ("/usr/lib", "/usr/local/lib")

# Apple clang maps some GNU spellings onto its own libraries, so "-lstdc++"
# resolves to libc++ even though no libstdc++ is installed.
LIBRARY_ALIASES = {"stdc++": ("c++",)}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def sdk_search_dirs() -> list[str]:
    """Return the SDK and toolchain directories the linker searches by default."""
    dirs: list[str] = []
    xcrun = shutil.which("xcrun")
    if not xcrun:
        return dirs
    sdk = run([xcrun, "--show-sdk-path"])
    if sdk.returncode == 0 and sdk.stdout.strip():
        dirs.append(os.path.join(sdk.stdout.strip(), "usr", "lib"))
    clang = run([xcrun, "--find", "clang"])
    if clang.returncode == 0 and clang.stdout.strip():
        toolchain = os.path.dirname(os.path.dirname(clang.stdout.strip()))
        dirs.append(os.path.join(toolchain, "lib"))
    return dirs


def option_search_dirs(paths: list[str]) -> list[str]:
    """Return the -L directories declared in meson option files.

    mpv_options holds the link args mpv is configured with, so these are the
    search paths the mpv link actually uses on top of the ones pkg-config
    contributes.
    """
    dirs: list[str] = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
        except OSError as error:
            print(f"cannot read {path}: {error}", file=sys.stderr)
            continue
        for token in content.split():
            if token.startswith("-L") and len(token) > 2:
                dirs.append(token[2:])
    return dirs


def pkgconfig_libs(package: str, pkg_config_path: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PKG_CONFIG_PATH"] = pkg_config_path
    return subprocess.run(
        ["pkg-config", "--libs", package], capture_output=True, text=True, env=env
    )


def parse_flags(flags: str) -> tuple[list[str], list[str], list[str]]:
    """Split pkg-config output into search paths, library names and file paths."""
    tokens = flags.split()
    lib_dirs: list[str] = []
    libraries: list[str] = []
    files: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        kind = None
        value = None
        if token in ("-L", "-l"):
            kind = token[1]
            if index + 1 < len(tokens):
                value = tokens[index + 1]
                index += 1
        elif token.startswith("-L"):
            kind, value = "L", token[2:]
        elif token.startswith("-l"):
            kind, value = "l", token[2:]
        elif token.startswith("/"):
            files.append(token)
        if kind == "L" and value:
            lib_dirs.append(value)
        elif kind == "l" and value:
            libraries.append(value)
        index += 1
    return lib_dirs, libraries, files


def find_library(name: str, search_dirs: list[str]) -> str | None:
    """Return the library file that would satisfy "-l<name>", if there is one."""
    for directory in search_dirs:
        for pattern in (
            f"lib{name}.dylib",
            f"lib{name}.tbd",
            f"lib{name}.a",
            f"lib{name}.*.dylib",
        ):
            for match in sorted(glob.glob(os.path.join(directory, pattern))):
                if os.path.exists(match):
                    return match
    return None


def resolve_library(name: str, search_dirs: list[str]) -> str | None:
    for candidate in (name, *LIBRARY_ALIASES.get(name, ())):
        found = find_library(candidate, search_dirs)
        if found:
            return found
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pkgconfig_dirs",
        nargs="+",
        help="directories holding the generated .pc files",
    )
    parser.add_argument(
        "--options",
        action="append",
        default=[],
        help="meson option file whose -L entries are part of the link (repeatable)",
    )
    args = parser.parse_args()

    if not shutil.which("pkg-config"):
        print("pkg-config not found", file=sys.stderr)
        return 1

    packages: list[str] = []
    for directory in args.pkgconfig_dirs:
        if not os.path.isdir(directory):
            print(f"skipping missing directory: {directory}")
            continue
        packages.extend(
            sorted(os.path.basename(path)[:-3] for path in glob.glob(f"{directory}/*.pc"))
        )

    if not packages:
        print("no pkg-config files found, nothing to check")
        return 0

    pkg_config_path = os.pathsep.join(args.pkgconfig_dirs)
    option_dirs = option_search_dirs(args.options)
    problems: list[str] = []
    lib_dirs: list[str] = []
    libraries: list[str] = []
    files: list[str] = []

    for package in packages:
        result = pkgconfig_libs(package, pkg_config_path)
        if result.returncode != 0:
            problems.append(
                f"{package}: pkg-config --libs failed: {result.stderr.strip() or 'unknown error'}"
            )
            continue
        package_dirs, package_libraries, package_files = parse_flags(result.stdout)
        lib_dirs.extend(package_dirs)
        libraries.extend(package_libraries)
        files.extend(package_files)

    search_dirs: list[str] = []
    for directory in [*lib_dirs, *option_dirs, *FALLBACK_DIRS, *sdk_search_dirs()]:
        if directory not in search_dirs:
            search_dirs.append(directory)

    for directory in lib_dirs:
        if not os.path.isdir(directory) and directory not in problems:
            problems.append(f"search path does not exist: {directory}")

    for directory in option_dirs:
        if not os.path.isdir(directory) and directory not in problems:
            problems.append(f"declared search path does not exist: {directory}")

    for path in files:
        if not os.path.exists(path):
            problems.append(f"library file does not exist: {path}")

    unresolved: list[str] = []
    for library in libraries:
        if library in unresolved:
            continue
        if resolve_library(library, search_dirs) is None:
            unresolved.append(library)

    for library in unresolved:
        problems.append(
            f"library '{library}' is not in any search path "
            f"(add its directory with -L to the link args)"
        )

    print(
        f"checked {len(packages)} packages, {len(set(libraries))} libraries, "
        f"{len(search_dirs)} search paths"
    )
    for problem in problems:
        print(f"ERROR: {problem}", file=sys.stderr)
    if unresolved:
        print("searched:", file=sys.stderr)
        for directory in search_dirs:
            print(f"  {directory}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} problem(s) found", file=sys.stderr)
        return 1
    print("all referenced libraries resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
