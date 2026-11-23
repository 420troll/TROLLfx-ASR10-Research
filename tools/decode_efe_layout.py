#!/usr/bin/env python3
"""Print a redacted, bounds-checked layout report for a private EFE object."""
import argparse
import json
from pathlib import Path

from efe_layout import decode_file


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("object", type=Path)
    ap.add_argument("--paired", type=int, required=True, help="runtime-verified paired record count")
    ap.add_argument("--instruction-only", type=int, required=True, help="runtime-verified instruction-only count")
    args = ap.parse_args()
    try:
        print(json.dumps(decode_file(args.object, args.paired, args.instruction_only), indent=2))
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
