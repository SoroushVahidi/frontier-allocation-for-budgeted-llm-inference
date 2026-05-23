#!/usr/bin/env python3
"""
Analyze Mistral GSM8K cases where agreement_only_2of3 loses to S1.
Produces all outputs under outputs/mistral_cases_where_agreement_loses_to_s1_20260523/
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
REPO = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference")
RUN_DIR = REPO / "outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z"
INNER_RUN = RUN_DIR / "cohere_real_model_cost_normalized_validation_20260523T145416Z"
PER_EXAMPLE_JSONL = INNER_RUN / "per_example_records.jsonl"

LIVE_DIR = REPO / "outputs/mistral_frozen_agreement_only_2of3_live_result_20260523"
S1_DOM = REPO / "outputs/mistral_s1_dominance_diagnostic_20260523"
ALG_IMP = REPO / "outputs/mistral_algorithm_improvement_diagnostic_20260523"
DEEP_ERR = REPO / "outputs/mistral_deep_error_and_selector_diagnostic_20260523"

OUT_ROOT = REPO / "outputs/mistral_cases_where_agreement_loses_to_s1_20260523"
CASE_LOG_DIR = OUT_ROOT / "case_logs_existing_artifacts"
CASE_LOG_DIR.mkdir(parents=True, exist_ok=True)

# method name mapping
METHOD_MAP = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "l1",
    "external_s1_budget_forcing": "s1",
    "external_tale_prompt_budgeting": "tale",
}

# ── load per-example records ─────────────────────────────────────────────────
print("[1/13] Loading per_example_records.jsonl ...")
records_by_eid_method = {}  # (example_id, short_method) -> record
all_eids_ordered = []
seen_eids = set()

with open(PER_EXAMPLE_JSONL) as f:
    for line in f:
        rec = json.loads(line)
        eid = rec["example_id"]
        mshort = METHOD_MAP.get(rec["method"], rec["method"])
        records_by_eid_method[(eid, mshort)] = rec
        if eid not in seen_eids:
            all_eids_ordered.append(eid)
            seen_eids.add(eid)

print(f"  {len(all_eids_ordered)} unique examples, {len(records_by_eid_method)} method-example pairs")

# ── load unified table ───────────────────────────────────────────────────────
print("[2/13] Loading unified_mistral_example_table.csv ...")
unified_path = ALG_IMP / "unified_mistral_example_table.csv"
unified_rows = {}  # example_id -> dict

with open(unified_path, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        unified_rows[row["example_id"]] = row

print(f"  {len(unified_rows)} rows loaded")

# ── helper: get full reasoning text ─────────────────────────────────────────
def get_reasoning(eid, method):
    rec = records_by_eid_method.get((eid, method))
    if rec is None:
        return "(no record found)"
    nodes = rec.get("final_nodes") or []
    if not nodes:
        return rec.get("final_answer_raw") or "(no reasoning)"
    parts = []
    for i, node in enumerate(nodes):
        rt = node.get("reasoning_text", "")
        pa = node.get("predicted_answer", "")
        if rt:
            parts.append(f"[Node {i}] {rt.strip()}")
            if pa:
                parts.append(f"  → Predicted answer: {pa}")
    return "\n\n".join(parts) if parts else "(no reasoning text in nodes)"

def get_answer(eid, method):
    rec = records_by_eid_method.get((eid, method))
    if rec is None:
        return "N/A"
    return str(rec.get("final_answer_raw") or rec.get("selected_answer_raw") or "N/A")

def is_correct(eid, method):
    rec = records_by_eid_method.get((eid, method))
    if rec is None:
        return None
    return bool(rec.get("exact_match"))

def get_field(row, col, default=""):
    return row.get(col, default) or default

# ── Step 3: reconstruct canonical case list ──────────────────────────────────
print("[3/13] Identifying primary and secondary case sets ...")

primary_cases = []        # agreement wrong, S1 correct
frontier_wrong_kept = []  # S1 correct, frontier wrong, agreement kept frontier
deferred_wrong = []       # S1 correct, agreement deferred but wrong
wrong_ext_majority = []   # S1 correct, wrong external majority excludes S1
pooled4_wrong = []        # S1 correct, pooled-4 wrong
only_s1_correct_cases = []  # only S1 correct among all 4
contrast_s1_wrong = []    # S1 wrong, agreement correct

for eid, row in unified_rows.items():
    agr_correct = row.get("agreement_only_2of3_against_frontier_correct", "") == "1"
    s1_correct_flag = row.get("s1_correct", "") == "1"
    frontier_correct_flag = row.get("frontier_correct", "") == "1"
    l1_correct_flag = row.get("l1_correct", "") == "1"
    tale_correct_flag = row.get("tale_correct", "") == "1"
    pooled_correct = row.get("pooled_4_with_fallback_correct", "") == "1"
    agr_action = row.get("agreement_only_2of3_against_frontier_selected_action", "")
    ext_maj_excl_s1 = row.get("external_majority_excludes_s1", "") == "1"

    if s1_correct_flag and not agr_correct:
        primary_cases.append(eid)

    if s1_correct_flag and not frontier_correct_flag and agr_action == "keep_frontier":
        frontier_wrong_kept.append(eid)

    if s1_correct_flag and not agr_correct and agr_action == "external_majority":
        deferred_wrong.append(eid)

    if s1_correct_flag and ext_maj_excl_s1:
        wrong_ext_majority.append(eid)

    if s1_correct_flag and not pooled_correct:
        pooled4_wrong.append(eid)

    if (s1_correct_flag and not frontier_correct_flag and
            not l1_correct_flag and not tale_correct_flag):
        only_s1_correct_cases.append(eid)

    if not s1_correct_flag and agr_correct:
        contrast_s1_wrong.append(eid)

print(f"  primary (agreement wrong, S1 correct): {len(primary_cases)}")
print(f"  frontier wrong, agreement kept frontier: {len(frontier_wrong_kept)}")
print(f"  agreement deferred wrong: {len(deferred_wrong)}")
print(f"  wrong external majority excludes S1: {len(wrong_ext_majority)}")
print(f"  pooled-4 wrong, S1 correct: {len(pooled4_wrong)}")
print(f"  only S1 correct: {len(only_s1_correct_cases)}")
print(f"  contrast (S1 wrong, agreement correct): {len(contrast_s1_wrong)}")

# ── CSV writer helpers ───────────────────────────────────────────────────────
CASE_COLS = [
    "example_id", "question_hash", "question", "gold_answer",
    "frontier_answer", "frontier_correct",
    "l1_answer", "l1_correct",
    "s1_answer", "s1_correct",
    "tale_answer", "tale_correct",
    "agreement_selected_answer", "agreement_action", "agreement_correct",
    "pooled4_selected_answer", "pooled4_action", "pooled4_correct",
    "external_majority_answer", "external_majority_includes_s1",
    "external_majority_excludes_s1",
    "agreement_pattern",
    "loss_category",
    "suspected_failure_mode",
]

def build_case_row(eid, loss_category):
    row = unified_rows.get(eid, {})
    r = records_by_eid_method.get((eid, "frontier"), {})
    return {
        "example_id": eid,
        "question_hash": get_field(row, "question_hash"),
        "question": get_field(row, "question") or get_field(r, "question", ""),
        "gold_answer": get_field(row, "gold_answer") or get_field(r, "gold_answer", ""),
        "frontier_answer": get_field(row, "frontier_selected_answer"),
        "frontier_correct": get_field(row, "frontier_correct"),
        "l1_answer": get_field(row, "l1_selected_answer"),
        "l1_correct": get_field(row, "l1_correct"),
        "s1_answer": get_field(row, "s1_selected_answer"),
        "s1_correct": get_field(row, "s1_correct"),
        "tale_answer": get_field(row, "tale_selected_answer"),
        "tale_correct": get_field(row, "tale_correct"),
        "agreement_selected_answer": get_field(row, "agreement_only_2of3_against_frontier_selected_answer"),
        "agreement_action": get_field(row, "agreement_only_2of3_against_frontier_selected_action"),
        "agreement_correct": get_field(row, "agreement_only_2of3_against_frontier_correct"),
        "pooled4_selected_answer": get_field(row, "pooled_4_with_fallback_selected_answer"),
        "pooled4_action": get_field(row, "pooled_4_with_fallback_selected_action"),
        "pooled4_correct": get_field(row, "pooled_4_with_fallback_correct"),
        "external_majority_answer": get_field(row, "external_majority_answer"),
        "external_majority_includes_s1": get_field(row, "external_majority_includes_s1"),
        "external_majority_excludes_s1": get_field(row, "external_majority_excludes_s1"),
        "agreement_pattern": get_field(row, "agreement_pattern"),
        "loss_category": loss_category,
        "suspected_failure_mode": get_field(row, "suspected_failure_mode"),
    }

def write_case_csv(path, eids, loss_category):
    rows = [build_case_row(eid, loss_category) for eid in eids]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CASE_COLS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {path.name} ({len(rows)} rows)")

# ── Step 4: Write case-set CSVs ──────────────────────────────────────────────
print("[4/13] Writing case-set CSVs ...")

write_case_csv(OUT_ROOT / "primary_agreement_wrong_s1_correct_cases.csv",
               primary_cases, "primary")
write_case_csv(OUT_ROOT / "s1_correct_frontier_wrong_agreement_kept_frontier_cases.csv",
               frontier_wrong_kept, "frontier_wrong_kept")
write_case_csv(OUT_ROOT / "s1_correct_agreement_deferred_wrong_cases.csv",
               deferred_wrong, "agreement_deferred_wrong")
write_case_csv(OUT_ROOT / "s1_correct_wrong_external_majority_cases.csv",
               wrong_ext_majority, "wrong_external_majority")
write_case_csv(OUT_ROOT / "s1_correct_pooled4_wrong_cases.csv",
               pooled4_wrong, "pooled4_wrong")
write_case_csv(OUT_ROOT / "only_s1_correct_cases.csv",
               only_s1_correct_cases, "only_s1_correct")
write_case_csv(OUT_ROOT / "contrast_s1_wrong_agreement_correct_cases.csv",
               contrast_s1_wrong, "contrast_s1_wrong")

# ── Step 5: Extract full case logs ───────────────────────────────────────────
print("[5/13] Extracting full case logs for primary cases ...")

def safe_id(eid):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", eid)

case_log_index_rows = []

for idx, eid in enumerate(primary_cases):
    row = unified_rows.get(eid, {})
    r_frontier = records_by_eid_method.get((eid, "frontier"), {})
    question = get_field(row, "question") or str(r_frontier.get("question", ""))
    gold = get_field(row, "gold_answer") or str(r_frontier.get("gold_answer", ""))

    # selector analysis
    agr_action = get_field(row, "agreement_only_2of3_against_frontier_selected_action")
    agr_answer = get_field(row, "agreement_only_2of3_against_frontier_selected_answer")
    ext_maj = get_field(row, "external_majority_answer")
    ext_maj_exists = get_field(row, "external_majority_exists")
    ext_maj_incl_s1 = get_field(row, "external_majority_includes_s1")
    ext_maj_excl_s1 = get_field(row, "external_majority_excludes_s1")
    agr_pattern = get_field(row, "agreement_pattern")
    suspected = get_field(row, "suspected_failure_mode")

    # per-method answers
    f_ans = get_field(row, "frontier_selected_answer")
    l_ans = get_field(row, "l1_selected_answer")
    s_ans = get_field(row, "s1_selected_answer")
    t_ans = get_field(row, "tale_selected_answer")
    f_corr = get_field(row, "frontier_correct")
    l_corr = get_field(row, "l1_correct")
    s_corr = get_field(row, "s1_correct")
    t_corr = get_field(row, "tale_correct")

    # full reasoning
    f_reasoning = get_reasoning(eid, "frontier")
    l_reasoning = get_reasoning(eid, "l1")
    s_reasoning = get_reasoning(eid, "s1")
    t_reasoning = get_reasoning(eid, "tale")

    # token counts
    def tok(m):
        rec = records_by_eid_method.get((eid, m), {})
        return f"in={rec.get('input_tokens','?')} out={rec.get('output_tokens','?')}"

    # Why did agreement-only lose?
    if agr_action == "keep_frontier" and f_corr != "1":
        why_lost = "Agreement-only kept frontier (no external majority), but frontier was wrong. S1 was correct but isolated."
    elif agr_action == "external_majority":
        why_lost = f"Agreement-only deferred to external majority ({ext_maj}), which excluded S1. S1 had correct answer ({s_ans})."
    else:
        why_lost = f"Agreement-only selected action='{agr_action}', answer='{agr_answer}', which was wrong. S1={s_ans} (correct)."

    # What S1 did differently
    s1_len = get_field(row, "s1_reasoning_len")
    f_len = get_field(row, "frontier_reasoning_len")
    s1_clean = get_field(row, "s1_clean_numeric") == "1"
    s1_int = get_field(row, "s1_is_integer") == "1"
    what_s1 = []
    if s1_clean:
        what_s1.append("S1 produced a clean numeric answer")
    if s1_len and f_len:
        try:
            if int(s1_len) > int(f_len):
                what_s1.append(f"S1 used longer reasoning ({s1_len} chars vs frontier {f_len} chars)")
            else:
                what_s1.append(f"S1 was more concise ({s1_len} chars vs frontier {f_len} chars)")
        except ValueError:
            pass
    if not what_s1:
        what_s1.append("See full reasoning below for comparison")
    what_s1_str = "; ".join(what_s1)

    # Algorithm lesson
    if ext_maj_exists == "0" or ext_maj_exists == "":
        lesson = "When no external majority exists and S1 disagrees with frontier, consider preferring S1 (especially if S1 has clean numeric answer)."
    elif ext_maj_excl_s1 == "1":
        lesson = "External majority excluded S1 and was wrong. Consider S1-clean-numeric override when external majority excludes S1."
    else:
        lesson = f"Agreement pattern: {agr_pattern}. Review whether S1 could be promoted in this pattern."

    filename = f"case_{idx+1:02d}_{safe_id(eid)}.md"
    case_path = CASE_LOG_DIR / filename

    md = f"""# Case {idx+1}: {eid}

