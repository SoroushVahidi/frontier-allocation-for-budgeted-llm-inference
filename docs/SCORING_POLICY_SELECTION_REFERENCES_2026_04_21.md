# Scoring Policy Selection References (2026-04-21)

## Problem statement

Current repo failure analysis for finalized default `strict_gate1_cap_k6` shows a substantial in-tree selection issue:

- in the canonical hundred-case exact-loss analysis, many losses are `present_not_selected` (gold answer present in tree, wrong answer surfaced),
- this points to a selection/scoring/surfacing opportunity rather than pure tree-coverage failure.

This note records the reference families used to motivate a compact selection-policy upgrade experiment, and what was actually implemented.

## Implementation hypothesis used in this repo

Use answer-group-first selection with lightweight score shaping:

1. aggregate candidate evidence at final-answer group level,
2. combine support multiplicity with branch/node quality,
3. normalize/calibrate score contribution in near-tie settings,
4. apply robust tie-breaks favoring stable multi-branch evidence,
5. keep deterministic extraction/surfacing consistency checks.

The experiment remains training-free and bounded to the selection layer.

## Literature families and relevance

### 1) Self-consistency / answer aggregation
- **Wang et al., 2023, Self-Consistency Improves Chain of Thought Reasoning in Language Models**  
  [https://arxiv.org/abs/2203.11171](https://arxiv.org/abs/2203.11171)  
  Relevance: aggregate multiple reasoning traces at answer level instead of trusting a single top trace.

### 2) Verifier-based reranking
- **Cobbe et al., 2021, Training Verifiers to Solve Math Word Problems**  
  [https://arxiv.org/abs/2110.14168](https://arxiv.org/abs/2110.14168)  
  Relevance: final candidate selection can be improved by verifier-like reranking signals rather than raw generator score only.

### 3) Process supervision / PRM-style scoring
- **Lightman et al., 2023, Let's Verify Step by Step**  
  [https://arxiv.org/abs/2305.20050](https://arxiv.org/abs/2305.20050)  
  Relevance: process-aware quality signals can improve ranking and reduce brittle final-answer choice.

### 4) Calibration and confidence shaping
- **Guo et al., 2017, On Calibration of Modern Neural Networks**  
  [https://arxiv.org/abs/1706.04599](https://arxiv.org/abs/1706.04599)  
  Relevance: score normalization/calibration is a simple, defensible mechanism when raw scores are not directly comparable.

### 5) Grouped-answer selection and robust tie-break
- Broadly informed by ensemble aggregation and confidence-aware selection literature (including self-consistency and verifier reranking above): prefer robust multi-branch support under near ties instead of brittle single maxima.

## Implemented vs noted

Implemented in this repo experiment:
- answer-group support-only selection policy,
- answer-group support + node-score selection,
- answer-group support + calibrated score,
- answer-group support + calibrated score + tie-break cleanup,
- deterministic extraction/surfacing path retained with rescue behavior.

Not implemented in this experiment:
- heavy learned verifier retraining,
- full PRM/ORM retraining stack,
- changes to upstream search/expansion procedure.

## Scope boundary

Claims from this reference-guided update are limited to:
- current finalized default (`strict_gate1_cap_k6`),
- current evaluated exact-loss/failure surfaces,
- current selection-layer-only experiment.
