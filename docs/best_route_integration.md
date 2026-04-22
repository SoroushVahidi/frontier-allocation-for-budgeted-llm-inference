# BEST-Route integration note (official adjacent import-validated lane)

## Canonical reference

- **Paper title:** *BEST-Route: Adaptive LLM Routing with Test-Time Optimal Compute*
- **Authors:** Dujian Ding, Ankur Mallick, Shaokun Zhang, Chi Wang, Daniel Madrigal, Mirian Del Carmen Hipolito Garcia, Menglin Xia, Laks V.S. Lakshmanan, Qingyun Wu, Victor Ruhle
- **Venue / year / status:** ICML 2025 (main conference; also on arXiv as `2506.22716`)
- **Paper:** https://arxiv.org/abs/2506.22716
- **Official code repository:** https://github.com/microsoft/best-route-llm
- **Project/publication page:** https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/

## Provenance and repository classification

- **Provenance level:** `official`
- **Normalized status (this repo):** `import_validated`
- **Control-equivalence label (this repo):** `adjacent`
- **Canonical config:** `configs/best_route_official_import_v1.json`
- **Canonical validator:** `scripts/verify_best_route_import.py`

This classification means the upstream method/code is official, and this repository provides a conservative import-validation lane. It does **not** mean this repository reproduces the full BEST-Route training stack end-to-end.

## Runtime status update (2026-04-22 stabilization pass)

- A two-lane runtime pass (`scripts/run_best_route_runtime_stabilization_pass.py`) now enforces:
  - **Lane A:** stable adjacent import-validation and comparison-row export.
  - **Lane B:** explicit crash-isolation matrix + tiny synthetic router run.
- In this pass, the runner produced a full two-lane artifact bundle under `outputs/best_route_runtime_stabilization/<run_id>/` and recorded all 10 requested crash-isolation tests.
- This still required non-upstream compatibility pinning (`transformers==4.50.0`, `tokenizers==0.21.4`) in this container context; full benchmark-faithful upstream reproduction remains out of scope.

## Problem class and scope boundary

BEST-Route is treated here as an **adjacent query-level adaptive routing** baseline:

- action space: choose `(model, n)` where `n` is best-of-n sampling count,
- objective: quality/cost tradeoff under routing policy,
- operating level: query-level routing.

This is **not** the same as this repo’s frontier-allocation control problem over active reasoning branches.

## Safe claims vs unsafe claims

### Safe now

- BEST-Route is integrated in this repo as an **official adjacent import-validated baseline**.
- BEST-Route comparison rows can be reported when imported artifacts pass `scripts/verify_best_route_import.py`.
- BEST-Route should be labeled adjacent-only in comparisons and manuscript text.

### Not safe now

- Claiming BEST-Route is a direct frontier-allocation baseline.
- Claiming full paper-faithful BEST-Route reproduction inside this repository.
- Collapsing “official code exists” into “full in-repo reproduction completed.”

## Minimum runnable path

1. Prepare or import a BEST-Route result package (`metadata.json` + `results.csv`) following `configs/best_route_official_import_v1.json`.
2. Run validator:

```bash
python scripts/verify_best_route_import.py \
  --config configs/best_route_official_import_v1.json \
  --results-path tests/fixtures/best_route_import_valid \
  --expected-dataset gsm8k \
  --expected-split test \
  --expected-budgets 1,2
```

3. Require verdict `import_validated` before using imports for adjacent comparison reporting.

## Artifact expectations

- Package files: `metadata.json`, `results.csv`
- Metadata requirements include:
  - upstream repo + paper URLs,
  - BEST-Route workflow-stage declarations,
  - candidate-arm schema over model + best-of-n,
  - provenance identifiers.
- Results requirements include:
  - explicit `best_route_adjacent_import` mode,
  - explicit `adjacent_only` comparability scope,
  - expected dataset/split/budget coverage,
  - numeric sanity for quality/cost fields.

## Difference from our method

- **BEST-Route:** adaptive **query routing** over `(model, n)` arms.
- **Our method focus:** adaptive **frontier allocation** across active reasoning states/branches.

Therefore, BEST-Route is reviewer-relevant and valuable, but remains an **adjacent** (not direct) baseline in this repository’s normalized taxonomy.


## Strengthened repository-native integration lane (2026-04-21)

Use the canonical runner to produce an artifact-backed BEST-Route adjacent bundle:

```bash
python scripts/run_best_route_adjacent_integration.py \
  --import-config configs/best_route_official_import_v1.json \
  --contract-config configs/best_route_adjacent_comparison_contract_v1.json
```

Outputs are written to:
- `outputs/best_route_adjacent_integration/<run_id>/manifest.json`
- `outputs/best_route_adjacent_integration/<run_id>/status.json`
- `outputs/best_route_adjacent_integration/<run_id>/validation_results.json`
- `outputs/best_route_adjacent_integration/<run_id>/validation_status.csv`
- `outputs/best_route_adjacent_integration/<run_id>/comparison_ready_rows.csv`


Runtime stabilization runner:

```bash
python scripts/run_best_route_runtime_stabilization_pass.py
```

Outputs are written to:
- `outputs/best_route_runtime_stabilization/<run_id>/manifest.json`
- `outputs/best_route_runtime_stabilization/<run_id>/stage_status.csv`
- `outputs/best_route_runtime_stabilization/<run_id>/crash_isolation_matrix.csv`
- `outputs/best_route_runtime_stabilization/<run_id>/comparison_readiness.json`
