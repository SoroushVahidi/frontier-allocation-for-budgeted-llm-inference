RelationReady annotation guide

Goal
- Label each reasoning trace as `ready` (1) or `not_ready` (0): does the trace establish
  the problem's target relation through visible, step-by-step computation and arrive at
  the correct answer?

Annotation unit
- One row per candidate trace, tied to a `row_id` / `problem_id`.
- Columns: `relation_ready_label_manual`, `first_error_axis_manual` (debug metadata only),
  `notes_manual` (free text).

Primary labels

  ready (1)
    The trace shows all required computation steps, correctly binds intermediate values
    to the problem variables, and arrives at the correct final answer. The reader can
    follow the derivation from source facts to answer without inference gaps.

  not_ready (0)
    Anything that fails the above: opaque trace, truncated trace, final-answer-only,
    wrong answer, or a trace that skips the target relation step.

Calibrated decision rules (apply in order)

1. Trace + answer must both be present and correct.
   If the answer is wrong, label not_ready regardless of trace quality.

2. Final-answer-only or opaque traces are not_ready.
   A trace that states the answer without showing the derivation steps is not_ready
   even if the answer is numerically correct.

3. PAL / code traces can be ready.
   If the code operations establish the target relation (variables are bound to problem
   values, the computation is shown), the trace qualifies as ready.
   Pseudocode or sketch-only code without real bindings is not_ready.

4. Trivial final aggregation is acceptable.
   If all operands are visible in the trace and only a simple sum/product/ratio remains,
   the trace is ready even if the last arithmetic step is implicit.
   Example: "A=12, B=7, so A+B" is acceptable if A and B were derived in prior steps.

5. Nontrivial missing target relation is not_ready.
   If a required intermediate quantity (source fact, intermediate variable, binding) is
   never computed and just asserted, label not_ready with axis `missing_source_fact` or
   `relation_composition_missing`.

6. Wrong variable binding is not_ready.
   If the trace computes the right numeric answer but binds it to the wrong variable
   (e.g., confuses "cost per unit" with "total cost"), label not_ready with axis
   `wrong_variable_binding`.

Error axes (debug metadata — not used for training)
  missing_source_fact          Required input value is never established
  relation_composition_missing Intermediate step is skipped
  final_after_process          Trace uses a formula that requires a prior process it omits
  wrong_variable_binding       Correct value assigned to wrong variable
  arithmetic_precision         Rounding/unit inconsistency, otherwise correct derivation
  unit_scale_error             Dimensional mismatch (e.g., seconds vs minutes)
  other                        Does not fit above categories

Gold metadata policy
- `gold_answer_metadata_only` and `is_correct_offline_metadata` are for offline audit
  and human review only.
- These fields must never appear in `feature_text`, provider prompts, or model inputs.
- Annotators may consult gold values during adjudication only; gold must not be shown
  to the model at any stage.

Quality control
- Azure strong model (`gpt-5.4`) may be used as a second opinion on hard disagreements.
- Azure outputs are preliminary — not automatic ground truth.
- All label changes must be documented in `notes_manual` with the human annotator's
  reasoning. Final labels are human-reviewed/accepted before entering the training set.

Privacy / provenance
- Do not include gold values in any prompt shown to a model or annotator during labeling.
- Gold may be revealed only during human adjudication, never as a model input feature.
