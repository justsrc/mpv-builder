#!/usr/bin/env bash
set -euo pipefail

# Refresh Homebrew once, then install the dependencies used by the build.
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
