# BEST-Route (Microsoft) external baseline import lane

## Upstream references

- **Official repo:** https://github.com/microsoft/best-route-llm
- **Paper:** https://arxiv.org/abs/2506.22716
- **Microsoft Research page:** https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/
- **Upstream license:** MIT (`LICENSE.md` in upstream repo; verify on pinned commit when cloning)

## What to clone

This repository does **not** vendor upstream BEST-Route code.

Recommended local clone target (documented in `configs/best_route_official_import_v1.json`):

```bash
git clone https://github.com/microsoft/best-route-llm.git external/best_route_microsoft/upstream/best-route-llm
```

## What the upstream repo is expected to contain

Conservative markers for import-lane validation (if a local clone is available):

- `README.md`
- `LICENSE.md`
- training/eval entrypoint markers such as `train_router.py`, `scripts/train_router.py`, or `src/`

These checks are conservative structural checks, not full pipeline execution.

## How this repository uses BEST-Route

BEST-Route is integrated as an **official adjacent import-validated baseline**:

- resource level: `official`
- status: `import_validated`
- control equivalence: `adjacent`

BEST-Route is treated as query-level adaptive routing over `(model, best_of_n)` arms, not as frontier-allocation control.

## What is and is not claimed

### Claimed

- This repo can validate imported BEST-Route artifacts through a strict contract.
- Adjacent comparison rows are allowed only after validator success.

### Not claimed

- Full paper-faithful BEST-Route reproduction inside this repo.
- Direct control-space equivalence with this repo’s frontier-allocation method.

## Import validation workflow

Canonical files:

- config: `configs/best_route_official_import_v1.json`
- validator: `scripts/verify_best_route_import.py`
- status artifacts:
  - `outputs/external_baseline_completeness/best_route_status.json`
  - `outputs/external_baseline_completeness/best_route_status.md`

Example command:

```bash
python scripts/verify_best_route_import.py \
  --config configs/best_route_official_import_v1.json \
  --results-path tests/fixtures/best_route_import_valid \
  --expected-dataset gsm8k \
  --expected-split test \
  --expected-budgets 1,2
```

## Expected imported artifact shape

Required package files:

- `metadata.json`
- `results.csv`

Contract highlights:

- workflow-stage declarations for BEST-Route pipeline stages,
- candidate-arm declarations including bo1 and at least one bo>1,
- results rows tagged `mode=best_route_adjacent_import` and `comparability_scope=adjacent_only`.
