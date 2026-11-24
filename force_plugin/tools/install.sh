#!/bin/sh
set -eu
[ "$#" = 2 ] || { echo "usage: install.sh PACKAGE_DIR FORCE_VST2_PLUGINS_DIR" >&2; exit 2; }
PKG=$(CDPATH= cd -- "$1" && pwd); TARGET=$2; NAME='TROLLfx - VST - ASR10 FX Collection'
[ -f "$PKG/plugin.json" ] && [ -f "$PKG/VST/asr10-fx-collection-arm32.so" ] || { echo "invalid ARM32 package" >&2; exit 2; }
mkdir -p "$TARGET"
[ ! -e "$TARGET/$NAME" ] || { echo "target exists; move it aside before installing" >&2; exit 1; }
cp -R "$PKG" "$TARGET/$NAME"
echo "Copied plugin. Restart the host manually to rescan."
