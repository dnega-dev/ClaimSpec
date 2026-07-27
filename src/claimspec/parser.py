"""Parsers and normalizers for .claimspec and JSON contracts."""

import json
import shlex
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .errors import ContractParseError, ContractValidationError
from .model import Contract, Rule
from .rules import RULES

CONTRACT_VERSION = "1.0"


def _reject_json_constant(value: str) -> Any:
    raise ValueError("non-standard JSON constant {!r} is not allowed".format(value))


def _parse_value(raw: str, source: Optional[str], line: int) -> Any:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    if raw.startswith("[") or raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContractParseError(
                "invalid JSON parameter value: {}".format(exc.msg), source, line, exc.colno
            )
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    if "," in raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return raw


def _tokens(line_text: str, source: Optional[str], line: int) -> List[str]:
    try:
        lexer = shlex.shlex(line_text, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = "#"
        return list(lexer)
    except ValueError as exc:
        raise ContractParseError(str(exc), source, line)


def parse_claimspec(text: str, source: Optional[str] = None) -> Contract:
    """Parse the line-oriented ClaimSpec syntax."""

    version = None
    name = None
    description = ""
    description_seen = False
    rules: List[Rule] = []
    header_seen = False

    for line_number, line_text in enumerate(text.splitlines(), 1):
        tokens = _tokens(line_text, source, line_number)
        if not tokens:
            continue
        keyword = tokens[0]
        if not header_seen:
            if keyword != "claimspec" or len(tokens) != 2:
                raise ContractParseError(
                    "first statement must be 'claimspec 1.0'", source, line_number
                )
            version = tokens[1]
            header_seen = True
            continue
        if keyword in ("name", "description"):
            values = tokens[1:]
            if values and values[0] == "=":
                values = values[1:]
            if not values:
                raise ContractParseError(
                    "{} requires a value".format(keyword), source, line_number
                )
            value = " ".join(values)
            if keyword == "name":
                if name is not None:
                    raise ContractParseError("duplicate name", source, line_number)
                name = value
            else:
                if description_seen:
                    raise ContractParseError("duplicate description", source, line_number)
                description = value
                description_seen = True
            continue
        if keyword == "require":
            if len(tokens) < 2:
                raise ContractParseError("require needs a rule name", source, line_number)
            rule_name = tokens[1]
            params: Dict[str, Any] = {}
            for token in tokens[2:]:
                if "=" not in token:
                    raise ContractParseError(
                        "rule parameters must use key=value", source, line_number
                    )
                key, raw_value = token.split("=", 1)
                if not key or not raw_value:
                    raise ContractParseError(
                        "rule parameters need non-empty keys and values", source, line_number
                    )
                if key in params:
                    raise ContractParseError(
                        "duplicate parameter '{}'".format(key), source, line_number
                    )
                params[key] = _parse_value(raw_value, source, line_number)
            if rule_name in ("jurisdiction_allowlist", "source_domain_allowlist") and isinstance(
                params.get("allow"), str
            ):
                params["allow"] = [params["allow"]]
            rules.append(Rule(name=rule_name, params=params, line=line_number))
            continue
        raise ContractParseError(
            "unknown statement '{}'; expected name, description, or require".format(keyword),
            source,
            line_number,
        )

    if not header_seen:
        raise ContractParseError("empty contract; expected 'claimspec 1.0'", source, 1)
    contract = Contract(
        version=version or "",
        name=name or "",
        description=description,
        rules=rules,
        source=source,
    )
    validate_contract(contract)
    return contract


def parse_json_contract(text: str, source: Optional[str] = None) -> Contract:
    """Parse a contract represented as JSON."""

    try:
        data = json.loads(text, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise ContractParseError(exc.msg, source, exc.lineno, exc.colno)
    except ValueError as exc:
        raise ContractParseError(str(exc), source)
    if not isinstance(data, dict):
        raise ContractParseError("JSON contract root must be an object", source)
    extras = sorted(set(data) - {"version", "name", "description", "rules"})
    if extras:
        raise ContractParseError(
            "unknown JSON contract field(s): {}".format(", ".join(extras)), source
        )
    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        raise ContractParseError("JSON contract 'rules' must be an array", source)
    rules: List[Rule] = []
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            raise ContractParseError("rule {} must be an object".format(index), source)
        if "name" not in raw_rule:
            raise ContractParseError("rule {} has no name".format(index), source)
        params = {key: value for key, value in raw_rule.items() if key != "name"}
        rules.append(Rule(name=raw_rule["name"], params=params))
    contract = Contract(
        version=data.get("version", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
        rules=rules,
        source=source,
    )
    validate_contract(contract)
    return contract


def parse_contract(text: str, source: Optional[str] = None, format_hint: Optional[str] = None) -> Contract:
    """Parse either supported contract representation."""

    hint = (format_hint or "").lower()
    if hint not in ("", "json", "claimspec"):
        raise ContractParseError("unknown contract format {!r}".format(format_hint), source)
    if hint == "json" or (not hint and text.lstrip().startswith("{")):
        return parse_json_contract(text, source)
    return parse_claimspec(text, source)


def load_contract(path: str) -> Contract:
    """Read and parse a contract file."""

    contract_path = Path(path)
    try:
        text = contract_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractParseError("cannot read contract: {}".format(exc), str(contract_path))
    hint = "json" if contract_path.suffix.lower() == ".json" else "claimspec"
    return parse_contract(text, str(contract_path), hint)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_params(rule: Rule, allowed: Iterable[str], errors: List[str]) -> None:
    extras = sorted(set(rule.params) - set(allowed))
    if extras:
        errors.append(
            "rule '{}': unknown parameter(s): {}".format(rule.name, ", ".join(extras))
        )


def validate_contract(contract: Contract) -> None:
    """Validate normalized contract semantics and parameter types."""

    errors: List[str] = []
    if contract.version != CONTRACT_VERSION:
        errors.append("unsupported contract version {!r}; expected '1.0'".format(contract.version))
    if not isinstance(contract.name, str) or not contract.name.strip():
        errors.append("contract name must be a non-empty string")
    if not isinstance(contract.description, str):
        errors.append("contract description must be a string")
    if not contract.rules:
        errors.append("contract must contain at least one rule")
    seen = set()
    for rule in contract.rules:
        prefix = "rule '{}'".format(rule.name)
        if not isinstance(rule.name, str) or rule.name not in RULES:
            errors.append("unknown rule {!r}".format(rule.name))
            continue
        if rule.name in seen:
            errors.append("duplicate rule '{}'".format(rule.name))
        seen.add(rule.name)
        if not isinstance(rule.params, dict):
            errors.append("{} parameters must be an object".format(prefix))
            continue
        if rule.name in ("min_sources", "min_primary_sources"):
            _check_params(rule, ("count", "cited_only"), errors)
            count = rule.params.get("count")
            if not _is_int(count) or count < 0:
                errors.append("{} requires integer count >= 0".format(prefix))
        elif rule.name in ("retrieval_results", "no_completion_without_core_retrieval"):
            _check_params(rule, ("min_count",), errors)
            count = rule.params.get("min_count", 1)
            if not _is_int(count) or count < 1:
                errors.append("{} min_count must be an integer >= 1".format(prefix))
        elif rule.name in ("jurisdiction_allowlist", "source_domain_allowlist"):
            _check_params(rule, ("allow", "cited_only"), errors)
            allow = rule.params.get("allow")
            if not isinstance(allow, list) or not allow or not all(
                isinstance(item, str) and item.strip() for item in allow
            ):
                errors.append("{} requires a non-empty string list in allow".format(prefix))
            elif len(allow) != len(set(allow)):
                errors.append("{} allow entries must be unique".format(prefix))
        elif rule.name == "quantitative_values_in_evidence":
            _check_params(rule, ("normalize_whitespace",), errors)
        elif rule.name in ("sources_accessed_current_run",):
            _check_params(rule, ("cited_only",), errors)
        else:
            _check_params(rule, (), errors)
        for bool_key in ("cited_only", "normalize_whitespace"):
            if bool_key in rule.params and not isinstance(rule.params[bool_key], bool):
                errors.append("{} {} must be boolean".format(prefix, bool_key))
    if errors:
        raise ContractValidationError(errors)


def format_contract(contract: Contract) -> str:
    """Serialize a normalized contract in line-oriented form."""

    lines = ["claimspec {}".format(contract.version), "name {}".format(json.dumps(contract.name))]
    if contract.description:
        lines.append("description {}".format(json.dumps(contract.description)))
    lines.append("")
    for rule in contract.rules:
        pieces = ["require", rule.name]
        for key, value in rule.params.items():
            if isinstance(value, bool):
                rendered = "true" if value else "false"
            elif isinstance(value, list):
                rendered = ",".join(str(item) for item in value)
            else:
                rendered = str(value)
            pieces.append("{}={}".format(key, rendered))
        lines.append(" ".join(pieces))
    return "\n".join(lines) + "\n"
