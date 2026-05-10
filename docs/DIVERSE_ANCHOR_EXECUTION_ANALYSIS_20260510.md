# Diverse-Anchor Execution Analysis (2026-05-10)

## Question
In the Cohere 30-case failure-recovery diagnostic, why did `ratio_percentage_anchor` and `backward_check_anchor` not appear as executed contributors, even though they were planned/configured?

## What We Can Inspect (No API)
- The referenced live artifacts directory under `/tmp/...` is **missing** on this machine.
- The repository **does** contain the recorded run artifacts under:
  - `outputs/cohere_diverse_anchor_failure_recovery_30case_20260510T184818Z/manifest.json`
  - `outputs/cohere_diverse_anchor_failure_recovery_30case_20260510T184818Z/results.jsonl`

## Root Cause
This is a **budget constraint / design outcome**, not an anchor-registration bug.

### Key fact: the run used `budget: 4`
`outputs/cohere_diverse_anchor_failure_recovery_30case_20260510T184818Z/manifest.json` records:
- `"budget": 4`

### Budget accounting for the diverse-anchor method (budget=4)
The new method is wired as:
- `enable_direct_hybrid_seed=True`, `direct_hybrid_seed_budget_actions=1`
- `enable_diverse_prompt_anchors=True`, `diverse_prompt_anchor_budget_actions=1`
- default planned anchor IDs include 5 anchors:
  - `direct_l1_anchor`, `equation_first_anchor`, `unit_ledger_money_anchor`, `ratio_percentage_anchor`, `backward_check_anchor`

In `experiments/controllers.py`, anchor execution happens **after** the direct-reserve phase and the optional direct-hybrid seed, and stops when `remaining_budget < diverse_prompt_anchor_budget_actions` (a `break`, not a `continue`).

With `budget=4`, a typical per-case action split is:
1) Direct-reserve (1 action)  
2) Direct-hybrid seed (1 action) → also recorded as `direct_l1_anchor`  
3) Diverse prompt anchors (only **2** more actions available) → only the first two non-`direct_l1_anchor` anchors run

As a result:
- Executed anchors (recorded): `direct_l1_anchor`, `equation_first_anchor`, `unit_ledger_money_anchor`
- Skipped (not executed due to budget): `ratio_percentage_anchor`, `backward_check_anchor`

This matches the post-processed per-case fields in `outputs/.../results.jsonl`, e.g. `cohere_logical_api_calls: 4` and `per_anchor_support` containing only those three anchors.

## Was This a Bug or Only a Reporting Issue?
- **Execution behavior:** expected given `budget=4` and 1 action per anchor.
- **Reporting gap:** the metadata previously showed `diverse_prompt_anchor_ids_planned` and the executed-anchor metadata, but it did **not** explicitly record which planned anchors were skipped (and why). This is what made the run look like “planned but not executed” with no clear reason.

## Safe Fix Before Another Cohere Run
Without changing algorithm behavior, record:
- configured/planned anchor IDs
- executed anchor IDs (including anchors that executed but produced an empty answer)
- skipped anchors with explicit `skip_reason` and remaining budget at the time of skipping
- budget-per-anchor and remaining-budget-before/after-anchor phase

This makes future runs auditable and prevents misinterpretation when `budget` is small.

## Recommendation on Rerunning Cohere
Do **not** rerun Cohere until:
- you decide whether the intended design is to run **all 5 anchors** (which requires a higher per-case action budget), or
- you accept that `budget=4` can only run **3 anchors total** (direct L1 + 2 diverse anchors), and treat the planned list as aspirational under tighter budgets.

If the goal is to evaluate the incremental value of `ratio_percentage_anchor` and `backward_check_anchor`, increase the per-case `budget` above 4 (and verify via the new metadata that those anchors actually execute).
