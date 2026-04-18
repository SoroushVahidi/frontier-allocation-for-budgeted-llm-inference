# Completion-aware decision bounded status (2026-04-18)

## Scope and insertion-point summary

This pass adds a bounded completion-aware decision experiment to test semantic/objective mismatch in fixed-budget next-step branch allocation.

Insertion points used:
- New bounded experiment script: `scripts/run_completion_aware_decision_experiment.py`.
- Existing observability-enabled worst-failure run artifacts:
  - `outputs/frontier_target_construction/worst_real_failure_observability_20260418T015924Z/`
  - `outputs/branch_observability/worst_real_failure_observability_20260418T015924Z/`
- Existing canonical multistep validation aggregate reference:
  - `outputs/branch_label_bruteforce_learning/multistep_branch_utility_target_validation_eval_20260417/aggregate_comparison_summary.json`.

Bounded framing preserved:
- We keep next-step allocation framing.
- We do not redesign controller family.
- We test a small interpretable set of completion-aware decision rules.

## Completion / answer-evidence signal definition (exact)

Per `(state_id, branch_id)`, we derive machine-readable fields:
- `branch_has_final_answer_text`: `True` iff `branch_final_answer_text_raw` is non-empty.
- `branch_has_normalized_answer`: `True` iff `branch_final_answer_normalized` is non-null.
- `branch_reasoning_completion_flags`:
  - `has_reasoning_text`
  - `has_final_step_cue` (explicit textual cues in final line: “therefore”, “thus”, “answer is”, “final answer”, etc.)
  - `has_final_arithmetic_or_comparison_step` (digit + arithmetic/comparison symbol in final line or reasoning)
  - `has_terminal_numeric_token`
- `branch_completion_score` (bounded additive, capped at 1.0):
  - `+0.45` final answer text present
  - `+0.25` normalized answer recoverable
  - `+0.20` arithmetic/comparison final-step evidence
  - `+0.10` explicit final-step textual cue
- `branch_answer_evidence_score` (bounded additive, capped at 1.0):
  - `+0.60` normalized answer recoverable
  - `+0.30` final answer text present
  - `+0.10` terminal numeric token present
- `completion_signal_provenance`:
  - explicit source fields
  - explicit rule-set id (`explicit_boolean_heuristics_v1`)
  - explicit fallback reason when observability record is missing.

Conservative behavior:
- Missing branch observability defaults to zero-evidence signal rows (not inferred optimistically).

## Policy definitions (exact)

Compared policies on the same observability run states:
1. `oracle_one_step_reference`
   - Picks `argmax expected_value_if_branch`.
2. `best_bounded_learned_branch_score_current`
   - Replays method-chosen branch from trace (`method_chosen_branch_id`).
3. `completion_bonus`
   - Picks `argmax(expected_value_if_branch + completion_bonus * branch_completion_score)`.
   - Used `completion_bonus=0.03`.
4. `completion_outside_gate`
   - Start from oracle one-step top.
   - Allow completion override only when top completion branch satisfies:
     - `branch_completion_score >= 0.20`
     - `delta_u_vs_outside >= -0.02`
     - oracle value drop <= `0.02`.
5. `completion_tie_resolution`
   - If oracle top-2 gap <= `0.03`, choose highest completion-score branch among oracle-near-tie eligible set.
   - Else keep oracle one-step top.

## Interaction with existing multistep/oracle-style signals

- On observability run states, the experiment uses branch-level one-step utility (`expected_value_if_branch`) as the current explicit oracle target.
- Completion features are only used as bounded policy modifiers (bonus/gate/tie), not a replacement objective.
- `multistep_k3_current` remains explicitly included as an external canonical reference from prior validation aggregate metrics.

## Commands run

1. Regenerated observability-enabled bounded worst-failure artifacts used as experiment input:

```bash
python scripts/run_worst_real_failure_casebook_with_reasoning.py \
  --subset-size 8 --seed 19 --budget 5 --init-branches 3 --max-branches 4 \
  --provider openai --model gpt-4.1-mini --allow-sim-fallback
```

2. Ran completion-aware decision experiment:

