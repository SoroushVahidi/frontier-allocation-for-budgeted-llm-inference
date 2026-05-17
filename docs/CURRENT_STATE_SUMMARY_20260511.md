# Current State Summary (2026-05-11)

This is the canonical fast read after `README.md` and `START_HERE_CURRENT.md`.
It keeps the evidence hierarchy, the current method target, and the no-API replay status in one place.

## Project Purpose

The repository studies fixed-budget inference over a reasoning frontier: where to spend the next unit of compute, how to keep useful candidate diversity, and how to select a final answer from the explored frontier without gold leakage. The current work separates discovery/coverage from selection/replay, because selector changes cannot recover answers that never enter the candidate pool.

## Current Evidence Hierarchy

1. Main evidence: 300-case paired PAL+retry vs `external_l1_max`
2. Diagnostic caution: 30-case four-way Cohere pilot
3. Latest targeted follow-up: 15-case Direct L1 strong-seed run
4. Latest offline replay: `pal_frontier_structural_target_replay_v1`

## Main External-Baseline Comparison

| Method | Provider / model | Cases | Exact | Gap / interpretation |
|---|---|---:|---:|---|
| PAL+retry / guarded PAL `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` | Cohere `command-r-plus-08-2024` | 300 | `252/300 = 84.00%` | `external_l1_max` was `244/300 = 81.33%`; paired gap `+8` cases / `+2.67 pp`; McNemar `p≈0.322`; bootstrap paired-diff CI `[-2.00 pp, +7.33 pp]` |

Claim wording: PAL+retry is directionally ahead / competitive against `external_l1_max` on the 300-case paired Cohere GSM8K bundle, but the evidence is not statistically decisive and does not support a robust superiority claim.

## Diagnostic Comparisons

| Diagnostic | Cases | Result | Use |
|---|---:|---|---|
| 30-case four-way Cohere pilot | 30 | PAL `17/30`; `external_l1_max` `21/30`; `external_tale_prompt_budgeting` `20/30`; `external_s1_budget_forcing` `20/30` | Diagnostic only, not a universal ranking |
| Direct L1 strong-seed live follow-up | 30 scored total across two 15-case seeds | Baseline `direct_hybrid` `11/30`; treatment `direct_l1_strong_seed_v1` `11/30`; seed `11` improved `5/15 -> 6/15`; seed `23` regressed `6/15 -> 5/15`; gold-in-tree proxy worsened `15/30 -> 11/30`; treatment cost more | Mixed / negative follow-up, not promoted |
| Offline structural-target replay v1 | 158 primary, 100 focus, 55 secondary, 30 guardrail, 15 strong-seed diagnostic, 18 target-audit reference | Deterministic replay only; no API calls; no runtime promotion | Candidate-level structural analysis and selector ablation only |

## Current Method Status

| Method ID | Status |
|---|---|
| `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` | Current best engineered PAL line and main external-baseline comparator |
| `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid` | Baseline diagnostic for strong-seed comparisons |
| `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1` | Opt-in experimental; not promoted |
| `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor` | Diagnostic scaffold |
| `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1` | Opt-in experimental Track B variant; causal benefit unproven |
| `strict_f3` / `strict_gate1_cap_k6` / `strict_f2` | Historical / reference only; not current PAL-line evidence |

## Current Failure-Mechanism Understanding

The broad pattern remains gold-absent / frontier collapse / low diversity.

The more precise working hypothesis is:

- wrong target
- premature intermediate answer
- wrong entity-unit-state
- wrong operation relation
- wrong-supported consensus reinforcing the wrong group

Current counts from the PAL unresolved corpus:

- `157/157` PAL still-failing covered cases gold-absent
- `155/157` frontier collapse / low diversity
- `155/157` direct-seed wrong-or-missing
- `97/157` wrong-supported-consensus
- `43/157` direct-L1-anchor-potential

Important limitation: these labels are still incomplete and heuristic. Do not claim the 97 cases are solved.

## Latest Structural-Target Replay

Implemented work item: `pal_frontier_structural_target_replay_v1`

Updated files:

- `experiments/selector_error_features.py`
- `experiments/gsm8k_structural_validate.py`
- `scripts/evaluate_gsm8k_structural_validator.py`
- `tests/test_gsm8k_structural_validate.py`

New candidate-level fields:

- `target_tuple`
- `entity_unit_ledger_proxy`
- `final_answer_role`
- `last_operation_family`
- `target_alignment_score`
- `intermediate_answer_penalty`
- `duplicate_wrong_signature`
- `structural_selector_score`

Fresh replay output:

- `outputs/gsm8k_structural_validator_eval_20260507/pal_frontier_structural_target_replay_v1_20260511T222238Z/`
- key files: `replay_report.md`, `replay_summary.json`, `candidate_feature_rows.csv`

Replay numbers from `replay_summary.json`:

- Primary slice loaded: `158`
- Primary replay-ready in current bundle: `58`
- Focus slice loaded: `100`
- Focus replay-ready in current bundle: `0`
- Secondary slice loaded: `55`
- Secondary replay-ready in current bundle: `30`
- Guardrail slice loaded: `30`
- Strong-seed diagnostic loaded: `15`
- Target-audit reference loaded: `18`
- Candidate feature rows emitted: `185`

Observed ablation result on the replay-ready primary slice:

- baseline selector: `0.0`
- combined structural selector: `0.13793103448275862`
- improvements vs baseline: `8`
- regressions vs baseline: `0`

This supports the offline structural replay / logging layer and suggests the structural features are informative on the replay-ready subset. It does not justify runtime promotion, and it does not resolve the missing-pool focus slice.

## Proven vs Hypothesis

Proven:

- PAL+retry is competitive on the 300-case paired bundle against `external_l1_max`.
- The 30-case pilot is diagnostic only.
- The 15-case Direct L1 strong-seed run is mixed / negative and not promoted.
- The structural replay runs offline with no API calls.

Hypothesis:

- Better candidate-level structural features may help rank replay-ready cases.
- Wrong-supported-consensus cases may benefit from duplicate-consensus penalties.
- Some of the unresolved tail still needs better candidate generation, not only better selection.

## Safe Claims

- PAL+retry is directionally competitive on the 300-case paired bundle against `external_l1_max`.
- The 30-case four-way pilot is only a diagnostic slice.
- The 15-case Direct L1 strong-seed run is mixed and not promoted.
- The offline structural replay adds deterministic candidate-level logging and selector ablations.
- Current bundle coverage is incomplete for some slices, so missing metadata should be reported explicitly.

## Unsafe Claims

- Robust or universal superiority over `external_l1_max`.
- Treating the 15-case Direct L1 strong-seed result as the main external-baseline evidence.
- Treating structural replay as runtime promotion.
- Treating the focus wrong-supported-consensus bucket as solved.
- Using proxy audits as proof of causal gold-path recovery.

## Immediate Next Steps

1. Continue no-API failure analysis on the 157 PAL-still-failing covered cases.
2. Use the new candidate-level structural fields to inspect where the replay-ready subset improves and where it still fails.
3. Keep target-staged PAL retry / discovery-side work under review if the missing-pool gap remains the bottleneck.
4. Revisit any live run only with a pre-registered capped plan and explicit approval.

## Paid API Guardrails

- No paid/model API calls without explicit approval.
- No bulk deletion or overwrite of `outputs/`.
- Prefer manifest / summary / report files over raw JSONL when interpreting evidence.
- Keep exact method IDs, seed, budget, model, and output directory fixed before any future paid comparison.
- Preserve the distinction between canonical evidence, proxy audits, and historical strict-method results.

## Addendum (2026-05-17): Verifier-Guided Frontier Allocation Transition

This addendum preserves the historical evidence hierarchy above and records the current
frontier-allocation validation status.
Companion docs:
- `docs/FRONTIER_ALLOCATION_VERIFIER_INTEGRATION_STATUS_20260517.md`
- `docs/PAPER_DRAFT_VERIFIER_GUIDED_WITHIN_METHOD_RERANKING_20260517.md`

### Current high-level state

