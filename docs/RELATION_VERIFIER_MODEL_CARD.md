# RelationReady Verifier — Model / Experiment Card

**Created:** 2026-05-16  
**Branch:** `feat/missing-gold-topology-v1`  
**Status:** SetFit hyperparameter tuning complete (cfg0–cfg4 done; cfg5 failed OOM). Best config identified.

---

## 1. Purpose

The RelationReady verifier predicts whether a candidate answer together with a visible
reasoning trace establishes the problem's target computational relation for a math word
problem.

- **Binary labels:** `ready` (1) / `not_ready` (0)
- **Intended use:** Offline verifier / research component for frontier-model allocation
  under inference budget constraints. Not deployed for live inference yet.
- **Not in scope:** Judging numerical correctness alone, or ranking traces by quality.
  The verifier is a binary gate: does the trace show its work in a relation-establishing way?

---

## 2. Label Definition

### `ready` (1)
The trace and answer together establish the problem's target relation through visible
reasoning or code. Requirements:
- All required intermediate quantities are derived (not just asserted).
- The answer is correct and follows from the visible derivation.
- The reader can follow the chain from source facts to final answer without inference gaps.

Trivial final aggregation is accepted when all operands are visible in the trace
(e.g., `A=12, B=7, answer=A+B`). PAL/code traces qualify if the operations bind
problem variables and establish the target relation.

### `not_ready` (0)
Anything that fails the above. Specific failure modes:
- Final-answer-only or opaque trace (no visible derivation)
- Missing source fact (required input value never established)
- Missing target relation (intermediate relation step skipped)
- Wrong variable binding (value computed but assigned to wrong variable)
- Process-state error (formula requires a prior process the trace omits or misorients)
- Unit or scale error (dimensional mismatch in the derivation)
- Arithmetic or process failure (derivation shown but incorrect)
- Incomplete trace (truncated before the key step)

### Excluded from training
- `uncertain` — annotator could not determine label with confidence
- `gold_inconsistent` — trace answer inconsistent with gold answer in a way that makes
  the label ambiguous; excluded to avoid signal noise

---

## 3. Data Sources and Labels

All label CSVs are local-only outputs and are not committed to git.

### Seed dataset — 33 rows
- File: `outputs/relation_verifier_seed_smoke_20260513T032059Z/manual_audit_33rows.csv`
- Labels: ready=5, not_ready=25, uncertain=3
- Source: manually annotated from scratch

### Expansion pool — 250 rows
- File: `outputs/relation_verifier_training_pool_expansion_20260515T050603Z/manual_audit_batch.csv`
- Labels: ready=5, not_ready=245
- Source: `build_relation_verifier_training_pool.py`; 175 opaque rows bulk-labeled
  `not_ready` in a cleaning pass

### Positive candidate batch — 100 rows
- File: `outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/positive_candidate_batch.csv`
- Labels: ready=83, not_ready=17
- Source: `per_example_records.jsonl` files, filtered on `exact_match=True`, non-opaque traces
- Rows 0–49: manually labeled
- Rows 50–99: Azure `gpt-4.1-mini` first pass + Azure `gpt-5.4` strong adjudication for
  flagged hard cases + human acceptance before patching

### Combined training dataset (current)
- Dir: `outputs/relation_verifier_training_dataset_combined_33plus250plus100_20260516T221311Z/`
- Input rows: 383 total; 3 uncertain excluded
- **Included: 380 rows — ready=93, not_ready=287** (~3:1 imbalance)

---

## 4. Labeling Process

- **Human/manual labels are the final supervision signal** — no automated label enters
  training without explicit human acceptance.
- Azure `gpt-4.1-mini` was used as a preliminary first-pass labeler to reduce human
  review effort for rows 50–99 of the positive-candidate batch.
- Azure `gpt-5.4` was used as a strong adjudicator for hard disagreement cases only —
  not as automatic ground truth.
- All model-suggested labels required explicit human review and acceptance before being
  patched into the label CSV. Any change is recorded in `notes_manual`.
