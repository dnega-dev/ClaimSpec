"""Text, JSON, JUnit XML, and SARIF result renderers."""

import json
import xml.etree.ElementTree as ET
from typing import Callable, Dict

from .model import EvaluationResult
from .rules import RULES


def render_text(result: EvaluationResult) -> str:
    """Render a concise human-readable report."""

    state = "PASS" if result.passed else "FAIL"
    lines = [
        "{} ClaimSpec contract {!r} for run {}".format(
            state, result.contract_name, result.run_id
        ),
        "rules: {} passed, {} failed, {} total".format(
            result.summary["pass"], result.summary["fail"], result.summary["total"]
        ),
    ]
    for finding in result.findings:
        line = "[{}] {}: {}".format(finding.status.upper(), finding.rule, finding.message)
        if finding.subjects:
            line += " (subjects: {})".format(", ".join(finding.subjects))
        lines.append(line)
    return "\n".join(lines) + "\n"


def render_json(result: EvaluationResult) -> str:
    """Render the normative result object as pretty JSON."""

    return json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"


def render_junit(result: EvaluationResult) -> str:
    """Render one testcase per contract rule as JUnit XML."""

    suite = ET.Element(
        "testsuite",
        {
            "name": "claimspec.{}".format(result.contract_name),
            "tests": str(result.summary["total"]),
            "failures": str(result.summary["fail"]),
            "errors": "0",
            "skipped": "0",
        },
    )
    properties = ET.SubElement(suite, "properties")
    ET.SubElement(properties, "property", {"name": "run_id", "value": result.run_id})
    ET.SubElement(
        properties,
        "property",
        {"name": "contract_version", "value": result.contract_version},
    )
    for finding in result.findings:
        case = ET.SubElement(
            suite,
            "testcase",
            {"classname": "claimspec.rules", "name": finding.rule},
        )
        if finding.status == "fail":
            failure = ET.SubElement(case, "failure", {"message": finding.message, "type": "GroundingContractFailure"})
            failure.text = json.dumps(finding.to_dict(), sort_keys=True)
    return ET.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"


def render_sarif(result: EvaluationResult) -> str:
    """Render failed findings as SARIF 2.1.0 results."""

    used_rules = []
    for finding in result.findings:
        metadata = RULES.get(finding.rule, {})
        used_rules.append(
            {
                "id": finding.rule,
                "name": finding.rule,
                "shortDescription": {"text": metadata.get("summary", finding.rule)},
                "helpUri": "https://claimspec.dev/rules/{}".format(finding.rule),
            }
        )
    sarif_results = []
    for finding in result.findings:
        if finding.status != "fail":
            continue
        item = {
            "ruleId": finding.rule,
            "level": "error",
            "message": {"text": finding.message},
            "properties": {
                "runId": result.run_id,
                "subjects": finding.subjects,
                "details": finding.details,
            },
        }
        if finding.subjects:
            item["locations"] = [
                {
                    "logicalLocations": [
                        {
                            "name": subject,
                            "fullyQualifiedName": "trace/{}".format(subject),
                            "kind": "traceSubject",
                        }
                    ]
                }
                for subject in finding.subjects
            ]
        sarif_results.append(item)
    document = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ClaimSpec",
                        "informationUri": "https://claimspec.dev/",
                        "semanticVersion": "0.1.0",
                        "rules": used_rules,
                    }
                },
                "invocations": [{"executionSuccessful": result.passed}],
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


RENDERERS: Dict[str, Callable[[EvaluationResult], str]] = {
    "text": render_text,
    "json": render_json,
    "junit": render_junit,
    "sarif": render_sarif,
}


def render(result: EvaluationResult, format_name: str) -> str:
    """Render a result using a registered output format."""

    try:
        renderer = RENDERERS[format_name]
    except KeyError:
        raise ValueError("unknown output format {!r}".format(format_name))
    return renderer(result)
