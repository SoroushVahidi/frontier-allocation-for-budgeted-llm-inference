# RelationReady Verifier Phase Closure (2026-05-17)

## Closure Status
**The RelationReady verifier phase is closed for the current project stage.**

This closure means verifier model/training design is complete enough for current frontier-allocation work. Remaining priority is allocation-policy validation and paper/report packaging, not additional verifier training.

## What Is Frozen / Selected

- **Selected verifier:** SetFit `all-mpnet-base-v2` cfg1.
- **Training data used:** 380 included rows after excluding uncertain labels (`ready=93`, `not_ready=287`).
- **Label definition:**
  - `ready`: visible derivation establishes the target relation.
  - `not_ready`: opaque/incomplete/wrong-binding or other relation-establishment failure.
- **Leakage guardrails:** gold/offline correctness metadata excluded from model features and provider prompts.
- **Leakage checks:** documented checks pass for feature construction and scoring workflows.

## Standalone Verifier Evidence

- Ready F1: **0.8646** (OOF, threshold 0.5)
- PR-AUC: **0.883** (verified from `predictions.jsonl`)
- Macro F1: **0.9094**
- Confusion matrix (threshold 0.5): **TN=271, FP=16, FN=10, TP=83**
- Group-bootstrap ready-F1 CI lower bound supports improvement over frozen `all-mpnet-base-v2` SVM baseline.
- PR-AUC should be reported conservatively: point estimate is higher than frozen SVM, but CIs overlap (no definitive PR-AUC superiority claim).

## Downstream Evidence (Current Stage)

- **Cross-method selection:** method-entangled; not promoted as a routing policy.
- **Exploratory 1440-row within-method reranking:** verifier `75.83%`, random `66.04%`, lift `+9.79pp`.
- **Small 15-case sanity validation:** verifier `40.00%`, random `36.67%`, lift `+3.33pp` (underpowered).
- **Independent budget-6 Cohere validation:** verifier `86.67%`, random `82.08%`, lift `+4.58pp`.
- **Uncertainty-backed headline:** verifier-minus-random `+4.58pp`, 95% cluster-bootstrap CI `[+0.28pp, +9.03pp]`.
- **Budget-4/8 full artifact:** overlap-contaminated, not independent.
- **Budget-4/8 filtered subset:** small and uncertain.
- **Frozen slice-aware transfer:** neutral/negative overall and not promoted.

## Final Approved Use Boundary

### Approved
- Use verifier as a **within-method** seed/trace reranking signal.
- Use verifier score comparatively **within the same method/budget candidate pool**.
- Use verifier in offline allocation-policy analysis with gold-free features/prompts.

### Not Approved
- Naive cross-method routing directly from raw `proba_ready`.
- Claiming slice-aware/tie-aware policy gains beyond verifier top-1 from current evidence.
- Using `gold` / `exact_match` as model features or provider prompt inputs.
- Treating oracle ceilings as deployable policy behavior.

## Remaining Non-Verifier Work

1. Paper/results section finalization.
2. Claim-artifact reproducibility table integration.
3. Optional provider/dataset replication.
4. Optional truly independent budget-4/8 rerun using hardened disjointness preflight.
5. Allocation-policy design and validation work.

## Reopen Criteria (Only If Needed)

Reopen verifier training only if one or more of the following occurs:

- Failure analysis shows verifier ranking errors are the dominant bottleneck.
- Additional labeled data reveals systematic missing error categories.
- New provider/dataset distribution causes verifier collapse.
- Review requirements demand stronger model ablations than current evidence provides.

## Closure Checklist

- [x] Label definition documented.
- [x] Model card updated and linked.
- [x] Training roadmap updated.
- [x] Leakage controls documented.
- [x] Selected model documented.
- [x] Downstream validation documented.
- [x] Uncertainty analysis documented.
- [x] Disjointness bug fixed and preflight enforcement wired.
- [x] Approved-use boundary documented.
