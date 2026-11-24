#!/usr/bin/env python3
"""Verify a private factory-reference provenance receipt and its artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/audio_validation"))
from reference_provenance import verify_provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provenance", type=Path)
    parser.add_argument("--skip-source-check", action="store_true",
                        help="verify captured artifacts and inputs without reopening the original source tree")
    args = parser.parse_args()
    try:
        result = verify_provenance(args.provenance, check_source=not args.skip_source_check)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
