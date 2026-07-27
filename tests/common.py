"""Shared test fixtures."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
CONTRACTS = EXAMPLES / "contracts"
VALID_TRACE = EXAMPLES / "traces" / "valid" / "full.json"


def trace_fixture():
    return copy.deepcopy(json.loads(VALID_TRACE.read_text(encoding="utf-8")))
