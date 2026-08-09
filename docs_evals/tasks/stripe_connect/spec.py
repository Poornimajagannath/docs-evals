"""Stripe Connect create-account task spec."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from docs_evals.task_ab import HttpResult, TaskSpec

from .doc_stores import TARGET_PATH

SYSTEM = (
    "You are an integration agent. You may ONLY use facts from search_docs / "
    "get_page results. Never invent endpoints or fields. "
    "Each turn respond with JSON only, one of:\n"
    '{"action":"search_docs","query":"..."}\n'
    '{"action":"get_page","id":"..."}\n'
    '{"action":"propose_request","path":"...","body":{...},'
    '"rationale":"...","doc_sources":["..."]}\n'
    '{"action":"give_up","reason":"...","doc_sources":["..."]}\n'
)


def _parse_proposal(action: Dict[str, Any], default_path: str) -> Tuple[str, Dict[str, Any], List[str]]:
    path = str(action.get("path") or default_path)
    body = action.get("body") or {}
    if not isinstance(body, dict):
        body = {}
    sources = [str(s) for s in (action.get("doc_sources") or [])]
    return path, body, sources


def connect_create_account_spec() -> TaskSpec:
    def seed_predicate(text: str) -> bool:
        return "/v1/accounts" in text and "country" in text.lower()

    def score(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        ctrl = body.get("controller") if isinstance(body.get("controller"), dict) else {}
        return {
            "endpoint_correct": path.rstrip("/") == TARGET_PATH,
            "body_has_country": bool(body.get("country")),
            "body_has_controller": bool(ctrl),
        }

    def gate(result: HttpResult, scored: Dict[str, Any]) -> bool:
        return result.status in (200, 201) and scored.get("endpoint_correct", False)

    return TaskSpec(
        task_id="connect-create-account",
        title="Stripe Connect create account",
        target_path=TARGET_PATH,
        task_prompt=(
            "Create a Connect account by calling POST /v1/accounts in Stripe test mode. "
            "Success is HTTP 200/201 with an account id. Use only documentation tools."
        ),
        system_prompt=SYSTEM + f" Path must be {TARGET_PATH}.",
        seed_query="Connect POST /v1/accounts country controller fees",
        seed_page_predicate=seed_predicate,
        parse_proposal=lambda a: _parse_proposal(a, TARGET_PATH),
        score_proposal=score,
        gate_pass=gate,
    )


METRIC_KEYS = ("body_has_country", "body_has_controller")
