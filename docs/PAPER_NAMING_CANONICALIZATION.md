# Paper Naming Canonicalization

This file is the single canonical mapping used by manuscript scripts, plot data, tables, figure labels, and docs.

## Method canonicalization

- `strict_coupled_tie_aware_promoted` -> `Promoted (Strict-Coupled Tie-Aware, bridged)`
- `adaptive_budget_guarded` -> `Adaptive Budget Guarded`
- `reasoning_beam2` -> `Reasoning Beam-2`
- `self_consistency_3` -> `Self-Consistency-3`
- `reasoning_greedy` -> `Reasoning Greedy`
- `verifier_guided_search` -> `Verifier-Guided Search`
- `program_of_thought` -> `Program-of-Thought`
- `oracle_frontier_upper_bound` -> `Oracle Frontier Upper Bound`

Conflict resolution note:
- Docs describe the promoted strict-coupled/tie-aware line as conceptual controller identity.
- Current canonical frontier CSVs represent it via alias bridge row in `20260420T_multidataset_frontier_v1`.
- Paper-facing label includes `bridged` suffix to avoid overclaiming native integration status.

## Dataset canonicalization

Primary frontier dataset order:
1. `openai/gsm8k`
2. `HuggingFaceH4/MATH-500`
3. `Idavidrein/gpqa`

Secondary/appendix context dataset:
- `HuggingFaceH4/aime_2024`

## Metric canonicalization

- `accuracy` -> `Accuracy`
- `avg_actions` -> `Average Actions`
- `gap_to_oracle` / `oracle_gap` -> `Gap to Oracle`
- `budget_exhaustion_rate` -> `Budget Exhaustion Rate`
- `allocation_entropy` -> `Allocation Entropy`
- `max_family_share` -> `Max Family Share`

## Budget labels

Main-paper budget labels:
- `8` -> `Low Budget`
- `10` -> `High Budget`

(Use numeric values in axes/tables; textual labels only for narrative summaries.)

## Output bundle canonicalization

Main canonical bundles:
- `outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z`
- `outputs/full_method_comparison_bundle/20260419T214335Z`

All paper scripts must pull from these bundles unless explicitly documented otherwise.
