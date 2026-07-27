"""Deterministic evaluator for ClaimSpec grounding traces."""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Set
from urllib.parse import urlparse

from .errors import TraceValidationError
from .model import Contract, EvaluationResult, Finding, Rule
from .parser import validate_contract
from .schema import validate_trace

RESULT_VERSION = "1.0"


def _reject_json_constant(value: str) -> Any:
    raise ValueError("non-standard JSON constant {!r} is not allowed".format(value))


def load_trace(path: str) -> Dict[str, Any]:
    """Load and structurally validate a trace JSON file."""

    trace_path = Path(path)
    try:
        text = trace_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise TraceValidationError(["cannot read trace {}: {}".format(trace_path, exc)])
    try:
        trace = json.loads(text, parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise TraceValidationError(
            ["{}:{}:{}: {}".format(trace_path, exc.lineno, exc.colno, exc.msg)]
        )
    except ValueError as exc:
        raise TraceValidationError(["{}: {}".format(trace_path, exc)])
    validate_trace(trace)
    return trace


class Evaluator:
    """Evaluate one normalized contract against one validated trace."""

    def __init__(self, contract: Contract, trace: Dict[str, Any]):
        validate_contract(contract)
        validate_trace(trace)
        self.contract = contract
        self.trace = trace
        self.run_id = trace["run"]["id"]
        self.claims = {item["id"]: item for item in trace["claims"]}
        self.citations = {item["id"]: item for item in trace["citations"]}
        self.sources = {item["id"]: item for item in trace["sources"]}
        self.handlers: Dict[str, Callable[[Rule], Finding]] = {
            "min_sources": self._min_sources,
            "min_primary_sources": self._min_primary_sources,
            "factual_claims_cited": self._factual_claims_cited,
            "citations_resolve": self._citations_resolve,
            "quotes_verbatim": self._quotes_verbatim,
            "quantitative_values_in_evidence": self._quantitative_values,
            "sources_accessed_current_run": self._sources_accessed_current_run,
            "retrieval_results": self._retrieval_results,
            "unsupported_claims_labeled_or_removed": self._unsupported_labeled_or_removed,
            "uncertainty_reason": self._uncertainty_reason,
            "jurisdiction_allowlist": self._jurisdiction_allowlist,
            "source_domain_allowlist": self._source_domain_allowlist,
            "contradiction_search_high_risk": self._contradiction_search,
            "no_completion_without_core_retrieval": self._completion_requires_core,
        }

    def evaluate(self) -> EvaluationResult:
        findings = [self.handlers[rule.name](rule) for rule in self.contract.rules]
        pass_count = sum(1 for finding in findings if finding.status == "pass")
        fail_count = len(findings) - pass_count
        return EvaluationResult(
            schema_version=RESULT_VERSION,
            contract_name=self.contract.name,
            contract_version=self.contract.version,
            run_id=self.run_id,
            passed=fail_count == 0,
            summary={"pass": pass_count, "fail": fail_count, "total": len(findings)},
            findings=findings,
        )

    @staticmethod
    def _pass(rule: Rule, message: str, details: Dict[str, Any] = None) -> Finding:
        return Finding(rule.name, "pass", message, [], details or {})

    @staticmethod
    def _fail(
        rule: Rule,
        message: str,
        subjects: Iterable[str],
        details: Dict[str, Any] = None,
    ) -> Finding:
        return Finding(rule.name, "fail", message, sorted(set(subjects)), details or {})

    def _retained_claims(self) -> List[Dict[str, Any]]:
        return [claim for claim in self.trace["claims"] if claim["action"] != "removed"]

    def _cited_source_ids(self) -> Set[str]:
        source_ids: Set[str] = set()
        for claim in self._retained_claims():
            for citation_id in claim["citations"]:
                citation = self.citations.get(citation_id)
                if citation:
                    source_ids.add(citation["source_id"])
        return source_ids

    def _source_pool(self, cited_only: bool) -> List[Dict[str, Any]]:
        if not cited_only:
            return list(self.trace["sources"])
        cited = self._cited_source_ids()
        return [source for source in self.trace["sources"] if source["id"] in cited]

    @staticmethod
    def _successfully_accessed(source: Dict[str, Any]) -> bool:
        return source["access"]["status"] == "success"

    def _min_sources(self, rule: Rule) -> Finding:
        required = rule.params["count"]
        pool = self._source_pool(rule.params.get("cited_only", False))
        eligible = {source["id"] for source in pool if self._successfully_accessed(source)}
        details = {"required": required, "observed": len(eligible)}
        if len(eligible) >= required:
            return self._pass(rule, "observed {} eligible source(s)".format(len(eligible)), details)
        return self._fail(
            rule,
            "requires at least {} source(s), observed {}".format(required, len(eligible)),
            [],
            details,
        )

    def _min_primary_sources(self, rule: Rule) -> Finding:
        required = rule.params["count"]
        pool = self._source_pool(rule.params.get("cited_only", False))
        eligible = {
            source["id"]
            for source in pool
            if source["source_type"] == "primary" and self._successfully_accessed(source)
        }
        details = {"required": required, "observed": len(eligible)}
        if len(eligible) >= required:
            return self._pass(rule, "observed {} primary source(s)".format(len(eligible)), details)
        return self._fail(
            rule,
            "requires at least {} primary source(s), observed {}".format(required, len(eligible)),
            [],
            details,
        )

    def _factual_claims_cited(self, rule: Rule) -> Finding:
        factual = [claim for claim in self._retained_claims() if claim["kind"] == "factual"]
        missing = [claim["id"] for claim in factual if not claim["citations"]]
        if not missing:
            return self._pass(
                rule, "all {} retained factual claim(s) declare citations".format(len(factual))
            )
        return self._fail(
            rule,
            "{} retained factual claim(s) have no citation".format(len(missing)),
            missing,
        )

    def _citations_resolve(self, rule: Rule) -> Finding:
        unresolved: List[str] = []
        for claim in self.trace["claims"]:
            for citation_id in claim["citations"]:
                citation = self.citations.get(citation_id)
                if citation is None:
                    unresolved.append("{}->{}".format(claim["id"], citation_id))
                elif citation["source_id"] not in self.sources:
                    unresolved.append("{}->{}->{}".format(claim["id"], citation_id, citation["source_id"]))
        for citation in self.trace["citations"]:
            if citation["source_id"] not in self.sources:
                unresolved.append("{}->{}".format(citation["id"], citation["source_id"]))
        if not unresolved:
            return self._pass(rule, "all citation references resolve to source records")
        return self._fail(
            rule,
            "{} citation path(s) do not resolve".format(len(set(unresolved))),
            unresolved,
        )

    def _quotes_verbatim(self, rule: Rule) -> Finding:
        mismatches: List[str] = []
        for quote in self.trace["quotes"]:
            source = self.sources.get(quote["source_id"])
            if source is None or quote["text"] not in source["fetched_text"]:
                mismatches.append(quote["id"])
        if not mismatches:
            return self._pass(
                rule, "all {} quote(s) occur verbatim in fetched text".format(len(self.trace["quotes"]))
            )
        return self._fail(
            rule,
            "{} quote(s) were not found verbatim in their source text".format(len(mismatches)),
            mismatches,
        )

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _quantitative_values(self, rule: Rule) -> Finding:
        normalize = rule.params.get("normalize_whitespace", True)
        missing: List[str] = []
        checked = 0
        for claim in self._retained_claims():
            values = claim.get("quantitative_values", [])
            if not values:
                continue
            evidence_texts: List[str] = []
            for citation_id in claim["citations"]:
                citation = self.citations.get(citation_id)
                source = self.sources.get(citation["source_id"]) if citation else None
                if source:
                    evidence_texts.append(source["fetched_text"])
            if normalize:
                evidence_texts = [self._normalize_whitespace(text) for text in evidence_texts]
            for index, raw_value in enumerate(values):
                value = raw_value.get("value") if isinstance(raw_value, dict) else raw_value
                rendered = str(value)
                if normalize:
                    rendered = self._normalize_whitespace(rendered)
                checked += 1
                if not any(rendered in text for text in evidence_texts):
                    missing.append("{}:{}:{}".format(claim["id"], index, rendered))
        if not missing:
            return self._pass(
                rule, "all {} declared quantitative value(s) occur in cited evidence text".format(checked)
            )
        return self._fail(
            rule,
            "{} declared quantitative value(s) were absent from cited evidence".format(len(missing)),
            missing,
            {"checked": checked},
        )

    def _sources_accessed_current_run(self, rule: Rule) -> Finding:
        pool = self._source_pool(rule.params.get("cited_only", True))
        stale = [
            source["id"]
            for source in pool
            if source["access"]["run_id"] != self.run_id
            or source["access"]["status"] != "success"
        ]
        if not stale:
            return self._pass(
                rule, "all {} selected source(s) were accessed successfully in run {}".format(len(pool), self.run_id)
            )
        return self._fail(
            rule,
            "{} selected source(s) lack a successful current-run access".format(len(stale)),
            stale,
        )

    def _retrieval_results(self, rule: Rule) -> Finding:
        required = rule.params.get("min_count", 1)
        events = [
            event
            for event in self.trace["events"]
            if event["type"] == "retrieval"
            and event["run_id"] == self.run_id
            and event["status"] == "success"
        ]
        observed = sum(event.get("result_count", 0) for event in events)
        details = {"required": required, "observed": observed, "events": len(events)}
        if events and observed >= required:
            return self._pass(
                rule,
                "successful current-run retrieval returned {} result(s)".format(observed),
                details,
            )
        return self._fail(
            rule,
            "requires successful retrieval with at least {} result(s), observed {}".format(required, observed),
            [event["id"] for event in events],
            details,
        )

    def _unsupported_labeled_or_removed(self, rule: Rule) -> Finding:
        invalid = [
            claim["id"]
            for claim in self.trace["claims"]
            if claim["kind"] == "factual"
            and claim["support"] == "unsupported"
            and claim["action"] not in ("labeled", "removed")
        ]
        if not invalid:
            return self._pass(rule, "all unsupported factual claims are labeled or removed")
        return self._fail(
            rule,
            "{} unsupported factual claim(s) are retained without a label".format(len(invalid)),
            invalid,
        )

    def _uncertainty_reason(self, rule: Rule) -> Finding:
        missing = [
            claim["id"]
            for claim in self._retained_claims()
            if claim["kind"] == "factual"
            and claim["support"] in ("uncertain", "unsupported")
            and not str(claim.get("uncertainty_reason", "")).strip()
        ]
        if not missing:
            return self._pass(rule, "all retained uncertain claims state an uncertainty reason")
        return self._fail(
            rule,
            "{} uncertain or unsupported retained claim(s) omit a reason".format(len(missing)),
            missing,
        )

    def _jurisdiction_allowlist(self, rule: Rule) -> Finding:
        allowed = {item.casefold() for item in rule.params["allow"]}
        pool = self._source_pool(rule.params.get("cited_only", True))
        invalid = [
            source["id"]
            for source in pool
            if not isinstance(source.get("jurisdiction"), str)
            or source["jurisdiction"].casefold() not in allowed
        ]
        if not invalid:
            return self._pass(
                rule, "all {} selected source(s) use allowed jurisdictions".format(len(pool))
            )
        return self._fail(
            rule,
            "{} selected source(s) are outside the jurisdiction allowlist".format(len(invalid)),
            invalid,
            {"allow": sorted(rule.params["allow"])},
        )

    @staticmethod
    def _domain_allowed(hostname: str, allowed: Set[str]) -> bool:
        host = hostname.rstrip(".").casefold()
        return any(host == domain or host.endswith("." + domain) for domain in allowed)

    def _source_domain_allowlist(self, rule: Rule) -> Finding:
        allowed = {item.strip().lstrip(".").rstrip(".").casefold() for item in rule.params["allow"]}
        pool = self._source_pool(rule.params.get("cited_only", True))
        invalid: List[str] = []
        for source in pool:
            try:
                hostname = urlparse(source["url"]).hostname
            except ValueError:
                hostname = None
            if not hostname or not self._domain_allowed(hostname, allowed):
                invalid.append(source["id"])
        if not invalid:
            return self._pass(
                rule, "all {} selected source(s) use allowed domains".format(len(pool))
            )
        return self._fail(
            rule,
            "{} selected source(s) are outside the domain allowlist".format(len(invalid)),
            invalid,
            {"allow": sorted(allowed)},
        )

    def _contradiction_search(self, rule: Rule) -> Finding:
        high_risk = [claim for claim in self._retained_claims() if claim.get("risk") == "high"]
        searched = {
            event.get("claim_id")
            for event in self.trace["events"]
            if event["type"] == "contradiction_search"
            and event["run_id"] == self.run_id
            and event["status"] == "success"
        }
        missing = [claim["id"] for claim in high_risk if claim["id"] not in searched]
        if not missing:
            return self._pass(
                rule, "all {} high-risk retained claim(s) have a contradiction search event".format(len(high_risk))
            )
        return self._fail(
            rule,
            "{} high-risk retained claim(s) lack a successful contradiction search".format(len(missing)),
            missing,
        )

    def _completion_requires_core(self, rule: Rule) -> Finding:
        status = self.trace["output"]["completion_status"]
        required = rule.params.get("min_count", 1)
        if status != "completed":
            return self._pass(rule, "output status is {}; completion gate is not triggered".format(status))
        events = [
            event
            for event in self.trace["events"]
            if event["type"] == "retrieval"
            and event.get("core") is True
            and event["run_id"] == self.run_id
            and event["status"] == "success"
        ]
        observed = sum(event.get("result_count", 0) for event in events)
        details = {"required": required, "observed": observed, "events": len(events)}
        if events and observed >= required:
            return self._pass(
                rule,
                "completed output follows core retrieval with {} result(s)".format(observed),
                details,
            )
        return self._fail(
            rule,
            "output is completed but core retrieval returned fewer than {} result(s)".format(required),
            [event["id"] for event in events],
            details,
        )


def evaluate(contract: Contract, trace: Dict[str, Any]) -> EvaluationResult:
    """Convenience function for one evaluation."""

    return Evaluator(contract, trace).evaluate()
