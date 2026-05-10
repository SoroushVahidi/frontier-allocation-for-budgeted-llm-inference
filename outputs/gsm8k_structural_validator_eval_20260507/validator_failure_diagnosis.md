# GSM8K structural validator — failure diagnosis (batch v1)

Offline analysis only; no code changes in this step.

This document explains why the first batch evaluation showed **non-gold rows scoring higher on average than gold-matching rows**, **zero** present-not-selected wins for gold alternatives vs wrong `current_final`, **many ties**, and a **~36%** guardrail warning rate on PAL-correct finals.

---

## A. Why the first score failed

### A.1 Primary mechanism: evidence asymmetry (haystack bias)

The validator builds a **candidate-only haystack** from `candidate_trace`, `candidate_code`, and `candidate_answer` (see `experiments/gsm8k_structural_validate.py`, `_candidate_channels_haystack` usage inside `_validate_gsm8k_candidate_impl`).

The batch script wires candidates as follows (`scripts/evaluate_gsm8k_structural_validator.py`, `build_candidate_specs`):

| Candidate role | Typical `candidate_trace` / `candidate_code` passed to `validate_gsm8k_candidate` |
|----------------|--------------------------------------------------------------------------------|
| `current_final`, `pal_stdout`, `direct_reserve`, `overlay_tiebreak`, most `other` | **Full PAL trace** (concat `final_nodes` reasoning) **+ PAL Python code** |
| `external_answer` | **`None` / empty** trace and code — **answer string only** enters the haystack |

So **PAL-path candidates** inherit hundreds–thousands of characters of “derivation evidence,” while **externals** are scored as if they were **bare numeric outputs**.

Quantity coverage is computed by matching **salient numeric norms from the problem text** against that haystack. PAL executions usually reproduce many literals (`121`, `5`, etc.), often driving **coverage toward 1.0**. Externals only contribute digits present in the **final answer text** (often a single token), so coverage collapses (typical **0.0–0.33** in the misleading cases below).

Operation-cue logic similarly searches the haystack for regex proxies (“per”, “difference”, temporal keywords). PAL trace/code satisfies many cues **even when the final answer is wrong**; externals miss most cues **even when the answer is gold**.

**Structural score** blends coverage and cue overlap with light penalties on warnings (`_structural_score` uses weight **0.75** on the coverage-based base and **0.25** on cue overlap; penalty **`0.03 * max(0, len(warnings)-3)`**). PAL-heavy rows therefore land in a **high base band**; externals accumulate **many warnings** and a **low base**, producing **lower scores for correct externals** in side-by-side pools.

### A.2 Secondary mechanisms

1. **Crude score formula**: The scalar folds heterogeneous warnings after the third into a mild shrink — not enough to reorder PAL vs external when base scores differ by ~0.5.

2. **Noisy / coarse heuristics**: `_required_operation_cues` fires multiple cues from regex scans on the problem (rate + difference + …). `_found_operation_cues` uses fragile substring heuristics on the haystack. Correct PAL traces still miss **individual** demanded cues (e.g. “difference” evidence), yielding **non-zero warnings even when the answer is correct** — contributing to guardrail false positives.

3. **Salient quantity extraction**: Word-number problems may yield **`no_numeric_mentions_extracted_from_problem`** / **`quantity_coverage is None`** (abstain path uses base **0.45**). That explains sparse-score ties (e.g. `openai_gsm8k_1082`) unrelated to “semantic quality.”

4. **Batch metric confound**: Aggregating **gold vs non-gold across all roles** mixes PAL-rich rows with external-sparse rows. The headline means (**0.473 vs 0.656**) are **not** a fair test of “does structure predict correctness”; they largely measure **which candidate family dominates each label**.

### A.3 What did *not* need API or controllers

Nothing here implies the failure mode is “missing API.” It is **offline wiring + definition of comparable evidence**.

---

## B. Misleading present-not-selected cases

Three cases where **wrong `current_final` structural_score > best gold-matching candidate** (from `summary.json`):

### B.1 `openai_gsm8k_1083`

