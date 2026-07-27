# ClaimSpec language and trace semantics

This document defines ClaimSpec 1.0 as implemented by the MVP. JSON Schemas describe interchange structure; this document defines evaluator behavior.

## Contract forms

### Line-oriented `.claimspec`

A contract is UTF-8 text. Blank lines and comments beginning with `#` are ignored. Quoted strings use shell-like quoting. The first non-comment statement is the version header.

```text
claimspec 1.0
name "contract name"
description "optional description"
require rule_name key=value key=value
```

Approximate grammar:

```ebnf
contract    = header, name, [description], 1*require ;
header      = "claimspec", space, "1.0" ;
name        = "name", space, string ;
description = "description", space, string ;
require     = "require", space, identifier, *(space, parameter) ;
parameter   = identifier, "=", value ;
value       = integer | float | boolean | csv-list | string ;
boolean     = "true" | "false" ;
csv-list    = string, 1*(",", string) ;
```

`name = "value"` and `description = "value"` are also accepted. Rule names may occur only once. Unknown statements, rules, and parameters are errors. A line number is retained for rule diagnostics.

Comma-separated lists are the most readable allowlist form:

```claimspec
require jurisdiction_allowlist allow=US,CA,EU
require source_domain_allowlist allow=example.gov,agency.example cited_only=true
```

### JSON contracts

JSON contracts use the normalized form:

```json
{
  "version": "1.0",
  "name": "research-baseline",
  "description": "Optional",
  "rules": [
    {"name": "min_sources", "count": 2},
    {"name": "factual_claims_cited"}
  ]
}
```

The CLI selects JSON for a `.json` extension and the line format otherwise. The parser API can also detect a leading `{` when no format hint is supplied.

## Rule reference

### `min_sources`

Parameters: required integer `count >= 0`; optional boolean `cited_only` (default `false`).

Counts distinct source records whose `access.status` is `success`. If `cited_only=true`, the source must be reached through a citation on a non-removed claim. This rule does not require the access record's `run_id` to be current; combine it with `sources_accessed_current_run` for that property.

### `min_primary_sources`

Parameters: required integer `count >= 0`; optional boolean `cited_only` (default `false`).

As above, but the source must also declare `source_type: "primary"`. Classification is trace data; ClaimSpec does not infer source type from a URL.

### `factual_claims_cited`

Every claim with `kind: "factual"` and an action other than `removed` must list at least one citation ID. Citation resolution is a separate rule, so use `citations_resolve` as well.

### `citations_resolve`

Every citation ID used by any claim must identify a citation record, and every citation record must identify an existing source record. This is referential integrity only. It does not decide whether the source supports, entails, or proves the claim.

### `quotes_verbatim`

Every `quotes[]` item must point to an existing source and its `text` must occur exactly in that source's supplied `fetched_text`. Comparison is case-sensitive and no whitespace, punctuation, Unicode, or HTML normalization is performed.

### `quantitative_values_in_evidence`

Optional boolean parameter `normalize_whitespace` defaults to `true`.

For every declared `quantitative_values[]` entry on a non-removed claim, the string form of `value` must occur in fetched text reached through that claim's citations. Whitespace runs are collapsed before matching by default. Numeric equivalence, unit conversion, locale conversion, rounding, tables, and semantic linkage are not inferred. Authors should record the exact source representation (for example, `"12.5%"`).

### `sources_accessed_current_run`

Optional boolean `cited_only` defaults to `true`.

Each selected source must have `access.run_id` equal to `run.id` and `access.status: "success"`. With the default, only sources reached through non-removed claims are selected. The record is an input assertion; the verifier does not independently contact the URL or attest the timestamp.

### `retrieval_results`

Optional integer `min_count >= 1` defaults to `1`.

At least one event must have:

- `type: "retrieval"`;
- `run_id` equal to the current run;
- `status: "success"`.

The sum of `result_count` across matching events must meet `min_count`. A missing `result_count` contributes zero.

