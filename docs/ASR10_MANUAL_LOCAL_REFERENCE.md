# ASR-10 Musician's Manual — local reference source

**Document:** *Ensoniq ASR-10 Musician's Manual* (copyright © 1992 Ensoniq); attached copy: `23583406(1).pdf`.

**Verification (the user-supplied copy):**
- SHA-256: `e8ab5100904caf91fe355065ed9646aff197761b0663a7d452dc98af1f9a29dc`
- PDF pages: **391**
- File size: **1,093,049 bytes**
- Title metadata: `Ensoniq ASR-10`
- The PDF is **not** included in this public source repo. Copyright remains with the applicable rights holder; do not redistribute the complete manual unless you have appropriate rights or permission.

## Local access

For WSL/Codex running on the user's Windows desktop, first **locate** the user's copy (previous sessions reported `/mnt/c/Users/Gamer/Downloads/23583406.pdf`; do not assume that path is current). The matching attached chat copy was named `23583406(1).pdf`.

Verify the actual copy before using it:

```sh
sha256sum '/path/to/23583406.pdf'
pdfinfo '/path/to/23583406.pdf' | grep Pages
```

Expected hash above. If the hash differs, treat it as another edition/scan and document that provenance rather than silently mixing page numbering and parameter ranges.

Set a shared local path without checking the PDF into Git:

```sh
export TROLLFX_ASR10_MANUAL_PDF='/absolute/path/to/23583406.pdf'
test -r "$TROLLFX_ASR10_MANUAL_PDF" && sha256sum "$TROLLFX_ASR10_MANUAL_PDF"
```

For the three Codex agents, prefer a single **read-only desktop/WSL file** through the above environment variable rather than three stale manual copies in separate worktrees. Never include the PDF in release ZIPs or on-Force package assets.

## High-value study map (PDF pagination differs from printed page numbers)

- **Section 5 — Effect Concepts:** instrument, bank, ROM effect ownership; four variations; dual modulation destinations per variation; BUS1/2/3 and AUX dry routing; reloading/reset/selection semantics; sample-rate/voice-count behavior.
- **Section 6 — Effect Parameters:** 50 factory ROM algorithms with displayed ranges, named controls, variation effects and bus behavior. Parameter labels/ranges are not sufficient to establish the true original OS raw code, ordered GPR writes or VST mapping.
- **Appendix — Additional 44 kHz Effect Descriptions:** 12 additional disk/OS effects; treat as separate inventory from the 50 ROM factory effect slots.
- **Appendix — MIDI Implementation:** registered parameters and MIDI conventions; do not assume all original effect editing is addressable through the current VST2 parameter interface.
- **Command/Effects and save/load sections:** saving instrument/bank effects and copying/editing ROM effects; important for original semantics and future preset modelling.

## Required provenance for extracted findings

For each manual-derived control/effect record store: source PDF SHA, PDF page index **and printed section/page**, algorithm name/slot, parameter name, printed range/units, description, manual edition, and evidence grade. Add original OS code address, raw editor state, original ROM sample rate, ordered DSP GPR group and audio test results only when separately demonstrated; never infer them from the manual's wording alone.

**Implementation boundaries:** The actual Akai Force FX Collection VST2 is not the complete ASR-10 instrument emulator. It may intentionally omit instrument/bank ownership, voice polyphony, or original MIDI semantics. Keep those as research requirements unless explicitly adopted as plugin features.

**Project coordination:** [Master handoff](TROLLFX_ASR10_CODEX_MASTER_HANDOFF.md), [architecture audit](TROLLFX_ASR10_ARCHITECTURE_WORKFLOW_AUDIT_V1.md), [test policy](TROLLFX_ASR10_TEST_POLICY_V1.md).

## Distribution status

This page records a **locally held user-provided reference**, not a grant to publish the copyrighted manual. If a legitimately redistributable edition or permission is established, it can be added to the repo in a later independent, appropriately licensed step.
