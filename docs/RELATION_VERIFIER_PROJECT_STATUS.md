# Relation Verifier — Project Status Handoff

**Last updated:** 2026-05-17 (independent 720-row Cohere validation + uncertainty + frozen slice-aware transfer readout completed)
**Branch:** `feat/missing-gold-topology-v1`
**Canonical fast read:** after `README.md` and `docs/CURRENT_STATE_SUMMARY_20260511.md`
**Model/data/evaluation details:** see `docs/RELATION_VERIFIER_MODEL_CARD.md`

---

## 0. Current Status (2026-05-17 — verifier accepted, transitioning to frontier integration)

### Branch
`feat/missing-gold-topology-v1` — active development.

### Dataset
Combined training dataset: **380 rows** (33 seed + 250 expansion + 100 positive),
ready=93, not_ready=287 (~3:1 imbalance). All labels human-reviewed.

### Model leaderboard (grouped 5-fold CV, OOF — FINAL, verified from predictions)

| System | ready F1 | PR-AUC | Notes |
|---|---|---|---|
| TF-IDF + LogReg (balanced) | 0.710 | 0.808 | sklearn baseline |
| Frozen mpnet + SVM (balanced) | 0.786 | 0.844 | embedding baseline |
| SetFit mpnet first run (e1 i10) | 0.857 | 0.866 | pre-tuning |
| **SetFit cfg1 (e1 i20) ← selected** | **0.8646** | **0.883** | **tuning winner; see CI below** |
| SetFit cfg3 (e2 i20) | 0.868 | 0.860 | higher F1 at thr=0.5, worse PR-AUC |

PR-AUC note: tuning wrapper reported 0.890 for cfg1; verified from predictions.jsonl = **0.883**.

### CI interpretation (2026-05-17, group-bootstrap 1000 reps)

| Metric | Point estimate | Group-bootstrap 95% CI | vs frozen SVM |
|---|---|---|---|
| Ready F1 | 0.8646 | [0.8045, 0.9140] | ✓ CI lower bound > 0.786 |
| PR-AUC | 0.883 | [0.8027, 0.9467] | ⚠ CI lower bound < 0.844 (overlap) |

**SetFit clearly improves ready F1 over frozen mpnet SVM** — both example-level and
group-level bootstrap lower bounds exceed the SVM baseline (0.786). The improvement
is supported statistically given the available data.

**PR-AUC improvement is not definitive** — point estimate (0.883) is above the SVM
baseline (0.844), but the CI lower bound (0.8027) falls below it. The dataset is
too small for a definitive PR-AUC claim. Describe cautiously in any paper: "PR-AUC
improves from 0.844 to 0.883 (95% CI [0.803, 0.947] by group bootstrap)."

Per-fold ready F1: mean=0.867, std=0.050, range [0.791, 0.914].
Fold 4 is the weakest fold (F1=0.7907, PR-AUC=0.769); the other four folds score
0.842–0.914.

### Completed milestones

- ~~Labeling (100 positive-candidate rows)~~ — Done.
- ~~Sklearn baselines~~ — Done. TF-IDF LogReg: F1=0.710.
- ~~Embedding baselines~~ — Done. Frozen mpnet SVM: F1=0.786.
- ~~First SetFit run~~ — Done. e1 i10: F1=0.857.
- ~~SetFit hyperparameter tuning~~ — Done. cfg1 selected (F1=0.865, PR-AUC=0.883 verified).
- ~~Bootstrap CI / per-fold reporting~~ — Done. `scripts/analyze_relation_verifier_predictions.py`.
- ~~Held-out split sanity check~~ — Done. `--eval-split-mode explicit` added to trainer.
- **Verifier accepted for frontier integration** — Active next step: see §12 of MODEL_CARD.md.
- **Independent/disjoint within-method validation completed (720-row dedup artifact)** — positive same-direction confirmation.

