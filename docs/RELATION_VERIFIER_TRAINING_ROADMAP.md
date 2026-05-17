# RelationReady Verifier — Training Roadmap

**Status as of 2026-05-17 (verifier phase closed for this stage; frontier-allocation validation active)**

This document specifies the planned training progression for the RelationReady binary
classifier (ready / not_ready). It is a planning document, not a training script.

---

## 1. Current Training Status

Prerequisites are satisfied and core verifier training is complete enough for the
current stage, and verifier training is now treated as phase-closed unless reopen
criteria are met (see `docs/RELATION_VERIFIER_PHASE_CLOSURE_20260517.md`):

| Label | Count (current dataset) |
|---|---|
| ready | 93 |
| not_ready | 287 |
| **Total** | **380** |

The positive-candidate batch (100 rows, ready=83, not_ready=17) has been fully labeled
(human-reviewed; Azure `gpt-5.4` used only for hard adjudication) and merged into the
combined training dataset at
`outputs/relation_verifier_training_dataset_combined_33plus250plus100_20260516T221311Z/`.

### Completed training runs (as of 2026-05-17)

| Model | ready F1 | PR-AUC | Output dir |
|---|---|---|---|
| TF-IDF + LogReg (balanced, grouped 5-fold) | 0.710 | 0.808 | `relation_verifier_baseline_combined380_grouped_threshold_train_20260516T222426Z` |
| Frozen mpnet + SVM (balanced, grouped 5-fold) | 0.786 | 0.844 | `relation_verifier_embedding_mpnet_svm_grouped_20260516T230932Z` |
| SetFit mpnet — first run (e1 i10) | 0.857 | 0.866 | `relation_verifier_setfit_mpnet_train_20260516T233217Z` |
| **SetFit tuning cfg1 (e1 i20) — selected** | **0.865** | **0.890** | `relation_verifier_setfit_tuning_20260516_20260517T000951Z/cfg1_e1_i20_b16_spl2` |

SetFit tuning study (cfg0–cfg5) is complete; cfg1 is selected for downstream use.
Verified OOF metrics from `predictions.jsonl` are ready F1=0.8646 and PR-AUC=0.883.

### Training decision status

- Verifier is accepted for frontier-allocation integration.
- ModernBERT/DeBERTa remains optional, only if integration diagnostics show systematic long-trace failures.
- Additional labeling (`ready_candidate_batch.csv`) is optional and not a blocker.

---

## 2. Baseline Suite (Paper-ready)

### 2a. TF-IDF + Logistic Regression

```
Input:  candidate_trace_short  (+ optionally question + candidate_answer)
Model:  TfidfVectorizer(ngram_range=(1, 2), max_features=50000)
        + LogisticRegression(class_weight='balanced', C=1.0, max_iter=1000)
Tuning: threshold on validation fold (not test) to maximise ready F1
```

- Use `class_weight='balanced'` to compensate for 30:1 imbalance.
- Report threshold at which precision and recall cross on the validation PR curve.

### 2b. TF-IDF + Linear SVM

```
Input:  candidate_trace_short  (+ optionally question + candidate_answer)
Model:  TfidfVectorizer(ngram_range=(1, 2), max_features=50000)
        + LinearSVC(class_weight='balanced', C=0.1)
        Calibrated via CalibratedClassifierCV for probability output.
```

- LinearSVM often outperforms LR on sparse text features.
- Calibrate for PR-AUC reporting.

### 2c. Shared evaluation for sklearn baselines

Metrics to report for every baseline:

| Metric | Note |
|---|---|
| Ready precision / recall / F1 | Primary metric |
| Not-ready precision / recall / F1 | Secondary |
| Macro F1 | For overall balance |
| PR-AUC (ready class) | Threshold-independent |
| Confusion matrix | For error analysis |

**Threshold tuning:** sweep decision threshold on training/validation splits only.
Never tune on the test set.

---

## 3. Embedding Baselines

Frozen sentence-transformer embeddings replace TF-IDF; the classifier head is
unchanged (LogisticRegression or SVM).

### Candidate embedding models

| Model | Dim | Notes |
|---|---|---|
| `all-MiniLM-L6-v2` | 384 | Fast; good starting point |
| `all-mpnet-base-v2` | 768 | Higher quality; ~2× slower |
| ModernBERT embedding model | TBD | Use if available in the environment |

### Input construction

```python
text = f"question: {question}\ntrace: {candidate_trace_short}"
embedding = model.encode(text, normalize_embeddings=True)
```

