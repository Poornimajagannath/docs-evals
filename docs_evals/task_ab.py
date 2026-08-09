"""Shared live-agent A/B task eval runner (spec v3.1 phase 4).

Arm A = control docs (original site). Arm B = generated pages.
Held constant: model, prompt template, sandbox, step budget, trace format.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple


@dataclass
class HttpResult:
    status: int
    body: str = ""
    looks_like_jwt: bool = False
    error: Optional[str] = None


@dataclass
class StepTrace:
    step: int
    action: str
    detail: Dict[str, Any] = field(default_factory=dict)
    guess_or_backtrack: bool = False
    doc_sections: List[str] = field(default_factory=list)


@dataclass
class TrialResult:
    arm: str
    trial: int
    gate_pass: bool
    steps_to_success: Optional[int]
    guesses_or_backtracks: int
    failure_doc_sections: List[str]
    http_status: Optional[int]
    endpoint_correct: bool
    auth_blocked: bool
    extra: Dict[str, Any] = field(default_factory=dict)
    steps: List[StepTrace] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["steps"] = [asdict(s) for s in self.steps]
        return d


@dataclass
class TaskSpec:
    task_id: str
    title: str
    target_path: str
    task_prompt: str
    system_prompt: str
    seed_query: str
    seed_page_predicate: Callable[[str], bool]
    parse_proposal: Callable[[Dict[str, Any]], Tuple[str, Dict[str, Any], List[str]]]
    score_proposal: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    gate_pass: Callable[[HttpResult, Dict[str, Any]], bool]
    default_step_budget: int = 8


class DocStore(Protocol):
    arm: str

    def list_pages(self) -> List[str]: ...

    def search(self, query: str, *, limit: int = 5) -> List[Dict[str, str]]: ...

    def get(self, page_id: str) -> str: ...


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def chat(messages: List[Dict[str, str]], *, llm_url: str, model: str) -> str:
    import urllib.request

    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 1024,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": messages,
    }
    req = urllib.request.Request(
        llm_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    msg = body["choices"][0]["message"]
    content = msg.get("content") or msg.get("reasoning") or ""
    content = str(content).strip()
    if not content:
        raise RuntimeError(
            f"empty LLM content finish={body['choices'][0].get('finish_reason')}"
        )
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return content


def parse_action(raw: str, *, target_path: str) -> Dict[str, Any]:
    def _coerce(data: Dict[str, Any]) -> Dict[str, Any]:
        if "action" in data:
            return data
        if isinstance(data.get("body"), dict):
            return {
                "action": "propose_request",
                "path": data.get("path") or target_path,
                "body": data["body"],
                "rationale": "recovered from body wrapper",
                "doc_sources": data.get("doc_sources") or [],
            }
        return data

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return _coerce(data)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return _coerce(data)
        except json.JSONDecodeError:
            pass
    return {"action": "give_up", "reason": f"unparseable model output: {raw[:200]}"}


def run_trial(
    *,
    arm: str,
    trial: int,
    store: DocStore,
    spec: TaskSpec,
    llm_url: str,
    model: str,
    step_budget: int,
    execute: bool = True,
    execute_request: Optional[Callable[[str, Dict[str, Any]], HttpResult]] = None,
    check_creds: Optional[Callable[[], None]] = None,
) -> TrialResult:
    seed_hits = store.search(spec.seed_query)
    seed_page_id = ""
    seed_page_text = ""
    for hit in seed_hits:
        page = store.get(hit["id"])
        if spec.seed_page_predicate(page):
            seed_page_id = hit["id"]
            seed_page_text = page
            break
    if not seed_page_id and seed_hits:
        seed_page_id = seed_hits[0]["id"]
        seed_page_text = store.get(seed_page_id)

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": spec.system_prompt},
        {
            "role": "user",
            "content": (
                f"{spec.task_prompt}\n\nAvailable page ids (use get_page):\n"
                + "\n".join(f"- {p}" for p in store.list_pages()[:40])
                + "\n\nInitial search_docs results (already run for you):\n"
                + json.dumps(seed_hits, indent=2)
                + (
                    f"\n\nInitial get_page ({seed_page_id}) already run for you:\n"
                    + seed_page_text
                    if seed_page_id
                    else ""
                )
                + "\n\nNext: propose_request from the docs above, or get_page "
                "another id if needed."
            ),
        },
    ]
    steps: List[StepTrace] = [
        StepTrace(
            step=0,
            action="search_docs",
            detail={"query": spec.seed_query, "hits": [h["id"] for h in seed_hits], "seeded": True},
            doc_sections=[h["id"] for h in seed_hits],
        )
    ]
    if seed_page_id:
        steps.append(
            StepTrace(
                step=0,
                action="get_page",
                detail={"id": seed_page_id, "found": True, "seeded": True},
                doc_sections=[seed_page_id],
            )
        )

    guesses = 0
    failure_docs: List[str] = []
    last_sources = [h["id"] for h in seed_hits]
    http_status: Optional[int] = None
    endpoint_correct = False
    auth_blocked = False
    gate_pass = False
    steps_to_success: Optional[int] = None
    notes = ""
    extra: Dict[str, Any] = {}

    for i in range(1, step_budget + 1):
        try:
            raw = chat(messages, llm_url=llm_url, model=model)
        except Exception as exc:  # noqa: BLE001
            steps.append(StepTrace(step=i, action="llm_error", detail={"error": str(exc)[:200]}))
            notes = f"LLM error: {exc}"
            break

        action = parse_action(raw, target_path=spec.target_path)
        act = action.get("action")

        if act == "search_docs":
            hits = store.search(str(action.get("query") or spec.seed_query))
            last_sources = [h["id"] for h in hits]
            steps.append(
                StepTrace(
                    step=i,
                    action="search_docs",
                    detail={"query": action.get("query"), "hits": last_sources},
                    doc_sections=last_sources,
                )
            )
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {"role": "user", "content": "search_docs results:\n" + json.dumps(hits, indent=2)}
            )
            continue

        if act == "get_page":
            pid = str(action.get("id") or "")
            text = store.get(pid)
            last_sources = [pid]
            backtrack = "NOT FOUND" in text
            if backtrack:
                guesses += 1
            steps.append(
                StepTrace(
                    step=i,
                    action="get_page",
                    detail={"id": pid, "found": not backtrack},
                    guess_or_backtrack=backtrack,
                    doc_sections=[pid],
                )
            )
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"get_page {pid}:\n{text}"})
            continue

        if act == "propose_request":
            path, body, sources = spec.parse_proposal(action)
            if not sources:
                sources = last_sources
            scored = spec.score_proposal(path, body)
            endpoint_correct = bool(scored.get("endpoint_correct"))
            extra.update(scored)
            steps.append(
                StepTrace(
                    step=i,
                    action="propose_request",
                    detail={
                        "path": path,
                        "body_keys": sorted(body.keys()) if isinstance(body, dict) else [],
                        "rationale": str(action.get("rationale") or "")[:300],
                        **{k: v for k, v in scored.items() if k != "endpoint_correct"},
                    },
                    doc_sections=[str(s) for s in sources],
                )
            )

            if not execute:
                notes = "dry-run: proposal scored without sandbox call"
                break

            if check_creds is not None:
                try:
                    check_creds()
                except RuntimeError as exc:
                    auth_blocked = True
                    notes = str(exc)
                    failure_docs = [str(s) for s in sources]
                    break

            if execute_request is None:
                notes = "execute_request missing for live trial"
                break

            result = execute_request(path if path.startswith("/") else spec.target_path, body)
            http_status = result.status
            steps[-1].detail["http_status"] = result.status
            if result.error:
                steps[-1].detail["http_error"] = result.error[:300]

            if spec.gate_pass(result, scored):
                gate_pass = True
                steps_to_success = i
                notes = f"Gate pass status={result.status}"
                break

            if result.status == 401:
                auth_blocked = True
                notes = "HTTP 401 Authentication Failed"
                failure_docs = [str(s) for s in sources]
                break

            failure_docs = [str(s) for s in sources]
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Request failed status={result.status} "
                        f"body={result.body[:400]}. Fix from docs only."
                    ),
                }
            )
            guesses += 1
            continue

        if act == "give_up":
            failure_docs = [str(s) for s in (action.get("doc_sources") or last_sources)]
            notes = str(action.get("reason") or "gave up")
            steps.append(
                StepTrace(
                    step=i,
                    action="give_up",
                    detail={"reason": notes[:300]},
                    guess_or_backtrack=True,
                    doc_sections=failure_docs,
                )
            )
            guesses += 1
            break

        guesses += 1
        steps.append(
            StepTrace(step=i, action="unknown", detail={"raw": raw[:300]}, guess_or_backtrack=True)
        )
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {"role": "user", "content": "Unknown action. Use allowed JSON actions only."}
        )

    if not notes and not gate_pass:
        notes = "Step budget exhausted without gate pass"

    return TrialResult(
        arm=arm,
        trial=trial,
        gate_pass=gate_pass,
        steps_to_success=steps_to_success,
        guesses_or_backtracks=guesses,
        failure_doc_sections=failure_docs,
        http_status=http_status,
        endpoint_correct=endpoint_correct,
        auth_blocked=auth_blocked,
        extra=extra,
        steps=steps,
        notes=notes,
    )


def summarize_ab(results: Sequence[TrialResult], *, metric_keys: Sequence[str]) -> Dict[str, Any]:
    def arm_roll(label: str) -> Dict[str, Any]:
        rs = [r for r in results if r.arm == label]
        n = len(rs) or 1
        passes = sum(1 for r in rs if r.gate_pass)
        ep = sum(1 for r in rs if r.endpoint_correct)
        auth = sum(1 for r in rs if r.auth_blocked)
        steps = [r.steps_to_success for r in rs if r.steps_to_success is not None]
        guesses = [r.guesses_or_backtracks for r in rs]
        roll: Dict[str, Any] = {
            "trials": len(rs),
            "gate_pass": f"{passes}/{len(rs)}",
            "endpoint_correct": f"{ep}/{len(rs)}",
            "auth_blocked": f"{auth}/{len(rs)}",
            "mean_steps_to_success": round(sum(steps) / len(steps), 2) if steps else None,
            "mean_guesses_or_backtracks": round(sum(guesses) / len(guesses), 2) if guesses else None,
            "failure_doc_sections": sorted({s for r in rs for s in r.failure_doc_sections}),
            "trial_notes": [r.notes for r in rs],
        }
        for key in metric_keys:
            ok = sum(1 for r in rs if r.extra.get(key))
            roll[key] = f"{ok}/{len(rs)}"
        return roll

    a = arm_roll("A")
    b = arm_roll("B")

    def score(roll: Dict[str, Any]) -> float:
        def frac(s: str) -> float:
            num, den = s.split("/")
            return float(num) / float(den) if float(den) else 0.0

        s = frac(roll["gate_pass"]) * 10 + frac(roll["endpoint_correct"]) * 3
        for key in metric_keys:
            if key in roll:
                s += frac(roll[key]) * 2
        s -= (roll["mean_guesses_or_backtracks"] or 0) * 0.25
        return s

    sa, sb = score(a), score(b)
    if abs(sa - sb) < 0.05:
        winner, margin = "tie", 0.0
    elif sb > sa:
        winner, margin = "B", round(sb - sa, 3)
    else:
        winner, margin = "A", round(sa - sb, 3)

    return {
        "arm_A_control": a,
        "arm_B_treatment": b,
        "winner": winner,
        "margin_score": margin,
        "score_A": round(sa, 3),
        "score_B": round(sb, 3),
    }


def _default_redact(text: str) -> str:
    import os
    import re

    patterns = [
        os.environ.get("STRIPE_TEST_SECRET_KEY", ""),
        os.environ.get("STRIPE_SECRET_KEY", ""),
        os.environ.get("CYBS_SHARED_SECRET", ""),
        os.environ.get("CYBS_MERCHANT_ID", ""),
        os.environ.get("CYBS_KEY_ID", ""),
    ]
    out = text
    for pat in patterns:
        if pat and len(pat) > 4:
            out = out.replace(pat, "[REDACTED]")
    out = re.sub(r"sk_(test|live)_[A-Za-z0-9]+", "[REDACTED]", out)
    return out


def write_ab_report(
    *,
    out_dir: Path,
    spec: TaskSpec,
    summary: Dict[str, Any],
    results: Sequence[TrialResult],
    meta: Dict[str, Any],
    redact: Optional[Callable[[str], str]] = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "generated_at": utc_now(),
        "task_id": spec.task_id,
        "target_path": spec.target_path,
        "summary": summary,
        "trials": [r.to_dict() for r in results],
        **meta,
    }
    redact_fn = redact or _default_redact
    blob = redact_fn(json.dumps(payload, indent=2))
    (out_dir / f"ab-report-{stamp}.json").write_text(blob + "\n", encoding="utf-8")
    (out_dir / "ab-report-latest.json").write_text(blob + "\n", encoding="utf-8")

    lines = [
        f"# {spec.title} A/B report",
        "",
        f"- Task: `{spec.task_id}` → `{spec.target_path}`",
        f"- Winner: **{summary['winner']}** (margin={summary['margin_score']})",
        f"- Score A={summary['score_A']} B={summary['score_B']}",
        "",
    ]
    for key in ("arm_A_control", "arm_B_treatment"):
        roll = summary[key]
        lines.append(f"## {key}")
        for k, v in roll.items():
            if k != "trial_notes":
                lines.append(f"- **{k}:** {v}")
        lines.append("")
    md = "\n".join(lines)
    (out_dir / f"ab-report-{stamp}.md").write_text(md + "\n", encoding="utf-8")
    (out_dir / "ab-report-latest.md").write_text(md + "\n", encoding="utf-8")
