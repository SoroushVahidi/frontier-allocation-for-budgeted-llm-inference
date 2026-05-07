# Research Next Frontier Handoff (2026-05-07)

## A) Repository State
- Current branch: `research-next-frontier-iteration-2`
- Latest commit hash: `5aa56f3`
- Branch sync: aligned with `origin/research-next-frontier-iteration-2` at handoff time.
- Working tree warning: many local untracked `docs/` and `outputs/` artifacts exist; do not blindly run `git add .`.

## B) Latest Best Algorithm
- Best algorithm so far: **PAL+retry / guarded PAL variant**.
- Short description: program-aided reasoning path with empty-code retry support and guarded frontier/discovery logic in the diverse-root stack.

## C) Latest Best Comparison to External Baseline
- Cohere paired GSM8K run on 300 cases:
  - external L1: `244/300 = 81.33%`
  - PAL+retry: `252/300 = 84.00%`
  - PAL − external: `+8` cases, `+2.67 pp`
  - McNemar `p ≈ 0.322`
  - bootstrap paired-diff 95% CI crosses zero, approximately `[-2.00 pp, +7.33 pp]`
- Interpretation: directionally better, not statistically decisive.

## D) Previous Failure Recovery Audit
- total previous failure/loss cases: `48`
- corrected now: `7`
- still failing: `41`
- missing/no current output: `0`
- external_only: `1` corrected / `20` still failing
- both_wrong: `6` corrected / `21` still failing
- gold_absent_everywhere_detectable: `7` corrected / `27` still failing
- rate_ratio anchors: `7` corrected / `5` still failing
- previously-correct-regressed anchors: `1` corrected / `4` still failing
- Caveat: based on latest available artifacts, not a fresh rerun of latest committed code unless explicitly verified.

## E) What We Learned / Bottleneck
- Dominant remaining bottleneck: upstream candidate-generation/path coverage.
- Many failures are `gold_absent_everywhere_detectable`.
- Selector/pool/overlay perturbations can regress previously correct cases.
- Adding candidates can improve apparent coverage while hurting final exact accuracy.

## F) Failed or Reverted Directions
- PAL execution-pool merge / poolfix:
  - added `0` candidates
  - did not reduce dominant failure mode
- Broad rate/ratio gate:
  - triggered broadly
  - slight coverage movement but exact worsened
- Conservative rate/ratio gate:
  - `override_allowed=0` but exact still worsened
  - lesson: selector-visible pool perturbation can still change outcomes
- Selector-isolated exploration logging:
  - `selector_visible=0` but exact still worsened because logging consumed action/search budget
  - lesson: metadata-only logging must not consume normal search budget

## G) Current No-Go Rules
- Do not blindly inject candidates into selector-visible pool.
- Do not consume search/action budget purely for exploration logging.
- Do not implement another method before inspecting a larger failure corpus.
- Do not claim robust superiority over external baseline yet.

## H) API Policy Going Forward
- Default offline/local first.
- API/reruns allowed when needed for real progress.
- Use Cohere first for paid generation.
- Enforce hard call caps.
- Start with small pilots before larger runs.
- Do not print credentials/tokens.
- Expected tokens: `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN` and `COHERE_API_KEY` / `CO_API_KEY`.
- If non-HF/non-Cohere token/API is required, stop and ask.
- Always report estimated and actual logical calls.

## I) Recommended Next Step
- Main next step: build and inspect a larger failure/loss-case corpus before any new method implementation.
- Include cases where:
  - PAL/current method is wrong
  - external baseline is correct and PAL is wrong
  - `gold_absent_everywhere_detectable` is true
  - both methods are wrong but PAL has useful failure metadata
  - case appeared in failed gate/logging validation anchors
- Per case, store:
  - `example_id` / `case_id`
  - problem statement
  - gold answer
  - PAL answer/correctness
  - external answer/correctness
  - outcome bucket
  - PAL candidate pool
  - external candidate pool if available
  - PAL discovery trace/tree fields
  - external discovery tree if available
  - PAL execution metadata
  - retry metadata
  - overlay/tiebreak metadata
  - feature tags: operation hints, numeric quantity count, question length bucket, candidate diversity, gold presence flags, source-family counts, failure-stage labels
- Proposed script: `scripts/build_failure_case_corpus.py`
- Proposed output: `outputs/failure_case_corpus_20260507/` with:
  - `failure_cases.jsonl`
  - `failure_cases.csv`
  - `feature_summary.json`
  - `pattern_seed_report.md`
  - `case_index.md`

## J) Open Question for Next Chat
- Are external baseline discovery trees/traces available for the target comparison run?
- If yes: use exact file/field paths.
- If no: explicitly record `external_tree_available=false` and do not invent traces.
- For the current 300-case paired artifact, external `action_trace` exists in `outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/external_l1_results.jsonl`; however, external `final_branch_states`/`branch_states` are not present there.
- A fresh capped Cohere rerun should be considered only after corpus findings identify a concrete rerun hypothesis.
