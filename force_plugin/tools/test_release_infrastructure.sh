#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
python3 "$ROOT/force_plugin/tools/test_catalog.py"
python3 "$ROOT/force_plugin/tests/test_release_infrastructure.py"
python3 -m json.tool "$ROOT/force_plugin/schemas/dsp-integration-report.schema.json" >/dev/null
python3 -m py_compile "$ROOT"/force_plugin/tools/*.py
