# Q* (deliberative planning) external baseline note

## Canonical paper identity (verified)

- **Title:** *Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning
- **Authors:** Chaojie Wang, Yanchen Deng, Zhiyi Lyu, Liang Zeng, Jujie He, Shuicheng Yan, Bo An
- **Venue/year:** arXiv preprint (under review), 2024
- **Canonical paper URL:** https://arxiv.org/abs/2406.14283
- **PDF:** https://arxiv.org/pdf/2406.14283.pdf
- **DOI:** https://doi.org/10.48550/arXiv.2406.14283

## Current status in this repository

- **Baseline id:** `qstar_deliberative_planning`
- **Baseline class:** direct-family conceptual neighbor
- **Current normalized status:** `discuss_only`
- **Operational integration state:** blocked pending verified official artifacts
- **Paper-phase priority:** essential

## Provenance findings (conservative)

At this time, this repository has **not** verified any of the following for this exact paper:

- official code repository,
- official project page,
- official checkpoints/artifacts,
- official code/artifact license.

No clone URL is recorded for this baseline in `configs/external_baselines_registry.json` unless official provenance is verified.

## Why Q* is conceptually close

Q* is methodologically close to this repo's problem family because it treats multi-step reasoning as deliberative search/control over partial reasoning traces, with value-like guidance for expansion decisions.

## Why runnable integration claims are still risky

Conceptual closeness is not enough to justify empirical runnable-baseline claims. Without verified official artifacts and a strict integration contract, claiming direct reproducibility would be misleading.

Therefore this baseline remains discuss-only with explicit blockers.

## Manuscript-safe wording

Use Q* as a direct-family conceptual reference and motivation anchor for deliberative reasoning control, while explicitly stating that this repository does not yet provide a verified official runnable integration for Q*.

## Canonical provenance audit for this pass

- `docs/QSTAR_PROVENANCE_AND_INTEGRATION_PASS_20260422T013736Z.md`
