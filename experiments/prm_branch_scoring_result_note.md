# PRM branch scoring result note (new-paper track)

## Why this was added

The new-paper frontier allocator has clear oracle headroom, and current branch decisions rely mostly on simple branch score heuristics and verify proxies. This note records a lightweight PRM-style partial-trace scoring integration to improve marginal next-action decisions.

## Audit of current scoring path before changes

- Frontier methods are assembled via `experiments/frontier_matrix_core.py` and evaluated by shared runners such as:
  - `scripts/run_comparative_frontier_audit.py`
  - `scripts/run_new_paper_frontier_matrix.py`
- Branch ranking originally used `experiments/scoring.py` (`SimpleBranchScorer` et al.), which does not model partial-trace process quality.
- `VerifierGuidedSearchController` uses post-generation verifier scores, but no explicit partial-trace scorer / early-rejection gate before verifier calls.
- `ProgramOfThoughtController` is represented as one-shot code generation + sandbox execution; it does not produce multi-step adaptive frontier traces.
- `AdaptiveController` already exposes auditable action traces (`metadata.action_trace`) and anti-collapse guards, making it the lowest-risk insertion point for PRM-style partial scoring and early-rejection flags.

## Implementation summary

- Added `experiments/prm_partial_scorer.py` with:
  - `PartialBranchScorer` interface (`score_partial_branch`, `score_full_candidate`)
  - `PRMScore` metadata container
  - `HeuristicPRMPartialScorer` (explicitly documented as a **proxy**, not trained PRM)
- Integrated into controllers:
  - `AdaptiveController` now supports partial scoring and optional early rejection with explicit trace fields:
    - `partial_score`, `score_source`, `score_stage`, `early_reject_flag`, `scorer_notes`, `fallback_score`
  - `VerifierGuidedSearchController` now supports partial candidate scoring and optional candidate early rejection.
- Integrated into strategy construction (`build_frontier_strategies`) with new variants:
  - `adaptive_prm_partial`
  - `adaptive_prm_partial_early_reject`
  - `verifier_guided_search_prm`
  - `verifier_guided_search_prm_early_reject`
- Integrated into comparative / matrix runners via flags:
  - `scripts/run_comparative_frontier_audit.py --include-prm-variants ...`
  - `scripts/run_new_paper_frontier_matrix.py --include-prm-variants ...`
- Added dedicated experiment runner:
  - `scripts/run_new_paper_prm_branch_scoring.py`
  - outputs under `outputs/new_paper/prm_branch_scoring/<run_id>/`

## Runs executed

### 1) Smoke validation (simulator)

```bash
python scripts/run_new_paper_prm_branch_scoring.py \
  --datasets openai/gsm8k \
  --subset-size 4 \
  --budgets 6 \
  --api-backend simulator
```

Output:
- `outputs/new_paper/prm_branch_scoring/20260414T012242Z/`

### 2) Meaningful simulator comparison

```bash
python scripts/run_new_paper_prm_branch_scoring.py \
  --datasets openai/gsm8k,EleutherAI/hendrycks_math \
  --subset-size 24 \
  --budgets 6,8 \
  --api-backend simulator
```

Output:
- `outputs/new_paper/prm_branch_scoring/20260414T012250Z/`

### 3) Real-model pilot comparison (OpenAI)

```bash
python scripts/run_new_paper_prm_branch_scoring.py \
  --datasets openai/gsm8k,EleutherAI/hendrycks_math \
  --subset-size 4 \
  --budgets 6 \
  --api-backend openai \
  --model gpt-4.1-mini \
  --timeout-seconds 25 \
  --adaptive-min-expand-grid 1
```

Output:
- `outputs/new_paper/prm_branch_scoring/20260414T012300Z/`

### 4) Comparative-audit path integration check

```bash
python scripts/run_comparative_frontier_audit.py \
  --datasets openai/gsm8k \
  --subset-size 8 \
  --budgets 6 \
  --adaptive-min-expand-grid 1 \
  --include-prm-variants \
  --api-backend simulator
```

Output:
- `outputs/comparative_frontier_audit/20260414T013523Z/`

## Required artifacts emitted by PRM runner

Each run emits:
- `method_metrics.csv`
- `branch_score_diagnostics.csv`
- `early_rejection_summary.csv`
- `oracle_gap_summary.csv`
- `run_manifest.json`
- `interpretation.md`

## Honest takeaways

- This implementation is a **mechanism-level PRM proxy**, not a trained PRM.
- Simulator results show mixed behavior: some budget/dataset cells improve oracle gap and/or accuracy, others regress.
- Early rejection can reduce actions in some cells, but can also hurt accuracy or fail to reduce compute depending on threshold regime.
- Real-model run (small) shows promising GSM8K movement for `adaptive_prm_partial` vs baseline adaptive at budget 6, but evidence remains pilot-scale and unstable.
- Direction is promising as a low-cost insertion point, but closing oracle gap materially likely needs a stronger learned process-value signal.