| Field | Value |
|-------|--------|
| Problem (snippet) | Whirligig / thingamabob / whatchamacallit speeds; whatchamacallit at **121** m/s; ask whirligig speed. |
| Gold | **55** |
| Wrong `current_final` | **605** |
| Best gold-matching candidates | External answers **55** (`external_l1_max`, `external_s1_budget_forcing`, casebook duplicates) |
| Wrong PAL scores | `current_final` / `pal_stdout` / `direct_reserve`: **0.725**, coverage **1.0**, **1** warning (`missing_operation_cue_in_trace_or_code:difference`) |
| Gold external scores | **0.235**, coverage **0.333**, **6** warnings (low coverage, unused salient quantities, multiple missing cues, rate/contrast heuristics) |
| Trace/code | PAL: trace ≈ **959** chars, code ≈ **54** chars. External: **trace 0, code 0** (answer-only). |

**Diagnosis:** Identical formula applied to **rich PAL haystack** vs **answer-only external**. Correct externals are penalized for **sparse evidence**, not wrong math surface.

### B.2 `openai_gsm8k_1299`

| Field | Value |
|-------|--------|
| Problem (snippet) | Salt scrub recipe; **10**-ounce jar; relative amounts of zest, fragrance, salt, sugar, oil. |
| Gold | **4** |
| Wrong `current_final` | **5** |
| Best gold-matching | External **4** (`external_s1_budget_forcing` / casebook) |
| Wrong PAL | Score **0.850**, coverage **1.0**, **0** warnings |
| Gold external | Score **0.1575**, coverage **0.0**, **4** warnings |

Same **haystack asymmetry** pattern; externals cannot show intermediate quantities in trace because none is passed.

### B.3 `openai_gsm8k_1307`

| Field | Value |
|-------|--------|
| Problem (snippet) | Water with meals weekdays vs soda weekends — **week** story. |
| Gold | **26** |
| Wrong `current_final` | **21** |
| Best gold-matching | External **26** (multiple copies) |
| Wrong PAL | **0.725**, coverage **1.0**, **1** warning (`missing_operation_cue_in_trace_or_code:temporal`) |
| Gold external | **0.0975**, coverage **0.0**, **6** warnings |

Again: PAL narrative + code saturates coverage; externals answer-only.

**Bottom line for “misleading”:** These are **almost entirely explained by (3) unfair comparison between rich PAL traces and sparse external answers**, amplified by **(4) score formula** rewarding coverage and **(5) noisy cues**.

---

## C. Tie case analysis (present_not-selected cohort)

There are **20** tie cases where **best gold-matching structural_score == wrong `current_final` score** (same batch CSV).

### C.1 What tied — gold candidates are usually *not* externals

Inspecting which roles carry the **gold** label among tying rows:

- Many ties pair wrong `current_final` with gold on **`other` / `overlay_previous`**, **`pal_json_answer`**, **`overlay_tiebreak`**, or **`direct_reserve`** — all wired with the **same PAL trace and code** as `current_final`.
- **Scores duplicate trivially** because the validator sees **identical evidence channels**.

Representative patterns:

| Pattern | Meaning |
|---------|---------|
| **Identical warnings + identical coverage** | Same PAL bundle → same base score and cue overlap (e.g. score **0.850**, coverage **1.0**, **0** warnings for both wrong final and gold overlay/json). |
| **`overlay_previous` equals gold** | Structural checks cannot distinguish “promoted wrong PAL final” vs “previous numeric snapshot” when both share trace/code. |
| **`pal_json_answer` gold** | JSON head disagrees with stdout/final; validator still uses PAL trace — ties `current_final` if penalties align. |
| **1082-style abstain** | `quantity_coverage` / abstain on salient extraction (`no_numeric_mentions_extracted_from_problem`) yields **shared low-information plateau** (~**0.504**) for multiple roles. |

### C.2 Ten illustrative tie cases (sorted `case_id`)

