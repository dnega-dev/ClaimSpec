"""Published JSON Schemas and zero-dependency structural validation."""

import copy
import math
from typing import Any, Dict, List

from .errors import TraceValidationError

SCHEMA_BASE = "https://claimspec.dev/schema/1.0/"

TRACE_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_BASE + "trace.schema.json",
    "title": "ClaimSpec grounding trace",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "run",
        "output",
        "claims",
        "citations",
        "sources",
        "quotes",
        "events",
    ],
    "properties": {
        "schema_version": {"const": "1.0"},
        "run": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "started_at"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "started_at": {"type": "string", "format": "date-time"},
                "ended_at": {"type": "string", "format": "date-time"},
            },
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "required": ["completion_status"],
            "properties": {
                "completion_status": {
                    "enum": ["completed", "partial", "aborted", "refused"]
                },
                "text": {"type": "string"},
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "text", "kind", "support", "action", "citations"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "text": {"type": "string"},
                    "kind": {"enum": ["factual", "opinion", "instruction"]},
                    "support": {"enum": ["supported", "unsupported", "uncertain"]},
                    "action": {"enum": ["retained", "labeled", "removed"]},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "uniqueItems": True,
                    },
                    "uncertainty_reason": {"type": "string"},
                    "risk": {"enum": ["low", "medium", "high"]},
                    "quantitative_values": {
                        "type": "array",
                        "items": {
                            "oneOf": [
                                {"type": "string", "minLength": 1},
                                {"type": "number"},
                                {
                                    "type": "object",
                                    "required": ["value"],
                                    "additionalProperties": False,
                                    "properties": {
                                        "value": {
                                            "oneOf": [
                                                {"type": "string", "minLength": 1},
                                                {"type": "number"},
                                            ]
                                        },
                                        "unit": {"type": "string"},
                                    },
                                },
                            ]
                        },
                    },
                },
            },
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "source_id"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "source_id": {"type": "string", "minLength": 1},
                    "locator": {"type": "string"},
                },
            },
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "url", "source_type", "access", "fetched_text"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "url": {"type": "string", "minLength": 1},
                    "source_type": {"enum": ["primary", "secondary", "unknown"]},
                    "jurisdiction": {"type": "string"},
                    "fetched_text": {"type": "string"},
                    "access": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["run_id", "status", "accessed_at"],
                        "properties": {
                            "run_id": {"type": "string", "minLength": 1},
                            "status": {"enum": ["success", "failed"]},
                            "accessed_at": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            },
        },
        "quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "source_id", "text"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "source_id": {"type": "string", "minLength": 1},
                    "claim_id": {"type": "string"},
                    "text": {"type": "string", "minLength": 1},
                },
            },
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "type", "run_id", "status", "occurred_at"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "type": {"enum": ["retrieval", "contradiction_search"]},
                    "run_id": {"type": "string", "minLength": 1},
                    "status": {"enum": ["success", "failed"]},
                    "occurred_at": {"type": "string", "format": "date-time"},
                    "result_count": {"type": "integer", "minimum": 0},
                    "core": {"type": "boolean"},
                    "claim_id": {"type": "string"},
                    "query": {"type": "string"},
                },
            },
        },
    },
}

def _contract_rule_schema(
    name: str,
    properties: Dict[str, Any] = None,
    required: List[str] = None,
) -> Dict[str, Any]:
    """Build one closed JSON-contract rule variant."""

    rule_properties = {"name": {"const": name}}
    rule_properties.update(properties or {})
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["name"] + list(required or []),
        "properties": rule_properties,
    }


