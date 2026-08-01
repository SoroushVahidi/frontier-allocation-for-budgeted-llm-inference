# Pilot Result 2: First API-Backed Real-GSM8K Pilot

This run is the first pilot in this repo that used **real GSM8K data** with an **API-backed branch generator** (OpenAI-compatible Responses endpoint).

## 1) Diagnosis of prior GSM8K loading failures

`experiments/data.py` already attempted Hugging Face `gsm8k/main` first, then mock fallback. The previous failure was environment-side (missing/failed datasets path), not an intentional dataset switch.

What was fixed for robustness now:
- kept Hugging Face as first-class loading path,
- preserved fallback only as backup,
- added explicit fallback error metadata (`load_error`) when fallback is used so it is not silent.

In this run, GSM8K loaded successfully from Hugging Face (`data_source = huggingface:gsm8k`).

## 2) Exact commands used

```bash
python - <<'PY'
import importlib
mods=['experiments.controllers','experiments.branching','experiments.data','scripts.run_pilot_gsm8k','scripts.evaluate_pilot_gsm8k']
for m in mods:
    importlib.import_module(m)
print('imports_ok')
PY

python -m pip install datasets -q
python scripts/run_pilot_gsm8k.py --config configs/pilot_gsm8k.yaml
python scripts/evaluate_pilot_gsm8k.py outputs/pilot/20260412T224353Z
```

## 3) Data + provider/model + pilot setup

- Real GSM8K used: **Yes** (`huggingface:gsm8k`, split `test`).
- Provider used successfully: **OpenAI-compatible Responses path**.
- Model: `gpt-4.1-mini`.
- Pilot size: `12` examples.
- Matched budget: `max_actions_per_problem = 8`.
- Methods compared:
  - Greedy single-path
  - Best-of-N
  - Fixed-width beam
  - Adaptive expand/verify/prune

Note: Runtime had `OPENAI_BASE_URL` configured and API mode executed with that backend proxy (`generator_mode = openai_api`).

## 4) Metrics (run id: `20260412T224353Z`)

| Method | Accuracy | Avg actions | Avg expansions | Avg verifications | Avg surviving branches | Budget exhaustion rate |
|---|---:|---:|---:|---:|---:|---:|
| Greedy single-path | 0.9167 | 3.5000 | 3.5000 | 0.0000 | 1.0000 | 0.0000 |
| Best-of-N | 0.9167 | 8.0000 | 6.5000 | 1.5000 | 2.2202 | 1.0000 |
| Fixed-width beam | 0.9167 | 6.8333 | 6.8333 | 0.0000 | 2.0000 | 0.5000 |
| Adaptive expand/verify/prune | 0.0000 | 1.0000 | 0.0000 | 1.0000 | 0.5000 | 0.0000 |

## 5) Short interpretation

### Did adaptive still lose?

Yes, decisively. On this pilot it failed on all 12/12 examples while all baselines tied at 11/12.

### Is verification still overused?

Yes in a specific way: adaptive appears stuck in verify-then-prune behavior.
From diagnostics totals across 12 examples: `expand=0`, `verify=12`, `prune=12`.
That means adaptive never actually expanded a branch in this run.

### Are these results more trustworthy than pilot_result_1?

Yes, because this run used real GSM8K data and API-backed branch operations. But it is still a tiny pilot (`n=12`), so it is directional rather than definitive.

### Next implementation weakness

Current score/threshold dynamics are broken for adaptive under this backend:
- verify does not lift score above expand threshold,
- controller prunes without exploring,
- policy is overly brittle to score calibration.

## 6) Honesty / limitations

- This run is still small and cost-constrained.
- Results should not be overgeneralized.
- The API path is functional but still provisional (prompted JSON parsing and lightweight verifier heuristic).
