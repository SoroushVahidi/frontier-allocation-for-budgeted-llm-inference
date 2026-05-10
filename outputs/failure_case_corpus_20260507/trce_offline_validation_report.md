# TRCE Offline Precondition + Regression-Trap Review

Generated offline from corpus artifacts only (no API calls, no code changes).

---

## A. Hypothesis restatement

**Temporal-Rate Coverage Expansion (TRCE)** targets the intersection of:

- `outcome_bucket = external_only` (PAL wrong, external branch correct),
- `failure_stage = gold_absent_everywhere_detectable` (gold never appears in PAL-visible discovery artifacts),
- operation hints dominated by **temporal_change**, **rate_ratio**, and closely related **product/temporal** compositions.

The proposed remedy (conceptual only here) is a **bounded discovery-only auxiliary lane** that expands coverage for these structured problems, keeps diagnostics **off the selector-visible candidate pool** until acceptance checks pass, and avoids spending normal search/action budget on logging-only paths.

---

## B. Target case table

High-confidence TRCE seeds from `selected_discovery_hypothesis_checklist.md` (8 cases). All eight appear in `failure_cases.csv` / `failure_cases.jsonl` with `external_only`, `gold_absent_everywhere_detectable`, and non-empty `operation_hints` in the temporal/rate/product families.

| case_id | operation_hint_tags | gold_absent | candidate_diversity | PAL exec OK | retry empty-code ran | Offline verdict |
|---------|---------------------|-------------|---------------------|-------------|----------------------|-----------------|
| openai_gsm8k_773 | temporal_change | yes | 2 | yes | no | **pass** |
| openai_gsm8k_814 | rate_ratio\|temporal_change | yes | 2 | yes | no | **pass** |
| openai_gsm8k_851 | product\|temporal_change | yes | 3 | yes | yes | **pass** |
| openai_gsm8k_995 | product\|temporal_change | yes | 2 | yes | no | **pass** |
| openai_gsm8k_1003 | product\|temporal_change | yes | 2 | no | yes | **pass** (discovery/exec deficit) |
| openai_gsm8k_1006 | rate_ratio\|total_sum | yes | 3 | no | yes | **pass** (modeling/exec deficit) |
| openai_gsm8k_1027 | rate_ratio | yes | 2 | yes | no | **pass** |
| openai_gsm8k_1029 | temporal_change | yes | 2 | yes | no | **pass** |

**Target slice passing structured offline characterization:** **8 / 8**.

---

## C. Broader related case table

The checklist’s **12-case** neighborhood is `external_only` ∩ `gold_absent_everywhere_detectable`. Beyond the eight seeds, four additional corpus rows complete that slice:

| case_id | operation_hint_tags | Notes |
|---------|---------------------|-------|
| openai_gsm8k_829 | none | Still gold-absent discovery failure; weaker operation-tag alignment with TRCE |
| openai_gsm8k_841 | none | Raise/bonus arithmetic; tag mismatch vs pure temporal-rate |
| openai_gsm8k_875 | none | PAL modeling weakness; weak tag alignment |
| openai_gsm8k_906 | total_sum | Summation-heavy; partial alignment |

Ledger verdict for these four: **needs_manual_review** (still relevant to gold-absent external-only losses, but not all are temporal-rate-shaped).

---

## D. Regression guardrail table

### D.1 Failed gate / isolated-log anchors (local artifacts)

Sources:

- `outputs/offline_rate_ratio_gate_anchor_validation_20260507/`
- `outputs/offline_rate_ratio_conservative_gate_anchor_validation_20260507/`
- `outputs/offline_selector_isolated_exploration_log_anchor_validation_20260507/`

