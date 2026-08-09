# docs-evals

Standalone evaluation harness for generated documentation (Content Engine spec v3.1).

Measures whether real questions can be answered from a markdown corpus and runs
live-agent A/B trials comparing control docs vs generated pages.

Spec: [`docs/content-engine-spec-v3.1.md`](docs/content-engine-spec-v3.1.md)

## What’s in here

| Component | Module / script | Purpose |
| --- | --- | --- |
| Question eval | `docs_evals/question_eval.py`, `scripts/run_question_eval.py` | Score eval cases against `content/` (evidence only) |
| Task A/B | `docs_evals/task_ab.py`, `scripts/run_task_ab.py` | Arm A vs B live-agent trials with optional sandbox calls |
| Doc store | `docs_evals/doc_store.py` | Search/get over markdown corpora |
| Stripe Connect task | `docs_evals/tasks/stripe_connect/` | Example task: `POST /v1/accounts` |

Consumer repos (**content-bench**, **bench-new**) point these scripts at their own
`content/`, `gateway-docs/`, and eval-case files.

## Quick start

```bash
python3 -m unittest discover -s tests

# Question eval (uses bundled fixtures by default)
python3 scripts/run_question_eval.py

# Against a consumer repo corpus
python3 scripts/run_question_eval.py \
  --cases /path/to/eval-cases.jsonl \
  --corpus /path/to/content-bench/content

# Task A/B dry-run (no LLM call needed for import/tests; live needs Qwen @ :8000)
python3 scripts/run_task_ab.py \
  --control /path/to/gateway-docs \
  --treatment /path/to/content

# Live Stripe sandbox
STRIPE_TEST_SECRET_KEY=sk_test_... python3 scripts/run_task_ab.py --live
```

## Design rules

- **Evidence-only by default** — question eval never blocks PR until a baseline is set.
- **Never single-arm** — task A/B always runs control and treatment.
- **Provider-agnostic core** — inject `execute_request` for Stripe, CyberSource, etc.
- **No secrets in reports** — traces redact API keys before write.

## Layout

```
docs_evals/          # importable library
scripts/             # CLI entry points
tests/example_corpus/      # minimal corpus + eval cases for CI
reports/             # gitignored output (question eval, A/B reports)
docs/                # spec v3.1 reference
```
