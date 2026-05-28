# Trained Selector Inventory (2026-05-24)

## Executive answer
- **Trained selectors/models exist in this repository**, but **the currently promoted frontier/L1/S1/TALE routing policy is rule-based (FIX-2+FIX-4)**.
- **No runtime-promoted learned fixed-pool reliability router among {frontier, L1, S1, TALE} was found.**

## 1) Does a trained selector already exist?
- Yes, trained selector-related artifacts exist (candidate scorers, metacontroller/router, verifier models).
- For the specific promoted fixed-pool reliability routing objective (frontier/L1/S1/TALE), current policy is rule-based, not learned.

## 2) If yes, details of trained selectors found
- **Direct reserve candidate scorer**
  - Code: `scripts/train_direct_reserve_candidate_scorer.py`
  - Artifacts: `outputs/direct_reserve_candidate_scorer_train_*/selected_model.joblib`
  - Labels: `is_gold_candidate`
  - Features: candidate pool metadata (`branch_depth`, `answer_group_support`, entropy/gap, cross-method sharing, etc.)
  - Model types: logistic regression, random forest, hist gradient boosting (+ optional pairwise logistic)
  - Use scope: within-frontier candidate reranking; not promoted cross-source router.
- **Paired selector retrain fallback**
  - Code: `scripts/direct_reserve_learned_override_utils.py` + `scripts/run_direct_reserve_paired_selector_eval.py`
  - Artifacts: `outputs/direct_reserve_paired_selector_eval_*/retrained_model.joblib`
  - Labels/features: candidate-level same family as above
  - Use scope: evaluation/recovery utility; not promoted fixed-pool policy.
- **Frontier lightweight router**
  - Code: `experiments/frontier_router.py`
  - Model: TF-IDF + logistic regression (or constant fallback)
  - Labels: oracle-best strategy labels from evaluated strategy rows
  - Use scope: routes among internal strategy families in new-paper scaffold scripts.
- **Learned state metacontroller (older broad-diversity family)**
  - Code: `scripts/run_learned_state_metacontroller_20260420.py`
  - Model types: logistic regression / decision tree / random forest
  - Labels: best action among `{refine_incumbent, verify_incumbent, widen_to_challenger, commit}` from counterfactual scoring
  - Use scope: old family diagnostic hardening; not current promoted policy.

## 3) If no promoted learned fixed-pool router, what rule-based selectors exist?
- `experiments/support_aware_selector.py` (FIX-1..FIX-5, combined FIX-2+FIX-4, agreement-only 2of3).
- `scripts/merge_repaired_runs_and_replay_selectors.py` (pooled-4, calibration-aware fallbacks, CV spread-regime rules).
- `experiments/cluster_answer_selector.py` (FIX-7 offline rule prototype).

## 4) Is support-aware selector trained or rule-based?
- Rule-based. No training step or model artifact required for inference.

## 5) What are FTA/FIX variants?
- FTA in current docs corresponds to failure-trace-guided gating around FIX policies (especially FIX-2+FIX-4).
- FIX-1..FIX-5 are deterministic rule stacks in `experiments/support_aware_selector.py`.
- FIX-6/7/8 were evaluated and not promoted per canonical results docs.

## 6) Existing tests covering selector logic
- `tests/test_support_aware_selector.py` (FIX stack and precedence).
- `tests/test_frontier_router.py` (lightweight router fit/predict behavior).
- `tests/test_direct_reserve_paired_selector_eval.py` (paired learned selector eval path).
- `tests/test_outcome_verifier_answer_group_selector.py` (outcome-verifier selector behavior/guardrails).

## 7) Gaps for a real learned reliability router over frontier/L1/S1/TALE
- No canonical training dataset committed specifically for per-example source-choice labels under the current fixed-pool contract.
- No promoted persisted learned router artifact for frontier/L1/S1/TALE.
- No dedicated test suite asserting learned source-router behavior under production-evidence constraints.

## 8) Recommendation
- Reuse existing extraction/replay infrastructure, but implement a **new explicit learned fixed-pool reliability-router module** if that is the target.
- Keep `support_aware_selector` as rule-based baseline and comparator for any learned router candidate.

## 9) Checks/tests run
- `python3 scripts/check_repo_health.py` -> OK
- `pytest -q tests/test_support_aware_selector.py tests/test_live_validation_hardening_20260523.py` -> 81 passed
- `pytest -q tests/test_frontier_router.py tests/test_direct_reserve_paired_selector_eval.py tests/test_outcome_verifier_answer_group_selector.py` -> 33 passed

## 10) Safety confirmations
- No API calls were launched in this inventory task.
- Active external jobs were observed only and left untouched.

## Inventory outputs
- `outputs/trained_selector_inventory_20260524/trained_selector_inventory.json`
- `outputs/trained_selector_inventory_20260524/trained_selector_code_search_hits.txt`
- `outputs/trained_selector_inventory_20260524/trained_selector_file_search_hits.txt`
- `outputs/trained_selector_inventory_20260524/trained_selector_model_artifacts.txt`
- `outputs/trained_selector_inventory_20260524/trained_selector_docs_search_hits.txt`
- `outputs/trained_selector_inventory_20260524/selector_classification_table.csv`
- `outputs/trained_selector_inventory_20260524/existing_selector_details.md`
