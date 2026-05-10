# Track B A/B pilot — causal audit (offline analysis)

**Bundle:** `outputs/cohere_track_b_ab_pilot_30case_20260507T204409Z/`  
**Scope:** Analysis only — no API, no code changes in this step.

---

## A. Recomputed metrics (validated from raw files)

Sources: `results.jsonl`, `paired_casebook.csv`, `per_example_records.jsonl` (60 scored rows, no `failed` rows).

| Metric | Value |
|--------|------:|
| Baseline PAL correct | **20 / 30** (accuracy **0.6667**) |
| Track B correct | **22 / 30** (accuracy **0.7333**) |
| Pairwise both_correct | **18** |
| Pairwise baseline_only | **2** |
| Pairwise track_b_only | **4** |
| Pairwise both_wrong | **6** |
| Track B gate rows with **override_applied** (from paired_casebook) | **4** |
| Overrides tagged helpful (baseline wrong → TB correct, override on) | **0** |
| Overrides tagged harmful (baseline correct → TB wrong, override on) | **1** |
| Overrides tagged neutral (same correctness class, override on) | **3** |
| Failed / skipped paired rows | **0** |

Net **+2** scored cases for Track B matches **(22−20)=2** and **(+4 track_b_only) − (+2 baseline_only) = 2**.

---

## B. Case IDs by outcome bucket

### track_b_only (4)

| case_id | Notes (high level) |
|---------|---------------------|
| `openai_gsm8k_100` | Gate evaluated; **no** override (`abstain_stdout_aligned`). Tie-break **differs** vs baseline. |
| `openai_gsm8k_103` | Gate evaluated; **no** override (`abstain_no_tiebreak`). |
| `openai_gsm8k_105` | Gate evaluated; **no** override (`abstain_stdout_aligned`). Tie-break **differs** vs baseline. |
| `openai_gsm8k_107` | **`track_b_gate_evaluated` = false** in paired export (see §C). TB wins; early path differs. |

### baseline_only (2)

| case_id | Role |
|---------|------|
| `openai_gsm8k_98` | **Harmful override** row (see §E); baseline correct, TB wrong in scored output. |
| `openai_gsm8k_109` | Gate evaluated; **no** override; PAL surface differs (30 vs 35). |

### both_wrong (6)

`openai_gsm8k_82`, `openai_gsm8k_93`, `openai_gsm8k_104`, `openai_gsm8k_106`, `openai_gsm8k_108`, `openai_gsm8k_85`  
(85 also has a **neutral** override — both methods wrong.)

### Rows with `track_b_gate_override_applied` = 1 (4)

| case_id | Pairwise outcome | Override tag |
|---------|------------------|----------------|
| `openai_gsm8k_80` | both_correct | neutral |
| `openai_gsm8k_85` | both_wrong | neutral |
| `openai_gsm8k_98` | baseline_only | **harmful** |
| `openai_gsm8k_108` | both_wrong | neutral |

### Harmful override (1)

- **`openai_gsm8k_98`**

### Neutral overrides (3)

- **`openai_gsm8k_80`** (both correct after override)  
- **`openai_gsm8k_85`** (still both wrong)  
- **`openai_gsm8k_108`** (still both wrong; override does not fix gold)

---

## C. track_b_only — did the gate cause the win?

**Bottom line:** None of the four **track_b_only** wins are explained by a **helpful Track B override**. All four have **`track_b_gate_override_applied = 0`** in `paired_casebook.csv`. Gains come from **different exploration / tie-break / sampling outcomes**, not from the commitment gate firing “wrong→right.”

### `openai_gsm8k_100`

- Gate: evaluated; decision **`abstain_stdout_aligned`** (no override).
- **Structural drift vs baseline:**  
  - Logical API calls: **4 vs 2**  
  - `remaining_budget_before_frontier`: **2 vs 4**  
  - `frontier_tiebreak_triggered`: **False vs True**  
  - `final_nodes` count: **5 vs 6**  
- **Interpretation:** Baseline and Track B runs **diverge before** tie-break (budget left before frontier differs). That should not happen solely from a post-surfacing gate; it indicates **different stochastic expansion / branch ordering** between the two full passes (baseline batch then Track B batch).

### `openai_gsm8k_103`

- Gate: **`abstain_no_tiebreak`** — no override.
- Calls **2 vs 2**, but **`selected_group`**: baseline **15**, Track B **5** (gold **5**).
- **Interpretation:** Same nominal cost, **different selected frontier/PAL outcome**. Typical of **API sampling variability** between runs (two independent sequential passes over examples).

