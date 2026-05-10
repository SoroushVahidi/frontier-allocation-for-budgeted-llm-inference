# External L1 Advantage Analysis

## Scope
Analyzed 7 Stage-2 `external_l1_only` cases where `external_l1_max` was correct and integrated method was wrong.

## Common Pattern
- Most gaps look like target/representation failures (state update, ratio partition, sign/target inversion), not random arithmetic slips.
- For all 7 cases, routing-v2 produced correct answers on pilot rows; adaptive-router-v3 also corrected the subset it covered.
- This suggests core solveability exists, but production path did not trigger the right scaffold/action on checkpoint run.

## External Trace Availability
- Raw full chain-of-thought traces are not available.
- Compact external artifacts are available via `paired_casebook.csv` fields (`selected_group`, `final_nodes_answers`, `selector_pool_answers`, call counts).

## What External L1 Is Likely Doing Better
- Better decomposition/target setting on average, ratio, and withheld-amount formulations.
- Better base/denominator handling on percent-loss style case(s).
- Better final-target alignment (positive withheld amount vs signed delta errors).

## Scaffold Adequacy vs Missing Capability
- Current targeted scaffolds appear directionally correct on these exact case families.
- The bottleneck appears to be routing/activation + final-target verification in checkpoint runtime, not inability of scaffolds to solve the families.

## Method Implications
- New idea should emphasize selective activation + verifier checks (target quantity, sign, denominator base) before answer commit.
- Also inspect whether `external_l1_max` prompt shape induces cleaner decomposition that can be adapted without copying hidden artifacts.

## Decision Framing
- A) Inspect/reuse external_l1 prompt style: **Yes** (high value, low risk).
- B) Add answer verifier: **Yes** (target/sign/base checks).
- C) Implement another scaffold: **Maybe**, lower priority than routing+verifier fixes.
- D) Move to Stage 3 exploratory: **Yes**, after a small patch-loop to validate routing/verification changes.
- E) Stop iteration: **No**, gap appears structured and likely recoverable.
