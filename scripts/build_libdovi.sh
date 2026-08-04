#!/usr/bin/env bash
set -euo pipefail

prepare_homebrew() {
  if brew tap | grep -Fxq 'aws/tap'; then
    brew untap aws/tap
  fi
}

install_brew_dependencies() {
  brew update
  brew install \
    aom \
    autoconf \
    automake \
    dav1d \
    docutils \
    fdk-aac \
    fontconfig \
    freetype \
    fribidi \
    game-music-emu \
    gmp \
    gnutls \
    glslang \
    harfbuzz \
    icu4c@78 \
    jpeg-xl \
    lame \
    lcms2 \
    libarchive \
    libass \
    libbluray \
    libcdio \
    libcdio-paranoia \
    libdvdnav \
    libdvdread \
    libmodplug \
    libogg \
    libplacebo \
    libsoxr \
    libssh \
    libtool \
    libvidstab \
    libvmaf \
    libvorbis \
    libvpx \
    libxml2 \
    libzip \
    librsvg \
    luajit \
    meson \
    molten-vk \
    mujs \
    ninja \
    opus \
    openssl@3 \
    pkg-config \
    rav1e \
    rubberband \
    samba \
    shaderc \
    snappy \
    svt-av1 \
    uchardet \
    vapoursynth \
    vulkan-loader \
    webp \
    x264 \
    x265 \
    xxhash \
    zimg
}

install_cargo_c() {
  local cargo_c_sha cargo_home marker_path

  cargo_c_sha="${CARGO_C_SHA:?CARGO_C_SHA is required}"
  cargo_home="${CARGO_HOME:-$HOME/.cargo}"
  marker_path="$cargo_home/.cargo-c-source-sha"

  if cargo cinstall --help >/dev/null 2>&1 && [[ -f "$marker_path" ]] && [[ "$(<"$marker_path")" == "$cargo_c_sha" ]]; then
    return
  fi

  cargo install --git https://github.com/lu-zero/cargo-c.git --rev "$cargo_c_sha" --locked --force cargo-c
  printf '%s\n' "$cargo_c_sha" > "$marker_path"
}

deploy_libdovi() {
  local install_root="$1"

  rsync -a "$install_root/" /opt/homebrew/
}

build_libdovi() {
  local libdovi_sha cache_dir source_root install_root source_matches install_matches

  libdovi_sha="${LIBDOVI_SHA:?LIBDOVI_SHA is required}"
  cache_dir="${CACHE_DIR:-$HOME/.cache/mpv-builder}"
  source_root="$cache_dir/dovi_tool"
  install_root="$cache_dir/libdovi-install"
  source_matches=false
  install_matches=false

  if [[ -d "$source_root/.git" ]] && [[ "$(git -C "$source_root" rev-parse HEAD)" == "$libdovi_sha" ]]; then
    source_matches=true
  fi
  if [[ -d "$install_root/include" ]] && [[ -d "$install_root/lib" ]]; then
    install_matches=true
  fi

  if [[ "$source_matches" == true && "$install_matches" == true ]]; then
    deploy_libdovi "$install_root"
  else
    if [[ "$source_matches" != true ]]; then
      rm -rf "$source_root"
      mkdir -p "$source_root"
      git -C "$source_root" init --quiet
      git -C "$source_root" remote add origin https://github.com/quietvoid/dovi_tool.git
      git -C "$source_root" fetch --depth=1 origin "$libdovi_sha"
      git -C "$source_root" checkout --detach --quiet FETCH_HEAD
    fi

    rm -rf "$install_root"
    mkdir -p "$install_root"

    pushd "$source_root/dolby_vision" >/dev/null
    cargo cinstall --release --prefix "$install_root"
    popd >/dev/null
    deploy_libdovi "$install_root"
  fi

  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf 'libdovi_sha=%s\n' "$libdovi_sha" >> "$GITHUB_OUTPUT"
  fi
}

case "${1:-build}" in
  prepare-homebrew)
    prepare_homebrew
    ;;
  brew-dependencies)
    install_brew_dependencies
    ;;
  cargo-c)
    install_cargo_c
    ;;
  build)
    build_libdovi
    ;;
  *)
    printf 'Usage: %s {prepare-homebrew|brew-dependencies|cargo-c|build}\n' "$0" >&2
    exit 2
    ;;
esac
