#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="${TMPDIR:-/tmp}/es5510-factory-runtime-test"
mkdir -p "$out"
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -I"$root/include" -I"$root/src" \
  "$root/tests/test_es5510_factory_runtime.cpp" \
  "$root/src/es5510_factory_runtime.cpp" "$root/src/es5510.cpp" \
  -o "$out/test-es5510-factory-runtime"
"$out/test-es5510-factory-runtime"
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -I"$root/src" \
  "$root/tests/input_sanitization_test.cpp" -o "$out/test-input-sanitization"
"$out/test-input-sanitization"