| case_id | Tie score | Best gold role(s) | Notes |
|---------|-----------|---------------------|-------|
| openai_gsm8k_1082 | 0.504 | `other` / `overlay_previous` | Coverage abstain path; trace-rich but salient norms pipeline empty |
| openai_gsm8k_1085 | 0.850 | `other` / `pal_json_answer` | Full PAL evidence; zero warnings |
| openai_gsm8k_1087 | 0.850 | `overlay_tiebreak`, `overlay_previous` | Same evidence bundle |
| openai_gsm8k_1095 | 0.850 | `pal_json_answer` | Same |
| openai_gsm8k_1097 | 0.850 | `overlay_previous`, `pal_json_answer` | Same |
| openai_gsm8k_1116 | 0.850 | `overlay_previous` | Same |
| openai_gsm8k_1120 | 0.850 | `overlay_previous` | Same |
| openai_gsm8k_1121 | 0.600 | `direct_reserve`, `overlay_previous` | **2** warnings on both sides — identical penalty bucket |
| openai_gsm8k_1122 | 0.850 | `overlay_previous` | Same |
| openai_gsm8k_1124 | 0.850 | `direct_reserve` | Same |

### C.3 Root causes of ties (mapped to user hypotheses)

| Hypothesis | Supported? |
|------------|------------|
| Identical warnings | **Yes** when PAL-bundle roles tie (often **same warning multiset**). |
| No trace for both | **Rare** for PAL roles — trace is present; ties come from **shared** trace, not absence. |
| Answer-only with no derivation | **Yes for externals**, but ties here usually involve **non-external** gold roles. |
| Coverage saturating at 1.0 | **Yes** — drives **0.850** plateau for many rows. |
| Operation cues too coarse | **Yes** — when both sides miss the same cue or both satisfy coverage, **cue_ratio ties**. |

---

## D. Guardrail warning false positives (~36.1%)

Population: **guardrail_correct** cohort, **`current_final`**, **66 / 183** rows with ≥1 warning.

### D.1 Sample of 18 randomized rows (re-validated for raw warning strings)

Aggregated **multi-label** buckets (primary mechanisms):

| Bucket (interpretation) | Count / 18 |
|-------------------------|------------|
| `missing_operation_cue_*` — regex-demanded cue not found in haystack | **12** |
| `unused_salient_problem_quantities` — salient norms from problem “missing” from haystack | **5** |
| Keyword story heuristics (`rate_question_weak_*`, `temporal_story_weak_*`, etc.) | **4** |

### D.2 Mapping to requested categories

| Requested category | Observed in sample |
|--------------------|-------------------|
| Quantity in problem “unused” by candidate trace | **Yes** — `unused_salient_problem_quantities` on otherwise correct traces. |
| Constants / numeric noise | Not dominant in this sample (often **coverage is high**, e.g. **1.0**). |
| Written-number extraction FP | **Indirectly** — cue/story heuristics misfire before quantity noise dominates. |
| Trace/code missing despite correct answer | **No** in guardrail sample — **large trace_len / code_len** on inspected rows. |
| Operation cue required but unnecessary | **Yes** — temporal/rate cues flagged without proving error. |
| Unit/target heuristic too broad | **Rare** in sample (`money_context_*` not primary). |

**Interpretation:** Guardrail warnings are mostly **(5) noisy target/quantity/cue heuristics**, not missing traces for PAL.

---

## E. Evidence availability / haystack bias by candidate role

### E.1 Intended wiring (from `build_candidate_specs`)

- **`external_answer`**: validation calls use **`candidate_trace=None`, `candidate_code=None`** — **answer-only haystack**.
- **PAL-channel roles**: share **full internal trace + code** when PAL JSONL row exists.

### E.2 `missing_metadata_flags` in CSV

Case-level flags (`empty_trace`, `empty_pal_code`) reflect **whether the run had PAL trace/code globally**, **not** whether a particular row passed trace into the validator. So **`external_answer` rows still often carry no `empty_trace` flag** even though validation used **no trace**.

**Conclusion:** Role-by-role CSV flags **understate** trace absence for externals; the fair statement is **by construction** in the script.

