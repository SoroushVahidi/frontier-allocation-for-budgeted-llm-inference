# Cohere-Assisted PAL Failure Mechanism Labeling (2026-05-11)

## What This Is

This adds a **controlled annotation utility** to help label likely concrete failure mechanisms for a **small, targeted subset** of the `157` PAL still-failing covered cases.

- This is **pattern discovery / annotation**, not a new controller.
- Labels are **heuristic** and **not ground truth**.
- The deterministic no-API miners remain the primary evidence sources.

## Motivation

Recent no-API mining shows strong high-level patterns but weak concrete mechanism metadata:

- `gold_absent`: `157/157`
- `frontier_collapse_low_diversity`: `155/157`
- `direct_seed_wrong_or_missing`: `155/157`
- `wrong_supported_consensus`: `97/157`
- `direct_l1_anchor_potential`: `43/157`
- `unknown_mechanism`: `153/157`

We want to reduce the `unknown_mechanism` bucket for a small slice and decide whether to prioritize:

- stronger Direct L1 seed and independent arithmetic/unit self-check,
- anti-intermediate-answer instruction,
- money/unit-ledger strengthening,
- ratio/percentage base normalization,
- duplicate wrong-consensus penalties,
- or richer tree logging if metadata is insufficient.

## Script Added

[scripts/cohere_label_pal_failure_mechanisms.py](/home/soroush/frontier-allocation-for-budgeted-llm-inference/scripts/cohere_label_pal_failure_mechanisms.py)

Key properties:

- Defaults to **no-API** (dry-run).
- Requires `--allow-api` to make Cohere calls.
- Enforces a strict `--max-calls` cap (hard stop).
- Supports resume mode to skip already-labeled case IDs.
- Writes structured JSONL rows, a manifest, a summary, and a short markdown report.
- No OpenAI/Anthropic imports.

## Inputs / Subsets

The script expects `case_coverage_details.csv` from the merged recovery-coverage audit.

Subsets:

- `diagnostic_15`: deterministic 15-case slice (small pilot).
- `direct_l1_potential`: unresolved PAL failures where anchor-effect metadata indicates direct-L1 potential (target slice; expected size ~43 when using the same coverage audit inputs).
- `unresolved_covered`: all PAL `still_fails` covered cases (large; do not label broadly without explicit approval).

## Output Files

The script writes to `--output-dir` (recommended: under `/tmp`):

- `label_rows.jsonl`
- `manifest.json`
- `summary.json`
- `report.md`

## Decision Rule (Heuristic)

- If many labels point to target-quantity misread / arithmetic / unit self-check issues, proceed with stronger Direct L1 seed work.
- If many labels point to wrong-supported-consensus and duplicate inflation, prioritize a consensus penalty.
- If most labels have low confidence or cite insufficient metadata, prioritize richer tree logging (mechanism observability) before more controller tweaks.

## Guardrails

- No runtime behavior change.
- No external-baseline claim.
- Missing coverage in other methods is not treated as failure.
- API use is opt-in and call-capped.

## Validation Ladder

No-API (required):

```bash
python3 scripts/check_repo_health.py
python3 -m pytest -q tests/test_cohere_label_pal_failure_mechanisms.py
python3 scripts/cohere_label_pal_failure_mechanisms.py --subset diagnostic_15 --limit 15 --dry-run --output-dir /tmp/cohere_pal_failure_mechanism_labels_dryrun_20260511
git diff --check main...HEAD
```

Optional API smoke (only if `COHERE_API_KEY` is set; do not exceed 5 calls unless explicitly approved):

```bash
python3 scripts/cohere_label_pal_failure_mechanisms.py --subset diagnostic_15 --limit 5 --max-calls 5 --allow-api --output-dir /tmp/cohere_pal_failure_mechanism_labels_smoke_20260511
```