### Remaining optional steps (not blocking integration)
- Label `ready_candidate_batch.csv` (50 rows) if more ready examples needed.
- ModernBERT / DeBERTa baseline — deferred; only if integration reveals systematic failure.

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
| Cross-method method entanglement | On the 1440-row scored artifact, verifier-guided cross-method selection chose `external_l1_max` in 705/720 groups and matched `external_l1_max` accuracy (72.1% vs 72.2%), so naive cross-method `proba_ready` routing is not reliable. |
| Independent within-method validation status | Completed on disjoint Cohere artifact (`raw=738`, `dedup=720`, 120 groups) with cluster-bootstrap uncertainty: verifier-max 86.67% [79.17, 93.33], random 82.08% [75.56, 87.78], anti-verifier 72.50% [64.17, 80.83], oracle 95.83% [90.83, 100.00]. Lift vs random +4.58pp [ +0.28pp, +9.03pp ] overall (aggregate-stable), while per-method lift-vs-random CIs cross 0 (positive but individually uncertain). |
| Slice-aware rules are still unvalidated for promotion | Slice-aware/tie-aware policies were selected on the 1440-row artifact. Frozen transfer to independent validation (`all_positive_net_slices`) was neutral: baseline 0.866667 vs frozen 0.866667 (net gain 0; recoveries/regressions 3/3), with limited slice overlap. |
| Small disjoint validation is underpowered | The 15-case disjoint artifact is same-sign for within-method reranking but too small for strong claims (30 groups total). |
| Frozen-policy transfer overlap gap | Reusable transfer tooling now exists (`scripts/apply_frozen_slice_aware_reranking.py`), but the independent target had budget-6 slices only; most frozen rules were for budgets 4/8, limiting evaluable coverage. |

---

## 8. Recommended Next Steps  <!-- was §7 -->

**Immediate (post-independent-validation):**
1. Keep no-API frontier-analysis mode and conservative claim language.
2. Treat uncertainty as complete for the current independent artifact; use cluster-bootstrap CI as primary in summaries.
3. Treat frozen Task K transfer as implemented/evaluated; if revisited, use only frozen rules on an artifact with better slice overlap (e.g., budget 4/8 coverage).
4. Keep method-entanglement caveat explicit for any cross-method routing claim.

**Promotion criteria:**
5. Treat cross-method verifier routing as non-promotable unless method entanglement is mitigated on independent data.
6. Within-method reranking is now independently positive; further promotion should include uncertainty bounds and reproducible frozen-policy transfer behavior.

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
| SetFit tuning study results | `outputs/relation_verifier_setfit_tuning_20260516_20260517T000951Z/` |
| Selected cfg1 subdir | `.../cfg1_e1_i20_b16_spl2/` |
| CI analysis results | `outputs/relation_verifier_setfit_cfg1_ci_analysis_20260517T025701Z/` |
| CI analysis script | `scripts/analyze_relation_verifier_predictions.py` |

---

## 11. Transition to Frontier Allocation

The RelationReady verifier is now accepted for integration into the main frontier
allocation pipeline. The sub-project goal (binary verifier to filter/score reasoning
traces) is achieved.

### Why accepted

- Ready F1=0.8646, recall=0.8925 — the verifier catches ~89% of relation-ready traces.
- Group-bootstrap CI lower bound for ready F1 (0.8045) is above the strong embedding
  baseline (0.786). Statistical evidence for improvement is present.
- No gold leakage confirmed by end-to-end leakage checker.
- Inference is CPU-feasible (sentence-transformer + logistic head); no GPU needed for scoring.

### Verifier roles in frontier allocation

1. **Budget filter:** before allocating compute to a reasoning branch, score with the
   verifier. Deprioritize branches with `proba_ready < 0.2` (likely opaque/truncated).
2. **Edge reranker:** among frontier candidates at similar depth/cost, prefer higher
   `proba_ready` — traces that visibly establish the target relation.
3. **Hybrid scoring:** combine frontier confidence with `proba_ready`:
   `hybrid = α × frontier_score + (1−α) × proba_ready`
4. **Diagnostic:** audit which traces the existing selector chose and whether they
   were relation-ready, without changing selection logic.

### Immediate next steps for frontier integration

1. **Locate candidate trace artifacts** — find `per_example_records.jsonl` files with
   `candidate_trace_short` fields. These are the inputs the verifier needs.
2. **Write offline scorer** — `scripts/score_verifier_on_frontier_candidates.py`:
   loads cfg1 model from saved checkpoint, scores candidate traces without any API calls,
   saves scored output to `outputs/verifier_scored_candidates_<STAMP>/`.
3. **Dry-run validation** — compare `proba_ready` scores to `is_correct_offline_metadata`
   (metadata only; never a model input) to sanity-check alignment.
4. **Policy comparison** — evaluate budgeted accuracy curves for:
   - Baseline selector (no verifier)
   - External l1-max frontier policy
   - Verifier-guided selection
   - Hybrid score policy
5. **Repeat Cohere comparison** with cached/replayed outputs for paper-strength claims.

### Guardrails (carry forward from verifier project)

