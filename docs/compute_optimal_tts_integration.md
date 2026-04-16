# compute_optimal_tts integration note (reviewer-defensible)

## Scope

This note defines the repository's conservative integration status for `compute_optimal_tts`.

## 1) Target baseline identity in this repo

- **Title:** *Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning*
- **Venue:** ICLR 2025
- **OpenReview:** https://openreview.net/forum?id=4FWAwZtd2n

## 2) Provenance status in this pass

Linked code in registry:

- https://github.com/RyanLiu112/compute-optimal-tts

What is audited now:

- Local clone provenance (HEAD commit, README identity, license presence).
- Optional online cross-linkage signals from OpenReview / project page / linked repo README.

Canonical automation:

- `scripts/verify_compute_optimal_tts_provenance.py`
  - supports `--check-online` for networked signal checks.

Conservative outcome remains:

- `paper_repo_match_strength = weak`
- `official_for_target_paper = unverified`

## 3) Integration outcome

**Status: `blocked`.**

Why still blocked:

1. official paper↔repo mapping for OpenReview `4FWAwZtd2n` is not author-verified,
2. linked stack is heavyweight and not mapped to this repo's native evaluation path,
3. fair matched-cost adapter protocol is not yet implemented for this baseline.

## 4) Strengthened blocker package added

- `scripts/verify_compute_optimal_tts_provenance.py`
- `scripts/generate_compute_optimal_tts_blocker_report.py`
- `outputs/external_baseline_completeness/compute_optimal_tts_status.json`
- `outputs/external_baseline_completeness/compute_optimal_tts_status.md`

The status JSON now includes an **exact future official-import contract** (required files, metadata schema, results schema, and scope label) so unblocking criteria are explicit and auditable.

## 5) Manuscript-safe guidance

Safe now:

- Discuss as adjacent compute-optimal framing baseline.
- Report that provenance and fair adaptation remain unresolved.

Not safe now:

- Claim runnable empirical integration in this repo.
- Claim official reproduction for the OpenReview target paper.

## 6) Exact next step

- Pin author-verified official code release (or explicit author confirmation) for OpenReview `4FWAwZtd2n`, then implement strict official-import validation against the documented contract on shared prompts and matched cost accounting.
