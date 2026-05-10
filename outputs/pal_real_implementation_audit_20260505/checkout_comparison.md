# PAL implementation — checkout comparison

| Path | `/home/soroush/research-next-wt` (clean branch) | `/home/soroush/frontier-allocation-for-budgeted-llm-inference` (local main checkout) | `/home/soroush/pal-pilot-clean` | `/home/soroush/diverse-root-clean` |
|---|---|---|---|---|
| `experiments/pal_executor.py` | **missing** | **present** | missing | missing |
| `tests/test_pal_executor.py` | missing | present | unknown | unknown |
| `tests/test_pal_variant.py` | missing | present | unknown | unknown |
| `tests/test_pal_smoke_postprocess.py` | missing | present | unknown | unknown |
| `scripts/materialize_pal_smoke_summary.py` | missing | present | missing | missing |
| `experiments/controllers.py` lines | 8876; `enable_pal_branch`: **0** | 9752; `enable_pal_branch`: **6** | 8876; **0** | 8876; **0** |
| `experiments/frontier_matrix_core.py` `...FRONTIER_TIEBREAK_PAL` spec kwargs | **`strategy_seeded_outer_kwargs_k1_frontier4_tb` only** (no `enable_pal_branch`) | **`strategy_seeded_outer_kwargs_k1_frontier4_pal`** adds `enable_pal_branch=True`, `pal_budget_actions=1`, `pal_selection_policy=...` | same as merged main (PAL duplicate / absent) | same |
| `experiments/output_layer_repair.py` PAL integration helpers | **absent** (no `pal_execution` normalization / overlay skip paths found) | **`_extract_flat_pal_execution`** + **`apply_pal_integration_fix_*`** hooks present (~lines 148+) | absent | absent |

**Read-only note:** the main checkout is **dirty / ahead of merged `origin/main`** for PAL-related files (`git` not queried here); treat it as a **staging area** containing the substantive PAL patch, not as an authoritative merged baseline.
