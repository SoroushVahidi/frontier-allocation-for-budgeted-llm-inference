# Baseline Artifact Inventory (2026-05-07)

## Scope
- Paper PDF: not found in repository tree during this pass.
- Sources inspected: `docs/main_baselines.md`, `docs/external_baseline_completeness_summary.csv`, `docs/RESEARCH_NEXT_FRONTIER_HANDOFF_20260507.md`, method registries in `experiments/frontier_matrix_core.py` and `scripts/run_cohere_real_model_cost_normalized_validation.py`, and output artifacts under `outputs/`.

## Answers
- Exact number of main external near-direct baselines in paper grounding: **4** (`L1-MAX`, `L1-EXACT`, `TALE`, `S1`).
- `ZHAI-CPO-A` treatment in this inventory: **constrained-policy adapter / external adjacent** (appears in paper table context, not counted in the 4 near-direct headline baselines).
- Baselines with local per-case outputs found: **1** (`L1-MAX` only).
- Baselines with trace fields saved:
  - `L1-MAX`: per-case outputs exist, but `action_trace` and `final_branch_states` are **not present** in `external_l1_results.jsonl` for the 300-case artifact.
  - Others: no per-case outputs found, so trace availability is not established.
- Is 16-category PAL + 3 external-baseline taxonomy currently possible? **No**.

## Missing Artifacts Blocking Multi-Baseline Taxonomy
- Missing per-case outputs for at least two additional external-paper baselines among `L1-EXACT`, `TALE`, `S1` on the same case set as the 300-case PAL run.
- Missing aligned per-case outputs for `ZHAI-CPO-A` if it is to be included in main-table external taxonomy.
- Missing external trace payloads (`action_trace`, `final_branch_states`) for external baselines in the current 300-case artifact.

## Recommended Next Cleanup Action
- Materialize a single matched-case bundle (same 300 `example_id`s) containing per-case outputs for `external_l1_max`, `external_l1_exact`, `external_tale_prompt_budgeting`, and `external_s1_budget_forcing` (and optionally `external_zhai_cpo_mode_a`), with standardized columns: `example_id`, answer, correctness, and explicit trace fields (even if empty).
- After that, build the multi-baseline taxonomy table from one canonical bundle directory instead of mixed historical outputs.
