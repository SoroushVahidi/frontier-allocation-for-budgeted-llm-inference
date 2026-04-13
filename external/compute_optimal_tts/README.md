# Compute-optimal test-time scaling (Snell et al., ICLR 2025)

- **Canonical paper (ICLR 2025):** *Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning*
- **Paper (OpenReview):** https://openreview.net/forum?id=4FWAwZtd2n
- **Official code from authors (Snell et al.):** **Not verified** on the OpenReview page snapshot checked for this repo; check the **camera-ready PDF**, **ICLR supplementary**, and **authors’ pages** before treating any repository as authoritative for this exact paper.

## Related public codebase (different paper title on GitHub)

The following repository is **widely used** for compute-optimal test-time scaling experiments and is **MIT-licensed** on GitHub, but its README titles a **different** paper (*“Can 1B LLM Surpass 405B LLM? Rethinking Compute-Optimal Test-Time Scaling”*). Use as a **related / implementation baseline** unless you independently verify equivalence or author endorsement.

- **Repository:** https://github.com/RyanLiu112/compute-optimal-tts
- **License (GitHub API, verification time):** **MIT**
- **Import status:** **Linked only** — no submodule, no vendored code in this repo.

## Role for this project

Baseline framing for **compute-optimal allocation of test-time inference** under budget (aligned with frontier allocation). Cite **Snell et al.** for the theoretical/methodological reference; cite **Liu et al. / upstream repo** only for results obtained with that codebase.

## Setup notes (upstream)

```bash
git clone https://github.com/RyanLiu112/compute-optimal-tts.git
```

## Integration scaffold (this repo)

- Registry entry: `configs/external_baselines_registry.json` → `compute_optimal_tts`
- This directory contains **documentation only**.
