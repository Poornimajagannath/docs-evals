"""Tests for the evals-skills adaptation (judge stubs + TPR/TNR)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docs_evals.judges import (
    AUTH_FROM_DOCS_IS_CODE_ARM,
    JUDGE_MODES,
    PAGE_CAP_CHARS,
    flatten_ab_reports,
    prompt_path,
    scan_harness_artefacts,
    tpr_tnr,
    write_trace_jsonl,
)
from docs_evals.judges.loop import load_label_jsonl

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "example_corpus" / "ab_traces"
SCRIPT = ROOT / "scripts" / "review_ab_traces.py"


class JudgeLoopTests(unittest.TestCase):
    def test_named_modes_have_prompt_stubs(self) -> None:
        self.assertEqual(
            JUDGE_MODES,
            ("faithfulness-to-raw", "auth-not-asserted", "required-fields"),
        )
        for mode in JUDGE_MODES:
            text = prompt_path(mode).read_text(encoding="utf-8")
            self.assertIn("Pass / Fail", text)
            self.assertIn('"result": "Pass or Fail"', text)
            self.assertIn("not yet labeled", text)

    def test_unknown_mode_rejected(self) -> None:
        with self.assertRaises(KeyError):
            prompt_path("helpfulness")

    def test_auth_from_docs_is_code_arm(self) -> None:
        self.assertTrue(AUTH_FROM_DOCS_IS_CODE_ARM)
        prompt = prompt_path("auth-not-asserted").read_text(encoding="utf-8")
        self.assertIn("code arm", prompt.lower())
        self.assertNotIn("Likert", prompt)

    def test_flatten_and_artefacts(self) -> None:
        rows = flatten_ab_reports(FIXTURES)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["seeded"] for r in rows))
        self.assertEqual(sum(1 for r in rows if r["unparseable"]), 1)
        artefacts = scan_harness_artefacts(rows)
        self.assertEqual(artefacts["page_cap_chars"], PAGE_CAP_CHARS)
        self.assertEqual(artefacts["seeded_trials"], 2)
        self.assertEqual(artefacts["auth_blocked_trials"], 0)
        self.assertEqual(artefacts["auth_from_docs"], "code_arm_not_judge")

    def test_write_jsonl_roundtrip(self) -> None:
        rows = flatten_ab_reports(FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "traces.jsonl"
            write_trace_jsonl(rows, dest)
            loaded = load_label_jsonl(dest)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]["task_id"], "create-payment")

    def test_tpr_tnr(self) -> None:
        labels = load_label_jsonl(FIXTURES / "sample-labels.jsonl")
        scores = tpr_tnr(labels)
        self.assertEqual(scores["tpr"], 0.5)
        self.assertEqual(scores["tnr"], 0.5)
        self.assertTrue(scores["calibrated"])
        empty = tpr_tnr([])
        self.assertIsNone(empty["tpr"])
        self.assertFalse(empty["calibrated"])

    def test_cli_flatten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.jsonl"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--reports", str(FIXTURES), "--out", str(dest)],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["artefacts"]["trials"], 2)
            self.assertTrue(dest.is_file())


if __name__ == "__main__":
    unittest.main()
