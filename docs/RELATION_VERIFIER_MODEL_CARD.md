# RelationReady Verifier — Model / Experiment Card

**Created:** 2026-05-16  
**Branch:** `feat/missing-gold-topology-v1`  
**Status:** ✅ SetFit tuning complete. CI analysis complete. Transitioning to frontier-allocation integration.  
**Selected config: cfg1 (e1/i20/b16/spl2) — ready F1=0.8646, PR-AUC=0.883 (verified from OOF predictions).**  
**Group-bootstrap 95% CI: ready F1 [0.8045, 0.9140]; PR-AUC [0.8027, 0.9467].**

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
on the 380-row combined dataset. Primary metrics at default threshold=0.5.

### 7a. Full system comparison

| System | ready F1 | PR-AUC | Macro F1 | Notes |
|---|---|---|---|---|
| TF-IDF + LogReg (`class_weight=balanced`) | 0.710 | 0.808 | 0.806 | sklearn baseline |
| Frozen all-MiniLM-L6-v2 + LinearSVC | 0.615 | 0.657 | — | weak embedding baseline |
| Frozen all-mpnet-base-v2 + LinearSVC | 0.786 | 0.844 | 0.854 | strong embedding baseline |
| SetFit all-mpnet-base-v2, first run (e1 i10 b16 spl2) | 0.857 | 0.866 | 0.905 | pre-tuning run |
| **SetFit cfg1: e1 i20 b16 spl2 ← selected** | **0.8646** | **0.883**† | **0.909** | **tuning winner; group CI: F1 [0.8045, 0.9140]** |
| SetFit cfg3: e2 i20 b16 spl2 | 0.868 | 0.860 | 0.912 | higher F1, worse PR-AUC |
| SetFit cfg4: e1 i10 b16 spl4 | 0.859 | 0.861 | 0.907 | spl=4; marginal gain over cfg0 |
| SetFit cfg0: e1 i10 b16 spl2 | 0.831 | 0.852 | 0.886 | baseline config |
| SetFit cfg2: e2 i10 b16 spl2 | 0.825 | 0.838 | 0.882 | extra epoch hurts |
| SetFit cfg5: e1 i10 b32 spl2 | FAILED | — | — | CUDA OOM; batch=32 > VRAM limit |

### 7b. Full tuning config detail table

| Config | E | I | B | SPL | Acc | Macro F1 | ready P | ready R | ready F1 | PR-AUC | TN | FP | FN | TP | Best thr | Best F1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cfg0 (baseline) | 1 | 10 | 16 | 2 | 0.913 | 0.886 | 0.794 | 0.871 | 0.831 | 0.852 | 266 | 21 | 12 | 81 | 0.70 | 0.840 |
| **cfg1 ← selected** | **1** | **20** | **16** | **2** | **0.932** | **0.909** | **0.838** | **0.892** | **0.865** | **0.890** | 271 | 16 | 10 | 83 | 0.95 | **0.877** |
| cfg2 | 2 | 10 | 16 | 2 | 0.911 | 0.882 | 0.792 | 0.860 | 0.825 | 0.838 | 266 | 21 | 13 | 80 | 0.95 | 0.840 |
| cfg3 | 2 | 20 | 16 | 2 | 0.934 | 0.912 | 0.854 | 0.882 | 0.868 | 0.860 | 273 | 14 | 11 | 82 | 0.90 | 0.872 |
| cfg4 | 1 | 10 | 16 | 4 | 0.932 | 0.907 | 0.868 | 0.849 | 0.859 | 0.861 | 275 | 12 | 14 | 79 | 0.25 | 0.866 |
| cfg5 | 1 | 10 | 32 | 2 | — | — | — | — | — | — | — | — | — | — | — | OOM |

*E=epochs, I=contrastive iterations, B=batch size, SPL=samples per label.*  
*Best thr = diagnostic threshold sweep on OOF predictions (optimistically biased; not for paper claims).*  
*†cfg1 PR-AUC: the tuning wrapper reported 0.890; direct computation from predictions.jsonl gives 0.883. Use 0.883 for paper reporting.*

### 7c. Tuning takeaways

