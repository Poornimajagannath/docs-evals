"""Evals-skills adaptation: binary judge stubs + TPR/TNR, on top of task_ab.

Does not replace ``task_ab.py``, question eval, or the A/B harness.
Auth-from-docs stays a code arm — see ``AUTH_FROM_DOCS_IS_CODE_ARM``.
"""

from docs_evals.judges.loop import (
    AUTH_FROM_DOCS_IS_CODE_ARM,
    JUDGE_MODES,
    PAGE_CAP_CHARS,
    flatten_ab_reports,
    prompt_path,
    scan_harness_artefacts,
    tpr_tnr,
    write_trace_jsonl,
)

__all__ = [
    "AUTH_FROM_DOCS_IS_CODE_ARM",
    "JUDGE_MODES",
    "PAGE_CAP_CHARS",
    "flatten_ab_reports",
    "prompt_path",
    "scan_harness_artefacts",
    "tpr_tnr",
    "write_trace_jsonl",
]