- Gold answer metadata was never used in any provider prompt or as a model input feature.

---

## 5. Feature Construction and Leakage Policy

### Included in `feature_text`
- Problem text (question)
- Candidate answer
- Visible reasoning trace / code (`candidate_trace_short`)
- Safe metadata if applicable (e.g., trace source type)

### Strictly excluded from `feature_text` and model inputs
- `gold_answer_metadata_only` — offline audit metadata only
- `is_correct_offline_metadata` — correctness flag; metadata, not a feature
- `relation_ready_label_manual` — the target label itself
- `first_error_axis_manual` — debug annotation metadata
- `notes_manual` — annotator notes

The dataset builder runs a leakage check to confirm none of these appear in the
constructed feature text. No gold answers appear in any provider prompt or model feature
at any stage.

---

## 6. Evaluation Protocol

### Cross-validation
- `StratifiedGroupKFold` with **K=5**, grouped by `problem_id`.
- All traces from the same math problem are assigned to the same fold to prevent
  problem-level memorization from leaking across train/val.
- Each fold preserves the ready/not_ready ratio as closely as the group constraint allows.

### Metrics reported per model
| Metric | Role |
|---|---|
| ready precision / recall / F1 | Primary metric — target class performance |
| macro F1 | Overall balance across both classes |
| PR-AUC (ready class) | Threshold-independent summary |
| Accuracy | Sanity check |
| Confusion matrix (OOF) | Error analysis |

### Threshold sweep
- Threshold sweep over OOF predictions is provided as a **diagnostic** tool.
- Threshold sweep results are optimistically biased (threshold chosen on the same OOF
  data used for evaluation). They are reported for exploration; they are not the primary
  unbiased estimate.
- Primary reported metrics use the default threshold (0.5) unless otherwise noted.

---

## 7. Baseline and Model Leaderboard

All results use grouped 5-fold CV (OOF), `StratifiedGroupKFold(n_splits=5, group_field='problem_id')`,
on the 380-row combined dataset.

| System | ready F1 | PR-AUC | Macro F1 | Notes |
|---|---|---|---|---|
| TF-IDF + LogReg (`class_weight=balanced`) | 0.710 | 0.808 | 0.806 | sklearn baseline |
| Frozen all-MiniLM-L6-v2 + LinearSVC | 0.615 | 0.657 | — | weak embedding baseline |
| Frozen all-mpnet-base-v2 + LinearSVC | 0.786 | 0.844 | 0.854 | strong embedding baseline |
| SetFit all-mpnet-base-v2, first run (e1 i10 b16 spl2) | 0.857 | 0.866 | 0.905 | full fine-tune, default thr |
| **SetFit cfg1: e1 i20 b16 spl2** | **0.865** | **0.890** | **0.909** | **tuning winner — best PR-AUC** |
| SetFit cfg3: e2 i20 b16 spl2 | 0.868 | 0.860 | 0.912 | best accuracy/macro F1; lower PR-AUC |
| SetFit cfg4: e1 i10 b16 spl4 | 0.859 | 0.861 | 0.907 | 4 samples/label; marginal gain |
| SetFit cfg0: e1 i10 b16 spl2 | 0.831 | 0.852 | 0.886 | baseline config |
| SetFit cfg2: e2 i10 b16 spl2 | 0.825 | 0.838 | 0.882 | extra epoch hurts; overfitting |
| SetFit cfg5: e1 i10 b32 spl2 | **FAILED** | OOM | — | CUDA out of memory; batch=32 too large |

**Tuning takeaways:**
- More contrastive iterations (i10→i20) consistently improves PR-AUC (+0.024 in cfg1 vs cfg0).
- More epochs (e1→e2) does not help and slightly hurts PR-AUC — consistent with
  contrastive overfitting at this dataset size.
- More samples-per-label (spl2→spl4) gives a small gain with minimal cost.
- Batch size 32 exceeds available VRAM on the RTX 5060 Ti (16 GiB) at this model size.

---