**Hard constraint:** No gold fields (`is_correct_offline_metadata`, manual labels,
`gold_answer_metadata_only`) may appear in the input text or as model features at
any point.

### Classifier heads on top of frozen embeddings

- `LogisticRegression(class_weight='balanced')`
- `LinearSVC(class_weight='balanced')`

Embed once, persist embeddings to disk, sweep classifiers.

---

## 4. First Serious Model — SetFit-style Sentence-Transformer Classifier

### Why SetFit is appropriate here

- **Small labeled data:** SetFit was designed for few-shot regimes (8–64 labeled
  examples per class). After merging the positive-candidate batch we expect roughly
  50–80 ready and ~270 not_ready — exactly this regime.
- **No full fine-tuning required:** The sentence transformer is fine-tuned with
  contrastive pairs on the small labeled set, then a lightweight classifier head
  (logistic regression) is trained on the resulting embeddings. This avoids
  catastrophic forgetting from a full BERT-style fine-tune on <100 samples.
- **Strong inductive bias:** Pre-trained sentence transformers already encode
  semantic similarity; contrastive fine-tuning pulls ready traces closer and
  not_ready traces apart without needing thousands of labels.

### Training procedure

1. **Build contrastive pairs** from the labeled training fold:
   - Positive pairs: (ready trace A, ready trace B)
   - Negative pairs: (ready trace, not_ready trace)
   - Ratio: ~1:3 positive:negative to reflect dataset imbalance.
2. **Fine-tune the sentence transformer** with a contrastive or CoSENT loss
   for a small number of steps (e.g. 1–3 epochs on the pair set).
3. **Encode all training examples** with the fine-tuned model.
4. **Train a logistic regression head** on the embeddings using
   `class_weight='balanced'`.
5. **Evaluate** with grouped CV (see Section 7).

### Recommended starting point

```
Base model:  sentence-transformers/all-MiniLM-L6-v2
             or sentence-transformers/all-mpnet-base-v2
Library:     setfit (pip install setfit)
             or manual contrastive loop with sentence-transformers
```

---

## 5. Secondary Models (after baselines are informative)

These require more data and compute. Only attempt after:
- sklearn and SetFit baselines are tuned and evaluated.
- Dataset has ≥ 100 ready examples.
- GPU is confirmed available (`nvidia-smi`).

### 5a. ModernBERT-base sequence classifier

```
Base:        answerdotai/ModernBERT-base
Head:        linear(hidden_size, 2)
Loss:        CrossEntropy with class_weight
Fine-tune:   full model, low LR (1e-5 to 3e-5)
```

ModernBERT uses an efficient attention implementation and handles long traces
better than BERT-base. Good candidate if traces are frequently >512 tokens.

### 5b. DeBERTa-v3-base sequence classifier

```
Base:        microsoft/deberta-v3-base
Head:        linear(hidden_size, 2)
Loss:        CrossEntropy with class_weight
Fine-tune:   full model, LR 1e-5, warmup 10%
```

DeBERTa-v3 typically outperforms BERT-base and RoBERTa on classification tasks.
Use if compute budget allows.

---

## 6. Class Imbalance Plan

| Technique | Where applied | Notes |
|---|---|---|
| `class_weight='balanced'` | All models | Primary correction; always on |
| Positive oversampling (SMOTE / duplication) | Inside training fold only | Never applied to validation or test |
| Threshold tuning | Validation fold only | Sweep 0.1–0.9, maximise ready F1 |
| PR-AUC reporting | All models | Threshold-independent summary |

**Never resample the validation or test folds.** Resampling validation data produces
optimistically biased estimates of recall and should be treated as a methodological error.

---

## 7. Validation Protocol

### Grouped stratified K-fold

- **Group by `problem_id`:** All traces from the same math problem must be in the
  same fold. A model that memorises problem phrasing rather than trace structure will
  leak across folds if this constraint is violated.
- **Stratified:** Each fold should preserve the ready/not_ready ratio as closely
  as possible given the group constraint.
- **K = 5** for sklearn and embedding baselines; **K = 3** for SetFit and
  transformer models (expensive).

### Feature constraints (hard)

The following fields must **never** appear as model input features at any stage:

- `is_correct_offline_metadata`
- `gold_answer_metadata_only`
- `relation_ready_label_manual` (target only, not feature)
- `first_error_axis_manual`
- `notes_manual`

---

## 8. Resource and Training Policy

### When tmux is required

