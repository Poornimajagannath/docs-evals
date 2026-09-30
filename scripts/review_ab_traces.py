#!/usr/bin/env python3
"""Flatten existing A/B JSON reports to JSONL and optionally compute TPR/TNR.

Does not run the A/B harness. Does not call a model.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docs_evals.judges.loop import (  # noqa: E402
    flatten_ab_reports,
    load_label_jsonl,
    scan_harness_artefacts,
    tpr_tnr,
    write_trace_jsonl,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, help="Directory containing ab-report*.json")
    parser.add_argument("--out", type=Path, help="JSONL destination for flattened trials")
    parser.add_argument("--include-latest", action="store_true")
    parser.add_argument(
        "--calibrate",
        type=Path,
        help="Labeled JSONL with human/judge Pass|Fail fields",
    )
    args = parser.parse_args()

    if not args.reports and not args.calibrate:
        parser.error("pass --reports and/or --calibrate")

    if args.reports:
        rows = flatten_ab_reports(args.reports, include_latest=args.include_latest)
        artefacts = scan_harness_artefacts(rows)
        dest = args.out or (args.reports / "ab_traces.jsonl")
        write_trace_jsonl(rows, dest)
        print(json.dumps({"out": str(dest), "artefacts": artefacts}, indent=2))

    if args.calibrate:
        if not args.calibrate.is_file():
            print(f"ERROR: labels file missing: {args.calibrate}", file=sys.stderr)
            return 2
        labels = load_label_jsonl(args.calibrate)
        print(json.dumps({"calibrate": str(args.calibrate), "tpr_tnr": tpr_tnr(labels)}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
