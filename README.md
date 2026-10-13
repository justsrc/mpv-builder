# mpv macOS ARM64 builds

This repository builds custom Apple Silicon mpv packages from the configured
`ffmpeg_options` and `mpv_options` files. The nightly workflow checks mpv,
mpv-build, FFmpeg, libass and libplacebo first, so it skips the build when none
of those upstream revisions changed. Binaries target macOS 12, pinned by
`MACOSX_DEPLOYMENT_TARGET` for the C and Objective-C halves and by
`-Dswift-flags` for Swift, which does not read that variable.

`nightly.yml` publishes the rolling `nightly` prerelease. `release.yml` creates
permanent versioned releases on demand. Both publish `mpv-macos-arm64.zip`,
`SHA256SUMS.txt`, and `build-metadata.json`.

The build pipeline updates the Homebrew Cask only after its release assets are
published. `update-homebrew.yml` is a manual repair/resync workflow, so it
cannot race or duplicate the build pipeline's cask update.

Scheduled runs are gated by the `mpv`, `mpv-build`, `ffmpeg`, `libass` and
`libplacebo` revisions, all of which are pinned and recorded in the release
body, so a given set of revisions always produces the same dependency tree.
Because FFmpeg's master moves almost daily, most scheduled runs now rebuild
rather than skip. Once a build is needed, the current `libdovi` and Cargo-C
revisions choose exact caches: unchanged revisions are restored, while changed
revisions are built once and saved for later runs.

mpv is compiled with warnings as errors for C and ObjC (via `c_args` and
`objc_args`, not meson's `--werror`, whose link-time `-Wl,-fatal_warnings`
turns Homebrew's deployment-target warnings fatal) and its unit suite runs
before the app is bundled. The bundled binary is then executed once, so a build
that links cleanly but does not start still fails the run rather than shipping.

The cask lives in the tap. Each run rewrites only its `version` and
`sha256` stanzas. Adding a channel means adding the cask to the tap first, 
since nothing here creates one. The nightly cask pins no checksum, because 
its URL never changes.

Install the rolling build with `brew install --cask mpv@nightly` after tapping
`justsrc/tap`.

The cask update needs `HOMEBREW_TAP_TOKEN` and is quietly skipped without it,
rather than failing the run. It targets `justsrc/homebrew-tap` by default; set
the `HOMEBREW_TAP_REPO` repository variable to use a different tap.