_COUNT = {"type": "integer", "minimum": 0}
_POSITIVE_COUNT = {"type": "integer", "minimum": 1}
_BOOLEAN = {"type": "boolean"}
_ALLOWLIST = {
    "type": "array",
    "minItems": 1,
    "uniqueItems": True,
    "items": {"type": "string", "minLength": 1},
}
_CONTRACT_RULE_SCHEMAS = [
    _contract_rule_schema(
        "min_sources",
        {"count": _COUNT, "cited_only": _BOOLEAN},
        ["count"],
    ),
    _contract_rule_schema(
        "min_primary_sources",
        {"count": _COUNT, "cited_only": _BOOLEAN},
        ["count"],
    ),
    _contract_rule_schema("factual_claims_cited"),
    _contract_rule_schema("citations_resolve"),
    _contract_rule_schema("quotes_verbatim"),
    _contract_rule_schema(
        "quantitative_values_in_evidence", {"normalize_whitespace": _BOOLEAN}
    ),
    _contract_rule_schema("sources_accessed_current_run", {"cited_only": _BOOLEAN}),
    _contract_rule_schema("retrieval_results", {"min_count": _POSITIVE_COUNT}),
    _contract_rule_schema("unsupported_claims_labeled_or_removed"),
    _contract_rule_schema("uncertainty_reason"),
    _contract_rule_schema(
        "jurisdiction_allowlist",
        {"allow": _ALLOWLIST, "cited_only": _BOOLEAN},
        ["allow"],
    ),
    _contract_rule_schema(
        "source_domain_allowlist",
        {"allow": _ALLOWLIST, "cited_only": _BOOLEAN},
        ["allow"],
    ),
    _contract_rule_schema("contradiction_search_high_risk"),
    _contract_rule_schema(
        "no_completion_without_core_retrieval", {"min_count": _POSITIVE_COUNT}
    ),
]

CONTRACT_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_BASE + "contract.schema.json",
    "title": "ClaimSpec JSON contract",
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "name", "rules"],
    "properties": {
        "version": {"const": "1.0"},
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "rules": {
            "type": "array",
            "minItems": 1,
            "items": {"oneOf": _CONTRACT_RULE_SCHEMAS},
        },
    },
}

RESULT_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_BASE + "result.schema.json",
    "title": "ClaimSpec evaluation result",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "contract",
        "run_id",
        "passed",
        "summary",
        "findings",
    ],
    "properties": {
        "schema_version": {"const": "1.0"},
        "contract": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "version"],
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
            },
        },
        "run_id": {"type": "string"},
        "passed": {"type": "boolean"},
        "summary": {
            "type": "object",
            "additionalProperties": False,
            "required": ["pass", "fail", "total"],
            "properties": {
                "pass": {"type": "integer", "minimum": 0},
                "fail": {"type": "integer", "minimum": 0},
                "total": {"type": "integer", "minimum": 0},
            },
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rule", "status", "message", "subjects"],
                "properties": {
                    "rule": {"type": "string"},
                    "status": {"enum": ["pass", "fail"]},
                    "message": {"type": "string"},
                    "subjects": {"type": "array", "items": {"type": "string"}},
                    "details": {"type": "object"},
                },
            },
        },
    },
}

SCHEMAS = {"trace": TRACE_SCHEMA, "contract": CONTRACT_SCHEMA, "result": RESULT_SCHEMA}


def get_schema(kind: str) -> Dict[str, Any]:
    """Return a copy of one published schema."""

    if kind not in SCHEMAS:
        raise KeyError("unknown schema kind {!r}".format(kind))
    return copy.deepcopy(SCHEMAS[kind])


def _expect_type(value: Any, expected: type, path: str, errors: List[str]) -> bool:
    if expected is int:
        valid = isinstance(value, int) and not isinstance(value, bool)
    else:
        valid = isinstance(value, expected)
    if not valid:
        errors.append("{} must be {}".format(path, expected.__name__))
    return valid


def _nonempty_string(value: Any, path: str, errors: List[str]) -> bool:
    if not isinstance(value, str) or not value:
        errors.append("{} must be a non-empty string".format(path))
        return False
    return True


def _array(value: Any, path: str, errors: List[str]) -> bool:
    return _expect_type(value, list, path, errors)


def _object(value: Any, path: str, errors: List[str]) -> bool:
    return _expect_type(value, dict, path, errors)


def _valid_value_scalar(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, int):
        return True
    return math.isfinite(value)


def _reject_unknown(item: Dict[str, Any], allowed: Any, path: str, errors: List[str]) -> None:
    for key in sorted(set(item) - set(allowed), key=str):
        errors.append("{}.{} is not allowed".format(path, key))


