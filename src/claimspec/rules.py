"""Rule registry and human-readable rule documentation."""

from typing import Any, Dict


RULES: Dict[str, Dict[str, Any]] = {
    "min_sources": {
        "summary": "Require at least N distinct successfully accessed sources.",
        "params": {"count": "integer >= 0", "cited_only": "boolean (default false)"},
    },
    "min_primary_sources": {
        "summary": "Require at least N distinct sources classified as primary.",
        "params": {"count": "integer >= 0", "cited_only": "boolean (default false)"},
    },
    "factual_claims_cited": {
        "summary": "Require every retained factual claim to contain at least one citation reference.",
        "params": {},
    },
    "citations_resolve": {
        "summary": "Require claim citation IDs to resolve to citation records and source records.",
        "params": {},
    },
    "quotes_verbatim": {
        "summary": "Require each quote to occur character-for-character in its cited source fetched_text.",
        "params": {},
    },
    "quantitative_values_in_evidence": {
        "summary": "Require each declared quantitative value to occur literally in cited source text.",
        "params": {"normalize_whitespace": "boolean (default true)"},
    },
    "sources_accessed_current_run": {
        "summary": "Require cited sources to have a successful access record for the current run.",
        "params": {"cited_only": "boolean (default true)"},
    },
    "retrieval_results": {
        "summary": "Require retrieval events and at least a configured number of returned results.",
        "params": {"min_count": "integer >= 1 (default 1)"},
    },
    "unsupported_claims_labeled_or_removed": {
        "summary": "Require unsupported factual claims to be explicitly labeled or removed.",
        "params": {},
    },
    "uncertainty_reason": {
        "summary": "Require a non-empty reason on uncertain or unsupported retained factual claims.",
        "params": {},
    },
    "jurisdiction_allowlist": {
        "summary": "Restrict source jurisdiction values to an allowlist.",
        "params": {"allow": "non-empty list", "cited_only": "boolean (default true)"},
    },
    "source_domain_allowlist": {
        "summary": "Restrict source URL hostnames to exact or subdomain allowlist matches.",
        "params": {"allow": "non-empty list", "cited_only": "boolean (default true)"},
    },
    "contradiction_search_high_risk": {
        "summary": "Require a successful contradiction_search event for every high-risk retained claim.",
        "params": {},
    },
    "no_completion_without_core_retrieval": {
        "summary": "Forbid a completed output unless a successful core retrieval returned results.",
        "params": {"min_count": "integer >= 1 (default 1)"},
    },
}

RULE_ORDER = tuple(RULES)
