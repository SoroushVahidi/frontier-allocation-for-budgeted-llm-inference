# SEMANTIC_MINIMUM_MATURATION_CONTROLLER_DESIGN

## Candidate method name

`semantic_min_maturation_frontier_v1`

## Objective

Address absent-from-tree and immediate-miss failure mode where minimum depth over root branches does not guarantee exploration of semantically distinct reasoning regions.

## Core rule

1. Seed semantically distinct reasoning families at root.
2. Before adaptive scoring dominates, ensure each **viable** semantic family reaches `d_min` (`2` or `3`).
3. Redundant/paraphrased root branches do **not** count as separate families.
4. After semantic minimum maturation is satisfied, allocate remaining budget using existing frontier score/priority policy.
5. Block commit until one of:
   - (a) viable semantic families reach `d_min`,
   - (b) budget is exhausted,
   - (c) all under-depth families are invalid/unparseable,
   - (d) protected direct incumbent is high-confidence and challengers are weak.
6. Never use gold labels at inference time.

## Family construction (inference-time, deterministic)

Family signatures should combine lightweight features:
- normalized candidate answer (if present),
- operation type (`arithmetic`, `ratio/percent`, `algebraic`, `counting`, `units/rate`, `comparison`, `planning`, `science QA`, `unknown`),
- numeric quantity set,
- key reasoning verb patterns,
- similarity over first 1–2 reasoning steps,
- existing prompt/style/family IDs when available.

## Viability filters

A family can be marked temporarily non-viable if:
- malformed/unparseable generations persist,
- repeated empty/no-op steps exceed threshold,
- contradiction/invalid-state detectors trigger repeatedly,
- branch quality proxy remains below a hard floor for `k` attempts.

## Allocation schedule sketch

- **Phase 0 (seed):** diversify root proposals; deduplicate into families.
- **Phase 1 (semantic maturation):** round-robin or deficit-based expansion among under-depth viable families until `d_min` or stop condition.
- **Phase 2 (adaptive frontier):** revert to existing scorer-based expansion/verification and commit logic.
- **Phase 3 (finalization):** optional direct-incumbent protection and output repair under existing deterministic rules.

## Proposed ablation plan

Evaluate alongside canonical methods:
- `strict_f3`
- `strict_f2`
- `strict_gate1_cap_k6`
- `external_l1_max`
- `semantic_min_maturation_frontier_v1_d2`
- `semantic_min_maturation_frontier_v1_d3`
- `semantic_min_maturation_plus_direct_reserve_v1`

## Required diagnostics for go/no-go

1. Family diversity and redundancy in immediate_miss-labeled slice.
2. Correct-region family depth attainment (`>=2`, `>=3`) before commit.
3. Budget tradeoff vs strict baselines at 4/6/8 actions.
4. Error decomposition shift among:
   - immediate_miss,
   - partial_progress,
   - near_miss_absent_final,
   - present_but_misselected.

## Non-goals for this phase

- No modifications to canonical methods yet.
- No expensive reruns.
- No external API calls in audit path.
