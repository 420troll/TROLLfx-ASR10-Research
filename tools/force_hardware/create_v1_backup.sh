#!/usr/bin/env bash
# Create a non-overwriting V1 backup outside the Force VST2 scan directory.
set -euo pipefail

usage() {
  echo "Usage: $0 --create --backup-dir /media/SSD250g/TROLLfx/ASR10/rollback-v1-YYYYMMDD [ssh-host]" >&2
  exit 2
}

[[ ${1:-} == --create ]] || usage
shift
[[ ${1:-} == --backup-dir ]] || usage
shift
backup_dir=${1:-}
shift || true
host=${1:-akai-force}
[[ $# -le 1 ]] || usage
[[ $backup_dir =~ ^/media/SSD250g/TROLLfx/ASR10/rollback-v1-[0-9]{8}$ ]] || usage

ssh "$host" sh -s -- "$backup_dir" <<'REMOTE'
set -eu
backup_root=$1
active_root='/media/SSD250g/VST2 Plugins/TROLLfx - VST - ASR10 FX Collection'
backup_parent="$backup_root"
backup="$backup_parent/TROLLfx - VST - ASR10 FX Collection"
expected='225aacdcd3a0a200f5851af924f0128b20f1ff6b4e8c354df343e804fe0d9de5'
assets='/media/SSD250g/TROLLfx/ASR10/factory-effects'

test -d "$active_root"
test ! -L "$active_root"
test ! -e "$backup_parent"
test "$(cat "$active_root/factory-assets-path.txt")" = "$assets"
test -d "$assets"
active_hash=$(sha256sum "$active_root/VST/asr10-fx-collection-arm32.so" | awk '{print $1}')
test "$active_hash" = "$expected"
test "$(find "$active_root" -type l | wc -l)" -eq 0
mkdir -p "$(dirname "$backup_parent")"
mkdir "$backup_parent"
cp -a "$active_root" "$backup_parent/"
(cd "$backup" && sha256sum -c SHA256SUMS >/dev/null)
cmp "$active_root/factory-assets-path.txt" "$backup/factory-assets-path.txt"
test "$(sha256sum "$backup/VST/asr10-fx-collection-arm32.so" | awk '{print $1}')" = "$expected"
test "$(find "$backup" -type f | wc -l)" -eq "$(find "$active_root" -type f | wc -l)"
case "$backup" in '/media/SSD250g/VST2 Plugins/'*) echo 'refused: backup is in plugin scan directory' >&2; exit 2;; esac
echo "backup=$backup"
echo 'checksums=PASS'
echo "arm32_sha256=$expected"
echo "asset_path=$(cat "$backup/factory-assets-path.txt")"
REMOTE
