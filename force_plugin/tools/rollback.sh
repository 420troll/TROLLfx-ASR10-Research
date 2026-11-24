#!/bin/sh
set -eu
[ "$#" = 1 ] || { echo "usage: rollback.sh FORCE_VST2_PLUGINS_DIR" >&2; exit 2; }
TARGET="$1/TROLLfx - VST - ASR10 FX Collection"
[ -d "$TARGET" ] || { echo "plugin folder not found: $TARGET" >&2; exit 1; }
rm -rf "$TARGET"
echo "Removed plugin folder. Restart the host manually if needed."
