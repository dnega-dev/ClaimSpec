#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python3 -m compileall -q "$ROOT/src" "$ROOT/tests" "$ROOT/examples/make_invalid_traces.py"
python3 -m unittest discover -s "$ROOT/tests" -v

SCHEMA_TMP=$(mktemp -d "$ROOT/.claimspec-schemas.XXXXXX")
trap 'rm -rf "$SCHEMA_TMP"' EXIT HUP INT TERM

for kind in trace contract result; do
  python3 -m claimspec schema "$kind" --output "$SCHEMA_TMP/$kind.schema.json"
  python3 -c 'from pathlib import Path; import sys; expected = Path(sys.argv[1]).read_bytes(); actual = Path(sys.argv[2]).read_bytes(); raise SystemExit(0 if expected == actual else "stale schema: " + sys.argv[1])' "$ROOT/schemas/$kind.schema.json" "$SCHEMA_TMP/$kind.schema.json"
done

printf '%s\n' "ClaimSpec checks passed."
