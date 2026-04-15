# s1 external baseline integration note (2026-04-15)

## 1) What s1 does

`s1: Simple test-time scaling` (Muennighoff et al., 2025) combines a supervised-finetuned reasoning model with a simple **inference-time budget-forcing loop**. In the official inference recipe, the model is prompted to think, and when it emits a thinking stop boundary, decoding can be forced to continue by appending a short continuation cue (the README example uses `"Wait"`) for a fixed number of ignores (`NUM_IGNORE`) before final answering.

Primary sources:
- arXiv: https://arxiv.org/abs/2501.19393
- ACL Anthology EMNLP 2025: https://aclanthology.org/2025.emnlp-main.1025/
- Official code repo: https://github.com/simplescaling/s1

## 2) Which part we implement in this repository

We integrate the **inference-time budget-forcing stop/continue control** as an external published baseline adapter:

- Method id: `external_s1_budget_forcing`
- Family label: `external_published_baseline`
- Implementation class: `S1BudgetForcingController`
- Comparison runners:
  - `scripts/run_light_anchor_vs_s1_comparison.py` (anchor vs s1 only)
  - `scripts/run_light_external_style_baseline_comparison.py` (broader lightweight comparison now including s1)

This baseline targets our local fixed-budget controller environment so it can run in the same pipeline as the current adaptive anchor.

## 3) Faithful vs adapted

### Faithful elements

- Preserves the core control idea from s1 inference: **ignore early end-of-thinking and force continued reasoning** with a short continuation cue.
- Exposes key control knobs analogous to the official example:
  - `num_ignore_think_end` (like `NUM_IGNORE`)
  - global budget cap (our existing action budget)

### Adapted elements

- We implement s1 as a **controller adapter** over this repository's branch generator interface, not as the original s1 model stack.
- We do **not** import or vendor upstream training/eval code; this repo continues link-only policy for external code provenance.
- We use repository-native datasets/sampling and metrics schema (`accuracy`, action counts, exhaustion), not the full paper eval harness.
- In local simulation/API modes, forcing continuation is represented by reopening a done branch and appending a `Wait (forced-continue)` step marker.

## 4) Remaining comparability caveats

This integration is intentionally conservative and should be read as a **faithful behavior-level adapter**, not full paper reproduction.

Open caveats:

1. No claim of reproducing s1/s1.1 paper headline numbers.
2. No guaranteed matching of model checkpoint, tokenizer boundaries, stop-token handling, or serving engine behavior from upstream vLLM runs.
3. No direct use of s1K/s1K-1.1 training recipe in this path.
4. Our evaluation set and budget units are repository action units, not raw token-level thinking budgets.
5. Therefore: suitable for local method-family comparison under matched conditions; insufficient for definitive paper-level benchmarking claims.

## 5) Recommended comparison metrics against our method

Use matched local regimes and report at least:

- **Task quality:** `accuracy`
- **Compute usage:** `avg_actions`, `avg_expansions`, `budget_exhaustion_rate`
- **Efficiency trade-off:** accuracy at fixed budget and action-normalized deltas vs anchor
- **Stability:** multi-seed mean/std under same subset-size and budget grid

For higher-fidelity future comparison, add token-level accounting + upstream checkpoint/serving parity and run official benchmark suites in parallel.
