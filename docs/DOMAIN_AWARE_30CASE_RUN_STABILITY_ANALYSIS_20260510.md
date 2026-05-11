# Domain-Aware 30-Case Run Stability Analysis

This compares the same exact 30-case Cohere replay under two conditions:

- **Run A**: post-domain-detection fix, no guard, stronger result
- **Run B**: guard disabled by default after PR #384, weaker result

Both runs were evaluated offline from existing `/tmp` artifacts only.

## Executive Summary

- Both runs used the same 30 case IDs, the same old/new method IDs, the same budget (`4`), the same seed (`11`), the same provider (`cohere`), the same dataset (`openai/gsm8k`), and the same exact-case replay file invocation.
- Run A new-method exact was `14/30`; Run B new-method exact was `11/30`.
- The guard was not the source of Run B’s loss: it was available in Run B, but `regression_guard_enabled=0/30` and `regression_guard_triggered=0/30`.
- The instability is therefore not a guard artifact; it is case-level output drift under the same replay setup.

## Run Comparison

| Metric | Run A | Run B |
|---|---:|---:|
| Old exact | `9/30` | `9/30` |
| New exact | `14/30` | `11/30` |
| Recovered | `6` | `4` |
| Regressions | `1` | `2` |
| Gold-in-pool (new) | `15/30` | `13/30` |
| Mean answer groups (new) | `3.133` | `2.933` |
| Entropy (new) | `1.002` | `0.949` |
| Frontier collapse (new) | `3/30` | `2/30` |
| Logical Cohere calls | `180/300` | `180/300` |

Guard fields in Run B:

- `regression_guard_available=30/30`
- `regression_guard_enabled=0/30`
- `regression_guard_triggered=0/30`

## Equivalence Checks

- Same case IDs: `yes`
- Same old/new method IDs: `yes`
- Same budget: `yes`
- Same seed: `yes`
- Same provider: `yes`
- Same dataset: `yes`
- Same exact-case replay file invocation: `yes`
- Same domain detection source: `exact_case_metadata` for `30/30` in both runs
- Same domain counts: `money_cost_revenue=10`, `multi_step_arithmetic=10`, `ratio_percent=10` in both runs
- Same anchor routing counts: `ratio_percentage_anchor=10/10`, `backward_check_anchor=10/10`, `unit_ledger_money_anchor=10/10` in both runs

## Which Cases Flipped?

### Correct in Run A, Wrong in Run B

- `openai_gsm8k_17`
- `openai_gsm8k_36`
- `openai_gsm8k_166`
- `openai_gsm8k_337`
- `openai_gsm8k_347`
- `openai_gsm8k_458`

### Wrong in Run A, Correct in Run B

- `openai_gsm8k_168`
- `openai_gsm8k_213`
- `openai_gsm8k_70`

## Flip Analysis

| Case | A final | B final | Gold | Change type | Notes |
|---|---:|---:|---:|---|---|
| `openai_gsm8k_17` | `4` | `8` | `4` | generation failure in B | Gold fell out of tree in B; A had `gold_in_tree=1`, B had `0`. |
| `openai_gsm8k_36` | `16` | `10` | `16` | generation failure in B | B replaced the correct `16` candidate with `10`; gold fell out of tree. |
| `openai_gsm8k_166` | `15` | `18.34` | `15` | generation failure in B | B’s direct-L1 answer drifted to `18.34`; gold fell out of tree. |
| `openai_gsm8k_337` | `195` | `135` | `195` | generation failure in B | A kept the gold `195`; B lost it and selected `135`. |
| `openai_gsm8k_347` | `500` | `520` | `500` | selection instability | Gold stayed in-tree in both runs, but B selected the wrong group `520` despite `500` being present. |
| `openai_gsm8k_458` | `30` | `35` | `30` | generation failure in B | B’s candidate pool lost the gold `30` and selected `35`. |
| `openai_gsm8k_168` | `60` | `35` | `35` | recovery in B | B brought the gold back into the tree and selected it. |
| `openai_gsm8k_213` | `18` | `24` | `24` | recovery in B | B restored the gold candidate and selected it. |
| `openai_gsm8k_70` | `model_step_missing` | `18` | `18` | surfacing/parsing recovery in B | A surfaced `model_step_missing`; B surfaced the numeric answer. |

## Candidate-Level Notes

- The flip set is dominated by **candidate generation drift**, not selector changes.
- In the six A-correct/B-wrong cases, five lost gold from the tree entirely in Run B.
- `openai_gsm8k_347` is the only clear **selection** regression: gold remained in-tree, but the selector favored `520`.
- `openai_gsm8k_70` is a surfacing/parsing issue: Run B converted a bad surfaced answer into the gold answer.

## Diagnosis

- This is **stochastic model-output / candidate-generation instability** under the same replay setup.
- It is **not** explained by a configuration mismatch: the run parameters, methods, seed, budget, provider, dataset, and replay file are aligned.
- It is **not** explained by the disabled guard: Run B had the guard available, but it did not trigger in any case.
- The same anchor schedule executed in both runs, so the instability is in the candidate answers and support counts, not the domain router.

## Safest Next Step

- Do **not** widen to a 50-case run yet.
- First stabilize the diverging cases, especially:
  - `openai_gsm8k_347` for selector instability
  - the gold-absent flips: `openai_gsm8k_17`, `openai_gsm8k_36`, `openai_gsm8k_166`, `openai_gsm8k_337`, `openai_gsm8k_458`
- After that, rerun the same exact 30-case diagnostic to confirm the new behavior is repeatable before any larger slice.
