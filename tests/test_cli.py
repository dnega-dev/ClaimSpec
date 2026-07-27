import contextlib
import io
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from claimspec.cli import run
from claimspec.parser import load_contract

from common import CONTRACTS, EXAMPLES, ROOT, VALID_TRACE


class CLITests(unittest.TestCase):
    def invoke(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_init_creates_parseable_contract_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            path = Path(temp_dir) / "new.claimspec"
            code, out, err = self.invoke(["init", str(path), "--name", "cli test"])
            self.assertEqual(code, 0)
            self.assertEqual(err, "")
            self.assertIn("created", out)
            self.assertEqual(load_contract(str(path)).name, "cli test")
            code, out, err = self.invoke(["init", str(path)])
            self.assertEqual(code, 2)
            self.assertIn("already exists", err)
            code, _, _ = self.invoke(["init", str(path), "--force"])
            self.assertEqual(code, 0)

    def test_check_text_passes_and_failing_trace_returns_one(self):
        baseline = str(CONTRACTS / "01-baseline.claimspec")
        code, out, err = self.invoke(["check", baseline, str(VALID_TRACE)])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("PASS ClaimSpec", out)
        invalid = EXAMPLES / "traces" / "invalid" / "04-nonverbatim-quote.json"
        code, out, err = self.invoke(["check", baseline, str(invalid)])
        self.assertEqual((code, err), (1, ""))
        self.assertIn("[FAIL] quotes_verbatim", out)

    def test_check_json_output_can_be_written_to_file(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT)) as temp_dir:
            output = Path(temp_dir) / "result.json"
            code, out, err = self.invoke(
                [
                    "check",
                    str(CONTRACTS / "01-baseline.claimspec"),
                    str(VALID_TRACE),
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual((code, out, err), (0, "", ""))
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["passed"])

    def test_check_junit_and_sarif_outputs(self):
        contract = str(CONTRACTS / "07-quantitative-audit.claimspec")
        trace = str(EXAMPLES / "traces" / "invalid" / "05-quantitative-value-absent.json")
        code, junit, _ = self.invoke(["check", contract, trace, "--format", "junit"])
        self.assertEqual(code, 1)
        self.assertEqual(ET.fromstring(junit).tag, "testsuite")
        code, sarif, _ = self.invoke(["check", contract, trace, "--format", "sarif"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(sarif)["version"], "2.1.0")

    def test_explain_lists_rules_and_contract_subset(self):
        code, out, err = self.invoke(["explain", "--rule", "quotes_verbatim"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("occur character-for-character", out)
        self.assertNotIn("min_sources\n", out)
        code, out, _ = self.invoke(
            ["explain", str(CONTRACTS / "20-minimal.claimspec"), "--json"]
        )
        data = json.loads(out)
        self.assertEqual(set(data), {"factual_claims_cited", "citations_resolve"})

    def test_schema_prints_each_schema(self):
        for kind in ("trace", "contract", "result"):
            with self.subTest(kind=kind):
                code, out, err = self.invoke(["schema", kind])
                self.assertEqual((code, err), (0, ""))
                data = json.loads(out)
                self.assertEqual(data["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_malformed_trace_is_exit_two(self):
        invalid = EXAMPLES / "traces" / "invalid" / "20-structural-missing-events.json"
        code, out, err = self.invoke(
            ["check", str(CONTRACTS / "01-baseline.claimspec"), str(invalid)]
        )
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("$.events is required", err)

    def test_missing_file_is_exit_two(self):
        code, out, err = self.invoke(["check", "missing.claimspec", "missing.json"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("cannot read contract", err)


if __name__ == "__main__":
    unittest.main()
