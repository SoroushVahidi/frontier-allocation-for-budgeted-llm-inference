# Current research handoff — frontier iteration 2 (2026-05-07)

**Branch:** `research-next-frontier-iteration-2`  
**Audience:** new researchers, fresh chat sessions, future-you.  
**Scope:** empirical status, safe claims, artifacts, and what to do next. This doc **supersedes** older entry points for **navigation** (history remains in timestamped `outputs/` and dated docs).

---

## A. Project purpose (one paragraph)

This repository studies **how to allocate a fixed inference budget** across reasoning branches and **how to commit a final numeric answer** from an explored frontier under explicit contracts. Live work now cleanly separates **discovery/coverage** (did the right answer ever enter the candidate set?) from **selection/commitment** (given candidates, what rule surfaces the final answer?). Do not collapse the project back into legacy “cheap vs revise” routing narratives.

---

## B. Current best method

| Field | Value |
|-------|--------|
| **Exact method ID** | `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` |
| **Shorthand** | **PAL + retry / guarded PAL** (diverse-root guarded stack + frontier tie-break + **PAL** branch + **empty-code PAL retry**) |
| **What “PAL + retry” means** | Program-aided numeric lane inside the guarded diverse-root controller; **retry** regenerates PAL when seed code is empty / non-executable within policy. This is **not** “PAL always wins”—execution output still passes through the same commitment / overlay / selector machinery as other peers. |

**Do not confuse with:** `strict_f3`, `strict_gate1_cap_k6`, or older strict-phased IDs—they remain **manuscript or historical references**, not the headline real-model PAL line.

---

## C. External baselines

| Baseline | Role |
|----------|------|
| **`external_l1_max`** | Primary strong external comparator on GSM8K-style real-model slices. |
| **`external_tale_prompt_budgeting`** | Token-budget-aware external protocol (TALE-style). |
| **`external_s1_budget_forcing`** | Budget-forcing external protocol. |
| **`external_l1_exact`** | Fairness / length-matched diagnostic variant—**not** interchangeable with `external_l1_max` as the single headline “beat L1” bar. |

---

## D. Current empirical situation

### D1. 300-case paired PAL+retry vs external L1

- PAL+retry: **252 / 300 = 84.00%**
- `external_l1_max`: **244 / 300 = 81.33%**
- Case gap: **+8** (**+2.67 pp**)
- McNemar *p* ≈ **0.322**
- Bootstrap paired-diff 95% CI for difference ≈ **[-2.00 pp, +7.33 pp]**

**Interpretation:** directionally ahead on this bundle; **not** statistically decisive; **no** claim of robust superiority.

### D2. 30-case 4-way pilot (PAL vs three externals)

Reported headline exact counts on the pilot slice:

| Method | Exact |
|--------|------:|
| PAL+retry | 17 / 30 (**56.7%**) |
| `external_l1_max` | 21 / 30 (**70.0%**) |
| `external_tale_prompt_budgeting` | 20 / 30 (**66.7%**) |
| `external_s1_budget_forcing` | 20 / 30 (**66.7%**) |

**Interpretation:** small slice where PAL trails each external—use only with bundle manifests; not a universal ranking.

### D3. 247-ID GSM8K-style collection (4-way)

From **`failure_collection_summary.json`** in the latest curated failure bundle:

- Evaluated rows: **247** cases; **245** have complete 4-way scoring (two timeouts on `external_l1_max`).
- Approximate exact rates:
  - PAL+retry: **189 / 247 ≈ 76.5%**
  - `external_l1_max`: **182 / 245 ≈ 74.3%**
  - TALE: **175 / 247 ≈ 70.9%**
  - S1: **184 / 247 ≈ 74.5%**

PAL vs best external on **245** complete rows:

| Outcome | Count |
|---------|------:|
| both correct | 183 |
| external-only (PAL wrong, some external correct) | 34 |
| PAL-only | 5 |
| both wrong | 23 |

**Interpretation:** PAL is **competitive as a single fixed method**, but **per-case best external** still exposes many PAL losses—failure mining is essential before claiming closure.

---

## E. Failure evidence collected

| Corpus | Role | Notes |
|--------|------|-------|
| **48-case failure book** (from 300-case PAL-loss set) | Structured audit of PAL losses vs externals | Tags include external-only vs both-wrong, gold-absent, gold-in-trace, pool presence (counts per mining reports). |
| **30-case 4-way pilot follow-up** | Adds pilot-specific PAL-loss cases | Includes additional discovery / present-not-selected style rows documented under `outputs/failure_case_corpus_20260507/`. |
| **45-case selected failure collection** | PAL wrong + outcomes bucketed | **34 preferred** (PAL wrong, ≥1 external correct), **11 secondary** (PAL wrong, all externals wrong). |
| **Preferred-failure mining (34)** | Mechanism tags for external-win losses | Recent counts: **`present_not_selected` 23 / 34 (~68%)**, **`gold_absent_discovery` 11 / 34 (~32%)** — shifts priority toward **Track B commitment** vs pure TRCE discovery on this slice. |

