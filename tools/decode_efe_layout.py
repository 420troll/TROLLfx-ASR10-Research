#!/usr/bin/env python3
"""Print a redacted, bounds-checked layout report for a private EFE object."""
import argparse
import json
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("object", type=Path)
    ap.add_argument("--paired", type=int, default=0, help="runtime-verified paired record count")
    ap.add_argument("--paired-start", type=lambda x: int(x, 0), help="absolute object offset of first GPR initializer")
    ap.add_argument("--instruction-only", type=int, default=0, help="runtime-verified standalone instruction record count")
    ap.add_argument("--instruction-start", type=lambda x: int(x, 0), help="absolute object offset of first standalone instruction")
    ap.add_argument("--alias", action="append", default=[], metavar="ACTIVE:SOURCE",
                    help="runtime-verified active instruction alias, repeatable")
    args = ap.parse_args()
    try:
        from efe_layout import describe_layout
        aliases = tuple(tuple(int(x, 0) for x in item.split(":")) for item in args.alias)
        result = describe_layout(args.object.read_bytes(), paired_start_gpr=args.paired_start,
                                 paired_count=args.paired, instruction_start=args.instruction_start,
                                 instruction_count=args.instruction_only, aliases=aliases)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
