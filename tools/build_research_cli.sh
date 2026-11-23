#!/bin/sh
# Build only the native headless ASR-10 CLI; does not build MAME or the VST.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
build="$repo/build/research-cli"
mkdir -p "$build"

for src in m68kcpu m68kops m68kdasm; do
    gcc -O2 -I"$repo/musashi" -I"$repo/musashi/softfloat" -I"$repo/src" \
        -c "$repo/musashi/$src.c" -o "$build/$src.o"
done
gcc -O2 -I"$repo/musashi" -I"$repo/musashi/softfloat" -I"$repo/src" \
    -c "$repo/musashi/softfloat/softfloat.c" -o "$build/softfloat.o"

for src in cli asr10 dac_out m68302 duart fdc es5506 es5510 panel scsi efe_disk; do
    g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic \
        -I"$repo/src" -I"$repo/musashi" \
        -c "$repo/src/$src.cpp" -o "$build/$src.o"
done

g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic \
    "$build/cli.o" "$build/asr10.o" "$build/dac_out.o" "$build/m68302.o" \
    "$build/duart.o" "$build/fdc.o" "$build/es5506.o" "$build/es5510.o" \
    "$build/panel.o" "$build/scsi.o" "$build/efe_disk.o" \
    "$build/m68kcpu.o" "$build/m68kops.o" "$build/m68kdasm.o" "$build/softfloat.o" \
    -o "$build/asr10-cli"
echo "Built $build/asr10-cli"
