"""Documented evals-skills loop over existing A/B JSON reports.

Steps: flatten traces → review → three binary judges → TPR/TNR calibrate.
Reads the JSON the harness already writes. Writes JSONL. No new store.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

# Modes named by error analysis of bench-new evals/ab_* traces (2026-09-23).
# Do not add a judge for a mode the traces did not name.
JUDGE_MODES: Tuple[str, ...] = (
    "faithfulness-to-raw",
    "auth-not-asserted",
    "required-fields",
)

# Agent HTTP Signature construction is a harness arm, not a judge.
AUTH_FROM_DOCS_IS_CODE_ARM = True

# Consumer ArmDocStore.get slices at this many characters (bench-new).
PAGE_CAP_CHARS = 12000

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def prompt_path(mode: str) -> Path:
    if mode not in JUDGE_MODES:
        raise KeyError(f"no stub for {mode!r}; named modes are {JUDGE_MODES}")
    slug = mode.replace("-", "_")
    path = _PROMPT_DIR / f"{slug}.md"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def flatten_ab_reports(reports_dir: Path, *, include_latest: bool = False) -> List[Dict[str, Any]]:
    """One JSONL-shaped row per trial from existing ``ab-report*.json`` files."""
    rows: List[Dict[str, Any]] = []
    if not reports_dir.is_dir():
        return rows
    for path in sorted(reports_dir.rglob("ab-report*.json")):
        if not include_latest and path.name.endswith("-latest.json"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        task_id = payload.get("task_id")
        for trial in payload.get("trials") or []:
            details = [(s.get("action"), s.get("detail") or {}) for s in trial.get("steps") or []]
            seeded = any(d.get("seeded") for _, d in details)
            notes = trial.get("notes") or ""
            rows.append(
                {
                    "source": str(path),
                    "task_id": task_id,
                    "arm": trial.get("arm"),
                    "trial": trial.get("trial"),
                    "gate_pass": bool(trial.get("gate_pass")),
                    "auth_blocked": bool(trial.get("auth_blocked")),
                    "endpoint_correct": bool(trial.get("endpoint_correct")),
                    "http_status": trial.get("http_status"),
                    "steps_to_success": trial.get("steps_to_success"),
                    "guesses_or_backtracks": trial.get("guesses_or_backtracks"),
                    "seeded": seeded,
                    "unparseable": "unparseable" in notes.lower(),
                    "required_fields_mentioned": "required field" in notes.lower(),
                    "notes": notes,
                    "actions": [a for a, _ in details],
                    "steps": trial.get("steps") or [],
                    "extra": trial.get("extra") or {},
                }
            )
    return rows


def write_trace_jsonl(rows: Sequence[Mapping[str, Any]], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(dict(row), ensure_ascii=False) for row in rows]
    dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return dest


def scan_harness_artefacts(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Surface truncation/seeding/auth-silence artefacts. These are not judges."""
    n = len(rows)
    return {
        "trials": n,
        "page_cap_chars": PAGE_CAP_CHARS,
        "seeded_trials": sum(1 for r in rows if r.get("seeded")),
        "auth_blocked_trials": sum(1 for r in rows if r.get("auth_blocked")),
        "unparseable_trials": sum(1 for r in rows if r.get("unparseable")),
        "required_fields_mentioned": sum(1 for r in rows if r.get("required_fields_mentioned")),
        "gate_pass": sum(1 for r in rows if r.get("gate_pass")),
        "auth_from_docs": "code_arm_not_judge",
        "judge_modes": list(JUDGE_MODES),
    }


def tpr_tnr(
    pairs: Iterable[Mapping[str, str]],
    *,
    human_key: str = "human",
    judge_key: str = "judge",
    positive: str = "Pass",
    negative: str = "Fail",
) -> Dict[str, Any]:
    """TPR/TNR from labeled JSONL rows. Empty input is not a calibrated score."""
    tp = fp = tn = fn = 0
    other = 0
    for row in pairs:
        human = row.get(human_key)
        judge = row.get(judge_key)
        if human not in (positive, negative) or judge not in (positive, negative):
            other += 1
            continue
        if human == positive and judge == positive:
            tp += 1
        elif human == positive and judge == negative:
            fn += 1
        elif human == negative and judge == negative:
            tn += 1
        else:
            fp += 1
    pos = tp + fn
    neg = tn + fp
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "skipped": other,
        "tpr": (tp / pos) if pos else None,
        "tnr": (tn / neg) if neg else None,
        "calibrated": pos >= 1 and neg >= 1,
    }


def load_label_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
