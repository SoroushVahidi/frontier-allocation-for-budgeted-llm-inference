# Current phase refresh (2026-04-15)

## Why this note exists

Several canonical docs in the repository still describe the stop-vs-act line mainly as a **planned near-term direction**.

That is no longer fully accurate.

As of this refresh, the stop-vs-act line is:
- implemented,
- runnable,
- and already evaluated through multiple bounded follow-up passes.

Use this note as the most up-to-date project-phase summary until the older canonical notes are fully rewritten in-place.

---

## Current repo-phase interpretation

The current project is still best understood as:
- a strong research platform for fixed-budget adaptive test-time compute allocation,
- with cross-controller frontier allocation as the main framing,
- and supervision-target design as the main unresolved issue.

The key current shift is that the stop-vs-act controller line is no longer only a proposed next step. It is now a real implemented branch with multiple bounded evaluation passes.

---

## What has been done

### Established before the current stop-vs-act phase
- Frontier/controller allocation scaffold.
- Anti-collapse controller design and audits.
- Pairwise BT and related branch-scorer experimentation.
- Dataset and baseline readiness tooling.

### Implemented in the stop-vs-act phase
- Lightweight stop-vs-act controller core.
- Dataset builder and train/eval path.
- End-to-end stop-vs-act wrapper.
- Bounded robustness sweep.
- Diagnosis + targeted revision pass.
- Label-refinement pass.
- Counterfactual target pass.
- Small-horizon ACT-vs-STOP target pass.

This means the repo now contains both:
- branch-scorer lines,
- and a real stop-vs-act line with several completed bounded iterations.

---

## What has been learned

### Strong conclusions
1. Stop-vs-act is still the most promising near-term controller framing.
2. The line is strong enough to justify continued bounded development.
3. The strongest remaining limitation is no longer controller existence, but local target quality and local target noise.

### Mixed conclusions
1. The initial stop-vs-act run was promising.
2. Robustness versus the heuristic baseline remained mixed.
3. One targeted uncertainty-handling revision helped on a small matched grid, but not enough to settle the method.

### Negative / non-promoted conclusions
1. Simple threshold or uncertainty-band tuning did not solve the problem.
2. A one-step here-vs-best-other counterfactual target did not replace the default.
3. A small-horizon ACT-vs-STOP target also did not replace the default.

### Current practical conclusion
Keep the current default stop-vs-act setup as the working baseline, and treat newer target variants as informative but not promoted.

---

## What we are doing now

The current phase is best described as:

**bounded stop-vs-act target refinement, with the current default setup as anchor and target stabilization / variance reduction as the next most important goal.**

So the project is not currently centered on:
- heavier models,
- broad benchmark expansion,
- or replacing the stop-vs-act default with another target variant prematurely.

It is centered on:
- reducing local target noise,
- improving stability of bounded local value estimates,
- and preserving strong provenance around what helped and what did not.

---

## What we should do next

### Highest-priority next step
Run a bounded **target stabilization / variance reduction** pass for the current stop-vs-act target family.

Examples:
- tighter paired ACT/STOP rollout matching,
- repeated local target estimation with averaging,
- slightly more stable bounded horizon value summaries,
- explicit target reliability estimates used as training weights.

### What should remain fixed during that pass
- current default stop-vs-act setup as anchor,
- bounded small-grid evaluation style,
- conservative interpretation rules.

### What should not be the next move
- not another simple threshold-only tweak,
- not broad scaling,
- not heavy model changes,
- not promoting a new target variant without clear bounded evidence.

---

## Safe current wording

Safe to say:
- stop-vs-act is implemented,
- it is promising but mixed,
- current bottleneck is deeper target quality / noise control,
- current default remains the best bounded baseline within this line,
- later target variants are useful evidence but not promoted.

Not safe to say:
- stop-vs-act is already a robust winner over the best heuristic,
- one counterfactual target solved the supervision problem,
- the remaining issue is only scale.

---

## Suggested read order for the current phase

1. `docs/STOP_VS_ACT_STATUS.md`
2. `docs/CURRENT_PHASE_REFRESH_2026_04_15.md`
3. `docs/NEXT_PHASE_TARGET_STABILIZATION.md`
4. `docs/CURRENT_REFERENCES_SUPPLEMENT_2026_04_15.md`
5. existing canonical docs such as:
   - `docs/CURRENT_PROJECT_STATUS.md`
   - `docs/CURRENT_BOTTLENECKS.md`
   - `docs/EXPERIMENT_STATUS.md`
   - `docs/CURRENT_REFERENCES_AND_RATIONALE.md`

---

## Bottom line

The repository should now be read as supporting a project in which:
- the framing is strong,
- the stop-vs-act branch is real and implemented,
- the current default stop-vs-act setup remains the best bounded baseline,
- and the next important work is target stabilization, not another high-level reframing.
