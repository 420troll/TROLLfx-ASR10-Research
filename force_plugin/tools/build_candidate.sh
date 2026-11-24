#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SDK=${AKAI_FORCE_SDK:-"$(dirname "$ROOT")/AkaiForceSDK"}
[ -f "$SDK/tools/build.py" ] || { echo "SDK missing: $SDK" >&2; exit 2; }
STAGE="$SDK/plugins/.trollfx-asr10-force-collection"
OUT="$ROOT/force_plugin/dist"
rm -rf "$STAGE"
mkdir -p "$STAGE/src"
cp "$ROOT/force_plugin/plugin.json" "$ROOT/force_plugin/ui.json" "$STAGE/"
cp "$ROOT/force_plugin/src/ASR10FXCollection.cpp" "$STAGE/src/"
PYTHONPATH="${PYTHONPATH:-/tmp/trollfx-force-zig}" ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-/tmp/trollfx-force-zig-cache}" ZIG_LOCAL_CACHE_DIR="${ZIG_LOCAL_CACHE_DIR:-/tmp/trollfx-force-zig-local}" python3 "$SDK/tools/build.py" "$STAGE" --target all --toolchain zig --zig /usr/bin/python3
"$SDK/.sdk-tools/host_sim" "$STAGE/build/native/asr10-fx-collection.so" test --seconds 1 --wav /tmp/trollfx-force-candidate-smoke.wav
rm -rf "$OUT"
mkdir -p "$OUT"
cp -R "$STAGE/build/TROLLfx - VST - ASR10 FX Collection" "$OUT/"
cp "$ROOT/LICENSE" "$OUT/TROLLfx - VST - ASR10 FX Collection/LICENSE"
mkdir -p "$OUT/TROLLfx - VST - ASR10 FX Collection/LICENSES"
cp "$ROOT/force_plugin/LICENSES/SDK-MIT-NOTICE.txt" "$OUT/TROLLfx - VST - ASR10 FX Collection/LICENSES/"
cp "$ROOT/force_plugin/README.md" "$OUT/TROLLfx - VST - ASR10 FX Collection/README.txt"
python3 - "$OUT/TROLLfx - VST - ASR10 FX Collection" <<'PY'
import hashlib,sys
from pathlib import Path
root=Path(sys.argv[1]); entries=[]
for f in sorted(root.rglob('*')):
    if f.is_file(): entries.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(root)}")
(root/'SHA256SUMS').write_text('\n'.join(entries)+'\n')
PY
rm -rf "$STAGE"
echo "ARM32 Force candidate: $OUT/TROLLfx - VST - ASR10 FX Collection"
