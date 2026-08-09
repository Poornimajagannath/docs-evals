"""Unit tests for task A/B framework."""

from __future__ import annotations

import unittest
from pathlib import Path

from docs_evals.task_ab import TrialResult, parse_action, summarize_ab
from docs_evals.tasks.stripe_connect.doc_stores import ArmDocStore, TARGET_PATH
from docs_evals.tasks.stripe_connect.spec import connect_create_account_spec

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "tests" / "example_corpus" / "corpus" / "control"
TREATMENT = ROOT / "tests" / "example_corpus" / "corpus" / "treatment"


class TaskAbFrameworkTests(unittest.TestCase):
    def test_parse_action_recovers_body_wrapper(self) -> None:
        raw = '{"path":"/v1/accounts","body":{"country":"US","controller":{"fees":{"payer":"application"}}}}'
        act = parse_action(raw, target_path=TARGET_PATH)
        self.assertEqual(act["action"], "propose_request")
        self.assertIn("country", act["body"])

    def test_connect_create_account_spec_target(self) -> None:
        spec = connect_create_account_spec()
        self.assertEqual(spec.target_path, "/v1/accounts")

    def test_summarize_picks_winner(self) -> None:
        results = [
            TrialResult(
                arm="A", trial=1, gate_pass=False, steps_to_success=None,
                guesses_or_backtracks=1, failure_doc_sections=[], http_status=400,
                endpoint_correct=True, auth_blocked=False, extra={"body_has_country": True},
            ),
            TrialResult(
                arm="B", trial=1, gate_pass=True, steps_to_success=2,
                guesses_or_backtracks=0, failure_doc_sections=[], http_status=201,
                endpoint_correct=True, auth_blocked=False,
                extra={"body_has_country": True, "body_has_controller": True},
            ),
        ]
        summary = summarize_ab(results, metric_keys=("body_has_country", "body_has_controller"))
        self.assertEqual(summary["winner"], "B")


class ConnectArmStoreTests(unittest.TestCase):
    def test_arm_b_has_post_accounts_page(self) -> None:
        store = ArmDocStore("B", CONTROL, TREATMENT)
        self.assertIn("/v1/accounts", "\n".join(store.pages.values()))

    def test_arm_a_has_connect_reference(self) -> None:
        store = ArmDocStore("A", CONTROL, TREATMENT)
        self.assertTrue(any("/v1/accounts" in t or "controller" in t.lower() for t in store.pages.values()))


if __name__ == "__main__":
    unittest.main()
