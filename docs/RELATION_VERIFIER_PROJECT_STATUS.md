# Relation Verifier — Project Status Handoff

**Last updated:** 2026-05-17 (SetFit tuning results recorded; cfg1 selected)
**Branch:** `feat/missing-gold-topology-v1`
**Canonical fast read:** after `README.md` and `docs/CURRENT_STATE_SUMMARY_20260511.md`
**Model/data/evaluation details:** see `docs/RELATION_VERIFIER_MODEL_CARD.md`

---

## 0. Current Status (2026-05-16)

### Branch
`feat/missing-gold-topology-v1` — active development.

### Labeling
- Positive-candidate batch (100 rows) **fully labeled**: ready=83, not_ready=17.
- All labels are human-reviewed; Azure strong model (`gpt-5.4`) used only for
  hard adjudication disagreements — not as automatic ground truth.
- Combined training dataset rebuilt: **380 rows** (33 seed + 250 expansion + 100 positive),
  ready=93, not_ready=287 (~3:1 imbalance, workable for SetFit).

### Model leaderboard (grouped 5-fold CV, OOF — FINAL)

| System | ready F1 | PR-AUC | Notes |
|---|---|---|---|
| TF-IDF + LogReg (balanced) | 0.710 | 0.808 | sklearn baseline |
| Frozen mpnet + SVM (balanced) | 0.786 | 0.844 | embedding baseline |
| SetFit mpnet first run (e1 i10) | 0.857 | 0.866 | pre-tuning |
| **SetFit cfg1 (e1 i20) ← selected** | **0.865** | **0.890** | **tuning winner** |
| SetFit cfg3 (e2 i20) | 0.868 | 0.860 | higher F1, worse PR-AUC |

**SetFit tuning is complete** (finished 2026-05-17T02:13Z). cfg5 (batch=32) failed CUDA OOM.
cfg1 selected: best PR-AUC=0.890, ready F1=0.865, confusion TN=271/FP=16/FN=10/TP=83.
More iterations (i10→i20) consistently helps; more epochs (e1→e2) hurts PR-AUC (overfitting).

### Completed since tuning

- ~~**A) Bootstrap CIs / per-fold reporting**~~ — **Done (2026-05-17).**
  `scripts/analyze_relation_verifier_predictions.py` added. 1000-rep bootstrap on cfg1 OOF
  predictions: ready F1=0.8646 [0.8095, 0.9111] (example) / [0.8045, 0.9140] (group).
  Both CI lower bounds exceed frozen-mpnet SVM (0.786). PR-AUC=0.883 [0.811, 0.9476].
  Per-fold F1: mean=0.867, std=0.050, range [0.791, 0.914]. See §8a of MODEL_CARD.md.
- ~~**B) Held-out split sanity check**~~ — **Done (2026-05-17).**
  `--eval-split-mode explicit` added to trainer; test set has 0 ready examples so not
  diagnostic for F1, but confirmed the code path works end-to-end.

### Remaining next steps
- **C)** Label `ready_candidate_batch.csv` (50 rows, unlabeled) if more ready data needed.
- **D)** ModernBERT / DeBERTa baseline — only if SetFit F1=0.865 is judged insufficient.

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
- All 250 rows labeled: 245 `not_ready` (175 opaque bulk-labeled), 5 `ready`
- Label CSV: `outputs/relation_verifier_training_pool_expansion_20260515T050603Z/manual_audit_batch.csv`

### Positive candidate batch (100 rows) — **FULLY LABELED**
- Exported by `export_relation_verifier_positive_candidate_batch.py`
- Source: `per_example_records.jsonl` files, `exact_match=True`, non-opaque traces
- Batch: `outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/positive_candidate_batch.csv`
- **All 100 rows labeled:** ready=83, not_ready=17 (human-reviewed; Azure `gpt-5.4` used only for hard adjudication)

### Combined training dataset — **CURRENT: 380 rows**
- `outputs/relation_verifier_training_dataset_combined_33plus250plus100_20260516T221311Z/`
- 380 rows included; label totals: **ready=93, not_ready=287** (~3:1 imbalance)
- Prior dataset (280 rows, ready=10) is superseded — do not use for new training.

### Ready candidate batch (50 rows) — **not yet labeled**
- Exported by `export_relation_verifier_ready_candidate_batch.py`
- Source: structured artifacts with `candidate_nodes` / `final_nodes` fields
- Batch: `outputs/relation_verifier_ready_candidate_batch_20260515T235155Z/ready_candidate_batch.csv`
- Label these if more `ready` examples are needed after SetFit tuning results.

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

## 6. Provider Consistency Policy

These rules govern how Cohere, Mistral, and Azure/OpenAI are used across different
parts of the project, and what may be claimed in any paper or report.

### 6a. Main method comparisons

