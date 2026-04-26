# Zhang et al. (2020) — Distilling Effective Supervision From Severe Label Noise

**Paper:** https://openaccess.thecvf.com/content_CVPR_2020/papers/Zhang_Distilling_Effective_Supervision_From_Severe_Label_Noise_CVPR_2020_paper.pdf

## Summary
This paper is a major methodological reference for selective distillation under noisy or partially trusted supervision. It is not a direct stop-vs-act baseline, but it strongly shaped the project’s accepted / borderline / rejected supervision logic.

## Why it matters to this project
- It supports using a trusted slice rather than treating all labels equally.
- It supports weighting, relabeling, and selective trust rather than uniform hard-label imitation.
- It gives a principled precedent for our selective-distillation stage.

## How it relates to our method
- **Directness:** methodological idea source
- **Main contribution to our project:** trusted-slice supervision, selective weighting, and label-quality-aware student training.

## What we should use from it
- strong supervision on trusted examples
- weaker or more careful use of marginal examples
- avoiding uniform treatment of all oracle labels

## Current repo status
- Reference tracked
- BibTeX tracked
- Important methodology note for selective distillation
