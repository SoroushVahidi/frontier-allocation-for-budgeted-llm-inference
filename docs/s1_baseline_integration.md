# s1 baseline integration (reviewer-defensible split)

This document defines the repository's **fair and conservative** s1 integration for the fixed-budget allocation project.

## Mode definitions

## MODE A (primary): inference-only s1 budget forcing

- Name: **`inference_only`**.
- Goal: apples-to-apples comparison with unchanged-base-model controller baselines.
- Status: **implemented and runnable in this repository**.
- Runner:
  - `python scripts/run_s1_budget_forcing_baseline.py --config configs/s1_budget_forcing_inference_only_v1.json`

## MODE B (secondary): official/full results import + verification

- Name: **`full_or_official`**.
- Goal: side-by-side reporting for official/full s1 outputs when those outputs are externally produced.
- Status: **usable when verified official/full results package is provided**.
- Runner:
  - `python scripts/run_s1_budget_forcing_baseline.py --config configs/s1_full_or_official_adapter_v1.json`

Critical boundary:
- MODE B in this repo is **not** local full post-training reproduction.
- MODE B is a strict import contract with verification gates.

---

## MODE B official import contract (`s1_mode_b_official_import_v1`)

Required package at `official.results_path`:
- `metadata.json`
- `results.csv`

### Required metadata coverage

The metadata must include explicit fields for:
- source type (`official` / `author-produced` / `imported`),
- model/checkpoint identity,
- dataset identity + split,
- prompt template + prompt family,
- budget unit + budget settings,
- token accounting field mapping,
- decoding settings,
- metrics schema + primary metrics,
- provenance fields (`source_uri`, `exported_at_utc`, artifact id),
- commit/version/artifact identifiers (or explicit `..._if_available` field).

Canonical required keys are defined in:
- `configs/s1_full_or_official_adapter_v1.json` (`official.required_metadata_fields`)
- `scripts/verify_s1_mode_b_import.py`

### Required results table coverage

`results.csv` must include comparison-safe columns (including mode/source, dataset/split, model/prompt identity, budget setting, metrics, decoding settings, provenance ids).

Canonical required columns are defined in:
- `configs/s1_full_or_official_adapter_v1.json` (`official.required_results_columns`)
- `scripts/verify_s1_mode_b_import.py`

---

## Verification behavior

Verifier scripts:
- `scripts/verify_s1_mode_b_import.py`
- `scripts/generate_s1_mode_b_import_report.py`

Checks include:
- required files exist,
- metadata schema completeness,
- results schema completeness,
- dataset + split match run declaration,
- budget fields are parseable and cover expected budget grid,
- no MODE A mixing (`inference_only`, MODE A method markers),
- numeric metric/decode fields are interpretable,
- result rows are normalized for comparison tables.

Decision policy:
- no `official.results_path` → MODE B `blocked` with explicit reason,
- provided + valid package → MODE B `validated_imported_results`,
- provided + invalid package → MODE B `invalid_import_rejected` with report.

---

## MODE B run artifacts

Each run emits:
- `outputs/s1_baseline/<run_id>/official_mode_import.csv`
- `outputs/s1_baseline/<run_id>/official_mode_import_report.md`
- `outputs/s1_baseline/<run_id>/fairness_report.md`
- `outputs/s1_baseline/<run_id>/manifest.json`

Additional run artifacts still include:
- `summary.csv`, `summary_per_seed.csv`, `per_example.jsonl`, `comparison_to_ours.csv`, `frontier_summary.csv`, `note.md`.

---

## Manuscript-safe wording

Safe wording:
- “MODE A is the in-repo inference-only fair adapter.”
- “MODE B is an official/full-results import path with strict verification gates.”
- “MODE B does not imply local full s1 post-training reproduction in this repository.”

Not safe wording:
- “this repo fully reproduces official s1 training results” (unless that stack is actually added and auditable).

---

## Upstream references

- Paper: https://aclanthology.org/2025.emnlp-main.1025/
- PDF: https://aclanthology.org/2025.emnlp-main.1025.pdf
- Official code: https://github.com/simplescaling/s1