- **More iterations helped** (i10→i20): cfg1 vs cfg0 gains +0.034 ready F1 and +0.038 PR-AUC. Consistent finding.
- **More epochs hurt** (e1→e2): PR-AUC drops in both comparisons (cfg0→cfg2: −0.014; cfg1→cfg3: −0.030). Consistent with contrastive overfitting when the pair pool is exhausted at this dataset size.
- **More samples-per-label helped marginally** (spl2→spl4): cfg4 vs cfg0 gains +0.028 ready F1, but cfg1 (i20) still dominates cfg4 on PR-AUC.
- **Batch=32 failed OOM**: RTX 5060 Ti (16 GiB) cannot fit batch=32 for all-mpnet-base-v2 contrastive training. Batch=16 is the safe upper limit.
- **cfg1 is the recommended config**: best PR-AUC (0.890 by tuning wrapper; 0.883 verified) and strong ready F1 (0.8646). cfg3 has +0.002 ready F1 at default threshold but sacrifices 0.023 verified PR-AUC — not worth the trade-off.

---

## 8. Selected Model

**SetFit `sentence-transformers/all-mpnet-base-v2`, cfg1**

| Parameter | Value |
|---|---|
| epochs | 1 |
| contrastive iterations | 20 |
| batch size | 16 |
| samples per label | 2 |
| CV protocol | StratifiedGroupKFold(5), grouped by problem_id |
| accuracy | 0.9316 |
| macro F1 | 0.9094 |
| ready precision | 0.8384 |
| ready recall | 0.8925 |
| **ready F1 (thr=0.5)** | **0.8646** |
| **PR-AUC (verified)** | **0.883** |
| confusion matrix (thr=0.5) | TN=271, FP=16, FN=10, TP=83 |
| best diagnostic ready F1 | 0.877 at threshold=0.95 (OOF sweep, optimistically biased) |
| group-bootstrap 95% CI (ready F1) | [0.8045, 0.9140] |
| group-bootstrap 95% CI (PR-AUC) | [0.8027, 0.9467] |
| per-fold ready F1 | mean=0.867, std=0.050, range [0.791, 0.914] |

**Note on thresholds:** The default threshold (0.5) is the primary reported metric.
The diagnostic sweep (threshold=0.95 yielding F1=0.877) is exploratory — it is chosen on
the same OOF data used for evaluation and is therefore optimistically biased. It should not
be cited as an unbiased estimate until fold-internal threshold selection is implemented.

**Note on paper-strength claims:** All results are OOF cross-validated; no independent
held-out test set with ready examples exists. Bootstrap CIs are now available (see §8a).

Output dirs:
- Tuning study: `outputs/relation_verifier_setfit_tuning_20260516_20260517T000951Z/`
- Selected config subdir: `.../cfg1_e1_i20_b16_spl2/`
- First SetFit run (reference): `outputs/relation_verifier_setfit_mpnet_train_20260516T233217Z/`

---

## 8a. CI Analysis for cfg1 (Verified from OOF Predictions)

**Script:** `scripts/analyze_relation_verifier_predictions.py`  
**Analysis dir:** `outputs/relation_verifier_setfit_cfg1_ci_analysis_20260517T025701Z/`  
**Source:** `cfg1_e1_i20_b16_spl2/predictions.jsonl` joined with `train_rows.jsonl`

### Verified overall metrics (threshold=0.5)

| Metric | Value |
|---|---|
| n | 380 |
| n_ready (true) | 93 |
| Accuracy | 0.9316 |
| Macro F1 | 0.9094 |
| Ready Precision | 0.8384 |
| Ready Recall | 0.8925 |
| **Ready F1** | **0.8646** |
| **PR-AUC** | **0.883** |

> **Note on PR-AUC:** The tuning-study metrics.json reported `pr_auc_ready=0.8902`.
> Direct computation from `predictions.jsonl` (380 OOF scores) gives **0.883**. The
> discrepancy (~0.007) arises from a different internal computation path in the tuning
> wrapper. The verified value 0.883 is used for CI analysis and paper reporting.
>
> **Note on ready F1:** The tuning-study reported 0.865. This is the same value rounded
> to 3 decimal places; exact computation from the confusion matrix (TN=271, FP=16,
> FN=10, TP=83) gives F1 = 2×83/(2×83+16+10) = 0.8646.

### Per-fold metrics (fold assignments reconstructed via StratifiedGroupKFold)

