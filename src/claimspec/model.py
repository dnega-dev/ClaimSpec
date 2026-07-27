"""Immutable-ish data models used by the parser and evaluator."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Rule:
    """A single requirement in a contract."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {"name": self.name}
        data.update(self.params)
        return data


@dataclass(frozen=True)
class Contract:
    """A normalized ClaimSpec contract."""

    version: str
    name: str
    description: str = ""
    rules: List[Rule] = field(default_factory=list)
    source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "version": self.version,
            "name": self.name,
            "rules": [rule.to_dict() for rule in self.rules],
        }
        if self.description:
            result["description"] = self.description
        return result


@dataclass(frozen=True)
class Finding:
    """A machine-readable outcome for one evaluated rule."""

    rule: str
    status: str
    message: str
    subjects: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "rule": self.rule,
            "status": self.status,
            "message": self.message,
            "subjects": list(self.subjects),
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass(frozen=True)
class EvaluationResult:
    """Complete result of evaluating one trace against one contract."""

    schema_version: str
    contract_name: str
    contract_version: str
    run_id: str
    passed: bool
    summary: Dict[str, int]
    findings: List[Finding]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract": {
                "name": self.contract_name,
                "version": self.contract_version,
            },
            "run_id": self.run_id,
            "passed": self.passed,
            "summary": dict(self.summary),
            "findings": [finding.to_dict() for finding in self.findings],
        }
