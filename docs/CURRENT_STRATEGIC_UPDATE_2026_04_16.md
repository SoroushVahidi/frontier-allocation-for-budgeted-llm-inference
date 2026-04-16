# Current strategic update — 2026-04-16

This note consolidates the most important recent project decisions and should be treated as a canonical bridge between the older canonical docs and the latest repository state.

## 1) Current project identity

The project is centered on:
- fixed-budget adaptive test-time compute allocation for LLM reasoning,
- cross-controller frontier allocation,
- repeated next-step allocation over active branches,
- and honest cost-aware comparison across heterogeneous controller families.

The most faithful local question is:

> Which active branch should receive the next unit of compute?

A useful equivalent phrasing is:

> Is spending the next unit of compute on this branch better than the best alternative use of that unit?

## 2) Ranking/allocation is primary; stop is secondary

Recent discussion clarified that the project should **not** be centered on a standalone stop-vs-act story.

The primary problem is:
- score active frontier options,
- select the highest-value branch,
- and spend the next unit of budget there.

A stop decision is only a derived or helper view:
- as a local gate,
- as a null action,
- or as a comparison against an outside option.

So the repo should be interpreted primarily through:
- branch-priority allocation,
- next-step frontier allocation,
- pairwise or pointwise branch comparison,
- and budget-conditioned opportunity-cost-aware selection.

## 3) Main bottleneck, sharpened

The project bottleneck is not just generic proxy-label mismatch.

The sharper formulation is:

> supervision-target design for budget-conditioned comparative marginal utility under noisy branch-level credit assignment.

Concretely, the hard part is building targets for the question:

> under remaining budget B, is allocating one more unit of compute to branch b better than the best alternative use of that unit?

This bottleneck contains several subproblems:
- proxy-label mismatch,
- branch-level delayed credit assignment,
- noisy PRM- or rollout-derived supervision,
- opportunity-cost modeling,
- and remaining-budget dependence.

## 4) Current safe interpretation of the method direction

The strongest near-term method direction remains:
- branch-priority / next-step allocation over active branches,
- with pairwise or pointwise learned branch scoring,
- and any local stop-vs-act gate treated only as an implementation simplification.

The cleanest binary interpretation is not literal global termination. Instead:
- **ACT** means this branch deserves the next unit of budget,
- **STOP** means this branch does not beat the outside option for the next unit.

That outside option may be:
- another branch,
- another controller family,
- verifier use,
- or true termination.

## 5) External baseline status after the recent unblocking passes

The repository now has a materially stronger adjacent-baseline story.

Runnable or partially runnable now:
- `s1_simple_test_time_scaling`: MODE A runnable, MODE B guarded official-results import path.
- `tale_token_budget_aware_reasoning`: MODE A runnable, MODE B guarded official-results import path.
- `l1_length_control_rl`: MODE A runnable, MODE B guarded official-results import path.
- `best_route_microsoft`: runnable-adjacent via strict import validation.
- `when_solve_when_verify`: runnable-adjacent via strict import validation.
- `cascade_routing`: runnable-adjacent via strict import validation.
- `mob_majority_of_bests`: runnable-adjacent via strict import validation.
- `rest_mcts`: runnable-adjacent via strict import validation.

Still blocked or incomplete:
- `compute_optimal_tts`: still blocked because official paper↔repo mapping and fair matched protocol are unresolved.
- `openr`: next adjacent baseline to evaluate/unblock after the current pass.

Safe claim now:
- the repository supports several strong **validated adjacent import protocols** for neighboring baselines.

Not safe claim now:
- that these adjacent baselines are direct in-repo reproductions or control-equivalent comparisons to frontier/action-native methods.

## 6) Direct-paper comparator status

A very important direct conceptual comparator is:
- *What If We Allocate Test-Time Compute Adaptively?* (arXiv:2602.01070)

Current best interpretation:
- this is a **paper-level direct comparator** and likely one of the most important papers for positioning,
- but it is **not** currently an official-code or import-validated baseline in this repo,
- and should therefore be treated as a **paper-faithful reimplementation candidate**, not an official reproduction.

Safe wording:
- “paper-faithful reimplementation candidate from public paper specification”

Unsafe wording:
- “official reproduction”
- “author-released implementation baseline”
- “import-validated baseline package”

## 7) What is strong now vs what is still weak

Strong now:
- repo identity and paper framing,
- branch/frontier allocation formulation,
- anti-collapse controller perspective,
- multiple adjacent baseline integration protocols,
- careful safe-claim discipline,
- enough infrastructure for serious paper development.

Still weak:
- supervision target quality for next-step allocation,
- budget-conditioned comparative target design,
- robust branch scoring across budgets / seeds / datasets,
- decisive direct-comparator evidence against the closest adaptive-allocation alternative.

## 8) Recommended next research focus after baseline expansion

After finishing the adjacent-baseline expansion track, the next best use of effort is:

1. sharpen supervision targets for next-unit allocation,
2. build comparative-marginal labels rather than generic branch-quality labels,
3. model remaining-budget dependence explicitly,
4. make branch-vs-outside-option semantics explicit,
5. and only then scale broader experiments.

## 9) Practical writing rule

If a future paper sentence suggests the project is mainly about “should we stop reasoning?”, rewrite it unless the sentence explicitly means a helper gate or null action.

The more faithful language is:
- frontier allocation,
- branch-priority scoring,
- next-step compute allocation,
- marginal value of the next compute unit,
- and opportunity-cost-aware selection under a fixed budget.
