#!/usr/bin/env bash
set -euo pipefail

release_tag="${RELEASE_TAG:-nightly}"
release_title="${RELEASE_TITLE:-$release_tag}"
release_notes_file="${RELEASE_NOTES_FILE:-}"
release_asset_zip="${RELEASE_ASSET_ZIP:-}"
release_asset_sha256="${RELEASE_ASSET_SHA256:-}"
release_prerelease="${RELEASE_PRERELEASE:-false}"

if [[ -z "$release_notes_file" || -z "$release_asset_zip" || -z "$release_asset_sha256" ]]; then
  echo "RELEASE_NOTES_FILE, RELEASE_ASSET_ZIP, and RELEASE_ASSET_SHA256 are required" >&2
  exit 1
fi

release_args=(--title "$release_title" --notes-file "$release_notes_file")
if [[ "$release_prerelease" == true ]]; then
  release_args+=(--prerelease)
fi

if gh release view "$release_tag" >/dev/null 2>&1; then
  gh release upload "$release_tag" "$release_asset_zip" "$release_asset_sha256" --clobber
  gh release edit "$release_tag" "${release_args[@]}"
else
  gh release create "$release_tag" "$release_asset_zip" "$release_asset_sha256" "${release_args[@]}"
fi