### `openai_gsm8k_105`

- Gate: **`abstain_stdout_aligned`** — no override.
- **`frontier_tiebreak_triggered`**: **False vs True**; tie-break group drives TB final toward correct **14000** vs baseline **22000**.
- **Interpretation:** **Tie-break path differs between methods** without an overlay override. Again consistent with **non-deterministic tree / histogram evolution**, not the Track B gate rule.

### `openai_gsm8k_107`

- **Gate evaluated flag missing / false** in export (`track_b_gate_evaluated` = 0 in CSV); raw TB metadata shows **different PAL JSON path** (`pal_json` **100** vs **101**), logical calls **3 vs 4**, **`remaining_budget_before_frontier` 3 vs 2**.
- **Interpretation:** Strong **early-run divergence**; Track B win is **not** attributable to the gate (PAL branch/gate block may not mirror baseline).

**Conclusion for §C:** The **+4 track_b_only** bucket supports **hypothesis B/D** (incidental path perturbation and paired-run unreliability), **not** hypothesis “gate fixed wrong answers.”

---

## D. baseline_only — why Track B lost

### `openai_gsm8k_98` (harmful)

See **§E**. Override fires; scored TB answer worse than baseline; **PAL residual integration** also rewrites surfaced answer (§F).

### `openai_gsm8k_109`

- Gate evaluated; **`abstain_no_tiebreak`** — **no** override.
- Baseline **30** (correct); Track B **35** (wrong). Logical calls **2 vs 2**, same frontier budget before frontier; **`selected_group` 30 vs 35**.
- **Interpretation:** Loss is **not** from the gate; it matches **PAL / branch outcome drift** between independent runs.

---

## E. Harmful override — `openai_gsm8k_98`

### Labels (from raw `per_example_records.jsonl`, Track B method)

| Field | Baseline | Track B |
|-------|----------|---------|
| `gold_answer` (from row) | **75** | **75** |
| `exact_match` | **1** | **0** |
| `result_metadata.final_answer` (controller commit) | **75** | **57** |
| `final_answer_raw` (scored / surfaced in row) | **75** | **93** |

### Gate (Track B `pal_overlay.track_b_gate_decision`)

- **`should_override`:** true  
- **`reason`:** `override_overlay_prior_matches_tiebreak_conflicts_with_pal_stdout`  
- **`recommended_answer`:** **57**  
- **`recommended_source`:** `overlay_prior_matches_tiebreak`  
- **Signals (abbrev.):** tie-break group, PAL stdout vs tie-break, histogram support, overlay prior, **uniform multigroup tie** + stdout mass check (tightening signals present in decision dict).

### Structural context (Track B)

- **`frontier_tiebreak_triggered`:** True (baseline **False** for same case).  
- **`frontier_tiebreak_selected_group`:** **57** (baseline selected group **75** in metadata).  
- PAL: **`pal_answer` / stdout path** surfaces **93**; PAL JSON **63** (non-trivial disagreement channels).

### Why offline tightening did not prevent live harm

Offline tightening aimed to block **overlay** commits on **uniform ≥3-way ties with PAL stdout off the histogram**. Here the gate’s own **`signals_used`** includes **`histogram_uniform_multigroup_tie`** and **`pal_stdout_histogram_mass`** — the runtime guard **did run**, yet the overlay commit still fired (`should_override` true). That means either:

1. **PAL stdout histogram mass** was **≥ 1** on-manifold (so the triple-tie + off-manifold abstain path did not trigger), while tie-break still picked a **wrong peer vs gold**, or  
2. **Normalized bucket merging** for mass differs between offline fixtures and live metadata.

So the failure mode is **not** “forgot to abstain” in the abstract — it is **tie-break + overlay agreement on the wrong peer** when gold is another peer in the pool — a **gold-free** gate cannot know **75** is gold.

### Why scored output shows **93**, not **57**

Controller metadata **`final_answer` = 57** after the gate, but the row’s **`final_answer_raw`** used for exact-match is **93**.  

`result_metadata.pal_integration_evaluator` shows:

- **`pal_integration_fix_triggered`:** true  
- **`pal_integration_previous_answer`:** **57**  
- **`pal_integration_selected_answer`:** **93**  
- **`pal_integration_conflict_answer`:** **57**

