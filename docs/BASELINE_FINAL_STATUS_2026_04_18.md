# Baseline final status (2026-04-18)

## Scope of this final pass

This note closes the baseline-classification and consistency pass for the current paper phase focused on:
- fixed-budget next-step branch allocation,
- continuation-value core,
- bounded completion-aware correction in disagreement slices,
- and hard near-tie branch states.

## Internal baseline sufficiency

**Assessment:** Internal baseline coverage is sufficient for this phase.

Why:
- Strong internal matched baselines and multistep families are already artifact-backed.
- Hard-slice and near-tie diagnostics exist and are explicitly tracked.
- The baseline bottleneck is now taxonomy/coverage honesty, not missing internal scaffold classes.

## External baseline family sufficiency

**Assessment:** External family coverage is strong enough for the current phase **with caveats**.

### Direct family
- **Q*** (*Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning)
  - Class: **direct**
  - Status: **discuss-only / not-yet-integrated**
  - Priority: **essential**
  - Caveat: implementation gap is explicitly recorded.

### Adjacent essential families
- **Let's Verify Step by Step**
  - Class: **adjacent** (completion-aware PRM/verifier)
  - Status: **discuss-only**
  - Priority: **essential adjacent**
  - Non-equivalence: verifier/process scoring space differs from direct branch allocation control.

- **Rational Metareasoning for Large Language Models**
  - Class: **adjacent** (stop-vs-continue adaptive compute)
  - Status: **discuss-only**
  - Priority: **essential adjacent**
  - Non-equivalence: stop/continue metareasoning framing differs from frontier branch-allocation action space.

### Adjacent optional family (current framing)
- **Efficient Contextual LLM Cascades through Budget-Constrained Policy Learning**
  - Class: **adjacent** (routing/cascade)
  - Status: **runnable-adjacent** via cascade import validation path
  - Priority: **optional unless framing broadens**
  - Non-equivalence: cascade/routing decisions differ from next-step active-branch allocation.

### Ingredient / framing family
- **Best Arm Identification: A Unified Approach to Fixed Budget and Fixed Confidence**
  - Class: **ingredient-adjacent boundary**
  - Status: **discuss-only framing reference**
  - Priority: **essential framing for near-ties**
  - Non-equivalence: foundational bandit framing; not a direct empirical LLM baseline stack.

## What is still missing

- A runnable in-repo adapter/reproduction for the **Q*** direct family.
- Runnable implementations for two essential adjacent discuss-only families (Let's Verify Step by Step, Rational Metareasoning for LLMs).

These are recorded as explicit integration gaps, not hidden omissions.

## Final phase decision

**Hard conclusion: baseline section finished with explicit caveats.**

Interpretation:
- Finished for the current paper phase because all required families are now explicitly present, classified, and consistently documented with honest runnability labels.
- Caveat is implementation depth (discuss-only gaps), which remains clearly disclosed and does not block baseline-section completeness for this phase.
