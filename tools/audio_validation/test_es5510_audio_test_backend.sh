#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
out="$root/build/audio-test-backend"
mkdir -p "$out"
${CXX:-c++} -std=c++17 -O2 -Wall -Wextra -Wpedantic -I"$root/include" -I"$root/src" \
  "$root/src/es5510_audio_test_backend.cpp" "$root/src/es5510_factory_runtime.cpp" \
  "$root/src/es5510.cpp" "$root/src/wav_io.cpp" \
  "$root/src/experimental_audio_host.cpp" "$root/tests/test_es5510_audio_test_backend.cpp" \
  -o "$out/es5510-audio-test-backend-test"
"$out/es5510-audio-test-backend-test"
printf 'PASS: ES5510 WAV test backend synthetic suite\n'
