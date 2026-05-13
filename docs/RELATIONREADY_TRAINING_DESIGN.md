RelationReady training-data design — overview

Purpose
- Define a reproducible, auditable dataset design and annotation pipeline to train a learned RelationReady verifier that judges semantic correctness of candidate relations/formulas.
- Do NOT use live 20-case or 97-case slices for training; keep them held out for evaluation only.

Artifacts (to be created/maintained):
- docs/RELATIONREADY_ANNOTATION_GUIDE.md
- docs/RELATIONREADY_SCHEMA.md
- docs/RELATIONREADY_SPLIT_POLICY.md
- docs/RELATIONREADY_SYNTH_CORRUPTION_PLAN.md
- tests/test_relationready_presence.py

High-level approach
1. Construct a gold test/eval set (held-out): use existing live/pilot outputs only for evaluation, never as training input.
2. Build a large training pool via (a) curated human annotations over diverse cases, (b) synthetic corruption of valid relations, and (c) cross-dataset example mining from public benchmarks (derivative only; no gold leakage).
3. Annotation schema: structured JSON rows with separate fields for candidate, source evidence, executable form, deterministic-check results, and human judgment labels (accept/reject + error-type taxonomy).
4. Split policy: train/val/test splits with case-level separation; ensure no case from an evaluation slice appears in training or validation.
5. Annotation QA: double annotation + adjudication for ambiguous items; record annotator IDs and timestamps.

Next steps
- Create the annotation guide, schema, split policy, and synthetic corruption plan (next files).
- Run repository tests. Commit only docs/tests; leave outputs/ untracked.

Constraints
- No API/model calls.
- No deletion of outputs.
- Gold answers used only for label construction/evaluation, not as model inputs.

