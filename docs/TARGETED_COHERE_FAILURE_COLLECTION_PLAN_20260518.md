# Targeted Cohere Failure Collection Plan (2026-05-18)

## 1) Purpose

This plan defines a targeted diagnostic Cohere collection to gather promotion-reviewable failure/disagreement cases for calibrated gate reassessment. The objective is to improve failure separation analysis (recoveries vs regressions) under complete logging, not to produce paper-claim headline evidence.

## 2) Success Criteria

1. Every emitted row contains `promotion_review_record`.
2. Every emitted row contains `promotion_review_validation`.
3. At least `95%` of success rows have `enough_for_promotion_review=yes`.
4. Runtime/failure rows carry explicit reviewable failure states (no silent missing required fields).
5. Prompt/feature leakage checks for `gold` / `exact_match` are zero.
6. Dataset disjointness is proven, or the run is explicitly labeled as a logging smoke-test.

## 3) Required Schema

Each row should include, directly or via stable pointers:

- example/problem id
- prompt hash and prompt text pointer
- method, budget, seed, provider, model
- candidate answer and candidate trace, or explicit empty/unavailable state
- parser/canonicalizer output
- runtime cap/error status
- discovery tree payload/pointer
- node expansion order
- prune/selection reasons, or explicit unavailable/not_applicable marker
- cost/token/latency timeline
- verifier score placeholder at generation time
- offline verifier scoring pointer for later join
- gate features and decision fields for later join
- offline gold/exact fields as metadata only (never runtime prompt/model features)

## 4) Candidate Run Design

- Provider/model: Cohere `command-r-plus-08-2024`
- Dataset: `openai/gsm8k`
- Methods:
  - `direct_reserve_semantic_frontier_v2`
  - `external_l1_max`
  - Extension path (separate plan only): additional strong external baselines
- Budgets: start with `6` (primary) and optionally include `4` if cap headroom permits; budget 6 is prioritized to align with current strongest independent validation artifacts while still keeping failure-collection volume manageable.
- Seeds: minimum `2`, target `4` if cap allows.
- Case targeting: use case ids disjoint from prior Cohere validation sets.
- API cap: start in the `300-600` logical call window for the first diagnostic run.
- Expected rows/cost-risk: enough for failure inventory slices with capped spend; if disagreement yield is low, stop at cap and report insufficient yield rather than increasing cap mid-run.
- Execution: run in `tmux`; Cohere-only, no other providers.

## 5) Failure-Case Targeting

Target the following buckets for adequate review coverage:

- external wrong / frontier correct
- external correct / frontier wrong
- both wrong
- both correct controls

If pre-generation targeting is limited, run a capped balanced sample first, then filter and stratify using offline evaluation outputs.

## 6) Preflight

Require all of:

1. `python3 scripts/check_repo_health.py`
2. Clean tracked state for intended docs/source changes.
3. Cohere readiness check only (no cross-provider setup).
4. Hardened disjointness preflight against prior Cohere validation artifacts.
5. Unique output root reservation.
6. Dry-run call-plan verification.
7. Exact case-id file archived with run metadata.
8. Recorded `--max-total-api-calls` cap.
9. Recorded `tmux` launch command.

## 7) Post-Run Pipeline

After generation:

1. Validate promotion-review fields/sufficiency.
2. Run offline verifier scoring.
3. Join verifier scores back to per-row artifacts.
4. Produce failure inventory and bucket counts.
5. Mine failure patterns.
6. Manually audit switched and failure-heavy cases.
7. Re-evaluate safe gate and near-neighbor only after logging sufficiency passes.

## 8) Stop Conditions

Stop collection if any occur:

- provider readiness failure
- disjointness failure (unless explicitly designated smoke-test)
- promotion-review `yes` rate below target
- leakage detected
- runtime failures not reviewable
- API cap exceeded or unexpected call-volume behavior

## 9) Decision Boundary

- Cohere API collection is not required immediately for current documented status.
- This plan is launch-ready only when existing artifacts are insufficient for promotion-grade diagnosis or when fresh disjoint promotion-grade failure cases are needed.
- Any larger Cohere run requires explicit user approval before launch.
