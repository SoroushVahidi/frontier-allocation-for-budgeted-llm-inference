# Reviewer first: reproduction and claim-scope guide

This page is the shortest reviewer-facing path through the repository. It intentionally avoids historical run folders unless a canonical document promotes them.

## What this repository claims safely

The project studies frontier allocation and final-answer selection under explicit inference-budget contracts.

Safe current claims:

- The repository has an audited recovery-track outcome-verifier selector configuration.
- The selected verifier selector is a recovery/selector-evidence track choice only.
- `external_l1_max` is the strong external comparator to beat in current real-model comparisons.
- Timestamped `outputs/` folders are provenance; use canonical docs and manifests before citing numbers.

Unsafe without a new canonical promotion:

- Broad or universal superiority over `external_l1_max`.
- Runtime promotion of the selected outcome-verifier selector.
- Headline conclusions from cache-limited verifier runs, mock-backed verifier runs, or selected external-loss subsets.

## Minimal setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

Paid/API verifier tooling is optional and intentionally not installed by default:

```bash
python -m pip install -e .[dev,api]
```

## Reviewer-safe checks

These commands should not require paid API calls:

```bash
make health
make reviewer-test
make selector-test
```

Optional broader local check:

```bash
python -m pytest -q
```

## Paper artifact regeneration

Canonical paper-facing artifacts are regenerated with:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Canonical output roots:

- `outputs/paper_tables/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`

## Required reading before writing or reviewing claims

1. `START_HERE_CURRENT.md`
2. `docs/PAPER_SOURCE_OF_TRUTH.md`
3. `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
4. `docs/CURRENT_PROJECT_STATUS.md`
5. `docs/CURRENT_EXTERNAL_BASELINE_GAP.md`
6. `docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`
7. `docs/ARTIFACT_STATUS_TABLE.md`

## Selector/API separation

Use `scripts/run_outcome_verifier_answer_group_selector.py` for dry-run call-plan, heuristic, or cached-score selector evaluation. Use the dedicated scoring script for paid/API verifier score generation:

```bash
python scripts/run_outcome_verifier_scoring.py --help
```

Do not treat missing-score fallback behavior as a real selected-verifier comparison.
