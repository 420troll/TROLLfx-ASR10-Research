#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out="$root/build/experimental-audio-host"
mkdir -p "$out"
cxx=${CXX:-c++}
"$cxx" -std=c++17 -O2 -Wall -Wextra -Wpedantic -Iinclude -Isrc \
  src/experimental_audio_host.cpp src/factory_runtime_audio_adapter.cpp \
  src/es5510_factory_runtime.cpp src/es5510.cpp src/wav_io.cpp src/trollfx_audio_host_cli.cpp \
  -o "$out/trollfx-audio-host"
"$cxx" -std=c++17 -O2 -Wall -Wextra -Wpedantic -Isrc \
  src/experimental_audio_host.cpp tests/experimental_audio_host_test.cpp \
  -o "$out/experimental-audio-host-test"
printf 'Built %s\n' "$out/trollfx-audio-host"
