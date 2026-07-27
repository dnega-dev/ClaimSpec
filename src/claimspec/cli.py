"""Command-line interface for ClaimSpec."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .errors import ClaimSpecError
from .evaluator import evaluate, load_trace
from .parser import load_contract
from .renderers import RENDERERS, render
from .rules import RULES
from .schema import SCHEMAS, get_schema

STARTER_CONTRACT = '''claimspec 1.0
name {name}
description "Baseline grounding checks for research-agent output"

require min_sources count=2
require min_primary_sources count=1
require factual_claims_cited
require citations_resolve
require quotes_verbatim
require quantitative_values_in_evidence
require sources_accessed_current_run
require retrieval_results min_count=1
require unsupported_claims_labeled_or_removed
require uncertainty_reason
require contradiction_search_high_risk
require no_completion_without_core_retrieval
'''


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claimspec",
        description="Check research-agent traces against executable grounding contracts.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="write a starter .claimspec contract")
    init_parser.add_argument("path", nargs="?", default="research.claimspec")
    init_parser.add_argument("--name", default="research-grounding")
    init_parser.add_argument("--force", action="store_true", help="overwrite an existing file")
    init_parser.set_defaults(handler=_cmd_init)

    check_parser = subparsers.add_parser("check", help="evaluate a trace against a contract")
    check_parser.add_argument("contract", help=".claimspec or JSON contract path")
    check_parser.add_argument("trace", help="trace JSON path")
    check_parser.add_argument(
        "--format", "-f", choices=sorted(RENDERERS), default="text", dest="format_name"
    )
    check_parser.add_argument("--output", "-o", help="write report to this path instead of stdout")
    check_parser.set_defaults(handler=_cmd_check)

    explain_parser = subparsers.add_parser(
        "explain", help="describe available rules or the rules in a contract"
    )
    explain_parser.add_argument("contract", nargs="?", help="optional contract path")
    explain_parser.add_argument("--rule", choices=sorted(RULES), help="explain one rule")
    explain_parser.add_argument("--json", action="store_true", dest="as_json")
    explain_parser.set_defaults(handler=_cmd_explain)

    schema_parser = subparsers.add_parser("schema", help="print a published JSON Schema")
    schema_parser.add_argument("kind", choices=sorted(SCHEMAS))
    schema_parser.add_argument("--output", "-o", help="write schema to this path")
    schema_parser.set_defaults(handler=_cmd_schema)
    return parser


def _write(text: str, output: Optional[str]) -> None:
    if output:
        path = Path(output)
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _cmd_init(args: argparse.Namespace) -> int:
    if not args.name.strip():
        raise ClaimSpecError("contract name must not be empty")
    path = Path(args.path)
    if path.exists() and not args.force:
        raise ClaimSpecError("{} already exists; pass --force to overwrite".format(path))
    parent = path.parent
    if not parent.exists():
        raise ClaimSpecError("parent directory does not exist: {}".format(parent))
    rendered_name = json.dumps(args.name)
    path.write_text(STARTER_CONTRACT.format(name=rendered_name), encoding="utf-8")
    sys.stdout.write("created {}\n".format(path))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    trace = load_trace(args.trace)
    result = evaluate(contract, trace)
    _write(render(result, args.format_name), args.output)
    return 0 if result.passed else 1


def _selected_rule_names(args: argparse.Namespace) -> List[str]:
    if args.rule:
        return [args.rule]
    if args.contract:
        contract = load_contract(args.contract)
        return [rule.name for rule in contract.rules]
    return sorted(RULES)


def _cmd_explain(args: argparse.Namespace) -> int:
    names = _selected_rule_names(args)
    if args.as_json:
        data = {name: RULES[name] for name in names}
        sys.stdout.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return 0
    if args.contract:
        contract = load_contract(args.contract)
        sys.stdout.write("{} (ClaimSpec {})\n".format(contract.name, contract.version))
        if contract.description:
            sys.stdout.write(contract.description + "\n")
        sys.stdout.write("\n")
    for name in names:
        item = RULES[name]
        sys.stdout.write("{}\n  {}\n".format(name, item["summary"]))
        if item["params"]:
            for key, description in item["params"].items():
                sys.stdout.write("  {}: {}\n".format(key, description))
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    text = json.dumps(get_schema(args.kind), indent=2, sort_keys=True) + "\n"
    _write(text, args.output)
    return 0


def run(argv: Optional[List[str]] = None) -> int:
    """Run the CLI and return a process exit code (useful for tests)."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (ClaimSpecError, OSError) as exc:
        sys.stderr.write("claimspec: error: {}\n".format(exc))
        return 2


def main(argv: Optional[List[str]] = None) -> None:
    """Console entry point."""

    raise SystemExit(run(argv))
