#!/usr/bin/env python3
"""Validate private HALL/ROM-02 evidence and emit an ephemeral native-test provider.

The generated header is written outside the repository and contains references to
local assets only. Validation must pass before any evidence flags are populated.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools/audio_validation/validate_factory_runtime_package.py"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def cxx(value: str) -> str:
    return json.dumps(str(value))

def package(effect: str, manifest: Path, checkpoint: Path, reference_root: Path, events: Path):
    cmd = [sys.executable, str(VALIDATOR), "--effect", effect, "--manifest", str(manifest),
           "--checkpoint", str(checkpoint), "--reference-root", str(reference_root),
           "--events", str(events)]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{effect} private package validation failed: {result.stderr.strip() or result.stdout.strip()}")
    receipt = json.loads(result.stdout)
    if receipt.get("valid") is not True or receipt.get("effect") != effect:
        raise RuntimeError(f"{effect} validator returned no affirmative effect-specific receipt")
    doc = json.loads(manifest.read_text())
    expected_id = "ROM-01" if effect == "hall" else "ROM-02"
    if doc.get("provenance", {}).get("effect_id") != expected_id or doc.get("provenance", {}).get("os_version") != "3.53":
        raise RuntimeError(f"{effect} manifest effect or OS identity does not match expected RUN package")
    if not doc.get("pipeline", {}).get("complete") or doc.get("pipeline", {}).get("status") != "reset_after_load":
        raise RuntimeError(f"{effect} manifest lacks pipeline-reset evidence")
    if not doc.get("lifecycle", {}).get("halt_before_load") or not doc.get("lifecycle", {}).get("run_after_load"):
        raise RuntimeError(f"{effect} manifest lacks HALT/load/RUN evidence")
    if doc.get("serial", {}).get("host_serial") != 0x48 or doc.get("serial", {}).get("input_ports") != [2] or doc.get("serial", {}).get("output_ports") != [1]:
        raise RuntimeError(f"{effect} serial routing is not the expected port-2 to port-1 route")
    capture_frame = doc.get("capture", {}).get("run_frame") if effect == "hall" else doc.get("observed_run", {}).get("absolute_frame")
    rate = doc.get("audio_clock", {}).get("esp_frame_rate_hz") if effect == "hall" else doc.get("observed_run", {}).get("clock", {}).get("dsp_rate_hz")
    if capture_frame is None:
        raise RuntimeError(f"{effect} manifest has no RUN frame")
    rate = float(rate)
    active_words = int(doc["program"]["active_words"])
    end_word = int(doc["program"]["end_word"])
    if active_words not in (89, 60) or end_word + 1 != active_words:
        raise RuntimeError(f"{effect} program geometry does not match known active factory program")
    event_rows = []
    with events.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"boundary_frame", "index", "value"}
        if not required.issubset(reader.fieldnames or []):
            raise RuntimeError(f"{effect} event schedule is missing frame/index/value fields")
        for row in reader:
            event_rows.append((int(row["boundary_frame"]) - int(capture_frame), int(row["index"], 16), int(row["value"], 16)))
    if not event_rows or len(event_rows) > 256 or any(a[0] < 0 or a[1] >= 0xC0 or a[2] > 0xFFFFFF for a in event_rows):
        raise RuntimeError(f"{effect} event schedule is empty, too large, or malformed")
    if event_rows != sorted(event_rows, key=lambda x: x[0]):
        raise RuntimeError(f"{effect} event schedule is not ordered by boundary frame")
    return {"effect": effect, "manifest": manifest.resolve(), "checkpoint": checkpoint.resolve(),
            "events": events.resolve(), "doc": doc, "frame": int(capture_frame), "rate": rate,
            "active_words": active_words, "end_word": end_word, "event_rows": event_rows,
            "checkpoint_sha": sha256(checkpoint), "events_sha": sha256(events), "manifest_sha": sha256(manifest),
            "receipt": receipt}

def emit(path: Path, packages: list[dict]) -> None:
    lines = ["// generated in /tmp after strict factory-runtime validation; do not commit",
             '#include "ES5510DSPBackend.h"', '#include <stdexcept>', '#include <string>', '#include <utility>',
             '#include "trollfx/es5510_factory_parameter_discovery_v02.hpp"',
             "namespace trollfx_test {", "using namespace trollfx::es5510;",
             "class Provider final : public IValidatedFactoryPackageProvider {",
             "public:", "  Provider() {" ]
    for p in packages:
        d = p["doc"]
        slot = 1 if p["effect"] == "hall" else 2
        name = d["provenance"]["effect_id"] + " " + d["provenance"]["effect_name"]
        label = "hall" if slot == 1 else "rom02"
        lines += ["    { ValidatedEffectPackage p;", "      auto& d=p.descriptor;",
          f"      d.slot={slot}; d.factory_name={cxx(name)}; d.active_program_words={p['active_words']}; d.end_word={p['end_word']};",
          f"      d.program_sha256={cxx(d['program']['sha256'])}; d.factory_reference_rate_hz={p['rate']:.12f};",
          "      d.routing.host_serial_mode=0x48; d.routing.input_port=2; d.routing.output_port=1; d.routing.stereo=true;",
          f"      d.package_manifest_path={cxx(str(p['manifest']))}; d.initialization_manifest_path={cxx(str(p['manifest']))};",
          f"      d.run_checkpoint_path={cxx(str(p['checkpoint']))}; d.run_checkpoint_sha256={cxx(p['checkpoint_sha'])};",
          f"      d.firmware_event_schedule_path={cxx(str(p['events']))}; d.firmware_event_schedule_sha256={cxx(p['events_sha'])};"]
        for frame, gpr, value in p["event_rows"]:
            lines.append(f"      d.firmware_event_schedule.push_back(ScheduledGprWrite{{{frame}ULL,{gpr},{value}u}});")
        lines += ["      parameter_discovery_v02::append_verified_parameters(d);",
                  "      p.validation_receipt_valid=true; p.initialization_state_valid=true;",
                  "      p.program_identity_valid=true; p.pipeline_reset_valid=true; p.routing_valid=true;",
                  f"      std::string error; if(!registry_.register_validated(std::move(p), &error)) throw std::runtime_error(error); }} // {label}"]
    lines += ["  }", "  const ValidatedEffectPackage* package_for_slot(EffectSlot slot) const noexcept override { return registry_.find(slot); }",
              "private: EffectRegistry registry_;", "};", "inline Provider make_provider() { return Provider{}; }", "}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hall-manifest", type=Path, required=True); ap.add_argument("--hall-checkpoint", type=Path, required=True)
    ap.add_argument("--hall-reference-root", type=Path, required=True); ap.add_argument("--hall-events", type=Path, required=True)
    ap.add_argument("--rom02-manifest", type=Path, required=True); ap.add_argument("--rom02-checkpoint", type=Path, required=True)
    ap.add_argument("--rom02-reference-root", type=Path, required=True); ap.add_argument("--rom02-events", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    for p in (a.hall_manifest,a.hall_checkpoint,a.hall_reference_root,a.hall_events,a.rom02_manifest,a.rom02_checkpoint,a.rom02_reference_root,a.rom02_events):
        if not p.exists(): raise RuntimeError(f"required private validation input missing: {p}")
    data = [package("hall",a.hall_manifest,a.hall_checkpoint,a.hall_reference_root,a.hall_events),
            package("rom02",a.rom02_manifest,a.rom02_checkpoint,a.rom02_reference_root,a.rom02_events)]
    emit(a.output,data)
    for p in data: print(f"{p['effect']}: strict validator PASS; {p['active_words']} program words; {len(p['event_rows'])} scheduled writes; {p['rate']:.6f} Hz; RUN frame {p['frame']}")
    print(f"ephemeral validated test provider: {a.output}")

if __name__ == "__main__":
    try: main()
    except (OSError,RuntimeError,ValueError,KeyError,json.JSONDecodeError) as exc:
        print(f"prepare-native-test-packages: ERROR: {exc}", file=sys.stderr); raise SystemExit(2)