## 8. Current Trained Model Candidates

| Role | Model |
|---|---|
| **Best completed model** | SetFit `all-mpnet-base-v2`, cfg1 (e1 i20 b16 spl2) |
| Baseline to beat | Frozen `all-mpnet-base-v2` + LinearSVC (ready F1=0.786) |
| Tuning objective | ✅ Achieved — stable SetFit config identified |
| Next decision gate | Is ready F1≥0.87 sufficient for integration, or is more data/bigger model needed? |

Output dirs for trained models:
- First SetFit run: `outputs/relation_verifier_setfit_mpnet_train_20260516T233217Z/`
- Tuning study: `outputs/relation_verifier_setfit_tuning_20260516_20260517T000951Z/`
- Best config subdir: `.../cfg1_e1_i20_b16_spl2/`

---

## 9. Model References

The following references support the model choices. Full BibTeX should be added at
paper-writing time.

- **SetFit:** Tunstall et al., "Efficient Few-Shot Learning Without Prompts," arXiv:2209.11055.
  Motivation: designed for few-shot regimes (8–64 labeled examples/class); contrastive
  fine-tuning + lightweight head avoids catastrophic forgetting on <100 samples.
- **Sentence-BERT / sentence-transformers:** Reimers & Gurevych, "Sentence-BERT:
  Sentence Embeddings using Siamese BERT-Networks," EMNLP 2019.
- **all-mpnet-base-v2 model card:** sentence-transformers HuggingFace model card.
  768-dim embeddings; strong semantic similarity performance.
- **scikit-learn:** Pedregosa et al., JMLR 2011. Used for LogisticRegression and
  LinearSVC baselines.
- **DeBERTa-v3:** He et al., "DeBERTaV3: Improving DeBERTa using ELECTRA-Style
  Pre-Training with Gradient-Disentangled Embedding Sharing." Possible future encoder
  baseline if SetFit results are insufficient.
- **ModernBERT:** Answer.AI / LightOn ModernBERT paper and model card. Possible future
  long-context / code-aware encoder baseline, especially if traces are frequently >512 tokens.

---

## 10. Known Limitations

- **Small dataset:** 380 included rows; 93 ready examples. Confidence intervals not yet
  computed. Paper-strength claims require bootstrap CIs or repeated CV.
- **Model-assisted labels:** rows 50–99 of the positive batch are Azure-assisted
  (human-accepted). These labels carry more uncertainty than fully manual annotations.
- **Positive-candidate bias:** the positive batch was mined from `exact_match=True`
  traces, which biases it toward traces that are structurally similar to the seed.
  Out-of-distribution trace types may not be represented.
- **Grouped CV reduces but does not eliminate leakage:** problem-level grouping handles
  phrase memorization, but semantic overlap between problems is uncontrolled.
- **OOF threshold sweep is optimistically biased:** best-threshold metrics in `metrics.json`
  are for exploration only, not for unbiased reporting.
- **No independent held-out test set:** all evaluation is cross-validated OOF.
  A locked-out test set would provide a stronger unbiased estimate.
- **cfg5 (batch=32) failed OOM:** the RTX 5060 Ti (16 GiB) cannot run batch=32 for
  `all-mpnet-base-v2` within the SetFit contrastive training loop at this sequence length.

---

## 11. Immediate Next Steps

1. Decide whether to proceed with integration using cfg1 (ready F1=0.865, PR-AUC=0.890)
   or to collect more data first.
   - Decision rule: if F1 ≥ 0.87 → integrate; otherwise label `ready_candidate_batch.csv`
     (50 rows, unlabeled) to add more positive examples.
2. Add per-fold variance and confidence intervals to the evaluation script.
3. Prepare paper table with all baselines and the chosen SetFit config.
4. Only consider ModernBERT / DeBERTa fine-tuning if SetFit results are judged
   insufficient or if longer traces require larger context windows.
5. Run chosen verifier on held-out candidate traces to score relation-readiness.
6. Wire verifier score into the selector / budget-allocation policy.
