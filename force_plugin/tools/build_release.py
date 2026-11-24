#!/usr/bin/env python3
"""Discover the Force SDK/toolchain, build all SDK targets and package a gated candidate."""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_FOLDER = "TROLLfx - VST - ASR10 FX Collection"
PACKAGE_ROOT = ROOT / "force_plugin" / "dist"

def run(args, *, cwd=None, env=None, check=True):
    p = subprocess.run([str(x) for x in args], cwd=cwd, env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str,args))}\n{p.stdout}")
    return p

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def source_digest() -> str:
    h=hashlib.sha256()
    for rel in ("force_plugin/plugin.json","force_plugin/ui.json","force_plugin/src/ASR10FXCollection.cpp","force_plugin/effects.json"):
        h.update(rel.encode()+b"\0"); h.update((ROOT/rel).read_bytes())
    return h.hexdigest()

def git_value(repo: Path, *args: str, default="unknown") -> str:
    p=run(["git","-C",repo,*args],check=False)
    return p.stdout.strip() if p.returncode == 0 else default

def valid_sdk(path: Path) -> bool:
    return all((path/x).is_file() for x in ("tools/build.py","tools/validate.py","framework/mpc_plugin.h"))

def discover_sdk(override: str|None) -> Path:
    candidates=[]
    for value in (override,os.environ.get("AKAI_FORCE_SDK"),os.environ.get("MPC_PLUGIN_SDK")):
        if value: candidates.append(Path(value).expanduser())
    candidates += [ROOT.parent/"AkaiForceSDK", Path.home()/"research/AkaiForceSDK",
                   Path.home()/"work/AkaiForceSDK", Path("/opt/akai-force-sdk")]
    seen=set()
    for candidate in candidates:
        try: p=candidate.resolve(strict=True)
        except OSError: continue
        if p not in seen and valid_sdk(p): return p
        seen.add(p)
    tried="\n".join(f"  - {x}" for x in candidates)
    raise RuntimeError("Could not locate a compatible Akai/InMusic SDK. Set AKAI_FORCE_SDK or --sdk. Tried:\n"+tried)

def zig_candidates(sdk: Path):
    py_candidates=[]
    if os.environ.get("ZIG_PYTHON"): py_candidates.append(Path(os.environ["ZIG_PYTHON"]).expanduser())
    py_candidates.append(Path(sys.executable))
    for p in (Path("/tmp/trollfx-force-zig"), Path("/tmp/trollfx-zig"), sdk/".sdk-tools/zigenv/lib"):
        if p.exists():
            if (p/"ziglang/__main__.py").is_file():
                # Build.py accepts a python executable and imports ziglang from inherited PYTHONPATH.
                py_candidates.append(Path(sys.executable))
    for py in py_candidates:
        extras=[]
        for p in (Path(os.environ.get("ZIG_PYTHONPATH","/tmp/trollfx-force-zig")),Path("/tmp/trollfx-zig")):
            if (p/"ziglang/__main__.py").is_file(): extras.append(str(p))
        env=os.environ.copy()
        if extras: env["PYTHONPATH"]=os.pathsep.join(extras+[env.get("PYTHONPATH","")]).rstrip(os.pathsep)
        check=run([py,"-m","ziglang","version"],env=env,check=False)
        if check.returncode==0 and check.stdout.strip():
            return {"kind":"zig-python","arg":str(py),"version":check.stdout.strip(),"env":env,
                    "command":f"{py} -m ziglang"}
    z=os.environ.get("ZIG") or shutil.which("zig")
    if z:
        q=run([z,"version"],check=False)
        if q.returncode==0: return {"kind":"zig","arg":z,"version":q.stdout.strip(),"env":os.environ.copy(),"command":z}
    return None

def discover_toolchain(sdk: Path, requested: str):
    if requested in ("auto","zig"):
        z=zig_candidates(sdk)
        if z: return z
        if requested=="zig": raise RuntimeError("Zig was requested but no working zig binary or ziglang Python module was found. Set ZIG, ZIG_PYTHON, or ZIG_PYTHONPATH.")
    if requested in ("auto","gcc"):
        arm=shutil.which("arm-linux-gnueabihf-g++")
        a64=shutil.which("aarch64-linux-gnu-g++")
        if arm and a64:
            vers=run([arm,"--version"],check=False).stdout.splitlines()[0]
            return {"kind":"gcc","arg":None,"version":vers,"env":os.environ.copy(),"command":"arm-linux-gnueabihf-g++ + aarch64-linux-gnu-g++","paths":{"arm32":arm,"arm64":a64}}
    raise RuntimeError("No complete cross toolchain found. Install Zig/ziglang (recommended) or both arm-linux-gnueabihf-g++ and aarch64-linux-gnu-g++.")

