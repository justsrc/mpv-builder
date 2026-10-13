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

mpv builds with warnings as errors for C and ObjC. That goes in `c_args` and
`objc_args`, not in meson's `--werror`. Since meson 1.12, `--werror` also hands
the linker `-Wl,-fatal_warnings`, ld64 offers no way to turn that back off, and
every link here warns that Homebrew's dylibs were built for a newer macOS than
our 12.0 target. `--werror` fails the build over warnings that no code change
can fix.

`mpv_options` also passes `-Dobjc_link_args=-framework Foundation`. Upstream's
`test/paths` executable links `osdep/path-mac.m`, which uses `NSAutoreleasePool`,
and never declares a Foundation dependency. Their build only gets away with it by
accident: meson passes `-Wl,-dead_strip_dylibs`, but their test objects still
reference libavutil, so `libavutil.dylib` stays in the load command list and its
own dependencies pull Foundation in at launch. We build FFmpeg statically, so
libavutil is an archive with no load commands, nothing pulls Foundation in, and
the test dies with `dyld: symbol not found in flat namespace`. If those libavutil
references ever go away upstream, dead-stripping drops the dylib and their CI
hits the same crash, so treat this as latent rather than fixed.

`objc_link_args` is the name that matters: meson links that test with the ObjC
driver, because the `.m` object reaches the target through `extract_objects` and
ObjC outranks C when meson picks a link language. Keep the flag either way. Our
FFmpeg stays static, so it does the same work even after upstream fixes this.

The unit suite runs before the app is bundled, and the bundled binary runs once,
so a build that links cleanly but does not start still fails the run.

The cask lives in the tap. Each run rewrites only its `version` and
`sha256` stanzas. Adding a channel means adding the cask to the tap first, 
since nothing here creates one. The nightly cask pins no checksum, because 
its URL never changes.

Install the rolling build with `brew install --cask mpv@nightly` after tapping
`justsrc/tap`.

The cask update needs `HOMEBREW_TAP_TOKEN` and is quietly skipped without it,
rather than failing the run. It targets `justsrc/homebrew-tap` by default; set
the `HOMEBREW_TAP_REPO` repository variable to use a different tap.
