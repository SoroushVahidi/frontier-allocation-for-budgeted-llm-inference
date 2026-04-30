# Final adaptive-llm-inference transfer audit

## Scope and framing
This is a final transfer audit from `-adaptive-llm-inference` into the current frontier-allocation L1-defeat track. We do **not** copy the old binary route-vs-revise runtime policy direction. We only transfer offline diagnostic ideas for predicting L1 loss modes and coverage/selector risk.

## Old-repo files inspected
- `docs/HYBRID_ROUTING_FRAMEWORK.md`
- `scripts/build_hybrid_routing_dataset.py`
- `scripts/run_hybrid_strategy_recommender.py`
- `scripts/run_improved_tree_router_eval.py`
- `src/routing_hybrid/features/registry.py`
- `src/routing_hybrid/heuristics/registry.py`
- `src/routing_hybrid/models/registry.py`
- `src/routing_hybrid/optimizers/registry.py`
- `src/routing_hybrid/tree_router/selectors.py`
- `src/routing_hybrid/tree_router/tuning.py`
- `src/routing_hybrid/calibration.py`
- `src/routing_hybrid/utility.py`

## Classification

### Already transferred
- Oracle-ceiling style diagnostics.
- Candidate-level consistency/sanity checks and unified confidence/error style.
- Selector/policy catalog discipline.

### Transferable and worth testing now (offline)
- **Hybrid feature registry concept**: explicit feature families and availability reporting.
- **Heuristic registry concept**: small transparent risk rules (low-candidate, low-diversity, concentration).
- **Model registry idea (lightweight version)**: one small logistic diagnostic model with explicit skip conditions.
- **Probability calibration (deferred in implementation but retained in audit)**: apply only when enough rows exist.
- **Utility formulas (offline only)**: support-minus-error, confidence-minus-error, cost-adjusted confidence.
- **Improved tree-router eval principle**: train/test split discipline and label-degeneracy checks.
- **Token-budget/confidence-threshold router ideas (diagnostic proxies)**: token-per-candidate anomaly and low-confidence rules.

### Transferable but later
- Rich model registry with multiple tree ensembles and heavy ablation matrix.
- Full calibration comparison (none/sigmoid/isotonic) with reliability curves.
- Full optimizer stack (greedy upgrade / MCKP / lambda search) on richer candidate-action surfaces.
- Joint tuning pipeline (`tree_router/tuning.py`) when we have stable, large, trace-complete paired artifacts.

### Not transferable / wrong abstraction for current runtime
- Old binary route-vs-revise runtime policy as a primary method family.
- Prompt-level action-choice optimization as production selector replacement right now.
- Any claim that old routing policies directly solve current frontier candidate-pool coverage failures.

## Required topic coverage
- **Hybrid feature registry**: useful as modular offline feature-family bookkeeping; adopted in new predictor script.
- **Heuristic registry**: useful for transparent baselines; adopted as risk heuristics.
- **Model registry / learned router ideas**: partially adopted via one guarded logistic baseline; no runtime adoption.
- **Probability calibration**: acknowledged as useful, but held for later when row counts/class diversity justify it.
- **Utility formulas**: adopted as offline ranking diagnostics only.
- **Optimizers (greedy/MCKP/lambda)**: potentially useful later; currently wrong abstraction without a stable action-set surface.
- **Improved tree-router evaluation**: adopted in spirit (skip on class degeneracy, split discipline, no overclaiming).
- **Token-budget/confidence-threshold routing**: translated to simple diagnostics, not runtime router methods.
- **Why no old binary runtime copy**: current question is frontier candidate coverage + selector failure decomposition vs L1, not two-action route-vs-revise policy selection.

## Small empirical transfer tested now
Implemented `scripts/analyze_l1_loss_predictors_from_traces.py` as an offline diagnostic predictor over `per_example_records.jsonl` artifacts with synthetic fallback.

## Decision
After this audit, stop broad idea-mining from `-adaptive-llm-inference` by default. Continue current repo work with:
1. trace-complete paired artifacts,
2. coverage-vs-selection loss decomposition,
3. minimal targeted coverage repair and selector calibration.
