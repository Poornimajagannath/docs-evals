"""Question eval tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from docs_evals.doc_store import MarkdownDocStore
from docs_evals.question_eval import load_cases, predict_verdict, run_eval

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "example_corpus" / "eval_cases" / "sample.jsonl"
TREATMENT = ROOT / "tests" / "example_corpus" / "corpus" / "treatment"


class QuestionEvalTests(unittest.TestCase):
    def test_denominator_from_cases_file(self) -> None:
        store = MarkdownDocStore.from_roots(("content", TREATMENT))
        report = run_eval(CASES, store, repo_root=ROOT)
        self.assertEqual(report["denominator"], len(load_cases(CASES)))
        self.assertEqual(report["gate"], "evidence_only")

    def test_answered_case_finds_connect_post_accounts(self) -> None:
        store = MarkdownDocStore.from_roots(("content", TREATMENT))
        row = predict_verdict(
            {
                "case_id": "test-connect-create",
                "user_query": "HTTP method and path to create a Connect account",
                "expected_doc_sections": ["content/connect-postaccounts"],
                "verdict_from_log": "answered_from_docs",
            },
            store,
        )
        self.assertIn("content/connect-postaccounts", row["matched_expected_sections"])

    def test_gap_case_with_no_sections(self) -> None:
        store = MarkdownDocStore.from_roots(("content", TREATMENT))
        row = predict_verdict(
            {
                "case_id": "test-gap",
                "user_query": "quantumflux capacitor wiring diagram 8742999 nonexistent",
                "expected_doc_sections": [],
                "verdict_from_log": "gap",
            },
            store,
        )
        self.assertEqual(row["predicted_verdict"], "gap")


if __name__ == "__main__":
    unittest.main()
