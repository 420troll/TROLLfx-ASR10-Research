#!/bin/sh
# Install a checksummed playable package on the Force without target-side Python.
set -eu

usage() {
    echo "Usage: $0 PACKAGE PLUGIN_ROOT BACKUP_DIR NEW_ARM32_SHA256 OLD_ARM32_SHA256" >&2
    exit 2
}
[ "$#" -eq 5 ] || usage
package=$1
plugin_root=$2
backup_dir=$3
expected_new=$4
expected_old=$5
plugin_name='TROLLfx - VST - ASR10 FX Collection'
target=$plugin_root/$plugin_name
backup=$backup_dir/$plugin_name
arm_rel='VST/asr10-fx-collection-arm32.so'

case "$backup_dir" in "$plugin_root"|"$plugin_root"/*) echo "backup must be outside the VST scan directory" >&2; exit 2;; esac
case "$expected_new$expected_old" in *[!0-9a-f]*) echo "binary hashes must be lowercase SHA-256" >&2; exit 2;; esac
[ "${#expected_new}" -eq 64 ] && [ "${#expected_old}" -eq 64 ] || usage
[ -d "$package" ] && [ ! -L "$package" ] || { echo "staged package directory is missing or symlinked" >&2; exit 2; }
[ "$(basename "$package")" = "$plugin_name" ] || { echo "staged package folder name mismatch" >&2; exit 2; }
[ -f "$package/INTEGRATION_STATUS" ] && [ -f "$package/release-manifest.json" ] || { echo "playable marker or release manifest missing" >&2; exit 2; }
grep -F '"release_state": "playable"' "$package/release-manifest.json" >/dev/null
grep -F '"playable": true' "$package/release-manifest.json" >/dev/null
grep -F '"status": "playable"' "$package/INTEGRATION_STATUS" >/dev/null
grep -F '"mock_backend": false' "$package/INTEGRATION_STATUS" >/dev/null
marker_binary_field='"arm32_binary_sha256": "'"$expected_new"'"'
manifest_binary_field='"arm32_sha256": "'"$expected_new"'"'
grep -F "$marker_binary_field" "$package/INTEGRATION_STATUS" >/dev/null
grep -F "$manifest_binary_field" "$package/release-manifest.json" >/dev/null
[ -f "$package/SHA256SUMS" ] || { echo "candidate checksum manifest missing" >&2; exit 2; }
(cd "$package" && sha256sum -c SHA256SUMS >/dev/null)
actual_new=$(sha256sum "$package/$arm_rel" | cut -d ' ' -f 1)
[ "$actual_new" = "$expected_new" ] || { echo "candidate ARM32 binary hash mismatch" >&2; exit 2; }
[ -f "$package/factory-assets-path.txt" ] || { echo "factory asset path reference missing" >&2; exit 2; }
asset_root=$(sed -n '1p' "$package/factory-assets-path.txt")
case "$asset_root" in /*) ;; *) echo "factory asset path must be absolute" >&2; exit 2;; esac
[ -f "$asset_root/provider-index.tsv" ] || { echo "factory provider index missing at $asset_root" >&2; exit 2; }
awk -F '\t' 'NR==1 {if ($0 != "TROLLFX_FORCE_ASSETS\t1") exit 2; next} NF!=15 {exit 3} {if ($1 != NR-1) exit 4} END {if (NR!=51) exit 5}' "$asset_root/provider-index.tsv"
[ "$(find "$asset_root" -name package.json -type f | wc -l | tr -d ' ')" -eq 50 ] || { echo "factory package manifest count is not 50" >&2; exit 2; }
[ "$(find "$asset_root" -name run-checkpoint.esp -type f | wc -l | tr -d ' ')" -eq 50 ] || { echo "factory checkpoint count is not 50" >&2; exit 2; }
tab=$(printf '\t')
awk -F '\t' 'NR>1 {for (i=0;i<4;i++) print $(8+2*i) "\t" $(7+2*i)}' "$asset_root/provider-index.tsv" |
while IFS="$tab" read -r expected rel; do
    case "$rel" in /*|../*|*/../*|*/..) echo "unsafe factory asset path in provider index" >&2; exit 2;; esac
    [ -n "$expected" ] && [ -n "$rel" ] || { echo "empty provider index asset reference" >&2; exit 2; }
    actual=$(sha256sum "$asset_root/$rel" | cut -d ' ' -f 1)
    [ "$actual" = "$expected" ] || { echo "factory asset digest mismatch: $rel" >&2; exit 2; }
done

[ -d "$plugin_root" ] && [ ! -L "$plugin_root" ] || { echo "VST plugin root missing or symlinked" >&2; exit 2; }
[ ! -e "$backup_dir" ] || { echo "backup destination already exists: $backup_dir" >&2; exit 2; }
mkdir -p "$(dirname "$backup_dir")"
mkdir "$backup_dir"
old_moved=0
if [ -e "$target" ]; then
    [ -d "$target" ] && [ ! -L "$target" ] || { echo "installed plugin is not a real directory" >&2; exit 2; }
    old_actual=$(sha256sum "$target/$arm_rel" | cut -d ' ' -f 1)
    [ "$old_actual" = "$expected_old" ] || { echo "installed binary changed since preflight" >&2; exit 2; }
    if [ -f "$target/SHA256SUMS" ]; then (cd "$target" && sha256sum -c SHA256SUMS >/dev/null); fi
    mv "$target" "$backup"
    old_moved=1
    if [ -f "$backup/SHA256SUMS" ]; then (cd "$backup" && sha256sum -c SHA256SUMS >/dev/null); fi
    [ "$(sha256sum "$backup/$arm_rel" | cut -d ' ' -f 1)" = "$expected_old" ] || {
        mv "$backup" "$target"; echo "rollback backup verification failed" >&2; exit 2;
    }
fi

if ! mv "$package" "$target"; then
    if [ "$old_moved" -eq 1 ]; then mv "$backup" "$target"; fi
    echo "candidate activation failed; previous package restored" >&2
    exit 2
fi
if ! (cd "$target" && sha256sum -c SHA256SUMS >/dev/null) ||
   [ "$(sha256sum "$target/$arm_rel" | cut -d ' ' -f 1)" != "$expected_new" ]; then
    failed=$backup_dir/.failed-candidate-$(date +%Y%m%d-%H%M%S)
    mv "$target" "$failed"
    if [ "$old_moved" -eq 1 ]; then mv "$backup" "$target"; fi
    echo "installed candidate failed verification; prior package restored" >&2
    exit 2
fi
echo "installed=$target"
echo "arm32_sha256=$expected_new"
echo "asset_root=$asset_root"
if [ "$old_moved" -eq 1 ]; then echo "rollback_backup=$backup"; fi