| case_id | Harm mechanism | Incumbent → perturbed prediction (from reports) | TRCE expectation |
|---------|----------------|-----------------------------------------------------|------------------|
| openai_gsm8k_1025 | Broad + conservative **rate_ratio_gate** added candidates | Exact 1→0 (`23`→`21`) | **must_not_change** |
| openai_gsm8k_780 | Same gates | Exact 1→0 (`1`→`-2`); gold was even **in selector pool** | **must_not_change** |
| openai_gsm8k_979 | Same gates | Exact 1→0 (`3`→`4`) | **must_not_change** |
| openai_gsm8k_979 | Isolated **exploration_log** (`unit_rate_equation_v1`) | Exact 1→0 (`3`→`1`) | **must_not_change** |
| openai_gsm8k_812 | Isolated exploration log | Exact 1→0 (`73`→`74`) | **must_not_change** |
| openai_gsm8k_953 | Isolated exploration log | Exact 1→0 (`24`→`22`) | **must_not_change** |

**Sensitivity anchors (gate improved some rows):** `openai_gsm8k_819`, `openai_gsm8k_929` — prove selector/pool coupling even without explicit override.

**Stable anchors (reports):** e.g. `openai_gsm8k_778` stable across probes; use as **previously_correct_anchor** / comparator baselines.

### D.2 Previously correct cases from the 300-case PAL-retry run

From `statistical_summary.json`: **29** PAL-only wins · **223** both-correct · retry ran only **16 / 300** times.

Representative **PAL-only** temporal/rate-like IDs (keyword heuristic on `paired_casebook.csv`): **16** rows — ledger lists five exemplars (`774`, `817`, `845`, `924`, `975`).

Representative **both-correct** temporal/rate-like exemplars: `777`, `784`, `803` (among **125** keyword-matching both-correct rows).

---

## E. Failed-direction lessons incorporated

1. **Broad rate_ratio gate:** 12/12 anchors triggered; pool coverage rose but **exact regressed** (`summary.json`: incumbent exact 4/12 → new 3/12). **Lesson:** naive candidate injection perturbs selection even when diagnostics look favorable.
2. **Conservative gate (`override_allowed=0`):** **Still** 3 regressions on previously-correct incumbents (`report.md`). **Lesson:** “no override” does **not** imply selector-neutral pool expansion.
3. **Selector-isolated exploration logging:** `selector_visible_count_total = 0` yet **prediction_changed_count = 6**, **regressions_on_prev_correct = 3** (`summary.json`). **Lesson:** logging/exploration paths remain coupled to tree growth, priorities, or budgets despite hiding candidates from the selector UI channel.

**No-go implications for TRCE design:**

- No **selector-visible pool injection** by default; no “quiet” promotion without offline acceptance.
- No coupling where **diagnostic branches steal depth/actions** from the incumbent trajectory while the feature is meant to be off or diagnostic-only.
- Treat **rate-like triggers** as high-risk: prior gates fired universally on the anchor slice.

---

## F. Offline precondition results (Section 5 checklist)

| Precondition | Result | Evidence |
|--------------|--------|----------|
| ≥6 targets with temporal/rate structure + gold-absent discovery failure | **Pass** | **8/8** targets: `failure_stage = gold_absent_everywhere_detectable` and hints include `temporal_change`, `rate_ratio`, or `product|temporal_change` |
| ≥4 targets where external reasoning exposes a reusable structural clue absent from PAL candidates | **Pass (operationalized offline)** | For all eight targets, **gold answer does not appear among PAL candidate normalized answers** while `external_exact = 1` and `external_discovery_trace` is non-empty in `failure_cases.jsonl` — i.e., external search reaches the gold grouping PAL never materializes |
| TRCE expressible **without** selector-visible pool injection | **Pass (design-level)** | Matches checklist concept: auxiliary lane + offline acceptance before promotion |
| TRCE expressible **without** consuming normal search/action budget **only** for logging | **Pass (intent)** | Requires implementation proof via replay (not yet executed here) |
| Guardrail cases identified **before** implementation | **Pass** | Ledger + Sections D–E document anchors and PAL/both-correct exemplars |

