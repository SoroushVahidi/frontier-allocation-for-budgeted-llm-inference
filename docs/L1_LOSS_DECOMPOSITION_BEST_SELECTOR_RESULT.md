# L1 loss decomposition — best DR-v2 selector lane

## Current status

| Field | Value |
|---|---|
| status | `submitted_to_wulver` |
| cluster | Wulver (Slurm) |
| job_id | `1017716` |
| output_dir | `outputs/l1_loss_decomposition_best_selector_20260501T120000Z` |
| scientific conclusion | _not available yet — job was still running after the 2-minute startup window_ |

### Monitoring summary (first 2 minutes, 30-second cadence)

- Slurm accepted the job and scheduled it on node `n0111` (`debug` partition).
- Log path: `logs/slurm/l1_loss_decomposition_best_selector_1017716.out`
- Errors path: `logs/slurm/l1_loss_decomposition_best_selector_1017716.err`
- Startup checks printed hostname, UTC time, git SHA `5a7d2e0923c6fc8d41eee2bd20d6cd556f53e7b5`, Python `3.11.5`, boolean presence for credentials (`COHERE_API_KEY_present=true`, `HF_TOKEN_present=true`) without revealing values.
- The decomposition wrapper created `outputs/l1_loss_decomposition_best_selector_20260501T120000Z/` early (at minimum `call_budget_summary.json`).
- Cohere readiness probe succeeded (`Cohere readiness check passed: tiny authenticated request succeeded.`).
- Validation progress lines appeared for `external_l1_max`, `direct_reserve_semantic_frontier_v2`, and started `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` — real API execution began.

### Call-cap note for this submission

This submission used `--max-calls 600` on the command line. The wrapper estimated ~124 generator-level API calls per paired triple at budget `4`, so **600 calls caps the run to ~4 paired instances**, not 100 (see `call_budget_summary.json` in the output directory). This is explicitly **diagnostic / cap-limited**, not full 100-case evidence.

The checked-in batch file now defaults `MAX_CALLS` to **12400** (override per site quota). Resubmit with:

```bash
export MAX_CALLS=12400
export STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
./scripts/submit_l1_loss_decomposition_wulver.sh
```

### Canonical evaluation defaults

- Dataset: `openai/gsm8k` (HF split defaults to test via loader)
- Seed: `20260501`
- Budget: `4`
- Target paired cases: `100`
- Cohere chat model: `command-a-03-2025`
- OV rerank verifier model (env): `DR_V2_OV_RERANK_COHERE_MODEL=command-a-03-2025`

### Selector fallback order (implemented in `scripts/run_l1_loss_decomposition_for_best_selector.py`)

1. `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` when slices complete and mock-backend signals are absent under `DR_V2_OV_RERANK_VERIFIER_BACKEND=cohere`.
2. `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`
3. `direct_reserve_semantic_frontier_v2_selection_fix_v1`

### Continue monitoring

```bash
squeue -j 1017716
tail -f logs/slurm/l1_loss_decomposition_best_selector_1017716.out
```

### Post-run note (job 1017716)

The batch stdout reached selector scoring for four paired instances, but the Python wrapper exited with an error while writing the final `run_progress_summary.json` (`pathlib.Path.relative_to` mixed absolute/relative roots). That bug is fixed on branch `feat/l1-loss-decomposition-wulver-run` by resolving output paths; **resubmit** after pulling that branch so artifacts finish cleanly.

---

_No secrets are recorded in this document._