| Fold | N | N Ready | Ready P | Ready R | Ready F1 | PR-AUC |
|---|---|---|---|---|---|---|
| 0 | 77 | 19 | 0.8947 | 0.8947 | 0.8947 | 0.9148 |
| 1 | 77 | 19 | 0.8947 | 0.8947 | 0.8947 | 0.9677 |
| 2 | 75 | 18 | 0.8000 | 0.8889 | 0.8421 | 0.9497 |
| 3 | 75 | 18 | 0.9412 | 0.8889 | 0.9143 | 0.9521 |
| 4 | 76 | 19 | 0.7083 | 0.8947 | 0.7907 | 0.7692 |

Per-fold ready F1: mean=0.8673, std=0.0505, min=0.7907, max=0.9143

Fold 4 is the weakest fold (F1=0.7907, PR-AUC=0.769), pulling the mean below the
OOF global estimate. This fold likely contains harder or more diverse problems.

### 95% bootstrap confidence intervals (n=1000 reps, seed=20260516)

| Bootstrap type | Metric | Point estimate | 95% CI |
|---|---|---|---|
| Example-level | Ready F1 | 0.8646 | [0.8095, 0.9111] |
| Example-level | PR-AUC | 0.883 | [0.811, 0.9476] |
| Group-level (295 groups) | Ready F1 | 0.8646 | [0.8045, 0.9140] |
| Group-level (295 groups) | PR-AUC | 0.883 | [0.8027, 0.9467] |

**Comparison to frozen-mpnet SVM baseline (ready F1=0.786, PR-AUC=0.844):**

- Ready F1: both example- and group-level CI lower bounds (0.8095 / 0.8045) exceed
  the SVM baseline (0.786). The CI provides evidence that SetFit cfg1 beats the
  frozen-embedding baseline on ready F1.
- PR-AUC: CI lower bounds (0.811 / 0.803) are below the SVM PR-AUC baseline (0.844).
  The CIs overlap — dataset too small to claim a definitive PR-AUC improvement.

### Limitations of the CI analysis

- **Small dataset (n=380, n_ready=93):** CIs are wide; reflect resampling variance.
- **OOF only:** No independent held-out test set with ready examples.
- **Example bootstrap ignores group structure:** Likely underestimates variance.
- **Group bootstrap with ~295 groups:** Some bootstrap samples may lack ready examples,
  making PR-AUC undefined in those samples (excluded from CI computation).
- **Threshold is default (0.5):** Not tuned on a held-out val set for this analysis.

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

- **Small dataset:** 380 included rows; 93 ready examples. Bootstrap CIs now computed
  (see §8a); CIs are wide due to small n. Paper-strength claims require an independent
  held-out test set.
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

**Tuning is complete. cfg1 is selected. Next choices (in rough priority order):**

A. ~~**Add confidence intervals / per-fold reporting**~~ — **Done (2026-05-17).**
   Bootstrap CIs computed via `scripts/analyze_relation_verifier_predictions.py`.
   See §8a for verified metrics, per-fold table, and 95% CIs.
   Example CI lower bound (0.8095) and group CI lower bound (0.8045) both exceed
   frozen-mpnet SVM baseline (0.786) on ready F1. PR-AUC CIs overlap with baseline.

B. ~~**Run a held-out split sanity check**~~ — **Done (2026-05-17).**
   `--eval-split-mode explicit` added to trainer; sanity run completed. Test set
   has 0 ready examples, so not meaningful for ready F1 — see §8 output dirs.

C. **Label `ready_candidate_batch.csv`** (50 rows, currently unlabeled) — adds more
   `ready` examples if the current F1=0.865 is judged insufficient for integration.
   This would bring the dataset to ~143 ready examples and may allow ModernBERT/DeBERTa
   fine-tuning to become viable.

D. **ModernBERT / DeBERTa baseline** — only if SetFit is judged insufficient or traces
   are frequently >512 tokens. Requires ≥100 ready examples (borderline now; satisfied
   after option C).

**CI interpretation (2026-05-17):**
- SetFit cfg1 **clearly improves ready F1** over frozen mpnet SVM under grouped-CV
  bootstrap analysis. Group-bootstrap CI lower bound (0.8045) is above the SVM baseline
  (0.786); the improvement is supported by both example-level and group-level bootstrap.