- Use the **same provider** for all methods compared within a single experiment.
- Existing 100-case comparison evidence is **Cohere-based** (`run_relation_verifier_cohere_judge_adapter.py`, `relation100` subset).
- Claims about `best` vs `external_l1_max` must not mix Cohere results for one method
  with Azure/OpenAI results for another.
- If Azure/OpenAI is used to replicate a comparison, it must be reported as a **separate
  replication experiment**, not merged with the existing Cohere evidence.

### 6b. Verifier labeling

- Azure/OpenAI may be used as an **annotation assistant** or **adjudication helper**
  (e.g., `run_relation_verifier_azure_labeler.py`).
- Azure/OpenAI labels are **preliminary** unless explicitly human-reviewed and accepted.
- **Final training labels must be human-reviewed/accepted** — automated labels are
  draft inputs to human judgment, not ground truth.
- Gold answers must never be used as model input features or included in provider prompts
  (see §5 leakage conventions).

### 6c. Judge and calibration experiments

- Cohere, Mistral, and Azure/OpenAI judge outputs should be **reported as provider-specific
  judge-calibration results**, not merged as a single ground truth.
- Do not merge fine-grained axis labels from different providers into a single supervision signal.
- Evidence from multi-judge runs showed providers are useful for **binary sanity checks**
  but are unreliable for fine-grained axis labeling; do not use provider axis labels for training.

### 6d. Disagreement adjudication

- A strong Azure/OpenAI model may be used as a **diagnostic critic** on hard annotation
  disagreements, but only as a second opinion, not as an automatic overwrite.
- Azure/OpenAI diagnostic output must not automatically change human labels.
- Any label changes following a diagnostic run must be **documented as human adjudication**,
  with the human annotator's reasoning recorded in `notes_manual`.

### 6e. Paper reporting

Any result section or claim must clearly separate:

1. **Method-performance provider** — which provider's outputs were evaluated.
2. **Label-assistance provider** — which provider (if any) assisted annotation.
3. **Final human-reviewed training labels** — the ground truth used for training/evaluation.

Conflating these three will invalidate experimental claims.

---

## 7. Current Problems / Blockers  <!-- was §6 -->

| Problem | Details |
|---|---|
| ~~Class imbalance~~ | ~~Resolved~~ — positive batch labeled; combined dataset now ready=93, not_ready=287 |
| SetFit tuning not yet complete | cfg3–cfg5 still running; final config selection pending |
| Ready candidate batch unlabeled | 50-row `ready_candidate_batch.csv` not yet labeled; may be needed if more ready data required |
| Single-comparison underpowered | 100-case Cohere run affected by nondeterminism; repeated/cached replay needed for paper claims |
| No ModernBERT/DeBERTa decision yet | Pending SetFit tuning results — may not be needed if SetFit F1 is sufficient |

---

## 8. Recommended Next Steps  <!-- was §7 -->

**Immediate (wait for active job):**
1. Wait for `setfit_tune` tmux session to complete (cfg3–cfg5 remaining, ~35–45 min as of 21:50 2026-05-16).
2. Read `outputs/relation_verifier_setfit_tuning_*/master.log` and all `cfg*/metrics.json`.
3. Choose best stable config. Current leader: **cfg1** (e1 i20) — ready F1=0.865, PR-AUC=0.890.

**After tuning (decision gate):**
4. If best tuned SetFit ready F1 ≥ 0.87: proceed to integration. ModernBERT/DeBERTa optional.
5. If SetFit plateaus below 0.87: label `ready_candidate_batch.csv` (50 rows) to add more positives, then retrain.

**Integration (after verifier is good enough):**
6. Run verifier on held-out candidate traces to score relation-readiness.
7. Integrate verifier score into the selector / budget-allocation policy.
8. Revisit repeated Cohere comparison with caching/replay for paper-strength claims.

---

## 9. Labeling Workflow (for future agents)  <!-- was §8 -->

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

## 10. Key File Locations  <!-- was §9 -->

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
| Combined training dataset (current) | `outputs/relation_verifier_training_dataset_combined_33plus250plus100_20260516T221311Z/` |
| Positive candidate batch (fully labeled) | `outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/positive_candidate_batch.csv` |
| Ready candidate batch (unlabeled) | `outputs/relation_verifier_ready_candidate_batch_20260515T235155Z/ready_candidate_batch.csv` |
| TF-IDF baseline results | `outputs/relation_verifier_baseline_combined380_grouped_threshold_train_20260516T222426Z/` |
| Frozen embedding baseline results | `outputs/relation_verifier_embedding_mpnet_svm_grouped_20260516T230932Z/` |
| First SetFit run results | `outputs/relation_verifier_setfit_mpnet_train_20260516T233217Z/` |
| SetFit tuning study (active) | `outputs/relation_verifier_setfit_tuning_20260516_20260517T000951Z/` |
