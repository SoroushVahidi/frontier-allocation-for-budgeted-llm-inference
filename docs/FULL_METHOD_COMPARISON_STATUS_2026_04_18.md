# Full method comparison status (2026-04-18)

## Purpose

This note provides a repository-wide, artifact-backed comparison of the current recommended method/scaffold against:
- current internal baselines,
- earlier repository method lines,
- external/paper-inspired baselines that are actually implemented or import-validated,
- and fixed/adaptive/oracle reference points.

This is an assessment pass, not a new-method proposal.

## What was defined as “our method”

Primary recommended scaffold in this pass:

> **`multistep_k3_current` as the strongest bounded learned line, with bounded completion-aware correction only for disagreement/near-tie slices.**

Why this definition:
- multistep-k3 remains the strongest current bounded learned line in canonical multistep validation artifacts,
- completion-aware policies improve oracle-alignment diagnostics on observability-enabled contested states,
- but there is not yet broad evidence that completion-aware variants are globally superior as standalone learned methods.

Also explicitly included as “our line” representatives:
- best bounded learned branch-scoring (`full_method` variant in strict validation),
- multistep k1/k2/k3 family,
- tie-aware / fallback family (near-tie defer/fallback artifacts),
- completion-aware policy family (completion bonus/gate/tie-resolution).

## Included comparisons

## 1) Current internal baselines and earlier repo lines

Included (artifact-backed):
- `all_pairs_approx` / `baseline_all_pairs` / `baseline_current_matched`,
- pairwise binary baseline,
- penalized marginal proxy baseline,
- one-step/local matched baseline in multistep validation,
- branch-value uncertainty ablations (`value_only`, `value_raw_uncertainty`, `value_learned_risk`, `value_outside_option`),
- tie-aware / abstain / fallback slices (near-tie pointwise expert + abstention families),
- heuristic/controller baselines in light multi-dataset runs (`reasoning_greedy`, `reasoning_beam2`, `self_consistency_3`, `verifier_guided_search`, `program_of_thought`),
- adaptive frontier internal anchors (`adaptive_min_expand_{0,1,2}`, `adaptive_budget_guarded`).

## 2) External / paper-inspired baselines

Directly runnable in-repo adapters used in this pass:
- `external_s1_budget_forcing` (MODE A style adapter),
- `external_tale_prompt_budgeting` (MODE A style adapter),
- `external_l1_exact`, `external_l1_max` (MODE A style adapters).

Adjacent import-validated (not direct control-space-equivalent reproductions):
- BEST-Route,
- when_solve_when_verify,
- Cascade Routing,
- MoB,
- ReST-MCTS,
- OpenR.

Unavailable/blocked for direct in-repo direct-comparison claims in this pass:
- compute-optimal TTS (blocked),
- MODE B official-import-dependent paths where official result packages are absent.

## 3) Fixed/adaptive/oracle references

Included:
- `oracle_frontier_upper_bound` (reference point),
- fixed strategy baselines from imported-frontier eval,
- adaptive reference (`adaptive_budget_guarded`).

## Datasets and slices used

Datasets covered in this comparison bundle:
- `openai/gsm8k`
- `HuggingFaceH4/MATH-500`
- `HuggingFaceH4/aime_2024`
- `olympiadbench`
- strict-validation dataset slices: `gsm8k`, `math500`, `aime`, `olympiad`

Slices/perspectives included:
- overall accepted accuracy,
- coverage / defer / abstention behavior,
- near-tie accepted accuracy,
- adjacent-rank accepted accuracy,
- strict hard-slice accepted accuracy (where available),
- oracle alignment (match-oracle rate / mean oracle regret),
- budgeted cost-quality (accuracy vs avg actions and underspend/exhaustion),
- seed stability (std accuracy by budget/method),
- semantic failure taxonomy and recoverability summaries.

## Key results tables

### A) Canonical multistep line vs matched baseline

| Method | Accepted acc (mean) | Near-tie acc (mean) | Adjacent-rank acc (mean) | Strict-slice acc (mean) | Coverage |
|---|---:|---:|---:|---:|---:|
| baseline_current_matched | 0.5595 | 0.2000 | 0.5460 | 0.1667 | 1.0000 |
| multistep_k1 | 0.5952 | 0.2000 | 0.4794 | 0.1667 | 1.0000 |
| multistep_k2 | 0.6230 | 0.6000 | 0.5270 | 0.5833 | 1.0000 |
| **multistep_k3** | **0.7063** | **0.6000** | **0.6381** | **0.5833** | **1.0000** |

Headline delta (`multistep_k3` vs baseline):
- accepted accuracy: **+0.1468**,
- near-tie accepted accuracy: **+0.4000**,
- adjacent-rank accepted accuracy: **+0.0921**,
- strict hard-slice accepted accuracy: **+0.4167**.