def readelf_info(readelf: str, binary: Path, expected: str):
    h=run([readelf,"-h",binary]).stdout
    if expected=="arm32":
        if not re.search(r"Class:\s+ELF32",h) or not re.search(r"Machine:\s+ARM\b",h):
            raise RuntimeError(f"wrong ARM32 ELF architecture: {binary}")
        attrs=run([readelf,"-A",binary]).stdout
        if "Tag_ABI_VFP_args: VFP registers" not in attrs or "Tag_CPU_arch: v7" not in attrs:
            raise RuntimeError(f"ARM32 binary is not ARMv7 hard-float: {binary}")
        abi={"elf_class":"ELF32","machine":"ARM","cpu_abi":"ARMv7-A / hard-float (VFP registers)"}
    else:
        if not re.search(r"Class:\s+ELF64",h) or not re.search(r"Machine:\s+AArch64\b",h):
            raise RuntimeError(f"wrong AArch64 ELF architecture: {binary}")
        abi={"elf_class":"ELF64","machine":"AArch64"}
    dynamic=run([readelf,"-d",binary]).stdout
    abi["needed_libraries"]=sorted(set(re.findall(r"Shared library: \[([^]]+)\]",dynamic)))
    versions=run([readelf,"--version-info",binary]).stdout
    glibc=re.findall(r"GLIBC_(\d+)\.(\d+)",versions)
    abi["max_glibc"]=".".join(max(glibc,key=lambda v:(int(v[0]),int(v[1])))) if glibc else "none"
    return abi

def create_checksums(folder: Path):
    sums=[]
    for p in sorted(folder.rglob('*')):
        if p.is_symlink(): raise RuntimeError(f"package may not contain symlinks: {p}")
        if p.is_file() and p.name!="SHA256SUMS": sums.append(f"{digest(p)}  {p.relative_to(folder).as_posix()}")
    (folder/"SHA256SUMS").write_text("\n".join(sums)+"\n")

