# Data processing and canonical data status (2026-04-18)

## Purpose

This note consolidates the repository data layer for the current bottleneck:
- hard ambiguity-sensitive branch-allocation states,
- near-tie disagreement states,
- continuation-value vs completion-evidence mismatch,
- and target/oracle-definition quality on those states.

This pass does **not** add new datasets. It clarifies how finalized datasets and derived products should be cleaned, normalized, and used.

---

## 1) What data exists now

## Raw / source-layer data

- **Core + expansion evaluation datasets** are registry-backed in `experiments/hf_datasets.py` with canonical IDs, alias mapping, split defaults, and role map tags.  
- **Clone-based evaluation dataset** (NaturalPlan) is handled separately via git-spec entries (no raw vendoring policy).  
- **External supervision datasets** are tracked in `configs/external_reasoning_datasets_registry.json` and remain explicitly role-separated from benchmark evaluation.

## Processed / derived products already in repo

- Branch-target artifacts (candidate/pairwise/state summaries) under:
  - `outputs/branch_label_bruteforce_targets/`
  - `outputs/branch_label_bruteforce_learning/`
  - `outputs/branch_label_bruteforce_merged/`
- Branch observability and answer-recovery bundles under:
  - `outputs/branch_observability/`
  - `outputs/final_answer_recovery/`
- Canonical branch-learning row schema defined in:
  - `configs/branch_learning_corpus_schema_v1.json`

## Main duplication/inconsistency observed

- Multiple similarly-shaped derived artifacts exist across target/build/eval folders with overlapping semantics.
- Branch observability and branch-learning targets are high-value complements but not materialized by default as one canonical joined table.
- Alias/canonical naming was mostly strong but needed one explicit machine-readable canonical role map artifact for downstream consumers.

---

## 2) Canonical data-role map (now explicit)

The role map is now exported as machine-readable canonical data:
- `outputs/data_consolidation_20260418/dataset_role_map.json`
- `outputs/data_consolidation_20260418/dataset_alias_map.json`

### Role separation policy

1. **Core evaluation datasets**  
   Use for benchmark-level and hard-slice evaluation claims.

2. **Expansion evaluation datasets**  
   Use for ambiguity-regime breadth and disagreement-slice robustness checks.

3. **Supervision/prep datasets (external)**  
   Use for preparation, warm-start, and supervision experiments only; not direct benchmark claim evidence by default.

4. **Branch-level derived supervision products**  
   Candidate/pairwise/outside-option rows from canonical branch-learning pipelines.

5. **Hard-slice / near-tie / disagreement products**  
   Pairwise flags and mismatch diagnostics for target/oracle decision quality.

6. **Semantic diagnosis casebooks**  
   Worst-failure and completion-aware mismatch artifacts; diagnosis-first, separate from broad benchmark tables.

7. **Optional/historical/non-default products**  
   Kept for provenance; not canonical evidence unless promoted.

---

## 3) Cleaning + normalization completed in this pass

## Dataset identity consistency

- Canonical alias and role maps are now exported as default machine-readable products for all data consumers.
- Canonical-vs-loader distinction is explicit (example: canonical `allenai/drop` key with current `ucinlp/drop` loader fallback recorded).

## Answer normalization strengthened

Normalization now has an explicit canonical function:
- `experiments.data.normalize_answer_text`

It standardizes:
- numeric normalization (including fraction and comma handling),
- MCQ label extraction (A-E),
- short-text canonicalization (lowercase/whitespace-normalized),
- missing/malformed handling with explicit recoverability reason,
- type flags: `answer_type`, `numeric_answer_flag`, `multiple_choice_flag`, `long_form_flag`.

Branch observability now consumes this function and emits richer metadata:
- `answer_type`
- `numeric_answer_flag`
- `multiple_choice_flag`
- `long_form_flag`
- `normalization_failure_reason` (recoverability-grounded)

## Normalized example layer

`experiments.dataset_normalization.NormalizedExample` now includes:
- `dataset_name`, `example_id`, `split`
- `question`, `raw_answer`, `normalized_answer`
- `answer_type`, numeric/MCQ/long-form flags
- recoverability fields (`recoverable_answer_flag`, `recoverability_reason`)
- `task_format`, `extra`

This aligns the runtime object with canonical normalized-example requirements.

---

## 4) Canonical processed data objects to use now

This pass defines and exports canonical schema objects under:
- `outputs/data_consolidation_20260418/`

### Exported files

- `manifest.json`
- `dataset_role_map.json`
- `dataset_alias_map.json`
- `normalized_example_schema.json`
- `branch_state_schema.json`
- `decision_object_schema.json`
- `semantic_diagnosis_schema.json`
- `data_processing_inventory.json`
- `data_quality_findings.json`
- `commands_assumptions_caveats.md`

### Canonical layer interpretation

1. **Normalized examples**: benchmark-ready example layer for dataset-facing consistency.  
2. **Branch/state**: observability + recoverability layer with branch text, answer capture, and normalized answers.  
3. **Decision objects**: pairwise/top-vs-rest/near-tie/hard-slice/oracle-comparison/adjudication rows.  
4. **Semantic diagnosis**: casebook-level rows for worst failures and completion-aware mismatch adjudication.  

---

## 5) What remains exploratory vs canonical

## Canonical now

- Dataset roles and aliases (machine-readable).
- Answer normalization contract and branch-level normalization metadata.
- Schema definitions for normalized examples, branch states, decision objects, and semantic diagnosis.
- Inventory + quality findings bundle for data-layer governance.

## Still exploratory / non-default

- Many one-off bounded method output folders remain exploratory unless referenced in canonical docs.
- Some derived comparison artifacts are still report-shaped rather than canonical joined tables.
- Not all semantic diagnosis artifacts are yet emitted in one stable row schema across all runs.

---

## 6) Is current data usage correct for the bottleneck?

**Mostly yes, after this pass.**

The repository now has explicit support for:
- benchmark-level evidence,
- hard-slice/near-tie evidence,
- branch-level supervision objects,
- semantic diagnosis casebook objects,
- and strict dataset-role separation.

This is materially closer to the actual bottleneck than a generic benchmark-only framing.

---

## 7) Remaining data-layer bottleneck

The remaining bottleneck is now:

> **default materialization of a single joined canonical table that merges branch observability + continuation-value targets + decision-object outcomes + answer adjudication for contested states.**

Today these pieces exist and are schema-defined, but still require explicit joins by `state_id`/`branch_id` across output families.

That join-layer should be the next data-engineering step before the next major target/oracle freeze memo.