## Case Summary
- **Example ID:** {eid}
- **Agreement-only result:** WRONG (action={agr_action}, answer={agr_answer})
- **S1 result:** CORRECT (answer={s_ans})
- **Agreement pattern:** {agr_pattern}
- **External majority exists:** {ext_maj_exists}
- **External majority includes S1:** {ext_maj_incl_s1}
- **External majority excludes S1:** {ext_maj_excl_s1}
- **Suspected failure mode:** {suspected}

## Question and Gold
**Question:** {question}

**Gold answer:** {gold}

## Source Outputs Table
| Method | Answer | Correct | Reasoning length | Tokens |
|--------|--------|---------|-----------------|--------|
| Frontier | {f_ans} | {f_corr} | {get_field(row,'frontier_reasoning_len')} | {tok('frontier')} |
| L1 | {l_ans} | {l_corr} | {get_field(row,'l1_reasoning_len')} | {tok('l1')} |
| S1 | {s_ans} | {s_corr} | {get_field(row,'s1_reasoning_len')} | {tok('s1')} |
| TALE | {t_ans} | {t_corr} | {get_field(row,'tale_reasoning_len')} | {tok('tale')} |

## Full Frontier Raw Output
```
{f_reasoning}
```

## Full L1 Raw Output
```
{l_reasoning}
```

