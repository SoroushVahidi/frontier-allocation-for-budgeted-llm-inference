# compute_optimal_tts external baseline note

## Target paper tracked by this repository

- **Title:** *Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning*
- **Venue:** ICLR 2025
- **OpenReview:** https://openreview.net/forum?id=4FWAwZtd2n
- **Status of official code for this exact paper (in this repo's audit):** **unverified**

## Linked public code currently in registry

- **Repo:** https://github.com/RyanLiu112/compute-optimal-tts
- **Repo self-described paper:** arXiv `2502.06703` (*Can 1B LLM Surpass 405B LLM? Rethinking Compute-Optimal Test-Time Scaling*)
- **License:** MIT

### Why this matters

This linked repo is clearly valuable and related, but the paper-repo identity for the exact ICLR target paper above is not verified in this repository.

So this baseline is **not treated as official-reproduction-ready** here.

## Pinned provenance snapshot used in this repo pass

- **Observed HEAD commit in local audit clone:** `0ee2578af1f8d6cac445c9c4c72780528bb94556`
- **Clone command:**

```bash
git clone --depth 1 https://github.com/RyanLiu112/compute-optimal-tts.git .tmp_compute_optimal_tts
```

> Pinning this commit is for audit reproducibility of this repo pass only; it does **not** establish official mapping to OpenReview `4FWAwZtd2n`.

## Integration decision in this repository

- **Classification:** `blocked`
- **Reason:** unresolved paper↔repo official mapping + no fair matched-cost adapter protocol yet.
- **Canonical integration doc:** `docs/compute_optimal_tts_integration.md`
- **Machine-readable status artifacts:**
  - `outputs/external_baseline_completeness/compute_optimal_tts_status.json`
  - `outputs/external_baseline_completeness/compute_optimal_tts_status.md`

## Non-overclaim policy

- Do not claim this baseline is implemented/runnable in this repo today.
- Do not claim official reproduction for Snell et al. ICLR 2025 from this linked repo unless author-level mapping is verified.
- Use as adjacent discussion baseline until provenance and fairness protocol are both upgraded.