def validate_trace(trace: Any) -> None:
    """Validate the trace subset needed by the evaluator without third-party packages.

    The published JSON Schema is normative for interchange. This validator deliberately
    emits compact, deterministic diagnostics and enforces all evaluator invariants.
    """

    errors: List[str] = []
    if not _object(trace, "$", errors):
        raise TraceValidationError(errors)
    required = ("schema_version", "run", "output", "claims", "citations", "sources", "quotes", "events")
    _reject_unknown(trace, required, "$", errors)
    for key in required:
        if key not in trace:
            errors.append("$.{} is required".format(key))
    if any(key not in trace for key in required):
        raise TraceValidationError(errors)
    if trace["schema_version"] != "1.0":
        errors.append("$.schema_version must equal '1.0'")

    run = trace["run"]
    if _object(run, "$.run", errors):
        _reject_unknown(run, ("id", "started_at", "ended_at"), "$.run", errors)
        _nonempty_string(run.get("id"), "$.run.id", errors)
        _nonempty_string(run.get("started_at"), "$.run.started_at", errors)
        if "ended_at" in run:
            _nonempty_string(run["ended_at"], "$.run.ended_at", errors)

    output = trace["output"]
    if _object(output, "$.output", errors):
        _reject_unknown(output, ("completion_status", "text"), "$.output", errors)
        if output.get("completion_status") not in ("completed", "partial", "aborted", "refused"):
            errors.append("$.output.completion_status has an invalid value")
        if "text" in output and not isinstance(output["text"], str):
            errors.append("$.output.text must be str")

    _validate_records(trace["claims"], "claims", _validate_claim, errors)
    _validate_records(trace["citations"], "citations", _validate_citation, errors)
    _validate_records(trace["sources"], "sources", _validate_source, errors)
    _validate_records(trace["quotes"], "quotes", _validate_quote, errors)
    _validate_records(trace["events"], "events", _validate_event, errors)

    for collection in ("claims", "citations", "sources", "quotes", "events"):
        values = trace.get(collection)
        if isinstance(values, list):
            identifiers = [item.get("id") for item in values if isinstance(item, dict)]
            duplicates = sorted({item for item in identifiers if item and identifiers.count(item) > 1})
            if duplicates:
                errors.append("$.{} contains duplicate id(s): {}".format(collection, ", ".join(duplicates)))
    if errors:
        raise TraceValidationError(errors)


def _validate_records(value: Any, name: str, validator: Any, errors: List[str]) -> None:
    path = "$.{}".format(name)
    if not _array(value, path, errors):
        return
    for index, item in enumerate(value):
        item_path = "{}[{}]".format(path, index)
        if _object(item, item_path, errors):
            validator(item, item_path, errors)


def _validate_claim(item: Dict[str, Any], path: str, errors: List[str]) -> None:
    _reject_unknown(
        item,
        (
            "id",
            "text",
            "kind",
            "support",
            "action",
            "citations",
            "uncertainty_reason",
            "risk",
            "quantitative_values",
        ),
        path,
        errors,
    )
    _nonempty_string(item.get("id"), path + ".id", errors)
    if not isinstance(item.get("text"), str):
        errors.append(path + ".text must be str")
    if item.get("kind") not in ("factual", "opinion", "instruction"):
        errors.append(path + ".kind has an invalid value")
    if item.get("support") not in ("supported", "unsupported", "uncertain"):
        errors.append(path + ".support has an invalid value")
    if item.get("action") not in ("retained", "labeled", "removed"):
        errors.append(path + ".action has an invalid value")
    citations = item.get("citations")
    if _array(citations, path + ".citations", errors):
        for index, citation in enumerate(citations):
            _nonempty_string(citation, path + ".citations[{}]".format(index), errors)
        string_citations = [citation for citation in citations if isinstance(citation, str)]
        if len(string_citations) == len(citations) and len(string_citations) != len(set(string_citations)):
            errors.append(path + ".citations must contain unique items")
    if "uncertainty_reason" in item and not isinstance(item["uncertainty_reason"], str):
        errors.append(path + ".uncertainty_reason must be str")
    if "risk" in item and item["risk"] not in ("low", "medium", "high"):
        errors.append(path + ".risk has an invalid value")
    values = item.get("quantitative_values", [])
    if _array(values, path + ".quantitative_values", errors):
        for index, value in enumerate(values):
            value_path = path + ".quantitative_values[{}]".format(index)
            if isinstance(value, dict):
                _reject_unknown(value, ("value", "unit"), value_path, errors)
                if "value" not in value or not _valid_value_scalar(value["value"]):
                    errors.append(value_path + ".value is invalid")
                if "unit" in value and not isinstance(value["unit"], str):
                    errors.append(value_path + ".unit must be str")
            elif not _valid_value_scalar(value):
                errors.append(value_path + " is invalid")