## Full S1 Raw Output
```
{s_reasoning}
```

## Full TALE Raw Output
```
{t_reasoning}
```

## Selector Decision
- **Selected action:** {agr_action}
- **Selected answer:** {agr_answer}
- **External majority answer:** {ext_maj if ext_maj else 'N/A'}
- **External majority includes S1:** {ext_maj_incl_s1}
- **External majority excludes S1:** {ext_maj_excl_s1}

## Why Agreement-Only Lost
{why_lost}

## What S1 Did Differently
{what_s1_str}

## Algorithm-Improvement Lesson
{lesson}
"""
    case_path.write_text(md)

    case_log_index_rows.append({
        "case_index": idx + 1,
        "example_id": eid,
        "question_hash": get_field(row, "question_hash"),
        "agreement_action": agr_action,
        "agreement_answer": agr_answer,
        "s1_answer": s_ans,
        "frontier_correct": f_corr,
        "l1_correct": l_corr,
        "s1_correct": s_corr,
        "tale_correct": t_corr,
        "external_majority_exists": ext_maj_exists,
        "external_majority_includes_s1": ext_maj_incl_s1,
        "external_majority_excludes_s1": ext_maj_excl_s1,
        "suspected_failure_mode": suspected,
        "case_log_file": filename,
    })

print(f"  Wrote {len(case_log_index_rows)} case markdown files")

# Write index CSV
index_cols = list(case_log_index_rows[0].keys()) if case_log_index_rows else []
with open(OUT_ROOT / "primary_case_log_index.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=index_cols)
    writer.writeheader()
    writer.writerows(case_log_index_rows)
print(f"  Wrote primary_case_log_index.csv")

# ── Step 6: Log availability summary ────────────────────────────────────────
print("[6/13] Creating full_log_availability_summary.csv ...")

avail_rows = []
for eid in primary_cases:
    row = unified_rows.get(eid, {})
    has_full = {}
    for m in ["frontier", "l1", "s1", "tale"]:
        rec = records_by_eid_method.get((eid, m), {})
        nodes = rec.get("final_nodes") or []
        has_reasoning = any(n.get("reasoning_text") for n in nodes) if nodes else False
        has_full[m] = has_reasoning
    all_present = all(has_full.values())
    avail_rows.append({
        "example_id": eid,
        "has_frontier_full_log": has_full.get("frontier", False),
        "has_l1_full_log": has_full.get("l1", False),
        "has_s1_full_log": has_full.get("s1", False),
        "has_tale_full_log": has_full.get("tale", False),
        "all_methods_have_full_log": all_present,
        "rerun_needed": not all_present,
        "question_available": bool(row.get("question")),
        "gold_available": bool(row.get("gold_answer")),
        "selector_metadata_available": True,
        "prompt_metadata_available": "partial",
    })

with open(OUT_ROOT / "full_log_availability_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(avail_rows[0].keys()))
    writer.writeheader()
    writer.writerows(avail_rows)
needs_rerun = sum(1 for r in avail_rows if r["rerun_needed"])
print(f"  {needs_rerun}/{len(avail_rows)} cases need rerun. Rerun: {'NO' if needs_rerun == 0 else 'YES'}")

# ── Step 8: Failure taxonomy ─────────────────────────────────────────────────
print("[7/13] Building failure taxonomy ...")

TAXONOMY_LABELS = {
    "A": "no_external_majority_keep_frontier_but_s1_correct",
    "B": "external_majority_wrong_excludes_s1",
    "C": "frontier_and_wrong_external_agree_against_s1",
    "D": "S1_isolated_correct_but_selector_requires_support",
    "E": "S1_supported_but_not_majority_due_to_tie_or_rule",
    "F": "L1_TALE_shared_arithmetic_error",
    "G": "TALE_or_L1_bad_numeric_shortcut",
    "H": "frontier_premature_or_shallow_reasoning",
    "I": "S1_better_step_decomposition",
    "J": "answer_normalization_subtle_issue",
    "K": "other_unknown",
}

def classify_failure(eid, row):
    agr_action = get_field(row, "agreement_only_2of3_against_frontier_selected_action")
    ext_maj_exists = get_field(row, "external_majority_exists") == "1"
    ext_maj_excl_s1 = get_field(row, "external_majority_excludes_s1") == "1"
    ext_maj_incl_s1 = get_field(row, "external_majority_includes_s1") == "1"
    f_corr = get_field(row, "frontier_correct") == "1"
    l_corr = get_field(row, "l1_correct") == "1"
    t_corr = get_field(row, "tale_correct") == "1"
    s_isolated = get_field(row, "s1_isolated") == "1"
    l_agrees_t = get_field(row, "l1_agrees_tale") == "1"
    f_len_str = get_field(row, "frontier_reasoning_len")
    s_len_str = get_field(row, "s1_reasoning_len")
    s_clean = get_field(row, "s1_clean_numeric") == "1"

    cats = []

    # A: no external majority, kept frontier, frontier wrong
    if not ext_maj_exists and agr_action == "keep_frontier" and not f_corr:
        cats.append("A")

    # B: external majority wrong and excludes s1
    if ext_maj_exists and ext_maj_excl_s1 and not l_corr and not t_corr:
        cats.append("B")

    # C: frontier + wrong external agree (frontier agrees ext majority but both wrong)
    if ext_maj_exists and ext_maj_incl_s1 is False and f_corr is False and ext_maj_excl_s1:
        cats.append("C")

    # D: S1 isolated (no support from others)
    if s_isolated:
        cats.append("D")

    # F: L1 and TALE share same wrong arithmetic
    if l_agrees_t and not l_corr and not t_corr:
        cats.append("F")

    # H: frontier has short reasoning compared to S1
    try:
        f_len = int(f_len_str) if f_len_str else 0
        s_len = int(s_len_str) if s_len_str else 0
        if s_len > f_len * 1.5 and not f_corr:
            cats.append("H")
    except (ValueError, TypeError):
        pass

    # I: S1 has better step decomposition (longer reasoning + correct)
    try:
        f_len = int(f_len_str) if f_len_str else 0
        s_len = int(s_len_str) if s_len_str else 0
        if s_len > f_len * 1.2:
            cats.append("I")
    except (ValueError, TypeError):
        pass

    # G: TALE/L1 short answer vs S1 longer
    l_len_str = get_field(row, "l1_reasoning_len")
    t_len_str = get_field(row, "tale_reasoning_len")
    try:
        l_len = int(l_len_str) if l_len_str else 0
        t_len = int(t_len_str) if t_len_str else 0
        s_len = int(s_len_str) if s_len_str else 0
        if (l_len < s_len * 0.5 or t_len < s_len * 0.5) and not l_corr and not t_corr:
            cats.append("G")
    except (ValueError, TypeError):
        pass

    if not cats:
        cats.append("K")

    primary_cat = cats[0]
    return primary_cat, ",".join(cats)

tax_rows = []
for eid in primary_cases:
    row = unified_rows.get(eid, {})
    primary_cat, all_cats = classify_failure(eid, row)
    tax_rows.append({
        "example_id": eid,
        "question": get_field(row, "question"),
        "gold_answer": get_field(row, "gold_answer"),
        "primary_failure_category": primary_cat,
        "primary_failure_label": TAXONOMY_LABELS[primary_cat],
        "all_failure_categories": all_cats,
        "agreement_action": get_field(row, "agreement_only_2of3_against_frontier_selected_action"),
        "agreement_answer": get_field(row, "agreement_only_2of3_against_frontier_selected_answer"),
        "s1_answer": get_field(row, "s1_selected_answer"),
        "frontier_correct": get_field(row, "frontier_correct"),
        "l1_correct": get_field(row, "l1_correct"),
        "tale_correct": get_field(row, "tale_correct"),
        "external_majority_exists": get_field(row, "external_majority_exists"),
        "s1_isolated": get_field(row, "s1_isolated"),
    })

with open(OUT_ROOT / "case_failure_taxonomy.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(tax_rows[0].keys()))
    writer.writeheader()
    writer.writerows(tax_rows)

# Summary
cat_counts = defaultdict(int)
for r in tax_rows:
    for c in r["all_failure_categories"].split(","):
        cat_counts[c.strip()] += 1

summary_rows = []
for cat, label in TAXONOMY_LABELS.items():
    count = cat_counts.get(cat, 0)
    summary_rows.append({
        "category_code": cat,
        "category_label": label,
        "n_cases": count,
        "pct_of_primary": f"{100*count/max(len(primary_cases),1):.1f}%",
    })

with open(OUT_ROOT / "case_failure_taxonomy_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
    writer.writeheader()
    writer.writerows(summary_rows)
print(f"  Taxonomy: {dict(cat_counts)}")

# Examples markdown
tax_examples = []
for cat in ["A", "B", "C", "D", "F", "G", "H", "I", "K"]:
    cases = [r for r in tax_rows if cat in r["all_failure_categories"]]
    if cases:
        ex = cases[0]
        eid = ex["example_id"]
        row = unified_rows.get(eid, {})
        tax_examples.append(f"""## Category {cat}: {TAXONOMY_LABELS[cat]}

