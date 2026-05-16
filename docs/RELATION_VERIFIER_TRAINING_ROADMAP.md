# RelationReady Verifier — Training Roadmap

**Status as of 2026-05-16**

This document specifies the planned training progression for the RelationReady binary
classifier (ready / not_ready). It is a planning document, not a training script.
No training should be started until the prerequisites in Section 1 are satisfied.

---

## 1. Current Training Bottleneck

The current combined training dataset has a severe class imbalance:

| Label | Count |
|---|---|
| ready | ~10 |
| not_ready | ~270 |

As a result, any model trained on this data produces **ready-class F1 ≈ 0.00** — the
classifier learns to predict not_ready for everything and still achieves high accuracy.

**Root cause:** The original training pool was built from incorrect-answer traces; very
few correct-structure traces were included. The positive-candidate batch (rows 0–99 from
`outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/`) adds dozens of
`ready` examples, but those labels must be merged before training.

### Prerequisites before any model training

1. Finish labeling rows 50–99 (Azure-assisted + human review).
2. Merge all labeled positive-candidate rows into the combined training CSV.
3. Verify the merged dataset has at least ~40–50 ready examples (minimum for
   meaningful cross-validation).
4. Confirm no gold fields (`is_correct_offline_metadata`) appear as model features.

**Do not start serious training until these steps are complete.**

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

In priority order:

1. **Finish labeling rows 50–99** — Azure-assisted (approved, current rubric
   commit `05490be5`) + human spot-check on hesitant and not_ready rows.

2. **Merge positive-candidate labels into training dataset** — run
   `export_relation_verifier_positive_candidate_batch.py` equivalent after
   labeling is complete; combine with existing training CSV.

3. **Implement imbalance-aware options in the sklearn trainer** —
   `scripts/train_relation_verifier_baseline.py` should accept
   `--class-weight balanced` and `--threshold-sweep` flags if not already present.

4. **Run sklearn baselines** — TF-IDF + LR and TF-IDF + SVM with grouped CV.
   Report ready F1, macro F1, PR-AUC, confusion matrix.

5. **Run embedding baselines** — frozen `all-MiniLM-L6-v2` and `all-mpnet-base-v2`
   embeddings + LR/SVM heads; compare to TF-IDF baselines.

6. **Only then: SetFit** — once sklearn and embedding baselines are characterised and
   the dataset has ≥ 50 ready examples.

7. **ModernBERT / DeBERTa** — after SetFit is evaluated and dataset is larger.

---

## 10. Reference: Current Dataset Counts (2026-05-16)

| Source | ready | not_ready | Total |
|---|---|---|---|
| Original training pool | ~10 | ~270 | ~280 |
| Positive-candidate batch rows 0–49 (labeled) | TBD | 0 | ~50 |
| Positive-candidate batch rows 50–99 (pending) | TBD | 0 | ~50 |
| **Target after merge** | **≥ 50** | **~270** | **≥ 320** |

Realistic minimum for meaningful SetFit: **≥ 40 ready examples**.
Realistic minimum for fine-tuned transformer: **≥ 100 ready examples**.