| Job type | Local shell OK? | tmux required? |
|---|---|---|
| sklearn (TF-IDF, LR, SVM) on ≤ 500 rows | Yes | No |
| Embedding encode on ≤ 500 rows (no GPU) | Yes | No |
| SetFit fine-tuning | No | **Yes** |
| Any transformer fine-tuning | No | **Yes** |
| Any job expected to take > 2 minutes | No | **Yes** |

### Pre-flight checks before any GPU/large job

Run these before starting training; include output in the commit message or
run log:

```bash
free -h          # confirm available RAM
nproc            # CPU cores
nvidia-smi       # GPU availability and VRAM
df -h .          # disk space in repo
```

### Output directory policy

- Every training run writes to a timestamped `outputs/<run_name>_<STAMP>/` directory.
- Do **not** stage or commit output directories.
- Do **not** delete output directories without explicit instruction.
- The command used to launch the run and the output directory path must be
  recorded in the run log or reported before the job starts.

---

## 9. Immediate Next Steps

Steps 1–6 below are **complete**. Remaining work starts at step 7.

1. ~~Finish labeling rows 50–99~~ — **Done.** All 100 positive-candidate rows labeled.
2. ~~Merge positive-candidate labels~~ — **Done.** Combined dataset: 380 rows, ready=93.
3. ~~Implement imbalance-aware sklearn trainer~~ — **Done.** `--class-weight balanced` + `--threshold-sweep` implemented.
4. ~~Run sklearn baselines~~ — **Done.** TF-IDF LogReg: ready F1=0.710, PR-AUC=0.808.
5. ~~Run embedding baselines~~ — **Done.** Frozen mpnet SVM: ready F1=0.786, PR-AUC=0.844.
6. ~~First SetFit run~~ — **Done.** SetFit mpnet e1 i10: ready F1=0.857, PR-AUC=0.866.

7. ~~Wait for SetFit tuning to complete~~ — **Done.** Finished 2026-05-17T02:13Z.
   cfg5 (batch=32) failed CUDA OOM; cfg0–cfg4 completed successfully.

8. ~~Read tuning results~~ — **Done.** cfg1 (e1 i20 b16 spl2) selected as best config.
   ready F1=0.865, PR-AUC=0.890 at default threshold=0.5.

9. ~~**Decide on ModernBERT/DeBERTa**~~ — **Deferred; verifier declared ready (2026-05-17).**
   SetFit cfg1 verified metrics: ready F1=0.8646, PR-AUC=0.883, group-bootstrap CI
   ready F1 [0.8045, 0.9140]. CI lower bound exceeds frozen-mpnet SVM (0.786).
   ModernBERT/DeBERTa only needed if integration experiments reveal systematic failure
   on long traces (>512 tokens). Not blocking frontier integration.

10. ~~**Add confidence intervals / per-fold reporting**~~ — **Done (2026-05-17).**
    `scripts/analyze_relation_verifier_predictions.py` added; 1000-rep bootstrap on cfg1
    OOF predictions. Ready F1=0.8646 [0.8095, 0.9111] (example CI); both CI lower bounds
    exceed frozen-mpnet SVM baseline. Per-fold F1: mean=0.867, std=0.050. See MODEL_CARD §8a.

11. ~~**Run held-out split sanity check**~~ — **Done (2026-05-17).**
    `--eval-split-mode explicit` added to trainer; test set has 0 ready examples (not
    diagnostic for ready F1), but confirmed the code path works end-to-end.

12. **Optionally label `ready_candidate_batch.csv`** (50 rows, currently unlabeled) —
    adds ~50 more ready examples if more data is needed for the transformer baseline or
    to push past F1=0.87.

13. **Integration — ACTIVE NEXT STEP.** Verifier accepted (2026-05-17). Transition to
    frontier allocation pipeline:
    - Score existing `per_example_records.jsonl` candidate traces with cfg1 verifier
      (offline, no API calls).
    - Write `scripts/score_verifier_on_frontier_candidates.py` for offline dry-run.
    - Compare allocation policies (baseline, frontier, verifier-guided, hybrid) on
      budgeted accuracy curves.
    - See `docs/RELATION_VERIFIER_PROJECT_STATUS.md §11` for full transition plan.

