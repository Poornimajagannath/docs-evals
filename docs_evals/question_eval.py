"""Question eval core — score real questions against a markdown corpus."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from docs_evals.doc_store import MarkdownDocStore


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_cases(path: Path) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def predict_verdict(case: Dict[str, Any], store: MarkdownDocStore) -> Dict[str, Any]:
    question = case.get("user_query") or ""
    expected_sections = case.get("expected_doc_sections") or []
    expected_verdict = case.get("verdict_from_log") or "gap"

    hits = store.search(question, limit=8)
    hit_ids = [h["id"] for h in hits]

    def norm(s: str) -> str:
        return s.replace(".md", "").rstrip("/")

    expected_norm = {norm(s) for s in expected_sections}
    hit_norm = {norm(h) for h in hit_ids}
    matched_expected = expected_norm & hit_norm if expected_norm else set()
    any_hits = bool(hit_ids)

    if expected_verdict == "gap":
        if not expected_sections:
            predicted = "gap" if not any_hits else "partial"
        else:
            predicted = (
                "answered_from_docs"
                if matched_expected
                else ("partial" if any_hits else "gap")
            )
    elif expected_verdict == "partial":
        predicted = "partial" if (matched_expected or any_hits) else "gap"
    else:
        if expected_sections and matched_expected:
            predicted = "answered_from_docs"
        elif any_hits:
            predicted = "partial"
        else:
            predicted = "gap"

    return {
        "case_id": case.get("case_id"),
        "expected_verdict": expected_verdict,
        "predicted_verdict": predicted,
        "match": predicted == expected_verdict,
        "hits": hit_ids[:5],
        "matched_expected_sections": sorted(matched_expected),
    }


def run_eval(cases_path: Path, store: MarkdownDocStore, *, repo_root: Path) -> Dict[str, Any]:
    cases = load_cases(cases_path)
    rows = [predict_verdict(c, store) for c in cases]
    matched = sum(1 for r in rows if r["match"])
    by_expected: Dict[str, int] = {}
    by_predicted: Dict[str, int] = {}
    for r in rows:
        by_expected[r["expected_verdict"]] = by_expected.get(r["expected_verdict"], 0) + 1
        by_predicted[r["predicted_verdict"]] = by_predicted.get(r["predicted_verdict"], 0) + 1

    try:
        cases_source = str(cases_path.relative_to(repo_root))
    except ValueError:
        cases_source = str(cases_path)

    return {
        "evaluated_at": utc_now(),
        "cases_source": cases_source,
        "denominator": len(cases),
        "pages_in_corpus": len(store.pages),
        "matched": matched,
        "match_rate": round(matched / len(cases), 4) if cases else 0.0,
        "by_expected_verdict": by_expected,
        "by_predicted_verdict": by_predicted,
        "rows": rows,
        "gate": "evidence_only",
    }


def render_md(report: Dict[str, Any]) -> str:
    lines = [
        "# Question eval report",
        "",
        f"- Cases source: `{report['cases_source']}`",
        f"- Denominator: **{report['matched']}/{report['denominator']}** matched expected verdict",
        f"- Match rate: **{report['match_rate']:.1%}**",
        f"- Pages searched: **{report['pages_in_corpus']}**",
        f"- Gate: `{report['gate']}` (never blocks PR)",
        "",
        "## By expected verdict",
        "",
    ]
    for k, v in sorted(report.get("by_expected_verdict", {}).items()):
        lines.append(f"- {k}: **{v}/{report['denominator']}**")
    lines.extend(["", "## Mismatches", ""])
    mismatches = [r for r in report.get("rows") or [] if not r["match"]]
    if mismatches:
        for row in mismatches:
            lines.append(
                f"- `{row['case_id']}`: expected **{row['expected_verdict']}** "
                f"got **{row['predicted_verdict']}** hits={row['hits'][:3]}"
            )
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)
