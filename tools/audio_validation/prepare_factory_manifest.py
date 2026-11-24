#!/usr/bin/env python3
"""Build a private factory-state manifest from two verified OS RUN captures."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
from factory_replay_profiles import PROFILES
from replay_factory_from_boundary import correlate_source_efe, event_fingerprint, read_run, write_manifest


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile", choices=sorted(PROFILES))
    p.add_argument("reference_root", type=Path, help="private directory containing boot-a and boot-b")
    p.add_argument("--run-frame", required=True, type=int)
    p.add_argument("--efe-object", type=Path, help="private source EFE required for ROM profiles with source correlation")
    p.add_argument("--out", required=True, type=Path, help="private directory for manifest and payload sections")
    a = p.parse_args()
    out = a.out.expanduser().resolve()
    if out == ROOT or ROOT in out.parents:
        p.error("manifest and payload outputs must stay outside the checkout")
    profile = PROFILES[a.profile]
    root = a.reference_root.resolve(strict=True)
    boots = [read_run(root / f"boot-{x}", a.run_frame, 32768, profile) for x in ("a", "b")]
    first, second = boots
    if first["snapshot"].read_bytes() != second["snapshot"].read_bytes():
        raise SystemExit("fresh RUN checkpoints differ")
    if event_fingerprint(first) != event_fingerprint(second):
        raise SystemExit("fresh startup/load histories differ")
    if first["updates"] != second["updates"]:
        raise SystemExit("fresh post-RUN firmware histories differ")
    if first["inputs"] != second["inputs"] or first["outputs"] != second["outputs"]:
        raise SystemExit("fresh DSP serial references differ")
    if first["host_wav"].read_bytes() != second["host_wav"].read_bytes():
        raise SystemExit("fresh host WAV references differ")
    if profile.get("program_sha256"):
        if not a.efe_object:
            p.error("this effect profile requires its private source EFE object")
        first["source_correlation"] = correlate_source_efe(first, profile, a.efe_object)
    manifest = write_manifest(first, a.profile, out)
    print(f"prepared replay-ready private manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
