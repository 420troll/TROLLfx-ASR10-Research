#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PRIVATE=/home/gamer/research/private-results
HALL="$PRIVATE/asr10-hall-reference-capture-v2-20261124/boot-a/snapshots/run-frame-855973.esp"
ROM02="$PRIVATE/rom02-replay-v1-reference/boot-a/snapshots/run-frame-905028.esp"
[ -f "$HALL" ] && [ -f "$ROM02" ] || { echo "private HALL/ROM-02 checkpoints unavailable" >&2; exit 2; }
OUT="/tmp/trollfx-force-es5510-backend-test"
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -I"$ROOT/include" -I"$ROOT/src" -I"$ROOT/force_plugin/src" \
  "$ROOT/tests/force_es5510_backend_test.cpp" "$ROOT/force_plugin/src/ES5510DSPBackend.cpp" \
  "$ROOT/src/es5510_factory_runtime.cpp" "$ROOT/src/es5510.cpp" -pthread -o "$OUT"
"$OUT" "$HALL" "$ROM02"
