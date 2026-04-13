# Majority-of-the-Bests (MoB) — Rakhsha et al.

- **Canonical title:** *Majority of the Bests: Improving Best-of-N via Bootstrapping* (NeurIPS 2025 presentation; OpenReview listing).
- **OpenReview:** https://openreview.net/forum?id=ZVtHNM3Dd2
- **NeurIPS2025 poster:** https://neurips.cc/virtual/2025/poster/117285
- **Code repository (author GitHub org; widely cited as implementation):** https://github.com/arakhsha/mob
- **License (GitHub API, verification time):** **MIT**
- **Paper license note:** OpenReview lists **CC BY-NC-SA 4.0** for the paper PDF; repository license is MIT — respect both when redistributing **paper text** vs **code**.
- **Import status:** **Linked only** — no submodule, no vendored code in this repo.
- **Official status note:** The arXiv abstract for this line of work should be cross-checked for an explicit “code at …” line; this README records the **author-affiliated** `arakhsha/mob` repo as the practical integration target. If the camera-ready or NeurIPS page lists a different URL, prefer that URL and update this file.

## Role for this project

MoB is a **test-time selection / Best-of-N improvement** baseline under imperfect reward models — relevant for comparing against verifier-guided search and frontier allocation.

## Setup notes (upstream)

```bash
git clone https://github.com/arakhsha/mob.git
```

(Git LFS may be required per upstream README.)

## Integration scaffold (this repo)

- Registry entry: `configs/external_baselines_registry.json` → `mob_majority_of_bests`
- This directory contains **documentation only**.
