# Current research handoff — frontier iteration 2 (2026-05-07)

**Branch:** `research-next-frontier-iteration-2`  
**Remote `HEAD`:** `bc693b8` — *Track B: opt-in commitment gate and evaluator skip*  
**Audience:** new researchers, fresh chat sessions, future-you.  
**Scope:** empirical status, safe claims, what is **pushed** vs **local-only**, and what to do next.

---

## Latest local work after `bc693b8` (not pushed; large `outputs/` still untracked)

The following exists in the worktree but is **not** on `origin` as of this cleanup pass—treat paths as **local until selectively committed**:

| Area | Status |
|------|--------|
| **Track B** | **Pushed:** opt-in method `…frontier_tiebreak_pal_track_b_commitment_v1` + evaluator fix so overrides control scored finals. **Causal benefit not established** (30-case A/B drift; 0 helpful / 1 harmful override before fix; see pushed commit message / prior notes). **No larger live run** until cached/interleaved design. |
| **GSM8K / PAL structural validator** | **Local code:** `experiments/gsm8k_structural_validate.py`, batch script `scripts/evaluate_gsm8k_structural_validator.py`, Track A diagnostics `scripts/track_a_discovery_diagnostics.py`, static PAL audit `scripts/pal_code_static_audit.py`, tests. **Finding:** universal `structural_score` is **not** a useful Track B ranker; stratified means ~flat (gold vs non-gold ~0.786 vs ~0.780); PN-comparable PAL-internal slice showed **no** gold-beats-wrong separation. **Conclusion:** keep as **telemetry / offline tooling**; **do not** wire into runtime selection or retry without new evidence. |
| **Schema mining (gold-absent / external-correct)** | **Local:** `scripts/mine_gold_absent_external_schema.py` + bundle under `outputs/gold_absent_external_success_schema_mining_20260507/`. **21** inspected discovery-style cases → **11** primary external-correct. **Strongest repeated schema:** `multi_step_chain`. Frequent: `aggregation_total`, `temporal_state_update`, `difference_comparison`, `rate_equation`, `target_mapping_error`. PAL failures: `wrong_operator`, `arithmetic_from_wrong_relation`, `wrong_target_variable`, failed/empty code. |
| **Target-staged PAL retry pilot (scaffold)** | **Local:** manifest `manifests/target_staged_pal_retry_primary_11_20260507.json`, prompts `prompts/target_staged_pal_retry/user_template_*.md`, dry-run + runner modules, mock-only tests. **`api_execution_enabled`: false**; live Cohere only with **`--execute-api`** *and* manifest flag true. **Hard cap** 120 logical calls; **11** primary case IDs tied to schema-mining CSV. |
| **API policy for repo hygiene** | **No API** for documentation/cleanup passes. When needed later: Cohere/HF allowed only under **explicit capped plans**; pilot runner stays **unarmed** by default. |

Single navigation index for heavy folders → **`docs/CURRENT_ARTIFACTS_INDEX_20260507.md`**.

---

## A. Best method and best paired 300-case result

| Field | Value |
|-------|--------|
| **Exact method ID** | `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` |
| **Shorthand** | **PAL + retry / guarded PAL** |

**300-case paired GSM8K (Cohere):**

- PAL+retry: **252 / 300 = 84.00%**
- `external_l1_max`: **244 / 300 = 81.33%**
- Gap: **+8** cases (**+2.67 pp**)
- McNemar *p* ≈ **0.322**
- Bootstrap 95% CI for paired diff ≈ **[-2.00 pp, +7.33 pp]**

**Interpretation:** directionally ahead on this bundle; **not** statistically decisive; **no** claim of robust superiority.

---

## B. External baseline comparisons (include 30-case 4-way caution)

**Primary headline comparator:** `external_l1_max`.

Also used in 4-way slices: `external_tale_prompt_budgeting`, `external_s1_budget_forcing`. `external_l1_exact` is **diagnostic / fairness**—not the main “beat L1” bar.

**30-case 4-way pilot (small *n*—diagnostic only):**

| Method | Exact |
|--------|------:|
| PAL+retry | 17 / 30 |
| `external_l1_max` | 21 / 30 |
| TALE | 20 / 30 |
| S1 | 20 / 30 |

**Interpretation:** on this slice PAL trails each listed external—**do not** treat as universal ranking; use only with bundle manifests.

---

## C. Failure corpus counts and dominant patterns

**247-ID GSM8K-style 4-way collection** (from curated failure bundle summaries):

- PAL+retry ≈ **189 / 247**; externals **175–184 / 245–247** depending on row completeness.
- **34** “external-only” (PAL wrong, ≥1 external correct) on complete rows; **5** PAL-only; **23** both wrong; **183** both correct (approximate—see bundle `failure_collection_summary.json`).

**Preferred-failure mining (34):** **`present_not_selected` ~23 / 34**; **`gold_absent_discovery` ~11 / 34** → prioritizes **Track B commitment** mechanics on this slice vs pure TRCE discovery.

---

## D. Track B implementation status and causal caveat

- **In `bc693b8` (pushed):** opt-in method  
  `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_track_b_commitment_v1`  
  plus **evaluator-layer** behavior so Track B overrides can control **scored** final answer.
- **Offline replay (tightened):** small counts of target fixes vs guardrail flips (see local/offline notes in collect bundle).
- **Live 30-case A/B:** score motion **not** attributed to clean causal overrides (helpful overrides **0**, harmful **1** before evaluator fix; post-fix evaluation posture improved but **larger proof still missing**).
- **Conclusion:** gate is **implemented and test-covered**, but **causal benefit is not established**. **No** large paid rerun until **cached / interleaved** design and pre-registered success criteria.

