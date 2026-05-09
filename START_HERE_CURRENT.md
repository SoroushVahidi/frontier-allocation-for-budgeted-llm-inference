# Start here — current front door (2026-05-07)

Short orientation for humans and agents. Historical timestamped material stays in place; **navigation truth** for frontier-iteration-2 is below.

## Latest local-only work (after pushed `bc693b8`)

Not on `origin` until you selectively commit: **GSM8K/PAL structural validator** + eval scripts (telemetry only—not a runtime ranker), **gold-absent schema mining** outputs + script, **target-staged PAL retry** unarmed pilot scaffold (manifest + prompts + tests), plus newer matched-50 / PAL-vs-production local artifacts from the frontier-iteration audit. See handoff **§ “Latest local work after bc693b8”** and the migration indexes below. Many local untracked paths were present during the migration audit; treat that count as volatile and re-check with `git status` before staging. Do **not** bulk-commit.

---

## Read this first

| Priority | Document |
|---------:|----------|
| **1** | **[`docs/CURRENT_RESEARCH_HANDOFF_20260507.md`](docs/CURRENT_RESEARCH_HANDOFF_20260507.md)** — purpose, PAL+retry headline results, failure mining, Track A/B bottlenecks, **pushed Track B caveat**, local validator/mining/pilot status, no-go rules |
| **2** | [`docs/CURRENT_ARTIFACTS_INDEX_20260507.md`](docs/CURRENT_ARTIFACTS_INDEX_20260507.md) — canonical vs local-heavy `outputs/` |
| **3** | [`docs/CLAIMS.md`](docs/CLAIMS.md) — safe vs unsafe claims |
| **4** | [`docs/CURRENT_METHOD_STATUS_20260507.md`](docs/CURRENT_METHOD_STATUS_20260507.md) — method IDs and roles |
| **5** | [`docs/references/external_baselines_references.md`](docs/references/external_baselines_references.md) — external methods/papers reference ledger |
| **6** | [`docs/MIGRATION_TRANSFER_INDEX_20260509.md`](docs/MIGRATION_TRANSFER_INDEX_20260509.md) — what must be committed, archived, or excluded before machine migration |
| **7** | [`docs/FAILURE_CASE_AND_API_ARTIFACT_INVENTORY_20260509.md`](docs/FAILURE_CASE_AND_API_ARTIFACT_INVENTORY_20260509.md) — failure-case and API-expensive artifact inventory |

### Curated artifact summaries (evidence trails)

| Artifact | Path |
|----------|------|
| 300-case paired analysis | [`outputs/pal_retry_300case_analysis_20260506/report.md`](outputs/pal_retry_300case_analysis_20260506/report.md) |
| Failure-pattern mining (latest collect bundle; **local until committed**) | `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/failure_pattern_mining_report.md` |
| Present-not-selected replay (same bundle) | `outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/present_not_selected_replay_report.md` |
| Discovery / TRCE checklist | [`outputs/failure_case_corpus_20260507/selected_discovery_hypothesis_checklist.md`](outputs/failure_case_corpus_20260507/selected_discovery_hypothesis_checklist.md) |
| Matched-50 frontier-iteration external suite comparison (**local artifact; not a blanket superiority proof over `external_l1_max`**) | `outputs/external_full_suite_matched50_comparison_20260508T222631Z/external_full_suite_summary.json` |

### Paste-ready session starter

[`docs/NEW_CHAT_STARTER_PROMPT_20260507.md`](docs/NEW_CHAT_STARTER_PROMPT_20260507.md)

---

## Do **not** start here for “current best method”

- **`strict_f3`** / **`strict_gate1_cap_k6`**-only harnesses and docs describe **historical strict-phase** surfaces—not the headline **PAL+retry** real-model line.
- Old **`START_HERE`** bullets that only cite **`k1_frontier4_frontier_tiebreak`** without **`_pal`** are **incomplete** for May 2026; use the method ID in **`CURRENT_RESEARCH_HANDOFF`**.

---

## One-line project question

Under explicit inference budgets, **where should the next unit of compute go**, and **how should the final answer be chosen** from the explored frontier—with discovery/coverage and selection/commitment treated separately?

---

## Current best internal method (engineering line)

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
```

Shorthand: **PAL + retry / guarded PAL**.

---

## Current external comparators

- **`external_l1_max`** — primary headline baseline.
- **`external_tale_prompt_budgeting`**, **`external_s1_budget_forcing`** — additional 4-way externals.
- **`external_l1_exact`** — fairness/diagnostic length contract — **not** the main headline comparator.

---

## Empirical snapshot (see handoff for nuance)

- **Matched-50 external suite (2026-05-08, same case IDs):** `production_equiv_v1` **36/50**; **`external_pal_pot_fair_v1` (PAL/PoT fair) 40/50** — currently the strongest *individual* external baseline on that slice; **`external_self_consistency_6_fair_v1` 36/50** (ties production_equiv). **Unsafe claim:** “beats all individual external baselines.” **Safe framing:** production_equiv beats L1/SC4/S1/TALE-EP, ties SC6, trails PAL/PoT on matched 50. Free-form retry and schema-grounded retry v1 are **negative diagnostics**, not integrated shippable methods. **Next:** expand a PAL-vs-production disagreement / PAL-only failure bank before a PAL-aware hybrid selector.
- **300-case paired:** PAL+retry **252/300** vs `external_l1_max` **244/300** — **directional** paired gap, **not** statistically decisive.
- **30-case 4-way pilot:** PAL trails each external on that small slice — **not** a universal ranking.
- **247-ID collection:** PAL competitive as one fixed method; **34** external-only losses motivate failure mining.

---

## Bottleneck today

1. **Track B:** **present-not-selected** / commitment / overlay / histogram / surfacing (priority for newest preferred external-win failures).  
2. **Track A / TRCE:** gold-absent structured discovery (still important; smaller share of newest preferred mining).

---

## Tests / fixtures worth running locally (no API)

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_build_failure_case_corpus.py
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_present_not_selected_replay_fixtures.py
# Local-only modules (after bc693b8; paths must exist in worktree):
PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_gsm8k_structural_validate.py \
  tests/test_gsm8k_structural_validator_eval.py \
  tests/test_target_staged_pal_pilot_manifest.py \
  tests/test_target_staged_pal_pilot_runner.py
```

---

## Older indexes (reference)

[`docs/CURRENT_APPROACHES_STATUS_20260505.md`](docs/CURRENT_APPROACHES_STATUS_20260505.md) · [`docs/METHOD_STATUS_TABLE.md`](docs/METHOD_STATUS_TABLE.md) · [`docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md`](docs/FAILED_AND_NEGATIVE_RESULTS_INDEX.md) · [`docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md`](docs/EXPERIMENT_EXECUTION_GUARDRAILS_20260504.md)

---

## Provenance

Timestamped directories under `outputs/` are scientific provenance—do not delete or reinterpret numerics without manifests.
