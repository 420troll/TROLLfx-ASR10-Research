# ES5510 ROM-02 Reference Provenance v1

## Finding

The historical ROM-02 reference is reproducible, but its original runtime environment cannot be authenticated retrospectively. The older capture logs contain no emulator executable hash, OS disk hash, or boot ROM hashes. Their file paths and scripts point to a WSL/Linux x86-64 setup using Windows-mounted assets; that attribution is an inference. A later CLI found in the old replay worktree has SHA-256 `9aaa2df71b6d1cc794ba818551e0b67d4e9c6c5a5012075340d89e3036464cc8`, but there is no evidence binding that binary to the original process.

This work creates a fresh, fully bound reference dataset. Two independent OS 3.53 boots were captured from the clean worktree commit recorded below. The existing 32,768-frame exact numerical verification was not repeated. The fresh capture checkpoint, rendered WAV, and host-output map match the prior reference byte for byte.

## Reference environment and inputs

The capture ran in Ubuntu 24.04.5 LTS under WSL2, x86-64 (`Linux 6.18.58.1-microsoft-standard-WSL2`), with Python 3.12.3 and `x86_64-linux-gnu-g++-13` 13.3.0. The source worktree was clean at commit `35723427640ffc9c68fbb8c74f6c10f78872eb24`; the built `asr10-cli` SHA-256 is `9aaa2df71b6d1cc794ba818551e0b67d4e9c6c5a5012075340d89e3036464cc8`.

All input material remains outside Git. The receipt records the absolute paths, byte counts, and hashes:

| Input | SHA-256 |
| --- | --- |
| OS 3.53 disk image | `335838dcf96dcec6e7fc2db4d671e2ac5075976999762beef74f472b439a98e9` |
| Low boot ROM | `94312f142db5b307bf31fbcc9b46e54197460f691596465d24870aa579a892fc` |
| High boot ROM | `d3f4863d74b44e85de69432e1618dc9b1df7dcdefe7c79f81af2b7990e0e16eb` |
| Private ROM-02 EFE source | `21562a079f5e1bf3d14cfeebfd9a7ef1afc0e5cb0edff788e4308d3552186f75` |
| Built emulator CLI | `9aaa2df71b6d1cc794ba818551e0b67d4e9c6c5a5012075340d89e3036464cc8` |

## Program and capture result

The private EFE source correlates with the runtime capture as `44KHZ REVERB`: 60 active instruction matches, 58 paired GPR initializers, matching source pair values, one ROM-02 source alias, and one instruction-only source record. The active program hash is `12119e86d4d232ab7d7ab4278e9c9dbed9db19a6b6eb352bfb29441181da4486`; program bytes are 360 bytes. These counts and hashes identify the program without publishing its proprietary words or EFE payload.

Each fresh process captured the state at source frame 905028 and 32,768 DSP frames. Process IDs were 11732 and 11819. The two boots had identical checkpoint snapshots, host-output maps, rendered WAVs, serial input and output traces, startup event summaries, post-RUN event summaries, and EFE correlations. The complete session logs are retained separately and are not byte-identical.

| Artifact | SHA-256 | Size |
| --- | --- | ---: |
| Factory checkpoint `run-frame-905028.esp` | `12e34452bd0c1b1285483b36a9b3a0ada02a24e18dd1fc9ca46933bc6428e2cd` | 2,098,872 |
| Rendered WAV (both boots) | `29a191bd58cc084e918e2e1ee58ef17d2c14b63554fd01bfa4b70159c003fd53` | 5,331,944 |
| Host-output map (both boots) | `a51c85c4b7747c11ff4529eccc425e4354501dee8a03a3788c197a0852717942` | 2,350,617 |
| Replay manifest `factory-state.json` | `6fa52cafda846b961ca20d3a88f1a06597d18840ade05ac7e8fa085e54f692b2` | 3,004 |
| Replay program bytes (private) | `12119e86d4d232ab7d7ab4278e9c9dbed9db19a6b6eb352bfb29441181da4486` | 360 |
| Replay GPR bytes (private) | `23c5b7ff6be9690cc49aa96485d87692b52a40645ddf43980835e231f65b03c4` | 576 |
| Replay special-register bytes (private) | `12579ae05ae60e7584fd624033f92887409bd00adcf0655cc8b6dab1fd9409cd` | 66 |

Full host logs, snapshots, WAVs, the private EFE, ROMs, and replay payloads stay under `/home/gamer/research/private-results/rom02-provenance-v1-reference`. `provenance.json` records every output size/hash, both process invocations and controlled environments, compiler and executable details, input hashes, source-tree file hashes, and validation outcomes. It is deliberately not committed because it contains machine-local paths and private capture metadata. The validator reported `valid: true`, two boots, and 12 output artifacts.

## Reproduce and verify

From a clean checkout with the private inputs available at the paths above, run:

```sh
python3 tools/audio_validation/capture_factory_reference.py \
  rom02-44khz-reverb-v1 \
  --roms /mnt/c/Users/Gamer/research/asr10emu-evaluation/ASR10-Windows/roms \
  --disk /mnt/c/Users/Gamer/research/asr10emu-evaluation/ASR10-Windows/roms/os353.img \
  --run-frame 905028 \
  --out /home/gamer/research/private-results/rom02-provenance-v1-reference \
  --efe-object /mnt/c/Users/Gamer/research/private-results/rom-to-efe-20261123/ROM02-44KHZ.payload.bin

python3 tools/audio_validation/verify_reference_provenance.py \
  /home/gamer/research/private-results/rom02-provenance-v1-reference/provenance.json
```

The capture builds the CLI from the recorded worktree, performs two independent cold boots with controlled environment variables, emits the private replay manifest, and verifies input, source-tree, process, and output hashes. The receipt verifier checks the recorded source file hashes against the exact captured Git commit, so later documentation commits do not invalidate the receipt. It also reports any changed or missing input/output or reused boot process ID.

## Remaining provenance limit

The new dataset binds the runtime reference to its exact modern capture environment and inputs. It does not retroactively prove which executable or assets produced the older reference. That old-process identity remains unavailable because the historic logs omitted those hashes. The byte-identical checkpoint, WAV, and host-output map provide a direct artifact-level link between the old reference and this new reproducible capture.
