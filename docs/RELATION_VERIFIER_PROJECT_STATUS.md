# Relation Verifier — Project Status Handoff

**Last updated:** 2026-05-16
**Branch:** `feat/missing-gold-topology-v1`
**Canonical fast read:** after `README.md` and `docs/CURRENT_STATE_SUMMARY_20260511.md`

---

## 1. Current Objective

Train a lightweight binary **RelationReady verifier** to classify whether a reasoning
trace and its final answer establish the problem's target relation through visible,
step-by-step computation — or not.

- **Label 0 `not_ready`**: trace is opaque, truncated, or correct-by-coincidence
- **Label 1 `ready`**: trace shows the full derivation and arrives at the right answer

Axis/error labels (`first_error_axis`) are collected as debug metadata only. API-based
multi-judge axis labeling proved too noisy and inconsistent for fine-grained supervision;
it is not used for training.

---

## 2. Implemented Components

All source in `scripts/`, tests in `tests/`.

### Data / labeling pipeline

| Script | Purpose |
|---|---|
| `build_relation_verifier_seed_dataset.py` | Builds initial 33-row seed from RELATIONREADY_SEED_POOL_V0 |
| `extract_relationready_seed_pool.py` | Extracts raw seed pool from GSM8K and annotated artifacts |
| `build_relation_verifier_training_pool.py` | Builds 250-row expansion pool from all per-example records |
| `export_relation_verifier_manual_audit_sheet.py` | Exports labeling sheets for manual review |
| `export_relation_verifier_labeling_batch_text.py` | Exports text-format labeling batches |
| `validate_relation_verifier_manual_labels.py` | Validates label CSV integrity after manual annotation |
| `export_relation_verifier_ready_candidate_batch.py` | Mines non-opaque candidates likely to be `ready` from structured artifacts |
| `export_relation_verifier_positive_candidate_batch.py` | Mines offline-correct rows from `per_example_records.jsonl` (exact_match=True) for human labeling |

### Judge / provider pipeline (experimental, not used for training)

| Script | Purpose |
|---|---|
| `build_relation_verifier_multijudge_label_requests.py` | Builds judge requests (row→question+trace batch) |
| `build_relation_verifier_provider_payloads.py` | Wraps requests into Cohere/Mistral API payloads |
| `run_relation_verifier_cohere_judge_adapter.py` | Submits to Cohere judge, parses responses |
| `run_relation_verifier_mistral_judge_adapter.py` | Submits to Mistral judge, parses responses |
| `run_relation_verifier_multijudge_calibration.py` | Calibration runner for axis agreement |

### Training pipeline

| Script | Purpose |
|---|---|
| `build_relation_verifier_training_dataset.py` | Merges seed + expansion labels into train/val/test CSV |
| `train_relation_verifier_baseline.py` | sklearn TF-IDF + LogisticRegression baseline with StratifiedKFold(3) |

### External comparison (context only — not verifier-specific)

| Script | Purpose |
|---|---|
| `run_relation_verifier_v1.py` | 20-case live relation-verifier pilot (diagnostic) |
| `build_relation_ready_v0_dataset.py` | v0 dataset builder (superseded) |

---

## 3. Key Experimental Results

### 3a. 100-case Cohere comparison (external-baseline context)

Run against `external_l1_max` on `relation100` subset.

| Stage | Best / PAL | external_l1_max | Notes |
|---|---|---|---|
| Pre-fix | 71/100 | 74/100 | Output-layer mismatch in 9 cases |
| Post-fix | Cohere nondeterminism affected re-run | — | Fix confirmed: mismatch 9 → 0 |

See `docs/RELATION100_COHERE_OUTPUT_LAYER_FIX_NOTE.md` for details.

### 3b. Relation verifier baseline (sklearn)

Combined dataset: 280 rows (33 seed + 250 expansion labels, 3 uncertain excluded)

| Split | Count |
|---|---|
| train | 17 |
| val | 8 |
| test | 5 |
| no-split (expansion) | 250 |

