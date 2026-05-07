# Research Next Frontier Handoff (2026-05-07)

## A) Current Branch / PR State
- Branch: `research-next-frontier-iteration-2`
- Latest local commit at handoff creation: `e1c326d` (`analysis: audit previous failure recovery`)
- Sync status before push: branch was ahead of `origin/research-next-frontier-iteration-2` by 1 commit.
- Note: many unrelated local `docs/` and `outputs/` artifacts exist; do not blindly `git add .`.

## B) Main Merged Achievements
- Diverse-root frontier V1 and guarded method integrated.
- Held-out 100-case GSM8K evaluation completed.
- Cohere API safety and call-cap controls implemented and used.
- Cohere parsing/extraction robustness fixes implemented.
- Capped Cohere PAL vs external L1 pilot completed.
- Offline PAL retry 300-case analysis completed.
- Offline failure mining, path-coverage counterfactual, and discovery-deficit atlas completed.
- Offline selector-sensitivity analysis completed.

## C) Best Current Performance Evidence
- 300 paired run evidence:
  - External: `244/300 = 81.33%`
  - PAL+retry: `252/300 = 84.00%`
  - Delta (PAL - external): `+2.67 pp`
  - McNemar `p ≈ 0.322`
  - Bootstrap CI crosses zero
- Interpretation: directionally positive but not statistically decisive.

## D) Previous Failure Recovery Audit
- Total previous failure/loss cases: `48`
- Corrected now: `7`
- Still failing: `41`
- Missing in current outputs: `0`
- By bucket:
  - `external_only`: `1` corrected / `20` failing
  - `both_wrong`: `6` corrected / `21` failing
  - `gold_absent_everywhere_detectable`: `7` corrected / `27` failing
  - `rate_ratio anchors`: `7` corrected / `5` failing
  - `previously-correct-regressed anchors`: `1` corrected / `4` failing
- Caveat: based on latest available local artifacts, not a fresh rerun of latest committed code.

## E) What Failed / Should Not Be Repeated Blindly
- Broad rate/ratio gate: gold presence improved slightly but exact accuracy worsened.
- Conservative rate/ratio gate: even with `override_allowed=0`, exact still worsened.
- Selector-isolated exploration logging: even with `selector_visible=0`, exact worsened because the extra step consumed action/search budget.
- Poolfix experiment: added `0` candidates and did not shrink dominant failure mode.
- Practical conclusion: avoid blind selector-visible candidate injection and avoid budget-consuming perturbations without targeted evidence.

## F) Current Bottleneck
- Upstream candidate generation / path coverage remains the bottleneck.
- A large share of failures remain `gold_absent_everywhere_detectable`.
- Selector/pool/overlay perturbations can regress previously correct incumbents.

## G) Best Next Research Direction
- Build a larger failure/loss-case corpus including:
  - problem statement
  - gold
  - our answer
  - external answer
  - correctness
  - our discovery tree/trace
  - external discovery tree (if available)
  - candidate pools
  - PAL execution
  - retry
  - overlay/tiebreak metadata
  - structured features
- Mine patterns first, then design method changes.
- If external trees are unavailable, record that explicitly in artifacts and reports.

## H) API Policy Going Forward
- Default offline-first analysis.
- API/reruns allowed when needed for real progress.
- Cohere first for API runs.
- Hard call caps required.
- Start with small pilots before larger runs.
- Never print credentials/tokens.
- If non-HF/non-Cohere API/token is required, stop and ask.
- Report estimated and actual logical calls for each run.

## I) Recommended First Task For New Chat
- If missing: implement/build `scripts/build_failure_case_corpus.py`.
- If present: run/inspect it first and decide whether a fresh capped Cohere rerun is needed.
- Do not start new method implementation until the failure corpus is inspected.
