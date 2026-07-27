import copy
import unittest

from claimspec.errors import TraceValidationError
from claimspec.schema import get_schema, validate_trace

from common import trace_fixture


class TraceSchemaTests(unittest.TestCase):
    def test_valid_example_is_structurally_valid(self):
        validate_trace(trace_fixture())

    def test_missing_required_collection_is_rejected(self):
        trace = trace_fixture()
        del trace["events"]
        with self.assertRaises(TraceValidationError) as context:
            validate_trace(trace)
        self.assertIn("$.events is required", context.exception.errors)

    def test_duplicate_ids_are_rejected(self):
        trace = trace_fixture()
        duplicate = copy.deepcopy(trace["claims"][0])
        trace["claims"].append(duplicate)
        with self.assertRaisesRegex(TraceValidationError, "duplicate id"):
            validate_trace(trace)

    def test_invalid_claim_state_is_rejected(self):
        trace = trace_fixture()
        trace["claims"][0]["support"] = "maybe"
        with self.assertRaisesRegex(TraceValidationError, "support has an invalid value"):
            validate_trace(trace)

    def test_negative_result_count_is_rejected(self):
        trace = trace_fixture()
        trace["events"][0]["result_count"] = -1
        with self.assertRaisesRegex(TraceValidationError, "integer >= 0"):
            validate_trace(trace)

    def test_unknown_fields_and_duplicate_claim_citations_are_rejected(self):
        trace = trace_fixture()
        trace["unexpected"] = True
        trace["claims"][0]["unexpected"] = True
        trace["claims"][0]["citations"].append(trace["claims"][0]["citations"][0])
        with self.assertRaises(TraceValidationError) as context:
            validate_trace(trace)
        message = str(context.exception)
        self.assertIn("$.unexpected is not allowed", message)
        self.assertIn("$.claims[0].unexpected is not allowed", message)
        self.assertIn("citations must contain unique items", message)

    def test_nonfinite_quantitative_values_are_rejected(self):
        trace = trace_fixture()
        trace["claims"][0]["quantitative_values"] = [float("nan")]
        with self.assertRaisesRegex(TraceValidationError, "quantitative_values.*is invalid"):
            validate_trace(trace)

    def test_wrong_root_type_is_rejected(self):
        with self.assertRaisesRegex(TraceValidationError, "must be dict"):
            validate_trace([])

    def test_schema_getter_returns_isolated_copy(self):
        first = get_schema("trace")
        second = get_schema("trace")
        first["title"] = "changed"
        self.assertNotEqual(first["title"], second["title"])
        self.assertEqual(second["properties"]["schema_version"]["const"], "1.0")

    def test_unknown_schema_kind_is_rejected(self):
        with self.assertRaises(KeyError):
            get_schema("unknown")


if __name__ == "__main__":
    unittest.main()
