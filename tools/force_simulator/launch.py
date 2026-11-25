#!/usr/bin/env python3
"""Build (if needed) and launch the local TROLLfx Force plugin interface simulator."""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from build import build,sdk_path,SIM_DIR

def assets_path(value):
    candidates=[value,os.environ.get("TROLLFX_FACTORY_PACKAGES_DIR"),str(Path.home()/"asr10-force-assets-v1")]
    for item in candidates:
        if not item:continue
        p=Path(item).expanduser()
        if (p/"provider-index.tsv").is_file():return p.resolve()
    raise RuntimeError("trusted private factory asset root not found; pass --assets or set TROLLFX_FACTORY_PACKAGES_DIR (must contain provider-index.tsv)")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--sdk");ap.add_argument("--assets");ap.add_argument("--host",default="127.0.0.1");ap.add_argument("--port",type=int,default=8765);ap.add_argument("--build-only",action="store_true");ap.add_argument("--force-build",action="store_true");a=ap.parse_args()
    sdk=sdk_path(a.sdk);plugin,host=build(sdk,a.force_build)
    if a.build_only:print(f"built {plugin}\nhost {host}");return
    from server import serve
    serve(assets_path(a.assets),a.host,a.port)
if __name__=="__main__":
    try:main()
    except Exception as e:print(f"trollfx-force-sim: {e}",file=sys.stderr);raise SystemExit(2)
