# TROLLfx ASR-10 Force Hardware QA and Release V3

Status: V1 hardware baseline recorded; V3 integration and physical effect testing are pending.

## Baseline: original Akai Force

The following observations came from a read-only `ssh akai-force` inspection on 2026-11-24. The command is available as `tools/force_hardware/read_only_baseline.sh akai-force`; it reads OS, CPU, memory, mount, package hashes, package counts and one CPU snapshot. It does not copy files, remount, restart, or change device state.

| Item | Observation |
| --- | --- |
| OS image | az0x base 5.0.18 (scarthgap), `/etc/version` `20261106132031` |
| Kernel / architecture | Linux 6.18.44-az01-2026-08-10-rt6, ARMv7, PREEMPT_RT; 4 CPU cores |
| MPC process | `/usr/bin/MPC`, process label `MPC 3 Main`; exact MPC application version was not exposed by this shell inspection |
| RAM | 2,065,132 kB total; 1,193,072 kB available at inspection; no swap |
| SSD | `/media/SSD250g`, exFAT, 223.6 GiB total / 175.6 GiB available (21% used) |
| Root / synth partition | `/` 96% used, 16.6 MB available; `/synths` 100% used, no available space |
| SSD mount flags | `rw,nosuid,nodev,relatime,nosymfollow,...`; `noexec` was absent in this inspection. No mount option was changed. |
| Installed plugin | `/media/SSD250g/VST2 Plugins/TROLLfx - VST - ASR10 FX Collection/` |
| Factory assets | `/media/SSD250g/TROLLfx/ASR10/factory-effects/`; plugin sidecar points to this exact directory |
| Asset inventory | 202 files: 50 manifests, 50 RUN checkpoints, provider index with 50 entries plus header; aggregate tree SHA-256 `d110fc562a21a932849521e34073e813ce9a00255a62b99fdb39467842b9783d` |
| Installed ARMv7 VST | SHA-256 `225aacdcd3a0a200f5851af924f0128b20f1ff6b4e8c354df343e804fe0d9de5`; installed package `SHA256SUMS` passed |
| Other plugin folders | 11 directories under the VST2 root; no `.rollback-*` folder existed at inspection |

The user reports that MPC discovered V1, loaded the SSD factory data and produced wet audio. The user also provided MPC CPU snapshots of 20%, 18% and 17%, with 80–81% system idle. The independent one-shot snapshot showed MPC at 17%, 16% user CPU + 2% system CPU overall, 80% idle and 1.38/1.20/1.01 load averages. These are aggregate measurements; none proves callback deadline safety or absence of occasional dropouts.

No controlled bypass-versus-enabled recording was available to this inspection. The V1 wet-audio confirmation is user-observed, not a controlled A/B result. No per-effect physical tests were supplied; all 50 matrix rows therefore remain `NOT_RUN`.

### Storage and rollback constraints

Keep both plugin and private packages on the SSD at the exact paths above. Leave root and `/synths` untouched. Do not change mount options: this inspection observed no `noexec`, and the user has confirmed the SSD-installed plugin loads. Never replace another plugin folder or restart MPC automatically.

#### V1 rollback copy created 2026-11-25

With the user's authorization in this follow-up, a non-destructive copy of the installed V1 package was created at:

`/media/SSD250g/TROLLfx/ASR10/rollback-v1-20261125/TROLLfx - VST - ASR10 FX Collection/`

It is outside `/media/SSD250g/VST2 Plugins/`, so MPC's VST2 scan cannot discover it as another plugin. The copy contains 21 files. Its `SHA256SUMS` validation passed; `factory-assets-path.txt` is byte-identical to the active install and still points to `/media/SSD250g/TROLLfx/ASR10/factory-effects`; its ARMv7 SHA-256 is `225aacdcd3a0a200f5851af924f0128b20f1ff6b4e8c354df343e804fe0d9de5`, matching the active V1 binary. The private package directory was not copied or modified; the configuration points to the existing 50-package SSD collection.

For a future V1 snapshot, the explicit-copy helper requires `--create`, accepts only a dated rollback path under `/media/SSD250g/TROLLfx/ASR10/`, refuses overwrite, checks the known V1 binary hash, copies the active package and validates checksums and the asset-path sidecar:

```sh
tools/force_hardware/create_v1_backup.sh --create \\
  --backup-dir /media/SSD250g/TROLLfx/ASR10/rollback-v1-YYYYMMDD akai-force
```

The copy is not an installer and does not mutate the active plugin. To recheck the existing copy manually:

```sh
ssh akai-force 'cd "/media/SSD250g/TROLLfx/ASR10/rollback-v1-20261125/TROLLfx - VST - ASR10 FX Collection" && sha256sum -c SHA256SUMS && cat factory-assets-path.txt && sha256sum VST/asr10-fx-collection-arm32.so'
```

No V1 restore was performed. Any future restore requires MPC closed and explicit user authorization; do not simply copy over an active plugin directory.

### Controlled CPU comparison procedure

`tools/force_hardware/measure_force_cpu.sh` samples the MPC process and system idle percentage from read-only BusyBox `top` output over SSH. It prompts the operator to set each state manually, warms up for 15 seconds, and then records 60 one-second samples by default for plugin bypass, HALL REVERB, 8-VOICE CHOR and PITCH SHIFT. Keep the same project, audio loop, routing, buffer, gain and playback level throughout. Use the Force touchscreen for state selection; the script does not send controls or write to the device. Output is a new local CSV, and the script refuses to overwrite it.

