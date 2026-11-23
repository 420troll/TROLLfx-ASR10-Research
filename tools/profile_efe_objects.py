#!/usr/bin/env python3
"""Conservative redacted inventory of private ASR-10 EFE objects."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

def profile(path):
    data = path.read_bytes()
    r = {"object_sha256": hashlib.sha256(data).hexdigest(), "file_size": len(data)}
    if len(data) < 46:
        return {**r, "status": "too_short"}
    name = "".join(chr(c) for c in data[10:34:2] if 32 <= c < 127).strip()
    fx_size = int.from_bytes(data[34:38], "big")
    fx_ucode = int.from_bytes(data[38:40], "big")
    valid = 46 <= fx_ucode < fx_size <= len(data)
    r.update({
        "status": "header_bounds_valid" if valid else "header_bounds_invalid",
        "name": name, "fx_size": fx_size, "fx_ucode": fx_ucode,
        "trailing_padding_bytes": len(data)-fx_size if fx_size <= len(data) else None,
        "undecoded_region_bytes": fx_size-fx_ucode if valid else None,
        "naive_six_byte_chunks_not_instructions": (fx_size-fx_ucode)//6 if valid else None,
    })
    return r

def catalog(paths):
    objects = [profile(p) for p in sorted(paths, key=lambda p: p.as_posix())]
    return {"format": "trollfx-efe-redacted-inventory-v1",
            "objects": objects,
            "counts_by_header_status": dict(sorted(Counter(x["status"] for x in objects).items())),
            "notice": "Observed header fields only. No instruction boundaries or factory accuracy claimed."}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", type=Path, nargs="+")
    ap.add_argument("--output", type=Path, help="optional local JSON path outside Git")
    args = ap.parse_args()
    paths = []
    for p in args.paths:
        if p.is_file():
            paths.append(p)
        elif p.is_dir():
            paths.extend(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in (".efe", ".bin"))
        else:
            ap.error(f"missing path: {p}")
    if not paths:
        ap.error("no private EFE objects found")
    result = json.dumps(catalog(paths), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")

if __name__ == "__main__":
    main()
