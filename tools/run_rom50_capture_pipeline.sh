#!/bin/sh
# Reproducible, resumable private ROM-effect inventory and capture run.
set -eu

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "usage: $0 PRIVATE_ROM_DIR OS353_IMAGE PRIVATE_OUTPUT_DIR [NATIVE_CLI]" >&2
    exit 2
fi

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
rom_dir=$(CDPATH= cd -- "$1" && pwd -P)
os_image=$(realpath -- "$2")
out=$(realpath -m -- "$3")
cli=${4:-$repo/build/research-cli/asr10-cli}
case "$out/" in
    "$repo/"*) echo "private output must remain outside the Git repository" >&2; exit 2 ;;
esac

needs_build=0
if [ ! -x "$cli" ]; then
    needs_build=1
else
    for source in "$repo"/src/*.cpp "$repo"/src/*.h; do
        if [ -f "$source" ] && [ "$source" -nt "$cli" ]; then
            needs_build=1
            break
        fi
    done
fi
if [ "$needs_build" -eq 1 ]; then
    "$repo/tools/build_research_cli.sh"
fi
mkdir -p "$out"
python3 "$repo/tools/capture_asr10_rom_effects.py" enumerate \
    --cli "$cli" --rom-dir "$rom_dir" --os-image "$os_image" --output "$out"
ESP_PIPELOG=1 python3 "$repo/tools/capture_asr10_rom_effects.py" capture-sweep \
    --cli "$cli" --rom-dir "$rom_dir" --os-image "$os_image" \
    --output "$out" --inventory "$out/inventory.json"
python3 "$repo/tools/package_rom_effect_collection.py" \
    --source "$out" --inventory "$out/inventory.json" \
    --output "$out/validated-packages" \
    --catalog "$repo/docs/ASR10_ROM_EFFECT_CATALOG.json"