So the **harness’s PAL residual strong-integration path** (evaluator-time, enabled by default on `*_tiebreak_pal*` methods) **promotes PAL stdout 93 over the controller’s post-gate 57** for scoring. That is a **layering / evaluation-order** issue: the pilot’s **reported** TB accuracy for this row reflects **93**, not **57**.

**Implication:** The “harmful override” story bundles (a) **wrong commitment vs gold** if the scorer honored **57**, and (b) **PAL integration overriding the gate commit** for surfacing, which **masks** the intended post-gate surface.

---

## F. Non-override drift and paired-run structure

### Sequential methods (not interleaved)

The harness runs **all baseline examples**, then **all Track B examples**. Each method pass is an **independent re-sample** of API outputs. **Paired deltas are not counterfactual** with identical LLM draws.

### Empirical drift flags (30 pairs)

| Check | # pairs with mismatch |
|-------|----------------------:|
| `cohere_logical_api_calls` | **5** |
| `final_nodes` count | **10** |
| `frontier_tiebreak_triggered` | **7** |
| `remaining_budget_before_frontier` | **5** |
| `selected_group` | **10** |

Examples with **multiple** divergences include **`openai_gsm8k_100`**, **`openai_gsm8k_107`**, **`openai_gsm8k_85`**, **`openai_gsm8k_98`**.

### Does enabling Track B change prompts/seeds/budgets?

The **only** intended behavioral delta is **`enable_track_b_overlay_commitment_gate`** on `DirectReserveFrontierGateController` for the Track B method ID. There is **no** separate prompt or seed in the registry path reviewed here.

Observed differences in tie-break flags and pre-frontier budgets **should not** occur if both runs were **bit-identical** up to the PAL overlay. They **do** occur in practice because **LLM outputs differ run-to-run**, changing expansion order, histogram mass, and tie-break triggers.

### Gate position vs state mutation

Track B runs **after** tie-break / hybrid overlay stages and **before** `decide_pal_strong_overlay_promotion` when enabled — it does not expand the frontier. Any **pre-gate** mismatch between baseline and TB is **not** caused by the gate logic itself.

---

## G. Root-cause conclusion

| Question | Conclusion |
|----------|------------|
| Is **+2** from intended gate fixes? | **No.** **Zero** helpful overrides; all **track_b_only** cases have **no** applied gate override. |
| Is **+2** from incidental perturbation? | **Yes** — tie-break and branch outcomes differ between independent passes (§C, §F). |
| Harmful override root cause? | **Wrong tie-break/overlay peer vs gold** (gold-free gate cannot know); plus **evaluator PAL integration** surfacing **93** over committed **57** (§E). |
| Implementation bug? | **Possible harness layering bug:** controller **`final_answer`** vs **`pal_integration_evaluator`** surfacing for Track B — **report before code change** (user constraint). |

Strongest overall label: **C + D + E** — unintended **evaluation / integration** interaction plus **non-interleaved live nondeterminism**, not a clean readout of the Track B gate alone.

---

## H. Recommendation

| Option | Verdict |
|--------|---------|
| **A.** Gate promising → one more tightening | **Low priority** until **paired design** and **scoring path** are fixed; tightening alone will not fix **98**-style peer-vs-gold ambiguity. |
| **B.** Gains not gate-driven; larger run misleading | **Supported** for **causal** claims. A wider slice may still estimate **population accuracy**, but not **gate attribution**. |
| **C.** Unintended path perturbation | **Supported** (tie-break + budget drift across pairs). |
| **D.** Small paired A/B unreliable without cached completions | **Supported.** |
| **E.** Prefer offline / cached-candidate A/B | **Supported** for **mechanism validation** of the gate. |

**Next actions (ordered):**

1. **Resolve scoring contract:** For Track B runs, decide whether **`pal_integration_evaluator` may override** controller-committed post-gate answers; reproduce on **`openai_gsm8k_98`** with logs only (no API if replaying JSON).  
2. **Redesign pilot:** **cached branches** or **interleaved** execution with **fixed** per-case LLM outputs if a causal paired test is required.  
3. **Larger Cohere spend:** Justified only for **population accuracy / cost**, **not** for attributing gains to the gate until (1)–(2) are addressed.

---

## I. API needed next?

**No** for continued **analysis / replay / harness fixes**. **Yes** only if you run a **new** experiment after changing harness behavior or pilot design.

---

## Appendix — commands used for recomputation

Internal recomputation used `python3` reading:

- `results.jsonl`  
- `paired_casebook.csv`  
- `cohere_real_model_cost_normalized_validation_live_run_20260507T204409Z/per_example_records.jsonl`  

(no network).