- Verifier must never see `gold_answer_metadata_only` or `is_correct_offline_metadata`.
- Use cached replay; avoid live provider calls for frontier comparisons.
- Do not mix Cohere / Azure / OpenAI runs in the same comparison table.
- All long-running jobs (fine-tuning, large batch scoring) must run in tmux.

### Frontier-allocation validation update (Tasks G/H/I/J/K/M; 2026-05-17)

- **Task G (cross-method policy comparison):** verifier-guided cross-method selection was effectively method-entangled and mostly reproduced `external_l1_max` (72.1% vs 72.2%; chosen `external_l1_max` in 705/720 groups).
- **Task H (within-method reranking, 1440-row artifact):** verifier-max beat random by +9.8pp overall (75.8% vs 66.0%); anti-verifier underperformed (53.8%).
- **Task I (missed-oracle audit):** missed-oracle cases were mostly tiny-margin/low-gap decisions; no large-gap confident verifier failures were found under the configured thresholding.
- **Task J (tie-aware sweep):** no global improvement over baseline verifier top-1; slice-level improvements appeared in selected method/budget slices.
- **Task K (slice-aware constrained policies):** exploratory same-artifact policies showed offline lift (up to +4.17pp), but this is not independent validation.
- **Task M (15-case disjoint sanity validation):** same-sign within-method lift (+3.3pp verifier-max vs random) with tiny spreads; underpowered and non-decisive.
- **Independent/disjoint Cohere multi-seed validation (new, completed):**
  - Generation root: `outputs/within_method_validation_generation_cohere_20260517T100852Z/`
  - Dedup/QA: raw `738` -> dedup `720`, duplicates removed `18` across `5` duplicate keys; duplicates were divergent; raw preserved.
  - Structural validation passed: 60 examples, 2 methods, budget 6, 6 seeds per `(example_id,budget,method)`, trace/final-answer metadata present, disjointness proof overlap count `0`.
  - Scoring: dry-run PASS, full scoring `720` candidates, leakage check PASS.
  - Within-method reranking (`120` groups): verifier-max `0.8667`, random `0.8208`, anti-verifier `0.7250`, oracle `0.9583`, lift vs random `+4.58pp`, lift vs anti `+14.17pp`.
  - By method:
    - `direct_reserve_semantic_frontier_v2`: verifier-max `0.8833`, random `0.8389`, anti `0.7333`, lift `+4.44pp`.
    - `external_l1_max`: verifier-max `0.8500`, random `0.8028`, anti `0.7167`, lift `+4.72pp`.
  - Confirmatory uncertainty readout (cluster bootstrap over `example_id`, primary CI):
    - verifier-max `86.67%` [79.17%, 93.33%]
    - random `82.08%` [75.56%, 87.78%]
    - anti-verifier `72.50%` [64.17%, 80.83%]
    - oracle `95.83%` [90.83%, 100.00%]
    - verifier-minus-random `+4.58pp` [+0.28pp, +9.03pp]
    - verifier-minus-anti `+14.17pp` [+6.67pp, +21.67pp]
    - oracle-minus-verifier `+9.17pp` [+4.17pp, +15.00pp]
    - by-method verifier-minus-random:
      - `direct_reserve_semantic_frontier_v2`: `+4.44pp` [-2.22pp, +11.11pp]
      - `external_l1_max`: `+4.72pp` [-1.67pp, +10.83pp]
  - Interpretation: aggregate verifier-vs-random gain is statistically stable (lower CI bound > 0); per-method verifier-vs-random lifts are positive but individually uncertain; cross-method entanglement caveat remains.
  - Frozen Task K transfer run (now completed, no retuning):
    - script: `scripts/apply_frozen_slice_aware_reranking.py` (commit `c30f1575`)
    - output: `outputs/frozen_slice_aware_transfer_new_validation_20260517T152312Z/`
    - policy: `all_positive_net_slices` from frozen `selected_slice_rules.csv`
    - overall: baseline verifier_top1 `0.866667`, frozen policy `0.866667`, delta `+0.000000`
    - recoveries/regressions/net: `3/3/0`; affected groups: `45/120` (37.5%)
    - matched target slice: `external_l1_max@6` only
    - unmatched target slice: `direct_reserve_semantic_frontier_v2@6`
    - interpretation: neutral/inconclusive; no improvement over verifier_top1 on this independent artifact.

See `docs/FRONTIER_ALLOCATION_VERIFIER_INTEGRATION_STATUS_20260517.md` for a compact handoff summary.
