Split policy for RelationReady dataset

Goals
- Avoid leakage: no case-level overlap between train/val/test/eval_holdout.
- Representative distribution: stratify by failure family (relation_composition_missing, prompt_gold_inconsistent, etc.) and candidate source.

Policy
1. Collect a large candidate pool across many cases and methods (BFTC, declarative_v1/v2, executable, etc.).
2. Precompute case-level strata by dominant failure family and dataset origin.
3. Randomly assign cases to splits with ratios: train 80%, val 10%, test 5%, eval_holdout 5% — but ensure at least N cases per stratum in each split where possible.
4. The eval_holdout must be manually selected from high-quality, audited slices (e.g., not the 20-case live pilot or 97-case wrong-supported-consensus slices) and kept offline until final evaluation.

Additional rules
- If case has multiple candidate rows, all rows for that case go to same split.
- Maintain a split manifest (CSV) with case_id -> split mapping and a hash of the manifest for reproducibility.

