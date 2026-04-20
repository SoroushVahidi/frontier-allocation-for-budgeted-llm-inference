# Paper Naming Canonicalization

This note defines one canonical paper-facing naming scheme across scripts, plot-data CSVs, tables, and docs.

## Method mapping

- `adaptive_budget_guarded` -> `Adaptive Budget Guarded`
- `reasoning_beam2` -> `Reasoning Beam-2`
- `self_consistency_3` -> `Self-Consistency-3`
- `reasoning_greedy` -> `Reasoning Greedy`
- `verifier_guided_search` -> `Verifier-Guided Search`
- `program_of_thought` -> `Program-of-Thought`
- `oracle_frontier_upper_bound` -> `Oracle Frontier Upper Bound`
- `strict_coupled_near_tie_specialized_pointwise_v1` -> `Strict-Coupled Near-Tie Specialized Pointwise v1`
- `binary_forced_baseline` -> `Binary Forced Baseline`
- `strict_coupled_tie_aware_posthoc_deferral_v1` -> `Strict-Coupled Tie-Aware Posthoc Deferral v1`

## Dataset naming

- `openai/gsm8k` is used as the canonical dataset label for the current frontier bundle.

## Budget and metric naming

- Budget axis label: `budget`
- Main metric label: `accuracy`
- Oracle-distance metric label: `gap_to_oracle` (or `oracle_gap` in derived plotting files)
- Allocation composition labels: `expansion`, `verification`

## Scope boundary

Canonical naming here is only for manuscript-facing artifacts under:
- `scripts/paper/`
- `outputs/paper_plot_data/`
- `outputs/paper_tables/`

It does not rename historical artifacts in-place.
