# Evals-skills loop (adaptation)

Sits on top of this package. Does **not** replace `task_ab.py`, question eval,
or the A/B harness.

Source process: [evals-skills](https://github.com/ai-evals-course/evals-skills)
(`eval-audit` → `error-discovery` → `write-judge-prompt` → `validate-evaluator`).

## Loop

1. **Trace review.** Flatten existing `ab-report*.json` to JSONL
   (`docs_evals.judges.flatten_ab_reports`). Same files the harness already
   writes. Phoenix is optional if someone already runs it; this package does
   not add a store.
2. **Name modes from the traces.** Only then write a judge. First review
   (2026-09-23, bench-new `evals/ab_*`): `faithfulness-to-raw`,
   `auth-not-asserted`, `required-fields`. content-bench has no A/B traces.
3. **Three binary judges.** Stubs in `docs_evals/judges/prompts/`. One failure
   mode each. Pass/Fail only. Few-shot slots stay empty until a train split
   exists.
4. **TPR/TNR calibration.** `docs_evals.judges.tpr_tnr` on a labeled JSONL of
   `{human, judge}`. Target TPR and TNR > 0.90 on a held-out test split
   (evals-skills `validate-evaluator`). No labels yet — do not report a
   fake agreement score.

## Not judges

| Finding | Why it is not a judge |
|---|---|
| 12k `get_page` cap | Harness artefact (`ArmDocStore.get` `[:12000]` in bench-new). Code/config. |
| Oracle seeding (`seeded: true` on every trial) | Harness artefact. Code/config. |
| Unparseable `propose_request` | Already `parse_action`. |
| `endpoint_correct` / `body_has_*` | Already Layer-1 code on the trial. |
| **Auth-from-docs** | Code arm: agent signs, harness transports. Not `auth-not-asserted`. |

`auth-not-asserted` scores **page text** (invented HMAC vs `AUTH_NOT_STATED_IN_SOURCE`).
`AUTH_FROM_DOCS_IS_CODE_ARM` is `True` in `docs_evals.judges`.

## Commands

```bash
# Flatten consumer-repo reports (bench-new evals/ab_*). JSONL only.
python3 scripts/review_ab_traces.py --reports /path/to/bench-new/evals --out reports/ab_traces.jsonl

# TPR/TNR once a domain expert has labeled a JSONL of {human, judge, mode}.
python3 scripts/review_ab_traces.py --calibrate /path/to/labels.jsonl
```
