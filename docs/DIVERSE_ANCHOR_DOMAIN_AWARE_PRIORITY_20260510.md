# Diverse-Anchor Domain-Aware Priority (2026-05-10)

## Motivation
With per-example `budget=4`, the diverse-anchor method can only fit:
1) direct-reserve (1 action)
2) direct-hybrid seed → recorded as `direct_l1_anchor` (1 action)
3) **two** additional diverse prompt anchors (2 actions total, because `diverse_prompt_anchor_budget_actions=1`)

This means only two non-direct anchors execute, so the **order** of planned anchors determines which anchors actually run.

## Policy
We add a **no-API**, heuristic domain-aware ordering step for diverse prompt anchors.

### Always preserved
- `direct_l1_anchor` remains special: it is populated from the direct-hybrid seed when it executes.
- We do not increase budget and do not change selection / PAL / commitment logic.

### Domain detection (`detected_problem_domain`)
A lightweight heuristic inspects the `question` text and returns one of:
- `money_cost_revenue` (contains cost/price/revenue/$/paid/buy/sell/etc.)
- `ratio_percent` (contains percent/%/ratio/proportion/fraction)
- `multi_step_arithmetic` (contains digits plus “then/after/total” pattern)
- `unknown` (fallback)

### Anchor ordering (`domain_aware_v1`)
Given the configured anchor list, we reorder the **non-direct** anchors as:
- **money/cost/revenue**: `unit_ledger_money_anchor`, then `equation_first_anchor`
- **ratio/percent**: `ratio_percentage_anchor`, then `equation_first_anchor`
- **multi-step arithmetic**: `equation_first_anchor`, then `backward_check_anchor`
- **unknown/mixed**: keep the existing default order:
  `equation_first_anchor`, `unit_ledger_money_anchor`, `ratio_percentage_anchor`, `backward_check_anchor`

The reorder is stable:
- it only moves preferred anchors earlier;
- it keeps any remaining anchors in their original order;
- it preserves any explicit user-provided anchor list (reordered within it).

## Metadata
Per example, controller metadata now includes:
- `anchor_priority_policy`
- `detected_problem_domain`
- `configured_anchor_ids` (original configured list)
- `prioritized_anchor_ids` (post-reorder list used for execution)
- `diverse_prompt_anchor_ids_executed`
- `diverse_prompt_anchor_skipped` with explicit skip reasons (e.g. `insufficient_remaining_budget`)
- `remaining_budget_before_diverse_anchors` / `remaining_budget_after_diverse_anchors`

This makes it obvious, under tight budgets, **which anchors were intended**, **which were prioritized**, and **which were skipped** (and why).
