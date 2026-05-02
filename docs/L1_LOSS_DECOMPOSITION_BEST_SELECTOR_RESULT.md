# L1 loss decomposition — best DR-v2 selector lane

## Current status

| Field | Value |
|---|---|
| status | `submitted_to_wulver` |
| cluster | Wulver (Slurm) |
| job_id | `1017718` |
| output_dir | `outputs/l1_loss_decomposition_best_selector_20260502T004638Z` |
| max_calls (generator cap) | `12400` (targets ~100 paired triples per estimator) |
| scientific conclusion | _pending — long-running job_ |

### Latest Slurm log

- Stdout: `logs/slurm/l1_loss_decomposition_best_selector_1017718.out`
- Stderr: `logs/slurm/l1_loss_decomposition_best_selector_1017718.err`

Continue monitoring:

```bash
squeue -j 1017718
tail -f logs/slurm/l1_loss_decomposition_best_selector_1017718.out
```

### Fixes applied before resubmit

- Resolved **`Path.relative_to`** failures when `--output-dir` was relative by resolving **`out_root`** and using **`REPO_ROOT.resolve()`** everywhere **`relative_to`** is used (including validation paths in **`selected_method_decision.json`**).

### Earlier attempt (reference only)

- Job **1017716** used **`--max-calls 600`** (~4 paired cases) and hit the **`relative_to`** bug before completing artifacts; superseded by **1017718**.

### Canonical evaluation defaults

- Dataset: `openai/gsm8k` (HF split defaults to test via loader)
- Seed: `20260501`
- Budget: `4`
- Target paired cases: `100`
- Cohere chat model: `command-a-03-2025`
- OV rerank verifier model (env): `DR_V2_OV_RERANK_COHERE_MODEL=command-a-03-2025`

### Selector fallback order

1. `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`
2. `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`
3. `direct_reserve_semantic_frontier_v2_selection_fix_v1`

---

_No secrets are recorded in this document._