Label distribution: **ready = 10, not_ready = 270** (27:1 imbalance)

Baseline results (`train_relation_verifier_baseline.py`, combined250 run):

| Metric | Value |
|---|---|
| Accuracy | 0.8929 |
| F1-macro | 0.4717 |
| not_ready F1 | 0.94 |
| **ready F1** | **0.00** |

**The model predicts almost all rows as `not_ready`.** Root cause: severe class imbalance —
175 opaque/final-answer-only rows in the expansion pool were bulk-labeled `not_ready`
during a cleaning pass without adding any `ready` examples, worsening the ratio from ~9:1
to 27:1.

---

## 4. Labeling / Data Status

### Seed dataset (33 rows)
- Manually annotated from scratch
- Source: `build_relation_verifier_seed_dataset.py`
- Split: train/val/test

### Expansion pool (250 rows)
- Built from `build_relation_verifier_training_pool.py`
- All 250 rows are now labeled:
  - 245 `not_ready` (175 opaque bulk-labeled in a cleaning pass)
  - 5 `ready`
- Label CSV: `outputs/relation_verifier_training_pool_expansion_20260515T050603Z/manual_audit_batch.csv`

### Combined training dataset
- `outputs/relation_verifier_training_dataset_combined_33plus250_20260515T234443Z/`
- 280 rows included, 3 uncertain excluded
- Current label totals: ready=10, not_ready=270

### Positive candidate batch (100 rows)
- Exported by `export_relation_verifier_positive_candidate_batch.py`
- Source: 64 `per_example_records.jsonl` files from past runs, `exact_match=True`, non-opaque traces
- Batch: `outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/positive_candidate_batch.csv`

**Labeling progress:**

| Row range | Status | Ready | Not-ready |
|---|---|---|---|
| 0–28 (29 rows) | Labeled and patched | 26 | 3 |
| 29–49 (21 rows) | Printed; **pending human labels** | — | — |
| 50–99 (50 rows) | Not yet printed or labeled | — | — |

### Ready candidate batch (50 rows)
- Exported by `export_relation_verifier_ready_candidate_batch.py`
- Source: structured artifacts with `candidate_nodes` / `final_nodes` fields
- Batch: `outputs/relation_verifier_ready_candidate_batch_20260515T235155Z/ready_candidate_batch.csv`
- Status: not yet labeled

---

## 5. Safety / Leakage Conventions

These apply at all times and must be maintained by future agents:

- **Gold answers are offline-only.** Never used as model input features, never in provider
  prompts, never in `feature_text`. The `gold_answer_metadata_only` column is metadata for
  human review and is kept blank by default.
- `is_correct_offline_metadata` is a metadata tag, not a feature. It must never appear in
  `feature_text` or be used as a model input.
- **Long jobs use tmux.** Any training run, API batch, GPU job, or process expected to run
  more than a few minutes must be launched in a `tmux` session.
- **RAM/CPU/GPU/disk must be checked** before any larger training or API batch run.
- **`outputs/` are local-only.** Never staged or committed. All outputs are regenerable from
  scripts + source data.
- **Do not call paid APIs** (OpenAI, Cohere, Mistral, Fireworks, Cerebras) without explicit
  per-call user approval.

---

## 6. Current Problems / Blockers

| Problem | Details |
|---|---|
| Class imbalance | ready=10 vs not_ready=270 in current training set; model F1-ready=0.00 |
| Insufficient ready labels | Need ~50–100 confirmed ready examples minimum for training to be useful |
| API judge noise | Multi-judge axis labeling has low agreement; not suitable for fine-grained supervision |
| Single-comparison underpowered | 100-case Cohere run affected by nondeterminism; repeated/cached replay needed for paper claims |
| No `class_weight='balanced'` yet | Trainer does not yet use imbalance correction — add alongside data fix, not instead of it |

---

## 7. Recommended Next Steps