```sh
tools/force_hardware/measure_force_cpu.sh akai-force 60 1 15 force-cpu-comparison.csv
```

Each row records state, sample number, MPC `%CPU` and system `%idle`. Run the comparison only during a controlled session with steady playback; note audio glitches and timing separately. This is process/system load evidence, not callback deadline or audio quality proof. No controlled CPU comparison has yet been run, so there are no per-state results to report.

## V1 desktop package checks

At the supplied V1 integration commit `5910f54`, the release package's SDK validation reported zero errors and zero warnings. The candidate contained ARM32 ELF32 ARMv7 hard-float and AArch64 binaries; the ARM32 maximum GLIBC requirement was 2.27. VSTPluginMain was exported, UI images and Q-Link resources validated, and the ARM32 package hash matches the hash independently read from the Force. These are desktop/package checks, not a new physical V3 validation.

The current published integration branch has moved to `d8f6c29341cc51523fe7a9e16f3be570e9321c1c` (“Package V2 verified parameter controls and ARMv7 evidence”). A fresh remote branch check on 2026-11-25 still found no V3/per-effect-editor branch or commit. Release integration remains on hold until Codex 2 publishes the committed GUI branch. No V3 binary was built, no V3 editor/Q-Link behavior was tested, and V1's playable marker must not be copied to any changed binary.

## Systematic physical procedure for all 50 effects

Use `ASR10_FORCE_HARDWARE_TEST_MATRIX_V3.csv` as the run log. It is generated from the canonical 1–50 `force_plugin/effects.json` list and deliberately initializes every result as `NOT_RUN`. Select a quiet, fixed monitoring level and a repeatable stereo test session, record the MPC project/session identifier privately, and do not overwrite the user's production project.

For each slot:

1. Confirm the displayed slot and original factory name, package availability, and loaded-state indication. Record any load error; never treat a browser selection as proof of processing.
2. With one fixed repeatable input passage, capture enabled and bypass audio at matched host gain. Record peak/RMS and listen for wet output, noise, abrupt level changes and tails. Keep input, output gain, wet/dry, host routing and monitoring level fixed across the pair.
3. Repeat separately with left-only, right-only, then stereo input to identify channel loss, cross-feed and image collapse. Record output peak and channel correlation or a short stereo recording for later comparison.
4. Run a two-minute sustained passage, then switch away and back three times. Note clicks, dropouts, tail handling, state reset/continuity, and any UI freeze. Do not claim click-free behavior without listening/recording evidence.
5. Save the host project, close/reopen it, and verify effect identity, verified parameters, host controls and sound. Record which state restored and which did not.
6. Record peak MPC CPU and system idle during the steady section and switching. Use an audio loopback or external recording and, if available, callback xruns/dropout counters. Aggregate CPU alone is not a real-time safety test.
7. Change only parameter points supported by the validated mapping evidence for that active effect. Record actual UI value and measured response. Mark all undocumented or untested parameter mappings unresolved; do not infer mappings from labels.

Suggested coverage order: slot 1 HALL; slot 2 ROM-02; slots 3, 6–7, 14–24 reverbs and combinations; slots 4–5 and 25–26, 33–37, 40 delays; slots 8–10, 12, 33–41 modulation/pitch combinations; slots 11, 13, 27–32 drive/filter/amp; slots 42–47 dynamics; slots 48–50 filter/EQ/other. The CSV includes the exact slot name for every row. Multi-effect entries should be reported as the named combination, not as isolated component coverage.

## V3 release gates

Before a new binary can be called playable, independently verify all of the following against the exact candidate build:

- all 50 private package manifests, RUN checkpoints, identities, routing and scheduled events; retain private payloads outside Git;
- every parameter mapping and control range shown by the editor, with unsupported/unresolved parameters clearly unavailable;
- GUI generation, slot selection, unavailable state, Q-Link assignment and Q-Link behavior for each active parameter page;
- host save/restore of active slot, verified parameters and host controls;
- native VST binary-bound HALL and ROM-02 audio tests plus the full per-slot test catalog's supported playback cases;
- callback allocation/file-I/O audit and switching/audio continuity tests;
- freshly compiled ARMv7 hard-float ABI, dependencies, symbols, SDK validation and checksums;
- fresh marker and release manifest bound to the new ARMv7 binary SHA-256. Never reuse V1's marker or binary hash.

Physical tests remain a separate gate. Desktop pass results do not imply Force hardware verification. Keep the V1 binary and assets as the rollback baseline until V3 has been physically exercised and accepted.

## Deployment policy

No V3 replacement was attempted. Do not install during an active MPC session, do not restart MPC, and do not alter mount options. After every desktop gate passes and the user explicitly authorizes replacement, use the verified local-to-SSD deployment procedure for the exact candidate: validate the package locally, check SSD mount and free space, stage only under `/media/SSD250g`, verify staged checksums, verify the current V1 hash, preserve V1 under a timestamped rollback name, atomically switch only the TROLLfx directory, then verify the new hash and asset sidecar. Keep `/media/SSD250g/TROLLfx/ASR10/factory-effects` untouched. The manually created dated V1 copy above is a separate recovery baseline and remains outside the plugin scan path. Reversal is a manual rename of the V3 folder aside and the preserved V1 folder back to the exact plugin path; restart MPC only after the session is closed and the user chooses to do so.

The V1 Python installer/rollback wrappers are development-host tools and are not suitable as Force commands because the Force shell did not expose Python. Exact V3 SCP/SSH replacement commands will be generated only for the final, checksummed candidate so paths and hashes are bound to the artifact that passed the gates. No such candidate exists yet.