---

## E. Validator / “Combinatorial Opt Agent”-inspired work — not a runtime policy (yet)

- **Artifacts (local):** `experiments/gsm8k_structural_validate.py`, `scripts/evaluate_gsm8k_structural_validator.py`, `scripts/track_a_discovery_diagnostics.py`, `scripts/pal_code_static_audit.py`, `outputs/gsm8k_structural_validator_eval_20260507/`.
- **Result:** static / structural signals are **weak discriminators** for gold-absent discovery and **failed** scaled implementation thresholds (e.g. no trigger met “≥20% gold_absent and ≤5% guardrail-FP” band).
- **Decision:** treat as **offline telemetry and design exploration**; **do not** promote to runtime **ranker, gate, or retry trigger** without a new hypothesis and offline proof.

---

## F. Schema mining and target-staged PAL retry rationale

- **Evidence:** gold-absent / external-success inspection → **`multi_step_chain`** is the strongest recurring schema; failures cluster around **wrong operator**, **wrong relation arithmetic**, **wrong target variable**, and **empty / failed code**.
- **Algorithmic idea (next concrete experiment):** force explicit **target + units + staged subgoals** before PAL **Python** (inspired by “formulation before solve” / Combinatorial Opt Agent-style structured metadata).
- **Scaffold (local, unarmed):** 11-case pilot manifest + `user_template_no_external_v1.md` + dry-run + gated Cohere runner + mock tests. See **`docs/TARGET_STAGED_PAL_RETRY_EXPERIMENT_PLAN_20260507.md`**.

---

## G. What should be committed next (suggested stack; **do not** bulk-add `outputs/`)

1. **Handoff / index refresh** — this file + `START_HERE_CURRENT.md` + `docs/NEW_CHAT_STARTER_PROMPT_20260507.md` + small updates to `docs/CURRENT_METHOD_STATUS_20260507.md`, `docs/CURRENT_ARTIFACTS_INDEX_20260507.md`, `docs/FAILED_DIRECTIONS_20260507.md` (see commit **F** in cleanup report).
2. **Validator + offline tooling** — core module, eval script, diagnostics/audit scripts, tests, plan doc (commit **G**).
3. **Schema mining + target-staged scaffold** — mining script, manifest, prompts, experiments, tests, optional **small** curated CSV under `data/` or documented path (commit **H**). **Avoid** raw JSONL / full validation dumps.

---

## H. What should remain local-only

- **Full** `outputs/cohere_real_model_cost_normalized_validation_*` trees, large **`per_example_records.jsonl`**, duplicated analysis CSVs, ad-hoc timestamped docs under `docs/COHERE_*` unless curated to one summary.
- **Entire** `outputs/` bundles **except** selectively curated `report.md` / small JSON summaries agreed for the paper or regression baselines.
- **`local_patches/`** and machine-specific notes.
- Environment secrets (never commit `.env` with keys).

---

## I. What not to redo

- Claim **decisive** superiority vs `external_l1_max` from current CI / *p*-values.
- **Broad** pool injection, **broad** rate/ratio gates, **selector-isolated logging** that spends search budget, **global** unsafe offline counterfactuals (`max_answer_group_support`, DR-heavy finals, blind PAL priority)—see **`docs/FAILED_DIRECTIONS_20260507.md`**.
- Promote **structural validator score** or **static-audit triggers** to **runtime** policy without new offline calibration.
- Run **large live** Track B or pilot batches **without** capped design and manifest discipline.

---

## J. Exact next technical step

1. **Commit organization:** handoff doc refresh first (**F**), then validator toolchain (**G**), then schema-mining script + target-staged scaffold + **vendored small inputs** (**H**)—each reviewed separately; **no** mass staging of `outputs/`.
2. **Pilot prep:** review target-staged manifest + dependency on `schema_mining_cases.csv` (today under `outputs/…`—prefer **moving a minimal copy** to a tracked `data/` path so clones work).
3. **Track B:** if more live work—only under **interleaved/cached** design; pre-register success metrics; keep manifest `api_execution_enabled` **false** until intentional pilot.
4. **Science:** treat **target-staged PAL retry** as the **next bounded experiment** motivated by mining—not a proven fix.

---

## Related docs (navigation)

| Doc | Use |
|-----|-----|
| **`START_HERE_CURRENT.md`** | Short entry |
| **`docs/CURRENT_ARTIFACTS_INDEX_20260507.md`** | Canonical vs local-heavy |
| **`docs/CURRENT_METHOD_STATUS_20260507.md`** | Method IDs / claim posture |
| **`docs/FAILED_DIRECTIONS_20260507.md`** | Negative results |
| **`docs/NEW_CHAT_STARTER_PROMPT_20260507.md`** | Paste into new LLM session |
| **`docs/TARGET_STAGED_PAL_RETRY_EXPERIMENT_PLAN_20260507.md`** | Pilot design |
| **`docs/GSM8K_PAL_STRUCTURAL_VALIDATOR_PLAN_20260507.md`** | Validator rationale |

---

## Historical sections (compressed)

**Project purpose:** allocate fixed inference budget across branches; separate **discovery/coverage** from **selection/commitment**. Do not collapse into legacy cheap-vs-revise routing.

**Track A / TRCE:** still relevant for **gold_absent_discovery**; smaller share of newest preferred external-win failures vs **present_not_selected**.

**Artifact map detail:** timestamped `outputs/` are provenance—cite summaries and manifests, not anecdotes.