**Immediate (labeling):**
1. Label rows 29–49 of `positive_candidate_batch.csv` and patch them in (see labeling workflow below).
2. Label rows 50–99.
3. Label the 50-row `ready_candidate_batch.csv`.

**After labeling (training):**
4. Rebuild combined training dataset:
   ```
   python3 scripts/build_relation_verifier_training_dataset.py \
       --seed-csv outputs/relation_verifier_seed_dataset_*/seed_dataset.csv \
       --expansion-csv outputs/relation_verifier_training_pool_expansion_*/manual_audit_batch.csv \
       --positive-csv outputs/relation_verifier_positive_candidate_batch_*/positive_candidate_batch.csv \
       --ready-csv outputs/relation_verifier_ready_candidate_batch_*/ready_candidate_batch.csv \
       --output-dir outputs/relation_verifier_training_dataset_<STAMP>
   ```
5. Add `class_weight='balanced'` and/or oversampling to `train_relation_verifier_baseline.py`.
6. Retrain baseline — target ready F1 > 0.5.
7. If larger training needed: use `tmux`, check RAM/CPU/GPU/disk first.

**After a working verifier:**
8. Run verifier on held-out candidate traces to score relation-readiness.
9. Integrate verifier score into the selector / budget-allocation policy.
10. Revisit repeated Cohere comparison with caching/replay for paper-strength claims.

---

## 8. Labeling Workflow (for future agents)

To label a batch and patch results:

```bash
# Print unlabeled rows for review
python3 - <<'EOF'
import csv
path = "outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/positive_candidate_batch.csv"
with open(path) as f:
    for i, row in enumerate(csv.DictReader(f)):
        if not row["relation_ready_label_manual"]:
            print(i, row["row_id"], row["candidate_trace_short"][:200])
EOF

# After human review, apply labels by row_id:
python3 - <<'EOF'
import csv
path = "..."
labels = {
    "rrpool_XXXX": ("ready", "", ""),
    "rrpool_YYYY": ("not_ready", "source_fact_missing", "Trace is truncated before the final step"),
}
with open(path) as f:
    rows = list(csv.DictReader(f))
    fieldnames = csv.DictReader(open(path)).fieldnames
for row in rows:
    if row["row_id"] in labels:
        lbl, axis, notes = labels[row["row_id"]]
        row["relation_ready_label_manual"] = lbl
        row["first_error_axis_manual"] = axis
        row["notes_manual"] = notes
with open(path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader(); w.writerows(rows)
EOF
```

**Convention:** A row is `ready` only if the trace establishes the target relation through
visible arithmetic/code steps AND arrives at the correct answer. Final-answer-only,
opaque, or truncated traces are `not_ready`.

---

## 9. Key File Locations

| What | Where |
|---|---|
| RelationReady annotation guide | `docs/RELATIONREADY_ANNOTATION_GUIDE.md` |
| RelationReady schema | `docs/RELATIONREADY_SCHEMA.md` |
| Training design | `docs/RELATIONREADY_TRAINING_DESIGN.md` |
| Split policy | `docs/RELATIONREADY_SPLIT_POLICY.md` |
| External verifier references | `docs/EXTERNAL_RELATION_VERIFIER_REFERENCES_20260513.md` |
| Output-layer fix note | `docs/RELATION100_COHERE_OUTPUT_LAYER_FIX_NOTE.md` |
| Seed dataset | `outputs/relation_verifier_seed_dataset_*/seed_dataset.csv` |
| Expansion pool labels | `outputs/relation_verifier_training_pool_expansion_20260515T050603Z/manual_audit_batch.csv` |
| Combined training dataset | `outputs/relation_verifier_training_dataset_combined_33plus250_20260515T234443Z/` |
| Positive candidate batch | `outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/positive_candidate_batch.csv` |
| Ready candidate batch | `outputs/relation_verifier_ready_candidate_batch_20260515T235155Z/ready_candidate_batch.csv` |
| Baseline results | `outputs/relation_verifier_baseline_combined250_train_20260515T234455Z/` |
