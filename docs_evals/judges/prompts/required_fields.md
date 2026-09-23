# Judge stub: required-fields

Named by error analysis of bench-new `evals/ab_*` traces (2026-09-23):
Arm A searches for "required fields" after the 12k `get_page` slice;
TMS `034423Z` trial 1 gave up listing `billTo.postalCode`,
`card.expirationMonth`, `previousTransactionID` — fields the example body
does not require. Presence of field *names* can be a code check; **required
vs example-only** needs this judge.

## 1. Task and evaluation criterion

You are an evaluator assessing whether a generated page's required-fields
list matches what `raw/` marks required — not what appears in an example JSON.

## 2. Pass / Fail definitions

PASS: every field the page lists as required is marked required in the cited
`raw/` section (plain term or linked term), and no `raw/`-required field for
that operation is omitted.

FAIL: a listed-required field is only in an example body, is absent from
`raw/`, or a `raw/`-required field is missing from the page.

Never infer required from a field appearing in an example.

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
  "critique": "string — list each disputed field and whether raw/ marks it required",
  "result": "Pass or Fail"
}
```

Feed the judge: the page's required-fields section + the matching `raw/`
required-fields section. Not the REST example block alone.
