# Conformal Thinking external baseline note

## Canonical paper identity

- **Title:** *Conformal Thinking: Risk Control for Reasoning on a Compute Budget*
- **arXiv page:** https://arxiv.org/abs/2602.03814
- **arXiv PDF:** https://arxiv.org/pdf/2602.03814.pdf

## Status in this repository

- **Official-paper record baseline id:** `conformal_thinking`
- **Runnable adapter lane id:** `conformal_thinking_mode_a`
- **Classification:** `adapter_based` (MODE A runnable lane)
- **Control equivalence:** `adjacent`
- **Method boundary:** risk-controlled early-exit stopping comparator, not branch-level frontier-allocation equivalent.

## Official code verification

As of this integration pass, no clearly verified official public code repository was confirmed directly from the arXiv page/PDF primary sources above.

Therefore this repository does **not** claim official reproduction.

## Implemented MODE A adapter

Runner:

- `scripts/run_conformal_thinking_mode_a.py`

Config:

- `configs/conformal_thinking_mode_a_v1.json`

Output family:

- `outputs/conformal_thinking_mode_a/<run_id>/`

Sanity bundle policies:

- `full_budget_baseline`
- `fixed_budget_truncation_baseline`
- `naive_upper_threshold_stopping`
- `conformal_thinking_mode_a_upper`
- `conformal_thinking_mode_a_dual`

## Claim boundary

Use manuscript-safe wording such as:

> We include a paper-inspired matched-substrate adapter implementing risk-controlled early exit with validation-calibrated thresholding and finite-sample correction. This lane is not an official reproduction and is adjacent rather than branch-level control-equivalent.
