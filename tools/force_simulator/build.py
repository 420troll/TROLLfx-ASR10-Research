"""Build a simulator-only native VST with actual ES5510 write tracing."""
from __future__ import annotations
import os, shutil, subprocess, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = Path.home() / ".cache" / "trollfx-asr10-force-simulator"
PLUGIN = SIM_DIR / "asr10-fx-collection-traced.so"
HOST = SIM_DIR / "libtrollfx-vst-host.so"
SOURCES = [
    ROOT / "force_plugin/src/ASR10FXCollection.cpp",
    ROOT / "force_plugin/src/ES5510DSPBackend.cpp",
    ROOT / "force_plugin/src/ES5510FactoryPackageProvider.cpp",
    ROOT / "src/es5510.cpp",
    ROOT / "src/es5510_factory_runtime.cpp",
]

def sdk_path(override: str | None = None) -> Path:
    for value in (override, os.environ.get("AKAI_FORCE_SDK"), "/mnt/c/Users/Gamer/research/AkaiForceSDK", str(Path.home()/"research/AkaiForceSDK")):
        if not value: continue
        candidate = Path(value).expanduser()
        if (candidate / "framework/mpc_plugin.h").is_file(): return candidate.resolve()
    raise RuntimeError("Akai Force SDK not found. Set AKAI_FORCE_SDK or pass --sdk.")

def build(sdk: Path, force=False):
    stamp = SIM_DIR / "build.sha256"
    dependencies = list(SOURCES)
    for directory in (ROOT/"include", ROOT/"src", ROOT/"force_plugin/src"):
        dependencies.extend(sorted((*directory.glob("*.h"), *directory.glob("*.hpp"))))
    dependencies.extend(p for p in (sdk/"framework").glob("*.h") if p.name in {
        "mpc_plugin.h", "mpc_vst2_abi.h", "mpc_resources.h"})
    dependencies.append(ROOT/"tools/force_simulator/vst_host.cpp")
    digest_builder=hashlib.sha256(str(sdk).encode())
    for path in sorted(set(dependencies)):
        digest_builder.update(str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name).encode())
        digest_builder.update(path.read_bytes())
    digest=digest_builder.hexdigest()
    current = stamp.read_text().strip() if stamp.is_file() else ""
    rebuild = force or current != digest or not PLUGIN.is_file() or not HOST.is_file()
    if not shutil.which("g++"): raise RuntimeError("g++ is required to build the native VST simulator")
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    common = ["g++", "-std=c++17", "-O2", "-fPIC", "-shared"]
    includes = ["-I"+str(sdk/"framework"), "-I"+str(ROOT/"include"), "-I"+str(ROOT/"src"), "-I"+str(ROOT/"force_plugin/src")]
    if rebuild:
        cmd = common + ["-DTROLLFX_SIMULATOR_TRACE", *includes, *map(str,SOURCES), "-pthread", "-o", str(PLUGIN)]
        subprocess.run(cmd, check=True, cwd=ROOT)
    if rebuild:
        subprocess.run(common + ["-I"+str(sdk/"framework"), str(ROOT/"tools/force_simulator/vst_host.cpp"),
            "-ldl", "-pthread", "-o", str(HOST)], check=True, cwd=ROOT)
    if rebuild: stamp.write_text(digest + "\n")
    return PLUGIN, HOST

if __name__ == "__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--sdk"); ap.add_argument("--force",action="store_true"); a=ap.parse_args()
    p,h=build(sdk_path(a.sdk),a.force); print(f"native VST: {p}\nhost shim: {h}")
