# Relation Verifier V1 20-Case Postmortem

## Scope

This postmortem analyzes the first valid `relation_verifier_v1` live diagnostic at `outputs/relation_verifier_v1_live_20cases_20260513T013951Z`.

The two earlier live outputs remain invalid evidence:

- `outputs/relation_verifier_v1_live_20cases_20260513T011800Z` failed before model output due to the old Cohere call-shape bug.
- `outputs/relation_verifier_v1_live_20cases_20260513T012431Z` captured empty `raw_response` rows before the `response.text` extraction fix.

## Bottom Line

`relation_verifier_v1` is mechanically valid but semantically too permissive. It is not ready as a branch gate or selector feature. Its main weakness is false acceptance of locally plausible declarative-v2 candidates that prior branch artifacts did not validate as exact or executable-exact.

## Surrogate Outcome Definition

This analysis uses prior branch success on the same case as a surrogate discriminator target:

- `prior_exact_any`: any of BFTC-only exact, declarative-v1 final exact, or declarative-v2 final exact.
- `prior_executable_exact_any`: any of BFTC executable exact, declarative-v1 executable exact, or declarative-v2 executable exact.
- A verifier `accept` is `error_type="none"`.
- `false_accept` means the verifier accepted the case but no prior exact or executable-exact branch recovery existed.
- `false_reject` means the verifier rejected the case even though some prior branch recovery existed.

This is a practical post-hoc diagnostic, not a gold-standard verifier benchmark.

## Counts

- Total cases: `20`
- Verifier accepts (`error_type="none"`): `14`
- True accepts: `4`
- False accepts: `10`
- True rejects: `5`
- False rejects: `1`
- Surrogate precision: `0.2857142857142857`
- Surrogate recall: `0.8`
- False-accept rate among `error_type="none"`: `0.7143`

## Main Answers

1. Among the `14` rows with `error_type="none"`, `4` had some prior exact or executable-exact branch recovery and `10` were false accepts.
2. False accepts are therefore the dominant weakness inside the accepted set.
3. False accepts are dominated by topology labels shown below.
4. False accepts are entirely concentrated in primary candidate source `declarative_v2` because this scaffold always chose the declarative-v2 candidate as primary when available.
5. The prompt likely over-trusted candidates because it judged a single primary candidate for local plausibility and did not force contrast against stronger alternatives or explicit disproof checks.
6. The verifier mostly judged local plausibility rather than target correctness on hard cases.
7. The worst false-accept concentration is in `relation_composition_missing`, `prompt_gold_inconsistent`, and `arithmetic_precision`, with weaker but still important misses in `final_after_process`.
8. A stronger v2 should decompose the judgment into explicit target-binding, source-fact sufficiency, process-state, unit, and executable-formula checks, with a required contradiction rationale before returning `error_type="none"`.
9. Recommended next method: **C. RelationReady decomposed deterministic+LLM checker**.
10. Another live `relation_verifier_v1` run is not justified.

## False Accept Breakdown

By topology label:
- `prompt_gold_inconsistent`: `4`
- `relation_composition_missing`: `3`
- `final_after_process`: `2`
- `arithmetic_precision`: `1`

By candidate source:
- `declarative_v2`: `10`

False-accept cases:
- `openai_gsm8k_1006` `relation_composition_missing` `declarative_v2`: Verifier accepted a locally coherent candidate without forcing the missing bridge/process-state check needed for target correctness.
- `openai_gsm8k_1029` `final_after_process` `declarative_v2`: Verifier accepted a locally coherent candidate without forcing the missing bridge/process-state check needed for target correctness.
- `openai_gsm8k_1069` `prompt_gold_inconsistent` `declarative_v2`: Verifier accepted local plausibility on a case whose broader evidence points to a prompt/gold inconsistency failure mode.
- `openai_gsm8k_166` `arithmetic_precision` `declarative_v2`: Verifier treated arithmetic executability as sufficient and did not contrast the candidate against stronger exact alternatives.
- `openai_gsm8k_190` `relation_composition_missing` `declarative_v2`: Verifier accepted a locally coherent candidate without forcing the missing bridge/process-state check needed for target correctness.
- `openai_gsm8k_213` `prompt_gold_inconsistent` `declarative_v2`: Verifier accepted local plausibility on a case whose broader evidence points to a prompt/gold inconsistency failure mode.
- `openai_gsm8k_22` `final_after_process` `declarative_v2`: Verifier accepted a locally coherent candidate without forcing the missing bridge/process-state check needed for target correctness.
- `openai_gsm8k_228` `prompt_gold_inconsistent` `declarative_v2`: Verifier accepted local plausibility on a case whose broader evidence points to a prompt/gold inconsistency failure mode.
- `openai_gsm8k_239` `prompt_gold_inconsistent` `declarative_v2`: Verifier accepted local plausibility on a case whose broader evidence points to a prompt/gold inconsistency failure mode.
- `openai_gsm8k_262` `relation_composition_missing` `declarative_v2`: Verifier accepted a locally coherent candidate without forcing the missing bridge/process-state check needed for target correctness.

## Predictive Value Of Verifier Fields

- `verifier_target_relation_correct` true in `19` rows; surrogate success when true = `5`; precision = `0.2632`
- `verifier_target_variable_correct` true in `20` rows; surrogate success when true = `5`; precision = `0.25`
- `verifier_source_facts_sufficient` true in `18` rows; surrogate success when true = `5`; precision = `0.2778`
- `verifier_equations_match_source_facts` true in `19` rows; surrogate success when true = `5`; precision = `0.2632`
- `verifier_process_state_correct` true in `19` rows; surrogate success when true = `5`; precision = `0.2632`
- `verifier_unit_scale_correct` true in `18` rows; surrogate success when true = `5`; precision = `0.2778`
- `verifier_arithmetic_executable` true in `18` rows; surrogate success when true = `5`; precision = `0.2778`

Interpretation: these fields have high true rates but weak discrimination. They are closer to permissive local-plausibility checks than to useful branch-success predictors.

## Why V1 Is Weak

- The prompt asks the model to judge one supplied candidate, with supporting context only as background.
- It does not require a contrastive comparison against another candidate or a target-focused counterexample.
- It does not force the verifier to prove that the target relation, process state, and executable formula are jointly sufficient for the requested answer.
- Because the primary candidate source is declarative-v2 for all 20 cases, the verifier mostly ratifies declarative-v2 local coherence instead of discriminating across candidate families.

## Recommendation

**Recommended next method: C. RelationReady decomposed deterministic+LLM checker**

Reason: The main failure mode is false acceptance of locally plausible but globally wrong candidates. A decomposed checker can hard-gate target binding, unit/process-state consistency, and source-fact sufficiency before using an LLM only for residual relation judgment.

A pure prompt-tightening `relation_verifier_v2` is probably not enough by itself. The next version should combine deterministic gates with a narrower LLM judgment, and optionally add contrastive pairwise checks as a secondary component.