### B) Best bounded learned branch-scoring (strict validation)

| Variant | Accepted pair acc | Coverage | Defer rate | Near-tie acc | Adjacent-rank acc |
|---|---:|---:|---:|---:|---:|
| value_only | 0.8967 | 1.0000 | 0.0000 | 0.6823 | 0.9260 |
| value_raw_uncertainty | 0.9573 | 0.7596 | 0.2404 | 0.6944 | 0.9719 |
| value_learned_risk | 0.9226 | 0.8389 | 0.1611 | 0.5833 | 0.9470 |
| value_outside_option | 0.9110 | 0.7543 | 0.2457 | 0.5820 | 0.9472 |
| **full_method** | **0.9646** | **0.7580** | **0.2420** | 0.6093 | **0.9735** |
| pairwise_binary_baseline | 0.8908 | 1.0000 | 0.0000 | — | — |
| penalized_marginal_proxy_baseline | 0.9032 | 0.8315 | 0.1685 | — | — |

Interpretation: the strongest bounded learned branch scorer wins on accepted accuracy and adjacent-rank slices but does so with materially lower coverage (higher defer).

### C) Completion-aware / oracle-alignment behavior on observability-enabled contested states

| Policy | Match-oracle rate | Mean oracle regret | Objective mismatch states | Resolved mismatch states |
|---|---:|---:|---:|---:|
| best_bounded_learned_branch_score_current | 0.4412 | 0.0231 | 2 | 2 |
| completion_bonus | 1.0000 | 0.0000 | 2 | 0 |
| completion_outside_gate | 0.8824 | 0.0009 | 2 | 0 |
| completion_tie_resolution | 0.9412 | 0.0010 | 2 | 0 |

Interpretation: completion-aware policies can sharply improve oracle-alignment metrics in the bounded contested-state study, but this does not yet establish global broad superiority over multistep-k3 or strict-validation full_method on wider evaluation tables.

### D) Broad multi-dataset budgeted comparison (light simulator run)

Top method by mean accuracy-over-budgets across each of the 4 datasets in this pass:
- `self_consistency_3` was top in all 4 datasets.

Implication:
- current recommended scaffold is **not yet broadly top** in this broad light multi-dataset comparison view.

### E) Fixed/adaptive/oracle reference snapshot

Imported frontier snapshot (gsm8k small split) shows:
- oracle frontier upper bound at accuracy 1.0 (reference),
- adaptive_budget_guarded still with substantial gap-to-oracle,
- several fixed baselines can outperform adaptive_budget_guarded on this small imported snapshot.

## Strongest wins, strongest losses

### Strongest wins
- Multistep-k3 substantially beats matched local baseline on accepted, near-tie, and strict hard slices in canonical multistep validation.
- Best bounded learned strict-validation full_method is strongest on accepted accuracy and adjacent-rank accepted accuracy among its ablations and baselines.
- Completion-aware policies show large oracle-alignment improvements in bounded observability-enabled contested-state diagnostics.

### Strongest losses
- In broad light multi-dataset budgeted comparisons, current “our” frontier anchors are not top overall; self-consistency baseline dominates mean accuracy-over-budgets.
- Best bounded learned strict-validation winner depends on defer/coverage tradeoff; full coverage baselines remain weaker in accepted accuracy but stronger in coverage.
- External baseline coverage is still incomplete for direct apples-to-apples claims: several notable methods are adjacent-import-only or blocked.

## Unavailable coverage and limitations

- Not all famous external baselines are direct in-repo reproductions; many are currently adjacent import-validated only.
- MODE B comparison pathways remain blocked without official external result packages.
- Some comparisons are based on bounded/diagnostic slices, and light multi-dataset runs are simulator-mode; claims must stay conservative.

## Hard conclusion (repository-facing)

After all current artifact-backed evidence in this pass:

> **Our method line is strong and clearly competitive on important hard slices (especially multistep-k3 vs local baseline, and full_method in strict-validation accepted metrics), but it is not yet broadly best across the wider multi-dataset budgeted baseline field.**

More specifically:
- **best regime today**: hard-slice targeted bounded learned branch allocation (multistep-k3 + strict-validation full_method behavior),
- **current weakness**: broad overall dominance versus strong simple internal baselines and external-style adapters in multi-dataset light evaluations,
- **most likely dependency**: gains are currently strongest where target/oracle framing and disagreement-slice handling matter; broad raw predictive supremacy is not yet established.

So the honest status is:

> **strong on targeted hard/ambiguity regimes, not yet broadly top overall; and final standing still depends materially on the target/oracle definition and disagreement-slice policy framing.**