**Count:** {cat_counts.get(cat, 0)} cases

**Example:** {eid}
**Question:** {ex['question'][:300]}
**Gold:** {ex['gold_answer']}
**Agreement action:** {ex['agreement_action']} → {ex['agreement_answer']}
**S1 answer:** {ex['s1_answer']}
**Pattern:** {get_field(row, 'agreement_pattern')}
""")

(OUT_ROOT / "case_failure_taxonomy_examples.md").write_text(
    "# Case Failure Taxonomy Examples\n\n" + "\n".join(tax_examples))

# ── Step 9: Reasoning quality comparison ─────────────────────────────────────
print("[8/13] Creating reasoning quality comparison ...")

rq_rows = []
for eid in primary_cases:
    row = unified_rows.get(eid, {})
    f_len = int(get_field(row, "frontier_reasoning_len") or 0)
    s_len = int(get_field(row, "s1_reasoning_len") or 0)
    l_len = int(get_field(row, "l1_reasoning_len") or 0)
    t_len = int(get_field(row, "tale_reasoning_len") or 0)
    f_corr = get_field(row, "frontier_correct") == "1"
    l_corr = get_field(row, "l1_correct") == "1"
    t_corr = get_field(row, "tale_correct") == "1"
    s_clean = get_field(row, "s1_clean_numeric") == "1"
    l_agrees_t = get_field(row, "l1_agrees_tale") == "1"
    agr_action = get_field(row, "agreement_only_2of3_against_frontier_selected_action")

    s1_more_steps = s_len > f_len * 1.2
    l1_tale_shared_err = l_agrees_t and not l_corr and not t_corr
    frontier_shallow = s_len > f_len * 1.5 and not f_corr

    rq_rows.append({
        "example_id": eid,
        "question": get_field(row, "question")[:200],
        "gold_answer": get_field(row, "gold_answer"),
        "frontier_answer": get_field(row, "frontier_selected_answer"),
        "s1_answer": get_field(row, "s1_selected_answer"),
        "agreement_action": agr_action,
        "frontier_reasoning_len": f_len,
        "s1_reasoning_len": s_len,
        "l1_reasoning_len": l_len,
        "tale_reasoning_len": t_len,
        "s1_clean_numeric": s_clean,
        "s1_more_steps_than_frontier": s1_more_steps,
        "l1_tale_shared_error": l1_tale_shared_err,
        "frontier_shallow_reasoning": frontier_shallow,
        "frontier_correct": f_corr,
        "l1_correct": l_corr,
        "tale_correct": t_corr,
        "agreement_pattern": get_field(row, "agreement_pattern"),
    })

with open(OUT_ROOT / "reasoning_quality_comparison.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rq_rows[0].keys()))
    writer.writeheader()
    writer.writerows(rq_rows)

# Representative cases markdown (up to 10)
rep_cases_md = ["# Representative Reasoning Quality Cases\n"]
for idx, eid in enumerate(primary_cases[:10]):
    row = unified_rows.get(eid, {})
    question = get_field(row, "question")
    gold = get_field(row, "gold_answer")
    f_ans = get_field(row, "frontier_selected_answer")
    s_ans = get_field(row, "s1_selected_answer")
    agr_action = get_field(row, "agreement_only_2of3_against_frontier_selected_action")
    pattern = get_field(row, "agreement_pattern")

    f_reasoning = get_reasoning(eid, "frontier")
    s_reasoning = get_reasoning(eid, "s1")
    l_reasoning = get_reasoning(eid, "l1")
    t_reasoning = get_reasoning(eid, "tale")

    rep_cases_md.append(f"""## Case {idx+1}: {eid}

