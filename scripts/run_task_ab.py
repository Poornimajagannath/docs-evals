#!/usr/bin/env python3
"""Live-agent task A/B eval CLI (spec v3.1 phase 4).

Default is dry-run (scores proposals without live API calls).
Use --live with STRIPE_TEST_SECRET_KEY for Stripe sandbox calls.
Never single-arm.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docs_evals.task_ab import HttpResult, run_trial, summarize_ab, write_ab_report  # noqa: E402
from docs_evals.tasks.stripe_connect import (  # noqa: E402
    METRIC_KEYS,
    ArmDocStore,
    connect_create_account_spec,
)

DEFAULT_LLM = "http://127.0.0.1:8000/v1/chat/completions"
DEFAULT_MODEL = "nvidia/Qwen3.6-35B-A3B-NVFP4"


def stripe_post(path: str, body: Dict[str, Any]) -> HttpResult:
    key = os.environ.get("STRIPE_TEST_SECRET_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        return HttpResult(0, "", error="Missing STRIPE_TEST_SECRET_KEY")
    req = urllib.request.Request(
        f"https://api.stripe.com{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return HttpResult(resp.status, resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return HttpResult(exc.code, exc.read().decode("utf-8", errors="replace"), error=str(exc)[:200])


def _check_stripe_creds() -> None:
    if not (os.environ.get("STRIPE_TEST_SECRET_KEY") or os.environ.get("STRIPE_SECRET_KEY")):
        raise RuntimeError("Missing STRIPE_TEST_SECRET_KEY for live A/B")


def run_ab(
    *,
    control_root: Path,
    treatment_root: Path,
    out_dir: Path,
    trials: int = 3,
    step_budget: int = 8,
    llm_url: str = DEFAULT_LLM,
    model: str = DEFAULT_MODEL,
    live: bool = False,
) -> int:
    spec = connect_create_account_spec()
    stores = {
        "A": ArmDocStore("A", control_root, treatment_root),
        "B": ArmDocStore("B", control_root, treatment_root),
    }
    results = []
    for arm in ("A", "B"):
        for t in range(1, trials + 1):
            results.append(
                run_trial(
                    arm=arm,
                    trial=t,
                    store=stores[arm],
                    spec=spec,
                    llm_url=llm_url,
                    model=model,
                    step_budget=step_budget,
                    execute=live,
                    execute_request=stripe_post if live else None,
                    check_creds=_check_stripe_creds if live else None,
                )
            )

    summary = summarize_ab(results, metric_keys=METRIC_KEYS)
    write_ab_report(
        out_dir=out_dir,
        spec=spec,
        summary=summary,
        results=results,
        meta={"model": model, "step_budget": step_budget, "trials_per_arm": trials, "live": live},
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, default=ROOT / "tests" / "example_corpus" / "corpus" / "control")
    parser.add_argument("--treatment", type=Path, default=ROOT / "tests" / "example_corpus" / "corpus" / "treatment")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "ab_connect_create_account")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--step-budget", type=int, default=8)
    parser.add_argument("--llm-url", default=DEFAULT_LLM)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    return run_ab(
        control_root=args.control,
        treatment_root=args.treatment,
        out_dir=args.out_dir,
        trials=args.trials,
        step_budget=args.step_budget,
        llm_url=args.llm_url,
        model=args.model,
        live=args.live,
    )


if __name__ == "__main__":
    raise SystemExit(main())
