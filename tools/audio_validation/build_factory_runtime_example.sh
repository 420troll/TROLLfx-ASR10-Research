#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="$root/build/audio-validation"
mkdir -p "$out"
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -I"$root/include" -I"$root/src" \
  "$root/examples/es5510_factory_runtime.cpp" \
  "$root/src/es5510_factory_runtime.cpp" "$root/src/es5510.cpp" \
  -o "$out/es5510-factory-runtime-example"
printf 'Built %s\n' "$out/es5510-factory-runtime-example"
