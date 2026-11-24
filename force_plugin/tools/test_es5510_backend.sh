#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PRIVATE=/home/gamer/research/private-results
HALL_ROOT=${TROLLFX_HALL_REFERENCE_ROOT:-$PRIVATE/asr10-hall-reference-capture-v2-20261124}
ROM02_ROOT=${TROLLFX_ROM02_REFERENCE_ROOT:-$PRIVATE/rom02-provenance-v1-reference}
HALL_MANIFEST=${TROLLFX_HALL_MANIFEST:-$PRIVATE/asr10-coldload-tail-20261123T210000Z/state/factory-state.json}
HALL_CHECKPOINT=${TROLLFX_HALL_CHECKPOINT:-$HALL_ROOT/boot-a/snapshots/run-frame-855973.esp}
HALL_EVENTS=${TROLLFX_HALL_EVENTS:-$PRIVATE/asr10-hall-replay-v4-verified-20261124/32768/scheduled-firmware-writes.csv}
ROM02_MANIFEST=${TROLLFX_ROM02_MANIFEST:-$ROM02_ROOT/replay-manifest/factory-state.json}
ROM02_CHECKPOINT=${TROLLFX_ROM02_CHECKPOINT:-$ROM02_ROOT/boot-a/snapshots/run-frame-905028.esp}
ROM02_EVENTS=${TROLLFX_ROM02_EVENTS:-$PRIVATE/rom02-replay-v1-replay/32768/firmware-events.csv}
OUT=${TROLLFX_BACKEND_TEST_DIR:-/tmp/trollfx-force-es5510-backend-test-work}
PACKAGES="$OUT/validated_test_packages.hpp"
CXX=${CXX:-g++}
mkdir -p "$OUT"
python3 "$ROOT/force_plugin/tools/prepare_native_test_packages.py" \
  --hall-manifest "$HALL_MANIFEST" --hall-checkpoint "$HALL_CHECKPOINT" --hall-reference-root "$HALL_ROOT" --hall-events "$HALL_EVENTS" \
  --rom02-manifest "$ROM02_MANIFEST" --rom02-checkpoint "$ROM02_CHECKPOINT" --rom02-reference-root "$ROM02_ROOT" --rom02-events "$ROM02_EVENTS" \
  --output "$PACKAGES"
COMMON="-std=c++17 -O2 -Wall -Wextra -Wpedantic -I$ROOT/include -I$ROOT/src -I$ROOT/force_plugin/src -I$OUT"
$CXX $COMMON "$ROOT/tests/force_es5510_backend_test.cpp" "$ROOT/force_plugin/src/ES5510DSPBackend.cpp" \
  "$ROOT/src/es5510_factory_runtime.cpp" "$ROOT/src/es5510.cpp" -pthread -o "$OUT/backend-test"
$CXX $COMMON -I"${AKAI_FORCE_SDK:-/mnt/c/Users/Gamer/research/AkaiForceSDK}/framework" \
  "$ROOT/tests/force_vst_wrapper_audio_test.cpp" "$ROOT/force_plugin/src/ES5510DSPBackend.cpp" \
  "$ROOT/force_plugin/src/ES5510FactoryPackageProvider.cpp" "$ROOT/src/es5510_factory_runtime.cpp" \
  "$ROOT/src/es5510.cpp" -pthread -ldl -o "$OUT/vst-wrapper-test"
"$OUT/backend-test"
"$OUT/vst-wrapper-test"
