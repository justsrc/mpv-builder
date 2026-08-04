#!/usr/bin/env bash
set -euo pipefail

release_tag="${RELEASE_TAG:-nightly}"
tap_repo="${TAP_REPO:-}"
formula_path="${FORMULA_PATH:-}"
formula_name="${FORMULA_NAME:-}"
formula_desc="${FORMULA_DESC:-mpv build from ${release_tag}}"
tap_token="${TAP_TOKEN:-${GH_TOKEN:-}}"

if [[ -z "$tap_repo" || -z "$formula_path" || -z "$formula_name" ]]; then
  echo "update-tap.sh requires TAP_REPO, FORMULA_PATH, and FORMULA_NAME" >&2
  exit 1
fi

if [[ -z "$tap_token" ]]; then
  echo "update-tap.sh requires TAP_TOKEN or GH_TOKEN for pushing to the tap repository" >&2
  exit 1
fi

# Derive the release asset URL and checksum from the published GitHub release.
archive_url="$(gh api "repos/${GITHUB_REPOSITORY}/releases/tags/${release_tag}" --jq '.assets[] | select(.name | endswith(".zip")) | .browser_download_url' | head -n 1)"
if [[ -z "$archive_url" ]]; then
  echo "Could not find a ZIP asset for release ${release_tag}" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

gh release download "$release_tag" --pattern '*.sha256' --dir "$tmp_dir" >/dev/null
checksum="$(awk '{print $1}' "$tmp_dir"/*.sha256 | head -n 1)"
if [[ -z "$checksum" ]]; then
  echo "Could not read a SHA256 asset for release ${release_tag}" >&2
  exit 1
fi

# Rebuild the formula file inside a temporary clone of the tap repository.
GH_TOKEN="$tap_token" gh repo clone "$tap_repo" "$tmp_dir/tap"
pushd "$tmp_dir/tap" >/dev/null

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

git remote set-url origin "https://x-access-token:${tap_token}@github.com/${tap_repo}.git"

mkdir -p "$(dirname "$formula_path")"

cat > "$formula_path" <<EOF
class ${formula_name} < Formula
  desc "${formula_desc}"
  homepage "https://github.com/${GITHUB_REPOSITORY}"
  url "${archive_url}"
  sha256 "${checksum}"
  version "${release_tag}"

  def install
    prefix.install Dir["*"]
  end
end
EOF

git add "$formula_path"
if git diff --cached --quiet; then
  echo "Tap formula already matches ${release_tag}, nothing to commit."
  exit 0
fi

git commit -m "Update ${formula_name} to ${release_tag}"
git push origin HEAD

popd >/dev/null
