#!/usr/bin/env bash
set -euo pipefail

release_tag="${RELEASE_TAG:-nightly}"
formula_kind="${FORMULA_KIND:-nightly}"
tap_repo="${TAP_REPO:-Justin24506/homebrew-tap}"
tap_token="${TAP_TOKEN:-}"

case "$formula_kind" in
  nightly)
    formula_path=Formula/mpv-nightly.rb
    formula_name=MpvNightly
    formula_desc='Rolling nightly build of mpv'
    ;;
  release)
    formula_path=Formula/mpv.rb
    formula_name=Mpv
    formula_desc='Pinned mpv release'
    ;;
  *)
    echo "FORMULA_KIND must be nightly or release" >&2
    exit 1
    ;;
esac

if [[ -z "$tap_token" ]]; then
  echo "TAP_TOKEN is required to update the tap" >&2
  exit 1
fi

archive_url="$(gh api "repos/${GITHUB_REPOSITORY}/releases/tags/${release_tag}" --jq '.assets[] | select(.name | endswith(".zip")) | .browser_download_url' | head -n 1)"
if [[ -z "$archive_url" ]]; then
  echo "Could not find a ZIP asset for release ${release_tag}" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

gh release download "$release_tag" --pattern '*.sha256' --dir "$tmp_dir" >/dev/null
checksum_file="$(find "$tmp_dir" -maxdepth 1 -name '*.sha256' -print -quit)"
if [[ -z "$checksum_file" ]]; then
  echo "Could not find a SHA256 asset for release ${release_tag}" >&2
  exit 1
fi
checksum="$(awk 'NR == 1 { print $1; exit }' "$checksum_file")"

GH_TOKEN="$tap_token" gh repo clone "$tap_repo" "$tmp_dir/tap"
pushd "$tmp_dir/tap" >/dev/null

git config user.name 'github-actions[bot]'
git config user.email 'github-actions[bot]@users.noreply.github.com'
git remote set-url origin "https://x-access-token:${tap_token}@github.com/${tap_repo}.git"

mkdir -p "$(dirname "$formula_path")"
cat > "$formula_path" <<FORMULA
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
FORMULA

git add "$formula_path"
if ! git diff --cached --quiet; then
  git commit -m "Update ${formula_name} to ${release_tag}"
  git push origin HEAD
fi

popd >/dev/null