- **PR-AUC improvement is not definitive.** Point estimate (0.883) exceeds SVM (0.844),
  but group-bootstrap CI lower bound (0.8027) is below 0.844. The dataset is too small
  to claim a definitive PR-AUC improvement.
- **Fold 4** is the weakest fold (ready F1=0.7907, PR-AUC=0.769). It contains harder or
  more diverse problems and pulls the mean below ~0.89. This is the main source of variance.

**Integration path — active next step (see §12):**
- Verifier is accepted for integration: ready F1≈0.865, recall≈0.893, no gold leakage.
- Run verifier scoring over cached candidate traces / frontier outputs offline.
- Wire verifier score into frontier edge-selection / budget-allocation policy.
- Compare policies: baseline, frontier, verifier-guided, hybrid.
- See §12 for full transition plan.

C. **Label `ready_candidate_batch.csv`** (50 rows, currently unlabeled) — optional; only
   needed if verifier is judged insufficient after integration experiments.

D. **ModernBERT / DeBERTa baseline** — deferred. SetFit cfg1 is accepted for integration.
   Revisit only if integration experiments reveal systematic failures on long traces (>512 tokens).

---

## 12. Transition to Frontier Allocation

**As of 2026-05-17, the RelationReady verifier is accepted for integration into the
frontier allocation pipeline.** This section describes why, how to use it, and what
the immediate integration experiments should look like.

### Why the verifier is ready

- Ready F1=0.8646 with grouped-CV bootstrap lower bound 0.8045 — above the frozen
  embedding baseline (0.786). Improvement is supported statistically.
- Ready recall=0.8925 — the verifier catches ~89% of traces that actually establish
  the target relation, with a false-positive rate of ~5.6% (FP=16/287).
- No gold leakage: the verifier sees only `question`, `candidate_answer`, and
  `candidate_trace_short`. Gold answers and correctness flags are never model inputs.
- Grouped-CV by `problem_id` prevents phrase-level memorization leakage.
- Model is lightweight (sentence-transformer + logistic-regression head); inference
  is CPU-feasible without GPU for offline scoring.

### How to use the verifier

The verifier assigns a `proba_ready` score ∈ [0, 1] to each (question, trace, answer)
triple. This score can be used in the frontier allocation pipeline as:

1. **Feature in edge/branch scoring:** add `proba_ready` as an additional feature
   alongside existing frontier scores (budget, depth, confidence, etc.).
2. **Candidate reranker:** among candidates that reach a scoring threshold, prefer
   those with higher `proba_ready` to prioritize traces that visibly establish
   the target relation.
3. **Budget filter / prior:** before allocating budget to explore a reasoning branch,
   pre-screen with the verifier. Skip branches where `proba_ready` is very low
   (e.g., < 0.2) — these are likely opaque or final-answer-only traces that won't
   improve answer confidence.
4. **Diagnostic only (no live-loop use):** use verifier scores to audit which traces
   the selector chose and whether they were relation-ready — independent of the
   selection decision.

The verifier is **not** a replacement for final answer checking. It answers a different
question: does this trace visibly establish the computation, not just produce a number.

### Immediate integration experiments (offline, no APIs)

All experiments should use **cached replay** to avoid provider nondeterminism and
API costs. Run verifier scoring over existing `per_example_records.jsonl` artifacts.

1. **Score existing candidate traces** using the trained cfg1 model (or the saved OOF
   predictions as a proxy for the training distribution).
2. **Compare allocation policies** on a fixed-budget accuracy curve:
   - Policy A: existing best / baseline selector (no verifier)
   - Policy B: `external_l1_max` / current frontier policy
   - Policy C: verifier-guided edge selection (select branches with highest `proba_ready`)
   - Policy D: hybrid score = α × frontier_score + (1−α) × proba_ready
3. **Evaluation metric:** budgeted accuracy at fixed inference budgets (e.g., 1×, 2×,
   4× base cost). Plot accuracy-cost curves for each policy.

**Guardrails:**
- Verifier must never see `gold_answer_metadata_only` or `is_correct_offline_metadata`.
- Use cached `per_example_records.jsonl` when possible; avoid live provider calls.
- Never mix Cohere-run outputs with Azure/OpenAI-run outputs in the same comparison table.
- Record which provider's outputs each policy was evaluated on.

### Next concrete step

