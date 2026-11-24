#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
sh "$root/tools/build_experimental_audio_host.sh"
"$root/build/experimental-audio-host/experimental-audio-host-test"
python3 -m unittest tests.test_experimental_audio_host_cli -v
