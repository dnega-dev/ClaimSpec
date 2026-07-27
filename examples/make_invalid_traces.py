#!/usr/bin/env python3
"""Rebuild the deliberately failing example traces from the valid full trace."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "traces" / "valid" / "full.json"
DEST = ROOT / "traces" / "invalid"
BASE = json.loads(SOURCE.read_text(encoding="utf-8"))


def emit(name, mutate):
    trace = copy.deepcopy(BASE)
    mutate(trace)
    (DEST / name).write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")


def claim(trace, claim_id):
    return next(item for item in trace["claims"] if item["id"] == claim_id)


def source(trace, source_id):
    return next(item for item in trace["sources"] if item["id"] == source_id)


emit("01-uncited-factual-claim.json", lambda t: claim(t, "claim-total").update(citations=[]))
emit("02-dangling-citation.json", lambda t: claim(t, "claim-total").update(citations=["missing-citation"]))
emit("03-missing-citation-source.json", lambda t: t["citations"][0].update(source_id="missing-source"))
emit("04-nonverbatim-quote.json", lambda t: t["quotes"][0].update(text="The total was approximately forty-two units."))
emit("05-quantitative-value-absent.json", lambda t: claim(t, "claim-total").update(quantitative_values=["999"]))
emit("06-source-from-prior-run.json", lambda t: source(t, "source-stat")["access"].update(run_id="run-older"))
emit("07-zero-retrieval-results.json", lambda t: t["events"][0].update(result_count=0))
emit("08-unsupported-retained.json", lambda t: claim(t, "claim-increase").update(support="unsupported", action="retained"))
emit("09-missing-uncertainty-reason.json", lambda t: claim(t, "claim-increase").update(uncertainty_reason=""))
emit("10-disallowed-jurisdiction.json", lambda t: source(t, "source-stat").update(jurisdiction="ZZ"))
emit("11-lookalike-domain.json", lambda t: source(t, "source-stat").update(url="https://example.gov.evil.test/report"))
emit("12-missing-contradiction-search.json", lambda t: t.update(events=[t["events"][0]]))
emit("13-completed-without-core-retrieval.json", lambda t: t["events"][0].update(core=False))


def too_few_sources(trace):
    trace["sources"] = [source(trace, "source-stat")]
    trace["citations"] = [trace["citations"][0]]
    claim(trace, "claim-total")["citations"] = ["cite-stat"]


emit("14-too-few-sources.json", too_few_sources)
emit("15-no-primary-source.json", lambda t: [item.update(source_type="secondary") for item in t["sources"]])
emit("16-retrieval-event-from-prior-run.json", lambda t: t["events"][0].update(run_id="run-older"))
emit("17-failed-source-access.json", lambda t: source(t, "source-stat")["access"].update(status="failed"))
emit("18-no-retrieval-event.json", lambda t: t.update(events=[t["events"][1]]))
emit("19-partial-but-uncited.json", lambda t: (t["output"].update(completion_status="partial"), claim(t, "claim-total").update(citations=[])))

structural = copy.deepcopy(BASE)
del structural["events"]
(DEST / "20-structural-missing-events.json").write_text(
    json.dumps(structural, indent=2) + "\n", encoding="utf-8"
)