**Checklist “minimum evidence before implementation” (hypothesis file §4–6):** **Not satisfied yet** — frozen guardrail suite must pass with zero regressions under default-off toggles; prior gate/log experiments **failed** keep criteria.

---

## G. Pass / fail decision (implement TRCE later or not yet)

**Characterization preconditions for TRCE:** **PASS** — the slice is coherently defined, anchored in corpus metrics, and externally differentiated from PAL candidates on all eight seeds.

**Implementation / pilot readiness:** **NOT YET** — historical offline validations show **any pool-adjacent or exploration-adjacent perturbation can regress exact matches** even when selectors ostensibly stay isolated.

**Net recommendation:** **Do not implement TRCE now.** Proceed with **offline replay specifications + guardrail harness** before writing controller code.

---

## H. If / when preconditions pass — exact implementation constraints

Derived from `selected_discovery_hypothesis_checklist.md` and failed probes:

1. **Default-off** feature flag; no selector-visible candidate mutation when disabled.
2. **Separate bounded budget lane** for temporal/rate discovery expansion — not billed against normal frontier/search accounting unless explicitly promoted.
3. **Non-selector-visible storage first** for diagnostics and candidate sketches; promotion only after offline/unit acceptance (schema compatibility, no pool delta under diagnostic-only mode).
4. **Regression suite mandatory:** union of ledger **must_not_change** IDs + anchor CSV suites used in gate validations.
5. **Hard stop conditions:** `prediction_changed_count > 0` with feature off; `regressions_on_prev_correct > 0`; selector-visible pool deltas under diagnostic-only mode; unexplained action-budget increases on baseline replay.

---

## I. If characterization passes but implementation fails — what analysis is missing

1. **Simulator replay proofs** that TRCE diagnostics **do not change** branch priorities, duplicate suppression, or tie-break metadata when disabled.
2. **Explicit accounting model** showing auxiliary expansions cannot shorten incumbent paths or exhaust shared caps (the failure mode hinted by isolated-log regressions despite `selector_visible_count = 0`).
3. **Trigger specificity study** so temporal-rate lanes do not replicate the **100% trigger rate** seen on rate-ratio anchors (`trigger_rate = 1.0` in conservative summary).
4. **Per-case differential diagnosis** on targets mixing **PAL exec failures** (`1003`, `1006`) vs pure coverage gaps — TRCE may need distinct sub-handlers.

---

## J. Whether API is needed now

**No.** Hypothesis checklist and statistical summaries already rule out a capped pilot until offline guardrails pass.

---

## K. Exact next action

Author an **offline replay test plan** (artifacts only) that:

1. Pins SHA256s for `paired_casebook.csv`, `pal_results.jsonl`, `external_l1_results.jsonl`, and the three anchor validation directories (already recorded in `feature_summary.json` manifest).
2. Defines **pass predicates** matching Section “Regression traps” in the checklist (prediction stability with flag off; zero pool deltas in diagnostic-only mode).
3. Only after those predicates pass on stored traces should TRCE controller changes be drafted — still **without** API spend until unit/offline replay gates succeed.

---

## Output artifacts

| File | Purpose |
|------|---------|
| `outputs/failure_case_corpus_20260507/trce_offline_validation_ledger.csv` | Per-case ledger (targets, broader slice, guardrails, exemplars) |
| `outputs/failure_case_corpus_20260507/trce_offline_validation_report.md` | This report |

---

## Summary counts (for downstream tracking)

| Metric | Value |
|--------|-------|
| Target cases passing offline characterization | **8 / 8** |
| Broader related rows (12-case slice remainder) | **4** |
| Strict regression guardrails (documented harm) | **5** unique IDs (`1025`, `780`, `979`, `812`, `953`; `979` counts once) |
| Failed-gate anchor rows in ledger | **5** (`819`, `929`, `778`, `934`, `944`) |
| Previously correct exemplar rows (PAL-only + both-correct samples) | **8** |
| Total distinct ledger rows | **30** |
