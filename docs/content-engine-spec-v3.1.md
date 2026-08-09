# Content engine, version 3.1: the work lane spec

This replaces version two. It is written for the work environment, where you already have Relay running, roughly 120 wiki pages generated from real questions, three months of question history, real credentials, internal network access, and a local model on the Spark box.

Version two assumed you were starting from nothing. You are not. The order of work changes because of that.

---

## What you keep

Relay's question-driven loop is the thing this rehearsal lane could never build, because it needs real demand data. It takes the questions your colleagues and support team actually ask, tries to answer them from the documentation, and produces wiki pages where the answers were weak. Keep the question pipeline, keep the wiki, keep the evals that measure whether a question can be answered.

Everything below is a better front end feeding that engine, plus a way to prove the output is good.

## What changes

The corpus is fetched as whole product guides rather than pages. Extraction reads API reference sections as well as click-by-click steps. Prose is rewritten by a local model that cannot alter a fact. Quality becomes a number with a denominator instead of an opinion. And nothing publishes without a person approving it.

---

## Phase 0. Measure what you already have

Do this before generating anything new. It costs no generation and it tells you whether the rebuild is worth doing.

1. Put the existing wiki pages where the engine can read them. Each page needs front matter naming its product and where its content came from.
2. Run the structural checks over them: how many steps state an expected outcome, how many endpoints list their required fields, how many pages carry a source pointer.
3. Run the parity check against the live developer site. Those pages were written months ago and the API has moved, so this tells you what has already drifted.
4. Convert the question log into eval cases. A question with a known good answer is exactly what an eval case is. This is the single highest value conversion in the whole spec, because it replaces invented test cases with real demand.

**Exit:** a quality baseline for the wiki as it stands today, and an eval set built from real questions.

## Phase 1. Build a clean, complete corpus

The corpus is the foundation and every number downstream depends on it being complete.

**Fetch whole guides, not pages.** Read `llms.txt`. It lists more than `docs.md` does, and its entries are subtopic URLs, which is fine because you are mining them for family paths rather than fetching them. For each URL, truncate to the family path and append the family name with `.md`:

```
.../boarding/developer/all/rest/boarding/boarding-intro-overview.md
  →  .../boarding/developer/all/rest/boarding.md
```

Dedupe the derived roots. That deduped set is the corpus and its denominator.

**Do not derive with rules alone; probe and pick.** Rule based derivation was measured at 47.9 percent success on families whose name does not repeat, and it produced 62 failures that looked like site defects but were our bugs. Instead, generate two or three candidate root URLs per family, fetch each, discard 404s and empty 200s, and keep whichever returns the most bytes with the most anchor headings. A guide is recognizable by being large and heavily anchored, so let size decide rather than a regex. This took derivation failures from 62 ours to 0 ours, leaving only genuine site defects. Fetch each root verbatim with a plain HTTP client into `raw/<date>/`, never through a summarizing fetcher. Subtopics arrive inside the root. Use `docs.md` only as a cross-check and report any family it adds. Record PDFs as unfetchable rather than skipping them silently.

**Prove completeness.** Crawl each family's HTML table of contents and confirm every topic appears inside its root. Report topics found, topics covered, and any not covered. Those are real gaps.

**Clean by lifting, not deleting.** The source is HTML converted to markdown and it is noisy.

- Brace anchors like `{#boarding-reg-create-merch-api}` are the site's own deep-link targets. Move them into metadata and build a working link back to the live page. Never leave them in body text, never discard them.
- Strip duplicate anchor lines, trailing empty link titles, and broken image references, recording the asset path in metadata.
- Preserve code blocks byte-exact, tagged with language and nearest anchor so an agent can address them directly.
- Quarantine by kind: revision histories, "about this guide" and audience and conventions boilerplate, support-center blocks, and pure navigation lists. Record every quarantine with its reason.

**Split for addressability.** Split each root by its own heading anchors. Each section keeps its anchor, title, byte range, parent product, and live deep link. The root stays canonical; sections are what everything downstream reads.