Canonical tables: `failure_cluster_summary.csv`, `failure_pattern_mining_report.md`, offline replay reports under the collect bundle.

---

## F. Current bottleneck

1. **Track B (priority for external-win PAL losses):** **present-not-selected** failures—gold-aligned evidence exists in trees/pools/histograms/overlay metadata, but **final commitment/surfacing** picks another numeric. Offline replay shows dominant **`overlay_previous_equals_gold_but_surface_used_bad_pal_stdout`**-style patterns and tie-break / histogram issues.
2. **Track A / TRCE:** Still essential for **`gold_absent_discovery`** and temporal/rate structured gaps, but **not** the majority of the newest preferred external-win set.

---

## G. Ideas tried and outcomes (high level)

| Direction | Outcome |
|-----------|---------|
| **PAL + empty-code retry** | Shipped in current best method ID; helps execution lane but does not solve commitment bugs alone. |
| **PAL execution → selector pool “poolfix”** | Little or no useful candidate merge; dominant failure unchanged in audits. |
| **Broad rate/ratio gate** | Coverage motion but **exact worsened**. |
| **Conservative rate/ratio gate** (`override_allowed=0`) | **Exact still worsened** — proves fragile gates risk regressions. |
| **Selector-isolated exploration logging** | **Exact worsened** because logging consumed **search/action budget**. |
| **Naive `max_answer_group_support` (offline)** | Fixes **16 / 23** present-not-selected targets but **flips ~39** “both correct” guardrail rows — **unsafe globally**. |
| **DR-heavy counterfactuals** | **112–113** guardrail flips — **unsafe**. |
| **`prefer_strong_pal_executable` (offline)** | **0 / 23** fixes on present-not-selected slice — PAL stdout can be confidently wrong (`1087`). |

---

## H. Next implementation candidate (pre-code)

**Track B design contract:** source-aware, answer-group-first **commitment** fixes—**overlay / tie-break / histogram / surfacing consistency**.  
**Status:** specification + offline fixtures exist; **runtime code not yet changed** for this contract.

Must pass **offline replay + guardrail budgets** before any implementation PR.

---

## I. Backup / parallel candidate

**Track A / TRCE:** structured discovery—static PAL validators, relation and quantity/state tracking, schema-triggered branching—for **gold-absent** temporal/rate failures; literature anchors include neural-symbolic MWP pipelines and decomposition patterns.

---

## J. No-go rules (until explicitly revised)

- No **broad** selector-visible pool injection “fixes.”
- No spending **search budget only for logging / exploration metadata.**
- No **broad rate/ratio gate** rerun without a new gated hypothesis and offline proof.
- No **statistical superiority** claims over `external_l1_max` from current paired CI / *p*-values.
- No **new paid API** batch until offline design + replay criteria pass (unless explicitly approved for a capped pilot).

---

## K. Artifact map (canonical vs local-heavy)

See **`docs/CURRENT_ARTIFACTS_INDEX_20260507.md`** for paths, tracked status, what to cite, and what must stay local-only (raw JSONL, huge CSVs).

---

## L. Tests and scripts

| Path | Purpose |
|------|---------|
| `scripts/build_failure_case_corpus.py` | Build failure corpus CSV/JSONL + summaries (**tracked**). |
| `scripts/materialize_cohere_4way_pilot_bundle.py` | Bundle pilot outputs (**untracked** locally—candidate for commit). |
| `scripts/collect_pal_failure_vs_externals.py` | Collect PAL vs external failure sets (**untracked**). |
| `scripts/materialize_failure_collection_bundle.py` | Materialize failure-collection bundle (**untracked**). |
| `tests/test_build_failure_case_corpus.py` | Corpus schema/tests (**passing**). |
| `tests/fixtures/present_not_selected_replay/` | Track B anchor fixtures (**untracked** locally). |
| `tests/test_present_not_selected_replay_fixtures.py` | Fixture/manifest schema tests (**passing**). |

---

## M. Exact current step

Repository **handoff polish** (this doc set + indices) and **pre-implementation Track B** artifacts (design contract + fixtures/tests already drafted). **No** new selector implementation merged yet.

---

## N. Next action

1. Read **`docs/CURRENT_ARTIFACTS_INDEX_20260507.md`** and **`outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/track_b_commitment_design_contract.md`** (local bundle; curated markdown safe to commit selectively).
2. Run offline policy simulations against **guardrail cohorts** until regression budgets are explicit.
3. Only then implement gated Track B changes behind flags + tests—not before.

---

## Related docs

| Doc | Use |
|-----|-----|
| **`docs/NEW_CHAT_STARTER_PROMPT_20260507.md`** | Paste into a new LLM session |
| **`docs/CURRENT_METHOD_STATUS_20260507.md`** | Method IDs and claim posture |
| **`docs/FAILED_DIRECTIONS_20260507.md`** | What not to repeat |
| **`docs/CLAIMS.md`** | Safe vs unsafe claims |
