# ORACLE MISMATCH STUDY (2026-04-18)

## Question
When continuation-value oracle disagrees with a more answer-complete branch, is it method error or target-definition mismatch?

## Answer (bounded run)
- Hard conclusion: **augment current oracle** (keep=unchanged, augment=use as one component, replace=full replacement).
- Disagreement rate across oracle targets: **0.0303** (1/33).
- Hybrid resolved visibly less-complete continuation choices in **1** states.
- Recoverable-answer states available for adjudication: **0**.

## Is current oracle sufficient?
- Sufficient as a primary continuation target for many states.
- Insufficient alone in disagreement states where explicit completion evidence is stronger on non-continuation branches.

## Where is it insufficient?
- Near-tie states with small continuation top-2 gaps.
- States where branch reasoning/final-answer evidence indicates stronger completion on non-continuation branches.

## Recommendation for training/evaluation target
- Continue to use continuation-value oracle as a core component.
- Add bounded completion-aware evidence as a transparent hybrid component for disagreement slices.
- Do not replace continuation objective wholesale from this bounded run alone.
