# compute_optimal_tts integration note (reviewer-defensible)

## Scope

This note defines the repository's conservative integration status for `compute_optimal_tts`.

## 1) What baseline this is supposed to correspond to

Target paper in this repository:

- **Title:** *Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning*
- **Venue:** ICLR 2025
- **OpenReview:** https://openreview.net/forum?id=4FWAwZtd2n

## 2) Current paper↔repo provenance truth status

Linked code in registry:

- https://github.com/RyanLiu112/compute-optimal-tts

What is verified in this pass:

- The linked repo self-identifies with arXiv **2502.06703** (*Can 1B LLM Surpass 405B LLM? Rethinking Compute-Optimal Test-Time Scaling*).
- The target paper for this repository is OpenReview **4FWAwZtd2n** (Snell et al., ICLR 2025).
- Therefore, for this repository's target baseline, paper↔repo identity is **not verified as official/equivalent**.

Conservative provenance label used now:

- **`paper_repo_match_strength = weak`**
- **`official_for_target_paper = unverified`**

## 3) Can a fair in-repo adapter be treated as feasible now?

**Current answer: no (blocked).**

Main blockers:

1. Provenance blocker:
   - Official code mapping for the exact target paper is not established.
2. Execution blocker:
   - Linked repo requires heavy multi-GPU and serving stack (vLLM, Ray, FastChat, PRM serving, tmux orchestration).
3. Fairness blocker:
   - No manuscript-safe matched protocol has been implemented yet for shared prompts, shared cost accounting, and comparable action space against this repo's frontier-allocation substrate.

## 4) Integration outcome in this pass

Outcome chosen: **OUTCOME B (strong protocol + blocker package)**.

Implemented in this repo:

- `scripts/verify_compute_optimal_tts_provenance.py`
  - records auditable provenance signals (paper target, linked repo identity, local pinned commit if clone exists).
- `scripts/generate_compute_optimal_tts_blocker_report.py`
  - generates manuscript-safe status artifacts under `outputs/external_baseline_completeness/`.
- Required status artifacts:
  - `outputs/external_baseline_completeness/compute_optimal_tts_status.json`
  - `outputs/external_baseline_completeness/compute_optimal_tts_status.md`

## 5) Current classification

- **Classification:** `blocked`
- **Why:** unresolved paper↔repo provenance + heavy upstream stack + no fair matched protocol yet.

## 6) Manuscript guidance now

Safe now:

- Discuss as an adjacent compute-optimal framing baseline.
- Cite the target paper and separately label linked repo evidence as related unless author-official mapping is confirmed.

Not safe now:

- Claim runnable empirical integration in this repository.
- Claim official reproduction for Snell et al. ICLR 2025 baseline.

## 7) Exact next step to strengthen later

Single concrete next step:

- **Pin author-verified official code release for OpenReview 4FWAwZtd2n (or explicit author confirmation), then implement an import-only adapter protocol over shared prompts and matched cost accounting before empirical claims.**