- RelationReady verifier training is complete enough for downstream testing.
- Selected verifier: SetFit `all-mpnet-base-v2` cfg1 (verified OOF ready F1=0.8646, PR-AUC=0.883).
- Independent multi-seed validation for within-method reranking has now completed on a disjoint Cohere artifact.
- New independent artifact QA: raw `738` -> dedup `720`, duplicates removed `18` across `5` duplicate keys (duplicates divergent), raw file preserved.

### Frontier-allocation findings (offline)

- Cross-method verifier-guided selection is method-entangled and mostly reproduces
  `external_l1_max`; this is not sufficient evidence for cross-method routing promotion.
- Within-method reranking on the 1440-row scored artifact is same-sign positive:
  verifier-max beats random by +9.8pp and anti-verifier underperforms.
- Missed-oracle audit indicates most misses are low-margin/tiny-gap decisions rather than
  large confident separations under the configured audit thresholds.
- Tie-aware and slice-aware policies show exploratory gains, but these were selected/evaluated
  on the same artifact and require disjoint validation.
- A small disjoint 15-case artifact shows same-sign lift (+3.3pp) but is underpowered and non-decisive.
- New independent/disjoint Cohere validation (120 groups) confirms same-direction within-method signal:
  verifier-max `0.8667` vs random `0.8208` (+4.58pp), anti-verifier `0.7250`, oracle `0.9583`.
- Confirmatory uncertainty analysis is complete (cluster bootstrap over `example_id`, primary CI):
  verifier-max `86.67%` [79.17%, 93.33%], random `82.08%` [75.56%, 87.78%],
  anti-verifier `72.50%` [64.17%, 80.83%], oracle `95.83%` [90.83%, 100.00%],
  verifier-minus-random `+4.58pp` [+0.28pp, +9.03pp], verifier-minus-anti `+14.17pp`
  [+6.67pp, +21.67pp], oracle-minus-verifier `+9.17pp` [+4.17pp, +15.00pp].
- Aggregate verifier-vs-random gain is statistically stable (cluster CI lower bound > 0),
  while per-method verifier-vs-random gains remain positive but individually uncertain
  (method-level CIs cross 0).
- Frozen slice-aware transfer is now implemented and evaluated (no retuning) on the
  same independent artifact:
  baseline verifier_top1 `0.866667` vs frozen `all_positive_net_slices` `0.866667`
  (`frozen_minus_verifier = +0.000000`, recoveries/regressions `3/3`, net `0`).
  Interpretation: neutral/inconclusive for incremental gain beyond verifier_top1.
  Rule-target overlap was limited (matched `external_l1_max@6`; target also contained
  unmatched `direct_reserve_semantic_frontier_v2@6`; most frozen rules were for budgets 4/8).
- By method on the new artifact:
  `direct_reserve_semantic_frontier_v2` lift vs random `+4.44pp`;
  `external_l1_max` lift vs random `+4.72pp`.
- Independent artifact structural checks passed (60 examples, 2 methods, budget 6, 6 seeds/group),
  trace/final-answer metadata present, and disjointness proof overlap count was zero.

### Claim discipline

- Within-method verifier reranking is now independently validated on a disjoint artifact,
  with smaller effect size than the original exploratory 1440-row analysis.
- Treat slice-aware/tie-aware policy improvements as exploratory for promotion; frozen
  transfer on current independent artifact is neutral/inconclusive.
- Cross-method method-entanglement caveat still holds; validated claim scope is within-method reranking,
  not naive cross-method verifier-guided selection.
- Continue to keep provider prompts gold-free; use `gold` / `exact_match` fields only as
  offline evaluation metadata.

### Correction Note (2026-05-17, budget-4/8 follow-up)

- A later budget-4/8 Cohere artifact was audited and is **not independent** due to
  40-example overlap with the prior 40-example scored source.
- The disjointness miss was a preflight parser schema bug on scored artifacts
  (`metadata.example_id` and question in `feature_text`/metadata).
- A clean non-overlap filtered subset (20 examples, 480 rows) is balanced but small:
  verifier-minus-random is positive point-estimate (`+3.75pp`) with uncertainty crossing 0.
- Frozen slice-aware transfer on that filtered subset is negative overall
  (`frozen_minus_verifier = -2.50pp`).
- Therefore the budget-6 independent artifact remains the strongest current validation anchor.
