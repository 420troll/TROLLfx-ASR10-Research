#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="$repo_root/build/audio-validation"
mkdir -p "$output_dir"
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -I"$repo_root/src" \
  "$repo_root/tools/audio_validation/clocked_es5510_replay.cpp" \
  "$repo_root/src/es5510.cpp" -o "$output_dir/clocked-es5510-replay"
printf 'Built %s\n' "$output_dir/clocked-es5510-replay"
