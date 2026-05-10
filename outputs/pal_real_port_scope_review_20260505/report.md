# PAL real-port — scope & safety review (pre-commit / pre–API-run)

Working tree: `/home/soroush/research-next-wt`. **No API calls**, **no live evaluation scripts**, **no git staging/commit** performed during this review.

## 1) Git inspect

Commands recorded from review:

```text
git status --short   → 6 modified tracked files + many untracked (code + outputs)
git diff --stat      → 6 files changed, 1291 insertions(+), 5 deletions(-)
git diff --name-only → branching.py, controllers.py, frontier_matrix_core.py,
                       output_layer_repair.py, strategy_seeded_semantic_diversity_frontier_v1.py,
                       run_cohere_real_model_cost_normalized_validation.py
```

PAL-specific modules/tests exist as **untracked** additions (`experiments/pal_executor.py`, several `tests/test_*.py`, `scripts/materialize_pal_smoke_summary.py`).

## 2) Classification summary

| Area | Verdict |
|------|---------|
| PAL core (executor, trace fields, output-layer promotion, `_pal` matrix kwargs, runner registry row) | **PAL-required** — safe to commit as code |
| `materialize_pal_smoke_summary.py` | **Supporting** — offline JSON/CSV postprocess |
| Tests listed in the task | **PAL / regression** — safe to commit |
| `outputs/**` validator & preflight trees | **Generated / do not commit** (keep untracked) |
| `outputs/pal_real_port_validation_20260505/` & this scope folder | **Artifacts** — usually **untracked** unless repo documents mandate checking proof in |

Details: `changed_files_classification.csv`.

## 3) File-by-file inspection (concise)

- **`experiments/pal_executor.py`** — AST whitelist, `execute_pal_code`, numeric stdout extraction, sanitized errors. **No network.**
- **`experiments/branching.py`** — Copies optional PAL fields into expand trace; **does not branch on gold.**
- **`experiments/output_layer_repair.py`** — `decide_pal_strong_overlay_promotion` documented **gold-free**; uses histogram support / tiebreak diagnostics only. Residual integration helper mirrors same policy for evaluator replay.
- **`experiments/frontier_matrix_core.py`** — Real `_pal` kwargs (`enable_pal_branch=True`, `pal_budget_actions=1`, selection policy). Also registers **decomp_eq** / **opcheck** specs (off unless those method IDs used).
- **`experiments/strategy_seeded_semantic_diversity_frontier_v1.py`** — Method string constants for `_pal`, `_decomp_eq`, `_opcheck`.
- **`scripts/run_cohere_real_model_cost_normalized_validation.py`** — Adds `_pal` METHODS entry; imports `apply_pal_residual_strong_integration_fix`; **does not alter** `external_l1_max` registry row in the diff. Evaluator flag defaults **True** but only applies when method id contains `tiebreak_pal`.
- **`scripts/materialize_pal_smoke_summary.py`** — Reads local artifacts; `_safe_metadata` prefers `result_metadata`.
- **Tests** — Exercise executor, variant wiring, smoke postprocess, registry, parser JSON, output surfacing, guarded K1 frontier4. Subprocess `validate-methods-only` asserts no API requirement for method resolution.

## 4) Accidental leakage check

- **outputs/** trees present and untracked — expected side channels; **do not stage**.
- **`git diff | grep` for credential-like markers** returned **no hits** (quick heuristic scan).
- **No raw traces/tokens committed** in the tracked diff (tracked diff only touches the six files above).

## 5) Behavior boundaries

| Requirement | Evidence |
|-------------|----------|
| `external_l1_max` unchanged | Runner diff adds `_pal`; **external row untouched** in diff; **`test_external_l1_max_still_registered` passed** (spot-check). |
| Non-PAL k1/tiebreak unchanged when not selected | `enable_pal_branch` defaults **False**; **`test_baseline_k1_tiebreak_unchanged_without_pal_fields` passed**. |
| PAL active only on `_pal` method | `_pal` spec sets `enable_pal_branch`; plain tiebreak omits PAL flags in matrix kwargs. |
| PAL sandbox | `pal_executor` restricts AST/builtins and executes locally. |
| No gold-driven PAL overlay | `decide_pal_strong_overlay_promotion` policy is histogram/support based; **`gold_answer` only passed into `generator.expand`** (shared interface). |
| opcheck/decomp_eq “only registry compatibility” | **Partially**: registry + constants added, **and** controller includes **full optional seed implementations** when flags on. **Defaults remain off** for standard k1 tiebreak methods. Tests **require** opcheck/unit-track parity. |

## 6) Tests

Prior full suite: **82 passed** (reported earlier). Suspicion around baseline registry → re-ran **2 spot tests** (**both green**); see `scope_review_summary.json`. Full rerun optional before PR if policy demands.

## 7) Answers to explicit review questions

- **controllers.py scoped to PAL?** **No** — PAL is bundled with optional **decomp_eq / opcheck / unit_track / hybrid** orchestration inside the hot `run()` path. Risk is breadth, mitigated by default flags + passing tests.

- **Include opcheck/decomp_eq with PR or split?** Recommend **same PR**: `test_pal_variant.py` imports those constants and checks metadata surfaces. Splitting cleanly requires test refactors dropping those assertions.

- **Safe to commit & open PR?** **Proceed after human skim of `controllers.py` diff around optional seed sequencing and budget.** Code + tests appear coherent; breadth is the main reviewer load.

- **API run blocked until merge?** **Organization-dependent.** Technically runnable on branch with credentials; safer practice is gated review + CI on PR before costly live runs — **merge is not a hard technical dependency**.

## Recommended commit subject

`feat(pal): wire sandboxed PAL branch for k1/frontier tiebreak_pal (+ optional seeds parity)`

Optional body bullets:

- Add `experiments/pal_executor.py` gated AST executor and trace plumbing.
- Extend `DirectReserveFrontierGateController` with optional PAL/decomp/opcheck/unit/hybrid seeds; enable PAL only via `_pal` matrix kwargs.
- Output-layer gold-free PAL overlay promotion + evaluator residual replay flag for `*_tiebreak_pal`.
- Register METHODS runner row; offline regression tests.
