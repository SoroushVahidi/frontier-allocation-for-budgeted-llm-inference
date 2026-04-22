# Q* provenance and integration hardening pass (2026-04-22T01:37:36Z)

## Scope and objective

This document is the canonical provenance and manuscript-safety audit for:

- `qstar_deliberative_planning`
- Paper identity: *Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning

The purpose is to preserve scientific relevance while preventing overclaims about runnable integration or official reproducibility.

## Canonical paper identity (verified)

- **Title:** Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning
- **Authors:** Chaojie Wang, Yanchen Deng, Zhiyi Lyu, Liang Zeng, Jujie He, Shuicheng Yan, Bo An
- **Venue/year:** arXiv preprint (under review), 2024
- **Canonical paper URL:** https://arxiv.org/abs/2406.14283
- **PDF URL:** https://arxiv.org/pdf/2406.14283.pdf
- **DOI:** https://doi.org/10.48550/arXiv.2406.14283

## Official artifact discovery outcome (conservative)

### OpenReview
- **Found:** no verified OpenReview entry was confirmed in this pass.

### Official code repository
- **Found:** no verified official repository for this exact paper was confirmed in this pass.

### Official project page
- **Found:** no verified official project page was confirmed in this pass.

### Official checkpoints / released artifacts
- **Found:** no verified official checkpoints or reproducibility artifacts were confirmed in this pass.

### Verified code/artifact license
- **Found:** no verified official code/artifact license could be established because no verified official artifact endpoint was confirmed.

## Provenance strength assessment

- **Assessment:** `paper_verified_artifacts_unverified`
- **Practical interpretation:**
  - The paper identity itself is strong and unambiguous.
  - Runnable integration provenance is weak because no official code/artifact endpoint was verified.
  - This does not invalidate Q* as an important scientific neighbor; it prevents a reproducibility claim.

## Methodological relevance (what remains true)

Q* is conceptually close to this repository's reasoning-control direction because it frames multi-step reasoning as deliberative search over partial traces and uses value-like guidance for expansion decisions.

However, conceptual closeness is not equivalent to a runnable, fair, apples-to-apples baseline integration in this repository.

## Safe claims vs unsafe claims

### Safe to claim now

- Q* is a high-priority **direct-family conceptual neighbor** for fixed-budget branch reasoning discussions.
- The canonical paper and DOI are verified.
- In this repository, Q* is currently **discussion-only** with explicit integration blockers.
- No official code/artifact endpoint has been verified here for this exact paper.

### Unsafe to claim now

- That this repository reproduces Q* results.
- That an official Q* codebase/checkpoint set has been verified and imported.
- That Q* is currently runnable as an apples-to-apples empirical comparator in this repository.
- That conceptual similarity alone establishes control-space equivalence and empirical comparability.

## Recommended taxonomy classification

- **baseline id:** `qstar_deliberative_planning`
- **status:** `discuss_only`
- **control_equivalence:** `direct` (conceptual family)
- **operational integration state:** blocked pending verified official artifacts or a clearly caveated, auditable adapter protocol
- **clone_url:** `null`

## Why this is the most honest classification

1. It preserves the paper's relevance in the direct-family map.
2. It avoids implying runnable integration without verified official artifacts.
3. It keeps manuscript language defensible under reviewer scrutiny.
4. It enables future upgrade if and only if verifiable official resources appear.

## Upgrade gate (strict)

Q* can be upgraded above `discuss_only` only after all of the following are satisfied:

1. A verified official repo/project artifact endpoint for the exact paper is identified.
2. License terms are auditable for allowed use.
3. A reproducible import or adapter contract is added with explicit comparability scope.
4. Artifact-backed status files are generated and linked from the registry/docs.

Until then, discussion-only treatment with explicit blocker language is mandatory.
