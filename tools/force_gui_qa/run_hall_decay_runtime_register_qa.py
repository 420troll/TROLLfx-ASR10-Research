#!/usr/bin/env python3
"""Compare runtime GPR state against two independent original-OS sweeps.

The private trace files and runtime source directory are inputs. A temporary
copy of the published runtime is instrumented with one read-only register
accessor; no Codex 1 source/worktree is modified. Only the aggregate test
result is printed. The expected GPR map comes exclusively from OS write logs.
"""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from audit_hall_decay_raw_domain import read_sweep


def os_register_map(trace_paths):
    expected = {}
    for path in trace_paths:
        _, directions, order_failures = read_sweep(path)
        if order_failures:
            raise ValueError(f"OS trace has {order_failures} ordered-write group failures")
        for direction in ("up", "down"):
            for display, group in directions[direction].items():
                raw = (group[0x6E] >> 16) & 0x7F
                values = tuple(group[index] for index in (0x6E, 0x5B, 0x03, 0x04, 0x05))
                if raw in expected and expected[raw] != values:
                    raise ValueError(f"original-OS traces disagree for raw code {raw}")
                expected[raw] = values
    if set(expected) != set(range(128)):
        raise ValueError(f"OS traces expose {len(expected)}/128 raw codes")
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True,
                        help="published Codex 1 source tree to copy and instrument temporarily")
    parser.add_argument("--trace-a", type=Path, required=True)
    parser.add_argument("--trace-b", type=Path, required=True)
    args = parser.parse_args()

    source_root = args.runtime_root.resolve()
    expected = os_register_map((args.trace_a, args.trace_b))
    with tempfile.TemporaryDirectory(prefix="hall-runtime-register-qa-") as tmp:
        tmp = Path(tmp)
        include = tmp / "include"
        src = tmp / "src"
        shutil.copytree(source_root / "include", include)
        src.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / "src/es5510_factory_runtime.cpp", src / "es5510_factory_runtime.cpp")
        shutil.copy2(source_root / "src/es5510.cpp", src / "es5510.cpp")
        shutil.copy2(source_root / "src/es5510.h", src / "es5510.h")
        shutil.copy2(source_root / "src/es5510_capture.h", src / "es5510_capture.h")

        header = include / "trollfx/es5510_factory_runtime.hpp"
        text = header.read_text()
        marker = "    RuntimeStatus getStatus() const noexcept;"
        if text.count(marker) != 1:
            raise RuntimeError("published runtime header shape changed; refusing an unsafe temporary edit")
        header.write_text(text.replace(marker, marker +
            "\n    std::uint32_t qaReadRegister(std::uint8_t index) const noexcept;"))

        runtime_cpp = src / "es5510_factory_runtime.cpp"
        text = runtime_cpp.read_text()
        marker = "} // namespace trollfx::es5510"
        if text.count(marker) != 1:
            raise RuntimeError("published runtime source namespace marker is ambiguous")
        accessor = ("std::uint32_t FactoryRuntime::qaReadRegister(std::uint8_t index) const noexcept {\n"
                    "    return impl_->dsp.register_value(index);\n}\n\n")
        runtime_cpp.write_text(text.replace(marker, accessor + marker))

        expected_csv = tmp / "os-gpr-by-raw.csv"
        with expected_csv.open("w") as stream:
            for raw in range(128):
                stream.write(f"{raw}," + ",".join(f"{v:06x}" for v in expected[raw]) + "\n")

        binary = tmp / "hall-runtime-register-qa"
        test = Path(__file__).resolve().parents[2] / "tests/force_gui_qa/test_hall_decay_runtime_independent.cpp"
        compiler = os.environ.get("CXX", "g++")
        command = [compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Wpedantic",
                   "-DTROLLFX_QA_REGISTER_ACCESS", f"-I{include}", f"-I{src}",
                   str(test), str(runtime_cpp), str(src / "es5510.cpp"), "-o", str(binary)]
        subprocess.run(command, check=True)
        subprocess.run([str(binary), str(expected_csv)], check=True)


if __name__ == "__main__":
    main()
