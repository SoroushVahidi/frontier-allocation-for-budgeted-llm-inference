# Main-table external baseline fairness audit (20260423T205134Z)

## Scope and question

Audited only the manuscript main-table near-direct external baselines:
- `external_l1_max` / `external_l1_exact`
- `external_tale_prompt_budgeting`
- `external_s1_budget_forcing`

Core question:
> Is there repository-grounded evidence that our main-table advantage could be caused by an incorrect, broken, or materially unfair implementation of these external baselines?

## Inputs inspected

Policy and paper-facing baseline docs:
- `docs/EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md`
- `docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`

Registry / configuration / runner path:
- `configs/external_baselines_registry.json`
- `configs/l1_inference_adapter_v1.json`
- `configs/tale_prompt_budgeting_v1.json`
- `configs/s1_budget_forcing_inference_only_v1.json`
- `scripts/run_l1_baseline.py`
- `scripts/run_tale_baseline.py`
- `scripts/run_s1_budget_forcing_baseline.py`
- `experiments/frontier_matrix_core.py`
- `experiments/controllers.py`
- `scripts/run_matched_surface_multiseed_main_comparison.py`

Existing fairness/result artifacts:
- `outputs/matched_surface_multiseed_main_comparison_20260423T235900Z/`
- `outputs/canonical_external_baseline_closure_20260424T000020Z/`
- `outputs/canonical_external_baseline_fairness_checklist_20260423T021422Z/`
- `outputs/paper_tables/table8_method_contract.csv`

## 1) Registration / availability correctness

### Checked
- Runtime registration in shared strategy builder (`build_frontier_strategies`) for:
  - `external_l1_exact`, `external_l1_max`
  - `external_tale_prompt_budgeting`
  - `external_s1_budget_forcing`
- Matched-surface runner method mapping (`METHOD_RUNTIME_MAP`) from paper-row names (`l1_max`, `l1_exact`, `tale`, `s1`) to runtime names.
- Runnable probing logic in matched-surface runner (`probe` + blocked-list path).
- Contract table naming in `table8_method_contract.csv`.

### Result
- **Pass.** The three near-direct baseline rows are registered in the same shared builder path used by the manuscript matched-surface runner and are explicitly mapped/reachable.
- Naming is internally consistent across:
  - paper row aliases (`l1_max`, `l1_exact`, `tale`, `s1`),
  - runtime method names (`external_*`),
  - baseline keys in readiness/closure artifacts.

## 2) Budget-matching correctness

### Checked
- Baseline configs all use budget grid `4,6,8` and action-to-token conversion metadata (`64.0`) with explicit matching-policy text.
- Main matched-surface runner uses common budgets `4,6,8` and identical dataset contract for all methods.
- Controller-level budget application:
  - L1: action cap `min(max_actions, token_budget/token_per_action)` with exact/max instruction mode.
  - TALE: per-question token budget estimator -> action-equivalent cap `min(max_actions, budget_actions)`.
  - s1: same action budget loop with forced-continue knobs bounded by action budget.

### Result
- **Pass (no material mismatch found).** Budget logic is explicit and internally consistent within the MODE A matched-substrate contract.
- No evidence of a silent bug that would make these baselines unreachable or trivially crippled under the manuscript 4/6/8 contract.

### Minor caveats (non-material)
- L1/TALE token-violation diagnostics are output-token estimates, not full-chain token reconstruction.
- s1 per-seed budget adherence is reported as 1.0 by construction under action-budget enforcement, without token-level stop-parity diagnostics.

These are **diagnostic granularity limitations**, not evidence of broken evaluation or unfair main-table ranking.

## 3) Same-substrate fairness

### Checked
- Matched-surface runner loops over same datasets, seeds, budgets, and sampled examples for all runnable methods in one contract.
- Same answer extraction / final-answer repair stack is used via shared path (`canonicalize_answer` + `choose_repair_answer`).
- External closure artifacts are sourced from this matched-surface raw-case bundle and explicitly label per-case matched contract usage.

### Result
- **Pass.** No repository evidence of a path where `strict_f3` gets a different dataset/seed/budget/extraction contract than these three external rows.

## 4) Guardrail honesty (MODE A vs MODE B)

### Checked
- Baseline runner docstrings and manifests for explicit MODE A adapter labeling and MODE B official-import separation.
- Paper-facing package and readiness docs for bounded claim language.

### Result
- **Pass.** The repo consistently labels main-table rows as MODE A matched-substrate adapter comparisons and does not present them as full official-stack reproductions.

## 5) Failure-risk spots reviewed

### Real correctness/fairness risk found?
- **No material issue found.**
- No evidence of broken runner wiring, misregistered runtime names, or unmatched comparison contract for these three baselines.

### Acceptable bounded-adapter simplifications
- Inference-only adapter design (MODE A) for L1/TALE/s1.
- Official/full-stack differences are explicitly separated into MODE B/import policy and not merged into main-table claims.

### Theoretical caveats only (not material issue evidence)
- Official upstream implementations could differ from adapter behavior.
- This is already policy-labeled and does not, by itself, invalidate the bounded near-direct claim.

## Direct answer to the main question

There is **no repository-grounded evidence** in this audit that the manuscript main-table advantage is caused by an incorrect, broken, or materially unfair implementation of the three near-direct external baselines.

## Final recommendation

`no_material_issue_found`

Current manuscript-facing main-table near-direct comparison remains trustworthy for its stated MODE A matched-substrate scope.

## Follow-up necessity

- No urgent manuscript change required.
- Optional engineering follow-up (non-blocking): improve token-level diagnostic reporting consistency across L1/TALE/s1 baseline summaries.
