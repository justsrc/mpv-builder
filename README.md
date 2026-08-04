# mpv macOS ARM64 builds

This repository builds custom Apple Silicon mpv packages from the configured
`ffmpeg_options` and `mpv_options` files. The nightly workflow checks mpv and
mpv-build first, so it skips the build when neither upstream revision changed.

`nightly.yml` publishes the rolling `nightly` prerelease. `release.yml` creates
permanent versioned releases on demand. Both publish `mpv-macos-arm64.zip`,
`SHA256SUMS.txt`, and `build-metadata.json`.

The build pipeline updates the Homebrew Cask only after its release assets are
published. `update-homebrew.yml` is a manual repair/resync workflow, so it
cannot race or duplicate the build pipeline's cask update.

Scheduled runs are gated only by `mpv` and `mpv-build` revisions. Once a build
is needed, the current `libdovi` and Cargo-C revisions choose exact caches:
unchanged revisions are restored, while changed revisions are built once and
saved for later runs.

Install the rolling build with `brew install --cask mpv@nightly` after tapping
`Justin24506/tap`. The generated cask installs `mpv.app` and verifies the
published SHA-256 checksum.

Set `HOMEBREW_TAP_TOKEN` only when the Homebrew tap is in another repository.
By default the updater targets `Justin24506/homebrew-tap`; set the
`HOMEBREW_TAP_REPO` repository variable to use a different tap.