1. Locate `per_example_records.jsonl` files that contain cached candidate traces with
   `candidate_trace_short` fields that the verifier can score.
2. Write a dry-run scorer (`scripts/score_verifier_on_frontier_candidates.py`):
   - Loads trained cfg1 model weights from
     `outputs/relation_verifier_setfit_tuning_20260516_20260517T000951Z/cfg1_e1_i20_b16_spl2/`
   - Applies verifier to each candidate trace without calling any provider API.
   - Saves scored candidates to `outputs/verifier_scored_candidates_<STAMP>/`.
3. Produce an offline report comparing verifier scores to `is_correct_offline_metadata`
   (metadata only; not used as model input) to validate alignment.
4. Once offline scoring is validated, proceed to policy comparison experiments.

---

## 13. Known Downstream Behavior (2026-05-17)

Findings from offline frontier-allocation analyses indicate that verifier usage must be
method-aware:

- **Cross-method method entanglement:** on a 1440-row, 2-method scored artifact, raw
  `proba_ready` favored `external_l1_max` in 705/720 groups; cross-method
  verifier-guided selection mostly reproduced `external_l1_max`.
- **Within-method ranking signal:** when controlling for method identity
  (`example_id, budget, method` groups), verifier-max beat random seed choice
  (+9.8pp on the 1440-row artifact).
- **Anti-verifier sanity check:** selecting lowest `proba_ready` substantially hurt
  performance, supporting that within-method ordering signal is meaningful.
- **Small disjoint check:** a 15-case disjoint artifact showed same-sign lift
  (+3.3pp) but is underpowered and non-decisive.
- **Independent disjoint validation (new, 720-row dedup artifact):**
  120 groups with verifier-max `0.8667` vs random `0.8208` (+4.58pp),
  anti-verifier `0.7250`, oracle `0.9583`. By method, lift vs random was
  +4.44pp (`direct_reserve_semantic_frontier_v2`) and +4.72pp (`external_l1_max`).
  Confirmatory uncertainty analysis (cluster bootstrap over `example_id`, primary CI)
  gave:
  - verifier-max `86.67%` [79.17%, 93.33%]
  - random `82.08%` [75.56%, 87.78%]
  - anti-verifier `72.50%` [64.17%, 80.83%]
  - oracle `95.83%` [90.83%, 100.00%]
  - verifier-minus-random `+4.58pp` [+0.28pp, +9.03pp]
  - verifier-minus-anti `+14.17pp` [+6.67pp, +21.67pp]
  - oracle-minus-verifier `+9.17pp` [+4.17pp, +15.00pp]
  By-method verifier-minus-random remained positive but individually uncertain:
  +4.44pp [-2.22pp, +11.11pp] for `direct_reserve_semantic_frontier_v2`,
  +4.72pp [-1.67pp, +10.83pp] for `external_l1_max`.
  This provides the strongest current evidence for within-method reranking on disjoint data,
  while preserving the method-entanglement caveat for cross-method selection.
- **Frozen slice-aware transfer on independent validation (new):**
  reusable transfer was implemented (`scripts/apply_frozen_slice_aware_reranking.py`)
  and run with frozen `all_positive_net_slices` rules (no retuning):
  baseline verifier_top1 `0.866667` vs frozen policy `0.866667` (delta `+0.000000`),
  recoveries/regressions `3/3` (net `0`), affected groups `45/120`.
  This is neutral/inconclusive for improvement beyond verifier_top1 on this target.
  Major limitation: slice overlap was narrow (`external_l1_max@6` matched; most frozen
  rules were for budgets 4/8 while target slices were budget 6).
- **Dedup/QA note for the independent artifact:** raw `738` -> dedup `720`;
  duplicates removed `18` across `5` duplicate keys; duplicate payloads were divergent
  (raw file preserved); scoring leakage check remained PASS.

Operational guidance:

1. Do **not** use raw cross-method `proba_ready` as a naive global selector.
2. Prefer within-method reranking/normalization. This has now been independently
   validated on a disjoint 720-row Cohere artifact, with positive lift for both methods.
3. Treat slice-aware/tie-aware policy gains as exploratory for promotion; current
   frozen transfer on independent data is neutral/inconclusive.
4. Keep claim scope explicit: validated claim is within-method seed reranking,
   not naive cross-method verifier-guided selection.
