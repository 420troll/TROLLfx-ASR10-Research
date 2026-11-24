#!/bin/sh
# Read-only V1 inspection. This script never copies, deletes, restarts, or remounts.
set -eu
target=${1:-akai-force}
ssh "$target" 'set -eu
PLUGIN_ROOT="/media/SSD250g/VST2 Plugins"
PLUGIN="$PLUGIN_ROOT/TROLLfx - VST - ASR10 FX Collection"
ASSETS=/media/SSD250g/TROLLfx/ASR10/factory-effects
echo "== OS/build =="
grep -E "^(PRETTY_NAME|VERSION_ID)=" /etc/os-release || true
cat /etc/version 2>/dev/null || true
echo "== CPU =="
awk "/^processor[[:space:]]*:/ {n++} /^model name[[:space:]]*:/ && !m {m=\$0} /^CPU architecture[[:space:]]*:/ && !a {a=\$0} END {print \"cores=\" n; print m; print a}" /proc/cpuinfo
echo "== memory =="
grep -E "^(MemTotal|MemAvailable|SwapTotal|SwapFree):" /proc/meminfo
echo "== storage =="
df -h / /synths /media/SSD250g
grep " /media/SSD250g " /proc/mounts
echo "== installed V1 =="
test -f "$PLUGIN/VST/asr10-fx-collection-arm32.so"
sha256sum "$PLUGIN/VST/asr10-fx-collection-arm32.so"
(cd "$PLUGIN" && sha256sum -c SHA256SUMS >/dev/null)
echo "package_checksums=PASS"
cat "$PLUGIN/factory-assets-path.txt"
test -d "$ASSETS"
echo "asset_files=$(find "$ASSETS" -type f | wc -l)"
echo "manifests=$(find "$ASSETS" -name package.json | wc -l)"
echo "run_checkpoints=$(find "$ASSETS" -name run-checkpoint.esp | wc -l)"
echo "provider_index_rows=$(wc -l < "$ASSETS/provider-index.tsv")"
tree_hash=$(cd "$ASSETS" && find . -type f | LC_ALL=C sort | while IFS= read -r f; do sha256sum "$f"; done | sha256sum | awk "{print \$1}")
echo "asset_tree_sha256=$tree_hash"
echo "== MPC process and instantaneous system snapshot =="
ps w | grep "[M]PC" | sed -n "1,3p" || true
top -n 1 | sed -n "1,8p"
echo "== other SSD plugin directories and rollback copies =="
echo "plugin_directories=$(find "$PLUGIN_ROOT" -mindepth 1 -maxdepth 1 -type d | wc -l)"
echo "rollback_copies=$(find "$PLUGIN_ROOT" -mindepth 1 -maxdepth 1 -type d -name ".rollback-*" | wc -l)"
'
