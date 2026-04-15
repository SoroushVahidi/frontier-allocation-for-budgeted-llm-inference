# s1 baseline integration (reviewer-defensible split)

This document defines the repository's **fair and conservative** s1 integration for the NeurIPS-oriented fixed-budget allocation project.

## Why this split is required

The s1 paper combines two ingredients:
1. **Post-training / supervised finetuning** on s1K-family data.
2. **Inference-time budget forcing** (e.g., forcing continued thinking by ignoring an early think-end boundary and appending a continuation cue like `Wait`).

For our controller paper, these must be separated to avoid unfair comparisons.

---

## Mode definitions

## MODE A (primary): inference-only s1 budget forcing

- Name: **`inference_only`**.
- Goal: apples-to-apples comparison with our unchanged-base-model controller.
- What it does in this repo:
  - Runs our local method family and the in-repo s1-style adapter (`external_s1_budget_forcing`) under matched dataset splits, seeds, and budget grid.
  - Uses the same base model family settings used by our method path.
  - Does **not** require or claim s1K post-training reproduction.
- Runner:
  - `python scripts/run_s1_budget_forcing_baseline.py --config configs/s1_budget_forcing_inference_only_v1.json`
- Status: **implemented and runnable in this repository**.

## MODE B (secondary): full/official s1 path (includes post-training)

- Name: **`full_or_official`**.
- Goal: side-by-side reporting with official/full s1 outputs where feasible.
- What it does in this repo:
  - Keeps labels and reporting separate from MODE A.
  - Accepts imported official/full s1 metrics via `official.results_path` in config.
  - Records explicit `blocked` status if official assets/results are unavailable.
- Runner:
  - `python scripts/run_s1_budget_forcing_baseline.py --config configs/s1_full_or_official_adapter_v1.json`
- Status: **partial adapter/reporting path** (no automatic in-repo reproduction of full s1 post-training stack).

---

## Implemented artifacts

- Configs:
  - `configs/s1_budget_forcing_inference_only_v1.json`
  - `configs/s1_full_or_official_adapter_v1.json`
- Scripts:
  - `scripts/run_s1_budget_forcing_baseline.py`
  - `scripts/run_s1_baseline_comparison_bundle.py`
- Outputs (per run):
  - `outputs/s1_baseline/<run_id>/manifest.json`
  - `outputs/s1_baseline/<run_id>/summary.csv`
  - `outputs/s1_baseline/<run_id>/summary_per_seed.csv`
  - `outputs/s1_baseline/<run_id>/per_example.jsonl`
  - `outputs/s1_baseline/<run_id>/note.md`
  - `outputs/s1_baseline/<run_id>/fairness_report.md`
  - `outputs/s1_baseline/<run_id>/comparison_to_ours.csv`
  - `outputs/s1_baseline/<run_id>/frontier_summary.csv`

---

## Fairness and budget matching policy

Primary comparison (manuscript-safe):
- `adaptive_min_expand_1` (ours anchor) vs `external_s1_budget_forcing` (s1 inference-only adapter).
- Same dataset, seeds, and budget grid.

Budget matching:
- Internal budget unit is `action`.
- We also report a token-equivalent column via fixed mapping:
  - `token_equivalent_cost = actions * action_to_token_equivalent`.
- This is a **reporting conversion**, not a claim of exact token-level engine parity.

Secondary comparison:
- Full/official s1 results are reported only when provided/imported, and explicitly labeled as potentially including post-training.

---

## Metrics and table-ready fields

At minimum, runs report:
- `accuracy` and `exact_match` (equal in current task extraction path),
- `avg_token_cost_equivalent` (plus `avg_actions`),
- `budget_adherence_rate`,
- `budget_violation_rate`,
- `budget_exhaustion_rate`,
- frontier summaries (Pareto on cost vs quality).

These are emitted in CSV/JSONL files suitable for manuscript table assembly.

---

## Explicit non-claims

- No claim that this repo fully reproduces s1/s1.1 paper numbers.
- No claim of exact parity with upstream tokenizer/serving/stop-token internals.
- MODE B is not marked complete unless official/full outputs are supplied and recorded.

---

## Upstream references

- Paper: https://aclanthology.org/2025.emnlp-main.1025/
- PDF: https://aclanthology.org/2025.emnlp-main.1025.pdf
- Official code: https://github.com/simplescaling/s1