```bash
python scripts/run_completion_aware_decision_experiment.py \
  --run-id worst_real_failure_observability_20260418T015924Z \
  --output-run-id completion_aware_decision_eval_20260418
```

## Output bundle written

- `outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/config_manifest.json`
- `outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/per_seed_summary.json`
- `outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/aggregate_comparison_summary.json`
- `outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/completion_alignment_diagnostics.json`
- `outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/failure_case_diagnostics.json`
- `outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/support_diagnostics.json`
- `outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/completion_signal_artifacts.json`
- `outputs/branch_label_bruteforce_learning/completion_aware_decision_eval_20260418/commands_assumptions_caveats.md`

## Key metrics

From `aggregate_comparison_summary.json` on 34 states:

- Current learned path (`best_bounded_learned_branch_score_current`):
  - `match_oracle_rate = 0.4412`
  - `mean_oracle_regret = 0.02311`
  - `objective_mismatch_states = 2` (oracle less complete than method).

- Completion-aware variants:
  - `completion_bonus`:
    - `match_oracle_rate = 1.0000`
    - `mean_oracle_regret = 0.00000`
    - `prefer_stronger_completion_vs_oracle_rate = 0.0000`
  - `completion_outside_gate`:
    - `match_oracle_rate = 0.8824`
    - `mean_oracle_regret = 0.00090`
    - `prefer_stronger_completion_vs_oracle_rate = 0.0294`
  - `completion_tie_resolution`:
    - `match_oracle_rate = 0.9412`
    - `mean_oracle_regret = 0.00098`
    - `prefer_stronger_completion_vs_oracle_rate = 0.0588`

Reference multistep (external canonical validation aggregate):
- `multistep_k3` accepted accuracy mean: `0.7063`
- near-tie accepted accuracy mean: `0.6000`
- strict-slice accepted accuracy mean: `0.5833`

## Small semantic case analysis (real states)

### Case A: objective-mismatch example where method is more completion-evident
- State: `s_ep3_d1_r4_d69ede3958bfe0e8c072`
- Method branch: `b0` completion score `0.2`
- Oracle branch: `b2` completion score `0.0`
- Interpretation: this is a true objective mismatch signature (oracle one-step preference does not align with stronger completion evidence).
- Outcome under completion-aware variants in this bounded pass:
  - `completion_bonus` reverted to oracle-like preference broadly and did not preserve this method-side completion advantage.
  - gate/tie variants did not systematically resolve these specific mismatch states.

### Case B: objective-mismatch example where method is more completion-evident
- State: `s_ep6_d1_r4_837e8a12eaf5e1c68df7`
- Method branch: `b0` completion score `0.2`
- Oracle branch: `b3` completion score `0.0`
- Same pattern as Case A: mismatch exists, but bounded completion policies did not produce a targeted net fix.

### Case C: completion-aware branch differs from oracle in near-tie slice
- State: `s_ep7_d1_r4_2910c13789136d96d0fc`
- Oracle branch: `b1` (completion score `0.2`)
- Completion-aware chosen branch (`completion_tie_resolution` / `completion_outside_gate`): `b2` (completion score `0.3`)
- This demonstrates the mechanism can prefer more answer-complete textual evidence in near-tie-like settings.
- However, these wins are sparse and not enough to establish robust mismatch resolution.

## Caveats

- Bounded to a single small observability-enabled run.
- Branch normalized answers were unrecoverable in this run (`recoverable_answer_n = 0`), so correctness-via-recoverable-answer could not adjudicate policy changes.
- `multistep_k3_current` is a canonical external reference metric in this pass, not re-trained/re-evaluated on the new observability states.

## Hard conclusion

In this bounded pass, explicit completion-aware decision logic **does surface objective-mismatch states** and can occasionally pick branches with stronger semantic completion evidence, but it **does not yet provide a robust targeted improvement over the current continuation-value-style oracle objective on the observed worst-real-failure slice**.

Practically:
- Some disagreements are real objective mismatch (oracle less complete than method on a subset).
- But completion-aware bonus/gate/tie rules, as currently bounded, mostly collapse back toward oracle-style choices or produce only sparse completion-favoring overrides.
- Therefore, completion evidence should be treated as a bounded auxiliary signal for diagnosis/guardrails, not yet as a dominant replacement objective.