**Exit:** every product root fetched and split, TOC coverage reported, quarantine list published, and a test asserting no cleaned document contains a raw brace anchor or empty link title.

## Phase 2. Extract everything, not one shape

The most expensive mistake in the rehearsal was tuning extraction for a single content shape. Fixing it more than doubled what the engine could see, from 438 claims to 1087.

Extract at least three shapes:

**Procedures.** Numbered steps with an actor, an action, an expected outcome, and failure modes. Where the source does not state an outcome, mark the step `outcome_missing` rather than inventing one.

**API reference.** Handle both Swagger 2.0 and OpenAPI 3.0, because the merged vendor spec is 2.0 and assuming 3.0 silently loses request bodies and auth on every page. That means reading `in: body` parameters as well as `requestBody`, merging `allOf` schema fragments, and falling back to `securityDefinitions` when an operation declares no security of its own. Cap very large field tables and link to the full reference rather than flattening megabytes into a page.

**Never assert the absence of authentication.** If auth cannot be resolved from the spec, emit "authentication not stated in source" as a gap marker. A generated page saying no security is required on a credentialed endpoint is the single most harmful thing this system can produce, and it must be impossible by construction with a test that fails on any such claim. Before recording an operation as auth-silent, check that your own slicing or filtering did not drop a document level `securityDefinitions` block.

The repeating source pattern is a heading, an Endpoint section with production and test lines, a Required Fields definition list where terms may be plain text or links to field reference pages, then a REST Example with request and response JSON. Emit these as endpoint facts, not steps. Accept both plain and link-style field terms, and join sibling required-fields pages by anchor. Tag every field with which source it came from. Never infer required from a field appearing in an example.

**Constraints.** Time limits and validity windows, reuse and rate limits, compliance statements, mandatory headers, encryption requirements, identifier format rules, hierarchy limits, status transitions, and prerequisites. This class is small, load-bearing, and the easiest to lose. A short page can be dense; length is never a signal of emptiness.

Anything matching no schema is dropped with a reason, and the drop log carries each file's size and first heading so a human can check ten of them per run.

**Exit:** claims by schema per product, claims per document, drop log, and recall measured against a named baseline.

## Phase 3. Compose, humanize, publish through review

**Compose one procedure, not fragments.** Knowledge for a single task is scattered across a user interface guide, an API guide, and child pages. Merge them into one ordered sequence with the API path beside the manual path. Prefer child pages over aggregate guides, never dedupe by text hash, and report residuals rather than merging them.

**Humanize without touching facts.** A local model rewrites prose against a style guide you own. Deterministic content is untouchable, enforced by hashing every fact block before and after and failing if any hash changes. Grow the style guide every time you edit a generated page.

**Publish only through a pull request a person approves.** No hand-edited pages, ever. Fix the source and regenerate.

## Phase 4. Prove it with two kinds of eval

**Task eval, deterministic, gates the build. Run it as A/B, never single arm.** Arm A gives the agent the original hand written documentation verbatim. Arm B gives it your generated pages. Same task, same model, same prompt, same sandbox, same step budget, three runs each. A single arm only proves an agent can integrate from your pages; the comparison proves whether your pages are better than what already exists, which is the actual claim. Report which arm won and by how much, including ties and including the case where the control wins.

An agent whose only knowledge of the API comes from the documents in its arm attempts a real task in the sandbox. Record a per-step trace naming the doc section read at each step. The gate is binary: did the transaction succeed. The per-step trace is the diagnostic.

**Parity eval, live, evidence only, never gates.** Compare the generated pages against the live documentation site nightly. It reads the open web so it can fail for reasons unrelated to your code, which is why it must never block a build. Push its report to an evidence branch.

**Question evals, from your own history.** Score whether each real question from the log can be answered from the current pages. This is the metric that matters most to your organization, because it is measured in questions people actually asked.

## Phase 5. Close the loop

Nightly, gather the evidence that already exists: eval traces, parity findings, question failures, gap findings, and hand-test logs from the doc agent. Pick the worst few pages, draft improvements with the local model, re-check each draft against the same tests, discard anything that does not score better, and open at most three pull requests for a person to approve.

