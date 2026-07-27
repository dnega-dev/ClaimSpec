import json
import unittest

from claimspec.errors import ContractParseError, ContractValidationError
from claimspec.parser import format_contract, load_contract, parse_claimspec, parse_contract, parse_json_contract

from common import CONTRACTS


class ClaimSpecParserTests(unittest.TestCase):
    def test_parses_line_contract_with_comments_and_typed_values(self):
        contract = parse_claimspec(
            '''# leading comment
claimspec 1.0
name = "Readable contract"
description "A short description" # trailing comment
require min_sources count=2 cited_only=true
require source_domain_allowlist allow=example.gov,agency.example cited_only=false
''',
            source="inline.claimspec",
        )
        self.assertEqual(contract.name, "Readable contract")
        self.assertEqual(contract.description, "A short description")
        self.assertEqual(contract.rules[0].params, {"count": 2, "cited_only": True})
        self.assertEqual(
            contract.rules[1].params["allow"], ["example.gov", "agency.example"]
        )
        self.assertEqual(contract.rules[0].line, 5)

    def test_json_and_line_contract_round_trip(self):
        original = parse_json_contract(
            json.dumps(
                {
                    "version": "1.0",
                    "name": "round trip",
                    "description": "test",
                    "rules": [
                        {"name": "min_sources", "count": 2, "cited_only": True},
                        {"name": "jurisdiction_allowlist", "allow": ["US", "CA"]},
                    ],
                }
            )
        )
        reparsed = parse_claimspec(format_contract(original))
        self.assertEqual(reparsed.to_dict(), original.to_dict())

    def test_autodetects_json_without_hint(self):
        contract = parse_contract(
            '{"version":"1.0","name":"json","rules":[{"name":"citations_resolve"}]}'
        )
        self.assertEqual(contract.name, "json")

    def test_loads_every_example_contract(self):
        files = sorted(CONTRACTS.iterdir())
        self.assertGreaterEqual(len(files), 20)
        for path in files:
            with self.subTest(path=path.name):
                contract = load_contract(str(path))
                self.assertEqual(contract.version, "1.0")
                self.assertTrue(contract.rules)

    def test_requires_header(self):
        with self.assertRaisesRegex(ContractParseError, "first statement"):
            parse_claimspec('name "bad"\nrequire citations_resolve\n', "bad.claimspec")

    def test_rejects_unknown_statement_with_location(self):
        with self.assertRaises(ContractParseError) as context:
            parse_claimspec('claimspec 1.0\nname "bad"\nmaybe citations_resolve\n', "bad.claimspec")
        self.assertIn("bad.claimspec:3", str(context.exception))
        self.assertIn("unknown statement", str(context.exception))

    def test_rejects_unknown_rule(self):
        with self.assertRaisesRegex(ContractValidationError, "unknown rule"):
            parse_claimspec('claimspec 1.0\nname "bad"\nrequire magical_truth\n')

    def test_rejects_unknown_parameter(self):
        with self.assertRaisesRegex(ContractValidationError, "unknown parameter"):
            parse_claimspec('claimspec 1.0\nname "bad"\nrequire citations_resolve typo=true\n')

    def test_rejects_duplicate_rule(self):
        with self.assertRaisesRegex(ContractValidationError, "duplicate rule"):
            parse_claimspec(
                'claimspec 1.0\nname "bad"\nrequire citations_resolve\nrequire citations_resolve\n'
            )

    def test_rejects_invalid_counts_and_booleans(self):
        with self.assertRaisesRegex(ContractValidationError, "count"):
            parse_claimspec('claimspec 1.0\nname "bad"\nrequire min_sources count=-1\n')
        with self.assertRaisesRegex(ContractValidationError, "must be boolean"):
            parse_claimspec(
                'claimspec 1.0\nname "bad"\nrequire min_sources count=1 cited_only=yes\n'
            )

    def test_rejects_empty_contract_and_bad_json_shape(self):
        with self.assertRaises(ContractParseError):
            parse_claimspec("")
        with self.assertRaisesRegex(ContractParseError, "root must be an object"):
            parse_json_contract("[]")
        with self.assertRaisesRegex(ContractParseError, "must be an array"):
            parse_json_contract('{"version":"1.0","name":"x","rules":{}}')

    def test_rejects_duplicate_parameter_and_unclosed_quote(self):
        with self.assertRaisesRegex(ContractParseError, "duplicate parameter"):
            parse_claimspec(
                'claimspec 1.0\nname "x"\nrequire min_sources count=1 count=2\n'
            )
        with self.assertRaises(ContractParseError):
            parse_claimspec('claimspec 1.0\nname "unterminated\n')

    def test_rejects_duplicate_empty_description_and_unknown_json_field(self):
        with self.assertRaisesRegex(ContractParseError, "duplicate description"):
            parse_claimspec(
                'claimspec 1.0\nname "x"\ndescription ""\ndescription "again"\nrequire citations_resolve\n'
            )
        with self.assertRaisesRegex(ContractParseError, "unknown JSON contract field"):
            parse_json_contract(
                '{"version":"1.0","name":"x","rules":[{"name":"citations_resolve"}],"typo":true}'
            )
        with self.assertRaisesRegex(ContractParseError, "non-standard JSON constant"):
            parse_json_contract(
                '{"version":"1.0","name":"x","rules":[{"name":"min_sources","count":NaN}]}'
            )


if __name__ == "__main__":
    unittest.main()
