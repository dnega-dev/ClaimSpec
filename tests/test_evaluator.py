import json
import unittest

from claimspec.evaluator import evaluate, load_trace
from claimspec.errors import TraceValidationError
from claimspec.parser import load_contract, parse_claimspec

from common import CONTRACTS, EXAMPLES, trace_fixture


def one_rule(name, parameters=""):
    suffix = (" " + parameters) if parameters else ""
    return parse_claimspec(
        'claimspec 1.0\nname "test"\nrequire {}{}\n'.format(name, suffix)
    )


def evaluate_one(name, trace, parameters=""):
    return evaluate(one_rule(name, parameters), trace).findings[0]


class EvaluatorTests(unittest.TestCase):
    def test_valid_trace_passes_baseline(self):
        contract = load_contract(str(CONTRACTS / "01-baseline.claimspec"))
        result = evaluate(contract, trace_fixture())
        self.assertTrue(result.passed)
        self.assertEqual(result.summary, {"pass": 12, "fail": 0, "total": 12})
        self.assertTrue(all(finding.status == "pass" for finding in result.findings))

    def test_min_source_count_uses_successful_distinct_records(self):
        trace = trace_fixture()
        trace["sources"][0]["access"]["status"] = "failed"
        finding = evaluate_one("min_sources", trace, "count=2")
        self.assertEqual(finding.status, "fail")
        self.assertEqual(finding.details, {"required": 2, "observed": 1})

    def test_cited_only_source_count_excludes_uncited_source(self):
        trace = trace_fixture()
        trace["claims"][0]["citations"] = ["cite-stat"]
        finding = evaluate_one("min_sources", trace, "count=2 cited_only=true")
        self.assertEqual(finding.status, "fail")

    def test_primary_source_count(self):
        trace = trace_fixture()
        trace["sources"][0]["source_type"] = "secondary"
        finding = evaluate_one("min_primary_sources", trace, "count=1")
        self.assertEqual(finding.status, "fail")

    def test_uncited_removed_factual_claim_is_excluded(self):
        trace = trace_fixture()
        trace["claims"][0]["citations"] = []
        trace["claims"][0]["action"] = "removed"
        finding = evaluate_one("factual_claims_cited", trace)
        self.assertEqual(finding.status, "pass")

    def test_unresolved_claim_reference_and_orphan_citation_source_fail(self):
        trace = trace_fixture()
        trace["claims"][0]["citations"] = ["not-there"]
        trace["citations"].append({"id": "orphan", "source_id": "absent"})
        finding = evaluate_one("citations_resolve", trace)
        self.assertEqual(finding.status, "fail")
        self.assertIn("claim-total->not-there", finding.subjects)
        self.assertIn("orphan->absent", finding.subjects)

    def test_quote_matching_is_exact_and_case_sensitive(self):
        trace = trace_fixture()
        trace["quotes"][0]["text"] = trace["quotes"][0]["text"].lower()
        finding = evaluate_one("quotes_verbatim", trace)
        self.assertEqual(finding.status, "fail")
        self.assertEqual(finding.subjects, ["quote-total"])

    def test_quantitative_values_must_be_in_cited_evidence(self):
        trace = trace_fixture()
        trace["claims"][0]["quantitative_values"] = ["43"]
        finding = evaluate_one("quantitative_values_in_evidence", trace)
        self.assertEqual(finding.status, "fail")
        self.assertIn("claim-total:0:43", finding.subjects)

    def test_quantitative_whitespace_normalization_is_configurable(self):
        trace = trace_fixture()
        trace["claims"][0]["quantitative_values"] = ["42   units"]
        normalized = evaluate_one(
            "quantitative_values_in_evidence", trace, "normalize_whitespace=true"
        )
        exact = evaluate_one(
            "quantitative_values_in_evidence", trace, "normalize_whitespace=false"
        )
        self.assertEqual(normalized.status, "pass")
        self.assertEqual(exact.status, "fail")

    def test_source_must_be_successful_and_current(self):
        trace = trace_fixture()
        trace["sources"][0]["access"]["run_id"] = "old"
        trace["sources"][1]["access"]["status"] = "failed"
        finding = evaluate_one("sources_accessed_current_run", trace)
        self.assertEqual(finding.status, "fail")
        self.assertEqual(finding.subjects, ["source-review", "source-stat"])

    def test_retrieval_counts_only_successful_current_run_events(self):
        trace = trace_fixture()
        trace["events"].extend(
            [
                {
                    "id": "retrieval-old",
                    "type": "retrieval",
                    "run_id": "old",
                    "status": "success",
                    "occurred_at": "2025-01-01T00:00:00Z",
                    "result_count": 100,
                },
                {
                    "id": "retrieval-failed",
                    "type": "retrieval",
                    "run_id": trace["run"]["id"],
                    "status": "failed",
                    "occurred_at": "2025-01-01T00:00:00Z",
                    "result_count": 100,
                },
            ]
        )
        finding = evaluate_one("retrieval_results", trace, "min_count=6")
        self.assertEqual(finding.status, "fail")
        self.assertEqual(finding.details["observed"], 5)

    def test_unsupported_claim_must_be_labeled_or_removed(self):
        trace = trace_fixture()
        trace["claims"][0].update(support="unsupported", action="retained")
        finding = evaluate_one("unsupported_claims_labeled_or_removed", trace)
        self.assertEqual(finding.status, "fail")
        trace["claims"][0]["action"] = "labeled"
        self.assertEqual(
            evaluate_one("unsupported_claims_labeled_or_removed", trace).status, "pass"
        )

    def test_uncertain_factual_claim_requires_nonblank_reason(self):
        trace = trace_fixture()
        trace["claims"][1]["uncertainty_reason"] = "   "
        finding = evaluate_one("uncertainty_reason", trace)
        self.assertEqual(finding.status, "fail")
        self.assertEqual(finding.subjects, ["claim-increase"])

    def test_jurisdiction_allowlist_is_case_insensitive_but_exact(self):
        trace = trace_fixture()
        passed = evaluate_one("jurisdiction_allowlist", trace, "allow=us")
        self.assertEqual(passed.status, "pass")
        trace["sources"][0]["jurisdiction"] = "US-CA"
        failed = evaluate_one("jurisdiction_allowlist", trace, "allow=US")
        self.assertEqual(failed.status, "fail")

    def test_domain_allowlist_accepts_subdomains_not_lookalikes(self):
        trace = trace_fixture()
        passed = evaluate_one(
            "source_domain_allowlist", trace, "allow=example.gov,agency.example"
        )
        self.assertEqual(passed.status, "pass")
        trace["sources"][0]["url"] = "https://example.gov.evil.test/report"
        trace["sources"][1]["url"] = "https://notagency.example.net/review"
        failed = evaluate_one(
            "source_domain_allowlist", trace, "allow=example.gov,agency.example"
        )
        self.assertEqual(failed.status, "fail")
        self.assertEqual(failed.subjects, ["source-review", "source-stat"])
        trace["sources"][0]["url"] = "https://[invalid"
        malformed = evaluate_one(
            "source_domain_allowlist", trace, "allow=example.gov,agency.example"
        )
        self.assertEqual(malformed.status, "fail")
        self.assertIn("source-stat", malformed.subjects)

    def test_each_high_risk_claim_needs_its_own_contradiction_event(self):
        trace = trace_fixture()
        trace["claims"][1]["risk"] = "high"
        finding = evaluate_one("contradiction_search_high_risk", trace)
        self.assertEqual(finding.status, "fail")
        self.assertEqual(finding.subjects, ["claim-increase"])

    def test_completion_gate_only_triggers_for_completed_output(self):
        trace = trace_fixture()
        trace["events"][0]["core"] = False
        failed = evaluate_one("no_completion_without_core_retrieval", trace)
        self.assertEqual(failed.status, "fail")
        trace["output"]["completion_status"] = "partial"
        passed = evaluate_one("no_completion_without_core_retrieval", trace)
        self.assertEqual(passed.status, "pass")

    def test_result_serialization_matches_summary(self):
        result = evaluate(one_rule("min_sources", "count=99"), trace_fixture())
        data = result.to_dict()
        self.assertFalse(data["passed"])
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["summary"], {"pass": 0, "fail": 1, "total": 1})
        self.assertEqual(data["findings"][0]["details"]["required"], 99)

    def test_invalid_manifest_cases_have_expected_failures(self):
        manifest = json.loads(
            (EXAMPLES / "invalid-manifest.json").read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(len(manifest), 10)
        for case in manifest:
            trace_path = EXAMPLES / case["trace"]
            contract_path = EXAMPLES / case["contract"]
            with self.subTest(trace=trace_path.name):
                if case.get("schema_error"):
                    with self.assertRaises(TraceValidationError):
                        load_trace(str(trace_path))
                    continue
                result = evaluate(load_contract(str(contract_path)), load_trace(str(trace_path)))
                actual = sorted(
                    finding.rule for finding in result.findings if finding.status == "fail"
                )
                self.assertEqual(actual, sorted(case["expected_failing_rules"]))
                self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
