# New-paper real-model matched-budget comparative frontier report (2026-04-14)

## Goal

Strengthen the comparative frontier audit with **real-model-backed** matched-budget runs (not simulator), prioritizing practical scale.

## 1) Real-model readiness audit of target methods

Methods requested:

- reasoning_greedy
- self_consistency_3
- reasoning_beam2
- adaptive_min_expand_0
- adaptive_min_expand_1
- adaptive_min_expand_2
- verifier_guided_search
- program_of_thought

Readiness status in this repo (evidence: real-API run manifests + successful metric rows):

- All eight are currently **real-model runnable** through `APIBranchGenerator` in the comparative audit path.
- All eight produced rows in:
  - `outputs/comparative_frontier_audit/20260414T000318Z/method_metrics.csv` (GSM8K)
  - `outputs/comparative_frontier_audit/20260414T001940Z/method_metrics.csv` (MATH mirror)

## 2) Provider/model path selected

Chosen path:

- **Provider:** OpenAI (`--api-backend openai`)
- **Model:** `gpt-4.1-mini`

Why this path:

- Direct first-class support in current `APIBranchGenerator` implementation.
- Key available in environment.
- Stable JSON-return behavior needed by expand/verify/PoT controllers.
- Stronger practical reliability than simulator for this question.

## 3) Runs executed

### GSM8K first (real API)

Primary run used for reporting:

```bash
python scripts/run_comparative_frontier_audit.py \
  --datasets openai/gsm8k \
  --subset-size 12 \
  --budgets 6 \
  --adaptive-min-expand-grid 0,1,2 \
  --api-backend openai \
  --model gpt-4.1-mini \
  --temperature 0.1 \
  --max-output-tokens 220 \
  --timeout-seconds 60
```

Outputs:

- `outputs/comparative_frontier_audit/20260414T000318Z/`

### MATH second (real API)

Attempt 1 (canonical id) failed in this environment:

```bash
python scripts/run_comparative_frontier_audit.py \
  --datasets hendrycks/competition_math \
  --subset-size 3 \
  --budgets 6 \
  --adaptive-min-expand-grid 0,1,2 \
  --api-backend openai \
  --model gpt-4.1-mini
```

- Failure logged under: `outputs/comparative_frontier_audit/20260414T001932Z/`.

Attempt 2 (repo-supported mirror) succeeded:

```bash
python scripts/run_comparative_frontier_audit.py \
  --datasets EleutherAI/hendrycks_math \
  --subset-size 3 \
  --budgets 6 \
  --adaptive-min-expand-grid 0,1,2 \
  --api-backend openai \
  --model gpt-4.1-mini
```

Outputs:

- `outputs/comparative_frontier_audit/20260414T001940Z/`

## 4) Where our method wins / loses (primary = `adaptive_min_expand_1`)

### GSM8K (`20260414T000318Z`)

- **Wins:** none.
- **Losses:** vs `reasoning_greedy`, `self_consistency_3`, `reasoning_beam2`, `program_of_thought`.
- **Tie:** vs `verifier_guided_search`.

Headline metrics (budget=6, subset=12):

- `adaptive_min_expand_1` accuracy: **0.25**, oracle gap: **0.75**.
- `reasoning_greedy` accuracy: **1.00**, oracle gap: **0.00**.
- `program_of_thought` accuracy: **0.9167**, oracle gap: **0.0833**.

### MATH mirror (`20260414T001940Z`)

- **Wins:** vs `program_of_thought` only.
- **Losses:** none.
- **Ties:** vs greedy, self-consistency, beam2, verifier-guided-search.

Headline metrics (budget=6, subset=3):

- `adaptive_min_expand_1` accuracy: **0.3333**, oracle gap: **0.0**.
- Most baselines (except PoT) also: accuracy **0.3333**, oracle gap **0.0**.

## 5) Top 3 drawbacks from real-model evidence

1. **Primary method underperformance on GSM8K real API pilot.**
   - `adaptive_min_expand_1` lags several simpler baselines at matched budget.
2. **Large oracle gap remains on GSM8K for the primary method.**
   - Suggests meaningful headroom for better per-query/per-step frontier allocation.
3. **Dataset robustness / scale limitations remain.**
   - Canonical `hendrycks/competition_math` access failed here; mirror used.
   - MATH sample is very small, so ties/wins are low-confidence.

## 6) Is evidence still pilot-scale or materially stronger?

- This is **materially stronger than simulator-only evidence** because all reported comparisons are real-API runs.
- It is **still pilot-scale** for publication-grade conclusions due to small subset sizes and limited budget sweep.
- Practical next step: increase subset size and include multiple budgets once rate/latency allows.
