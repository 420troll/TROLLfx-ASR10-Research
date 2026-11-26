#!/usr/bin/env python3
"""Run HALL 40/41 startup-ownership comparisons against an authorized local package.

The tool validates the local provider audit and payload hashes, then compiles a
temporary copy of FactoryRuntime with a read-only register accessor. It writes
no private assets or audio and never edits the production runtime tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = (Path.home() / "research/private-results/asr10-all-50-effects/"
                 "production-provider-audit.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--runtime-root", type=Path, default=ROOT,
                        help="source tree to copy into a temporary QA build")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text())
    row = next((item for item in audit["slots"] if item.get("slot") == 1), None)
    if row is None or not row.get("registry_eligible") or not row.get("capture_state_valid") or not row.get("checkpoint_is_at_run_boundary"):
        raise SystemExit("private audit does not authorize the HALL RUN package")
    descriptor = row["descriptor"]
    if descriptor.get("active_program_words") != 89 or descriptor.get("factory_name") != "HALL REVERB":
        raise SystemExit("private audit identifies a different active effect")
    checkpoint = Path(descriptor["run_checkpoint_path"]).resolve(strict=True)
    schedule = Path(descriptor["firmware_event_schedule_path"]).resolve(strict=True)
    variation = int(descriptor.get("factory_variation", 0))
    if not 0 <= variation <= 4:
        raise SystemExit("private audit contains an invalid HALL variation identity")
    if sha256(checkpoint) != descriptor["run_checkpoint_sha256"]:
        raise SystemExit("private HALL checkpoint digest mismatch")
    if sha256(schedule) != descriptor["firmware_event_schedule_sha256"]:
        raise SystemExit("private HALL schedule digest mismatch")

    source_root = args.runtime_root.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="hall-startup-ownership-") as temp:
        temp_root = Path(temp)
        include = temp_root / "include"
        source = temp_root / "src"
        shutil.copytree(source_root / "include", include)
        source.mkdir()
        for name in ("es5510_factory_runtime.cpp", "es5510.cpp", "es5510.h", "es5510_capture.h"):
            shutil.copy2(source_root / "src" / name, source / name)

        header = include / "trollfx/es5510_factory_runtime.hpp"
        contents = header.read_text()
        marker = "    RuntimeStatus getStatus() const noexcept;"
        if contents.count(marker) != 1:
            raise SystemExit("runtime public-header shape changed; refusing test instrumentation")
        header.write_text(contents.replace(marker, marker +
            "\n    std::uint32_t qaReadRegister(std::uint8_t index) const noexcept;"))

        runtime_cpp = source / "es5510_factory_runtime.cpp"
        contents = runtime_cpp.read_text()
        marker = "} // namespace trollfx::es5510"
        if contents.count(marker) != 1:
            raise SystemExit("runtime namespace marker is ambiguous")
        accessor = ("std::uint32_t FactoryRuntime::qaReadRegister(std::uint8_t index) const noexcept {\n"
                    "    return impl_->dsp.register_value(index);\n}\n\n")
        runtime_cpp.write_text(contents.replace(marker, accessor + marker))

        binary = temp_root / "hall-startup-ownership"
        command = [os.environ.get("CXX", "c++"), "-std=c++17", "-O2", "-Wall", "-Wextra",
                   "-Wpedantic", "-I" + str(include), "-I" + str(source),
                   str(source_root / "tools/audio_validation/hall_startup_ownership.cpp"),
                   str(runtime_cpp), str(source / "es5510.cpp"), "-o", str(binary)]
        subprocess.run(command, check=True)
        run = subprocess.run([str(binary), str(checkpoint), str(schedule),
            descriptor["program_sha256"], descriptor["run_checkpoint_sha256"],
            str(descriptor["factory_reference_rate_hz"]), str(variation)], check=True, text=True,
            stdout=subprocess.PIPE)
        print(run.stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
