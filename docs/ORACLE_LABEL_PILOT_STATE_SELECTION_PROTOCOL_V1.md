# Oracle-label pilot state-selection protocol v1

## Purpose

This protocol defines how to build the **pilot input state manifest** (no oracle labels yet) for the first heavy oracle-label run.

It bridges the current default stop-vs-act pipeline to the future oracle teacher stage.

---

## 1) What is a “state” for this pilot?

A pilot state is one candidate stop-vs-act decision row corresponding to:
- one simulation snapshot,
- one `current_branch_id` under consideration at that snapshot,
- one budget context (`budget`, `remaining_budget`),
- and one source seed/run provenance.

In this repo, this maps directly to a row emitted by `build_stop_vs_act_dataset(...)` with keys `(source_seed, budget, episode_id, decision_id, branch_id)`.

---

## 2) Source pipeline(s)

Pilot candidates are extracted from the existing default stop-vs-act data path:
- `experiments.stop_vs_act_controller.build_stop_vs_act_dataset`
- `target_mode = proxy_best_other_gain` (anchor baseline context)

No oracle computation is performed during state extraction.

---

## 3) Decision points to capture

Capture branch-level decision candidates at multi-branch decision steps (the same points that currently produce stop-vs-act training rows).

Exclude points that are not valid branching choices (e.g., terminal/single-branch-only contexts where stop-vs-act choice is not meaningful).

---

## 4) Deduplication

Deduplicate candidates by strict identity key:
- `source_seed`
- `budget`
- `episode_id`
- `decision_id`
- `branch_id`

If duplicates appear, keep the first deterministic occurrence after stable sort by key.

---

## 5) Stratification protocol

Stratify selected states by:

1. **Budget**: strict budget strata for `{10, 14}`.
2. **Ambiguity / difficulty**: bucket by `abs(gap_to_best_other_gain)` within each budget:
   - `high` ambiguity = lowest third (closest to tie),
   - `medium` ambiguity = middle third,
   - `low` ambiguity = highest third.
3. **Uncertainty**: `uncertain` vs `certain` from `is_uncertain`.

Final stratum tag:
`budget=<b>|ambiguity=<high|medium|low>|uncertainty=<uncertain|certain>`.

---

## 6) Target-size allocation (~1200)

Use total target `1200` states with equal budget share:
- `600` from budget `10`,
- `600` from budget `14`.

Within each budget:
- allocate as evenly as possible across 6 strata (3 ambiguity × 2 uncertainty),
- if a stratum is underfilled, redistribute remaining quota within the same budget to other available strata,
- if budget-level quota is still infeasible, record shortfall in metadata (do not silently backfill across budgets unless explicitly configured).

---

## 7) Required metadata per selected state

Each selected state must store at least:
- `state_id` (deterministic),
- source provenance: `source_pipeline`, `source_seed`, `budget`, `episode_id`, `decision_id`, `current_branch_id`,
- context: `remaining_budget`, `split`,
- stratification tags: `ambiguity_bucket`, `uncertainty_bucket`, `stratum_tag`,
- lightweight proxy info: `label_act_proxy`, `delta_mean_proxy`, `delta_std_proxy`, `delta_sign_flip_rate_proxy`,
- selected feature snapshot (current stop-vs-act feature family),
- extraction metadata: `selection_name`, `selection_seed`, `selected_rank_in_stratum`.

This is enough to reproduce oracle-label generation input and auditing.

---

## 8) Exclusions

Exclude states with:
- missing or non-finite core numeric fields,
- invalid branch identity fields,
- contexts flagged as non-branching/terminal extraction artifacts,
- malformed uncertainty or proxy-label fields.

Do **not** exclude uncertain or ambiguous states by default; these are important for oracle supervision value.

---

## Why this extraction step matters

Before heavy compute, this step ensures:
- the pilot input set is deterministic,
- stratification is explicit,
- provenance is auditable,
- and heavy oracle labeling runs can be repeated on the exact same state manifest.

It prevents a moving-target pilot definition and supports clean post-hoc comparisons.
