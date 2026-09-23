# Judge stub: faithfulness-to-raw

Named by error analysis of bench-new `evals/ab_*` traces (2026-09-23):
Arm A invented `/payments/v1/v1/payments` from the truncated mega-guide head;
TMS trial `034423Z` invented `clientReferenceInformation` and extra required
fields not in the served example. One mode per judge. Binary only.

Few-shot slots stay empty until a train split of human labels exists.
Do not copy these stubs into a live judge without `validate-evaluator`.

## 1. Task and evaluation criterion

You are an evaluator assessing whether a generated Relay page (or an agent
claim about that page) is faithful to the cited `raw/` snippet.

## 2. Pass / Fail definitions

PASS: every factual claim (endpoint, field name, required/optional, example
value, outcome) is supported by the provided `raw/` snippet. Gap markers
(`AUTH_NOT_STATED_IN_SOURCE`, `outcome_missing`) count as faithful silence.

FAIL: the page or claim invents a field, path, method, required-ness, or
outcome that the snippet does not state. Example-only presence is not
enough to call a field required.

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
  "critique": "string — cite the claim and the raw/ evidence (or its absence)",
  "result": "Pass or Fail"
}
```

Feed the judge: the claim or generated paragraph + the `raw/` snippet it
cites. Not the whole mega-guide.
