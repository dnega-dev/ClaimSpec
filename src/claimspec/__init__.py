"""ClaimSpec: executable grounding contracts for research-agent traces."""

from .evaluator import Evaluator, evaluate, load_trace
from .errors import ClaimSpecError, ContractParseError, ContractValidationError, TraceValidationError
from .model import Contract, EvaluationResult, Finding, Rule
from .parser import (
    format_contract,
    load_contract,
    parse_claimspec,
    parse_contract,
    parse_json_contract,
    validate_contract,
)
from .renderers import render
from .schema import get_schema, validate_trace

__all__ = [
    "ClaimSpecError",
    "ContractParseError",
    "ContractValidationError",
    "TraceValidationError",
    "Contract",
    "Rule",
    "Finding",
    "EvaluationResult",
    "Evaluator",
    "evaluate",
    "load_trace",
    "load_contract",
    "parse_contract",
    "parse_claimspec",
    "parse_json_contract",
    "format_contract",
    "validate_contract",
    "validate_trace",
    "get_schema",
    "render",
]

__version__ = "0.1.0"
