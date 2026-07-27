# ClaimSpec

ClaimSpec is a zero-runtime-dependency Python 3.9+ language and verifier for **grounding contracts**. A contract states observable requirements for a research-agent run; the verifier checks a JSON trace and emits deterministic text, JSON, JUnit, or SARIF results.

ClaimSpec checks trace consistency and evidence-presence conditions. **A passing check does not establish that a claim is true, that a source is trustworthy, or that a citation logically entails a claim.** In particular, the verifier does not fetch URLs. It evaluates the fetched text, access records, claims, and events supplied in the trace. Use provenance controls and human review where the risk warrants them.

## What the MVP checks

A contract can require:

- a minimum number of successfully accessed sources;
- a minimum number classified as primary sources;
- a citation reference on every retained factual claim;
- citation references that resolve to citation and source records;
- exact, case-sensitive occurrence of quotes in supplied fetched text;
- literal occurrence of declared quantitative values in cited evidence text;
- successful source access during the current run;
- successful retrieval with a nonzero/configurable result count;
- unsupported factual claims to be labeled or removed;
- a reason for retained uncertain or unsupported factual claims;
- jurisdiction and source-domain allowlists;
- a successful contradiction-search event for every retained high-risk claim; and
- no `completed` status when successful core retrieval did not return enough results.

The implementation uses only the Python standard library at runtime. JSON is the interchange format; the readable `.claimspec` format has no YAML dependency.

## Quick start

Run directly from a checkout:

```sh
export PYTHONPATH="$PWD/src"
python3 -m claimspec init research.claimspec
python3 -m claimspec check \
  examples/contracts/01-baseline.claimspec \
  examples/traces/valid/full.json
```

Or install the console script (the project itself declares no runtime dependencies):

```sh
python3 -m pip install -e .
claimspec check examples/contracts/01-baseline.claimspec examples/traces/valid/full.json
```

A small contract looks like this:

```claimspec
claimspec 1.0
name "research-baseline"
description "Evidence and retrieval gates"

require min_sources count=2
require min_primary_sources count=1
require factual_claims_cited
require citations_resolve
require quotes_verbatim
require quantitative_values_in_evidence
require sources_accessed_current_run
require retrieval_results min_count=1
require unsupported_claims_labeled_or_removed
require uncertainty_reason
require contradiction_search_high_risk
require no_completion_without_core_retrieval
```

The equivalent contract can be encoded as JSON. See `examples/contracts/21-public-records.json` and [`docs/language.md`](docs/language.md).

## CLI

### `init`

```sh
claimspec init [PATH] [--name NAME] [--force]
```

Writes a starter contract. The default path is `research.claimspec`; existing files are not replaced unless `--force` is present.

### `check`

```sh
claimspec check CONTRACT TRACE [--format text|json|junit|sarif] [--output PATH]
```

Exit status is `0` when every rule passes, `1` when one or more rules fail, and `2` for invalid input or I/O errors. Reports go to standard output unless `--output` is supplied.

Examples:

```sh
claimspec check contract.claimspec trace.json --format json
claimspec check contract.claimspec trace.json --format junit --output result.xml
claimspec check contract.claimspec trace.json --format sarif --output result.sarif
```

### `explain`

```sh
claimspec explain
claimspec explain contract.claimspec
claimspec explain --rule quotes_verbatim
claimspec explain contract.claimspec --json
```

Without arguments, lists all built-in rules. With a contract, lists the rules that contract uses.

### `schema`

```sh
claimspec schema trace
claimspec schema contract --output contract.schema.json
claimspec schema result --output result.schema.json
```

The same Draft 2020-12 schemas are committed under `schemas/` for tooling that should not invoke the CLI.

## Python API

The public package exports parsing, validation, evaluation, schema, and rendering helpers:

```python
from claimspec import evaluate, load_contract, load_trace, render

contract = load_contract("research.claimspec")
trace = load_trace("trace.json")
result = evaluate(contract, trace)
print(render(result, "json"), end="")
```

`result.passed` is true only when every configured rule passes. Invalid contract/trace structure raises a `ClaimSpecError` subclass rather than returning a rule finding.

## Trace model

A trace is a JSON object with these required collections:

- `run`: current run ID and timestamps;
- `output`: completion status (`completed`, `partial`, `aborted`, or `refused`);
- `claims`: typed claims, support/action labels, citation IDs, risk, and declared values;
- `citations`: stable citation IDs pointing to source IDs;
- `sources`: URL, source classification, jurisdiction, supplied fetched text, and access record;
- `quotes`: exact text plus its source ID;
- `events`: retrieval and contradiction-search records.

IDs must be unique within each collection. References are intentionally checked by contract rules rather than structural validation, so an unresolved reference produces a normal rule failure. See `schemas/trace.schema.json` and the annotated semantics in `docs/language.md`.

## Outputs

- **text** is optimized for local diagnosis.
- **JSON** conforms to `schemas/result.schema.json` and preserves structured subjects/details.
- **JUnit XML** emits one testcase per rule for CI test-report integrations.
- **SARIF 2.1.0** emits failed rules as error-level results with logical trace subjects.

No output format says that a citation proves truth; each reports only whether the configured grounding contract passed.

## Examples

`examples/contracts/` contains 24 contracts spanning general research, health, legal, policy, financial, quantitative, quotation, high-risk, allowlist, and completion-gate profiles. `examples/traces/invalid/` contains deliberately failing traces. `examples/invalid-manifest.json` maps each trace to a contract and expected failing rule(s). Regenerate the derived invalid traces with:

```sh
python3 examples/make_invalid_traces.py
```

## Development

```sh
./ci/check.sh
```

The check script compiles the package and runs the `unittest` suite. Tests require no third-party test runner. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Design boundaries

ClaimSpec is deliberately local and deterministic:

- it performs no network requests and executes no content from a trace;
- source classifications, fetched text, access records, and event records are assertions in the input unless an external system attests them;
- exact quote/value occurrence is a transcription/evidence-presence check, not semantic entailment;
- allowlists constrain declared URL hostnames/jurisdictions, not publisher identity or content quality;
- contradiction search is evidenced by an event record, not by an assessment that the search was exhaustive.

These boundaries make ClaimSpec suitable as one enforceable layer in a larger research-quality system, not as a truth oracle.

## License

Apache License 2.0. See [LICENSE](LICENSE).
