import json
import unittest
import xml.etree.ElementTree as ET

from claimspec.evaluator import evaluate
from claimspec.parser import parse_claimspec
from claimspec.renderers import render, render_json, render_junit, render_sarif, render_text

from common import trace_fixture


class RendererTests(unittest.TestCase):
    @staticmethod
    def failing_result():
        contract = parse_claimspec(
            'claimspec 1.0\nname "render-test"\nrequire min_sources count=99\nrequire citations_resolve\n'
        )
        return evaluate(contract, trace_fixture())

    def test_text_contains_summary_and_subject_diagnostics(self):
        text = render_text(self.failing_result())
        self.assertTrue(text.startswith("FAIL ClaimSpec contract 'render-test'"))
        self.assertIn("rules: 1 passed, 1 failed, 2 total", text)
        self.assertIn("[FAIL] min_sources", text)

    def test_json_is_result_object(self):
        data = json.loads(render_json(self.failing_result()))
        self.assertFalse(data["passed"])
        self.assertEqual(data["contract"]["name"], "render-test")
        self.assertEqual(len(data["findings"]), 2)

    def test_junit_has_one_testcase_per_rule_and_failure_payload(self):
        root = ET.fromstring(render_junit(self.failing_result()))
        self.assertEqual(root.tag, "testsuite")
        self.assertEqual(root.attrib["tests"], "2")
        self.assertEqual(root.attrib["failures"], "1")
        cases = root.findall("testcase")
        self.assertEqual([case.attrib["name"] for case in cases], ["min_sources", "citations_resolve"])
        self.assertIsNotNone(cases[0].find("failure"))
        self.assertIsNone(cases[1].find("failure"))

    def test_sarif_contains_only_failed_findings_as_results(self):
        data = json.loads(render_sarif(self.failing_result()))
        self.assertEqual(data["version"], "2.1.0")
        run = data["runs"][0]
        self.assertFalse(run["invocations"][0]["executionSuccessful"])
        self.assertEqual(len(run["tool"]["driver"]["rules"]), 2)
        self.assertEqual([item["ruleId"] for item in run["results"]], ["min_sources"])

    def test_dispatcher_rejects_unknown_format(self):
        with self.assertRaises(ValueError):
            render(self.failing_result(), "yaml")


if __name__ == "__main__":
    unittest.main()