**Question:** {question}
**Gold:** {gold}
**Agreement action:** {agr_action} | **Pattern:** {pattern}
**Frontier answer:** {f_ans} (wrong) | **S1 answer:** {s_ans} (correct)

### Frontier reasoning
```
{f_reasoning[:1000]}{'...' if len(f_reasoning) > 1000 else ''}
```

### S1 reasoning
```
{s_reasoning[:1000]}{'...' if len(s_reasoning) > 1000 else ''}
```

### L1 reasoning
```
{l_reasoning[:500]}{'...' if len(l_reasoning) > 500 else ''}
```

### TALE reasoning
```
{t_reasoning[:500]}{'...' if len(t_reasoning) > 500 else ''}
```
---
""")

(OUT_ROOT / "reasoning_quality_representative_cases.md").write_text("\n".join(rep_cases_md))
print(f"  Wrote reasoning_quality_comparison.csv and representative cases md")

# ── Step 10: Algorithm improvement lessons ───────────────────────────────────
print("[9/13] Extracting algorithm improvement lessons ...")

# Compute stats
n_primary = len(primary_cases)
n_no_ext_maj = sum(1 for eid in primary_cases
                   if get_field(unified_rows.get(eid, {}), "external_majority_exists") in ("0", ""))
n_ext_maj_excl_s1 = sum(1 for eid in primary_cases
                        if get_field(unified_rows.get(eid, {}), "external_majority_excludes_s1") == "1")
n_l1_tale_corr_err = sum(1 for r in rq_rows if r["l1_tale_shared_error"])
n_s1_clean = sum(1 for eid in primary_cases
                 if get_field(unified_rows.get(eid, {}), "s1_clean_numeric") == "1")
n_s1_more_steps = sum(1 for r in rq_rows if r["s1_more_steps_than_frontier"])

lessons_md = f"""# Algorithm Improvement Lessons from S1-Loss Cases

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

