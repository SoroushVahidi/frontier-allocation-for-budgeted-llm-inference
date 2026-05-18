# Stage 2 Plan: Baseline-Gated Hybrid Allocator (2026-05-17)

## Status Update (2026-05-18)

- Stage-2 calibrated gate prototype pass is complete and remains output-only.
- Current roles: safe gate `conservative_combo|f=0.85|b=0.40|m=0.5` as conservative candidate; near-neighbor `conservative_combo|f=0.80|b=0.45|m=0.5` as ablation.
- Promotion to tracked source policy is deferred pending log sufficiency and disjoint validation criteria.
- Canonical status and promotion criteria: `docs/STAGE2_CALIBRATED_GATE_STATUS_20260518.md`.

## 1) Stage Transition
Stage 1 (RelationReady verifier) is closed for the current project stage.

Stage 2 goal is to design and validate a budgeted allocation policy that can beat strong external baselines under matched budget/cost, with conservative claim discipline.

## 2) Why Verifier Alone Is Insufficient
- Raw cross-method verifier-guided selection is method-entangled and mostly reproduces `external_l1_max`.
- Within-method verifier reranking is validated on independent data, but this alone is not evidence that we beat all external baselines.
- Slice-aware/tie-aware policy variants are exploratory and not currently validated for promotion.

## 3) Algorithm 1: Baseline-Gated Hybrid Allocator
Baseline-gated hybrid allocator (Algorithm 1):
- Default policy: choose `external_l1_max`.
- Gate override: switch to frontier/direct candidate only when offline features predict positive marginal value.

Candidate utility/gate features (as available):
- `proba_ready` (verifier signal)
- method / budget / seed identity
- score spread / uncertainty proxies
- answer diversity / novelty proxies from answer text
- original frontier/search score (if available or backfilled)
- cost/token/latency fields (if available)

Objective:
- maximize `exact_match` at matched budget/cost,
- compare against strongest external baseline at the same operating point,
- avoid leakage (gold/exact only for offline evaluation).

## 4) Offline Implementation Plan
### Step A: Minimal Gate (Current Scored Fields)
- Develop on:
  - `outputs/verifier_frontier_scoring_full_20260517T032713Z/scored_candidates.jsonl`
- Validate on:
  - `outputs/verifier_scoring_new_multiseed_validation_full_20260517T144315Z/scored_candidates.jsonl`
- Start with no-training/simple policy family (threshold/grid over dev only), freeze before validation.

### Step B: Add Uncertainty/Spread Features
- Add group-level spread/tiny-spread and other uncertainty proxies.
- Keep tuning only on development artifact.

### Step C: Backfill Raw Frontier/Cost Features
- Join scored rows to raw `per_example_records.jsonl` where needed.
- Backfill frontier/candidate metadata (support/branch-score proxies) plus token/cost/latency fields.

### Step D: Expand to Multi-Method External Comparisons
- Prioritize scoring/evaluation on larger multi-method artifacts, especially:
  - `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_results.jsonl`
- Target comparison coverage: `external_l1_max`, `external_s1_budget_forcing`, `external_tale_prompt_budgeting`.

### Step E: Disjoint Validation + Uncertainty
- Use artifact-level disjoint development/validation splits.
- Report paired deltas and cluster-bootstrap CIs over `example_id`.

## 5) Artifact Plan
Development/tuning artifact:
- `outputs/verifier_frontier_scoring_full_20260517T032713Z/scored_candidates.jsonl`

Validation artifact:
- `outputs/verifier_scoring_new_multiseed_validation_full_20260517T144315Z/scored_candidates.jsonl`

Future multi-method artifact:
- `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_results.jsonl`

Disjointness hardening requirement for future generation/scoring:
- Use runner-level hardened preflight (`--disjointness-prior-jsonl`, optional labels/proof output), fail on overlap by default unless intentionally overridden.

## 6) Evaluation Protocol
Primary comparator:
- `external_l1_max`

Secondary comparators (when scored artifact exists):
- `external_s1_budget_forcing`
- `external_tale_prompt_budgeting`

Metrics/reporting:
- `exact_match`
- matched budget and matched cost
- paired deltas
- cluster-bootstrap CIs (primary uncertainty)

Rules:
- no retuning on evaluation artifact,
- tune/freeze on development only,
- report oracle ceilings only as diagnostics (not deployable behavior).

## 7) Success Criteria
First milestone:
- beat `external_l1_max` on independent disjoint artifact with positive CI, or at minimum a robust non-negative trend with conservative caveats.

Stronger milestone:
- beat best of all external baselines on disjoint multi-method artifact with uncertainty support.

## 8) Risks and Failure Modes
- Gate collapses to always selecting `external_l1_max`.
- Overfitting to exploratory 1440-row artifact.
- Verifier method entanglement persists in cross-method settings.
- Missing/incomplete frontier or cost features in scored artifacts.
- Insufficient disjoint validation sample size.
- Artifacts missing one or more target external baselines.

## 9) Immediate Next Source Task (Documented Only)
Implement (next coding step, not in this doc task):
- `scripts/compare_baseline_gated_hybrid_allocator.py`

Initial scope:
- minimal/no-training gate policy (hand-specified or grid-searched on dev artifact only),
- freeze policy,
- evaluate on independent artifact,
- compare to `external_l1_max`, random, verifier top-1,
- output metrics and CIs.

## Conservative Claim Boundary
Current evidence supports feasibility of offline baseline-gated hybrid prototyping against `external_l1_max`.

Current evidence does **not** support claiming superiority over all external baselines. That requires a disjoint verifier-scored multi-method artifact including `external_l1_max`, `external_s1_budget_forcing`, `external_tale_prompt_budgeting`, and frontier/PAL methods.
