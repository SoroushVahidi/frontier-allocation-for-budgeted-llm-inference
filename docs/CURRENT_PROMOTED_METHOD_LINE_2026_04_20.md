# Current promoted method line (2026-04-20)

## Purpose

This note gives the shortest canonical answer to:
- what the current promoted method line is,
- why it is promoted,
- what problem it is trying to solve,
- what evidence currently supports it,
- and what the next refinement discipline should be.

## Current promoted line

The current promoted line inside the repository is still:

> **broad diversity-aware branch allocation with answer-support aggregation, strengthened by anti-collapse answer-group-aware allocation, soft repeat-expansion control, and a deterministic output-layer repair stage.**

This is still the same broad family. It is **not** a separate controller family.

## Important current refinement update

What has changed recently is **not** the identity of the broad promoted family, but the **discipline used to test early-coverage refinements inside it**.

The repository now has a stricter hard-coverage interpretation:

> **finish F1 first, then F2, then F3**

for forced shallow balanced coverage over root families.

That stricter law made the current default-model question sharper and also changed which variants look strongest under controlled evaluation.

## Why this line is promoted

The strongest recent repository-backed diagnosis is that many bad cases arise from:
- early-to-mid branch-family monopolization,
- repeated expansion of one high-priority branch,
- shallow child spawning without sufficient alternative maturation,
- and, on a targeted repaired subset, output-layer surfacing mismatch after correct internal reasoning was already present.

The promoted line is the first recent integrated path that directly targets both:
- structural tree-growth failures,
- and a subset of final output-layer failures,
rather than only late-stage thresholding.

## What it is trying to fix

The bottleneck is now best understood as split:

> **under fixed budget, the controller still tends to over-expand one early-favored branch and does not yet reliably preserve and mature answer-distinct alternatives strongly enough; additionally, some targeted failures required explicit output-layer repair after correct internal reasoning had already been found.**

So the promoted line tries to improve:
- early answer-group survival,
- anti-collapse behavior,
- alternative maturation,
- soft control over repeated same-family expansion,
- and deterministic final-answer surfacing after branch selection.

## What evidence currently supports it

Current repository evidence supports the following bounded conclusions:
- anti-collapse design matters for realized budget use and controller behavior,
- answer-group-aware preservation and maturation are more relevant than generic diversity-for-diversity,
- soft repeat-expansion control improves the promoted line relative to weaker nearby variants,
- deterministic output-layer repair can strongly help on a targeted subset where the tree already contains the correct answer,
- strict-phased hard-coverage experiments materially change tree-entry behavior on the frozen hundred-case failure surface,
- and the strongest diagnostic stack now includes exact old-vs-current comparisons, fresh exact current-failure sets, targeted output-layer repair diagnostics, and strict-phased gate-vs-force comparisons.

## What it is not yet safe to claim

It is **not** yet safe to claim that this line is:
- a robust universal winner,
- broadly superior to all strong baselines,
- fully stable under broad real-model confirmation,
- or already the final paper-ready method without further disciplined validation.

It is also **not** yet safe to claim that one of the newest strict-phased early-coverage variants has already earned the default-model slot on broad matched evaluation.

## Current next-step discipline

The next-step discipline for this line is:
1. keep the current integrated broad family as the main repository line,
2. treat **strict phased F1 → F2 → F3** as the correct experimental law for the hard-coverage refinements,
3. compare the strongest strict-phased candidates on a broader matched evaluation surface,
4. reduce remaining tree-generation / absent-from-tree failures,
5. preserve interpretability and observability,
6. avoid broad new controller-family search unless this line clearly stalls.

## Current strongest strict-phased candidates

Under the stricter hard-coverage law, the strongest current default candidates appear to be:
- **strict Gate 1**,
- **strict Gate 2**,
- with **strict forced F3** now better viewed as a strong simple anchor rather than the clear default.

This is a current status note, not a final manuscript claim.

## Reading path

To understand this line quickly, read:
1. `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
2. `STRICT_PHASED_HARD_EARLY_COVERAGE_REPORT_20260421T020917Z.md`
3. `HUNDRED_THREE_GATE_DESIGN_COMPARISON_STRICT_PHASED_20260421T022459Z.md`
4. `CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
5. `CURRENT_SAFE_CLAIMS.md`

## Safe one-sentence summary

> The current promoted repository line is still a broad diversity/aggregation controller strengthened by anti-collapse answer-group-aware allocation, soft repeat-expansion control, and deterministic output-layer repair, but the newest hard-coverage refinements should now be interpreted under a strict phased F1 → F2 → F3 law, where the strongest current default candidates appear to be strict Gate 1 and strict Gate 2 pending broader matched evaluation.
