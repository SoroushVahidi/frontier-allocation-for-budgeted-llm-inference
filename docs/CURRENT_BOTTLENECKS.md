# Current bottlenecks (canonical)

## Primary bottleneck

The primary bottleneck is **supervision target quality / proxy-label mismatch** for the **next-step branch-allocation decision**.

## Why this dominates now

The project is no longer blocked mainly by lack of infrastructure. The repo already contains controllers, audits, dataset tooling, oracle-label pilot paths, and real-model pilot pathways.

The weaker point is that current labels or target approximations still do not capture the decision we care about with enough fidelity:

> **Which active branch should receive the next unit of compute?**

A local “continue this branch or not” question can still be useful, but only as a simplified proxy for the richer allocation problem.

## How the bottleneck appears in practice

- noisy branch-comparison targets,
- unstable near-threshold local decisions,
- shallow local comparator definitions,
- limited calibration transfer across budgets / seeds / datasets,
- controller wins that are promising but not yet consistently robust,
- under-spend or misallocated spend even when budget headroom exists.

## Explicit non-bottlenecks for the current phase

The main problem is **not** primarily:
- infrastructure completeness,
- lack of additional controller variants,
- lack of heavier models,
- or inability to run broader sweeps.

These may matter later, but they are not the highest-leverage next fix.

## Canonical near-term response

1. Improve branch-comparison and next-step allocation target design.
2. Make local comparator semantics more opportunity-cost-aware.
3. Continue uncertainty-aware filtering / reweighting.
4. Re-run matched controller comparisons against strong heuristics and BT baseline.
5. Use broader scaling only after target-quality improvements are visible.

## Practical consequence

The next efficient progress is expected to come from **better branch-allocation supervision and cleaner comparator design**, not from immediately scaling compute or model size.

## Evidence update from medium brute-force label run (2026-04-16)

- The supervision-data bottleneck has been **materially reduced but not removed** by a real medium-scale GSM8K run (`outputs/branch_label_bruteforce/gsm8k_medium_20260416/`), with hundreds of candidate/pairwise labels.
- Approximate labels show strong bounded alignment to exact tiny-state labels (winner agreement 0.956 on overlapping feasible states), supporting approximate mode as a practical supervision source.
- Remaining bottleneck shape: many non-negligible near-tie/low-margin comparisons and only moderate downstream pilot learner accuracy, indicating target noise/calibration issues still matter.
- Therefore the bottleneck status is best described as **partially resolved**.

## Evidence update from multi-dataset brute-force scaling run (2026-04-16)

- A larger merged corpus now exists across GSM8K, MATH-500, and AMO-Bench with multi-budget/multi-seed coverage (`docs/BRUTEFORCE_LABEL_SCALING_STATUS.md`).
- This materially reduced data scarcity for branch-allocation supervision (roughly 3.1x row-count expansion over the prior medium GSM8K corpus).
- Learned allocator metrics improved to moderate levels and remain dataset-sensitive, with non-trivial but not robustly high cross-dataset transfer.
- Exact-mode coverage is now present but still sparse, so exact-slice conclusions are still low-confidence.
- Updated bottleneck interpretation: supervision-data quantity is less limiting than before, but supervision-target fidelity/calibration remains a central unresolved issue; bottleneck remains **partially resolved**.

## Evidence update from GBDT branch-allocator integration pass (2026-04-16 bounded)

- Stronger tabular ranking model families (LightGBM LambdaRank, CatBoost YetiRankPairwise) are now integrated as matched baselines in the branch-allocator learning stack.
- Bounded matched runs (documented in `docs/GBDT_BRANCH_ALLOCATOR_STATUS.md`) showed mixed gains and no robust universal improvement over linear anchors.
- This is consistent with the current interpretation that model class alone is not the dominant unresolved issue; supervision-target fidelity/noise remains central.

## Evidence update from target-fidelity branch-comparison pass (2026-04-16 bounded)

- A new pair-construction/target-fidelity layer plus exact-vs-approx disagreement audit is now integrated and auditable (`docs/TARGET_FIDELITY_BRANCH_COMPARISON_STATUS.md`).
- Bounded matched regime runs show large performance shifts from pair-construction regime changes (especially margin/uncertainty filtering and pair-type choice), often larger than model-class-only differences in the same all-pairs setting.
- Updated interpretation remains conservative: bottleneck is still partially resolved and is now more sharply localized to near-tie ambiguity and supervision-target fidelity rather than missing model complexity alone.

