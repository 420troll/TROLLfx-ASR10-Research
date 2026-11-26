#!/bin/sh
# Restore an external Force plugin backup while preserving the failed candidate.
set -eu

[ "$#" -eq 2 ] || { echo "Usage: $0 PLUGIN_ROOT BACKUP_DIR" >&2; exit 2; }
plugin_root=$1
backup_dir=$2
plugin_name='TROLLfx - VST - ASR10 FX Collection'
target=$plugin_root/$plugin_name
backup=$backup_dir/$plugin_name
arm_rel='VST/asr10-fx-collection-arm32.so'
case "$backup_dir" in "$plugin_root"|"$plugin_root"/*) echo "backup must be outside the VST scan directory" >&2; exit 2;; esac
[ -d "$backup" ] && [ ! -L "$backup" ] || { echo "rollback package missing or symlinked" >&2; exit 2; }
[ -f "$backup/plugin.json" ] || { echo "rollback plugin metadata missing" >&2; exit 2; }
grep -F '"name": "ASR10 FX Collection"' "$backup/plugin.json" >/dev/null
grep -F '"manufacturer": "TROLLfx"' "$backup/plugin.json" >/dev/null
[ -f "$backup/SHA256SUMS" ] || { echo "rollback checksum manifest missing" >&2; exit 2; }
(cd "$backup" && sha256sum -c SHA256SUMS >/dev/null)
[ -f "$backup/$arm_rel" ] || { echo "rollback ARM32 binary missing" >&2; exit 2; }

stamp=$(date +%Y%m%d-%H%M%S)
removed=$backup_dir/.removed-current-$stamp
if [ -e "$target" ]; then
    [ -d "$target" ] && [ ! -L "$target" ] || { echo "current plugin is not a real directory" >&2; exit 2; }
    mv "$target" "$removed"
fi
if ! cp -a "$backup" "$target"; then
    if [ -e "$removed" ] && [ ! -e "$target" ]; then mv "$removed" "$target"; fi
    echo "rollback copy failed; prior candidate restored if present" >&2
    exit 2
fi
if ! (cd "$target" && sha256sum -c SHA256SUMS >/dev/null); then
    failed=$backup_dir/.failed-rollback-$stamp
    mv "$target" "$failed"
    if [ -e "$removed" ]; then mv "$removed" "$target"; fi
    echo "restored backup failed checksum; previous candidate restored" >&2
    exit 2
fi
echo "restored=$target"
echo "arm32_sha256=$(sha256sum "$target/$arm_rel" | cut -d ' ' -f 1)"
echo "previous_candidate_preserved=$removed"
