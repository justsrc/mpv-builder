#!/usr/bin/env bash
set -euo pipefail

release_name="${RELEASE_NAME:-nightly}"
build_root="${BUILD_ROOT:-mpv-build}"
dist_root="${DIST_ROOT:-dist}"
archive_name="${ARCHIVE_NAME:-mpv-${release_name}.zip}"
repo_root="$PWD"
bundle_path="${BUNDLE_PATH:-build/mpv.app}"

# Start from a clean build tree so reruns do not reuse stale artifacts.
rm -rf "$build_root" "$dist_root"
mkdir -p "$dist_root"

# Pull mpv-build and inject the repository-local option files.
git clone --depth=1 https://github.com/mpv-player/mpv-build.git "$build_root"
cp ffmpeg_options "$build_root/"
cp mpv_options "$build_root/"

# Build mpv with the Homebrew include and library paths used by the upstream formulas.
pushd "$build_root" >/dev/null
env \
  CFLAGS='-I/opt/homebrew/include' \
  LDFLAGS='-L/opt/homebrew/lib' \
  PKG_CONFIG_PATH='/opt/homebrew/lib/pkgconfig:/opt/homebrew/share/pkgconfig:/opt/homebrew/opt/glslang/lib/pkgconfig:/opt/homebrew/opt/libarchive/lib/pkgconfig' \
  ./use-mpv-master
env \
  CFLAGS='-I/opt/homebrew/include' \
  LDFLAGS='-L/opt/homebrew/lib' \
  PKG_CONFIG_PATH='/opt/homebrew/lib/pkgconfig:/opt/homebrew/share/pkgconfig:/opt/homebrew/opt/glslang/lib/pkgconfig:/opt/homebrew/opt/libarchive/lib/pkgconfig' \
  ./rebuild

# Replace the bundled helper scripts before wrapping the application.
cp ../osxbundle.py TOOLS/osxbundle.py
cp ../dylib_unhell.py TOOLS/dylib_unhell.py

# Create the .app bundle and compress it into a release asset.
python3 TOOLS/osxbundle.py build/mpv .
zip_path="../$dist_root/$archive_name"
ditto -c -k --keepParent "$bundle_path" "$zip_path"

# Emit a portable SHA256 file alongside the archive.
sha256_path="$zip_path.sha256"
shasum -a 256 "$zip_path" > "$sha256_path"

popd >/dev/null

# Surface the artifact locations to downstream workflow steps.
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    printf 'zip_path=%s\n' "$repo_root/$dist_root/$archive_name"
    printf 'sha256_path=%s\n' "$repo_root/$dist_root/$archive_name.sha256"
    printf 'app_path=%s\n' "$repo_root/$build_root/$bundle_path"
  } >> "$GITHUB_OUTPUT"
fi

printf 'zip_path=%s\n' "$repo_root/$dist_root/$archive_name"
printf 'sha256_path=%s\n' "$repo_root/$dist_root/$archive_name.sha256"
