# Cohere rerank branch-allocation bounded pass (2026-04-17)

## Why this was tested

Current bottleneck is supervision target mismatch for next-step branch allocation, especially near-tie / defer-worthy hard states. We tested whether a **listwise candidate-set ranker** can provide a useful comparison against current pairwise-focused methods.

## Repo-grounded insertion points used

- Branch candidate rows: `candidate_labels.jsonl` in target-regime directories.
- Pairwise supervision rows/baseline aggregation: `pairwise_labels.jsonl`.
- Existing hard-case semantics reused: near-tie definition from top-2 estimated-value gap.
- Existing branch-allocation workflow area: brute-force target/learning scripts under `scripts/` and `experiments/`.

## Option assessment (A/B/C/D)

1. **Option A: Cohere Rerank candidate-set branch scorer**
   - Bottleneck match: high (direct listwise next-step decision).
   - Reuse: current candidate artifacts; no new data model needed.
   - Complexity: small-to-medium.
   - Repo status: **bounded experimental**.
2. **Option B: Cohere Rerank near-tie fallback**
   - Bottleneck match: high on hard slices only.
   - Reuse: existing near-tie gates + baseline fallback.
   - Complexity: small.
   - Repo status: **bounded experimental helper**.
3. **Option C: Cohere embeddings retrieval fallback**
   - Bottleneck match: medium/indirect for next-step allocation.
   - Complexity: medium-to-large (retrieval corpus + policy coupling).
   - Repo status: exploratory.
4. **Option D: other**
   - No cleaner minimal path than A in current repo structure.

### Chosen path

Primary path: **Option A** (candidate-set Cohere Rerank baseline).

Supportive path also executed: **Option B** (hard-only fallback) to test selective use under ambiguity.

## What was implemented

- New runnable script:
  - `scripts/run_cohere_rerank_branch_allocation_experiment.py`
- Script behavior:
  - serializes per-state branch candidates into structured JSON candidate documents;
  - forms budget-aware ranking query payload;
  - calls Cohere Rerank (`ClientV2.rerank`) and records per-state ranked branch ids;
  - computes matched top-1 proxy metrics versus:
    - heuristic score baseline,
    - pairwise-vote baseline;
  - writes run manifest, per-state requests, per-state rankings, and machine-readable summary.
- Script index updated:
  - `scripts/README.md` now includes this Cohere rerank experiment path.

## Commands used (recorded)

```bash
python -m pip install -q cohere==5.15.0

python scripts/run_cohere_rerank_branch_allocation_experiment.py \
  --labels-dir outputs/branch_label_bruteforce_targets/validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417/regime_penalized_marginal_defer \
  --run-id cohere_rerank_penalized_all_states_20260417 \
  --eval-split all \
  --max-states 80 \
  --model rerank-v3.5 \
  --top-n 8

python scripts/run_cohere_rerank_branch_allocation_experiment.py \
  --labels-dir outputs/branch_label_bruteforce_targets/validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417/regime_penalized_marginal_defer \
  --run-id cohere_rerank_penalized_hard_fallback_20260417 \
  --eval-split all \
  --max-states 80 \
  --model rerank-v3.5 \
  --top-n 8 \
  --hard-only-fallback \
  --fallback-policy pairwise_vote
```

## Headline findings (bounded)

From `outputs/cohere_branch_allocation_rerank/cohere_rerank_comparison_20260417/comparison_summary.json`:

- Option A (all-states Cohere rerank) top-1 accuracy vs oracle proxy: `0.3375`.
- Option B (hard-only fallback Cohere) top-1 accuracy vs oracle proxy: `0.6375`.
- Pairwise-vote baseline top-1 accuracy vs oracle proxy: `0.7625`.
- Heuristic-score baseline top-1 accuracy vs oracle proxy: `0.5375`.
- Hard-only fallback Cohere coverage: `0.3750`.

Interpretation:
- Pure Cohere rerank is a useful external listwise comparison point but is not competitive with current pairwise-vote baseline in this bounded pass.
- Selective hard-only Cohere fallback is materially better than pure Cohere and better than heuristic score baseline, but still below pairwise-vote baseline.

## Fairness / auditability notes

- Cohere path is **listwise**, while current strong baseline is **pairwise-vote**.
- To keep comparison honest, all methods are evaluated on the same state set using the same top-1 proxy target: max `estimated_value_if_allocate_next` from candidate artifacts.
- Secrets are not written; request config/model/top_n are recorded in output manifests.

## Caveats

- Top-1 oracle proxy depends on candidate estimated values and inherits any approximation noise.
- This is bounded (`80` states, one regime family) and should not be over-generalized.
- This does not yet evaluate end-to-end task solve accuracy; it is decision-proxy-level comparison.

## Next recommended step

Run a **prompt/serialization ablation** for Option A within this same script path:
- compact numeric JSON candidate docs vs richer natural-language docs,
- two rerank models,
- then re-check near-tie and budget-slice metrics under identical state set.

If still below pairwise baseline, retain Cohere rerank as a bounded comparison/fallback tool rather than a primary controller path.