### E.3 Quantitative asymmetry (from misleading diagnostics)

| Role | Typical trace passed | Typical score band (these PN failure cases) |
|------|---------------------|---------------------------------------------|
| `current_final` | Full PAL trace | **0.725–0.850** with coverage **1.0** |
| `external_answer` (gold) | None | **0.098–0.235** with coverage **0.0–0.33** |

### E.4 `matches_gold_offline` distribution by role (full CSV)

Rough counts (from batch CSV): **`external_answer`** contributes **608** gold-labeled rows vs PAL-channel roles mostly labeled gold when answer matches — global mean separation is dominated by **role mix**, not semantic purity.

---

## F. What the Combinatorial Opt Agent analogy still helps with

- **Never-raise telemetry** and **cheap offline checks** remain valuable as **instrumentation**, not as a single scalar ranking objective.
- **Warning tags** (“missing cue”, “low coverage vs problem”) are plausible **inputs to downstream policies** if calibrated **within candidate families**.
- **Separation of concerns**: structural checks are **not correctness**; treating them as mandatory gates without normalization **will** mis-rank.

---

## G. Recommended refinement path (conceptual — not implemented here)

**Prioritized:**

1. **(A) Trace-normalized scoring / stratified evaluation** — Never compare `external_answer` to PAL-channel candidates on one scalar without **partitioning by evidence mode** (or attaching external reasoning when archived).

2. **(B) Answer-only channel for externals** — Separate validator mode: **problem + answer string only**, without penalizing missing PAL trace; or **omit externals** from structural-score ranking tests until external traces exist.

3. **(E) Down-weight `structural_score` as ranker** — Keep **diagnostic warning tags**; defer scalar ranking until normalization exists.

**Secondary / Track-specific:**

4. **(D) PAL-code / PAL-trace validator for Track A** — Retry triggers keyed off **PAL-specific** failures (syntax/exec/low coverage **within PAL evidence**).

5. **(C) Candidate-pair tests for Track B** — Compare **two PAL-internal commitments** (overlay vs frontier mass) with **shared trace context**, not PAL vs external scalar scores.

---

## H. Continue validator direction or pause?

**Continue the direction as telemetry + family-specific checks**; **pause using `structural_score` as a cross-family ranking signal** until evidence normalization exists.

The first batch did **not** falsify “structural warnings can help”; it falsified **“one scalar on heterogeneous candidate constructions predicts gold alignment.”**

---

## I. Exact next implementation query

Use this as the implementation brief when ready (verbatim):

> Implement **evidence-stratified** GSM8K structural evaluation and metrics: (1) partition batch rows into **PAL-evidence** vs **answer-only external** cohorts with **separate summary.json stats**; (2) add optional **`external_trace_if_available`** passthrough only when archived text exists; (3) add **PAL-internal pairwise delta** metrics for present-not-selected (`current_final` vs `overlay_previous` / `direct_reserve` only); (4) add **warning-tag histograms within PAL-evidence gold rows** to tune cue thresholds; (5) **do not** wire into controllers or selection; **no API**.

---

## Final short answers (user checklist)

| Question | Answer |
|----------|--------|
| Report path | `/home/soroush/research-next-wt/outputs/gsm8k_structural_validator_eval_20260507/validator_failure_diagnosis.md` |
| Main reason score failed | **Haystack/evidence asymmetry**: PAL candidates validated with **full trace+code**; **externals answer-only** → coverage/cue scores **punish correct externals** and **reward wrong PAL finals**. |
| Validator direction still useful? | **Yes** as **tag telemetry** and **within-family** signals; **not** as a universal scalar ranker yet. |
| Track B / A usefulness | **Track B**: scalar comparison across PAL vs external **not** useful yet; **pairwise PAL-internal** might be. **Track A**: **PAL-only** warning tags remain plausible **retry hints** after FP review. |
| Exact next action | Run implementation query **I** (stratified metrics + PAL-internal deltas); optionally archive external reasoning later — **no API required**. |
| API needed now? | **No.** |
