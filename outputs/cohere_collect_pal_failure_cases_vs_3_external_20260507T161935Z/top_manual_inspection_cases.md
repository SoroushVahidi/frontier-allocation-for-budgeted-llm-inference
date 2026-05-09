# Top manual-inspection cases

Purpose: offline deep-dives before any implementation — **no API**, **no code**.

Criteria used: **trace richness** (`final_nodes`, multi-step `direct_reserve_attempts`), **failure-type cluster** (present_not_selected vs gold_absent_discovery), **heterogeneous externals** (single-method saves), **alignment with dominant buckets** (≈68% present-not-selected among preferred), **match to temporal/rate tags where relevant**.

---

## Part A — Ten **preferred** failures (PAL wrong, ≥1 external correct)

### 1. `openai_gsm8k_1087`
PAL answers **−66** vs gold **6**; **L1+ TALE correct**, S1 wrong. **`failure_tag`:** present-but-not-selected pattern with **`gold_in_tree=1`**; multiple frontier traces (`final_nodes_count` 7). **Why inspect:** Strong **commitment/surfacing** story — absurd magnitude while gold was reachable in-evaluator tree; good for **selector / repair-layer** design.

### 2. `openai_gsm8k_1083`
Chain-rate setup; PAL **605** vs gold **55**; **L1 + S1 correct**, **TALE wrong**. **Why inspect:** Demonstrates **baseline disagreement** under one PAL branch — tests interventions that do **not** assume tale agrees with L1.

### 3. `openai_gsm8k_1121`
Steps/walking word problem; PAL **8000** vs gold **2000**; **only S1** hits gold among externals. **Why inspect:** Classic **heterogeneous save** — forces **selector logic** that cannot rely on “majority of externals.”

### 4. `openai_gsm8k_1125`
Multi-phase tap-rate story; PAL giant wrong numeric vs gold **2450**; **all three externals correct**. **`gold_in_tree=0`.** **Why inspect:** **TRCE-shaped** long-chain decomposition with clean external consensus — anchor case for **discovery expansion** without commitment confound.

### 5. `openai_gsm8k_1166`
Monthly savings partition word problem; PAL **25** vs gold **50**; **only S1 correct**. **`gold_in_tree=0`.** **Why inspect:** Algebraic framing in traces — check whether PAL **stopped derivation early** vs never represented gold.

### 6. `openai_gsm8k_1198`
Long chalk / percentage decay word problem; PAL **3** vs gold **2**; **only TALE correct**. **`gold_in_tree=0`.** **Why inspect:** Lengthy stem + multi-clause constraints — stress test for **coverage over long horizons**.

### 7. `openai_gsm8k_1244`
Household rice consumption weeks; PAL **2** vs gold **3**; **TALE + S1 correct**, L1 wrong. **`gold_in_tree=0`.** **Why inspect:** Small integer answer but **multi-step unit aggregation** — separates **numeric slip** from **structure slip**.

### 8. `openai_gsm8k_1291`
Custodian **percent-of-day** problem; PAL outputs **`0.125`** vs gold **`50`**; **`external_l1_max` exact**; tale/S1 output **31.25** (also wrong). PAL row **`gold_in_tree=1`**. **Why inspect:** **Percent vs fraction / display normalization** — a clean **commitment** case where the right *kind* of quantity may exist in artifacts but the **surfaced** answer is the wrong representation.

### 9. `openai_gsm8k_1124`
Shrimp peel/saute pipe problem; PAL **25** vs gold **45**; **TALE + S1**, not L1. **`gold_in_tree=1`.** **Why inspect:** PAL trace literally contains **correct decomposition text** but wrong surfaced pick — textbook **present-not-selected** debugging case.

### 10. `openai_gsm8k_1120`
Relational “fewer/more than” paintings; PAL **7** vs gold **31**; **TALE only** among externals. **`gold_in_tree=1`.** **Why inspect:** Relational translation errors plus **single-external save** — highlights **problem modeling** vs selector-only fixes.

---

## Part B — Five **secondary** failures (PAL wrong, **all** externals wrong)

These are **hard negatives** — useful for ceiling tests and **dataset ambiguity** review.

### 1. `openai_gsm8k_1115`
Land-sale staged money word problem; **all wrong**; **`gold_absent_discovery`.** **Why inspect:** Multi-stage monetary accounting — see whether **any** structural scaffold could appear under richer discovery.

### 2. `openai_gsm8k_1081`
Salary escalation policy; PAL wildly off vs gold **9360**; **all externals wrong**. **`gold_absent_discovery`.** **Why inspect:** Compound policy interpretation — distinguishes **model ignorance** from selector bugs.

### 3. `openai_gsm8k_1137`
Dog shelter toy inventory dynamics; **all wrong**; **`gold_absent_discovery`.** **Why inspect:** Multi-stage population changes — strong **path coverage** stress without external shortcut.

### 4. `openai_gsm8k_1132`
Candles/flashlights counting puzzle; **all wrong**; **`gold_absent_discovery`.** **Why inspect:** Object-count assembly across rooms — candidate for **counterfactual coverage** drills.

### 5. `openai_gsm8k_1112`
Housekeeping profit word problem (long stem); **all wrong**; **`gold_absent_discovery`.** **Why inspect:** Named-entity / wording traps (“Lucas” typo in stem per trace) — **parse vs reasoning** audit even when tags are sparse.

---

## How to use this list

1. Walk **`per_example_records.jsonl`** PAL rows for each ID above — verify **`failure_tag`**, **`gold_in_tree`**, **`direct_reserve_attempts`**, **`selector_candidate_pool`** / **`final_nodes`**.
2. Compare with **`results.jsonl`** / **`selected_failure_cases.jsonl`** for externals on the same IDs.
3. Feed outcomes into **design memos**: Track **B** (*present-not-selected*) vs Track **A** (*gold-absent discovery*) — **do not merge** diagnostics prematurely.