## Evidence update from hard-region exact-supervision expansion pass (2026-04-16 bounded)

- A new auditable pipeline now mines difficult pair regions and selectively promotes exact labels only for mined hard comparisons (`docs/HARD_REGION_EXACT_SUPERVISION_STATUS.md`).
- This reduces process ambiguity around where exact supervision is spent and provides explicit per-row replacement provenance.
- In the bounded matched run, direct hard-region exact promotion did not clearly improve near-tie or adjacent-rank slices versus the all-pairs approximate baseline.
- Updated bottleneck interpretation: supervision-fidelity weakness in hard ambiguous regions remains central; the pass improved localization/instrumentation more than end-metric closure.

## Evidence update from hard-case feature-representation pass (2026-04-16 bounded)

- A richer hard-case feature set is now integrated and auditable, including frontier context, rank/gap structure, verification dynamics normalization, and trend/stagnation/budget interactions (`docs/HARD_CASE_FEATURE_REPRESENTATION_STATUS.md`).
- Under fixed supervision regimes, the pairwise logistic baseline improved strongly on near-tie and adjacent-rank slices when using richer features versus the prior v1 representation.
- In the same bounded pass, CatBoost did not show a clear corresponding lift, so gains are model-path dependent.
- Updated bottleneck interpretation: remaining weakness now looks more like a mix of representation quality and irreducible hard-case ambiguity/modeling limits, rather than label provenance alone.

## Evidence update from ternary / selective-abstention formulation pass (2026-04-16 bounded)

- Tie-aware and abstaining branch-comparison formulations were added and compared in matched runs with fixed richer features (`v2`) and explicit fallback policy.
- Bounded evidence showed strong tie-detection capacity for ternary labels, but with severe coverage collapse under the tested tie-band; selective abstention showed a non-trivial coverage/accuracy tradeoff but did not clearly improve forced near-tie outcomes after fallback.
- Updated interpretation: forced binary pressure is part of hard-slice failure, but fallback calibration and ambiguity handling thresholds remain active bottlenecks; this does not yet support a claim of closure.

## Evidence update from ambiguity calibration + fallback pass (2026-04-16 bounded)

- Confidence-calibration variants (temperature/Platt/isotonic) and fallback-policy variants were compared in matched runs with fixed representation (`v2`) and explicit abstention threshold controls.
- In this bounded setting, probability-calibration metrics (Brier/ECE) did not uniformly improve, but calibrated abstention variants improved accepted-accuracy/coverage operating tradeoff versus the prior uncalibrated abstention baseline.
- Near-tie forced-decision behavior remained weak across variants, indicating that fallback design and irreducible ambiguity handling remain key unresolved bottlenecks.

## Evidence update from dedicated near-tie policy pass (2026-04-16 bounded)

- A dedicated near-tie detector + routing layer is now integrated with explicit configuration and provenance under matched feature/supervision settings (`docs/NEAR_TIE_POLICY_STATUS.md`).
- Bounded matched evidence indicates near-tie routing policy choice matters: pointwise fallback in routed near-tie cases improved hardest-slice forced accuracy in this run, while balanced/shared fallback improved near-tie slice but degraded overall forced/top-1.
- Updated interpretation remains conservative: bottleneck is still centered on hard near-tie ambiguity and policy quality in routed hard cases; this pass improves leverage/diagnostics rather than closing the bottleneck.

## Evidence update from near-tie pointwise-expert pass (2026-04-16 bounded)

- A dedicated near-tie pointwise-expert path is now integrated with explicit specialized/reweighted pointwise provenance plus near-tie bucket diagnostics (`docs/NEAR_TIE_POINTWISE_EXPERT_STATUS.md`).
- Bounded evidence indicates pointwise path quality is not automatic: near-tie-specialized pointwise retained the strongest near-tie slice signal in this run, while generic/reweighted pointwise variants under the tested routing gate degraded overall and did not improve near-tie forced behavior.
- Updated bottleneck interpretation: near-tie handling now appears most constrained by expert-model quality and routing-gate quality (with residual irreducible ambiguity), rather than by generic calibration/fallback logic alone.
