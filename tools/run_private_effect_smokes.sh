#!/bin/sh
# Reproducible private-asset CLI smoke test. All captures stay outside this repo.
set -eu

if [ "$#" -ne 3 ]; then
    echo "usage: $0 PRIVATE_ROM_DIR PRIVATE_OS353_IMG OUTPUT_DIR" >&2
    exit 2
fi

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
rom_dir=$(CDPATH= cd -- "$1" && pwd -P)
os_image=$(realpath -- "$2")
out_dir=$(realpath -m -- "$3")
cli="$repo/build/research-cli/asr10-cli"

case "$out_dir/" in
    "$repo/"*) echo "output must stay outside the Git repository" >&2; exit 2 ;;
esac
[ -x "$cli" ] || { echo "native CLI missing; build it first: $cli" >&2; exit 2; }
[ -f "$rom_dir/asr-648c-lo-1.5b.bin" ] || { echo "missing low ASR boot ROM" >&2; exit 2; }
[ -f "$rom_dir/asr-65e0-hi-1.5b.bin" ] || { echo "missing high ASR boot ROM" >&2; exit 2; }
[ -f "$os_image" ] || { echo "missing OS 3.53 image" >&2; exit 2; }
[ "$(wc -c < "$os_image" | tr -d ' ')" -eq 1638400 ] || { echo "OS image size is not 1,638,400 bytes" >&2; exit 2; }
mkdir -p "$out_dir"

run_one() {
    label=$1 seconds=$2 expected_display=$3 expected_words=$4
    shift 4
    ASR_ROUTE=-1,-1,1,-1,0 ASR_TEST_SINE=440:0.25 ESP_HOSTLOG=1 \
        "$cli" --roms "$rom_dir" --disk "$os_image" --seconds "$seconds" "$@" \
        --wav "$out_dir/$label.wav" --esp-list --esp-dump "$out_dir/$label.esp" \
        > "$out_dir/$label.log" 2>&1
    grep -F "$expected_display" "$out_dir/$label.log" >/dev/null || {
        echo "$label: expected effect-selection display not found" >&2; exit 1;
    }
    python3 "$repo/tools/esp_capture.py" "$out_dir/$label.esp" > "$out_dir/$label-summary.json"
    python3 - "$out_dir/$label-summary.json" "$out_dir/$label.wav" "$expected_words" <<'PY'
import json, math, struct, sys, wave
summary=json.load(open(sys.argv[1], encoding="utf-8"))
expected=int(sys.argv[3])
if summary["program"]["active_words_through_first_END"] != expected:
    raise SystemExit(f"expected {expected} active instructions")
if summary["runtime"]["control"]["halted"]:
    raise SystemExit("DSP was halted at capture time")
with wave.open(sys.argv[2], "rb") as wav:
    if (wav.getframerate(),wav.getnchannels(),wav.getsampwidth()) != (44100,2,2):
        raise SystemExit("expected 44.1 kHz stereo PCM16")
    raw=wav.readframes(wav.getnframes())
    samples=struct.unpack("<%dh"%(len(raw)//2),raw)
    peak=max(map(abs,samples),default=0)
    rms=math.sqrt(sum(x*x for x in samples)/len(samples)) if samples else 0
    if peak == 0 or not any(samples):
        raise SystemExit("render is silent")
print(json.dumps({"instructions":expected,"frames":wav.getnframes(),"peak":peak,"rms":round(rms,3),"capture_sha256":summary["file_sha256"],"program_sha256":summary["program"]["active_program_sha256"]}))
PY
    sha256sum "$out_dir/$label.wav" "$out_dir/$label.esp" > "$out_dir/$label.sha256"
}

run_one 44DDL-CHORUS 25 'FINAL |DISK COMMAND COMPLETED|' 60 \
    --button 15:9:1 --button 15.2:9:0 --button 15.5:35:1 --button 15.7:35:0
grep -F 'FILE 1  44DDL+CHORUS' "$out_dir/44DDL-CHORUS.log" >/dev/null || {
    echo "44DDL-CHORUS: effect name was not displayed during selection" >&2; exit 1;
}
run_one ROM01-HALL 22 'FINAL |FX=INST    HALL REVERB|' 89 \
    --button 15:7:1 --button 15.2:7:0
echo "Private CLI effect tests passed. Captures and WAVs: $out_dir"
