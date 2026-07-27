# Contributing to ClaimSpec

Thanks for improving ClaimSpec. Keep changes deterministic, standard-library-only at runtime, and compatible with Python 3.9+.

## Set up

No third-party runtime or test dependencies are required:

```sh
export PYTHONPATH="$PWD/src"
python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

The canonical local check is:

```sh
./ci/check.sh
```

An editable install is optional:

```sh
python3 -m pip install -e .
```

## Change guidelines

1. Add or update tests for every behavior change.
2. Preserve deterministic ordering and diagnostics; CI consumers may diff reports.
3. Do not add a runtime dependency without first demonstrating why the standard library is insufficient.
4. Keep the line language readable and reject unknown rules/parameters rather than silently ignoring them.
5. Update `docs/language.md`, schemas, examples, and the changelog when semantics or public fields change.
6. Treat traces as untrusted data. Do not add implicit network requests, code execution, template execution, or shell expansion.
7. Phrase checks precisely. Citation resolution or text occurrence does not establish truth or entailment.

## Adding a rule

A rule change normally touches:

- `src/claimspec/rules.py` for its registry description;
- `src/claimspec/parser.py` for parameter validation;
- `src/claimspec/evaluator.py` for deterministic evaluation;
- `docs/language.md` for normative behavior and edge cases;
- one or more example contracts and deliberately failing traces; and
- evaluator, parser, CLI/output, and manifest tests as appropriate.

Each rule should return one finding and identify offending trace subjects. Define how empty collections, removed claims, current-run identity, failed events, and malformed references behave.

## Schemas

The schema dictionaries in `src/claimspec/schema.py` are the source of truth. Regenerate committed copies after changing them:

```sh
PYTHONPATH=src python3 -m claimspec schema trace --output schemas/trace.schema.json
PYTHONPATH=src python3 -m claimspec schema contract --output schemas/contract.schema.json
PYTHONPATH=src python3 -m claimspec schema result --output schemas/result.schema.json
```

`./ci/check.sh` verifies that committed schema files are current.

## Examples

`examples/traces/invalid/` is generated from `examples/traces/valid/full.json`:

```sh
python3 examples/make_invalid_traces.py
```

Update `examples/invalid-manifest.json` whenever a case is added or its expected finding changes.

## Submitting changes

Use focused commits and include a concise rationale, behavior summary, test evidence, and compatibility/security notes. Do not include real user traces, copyrighted source dumps, credentials, or personal data.