14. ~~**Independent uncertainty analysis for within-method reranking**~~ — **Done (2026-05-17).**
    `scripts/analyze_within_method_reranking_uncertainty.py` added with tests, and run on
    `outputs/within_method_reranking_new_multiseed_validation_20260517T144336Z/`.
    Primary cluster-bootstrap CI (over `example_id`) for verifier-minus-random is
    `+4.58pp` `[+0.28pp, +9.03pp]` overall; by-method lifts are positive but individually
    uncertain (method-level CIs cross 0).

15. ~~**Reusable frozen slice-aware transfer script (Task K)**~~ — **Done (2026-05-17).**
    `scripts/apply_frozen_slice_aware_reranking.py` added with tests and run on
    independent validation using frozen `all_positive_net_slices` rules:
    baseline verifier_top1 `0.866667` vs frozen `0.866667` (delta `+0.000000`),
    recoveries/regressions/net `3/3/0`, affected `45/120` groups.
    Interpretation: neutral/inconclusive for gain beyond verifier_top1 on this target.

16. ~~**Wire hardened disjointness extraction into Cohere validation preflight**~~ —
    **Done (2026-05-17, commit `c13c0256`).**
    `scripts/run_cohere_real_model_cost_normalized_validation.py` now supports
    repeatable `--disjointness-prior-jsonl`, optional labels/proof output, and
    default fail-on-overlap behavior using schema-robust extraction logic.

---

## 10. Reference: Current Dataset Counts (2026-05-16, updated)

| Source | ready | not_ready | Total |
|---|---|---|---|
| Seed dataset (33 rows) | ~8 | ~25 | 33 |
| Expansion pool (250 rows) | 5 | 245 | 250 |
| Positive-candidate batch (100 rows) | 83 | 17 | 100 |
| **Combined (active dataset)** | **93** | **287** | **380** |
| Ready-candidate batch (unlabeled) | TBD | 0 | 50 |

Realistic minimum for meaningful SetFit: **≥ 40 ready examples** — satisfied (93 ready).
Realistic minimum for fine-tuned transformer: **≥ 100 ready examples** — borderline; labeling
the ready-candidate batch would bring the total to ~143 ready if needed.

---

## 11. Frontier-Allocation Integration Status (2026-05-17)

Training is no longer the bottleneck. Current integration findings:

1. Cross-method verifier-guided selection is method-entangled and mostly reproduces
   `external_l1_max`; raw cross-method `proba_ready` is not reliable as a global chooser.
2. Within-method reranking shows useful signal on the 1440-row cached artifact
   (verifier-max > random by +9.8pp).
3. Tie-aware and slice-aware rule gains are exploratory because selection and evaluation
   were on the same artifact.
4. A small disjoint 15-case validation is same-sign but underpowered.
5. Independent/disjoint Cohere multi-seed validation is now complete:
   - raw `738` -> dedup `720` (`18` duplicates removed across `5` duplicate keys; divergent duplicates, raw preserved)
   - structural validation PASS (60 examples, 2 methods, budget 6, 6 seeds/group, trace/final-answer metadata present, disjointness overlap count 0)
   - scoring dry-run PASS and full scoring on 720 candidates; leakage check PASS
   - within-method reranking (120 groups): verifier-max `0.8667`, random `0.8208`, anti `0.7250`, oracle `0.9583`, lift vs random `+4.58pp`
   - by method lift vs random: +4.44pp (`direct_reserve_semantic_frontier_v2`), +4.72pp (`external_l1_max`)

Current recommended work split:
- Independent validation is complete and positive for within-method reranking directionality.
- Uncertainty reporting is complete; use cluster-bootstrap CI as primary readout in summaries.
- Frozen-policy transfer script is complete; current independent transfer is neutral/inconclusive due to limited slice overlap.
- Prepare paper-ready writeup/results text that separates:
  verified verifier_top1-vs-random gains vs neutral slice-aware transfer outcome.
- Optional: run another independent artifact with budget-4/8 slice coverage before revisiting frozen Task K rules.
- Keep cross-method method-entanglement caveat explicit; validated claim scope remains within-method reranking.

### 11a. Budget-4/8 Audit Correction (2026-05-17)

- A completed budget-4/8 artifact was audited and found overlap-contaminated
  (40 overlapping IDs with prior 40-example scored source), so it is not independent evidence.
- Preflight disjointness parsing bug identified: prior scored artifacts required
  `metadata.example_id` and structured `feature_text`/metadata question extraction.
- Non-overlap filtered subset (`20` examples) remains useful as diagnostic follow-up but
  is too small to upgrade claims; overall lift uncertainty crosses zero.
- Frozen slice-aware transfer remains non-promotable (negative/neutral overall).