Two rules make this trustworthy.

The model runs locally, on your own hardware, so no documentation leaves the building. This is not a convenience, it is what makes the system acceptable to your employer.

The loop may rephrase, restructure, and assemble existing claims. It may never author a fact absent from the claim set. Test this explicitly: give it a step with no stated outcome and assert it emits a gap marker rather than an invented success. A model that can fabricate and chooses not to, with a test proving it, is the difference between this and every other tool in the category.

---

## The invariants

1. `raw/` is immutable verbatim evidence. Never served, never edited, never a paraphrase.
2. Everything published reaches readers only through a pull request a human approved.
3. The doc agent and generated pages answer only from generated content, and say gap rather than guessing.
4. Every eval and hand test leaves evidence. Failures are kept, never replaced by later passes.
5. Denominators and eval expectations are computed from the source of truth at runtime, never typed in. Every reported number arrives with its denominator and its source file.
6. One ledger per fact. If two components need the same roster, one owns it and the other derives from it.
7. No configuration flag without an implementation behind it. Every run report names the code path actually taken.

---

## The traps

Each of these actually happened during the rehearsal. They are the most valuable part of this document.

**A test fixture stood in for the real spec, twice.** Both times it produced a confident coverage number that meant nothing. Make the fixture reachable only from engine tests, and make every report print the file path it actually read.

**The agent discovery file was trusted as the list of what exists.** It listed 27 boarding URLs against 236 real pages and omitted the merchant boarding family entirely. Derive roots from it, never take it as the denominator.

**Pages were fetched one at a time when whole guides were available in a single file.** This hid the richest content, the endpoints and required fields and examples, for weeks, and made a well documented product look thin.

**Two components shared definitions but read different inputs.** Census read a directory, ingestion read a registry, and three documents stood in for 182 without any error. Shared definitions are not enough; share the input and test that the counts match.

**Extraction was tuned for one content shape.** Everything shaped differently was invisible. The engine was seeing less than half the corpus and nothing said so.

**A summarizing fetcher nearly put paraphrases into the evidence store.** A machine's summary of a document is not evidence of what the document said. Verbatim or nothing.

**An eval had its expected answers hard-coded**, so it compared the output to a list written by the same hand. It could not fail. Expectations come from the source of truth at runtime.

**A mode flag gated nothing**, because no implementation sat behind it, and the run report described a capability that did not exist.

**A demo storefront was built before the engine behind it.** Hand-pasted content produced a page that taught a deprecated authentication method to customers. Build the trunk before the shop window.

**A measured gap turned out to be our own parser.** Fifty seven endpoints appeared to lack required fields; after fixing a parser that only accepted link style terms, thirty were real. A gap you measure may be your blind spot rather than their defect, so check your own code before reporting a finding about someone else's documentation.

**A filtered spec looked silent about authentication.** All thirty operations in a sliced spec had no security block, which read as a finding about the spec until we asked whether slicing had dropped the document level definitions. Always ask whether your own preprocessing removed the thing you are now reporting as missing.

**Numbers were compared against the wrong pool.** Twenty boarding items were measured against 952 claims spanning every product. Always state the denominator, including when you are the one doing the measuring.

---

## What production actually requires

Almost nothing left is an engineering problem.

Technically you need the engine on a machine with corpus access, a local model so nothing leaves the building, and a review queue. That is it.

The real requirements are people and permission. Someone must decide that generated pages may be published. Someone must own the review queue, which costs a few hours a week at this scale. Someone other than you must be able to run it, which means the setup is documented well enough to survive your absence. And the documentation team needs to receive the gap report as help rather than criticism, which is mostly a question of how it is introduced.

Lead with the gap report, because it asks nobody to trust a machine. It says here are the procedure steps that never tell a developer what should happen, here are the endpoints documented without their required fields, and here is a whole product family your own agent discovery file does not list. Those are facts about the documentation that exists today, provable in a minute, and they make the case without anyone having to argue for it.
