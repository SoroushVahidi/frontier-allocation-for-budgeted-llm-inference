# TALE baseline integration (fair, reviewer-defensible)

This document defines a conservative TALE integration for the fixed-budget compute-allocation project.

## Mode split in this repository

## MODE A (primary): `prompt_budgeting_inference_only`

- Runnable in this repository.
- In-repo TALE-style prompt-budgeting adapter (per-instance budget estimation + prompt injection).
- Does **not** include TALE-PT post-training.

Runner:
- `python scripts/run_tale_baseline.py --config configs/tale_prompt_budgeting_v1.json`
- `python scripts/run_tale_matched_surface_fairness_closure.py --timestamp <UTC_TIMESTAMP>`

## MODE B (secondary): `official_full_adapter`

- Strict official/full TALE results import + verification path.
- Usable when valid external official/full package is provided.
- Not a local full TALE/TALE-PT reproduction claim.

Runner:
- `python scripts/run_tale_baseline.py --config configs/tale_official_adapter_v1.json`

Critical boundary:
- MODE A and MODE B must remain separate.
- TALE inference-time variant and TALE-PT variant must remain explicit and unblurred.

---

## MODE B official import contract (`tale_mode_b_official_import_v1`)

Required package at `official.results_path`:
- `metadata.json`
- `results.csv`

### Required metadata coverage

Metadata must explicitly include:
- source type (`official` / `author-produced` / `imported`),
- TALE variant identity (`tale_inference_budgeting` / `tale_pt` / other official TALE variant),
- explicit post-training inclusion flag,
- model/checkpoint identity,
- dataset identity + split,
- prompt template + prompt family,
- budget unit + settings,
- token accounting fields,
- decoding settings,
- metrics schema,
- provenance fields,
- artifact/version/commit identifier if available.

Canonical required keys are defined in:
- `configs/tale_official_adapter_v1.json` (`official.required_metadata_fields`)
- `scripts/verify_tale_mode_b_import.py`

### Required results table coverage

`results.csv` must include comparison-safe rows with explicit TALE variant identity and no MODE A mixing.

Canonical required columns are defined in:
- `configs/tale_official_adapter_v1.json` (`official.required_results_columns`)
- `scripts/verify_tale_mode_b_import.py`

---

## Verification behavior

Verifier scripts:
- `scripts/verify_tale_mode_b_import.py`
- `scripts/generate_tale_mode_b_import_report.py`

Checks include:
- required files exist,
- metadata schema completeness,
- results schema completeness,
- dataset + split match declared run,
- budget fields parseable and expected budget coverage present,
- imported outputs are not mixed with MODE A markers,
- variant identity is explicit and not mixed (TALE vs TALE-PT separation),
- metric/decode fields are numeric/interpretable,
- output rows are normalized for repository comparison tables.

Decision policy:
- no `official.results_path` → MODE B `blocked`,
- provided + valid package → MODE B `validated_imported_results`,
- provided + invalid package → MODE B `invalid_import_rejected`.

---

## MODE B run artifacts

Per run (`outputs/tale_baseline/<run_id>/`):
- `official_mode_import.csv`
- `official_mode_import_report.md`
- `fairness_report.md`
- `manifest.json`

Additional artifacts include:
- `summary.csv`, `summary_per_seed.csv`, `per_example.jsonl`, `note.md`, `comparison_to_ours.csv`, `frontier_summary.csv`.

For manuscript-surface fairness closure packaging:
- `outputs/tale_matched_surface_fairness_closure_<timestamp>/`
- `docs/TALE_MATCHED_SURFACE_FAIRNESS_CLOSURE_<timestamp>.md`

---

## Manuscript-safe wording

Safe wording:
- “MODE A is the in-repo prompt-budgeting TALE adapter.”
- “MODE B is official/full TALE results import with strict verification.”
- “MODE B does not imply local full TALE/TALE-PT reproduction in this repository.”
- “TALE and TALE-PT are explicitly separated in MODE B metadata and reporting.”

Unsafe wording:
- “this repo fully reproduces TALE-PT official training results” (unless that stack is truly added and auditable).

---

## Upstream references

- Paper page: https://aclanthology.org/2025.findings-acl.1274/
- PDF: https://aclanthology.org/2025.findings-acl.1274.pdf
- arXiv: https://arxiv.org/abs/2412.18547
- Official code: https://github.com/GeniusHTX/TALE
