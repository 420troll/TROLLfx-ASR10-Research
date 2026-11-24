#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="${TMPDIR:-/tmp}/es5510-factory-runtime-benchmark"
mkdir -p "$out"
g++ -std=c++17 -O3 -DNDEBUG -I"$root/include" -I"$root/src" \
  "$root/tools/audio_validation/benchmark_factory_runtime.cpp" \
  "$root/src/es5510_factory_runtime.cpp" "$root/src/es5510.cpp" \
  -o "$out/benchmark-factory-runtime"
"$out/benchmark-factory-runtime" "$@"
