# Selected Discovery Hypothesis Checklist (Offline-Only)

## Hypothesis name
Temporal-Rate Coverage Expansion (TRCE) for Gold-Absent External-Only Failures

## Target failure pattern
- Primary slice: `outcome_bucket=external_only` AND `gold_absent_everywhere_detectable`.
- Within that slice, the strongest repeated operations are temporal/rate style problems.
- Empirical signal from corpus:
  - total corpus: 48
  - `gold_absent_everywhere_detectable`: 34
  - `external_only`: 21
  - intersection (`external_only` + gold-absent): 12
  - narrowed temporal/rate-focused intersection: 8 cases

## Estimated affected cases in the 48-case corpus
- High-confidence directly targeted: **8 / 48**
- Broader related discovery-deficit neighborhood: up to **12 / 48** (`external_only` + gold-absent)

## Representative case IDs
- `openai_gsm8k_773`
- `openai_gsm8k_814`
- `openai_gsm8k_851`
- `openai_gsm8k_995`
- `openai_gsm8k_1003`
- `openai_gsm8k_1006`
- `openai_gsm8k_1027`
- `openai_gsm8k_1029`

## Why existing PAL+retry misses these cases
- The dominant miss mode is discovery absence (`gold_absent_everywhere_detectable`), not just final selection.
- In this narrowed slice, PAL execution often succeeds (many rows with parse/safety/exec success), which suggests the failure is upstream candidate/path coverage rather than pure sandbox/code absence.
- Retry is low-frequency and cannot materially change a coverage-deficit regime when good candidate paths are missing.

## Why external_l1_max may solve them (based only on available fields)
- External is correct while PAL is wrong in this slice (`external_only` by definition).
- Available external fields (`final_nodes`, `action_trace`, final answer) indicate external reaches a successful final trajectory on these cases.
- We do not have complete external branch-state internals; infer only that externally exposed trajectories end on the correct answer more often here.

## Why previous failed approaches did not solve them
- Broad rate/ratio gate and conservative rate/ratio gate changed candidate pools and regressed exact on anchors.
- Selector-isolated exploration logging still perturbed outcomes due to budget/search interactions.
- Poolfix-style perturbations are selector-sensitive and can regress stable cases.
- None of these approaches provided a clean, non-selector-perturbing discovery improvement with strict regression control.

## Proposed future intervention idea (conceptual only)
- Add a **discovery-only auxiliary expansion budget lane** for temporal/rate-structured cases that:
  - is bounded and explicitly separate from normal selector-visible search budget,
  - writes candidate/trace diagnostics to non-selector-visible storage first,
  - only promotes into selector-visible candidates after offline acceptance checks pass.
- This is a coverage intervention, not a selector override intervention.

## Files that would eventually be touched (if implemented later)
- `experiments/controllers.py`
- `experiments/frontier_matrix_core.py`
- `experiments/strategy_seeded_semantic_diversity_frontier_v1.py`
- `experiments/branching.py` (metadata schema only, if needed)
- `tests/test_guarded_k1_frontier4_method.py`
- `tests/test_selector_isolated_exploration_log.py`
- `tests/test_api_branch_generator_json_parsing.py`
- `scripts/run_cohere_real_model_cost_normalized_validation.py` (evaluation wiring only)

## Must remain unchanged to avoid regressions
- No selector-visible candidate injection by default.
- No selector policy/tiebreak behavior changes in the first pass.
- No extra action/search budget consumption in normal production path for logging-only logic.
- No broad gate activation that can perturb previously correct anchors.

---

## Strict offline validation checklist

### 1) Exact rows/case IDs to use
- Core target set (8):
  - `openai_gsm8k_773`, `814`, `851`, `995`, `1003`, `1006`, `1027`, `1029`
- Guardrail anchor sets (must be included):
  - `outputs/offline_rate_ratio_gate_anchor_validation_20260507/`
  - `outputs/offline_rate_ratio_conservative_gate_anchor_validation_20260507/`
  - `outputs/offline_selector_isolated_exploration_log_anchor_validation_20260507/`
- Full corpus reference:
  - `outputs/failure_case_corpus_20260507/failure_cases.jsonl`

### 2) Exact metrics to compute before any implementation
- Coverage diagnostics:
  - gold-absent rate on target set
  - candidate diversity distribution
  - source-family coverage distribution
- Stability diagnostics:
  - prediction-change count on guardrail anchors
  - previously-correct-regressed count on guardrail anchors
- Execution diagnostics:
  - parse/safety/exec-ok rates in target set
  - retry-ran rate and retry-selected contribution

### 3) Preconditions before writing implementation code
- Offline analysis must show target slice is predominantly discovery-deficit, not selector-deficit.
- Guardrail baseline metrics must be frozen and documented.
- A non-selector-visible data path for discovery diagnostics must be specified first.

### 4) Offline checks possible without API
- Static config/path check that proposed lane is disabled by default.
- Replay-style structural checks on stored artifacts to confirm:
  - no selector-visible pool deltas when feature disabled,
  - no action-budget deltas in incumbent path when feature disabled.
- Diff-based metadata schema check for backward compatibility.

### 5) Regression traps to test
- Any change in selected answer on previously correct anchor rows.
- Any increase in prediction-changed count on selector-isolated anchor suite.
- Any increase in runtime action usage for baseline method when feature flag is off.
- Any accidental coupling between logging diagnostics and selector candidate pool.

### 6) Stop conditions (hard fail)
- `prediction_changed_count > 0` on protected anchor subset with feature disabled.
- `regressions_on_prev_correct > 0` on guardrail anchors.
- Any selector-visible candidate delta under "diagnostic-only" mode.
- Any unexplained action-budget increase in baseline replay path.

### 7) Required tests before any live Cohere pilot
- Unit tests:
  - feature flag default-off behavior
  - no selector-pool mutation in diagnostic-only mode
  - no action-budget consumption for diagnostic logging path
- Replay/integration tests:
  - guardrail anchor suite exact unchanged under default settings
  - metadata sidecar schema consistency

### 8) Minimum evidence required before capped API run
- Offline guardrail suite passes with zero regressions.
- Target-slice offline diagnostics show credible path to reducing gold-absent prevalence.
- Clear pilot protocol:
  - fixed case list,
  - fixed call cap,
  - predefined success criterion:
    - no regressions on guardrail anchors,
    - measurable reduction in gold-absent count in target slice.

---

## Immediate recommendation
- Do not run API now.
- First perform the offline precondition + regression-trap checks above and produce a short pass/fail ledger.