def create_zip(folder: Path, zip_path: Path):
    zip_path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file(): z.write(p,(folder.name+"/"+p.relative_to(folder).as_posix()),compress_type=zipfile.ZIP_DEFLATED)
    zip_path.with_suffix(zip_path.suffix+".sha256").write_text(f"{digest(zip_path)}  {zip_path.name}\n")

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sdk",help="SDK checkout (or set AKAI_FORCE_SDK)")
    ap.add_argument("--toolchain",choices=("auto","zig","gcc"),default="auto")
    ap.add_argument("--no-zip",action="store_true",help="build validated folder only")
    a=ap.parse_args()
    sdk=discover_sdk(a.sdk); tc=discover_toolchain(sdk,a.toolchain)
    plugins=sdk/"plugins"
    if not plugins.is_dir(): raise RuntimeError(f"SDK lacks plugins directory: {plugins}")
    stage=Path(tempfile.mkdtemp(prefix=".trollfx-asr10-force-",dir=plugins))
    try:
        (stage/"src").mkdir()
        shutil.copy2(ROOT/"force_plugin/plugin.json",stage/"plugin.json")
        shutil.copy2(ROOT/"force_plugin/ui.json",stage/"ui.json")
        shutil.copy2(ROOT/"force_plugin/src/ASR10FXCollection.cpp",stage/"src/ASR10FXCollection.cpp")
        args=[sys.executable,sdk/"tools/build.py",stage,"--target","all","--toolchain",("gcc" if tc["kind"]=="gcc" else "zig")]
        if tc["kind"] in ("zig","zig-python"): args += ["--zig",tc["arg"]]
        built=run(args,cwd=sdk,env=tc["env"])
        print(built.stdout,end="")
        staged_out=stage/"build"/PLUGIN_FOLDER
        if not staged_out.is_dir(): raise RuntimeError(f"SDK builder output not found: {staged_out}")
        readelf=shutil.which("arm-linux-gnueabihf-readelf") or shutil.which("readelf")
        if not readelf: raise RuntimeError("readelf is required for explicit architecture/ABI verification")
        arm32=staged_out/"VST/asr10-fx-collection-arm32.so"
        arm64=staged_out/"VST/asr10-fx-collection-arm64.so"
        if not arm32.is_file() or not arm64.is_file(): raise RuntimeError("SDK build did not emit both ARM package targets")
        abi={"arm32":readelf_info(readelf,arm32,"arm32"),"arm64":readelf_info(readelf,arm64,"arm64")}
        # Build a fresh sibling, validate it, then replace the old candidate atomically.
        temp_pkg=Path(tempfile.mkdtemp(prefix=".force-dist-",dir=ROOT/"force_plugin"))
        try:
            out=temp_pkg/PLUGIN_FOLDER
            shutil.copytree(staged_out,out)
            shutil.copy2(ROOT/"LICENSE",out/"LICENSE")
            shutil.copytree(ROOT/"force_plugin/LICENSES",out/"LICENSES")
            shutil.copy2(ROOT/"force_plugin/README.md",out/"README.txt")
            version=json.loads((out/"plugin.json").read_text())["version"]
            revision=git_value(ROOT,"rev-parse","HEAD")
            origin=git_value(sdk,"remote","get-url","origin")
            sdk_commit=git_value(sdk,"rev-parse","HEAD")
            validation=run([sys.executable,sdk/"tools/validate.py",out],cwd=sdk,check=False)
            print(validation.stdout,end="")
            summary=re.search(r"(\d+) errors?, (\d+) warnings?",validation.stdout)
            if validation.returncode or not summary or int(summary.group(1)) != 0:
                raise RuntimeError("SDK final package validation failed")
            manifest={"schema":"trollfx-force-release-manifest-v1","product":"TROLLfx - VST - ASR10 FX Collection",
              "version":version,"release_channel":"experimental","release_state":"candidate","playable":False,
              "playable_marker_required":"INTEGRATION_STATUS","built_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "source_commit":revision,"source_inputs_sha256":source_digest(),"sdk":{"path":str(sdk),"origin":origin,"commit":sdk_commit},
              "toolchain":{"kind":tc["kind"],"command":tc["command"],"version":tc["version"],"paths":tc.get("paths",{})},
              "targets":abi,"binaries":{"arm32_sha256":digest(arm32),"arm64_sha256":digest(arm64)},
              "build_command":"force_plugin/tools/build_candidate.sh --toolchain auto","package_command":"force_plugin/tools/build_candidate.sh --toolchain auto","sdk_validation":{"result":"PASS","errors":int(summary.group(1)),"warnings":int(summary.group(2)),"command":"tools/validate.py"},
              "licensing":{"project":"GPL-3.0-only","sdk_framework":"MIT","proprietary_factory_payloads_included":False}}
            (out/"release-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
            (out/"INSTALL.txt").write_text("BUILD CANDIDATE ONLY — NOT PLAYABLE / DO NOT INSTALL.\nThis package has no approved DSP integration verification marker. Use the repository's opt-in installer only for a playable package.\n")
            create_checksums(out)
            final=ROOT/"force_plugin/dist"/PLUGIN_FOLDER
            backup=None
            if final.exists():
                stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                backup=final.parent/f".dist-old-{stamp}"
                final.rename(backup)
            ROOT.joinpath("force_plugin/dist").mkdir(exist_ok=True)
            try:
                out.rename(final)
            except Exception:
                if backup and backup.exists() and not final.exists(): backup.rename(final)
                raise
            if backup and backup.exists(): shutil.rmtree(backup)
            zip_path=ROOT/"force_plugin/dist"/f"asr10-fx-collection-{version}-candidate.zip"
            if not a.no_zip:
                create_zip(final,zip_path)
            print(f"Packaged unplayable candidate: {final}")
            if not a.no_zip: print(f"Archive: {zip_path}")
            print(f"SDK: {sdk} @ {sdk_commit}")
            print(f"Toolchain: {tc['command']} ({tc['version']})")
        finally:
            if temp_pkg.exists(): shutil.rmtree(temp_pkg)
    finally:
        shutil.rmtree(stage,ignore_errors=True)
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except (OSError,RuntimeError,ValueError,json.JSONDecodeError) as e:
        print(f"build-release: ERROR: {e}",file=sys.stderr); raise SystemExit(2)
