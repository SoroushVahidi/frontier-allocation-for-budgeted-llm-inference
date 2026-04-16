# Supervision-target gap note

This note records the current best articulation of the project's main methodological gap.

## Short version

The repo's main open problem is not generic controller complexity. It is:

> how to design a supervision target for next-step frontier allocation that reflects remaining budget, branch-level delayed credit, and the opportunity cost of alternative frontier actions.

## Why earlier wording was not sharp enough

It is true that the project has:
- proxy-label mismatch,
- noisy branch-comparison labels,
- and delayed credit assignment.

But those phrases are still slightly too broad.

The sharper target-design statement is:

> budget-conditioned comparative marginal utility under noisy branch-level credit assignment.

## Exact form of the missing target

For branch `b` and remaining budget `B`, the desired label is not simply:
- probability branch `b` eventually succeeds,
- local PRM score on branch `b`,
- or whether a future step on `b` is wrong.

Instead, the key quantity is closer to:

- expected gain from spending one more unit on `b` under remaining budget `B`,
- relative to the best alternative use of that unit.

So a good target must implicitly or explicitly account for:
1. remaining budget,
2. heterogeneous action types,
3. delayed downstream effects,
4. noisy rollout / PRM supervision,
5. and opportunity cost across the frontier.

## Why adjacent literature is useful but incomplete

Several nearby research lines help, but none fully solves the repo's target problem by itself:

- **Value-of-computation / metareasoning** papers clarify that compute decisions should be judged by expected utility gain minus cost.
- **Tree-structured RL credit-assignment** papers improve how value is assigned to prefixes or branch points.
- **Process reward model** papers diagnose that step-level labels can be noisy or policy-dependent.
- **MCTS value-estimation** papers explain why rollout-based labels can have high variance or bias.

These are all useful inputs, but they stop short of the exact target needed here:
- a lightweight inference-time controller,
- acting under a fixed remaining budget,
- comparing heterogeneous frontier actions,
- and deciding which one deserves the next compute unit.

## Practical implications for repo work

The next strong method step is not merely:
- more branch scoring,
- more data,
- more sweeps,
- or heavier models.

The next strong step is to improve the target itself.

Promising directions include:
- comparative labels rather than absolute labels,
- explicit outside-option modeling,
- budget-conditioned label construction,
- uncertainty-aware filtering or reweighting of noisy labels,
- and cleaner separation between local branch quality and global allocation value.

## Recommended project language

When describing the bottleneck, prefer wording like:
- comparative marginal utility,
- budget-conditioned next-step allocation target,
- opportunity-cost-aware branch supervision,
- branch-level credit under fixed remaining budget.

This is more precise than talking only about stop-vs-act or generic proxy-label mismatch.