### `unsupported_claims_labeled_or_removed`

A factual claim with `support: "unsupported"` must use action `labeled` or `removed`. A retained unsupported factual claim fails. ClaimSpec relies on the declared support state; it does not determine support from source semantics.

### `uncertainty_reason`

A non-removed factual claim with support `uncertain` or `unsupported` must contain a non-whitespace `uncertainty_reason`. Removed claims are excluded because they do not appear in output.

### `jurisdiction_allowlist`

Parameters: non-empty `allow` list; optional `cited_only` (default `true`).

Every selected source must have a jurisdiction exactly equal to one allowlist entry under case-insensitive comparison. Missing jurisdiction fails. There is no hierarchy inference: allowing `US` does not implicitly allow `US-CA`.

### `source_domain_allowlist`

Parameters: non-empty `allow` list; optional `cited_only` (default `true`).

The URL hostname must equal an allowed domain or be a dot-delimited subdomain of one. Matching is case-insensitive and strips terminal dots. For example, `data.example.gov` matches `example.gov`; `example.gov.evil.test` and `notexample.gov` do not. Paths, user-info, and query strings cannot create a match. This is a hostname syntax check, not an identity or content-quality guarantee.

### `contradiction_search_high_risk`

Every non-removed claim with `risk: "high"` must have a current-run event with `type: "contradiction_search"`, `status: "success"`, and a matching `claim_id`. A trace event shows that a step was recorded, not that the query was well chosen or exhaustive.

### `no_completion_without_core_retrieval`

Optional integer `min_count >= 1` defaults to `1`.

If `output.completion_status` is not `completed`, the completion gate passes without requiring core retrieval. For a completed output, at least one successful current-run retrieval event must set `core: true`, and matching events' summed result count must meet `min_count`.

## Trace conventions

The normative structure is `schemas/trace.schema.json`. Collections are required even when empty. IDs must be non-empty and unique within each collection.

### Claims and actions

- `retained`: emitted without an uncertainty label.
- `labeled`: emitted with an explicit qualification; `uncertainty_reason` records why.
- `removed`: excluded from output-oriented citation, value, allowlist, current-run, and risk checks.

`kind` separates factual assertions from opinions and instructions. Only factual claims are subject to citation and unsupported/uncertain-claim rules. High-risk contradiction search applies to every claim kind because a consequential instruction or opinion can also warrant challenge search.

### Source text

`fetched_text` is the exact text against which quote and quantitative occurrence checks run. Systems producing traces should preserve retrieval provenance and transformations outside this schema when auditability matters. ClaimSpec 1.0 has no signatures, content hashes, redirects, HTTP metadata, or independent fetcher.

### Events

Events belong to a run through `run_id`. `status: "failed"` never satisfies retrieval or contradiction-search requirements. Retrieval counts are summed, allowing multiple search calls. `core` identifies retrieval needed to answer the central request rather than optional enrichment.

### Completion

Completion is explicit rather than inferred from output text. Producers should use `partial`, `aborted`, or `refused` when the run did not complete. `no_completion_without_core_retrieval` only gates `completed`.

## Evaluation and result model

Rules are evaluated in contract order. Every rule emits exactly one finding with:

- `rule`: rule identifier;
- `status`: `pass` or `fail`;
- `message`: stable human-readable diagnosis;
- `subjects`: offending trace IDs or reference paths;
- optional `details`: observed/configured counts or allowlists.

A result passes only if all findings pass. The JSON result conforms to `schemas/result.schema.json`. Invalid contract or trace structure is an input error and exits with status 2 rather than producing a rule result.

## Security and resource limits

The parser never executes contract or trace content. It performs no network access. Nevertheless, input size is not capped in the library, and exact substring scans are proportional to supplied text and declared values. Callers accepting untrusted files should enforce file-size, record-count, and text-length limits before invoking ClaimSpec. See `SECURITY.md`.