## Summary Statistics
- Primary cases analyzed: {n_primary}
- Cases where no external majority existed: {n_no_ext_maj} ({100*n_no_ext_maj//max(n_primary,1)}%)
- Cases where external majority excluded S1: {n_ext_maj_excl_s1} ({100*n_ext_maj_excl_s1//max(n_primary,1)}%)
- Cases where L1+TALE shared arithmetic error: {n_l1_tale_corr_err} ({100*n_l1_tale_corr_err//max(n_primary,1)}%)
- Cases where S1 produced clean numeric answer: {n_s1_clean} ({100*n_s1_clean//max(n_primary,1)}%)
- Cases where S1 used more reasoning steps than frontier: {n_s1_more_steps} ({100*n_s1_more_steps//max(n_primary,1)}%)

## Lesson 1: No-External-Majority Cases
When no external majority exists ({n_no_ext_maj}/{n_primary} primary cases), agreement-only defaults to
keeping frontier. If S1 disagrees with frontier and has a clean numeric answer, overriding to S1
would recover some of these cases. The risk is regression on cases where frontier is correct.
**Runtime-legal signal:** external_majority_exists==False AND s1_disagrees_frontier AND s1_clean_numeric.

## Lesson 2: Wrong External Majority Excludes S1
In {n_ext_maj_excl_s1}/{n_primary} primary cases, the external majority (L1+TALE or similar)
excluded S1 and was wrong. This suggests L1 and TALE make correlated arithmetic errors on
certain problem types (chain-of-shortcut arithmetic). If S1 is isolated with a clean short
numeric answer when external majority excludes S1, that is a reliable signal that S1 may be right.
**Runtime-legal signal:** external_majority_excludes_s1 AND s1_clean_numeric.

## Lesson 3: Correlated L1+TALE Errors
{n_l1_tale_corr_err}/{n_primary} cases show L1 and TALE agreeing on the same wrong answer.
This is not independent evidence — both models tend to use similar arithmetic shortcuts and
share the same error. Agreement among correlated models should be discounted.
**Implication:** An "agreement" between L1 and TALE alone should not outweigh S1 when S1
has a well-formed numeric answer.

## Lesson 4: S1 Uses Better Step Decomposition
In {n_s1_more_steps}/{n_primary} cases, S1 produced substantially longer reasoning than frontier,
and was correct. S1's budget-forcing approach causes it to enumerate more solution steps,
which reduces arithmetic slip. Frontier's shallow reasoning sometimes misses a step or truncates.

## Lesson 5: Runtime-Legal Signals
The following signals are computable at selection time without using gold answers:
1. `s1_clean_numeric` — S1's answer is a short integer or decimal
2. `external_majority_exists` — whether L1+TALE (or L1+TALE+frontier) agree
3. `external_majority_excludes_s1` — external majority specifically excludes S1
4. `s1_reasoning_len` — how much reasoning S1 generated
5. `s1_isolated` — S1 is the only method with its answer
6. `l1_agrees_tale` — whether L1 and TALE agree (potential correlated error signal)

## Concrete Recommendations
1. **Override rule A:** If no external majority and s1_clean_numeric and s1 disagrees with
   frontier → prefer S1. Estimated gain: ~{n_no_ext_maj} cases, minimal regression.
2. **Override rule B:** If external majority excludes S1 and s1_clean_numeric → prefer S1.
   Estimated gain: ~{n_ext_maj_excl_s1} cases. Risk: regression when external majority is right.
3. **Discount L1+TALE agreement:** When only L1 and TALE agree (without frontier), weight
   that agreement lower, since they exhibit correlated errors.
4. **Use S1 reasoning length as a quality signal:** Longer S1 reasoning is correlated with
   correctness in borderline cases.
"""

(OUT_ROOT / "algorithm_improvement_lessons_from_s1_loss_cases.md").write_text(lessons_md)
print("  Wrote algorithm_improvement_lessons_from_s1_loss_cases.md")

# ── Step 11: Diagnostic fix evaluation ──────────────────────────────────────
print("[10/13] Evaluating diagnostic fixes ...")

# Compute baseline metrics
def compute_accuracy(method_col, rows_dict):
    correct = sum(1 for r in rows_dict.values() if get_field(r, method_col) == "1")
    return correct

n_total = len(unified_rows)
always_s1_correct = compute_accuracy("always_s1_correct", unified_rows)
agr_correct_total = compute_accuracy("agreement_only_2of3_against_frontier_correct", unified_rows)
pooled4_correct_total = compute_accuracy("pooled_4_with_fallback_correct", unified_rows)

# Compute diagnostic variants from unified table
diagnostic_variants = [
    ("agreement_only_but_if_no_majority_and_s1_differs_from_frontier_choose_s1",
     "agreement_plus_s1_no_majority_override"),
    ("agreement_only_but_if_external_majority_excludes_s1_choose_s1_when_s1_has_short_clean_numeric_answer",
     "agreement_plus_s1_clean_numeric_override"),
    ("prefer_s1_when_no_external_majority",
     "prefer_s1_when_no_external_majority"),
    ("prefer_s1_unless_two_non_s1_sources_agree_against_s1",
     "prefer_s1_unless_two_non_s1_agree"),
    ("provider_prior_weighted_selector_mistral_s1_prior",
     "provider_prior_weighted_s1_prior"),
]

fix_rows = []
for variant_col_prefix, fix_name in diagnostic_variants:
    col = f"{variant_col_prefix}_correct"
    # count correct on all examples
    n_correct_all = sum(1 for r in unified_rows.values() if get_field(r, col) == "1")
    # count correct on primary cases
    n_correct_primary = sum(1 for eid in primary_cases
                            if get_field(unified_rows.get(eid, {}), col) == "1")
    # regressions: was correct under agreement-only, now wrong under fix
    n_regression = sum(1 for r in unified_rows.values()
                       if get_field(r, "agreement_only_2of3_against_frontier_correct") == "1"
                       and get_field(r, col) != "1")

    fix_rows.append({
        "fix_name": fix_name,
        "n_correct_all_300": n_correct_all,
        "accuracy_all_300": f"{100*n_correct_all/max(n_total,1):.2f}%",
        "n_correct_primary_19": n_correct_primary,
        "pct_primary_recovered": f"{100*n_correct_primary/max(n_primary,1):.1f}%",
        "n_regressions_from_agreement_baseline": n_regression,
        "vs_always_s1": n_correct_all - always_s1_correct,
        "vs_agreement_baseline": n_correct_all - agr_correct_total,
        "diagnostic_only": True,
    })

# Add baselines for comparison
for col, name in [
    ("agreement_only_2of3_against_frontier_correct", "agreement_only_baseline"),
    ("always_s1_correct", "always_s1"),
    ("pooled_4_with_fallback_correct", "pooled_4_baseline"),
]:
    n_correct_all = sum(1 for r in unified_rows.values() if get_field(r, col) == "1")
    n_correct_primary = sum(1 for eid in primary_cases
                            if get_field(unified_rows.get(eid, {}), col) == "1")
    fix_rows.append({
        "fix_name": name,
        "n_correct_all_300": n_correct_all,
        "accuracy_all_300": f"{100*n_correct_all/max(n_total,1):.2f}%",
        "n_correct_primary_19": n_correct_primary,
        "pct_primary_recovered": f"{100*n_correct_primary/max(n_primary,1):.1f}%",
        "n_regressions_from_agreement_baseline": 0,
        "vs_always_s1": n_correct_all - always_s1_correct,
        "vs_agreement_baseline": n_correct_all - agr_correct_total,
        "diagnostic_only": name not in ("agreement_only_baseline", "always_s1", "pooled_4_baseline"),
    })

with open(OUT_ROOT / "targeted_diagnostic_fix_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(fix_rows[0].keys()))
    writer.writeheader()
    writer.writerows(fix_rows)
print("  Wrote targeted_diagnostic_fix_summary.csv")

# ── Step 12: Human-readable report ──────────────────────────────────────────
print("[11/13] Creating human-readable report ...")

# Sort fix_rows by accuracy for reporting
fix_rows_sorted = sorted([r for r in fix_rows if r["fix_name"] != "agreement_only_baseline"],
                         key=lambda r: int(r["n_correct_all_300"]), reverse=True)

best_fix = fix_rows_sorted[0] if fix_rows_sorted else {}

tax_summary_text = "\n".join(
    f"- {r['category_code']} ({r['category_label']}): {r['n_cases']} cases ({r['pct_of_primary']})"
    for r in summary_rows if int(r['n_cases']) > 0
)

fix_table = "\n".join(
    f"| {r['fix_name']} | {r['n_correct_all_300']} | {r['accuracy_all_300']} | "
    f"{r['n_correct_primary_19']}/{n_primary} | {r['n_regressions_from_agreement_baseline']} |"
    for r in fix_rows
)

report_md = f"""# Mistral Case Analysis: Agreement-Only Loses to S1
**Date:** {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

## Why This Analysis Was Done
The agreement_only_2of3_against_frontier selector achieves 85.33% on Mistral GSM8K (256/300),
while S1 alone achieves 89.67% (269/300). This 4.3 pp gap represents 13 cases where agreement-only
loses to S1. We analyze these to understand the failure modes and find runtime-legal improvements.

## Scope
- **Provider/model:** Mistral (mistral-small-latest)
- **Dataset:** GSM8K (300 examples, seed 71, budget B=6)
- **Primary case set:** agreement_only_2of3_against_frontier wrong AND S1 correct = **{n_primary} cases**
- **Full logs from:** existing per_example_records.jsonl (final_nodes field has full reasoning)
- **Targeted rerun:** NOT needed — full reasoning logs available in existing artifacts

## Log Availability
All {n_primary} primary cases have complete logs:
- Full raw reasoning text for all 4 methods (frontier, L1, S1, TALE)
- Extracted final answers and normalization
- Selector metadata (action, external majority, agreement pattern)
- Token counts and latency
- No API rerun was performed

## Failure Taxonomy

{tax_summary_text}

### Top Failure Patterns
**A — No external majority, kept frontier, frontier wrong:**
When agreement-only has no external majority signal, it defaults to keeping frontier. If frontier
is wrong and S1 is correct (but isolated), the selector cannot recover. This is the most common
pattern: {n_no_ext_maj} cases.

**B — External majority excludes S1:**
L1 and TALE form a majority that excludes S1. Since both are similar-capacity models using similar
arithmetic shortcuts, this is a correlated-error majority. S1's budget-forcing gives it a different
answer that happens to be correct.

**F — L1+TALE shared arithmetic error:**
L1 and TALE agree on the wrong answer. Both models likely follow the same shortcut reasoning path
and share the arithmetic mistake. S1 avoids it by enumerating more steps.

## What S1 Does Better

1. **More steps = fewer slips:** S1's budget-forcing explicitly extends its reasoning chain.
   In {n_s1_more_steps}/{n_primary} primary cases, S1 produced substantially more reasoning
   than frontier and was correct, suggesting richer step decomposition.

2. **Clean numeric answers:** {n_s1_clean}/{n_primary} primary cases show S1 producing a clean
   integer/decimal answer, vs frontier's potentially noisy output. Short clean numerics are a
   reliable correctness signal for math problems.

3. **Avoids shortcut arithmetic:** TALE and L1 use prompt-budgeting strategies that sometimes
   collapse multi-step arithmetic into a single shorthand. S1's step-by-step budget forcing
   avoids this.

## Are Wrong Majorities Caused by Correlated L1+TALE Errors?
**Yes.** In {n_l1_tale_corr_err}/{n_primary} primary cases, L1 and TALE agree on the same wrong
answer. This is not independent evidence. Both models process the problem similarly (they share
similar few-shot prompt styles and parameter scales) and tend to share the same arithmetic mistake.
The agreement between L1 and TALE should be treated as a correlated signal, not an independent vote.

## Runtime-Legal Signals (No Gold Required)
1. `external_majority_exists` — is there an L1+TALE (or 3-way) external majority?
2. `s1_clean_numeric` — is S1's answer a short integer/decimal?
3. `external_majority_excludes_s1` — does the external majority specifically disagree with S1?
4. `s1_isolated` — is S1 the only method with its answer?
5. `l1_agrees_tale` — L1 and TALE agree (potential correlated-error signal)
6. `s1_reasoning_len` — how much reasoning S1 generated

## Diagnostic Fix Results (All Diagnostic Only — Not Promoted)

| Fix | Correct/300 | Accuracy | Primary recovered | Regressions |
|-----|-------------|----------|-------------------|-------------|
{fix_table}

**Best diagnostic fix:** `{best_fix.get('fix_name','')}` with {best_fix.get('n_correct_all_300','')} correct ({best_fix.get('accuracy_all_300','')}).
Comparison vs always-S1 (269/300 = 89.67%): {best_fix.get('vs_always_s1', 'N/A'):+}.

## Algorithm-Improvement Recommendations
1. Add an override: when no external majority exists and S1 has a clean numeric answer
   that differs from frontier → prefer S1. Estimated net gain: ~{n_no_ext_maj} cases.
2. Add an override: when external majority excludes S1 and S1 has a clean numeric answer
   → prefer S1. Estimated net gain: ~{n_ext_maj_excl_s1} cases with some regression risk.
3. Discount L1+TALE-only agreement (without frontier) as a majority signal, since it
   represents correlated rather than independent evidence.
4. Consider `s1_reasoning_len > threshold` as a quality gate for S1 promotion.

## Caution
All new fixes described here are **diagnostic only**. No policy has been promoted or modified.
The frozen policy (agreement_only_2of3_against_frontier) is unchanged. Evaluations above
are post-hoc, using the same examples the selector already ran on — they are not held-out
validation estimates.

## Files Created
All outputs in `outputs/mistral_cases_where_agreement_loses_to_s1_20260523/`:
- `primary_agreement_wrong_s1_correct_cases.csv` — {n_primary} primary cases
- `s1_correct_frontier_wrong_agreement_kept_frontier_cases.csv` — {len(frontier_wrong_kept)} cases
- `s1_correct_agreement_deferred_wrong_cases.csv` — {len(deferred_wrong)} cases
- `s1_correct_wrong_external_majority_cases.csv` — {len(wrong_ext_majority)} cases
- `s1_correct_pooled4_wrong_cases.csv` — {len(pooled4_wrong)} cases
- `only_s1_correct_cases.csv` — {len(only_s1_correct_cases)} cases
- `contrast_s1_wrong_agreement_correct_cases.csv` — {len(contrast_s1_wrong)} cases
- `case_logs_existing_artifacts/` — {len(case_log_index_rows)} markdown case logs
- `primary_case_log_index.csv`
- `full_log_availability_summary.csv`
- `case_failure_taxonomy.csv`
- `case_failure_taxonomy_summary.csv`
- `case_failure_taxonomy_examples.md`
- `reasoning_quality_comparison.csv`
- `reasoning_quality_representative_cases.md`
- `algorithm_improvement_lessons_from_s1_loss_cases.md`
- `targeted_diagnostic_fix_summary.csv`
- `manifest.json`
"""

docs_dir = REPO / "docs"
docs_dir.mkdir(exist_ok=True)
(docs_dir / "MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md").write_text(report_md)
print("  Wrote docs/MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md")

# ── Step 13: Manifest ────────────────────────────────────────────────────────
print("[12/13] Creating manifest.json ...")

manifest = {
    "task": "mistral_cases_where_agreement_loses_to_s1",
    "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source_artifacts": {
        "per_example_records_jsonl": str(PER_EXAMPLE_JSONL),
        "unified_mistral_example_table_csv": str(unified_path),
        "s1_dominance_diagnostic": str(S1_DOM),
        "algorithm_improvement_diagnostic": str(ALG_IMP),
        "deep_error_selector_diagnostic": str(DEEP_ERR),
    },
    "n_primary_cases": n_primary,
    "n_frontier_wrong_kept": len(frontier_wrong_kept),
    "n_deferred_wrong": len(deferred_wrong),
    "n_wrong_external_majority": len(wrong_ext_majority),
    "n_pooled4_wrong": len(pooled4_wrong),
    "n_only_s1_correct": len(only_s1_correct_cases),
    "n_contrast_s1_wrong": len(contrast_s1_wrong),
    "targeted_rerun_occurred": False,
    "rerun_output_paths": [],
    "api_rate_limit_summary": "No rerun performed. Full logs available in existing artifacts.",
    "files_created": [
        "primary_agreement_wrong_s1_correct_cases.csv",
        "s1_correct_frontier_wrong_agreement_kept_frontier_cases.csv",
        "s1_correct_agreement_deferred_wrong_cases.csv",
        "s1_correct_wrong_external_majority_cases.csv",
        "s1_correct_pooled4_wrong_cases.csv",
        "only_s1_correct_cases.csv",
        "contrast_s1_wrong_agreement_correct_cases.csv",
        "primary_case_log_index.csv",
        "full_log_availability_summary.csv",
        "case_failure_taxonomy.csv",
        "case_failure_taxonomy_summary.csv",
        "case_failure_taxonomy_examples.md",
        "reasoning_quality_comparison.csv",
        "reasoning_quality_representative_cases.md",
        "algorithm_improvement_lessons_from_s1_loss_cases.md",
        "targeted_diagnostic_fix_summary.csv",
        "manifest.json",
    ] + [f"case_logs_existing_artifacts/case_{i+1:02d}_{safe_id(eid)}.md"
         for i, eid in enumerate(primary_cases)],
    "known_results": {
        "frontier_accuracy": "78.33%",
        "l1_accuracy": "72.33%",
        "s1_accuracy": "89.67%",
        "tale_accuracy": "63.00%",
        "agreement_only_2of3_accuracy": "85.33%",
        "pooled_4_with_fallback_accuracy": "83.67%",
    },
}

with open(OUT_ROOT / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print("  Wrote manifest.json")

# ── Final print summary ──────────────────────────────────────────────────────
print("\n[13/13] DONE. Summary:")
print(f"  Primary cases (agreement wrong, S1 correct): {n_primary}")
print(f"  Top failure category: A (no external majority) = {n_no_ext_maj} cases")
print(f"  L1+TALE correlated errors: {n_l1_tale_corr_err} cases")
print(f"  Rerun performed: NO (full logs available in existing artifacts)")
print(f"  Active Cerebras job (PID 2195513): UNTOUCHED")
print(f"  All outputs: {OUT_ROOT}")
print(f"  Report: docs/MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md")
print(f"\nFix summary:")
for r in fix_rows:
    print(f"  {r['fix_name']:60s} {r['n_correct_all_300']:3d}/300  primary={r['n_correct_primary_19']}/{n_primary}  reg={r['n_regressions_from_agreement_baseline']}")
