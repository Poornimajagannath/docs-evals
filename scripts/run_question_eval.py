#!/usr/bin/env python3
"""Question eval CLI — score real questions against a markdown corpus (evidence only)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docs_evals.doc_store import MarkdownDocStore  # noqa: E402
from docs_evals.question_eval import render_md, run_eval  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "tests" / "example_corpus" / "eval_cases" / "sample.jsonl",
    )
    parser.add_argument("--corpus", type=Path, action="append", default=[], help="content/ root (repeatable)")
    parser.add_argument("--generated", type=Path, help="optional generated/ root")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "question_eval")
    args = parser.parse_args()

    if not args.cases.is_file():
        print(f"ERROR: cases file missing: {args.cases}", file=sys.stderr)
        return 2

    corpus_roots = args.corpus or [ROOT / "tests" / "example_corpus" / "corpus" / "treatment"]
    prefixes: list[tuple[str, Path]] = [("content", p) for p in corpus_roots]
    if args.generated and args.generated.is_dir():
        prefixes.append(("generated", args.generated))

    store = MarkdownDocStore.from_roots(*prefixes)
    report = run_eval(args.cases, store, repo_root=ROOT)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    latest = args.out_dir / "question-eval-latest.json"
    (args.out_dir / f"question-eval-{stamp}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    latest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "question-eval-latest.md").write_text(render_md(report), encoding="utf-8")

    print(
        f"Question eval: {report['matched']}/{report['denominator']} "
        f"({report['match_rate']:.1%}) source={report['cases_source']}"
    )
    print(f"Wrote {latest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
