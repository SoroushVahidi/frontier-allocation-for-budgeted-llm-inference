# Pilot Diagnosis 1: Why Adaptive Underperforms

## Scope and artifacts inspected

- `experiments/pilot_result_1.md`
- Latest run: `outputs/pilot/20260412T224353Z/`
- Implementation files: `experiments/controllers.py`, `experiments/scoring.py`, `experiments/branching.py`, `scripts/run_pilot_gsm8k.py`, `scripts/evaluate_pilot_gsm8k.py`
- Added lightweight helper outputs for this diagnosis:
  - `outputs/pilot/20260412T224353Z/adaptive_failure_diagnostics.json`
  - `outputs/pilot/20260412T224353Z/adaptive_per_example_diagnostics.csv`

## Short summary of the failure

In the latest API-backed real-GSM8K run, adaptive collapses into a deterministic **verify-then-prune loop** and never performs expansion.
That makes it effectively incapable of producing answers, so it loses badly versus all baselines.

- Adaptive accuracy: `0.0000`
- Adaptive avg expansions: `0.0`
- Adaptive avg verifications: `1.0`
- Baselines (greedy / best-of-n / beam): all `0.9167`

## Quantitative diagnostic breakdown

### 1) Action selection behavior (expand / verify / prune)

From `adaptive_failure_diagnostics.json` and `adaptive_diagnostics.jsonl`:

- Total adaptive actions across 12 examples:
  - `expand = 0`
  - `verify = 12`
  - `prune = 12`
- Action fractions:
  - `expand = 0.00`
  - `verify = 0.50`
  - `prune = 0.50`

Interpretation:
- Adaptive is not merely "over-verifying"; it is **not expanding at all**.
- Every example starts at score `0.5`, gets verified once, drops to about `0.25`, then gets pruned.

### 2) Over-verification and budget usage

- Avg verify actions per adaptive example: `1.0`
- Avg expansion actions per adaptive example: `0.0`
- Budget exhaustion rate: `0.0`

Interpretation:
- Underperformance is **not** caused by spending too much budget on verification in this run.
- Instead, adaptive fails *before* budget becomes relevant: it exits after one verify + prune cycle.

### 3) High-score branches not expanded enough

Current thresholds:
- `high_threshold = 0.72`
- `low_threshold = 0.42`

Observed score dynamics:
- First `score_before` at adaptive root is always `0.5`.
- This triggers `verify` (because `0.5` is between low and high).
- `verify` average `score_after` is about `0.25` in this run.
- Next decision is `prune` (`0.25 < low_threshold`), so no expand occurs.

Interpretation:
- Yes: high-score expansion gate is unreachable with current initialization + verifier behavior.
- The controller never gets a chance to generate candidate reasoning trajectories.

### 4) Low-score branch survival / branch evolution

- Low-score branches do **not** survive long; they are pruned immediately after first verify.
- Average surviving branches in adaptive is `0.5` (consistent with quick collapse).
- Trace pattern is almost identical per example: `[verify, prune]`.

Interpretation:
- This is not a "branches survive too long" issue.
- It is a **premature branch collapse** issue.

### 5) Budget exhaustion before enough expansion

- Budget exhaustion for adaptive: `0.0`.

Interpretation:
- Failure is upstream of budgeting; budget policy is not the active bottleneck here.

### 6) Score separation of successful vs unsuccessful branches

- Adaptive has no successful examples in this run, so success/failure score separation cannot be estimated robustly.
- Diagnostic summary shows:
  - `first_score_failure_mean = 0.5`
  - `first_score_success_mean = null`

Interpretation:
- Current diagnostic signal is too degenerate (all failures) to validate score discriminativeness.
- We can still say thresholds are miscalibrated relative to observed score updates.

### 7) Cases where adaptive failed but baselines succeeded

- `11 / 12` examples: adaptive failed while at least one baseline succeeded.
- In many cases (e.g., `gsm8k_1`, `gsm8k_2`, `gsm8k_3`, `gsm8k_4`), all three baselines succeeded while adaptive returned no answer.

Interpretation:
- This strongly suggests adaptive control policy failure rather than dataset impossibility.

## Likely causes (ranked)

### 1) **Threshold-policy mismatch with score dynamics** (Most likely)
Type: **controller logic + scoring calibration**

Evidence:
- Controller only expands when `score >= 0.72`.
- Initial score is `0.5`; first action is always verify.
- Verify step often reduces score to ~`0.25`, forcing immediate prune.
- Net result: zero expansions.

### 2) **Verifier/scoring signal is unstable or badly scaled for this policy**
Type: **scoring / implementation interaction**

Evidence:
- API verifier output is converted to confidence and blended directly into branch score.
- In this run, verify pushes root from neutral score to low score, systematically below prune threshold.
- No corrective mechanism exists (e.g., verify floor, confidence clipping by prior, or minimum expands before prune).

### 3) **Adaptive starts from a single branch with no exploration guarantee**
Type: **controller logic**

Evidence:
- With one initial branch and no mandatory expand-before-prune rule, a single bad verify update kills the entire search.
- Baselines that force expansion (greedy/beam/bon) produce strong performance on same examples.

## Which causes are fallback/mock limitations?

- The **main failure mode here is not due to mock fallback**, because this run used real GSM8K and API-backed generation path.
- However, historical mock-mode pilots (e.g., pilot_result_1) can still mislead calibration decisions because simulator score dynamics differ from API verifier dynamics.

## Most likely immediate fix

Introduce a **minimum expansion floor** for adaptive before verify/prune logic can dominate.

Concrete minimal patch idea:
1. Force at least 1 (or 2) `expand` actions on each new branch before `verify` or `prune` is allowed.
2. Keep thresholds unchanged initially.
3. Re-run same pilot and check whether adaptive now generates answers and whether accuracy rises from zero.

Why this is highest-priority:
- It directly breaks the verify→prune dead loop observed in traces.
- It is low-risk and easy to isolate in ablations.

## Suggested next ablations

1. **Expand-floor ablation**: min expands per branch = 1 vs 2.
2. **Threshold sweep**: lower `high_threshold` (e.g., 0.72 → 0.60 / 0.55).
3. **Verifier damping**: cap verify-induced downward score shift per step.
4. **No-prune-early ablation**: disallow prune in first 2 actions.
5. **Dual-branch bootstrap**: start adaptive with 2 branches instead of 1.

## Confidence and limitations of this diagnosis

- Confidence is high that the immediate failure is policy/threshold collapse (directly visible in traces).
- Confidence is moderate on deeper root cause between verifier quality vs controller calibration, because sample is still small (`n=12`) and the verifier is a lightweight heuristic.
- Additional runs are needed after the immediate fix to separate scoring weakness from control-policy weakness.