def _validate_citation(item: Dict[str, Any], path: str, errors: List[str]) -> None:
    _reject_unknown(item, ("id", "source_id", "locator"), path, errors)
    _nonempty_string(item.get("id"), path + ".id", errors)
    _nonempty_string(item.get("source_id"), path + ".source_id", errors)
    if "locator" in item and not isinstance(item["locator"], str):
        errors.append(path + ".locator must be str")


def _validate_source(item: Dict[str, Any], path: str, errors: List[str]) -> None:
    _reject_unknown(
        item,
        ("id", "url", "source_type", "jurisdiction", "fetched_text", "access"),
        path,
        errors,
    )
    _nonempty_string(item.get("id"), path + ".id", errors)
    _nonempty_string(item.get("url"), path + ".url", errors)
    if item.get("source_type") not in ("primary", "secondary", "unknown"):
        errors.append(path + ".source_type has an invalid value")
    if "jurisdiction" in item and not isinstance(item["jurisdiction"], str):
        errors.append(path + ".jurisdiction must be str")
    if not isinstance(item.get("fetched_text"), str):
        errors.append(path + ".fetched_text must be str")
    access = item.get("access")
    if _object(access, path + ".access", errors):
        _reject_unknown(access, ("run_id", "status", "accessed_at"), path + ".access", errors)
        _nonempty_string(access.get("run_id"), path + ".access.run_id", errors)
        _nonempty_string(access.get("accessed_at"), path + ".access.accessed_at", errors)
        if access.get("status") not in ("success", "failed"):
            errors.append(path + ".access.status has an invalid value")


def _validate_quote(item: Dict[str, Any], path: str, errors: List[str]) -> None:
    _reject_unknown(item, ("id", "source_id", "claim_id", "text"), path, errors)
    _nonempty_string(item.get("id"), path + ".id", errors)
    _nonempty_string(item.get("source_id"), path + ".source_id", errors)
    _nonempty_string(item.get("text"), path + ".text", errors)
    if "claim_id" in item:
        _nonempty_string(item["claim_id"], path + ".claim_id", errors)


def _validate_event(item: Dict[str, Any], path: str, errors: List[str]) -> None:
    _reject_unknown(
        item,
        ("id", "type", "run_id", "status", "occurred_at", "result_count", "core", "claim_id", "query"),
        path,
        errors,
    )
    _nonempty_string(item.get("id"), path + ".id", errors)
    if item.get("type") not in ("retrieval", "contradiction_search"):
        errors.append(path + ".type has an invalid value")
    _nonempty_string(item.get("run_id"), path + ".run_id", errors)
    _nonempty_string(item.get("occurred_at"), path + ".occurred_at", errors)
    if item.get("status") not in ("success", "failed"):
        errors.append(path + ".status has an invalid value")
    if "result_count" in item and (
        not isinstance(item["result_count"], int)
        or isinstance(item["result_count"], bool)
        or item["result_count"] < 0
    ):
        errors.append(path + ".result_count must be an integer >= 0")
    if "core" in item and not isinstance(item["core"], bool):
        errors.append(path + ".core must be bool")
    if "claim_id" in item:
        _nonempty_string(item["claim_id"], path + ".claim_id", errors)
    if "query" in item and not isinstance(item["query"], str):
        errors.append(path + ".query must be str")
