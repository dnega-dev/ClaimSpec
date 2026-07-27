# Security policy

## Supported versions

ClaimSpec is currently an MVP. Security fixes are applied to the latest `0.1.x` release and the unreleased development line.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| Older | No |

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the maintainers using the private security contact associated with the distribution or repository where you obtained ClaimSpec. If that channel is not visible, ask the maintainer for a private reporting route without including exploit details. Do not include sensitive traces, source text, tokens, or personal data in a public issue.

A useful report includes:

- affected ClaimSpec version and Python version;
- command or API path involved;
- a minimized contract/trace that contains no secrets;
- expected and observed behavior;
- impact and any known mitigations.

Maintainers should acknowledge a report, reproduce it, assess supported versions, prepare a fix and regression test, and coordinate disclosure with the reporter. No response-time guarantee is made by this volunteer project.

## Threat model and hardening guidance

ClaimSpec treats contract and trace files as untrusted data. It does not evaluate Python, invoke a shell, fetch source URLs, or execute embedded content. It writes only to paths explicitly requested through `init`, `--output`, or schema output.

Deployers remain responsible for:

- limiting file size, record count, and `fetched_text` length before parsing;
- constraining input/output paths when ClaimSpec is exposed through a service;
- applying process time and memory limits to adversarial inputs;
- preventing symlink/path attacks in a privileged wrapper;
- redacting sensitive fetched text from traces and reports;
- authenticating and integrity-protecting traces if producers are not trusted; and
- independently enforcing network, provenance, and publisher-identity controls.

A successful ClaimSpec result is not a trust boundary. Source type, jurisdiction, fetched text, access status, event status, and result counts are declarations in the trace. The verifier checks consistency with the contract; it does not attest those declarations or establish factual truth.
