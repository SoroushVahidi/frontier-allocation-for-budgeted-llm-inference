# Paper Draft: Verifier-Guided Within-Method Reranking (2026-05-17)

## 1. Title
Verifier-Guided Within-Method Seed Reranking Under Budgeted Frontier Inference.

## 2. Abstract
We study whether a learned RelationReady verifier can improve fixed-budget answer selection in frontier-style LLM inference. Raw verifier-guided cross-method selection was not sufficient because verifier scores were entangled with method identity and mostly reproduced the strongest baseline method. We therefore evaluate a method-controlled protocol: within each `(example_id, budget, method)` group, select the seed with highest verifier score and compare against random seed expectation, anti-verifier selection, and a fixed-pool oracle ceiling. On an independent 720-row Cohere validation artifact (120 groups), verifier top-1 outperforms random by +4.58pp, with a 95% cluster-bootstrap CI of [+0.28pp, +9.03pp]. This supports within-method seed reranking as a conservative, validated claim, while slice-aware refinements remain unvalidated for promotion.

## 3. Problem Framing
Budgeted LLM inference is not only a generation problem; it is also an allocation and selection problem. Frontier allocation must decide which branches/seeds to invest in and which final candidate to return under fixed cost. Simply generating more similar candidates is insufficient when diversity collapses or when a selector cannot distinguish structurally useful traces from superficially plausible ones.

## 4. RelationReady Verifier
The RelationReady verifier predicts whether a candidate trace visibly establishes the target computational relation (not just whether a final numeric answer is plausible). It is used as an intermediate selection signal, not a replacement for end-task correctness evaluation. Feature construction remains gold-free for model input; `gold`/`exact_match` fields are used only for offline reporting.

## 5. Cross-Method Result and Entanglement
Cross-method verifier-guided selection on the exploratory scored artifact was method-entangled: verifier-guided accuracy was 72.08% versus 72.22% for `external_l1_max`, and the verifier-guided chooser selected `external_l1_max` in 705/720 groups. Therefore, raw cross-method `proba_ready` is not sufficient as a global routing policy.

## 6. Within-Method Reranking Protocol
To control for method identity, evaluation groups are defined by `(example_id, budget, method)`. Each group contains seed alternatives for the same method. Policies are:
- verifier_top1: choose seed with max verifier score;
- random_expected: expected seed accuracy under uniform random seed choice;
- anti_verifier: choose seed with minimum verifier score;
- oracle ceiling: whether any seed in the fixed candidate pool is correct (diagnostic, not deployable).

## 7. Main Results
| Artifact | verifier_top1 | random_expected | verifier_minus_random |
|---|---:|---:|---:|
| exploratory_1440 | 75.83% | 66.04% | +9.79pp |
| small_disjoint_15case | 40.00% | 36.67% | +3.33pp |
| independent_720_cohere | 86.67% | 82.08% | +4.58pp |

Interpretation by tier:
- The 1440-row artifact is exploratory (same artifact used for downstream rule exploration).
- The 15-case disjoint check is directionally useful but underpowered.
- The 720-row Cohere artifact is the strongest independent validation.

## 8. Uncertainty (Independent 720-Row Artifact)
Primary uncertainty readout uses cluster bootstrap over `example_id`:
- verifier_minus_random: **+4.58pp** with 95% CI **[+0.28pp, +9.03pp]**.

Method-level independent gains are positive but individually uncertain:
- `direct_reserve_semantic_frontier_v2`: +4.44pp, CI [-2.22pp, +11.11pp]
- `external_l1_max`: +4.72pp, CI [-1.67pp, +10.83pp]

## 9. Slice-Aware / Tie-Aware Policy Status
Exploratory slice-aware/tie-aware policies improved on the original artifact, but frozen transfer to independent validation is neutral so far. Using frozen `all_positive_net_slices` rules:
- baseline verifier_top1: 86.67%
- frozen policy: 86.67%
- recoveries/regressions: 3/3 (net 0)

No promotion decision is justified for slice-aware policy beyond verifier_top1 at this stage.

## 10. Limitations
- Evidence is currently concentrated in one provider/dataset family.
- Method-level CIs for verifier-vs-random cross zero.
- Oracle is a fixed-pool diagnostic upper bound, not deployable policy behavior.
- Cross-method score entanglement remains unresolved.
- Independent generation required deduplication (raw 738 -> dedup 720) before validation reporting.

## 11. Conservative Claim
Current validated claim: verifier-guided **within-method** seed reranking improves over random seed expectation on independent validation (+4.58pp, 95% cluster-bootstrap CI [+0.28pp, +9.03pp]). This is not evidence for general cross-method verifier-guided allocation.

## 12. Next Steps
1. Finalize paper-ready method/results/limitations table text with explicit evidence tiers.
2. If revisiting slice-aware rules, run additional independent validation with budget-4/8 slice coverage to reduce rule-target overlap mismatch.
3. Add independent provider/dataset validation before broader generalization claims.

## Correction Addendum (2026-05-17, Budget-4/8 Artifact)

- A completed budget-4/8 Cohere artifact was later audited and found **overlap-contaminated**
  with the prior 40-example scored source (40 overlapping `example_id`s), so it is not
  independent claim-bearing evidence.
- Root cause was a preflight parser schema miss on scored artifacts
  (`metadata.example_id`, question in `feature_text`/metadata); preflight extraction is
  now hardened in the Cohere validation runner, while the headline claim remains the
  independent budget-6 validation result.
- A filtered non-overlap subset (20 examples, 480 rows) remains diagnostic:
  overall verifier-minus-random is positive (`+3.75pp`) but uncertain (cluster CI crosses 0),
  and DR-v2@8 is negative vs random.
- Frozen slice-aware transfer remains non-promotable overall (negative/neutral),
  including on the filtered budget-4/8 subset.
- Therefore, the independent budget-6 validation remains the primary headline evidence.
4. Revisit verifier model upgrades only if allocation-error analysis shows verifier quality is the bottleneck.
