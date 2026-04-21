# BEST-Route strengthening pass (2026-04-21)

## Decision and integration mode

Chosen mode: **stronger import-validated comparator with reproducible artifact contract**.

Why this is the strongest honest mode now:
- upstream BEST-Route (`microsoft/best-route-llm`) is runnable, but requires a heavy multi-stage pipeline (dataset mixing, multi-sample generation, armoRM/proxy-RM scoring, router training) and model/API resources not reproduced in this repository,
- this repository can safely and reproducibly validate official/author-produced imports and convert them into comparison-ready adjacent rows,
- claiming full in-repo faithful reproduction would be overclaiming at the current repo state.

## What was integrated in this pass

1. **Canonical comparison contract config**
   - `configs/best_route_adjacent_comparison_contract_v1.json`
   - Defines canonical benchmark mix coverage expectations and package locations.

2. **Repository-native BEST-Route integration runner**
   - `scripts/run_best_route_adjacent_integration.py`
   - Runs strict BEST-Route import validation per dataset and exports machine-readable artifacts.

3. **Artifact bundle output lane**
   - `outputs/best_route_adjacent_integration/<run_id>/`
   - Emits:
     - `manifest.json`
     - `status.json`
     - `validation_results.json`
     - `validation_status.csv`
     - `comparison_ready_rows.csv`

4. **Documentation/index updates**
   - `docs/best_route_integration.md` (adds strengthened runner path)
   - `docs/CURRENT_BASELINE_NEXT_STEPS_2026_04_21.md` (BEST-Route marked strengthened)
   - `docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md` (ordering updated)
   - `docs/main_baselines.md` (includes strengthened BEST-Route command lane)

## Upstream inspection summary (`microsoft/best-route-llm`)

Repository-level facts checked in this pass:
- upstream repo contains `README.md`, `LICENSE.md`, `train_router.py`, package code, notebooks, and `requirements.txt`,
- published run path includes prompt mixing, multi-sample response generation, oracle RM scoring, proxy RM modeling/scoring, and router training,
- dependencies include model-training stack and `llm-blender` from GitHub.

Honest boundary:
- this pass **does not** claim full upstream training/eval reproduction in this repo,
- this pass **does** claim reproducible adjacent import validation + export for comparison tables.

## Commands

Primary integration command:

```bash
python scripts/run_best_route_adjacent_integration.py \
  --import-config configs/best_route_official_import_v1.json \
  --contract-config configs/best_route_adjacent_comparison_contract_v1.json
```

Direct validator command (single package):

```bash
python scripts/verify_best_route_import.py \
  --config configs/best_route_official_import_v1.json \
  --results-path tests/fixtures/best_route_import_valid \
  --expected-dataset gsm8k \
  --expected-split test \
  --expected-budgets 1,2
```

## What is officially verified now

Verified in-repo:
- BEST-Route package schema validation (`metadata.json` + `results.csv`) with strict checks,
- provenance and workflow-stage declarations,
- adjacent-only comparability enforcement,
- comparison-ready row export from validated imports.

Not verified in-repo:
- full upstream model generation/scoring/training execution,
- paper-level absolute metric reproduction across all canonical datasets,
- direct frontier-allocation control equivalence.

## Safe vs unsafe comparison claims

Safe now:
- BEST-Route can be used as an **official adjacent import-validated** baseline with artifact-backed rows,
- validated BEST-Route import rows are safe for adjacent comparison tables and narrative.

Unsafe now:
- “BEST-Route is fully reproduced end-to-end in this repo.”
- “BEST-Route is direct-control equivalent to branch/frontier allocation.”

## Is BEST-Route ready for main adjacent-baseline story?

**Yes** for adjacent-paper-facing reporting, when rows come from validated imports and remain explicitly `adjacent_only`.

## Canonical benchmark mix status in this pass

- First repo-side run validates the available GSM8K fixture package and exports comparison rows.
- Full canonical mix coverage remains partial because imported BEST-Route packages for MATH-500, AIME 2024, and OlympiadBench are not yet available in-repo.
- This is documented as a blocker in `status.json` and `validation_status.csv` for the run artifact.
