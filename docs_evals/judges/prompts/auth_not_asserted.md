# Judge stub: auth-not-asserted

Named by error analysis of bench-new `evals/ab_*` traces (2026-09-23):
`auth_blocked` is 0/57 across dated A/B, latest-pointer, and null-arm trials.
The harness pre-signs (`signed_post` + `CYBS_*`). That behavioral gap is the
**auth-from-docs code arm**, not this judge.

This judge scores **page text**: does the page invent auth, or stay silent
when `raw/` is silent?

## 1. Task and evaluation criterion

You are an evaluator assessing whether a generated Relay page asserts
authentication in a way the cited `raw/` snippet does not support.

## 2. Pass / Fail definitions

PASS: the page either (a) quotes an auth scheme that `raw/` actually states,
or (b) emits `AUTH_NOT_STATED_IN_SOURCE` and does not invent signing steps.

FAIL: the page claims no authentication is required, or invents HTTP
Signature / HMAC / JWT / header construction that `raw/` does not state.

## 3. Few-shot examples

### Example 1: PASS

<!-- train split, clear Pass — not yet labeled -->

### Example 2: FAIL

<!-- train split, clear Fail — not yet labeled -->

### Example 3: PASS (borderline)

<!-- train split, borderline — not yet labeled -->

## 4. Structured output

```json
{
  "critique": "string — quote the page sentence and the raw/ evidence (or gap marker)",
  "result": "Pass or Fail"
}
```

Auth-from-docs (agent constructs the signature; harness only transports) is
a code arm on `task_ab`. Do not route that check through this prompt.
