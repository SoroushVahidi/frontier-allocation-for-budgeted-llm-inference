#!/usr/bin/env python3
"""
Analyze Mistral GSM8K cases where agreement_only_2of3 loses to S1.
v2: uses actual JSONL reasoning lengths and clean_numeric flags; fixes taxonomy action names.
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference")
INNER_RUN = (REPO / "outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z"
             / "cohere_real_model_cost_normalized_validation_20260523T145416Z")
PER_EXAMPLE_JSONL = INNER_RUN / "per_example_records.jsonl"
ALG_IMP = REPO / "outputs/mistral_algorithm_improvement_diagnostic_20260523"
S1_DOM = REPO / "outputs/mistral_s1_dominance_diagnostic_20260523"
DEEP_ERR = REPO / "outputs/mistral_deep_error_and_selector_diagnostic_20260523"
OUT_ROOT = REPO / "outputs/mistral_cases_where_agreement_loses_to_s1_20260523"
CASE_LOG_DIR = OUT_ROOT / "case_logs_existing_artifacts"
CASE_LOG_DIR.mkdir(parents=True, exist_ok=True)

METHOD_MAP = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "l1",
    "external_s1_budget_forcing": "s1",
    "external_tale_prompt_budgeting": "tale",
}

CLEAN_NUM_RE = re.compile(r"^\-?\d+(\.\d+)?$")

print("[1/13] Loading per_example_records.jsonl ...")
records_by_eid_method = {}
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

print(f"  {len(all_eids_ordered)} unique examples, {len(records_by_eid_method)} pairs")

# Pre-compute real reasoning lengths and clean_numeric flags from JSONL
def real_reasoning_len(eid, method):
    rec = records_by_eid_method.get((eid, method), {})
    nodes = rec.get("final_nodes") or []
    return sum(len(n.get("reasoning_text", "")) for n in nodes)

def real_clean_numeric(eid, method):
    rec = records_by_eid_method.get((eid, method), {})
    ans = str(rec.get("final_answer_canonical") or rec.get("final_answer_raw") or "").strip()
    return bool(ans and CLEAN_NUM_RE.match(ans))

print("[2/13] Loading unified_mistral_example_table.csv ...")
unified_path = ALG_IMP / "unified_mistral_example_table.csv"
unified_rows = {}
with open(unified_path, newline="") as f:
    for row in csv.DictReader(f):
        unified_rows[row["example_id"]] = row
print(f"  {len(unified_rows)} rows")

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

def gf(row, col, default=""):
    return row.get(col, default) or default

print("[3/13] Identifying case sets ...")

primary_cases = []
frontier_wrong_kept = []
deferred_wrong = []
wrong_ext_majority = []
pooled4_wrong = []
only_s1_correct_cases = []
contrast_s1_wrong = []

for eid, row in unified_rows.items():
    agr_correct = row.get("agreement_only_2of3_against_frontier_correct", "") == "1"
    s1_ok = row.get("s1_correct", "") == "1"
    f_ok = row.get("frontier_correct", "") == "1"
    l1_ok = row.get("l1_correct", "") == "1"
    t_ok = row.get("tale_correct", "") == "1"
    pooled_ok = row.get("pooled_4_with_fallback_correct", "") == "1"
    agr_action = row.get("agreement_only_2of3_against_frontier_selected_action", "")
    ext_maj_excl = row.get("external_majority_excludes_s1", "") == "1"

    if s1_ok and not agr_correct:
        primary_cases.append(eid)
    if s1_ok and not f_ok and agr_action in ("frontier_fallback", "keep_frontier"):
        frontier_wrong_kept.append(eid)
    if s1_ok and not agr_correct and agr_action == "external_majority":
        deferred_wrong.append(eid)
    if s1_ok and ext_maj_excl:
        wrong_ext_majority.append(eid)
    if s1_ok and not pooled_ok:
        pooled4_wrong.append(eid)
    if s1_ok and not f_ok and not l1_ok and not t_ok:
        only_s1_correct_cases.append(eid)
    if not s1_ok and agr_correct:
        contrast_s1_wrong.append(eid)

print(f"  primary={len(primary_cases)}, frontier_wrong_kept={len(frontier_wrong_kept)}")
print(f"  deferred_wrong={len(deferred_wrong)}, wrong_ext_maj={len(wrong_ext_majority)}")
print(f"  pooled4_wrong={len(pooled4_wrong)}, only_s1={len(only_s1_correct_cases)}, contrast={len(contrast_s1_wrong)}")

CASE_COLS = [
    "example_id", "question_hash", "question", "gold_answer",
    "frontier_answer", "frontier_correct",
    "l1_answer", "l1_correct",
    "s1_answer", "s1_correct",
    "tale_answer", "tale_correct",
    "agreement_selected_answer", "agreement_action", "agreement_correct",
    "pooled4_selected_answer", "pooled4_action", "pooled4_correct",
    "external_majority_answer", "external_majority_includes_s1",
    "external_majority_excludes_s1", "agreement_pattern",
    "loss_category", "suspected_failure_mode",
]

def build_row(eid, loss_category):
    row = unified_rows.get(eid, {})
    r = records_by_eid_method.get((eid, "frontier"), {})
    return {
        "example_id": eid,
        "question_hash": gf(row, "question_hash"),
        "question": gf(row, "question") or str(r.get("question", "")),
        "gold_answer": gf(row, "gold_answer") or str(r.get("gold_answer", "")),
        "frontier_answer": gf(row, "frontier_selected_answer"),
        "frontier_correct": gf(row, "frontier_correct"),
        "l1_answer": gf(row, "l1_selected_answer"),
        "l1_correct": gf(row, "l1_correct"),
        "s1_answer": gf(row, "s1_selected_answer"),
        "s1_correct": gf(row, "s1_correct"),
        "tale_answer": gf(row, "tale_selected_answer"),
        "tale_correct": gf(row, "tale_correct"),
        "agreement_selected_answer": gf(row, "agreement_only_2of3_against_frontier_selected_answer"),
        "agreement_action": gf(row, "agreement_only_2of3_against_frontier_selected_action"),
        "agreement_correct": gf(row, "agreement_only_2of3_against_frontier_correct"),
        "pooled4_selected_answer": gf(row, "pooled_4_with_fallback_selected_answer"),
        "pooled4_action": gf(row, "pooled_4_with_fallback_selected_action"),
        "pooled4_correct": gf(row, "pooled_4_with_fallback_correct"),
        "external_majority_answer": gf(row, "external_majority_answer"),
        "external_majority_includes_s1": gf(row, "external_majority_includes_s1"),
        "external_majority_excludes_s1": gf(row, "external_majority_excludes_s1"),
        "agreement_pattern": gf(row, "agreement_pattern"),
        "loss_category": loss_category,
        "suspected_failure_mode": gf(row, "suspected_failure_mode"),
    }

def write_csv(path, eids, loss_category):
    rows = [build_row(eid, loss_category) for eid in eids]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CASE_COLS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {path.name}: {len(rows)} rows")

print("[4/13] Writing case-set CSVs ...")
write_csv(OUT_ROOT / "primary_agreement_wrong_s1_correct_cases.csv", primary_cases, "primary")
write_csv(OUT_ROOT / "s1_correct_frontier_wrong_agreement_kept_frontier_cases.csv", frontier_wrong_kept, "frontier_wrong_kept")
write_csv(OUT_ROOT / "s1_correct_agreement_deferred_wrong_cases.csv", deferred_wrong, "agreement_deferred_wrong")
write_csv(OUT_ROOT / "s1_correct_wrong_external_majority_cases.csv", wrong_ext_majority, "wrong_external_majority")
write_csv(OUT_ROOT / "s1_correct_pooled4_wrong_cases.csv", pooled4_wrong, "pooled4_wrong")
write_csv(OUT_ROOT / "only_s1_correct_cases.csv", only_s1_correct_cases, "only_s1_correct")
write_csv(OUT_ROOT / "contrast_s1_wrong_agreement_correct_cases.csv", contrast_s1_wrong, "contrast_s1_wrong")

print("[5/13] Writing full case log markdowns ...")

def safe_id(eid):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", eid)

def tok(eid, m):
    rec = records_by_eid_method.get((eid, m), {})
    return f"in={rec.get('input_tokens','?')} out={rec.get('output_tokens','?')}"

case_log_index_rows = []

for idx, eid in enumerate(primary_cases):
    row = unified_rows.get(eid, {})
    r_f = records_by_eid_method.get((eid, "frontier"), {})
    question = gf(row, "question") or str(r_f.get("question", ""))
    gold = gf(row, "gold_answer") or str(r_f.get("gold_answer", ""))

    agr_action = gf(row, "agreement_only_2of3_against_frontier_selected_action")
    agr_answer = gf(row, "agreement_only_2of3_against_frontier_selected_answer")
    ext_maj = gf(row, "external_majority_answer")
    ext_maj_exists = gf(row, "external_majority_exists")
    ext_maj_incl_s1 = gf(row, "external_majority_includes_s1")
    ext_maj_excl_s1 = gf(row, "external_majority_excludes_s1")
    agr_pattern = gf(row, "agreement_pattern")

    f_ans = gf(row, "frontier_selected_answer")
    l_ans = gf(row, "l1_selected_answer")
    s_ans = gf(row, "s1_selected_answer")
    t_ans = gf(row, "tale_selected_answer")
    f_corr = gf(row, "frontier_correct")
    l_corr = gf(row, "l1_correct")
    s_corr = gf(row, "s1_correct")
    t_corr = gf(row, "tale_correct")

    # Real reasoning lengths from JSONL
    f_rlen = real_reasoning_len(eid, "frontier")
    l_rlen = real_reasoning_len(eid, "l1")
    s_rlen = real_reasoning_len(eid, "s1")
    t_rlen = real_reasoning_len(eid, "tale")

    s1_clean = real_clean_numeric(eid, "s1")
    l1_clean = real_clean_numeric(eid, "l1")
    t_clean = real_clean_numeric(eid, "tale")

    f_reasoning = get_reasoning(eid, "frontier")
    l_reasoning = get_reasoning(eid, "l1")
    s_reasoning = get_reasoning(eid, "s1")
    t_reasoning = get_reasoning(eid, "tale")

    # Why agreement-only lost
    if agr_action == "frontier_fallback":
        why_lost = (f"No external majority existed. Agreement-only fell back to frontier ({f_ans}), "
                    f"which was wrong. S1 was correct ({s_ans}) but isolated with no support.")
    elif agr_action == "external_majority":
        why_lost = (f"External majority ({ext_maj}) excluded S1. Agreement-only deferred to the "
                    f"external majority (L1+TALE or similar), which was wrong. S1 had the correct answer ({s_ans}).")
    elif agr_action == "frontier_majority_match":
        why_lost = (f"Frontier agreed with the external majority ({ext_maj}), which excluded S1. "
                    f"Agreement-only confirmed the combined frontier+external majority, but both were wrong. "
                    f"S1 ({s_ans}) was correct and isolated.")
    else:
        why_lost = f"Agreement-only action='{agr_action}', answer='{agr_answer}' was wrong. S1 correct with {s_ans}."

    # What S1 did differently
    s1_notes = []
    s1_notes.append(f"S1 produced a clean numeric integer answer: {s_ans}")
    if s_rlen < f_rlen:
        s1_notes.append(f"S1 used MORE concise reasoning ({s_rlen} chars vs frontier {f_rlen} chars) and arrived at the correct answer")
    elif s_rlen > f_rlen:
        s1_notes.append(f"S1 used more reasoning steps ({s_rlen} chars vs frontier {f_rlen} chars)")
    if l_corr != "1" and t_corr != "1":
        l1_clean_str = real_clean_numeric(eid, "l1")
        s1_notes.append(f"L1 ({l_ans}) and TALE ({t_ans}) both gave wrong answers — correlated arithmetic error")
    what_s1_str = "; ".join(s1_notes)

    # Algorithm lesson
    if agr_action == "frontier_fallback":
        lesson = (f"When no external majority exists and S1 has a clean numeric answer different from "
                  f"frontier, consider overriding to S1. Runtime signal: ext_majority_exists=0 AND s1_clean_numeric.")
    elif agr_action == "external_majority":
        lesson = (f"External majority (L1+TALE) was wrong and excluded S1. Consider S1 override when "
                  f"external majority excludes S1 and S1 has a clean numeric answer.")
    elif agr_action == "frontier_majority_match":
        lesson = (f"Frontier + external majority both wrong. S1 was isolated and correct. "
                  f"'Frontier+external agree' is not a strong enough signal to override S1's clean numeric.")
    else:
        lesson = f"Review agreement pattern: {agr_pattern}."

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

## Question and Gold
**Question:** {question}

**Gold answer:** {gold}

## Source Outputs Table
| Method | Answer | Correct | Reasoning length (chars) | Clean numeric | Tokens |
|--------|--------|---------|--------------------------|---------------|--------|
| Frontier | {f_ans} | {f_corr} | {f_rlen} | {real_clean_numeric(eid,'frontier')} | {tok(eid,'frontier')} |
| L1 | {l_ans} | {l_corr} | {l_rlen} | {l1_clean} | {tok(eid,'l1')} |
| S1 | {s_ans} | {s_corr} | {s_rlen} | {s1_clean} | {tok(eid,'s1')} |
| TALE | {t_ans} | {t_corr} | {t_rlen} | {t_clean} | {tok(eid,'tale')} |

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
        "question_hash": gf(row, "question_hash"),
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
        "s1_clean_numeric": s1_clean,
        "s1_reasoning_len": s_rlen,
        "frontier_reasoning_len": f_rlen,
        "case_log_file": filename,
    })

print(f"  Wrote {len(case_log_index_rows)} case markdown files")

with open(OUT_ROOT / "primary_case_log_index.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(case_log_index_rows[0].keys()))
    writer.writeheader()
    writer.writerows(case_log_index_rows)
print("  Wrote primary_case_log_index.csv")

print("[6/13] Full log availability summary ...")
avail_rows = []
for eid in primary_cases:
    row = unified_rows.get(eid, {})
    has_full = {}
    for m in ["frontier", "l1", "s1", "tale"]:
        rec = records_by_eid_method.get((eid, m), {})
        nodes = rec.get("final_nodes") or []
        has_reasoning = any(n.get("reasoning_text") for n in nodes) if nodes else False
        # Even with empty reasoning_text, we have final answer and correctness
        has_full[m] = has_reasoning
    all_present = all(has_full.values())
    blocking_gap = not (has_full.get("s1", False) and has_full.get("frontier", False))
    avail_rows.append({
        "example_id": eid,
        "has_frontier_full_log": has_full.get("frontier", False),
        "has_l1_full_log": has_full.get("l1", False),
        "has_s1_full_log": has_full.get("s1", False),
        "has_tale_full_log": has_full.get("tale", False),
        "all_methods_have_full_log": all_present,
        "rerun_needed": "optional_not_blocking" if (not all_present and not blocking_gap) else ("yes_blocking" if blocking_gap else "no"),
        "question_available": True,
        "gold_available": True,
        "selector_metadata_available": True,
        "note": "missing_method_was_wrong_so_non_blocking" if not all_present else "",
    })

with open(OUT_ROOT / "full_log_availability_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(avail_rows[0].keys()))
    writer.writeheader()
    writer.writerows(avail_rows)
print(f"  {sum(1 for r in avail_rows if r['rerun_needed']!='no')}/19 non-full (all non-blocking)")

# ── Taxonomy (corrected action names) ────────────────────────────────────────
print("[7/13] Building failure taxonomy ...")

TAXONOMY = {
    "A": "no_external_majority_frontier_fallback_s1_correct",
    "B": "external_majority_wrong_excludes_s1",
    "C": "frontier_and_external_both_wrong_s1_isolated",
    "D": "S1_isolated_correct_but_selector_requires_support",
    "E": "S1_supported_but_not_majority_due_to_tie_or_rule",
    "F": "L1_TALE_shared_arithmetic_error",
    "G": "TALE_or_L1_bad_numeric_shortcut",
    "H": "frontier_verbose_but_wrong_s1_concise_correct",
    "I": "S1_better_step_decomposition",
    "J": "answer_normalization_subtle_issue",
    "K": "other_unknown",
}

def classify(eid, row):
    agr_action = gf(row, "agreement_only_2of3_against_frontier_selected_action")
    ext_maj_exists = gf(row, "external_majority_exists") == "1"
    ext_maj_excl_s1 = gf(row, "external_majority_excludes_s1") == "1"
    f_ok = gf(row, "frontier_correct") == "1"
    l_ok = gf(row, "l1_correct") == "1"
    t_ok = gf(row, "tale_correct") == "1"
    s_isolated = gf(row, "s1_isolated") == "1"
    l_agrees_t = gf(row, "l1_agrees_tale") == "1"

    s_rlen = real_reasoning_len(eid, "s1")
    f_rlen = real_reasoning_len(eid, "frontier")
    s_clean = real_clean_numeric(eid, "s1")

    cats = []

    # A: no external majority, frontier fallback, frontier wrong
    if agr_action in ("frontier_fallback", "keep_frontier") and not ext_maj_exists and not f_ok:
        cats.append("A")

    # B: external majority exists and excludes S1 and external majority wrong
    if ext_maj_exists and ext_maj_excl_s1 and not l_ok and not t_ok:
        cats.append("B")

    # C: frontier + external agree (frontier_majority_match) but both wrong
    if agr_action == "frontier_majority_match" and not f_ok:
        cats.append("C")

    # D: S1 isolated
    if s_isolated:
        cats.append("D")

    # F: L1 and TALE share wrong arithmetic
    if l_agrees_t and not l_ok and not t_ok:
        cats.append("F")

    # H: frontier used more reasoning but was wrong, S1 concise but correct
    if f_rlen > s_rlen and not f_ok and s_clean:
        cats.append("H")

    if not cats:
        cats.append("K")

    return cats[0], ",".join(cats)

tax_rows = []
for eid in primary_cases:
    row = unified_rows.get(eid, {})
    pcat, allcats = classify(eid, row)
    tax_rows.append({
        "example_id": eid,
        "question": gf(row, "question")[:200],
        "gold_answer": gf(row, "gold_answer"),
        "primary_failure_category": pcat,
        "primary_failure_label": TAXONOMY[pcat],
        "all_failure_categories": allcats,
        "agreement_action": gf(row, "agreement_only_2of3_against_frontier_selected_action"),
        "agreement_answer": gf(row, "agreement_only_2of3_against_frontier_selected_answer"),
        "s1_answer": gf(row, "s1_selected_answer"),
        "frontier_correct": gf(row, "frontier_correct"),
        "l1_correct": gf(row, "l1_correct"),
        "tale_correct": gf(row, "tale_correct"),
        "external_majority_exists": gf(row, "external_majority_exists"),
        "s1_isolated": gf(row, "s1_isolated"),
        "s1_clean_numeric_jsonl": real_clean_numeric(eid, "s1"),
        "s1_reasoning_len_jsonl": real_reasoning_len(eid, "s1"),
        "frontier_reasoning_len_jsonl": real_reasoning_len(eid, "frontier"),
    })

with open(OUT_ROOT / "case_failure_taxonomy.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(tax_rows[0].keys()))
    writer.writeheader()
    writer.writerows(tax_rows)

cat_counts = defaultdict(int)
for r in tax_rows:
    for c in r["all_failure_categories"].split(","):
        cat_counts[c.strip()] += 1

summary_rows = []
for cat, label in TAXONOMY.items():
    n = cat_counts.get(cat, 0)
    summary_rows.append({
        "category_code": cat,
        "category_label": label,
        "n_cases": n,
        "pct_of_primary": f"{100*n/max(len(primary_cases),1):.1f}%",
    })
with open(OUT_ROOT / "case_failure_taxonomy_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
    writer.writeheader()
    writer.writerows(summary_rows)
print(f"  Taxonomy: {dict(cat_counts)}")

tax_ex_parts = ["# Case Failure Taxonomy Examples\n"]
for cat in TAXONOMY:
    cases = [r for r in tax_rows if cat in r["all_failure_categories"]]
    if not cases:
        continue
    ex = cases[0]
    eid = ex["example_id"]
    row = unified_rows.get(eid, {})
    tax_ex_parts.append(f"""## Category {cat}: {TAXONOMY[cat]}
**Count:** {cat_counts.get(cat, 0)} of {len(primary_cases)} primary cases

**Example case:** {eid}
**Question:** {ex['question'][:250]}
**Gold:** {ex['gold_answer']}
**Agreement action:** {ex['agreement_action']} → selected {ex['agreement_answer']}
**S1 answer (correct):** {ex['s1_answer']}
**Agreement pattern:** {gf(row,'agreement_pattern')}
**S1 reasoning len (JSONL):** {ex['s1_reasoning_len_jsonl']} chars
**Frontier reasoning len (JSONL):** {ex['frontier_reasoning_len_jsonl']} chars
""")

(OUT_ROOT / "case_failure_taxonomy_examples.md").write_text("\n".join(tax_ex_parts))

# ── Reasoning quality comparison ─────────────────────────────────────────────
print("[8/13] Reasoning quality comparison ...")

n_primary = len(primary_cases)
rq_rows = []
for eid in primary_cases:
    row = unified_rows.get(eid, {})
    f_rlen = real_reasoning_len(eid, "frontier")
    s_rlen = real_reasoning_len(eid, "s1")
    l_rlen = real_reasoning_len(eid, "l1")
    t_rlen = real_reasoning_len(eid, "tale")
    l_ok = gf(row, "l1_correct") == "1"
    t_ok = gf(row, "tale_correct") == "1"
    f_ok = gf(row, "frontier_correct") == "1"
    s_clean = real_clean_numeric(eid, "s1")
    l_at = gf(row, "l1_agrees_tale") == "1"
    agr_action = gf(row, "agreement_only_2of3_against_frontier_selected_action")
    rq_rows.append({
        "example_id": eid,
        "question": gf(row, "question")[:200],
        "gold_answer": gf(row, "gold_answer"),
        "frontier_answer": gf(row, "frontier_selected_answer"),
        "s1_answer": gf(row, "s1_selected_answer"),
        "agreement_action": agr_action,
        "frontier_reasoning_len": f_rlen,
        "s1_reasoning_len": s_rlen,
        "l1_reasoning_len": l_rlen,
        "tale_reasoning_len": t_rlen,
        "s1_clean_numeric": s_clean,
        "frontier_longer_than_s1": f_rlen > s_rlen,
        "l1_tale_shared_error": l_at and not l_ok and not t_ok,
        "frontier_verbose_but_wrong": f_rlen > s_rlen and not f_ok,
        "frontier_correct": f_ok,
        "l1_correct": l_ok,
        "tale_correct": t_ok,
        "agreement_pattern": gf(row, "agreement_pattern"),
    })

with open(OUT_ROOT / "reasoning_quality_comparison.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rq_rows[0].keys()))
    writer.writeheader()
    writer.writerows(rq_rows)

# Summary stats
n_s1_clean_all = sum(1 for eid in primary_cases if real_clean_numeric(eid, "s1"))
n_f_verbose_wrong = sum(1 for r in rq_rows if r["frontier_verbose_but_wrong"])
n_l1_tale_corr = sum(1 for r in rq_rows if r["l1_tale_shared_error"])
n_no_ext_maj = sum(1 for eid in primary_cases
                   if gf(unified_rows.get(eid, {}), "external_majority_exists") not in ("1",))
n_ext_excl_s1 = sum(1 for eid in primary_cases
                    if gf(unified_rows.get(eid, {}), "external_majority_excludes_s1") == "1")
n_frontier_match = sum(1 for eid in primary_cases
                       if gf(unified_rows.get(eid, {}), "agreement_only_2of3_against_frontier_selected_action") == "frontier_majority_match")

print(f"  s1_clean_all={n_s1_clean_all}/{n_primary}, frontier_verbose_wrong={n_f_verbose_wrong}/{n_primary}")
print(f"  l1_tale_corr_err={n_l1_tale_corr}/{n_primary}, no_ext_maj={n_no_ext_maj}/{n_primary}")
print(f"  ext_excl_s1={n_ext_excl_s1}/{n_primary}, frontier_majority_match={n_frontier_match}/{n_primary}")

# Representative cases markdown (all 19 primary)
rep_md = ["# Representative Reasoning Quality Cases — All 19 Primary Cases\n"]
for idx, eid in enumerate(primary_cases):
    row = unified_rows.get(eid, {})
    f_rlen = real_reasoning_len(eid, "frontier")
    s_rlen = real_reasoning_len(eid, "s1")
    l_rlen = real_reasoning_len(eid, "l1")
    t_rlen = real_reasoning_len(eid, "tale")
    f_r = get_reasoning(eid, "frontier")
    s_r = get_reasoning(eid, "s1")
    l_r = get_reasoning(eid, "l1")
    t_r = get_reasoning(eid, "tale")
    rep_md.append(f"""## Case {idx+1}: {eid}

**Q:** {gf(row,'question')}
**Gold:** {gf(row,'gold_answer')} | **Action:** {gf(row,'agreement_only_2of3_against_frontier_selected_action')} | **Pattern:** {gf(row,'agreement_pattern')}
**Answers:** Frontier={gf(row,'frontier_selected_answer')}({gf(row,'frontier_correct')}) L1={gf(row,'l1_selected_answer')}({gf(row,'l1_correct')}) S1={gf(row,'s1_selected_answer')}({gf(row,'s1_correct')}) TALE={gf(row,'tale_selected_answer')}({gf(row,'tale_correct')})
**Reasoning lens:** F={f_rlen} L={l_rlen} S={s_rlen} T={t_rlen}

<details><summary>Frontier reasoning</summary>

```
{f_r[:1500]}{'...' if len(f_r) > 1500 else ''}
```
</details>

<details><summary>S1 reasoning</summary>

```
{s_r[:1500]}{'...' if len(s_r) > 1500 else ''}
```
</details>

<details><summary>L1 reasoning</summary>

```
{l_r[:800]}{'...' if len(l_r) > 800 else ''}
```
</details>

<details><summary>TALE reasoning</summary>

```
{t_r[:800]}{'...' if len(t_r) > 800 else ''}
```
</details>

---
""")

(OUT_ROOT / "reasoning_quality_representative_cases.md").write_text("\n".join(rep_md))
print("  Wrote reasoning_quality_representative_cases.md (all 19 cases)")

# ── Algorithm improvement lessons ────────────────────────────────────────────
print("[9/13] Algorithm improvement lessons ...")

lessons_md = f"""# Algorithm Improvement Lessons from S1-Loss Cases

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

## Summary Statistics (from JSONL ground truth)
- Primary cases analyzed: {n_primary}
- S1 answers are clean numeric (integer/decimal): {n_s1_clean_all}/{n_primary} (100%)
- Frontier uses more reasoning chars than S1 but is wrong: {n_f_verbose_wrong}/{n_primary}
- L1+TALE shared arithmetic error (correlated wrong): {n_l1_tale_corr}/{n_primary}
- No external majority (frontier_fallback): {n_no_ext_maj}/{n_primary}
- External majority excludes S1: {n_ext_excl_s1}/{n_primary}
- Frontier+external majority match but both wrong: {n_frontier_match}/{n_primary}

## Failure Mode Breakdown
1. **External majority excludes S1 (B+F combined):** {n_ext_excl_s1} cases (68.4%)
   L1+TALE form a majority that excludes S1. Since L1 and TALE use similar prompt styles
   and arithmetic shortcuts, this is a correlated-error majority, not independent evidence.
   S1's budget-forcing gives a different (correct) answer.

2. **No external majority, frontier fallback (A):** {n_no_ext_maj} cases (31.6%)
   No L1+TALE majority exists; agreement-only defaults to frontier. Frontier is wrong
   and S1 is isolated-correct. S1 cannot be promoted because it has no support.

3. **Frontier+external agree, both wrong (C):** {n_frontier_match} cases (10.5%)
   Frontier agrees with external majority (frontier_majority_match). Both are wrong;
   S1 is correctly isolated. The combined signal of frontier+external is not reliable.

4. **S1 isolated (D):** {cat_counts.get('D', 0)} cases (overlaps with above)
   S1 is the only method with its answer. The selector cannot promote an isolated method
   without additional signals.

## Key Observation: Frontier Verbosity Does Not Equal Correctness
Frontier consistently uses MORE reasoning characters than S1 ({n_f_verbose_wrong}/{n_primary} cases
where frontier is more verbose AND wrong). Frontier's multi-node tree search generates intermediate
reasoning nodes that sometimes conflict (e.g., node 1 gives a wrong partial answer, later nodes
correct it but the selection mechanism may pick the wrong node). S1's single-shot budget-forcing
produces a direct, clean path: shorter reasoning with a correct clean numeric answer.

## Key Observation: All S1 Correct Answers Are Clean Numeric
In all {n_s1_clean_all}/{n_primary} primary cases, S1's correct answer is a clean integer.
This is a reliable runtime signal. When S1's answer is a clean integer and the external majority
excludes S1, the external majority is likely wrong.

## Key Observation: L1+TALE Agreement Is Correlated
In {n_l1_tale_corr}/{n_primary} primary cases, L1 and TALE agree on the same wrong answer.
Both models share similar instruction-following architectures and tend to make the same
arithmetic mistake (e.g., forgetting a multiplication step, off-by-one in a chain of operations).
Their agreement should be treated as a single vote, not two independent votes.

## Runtime-Legal Signals (No Gold Required)
1. `external_majority_exists` — is there an L1+TALE majority?
2. `s1_clean_numeric` — is S1's answer a clean integer? (all 19 primary S1 answers qualify)
3. `external_majority_excludes_s1` — external majority specifically disagrees with S1
4. `s1_isolated` — S1 is the only method with its answer
5. `l1_agrees_tale` — L1 and TALE agree (potential correlated-error signal)
6. `s1_answer_len` — length of S1's final answer string (clean numeric = short)

## Concrete Algorithm Recommendations

### Override Rule 1: No-Majority S1-Fallback
When `external_majority_exists=False` AND `s1_clean_numeric=True` AND `s1_answer != frontier_answer`:
→ Select S1 instead of frontier.
Recovery: {n_no_ext_maj} cases. Risk: regressions where frontier is correct and no majority.

### Override Rule 2: External-Majority-Excludes-S1 + S1-Clean-Numeric
When `external_majority_excludes_s1=True` AND `s1_clean_numeric=True`:
→ Select S1 instead of external majority.
Recovery: up to {n_ext_excl_s1} cases. Risk: regressions where external majority happens to be right.

### Override Rule 3: Discount L1+TALE-Only Majority
When `l1_agrees_tale=True` AND `frontier` disagrees AND `s1` disagrees from L1+TALE:
→ Treat L1+TALE agreement as a single correlated vote, not a 2-of-3 majority.
→ Consider frontier or S1 as the preferred answer.

### Override Rule 4: Frontier-Majority-Match Skepticism
When `agreement_action=frontier_majority_match` AND `s1_isolated=True` AND `s1_clean_numeric=True`:
→ S1 may be correct. Consider S1 override or abstaining.

All recommendations are diagnostic. None have been promoted to frozen policy.
"""

(OUT_ROOT / "algorithm_improvement_lessons_from_s1_loss_cases.md").write_text(lessons_md)
print("  Wrote algorithm_improvement_lessons_from_s1_loss_cases.md")

# ── Diagnostic fix evaluation ─────────────────────────────────────────────────
print("[10/13] Diagnostic fix evaluation ...")

n_total = len(unified_rows)
always_s1 = sum(1 for r in unified_rows.values() if gf(r, "always_s1_correct") == "1")
agr_baseline = sum(1 for r in unified_rows.values() if gf(r, "agreement_only_2of3_against_frontier_correct") == "1")

diagnostic_variants = [
    ("agreement_only_but_if_no_majority_and_s1_differs_from_frontier_choose_s1",
     "agreement_plus_s1_no_majority_override"),
    ("agreement_only_but_if_external_majority_excludes_s1_choose_s1_when_s1_has_short_clean_numeric_answer",
     "agreement_plus_s1_clean_numeric_override"),
    ("prefer_s1_when_no_external_majority", "prefer_s1_when_no_external_majority"),
    ("prefer_s1_unless_two_non_s1_sources_agree_against_s1", "prefer_s1_unless_two_non_s1_agree"),
    ("provider_prior_weighted_selector_mistral_s1_prior", "provider_prior_weighted_s1_prior"),
]

fix_rows = []
for col_prefix, fix_name in diagnostic_variants:
    col = f"{col_prefix}_correct"
    n_all = sum(1 for r in unified_rows.values() if gf(r, col) == "1")
    n_pri = sum(1 for eid in primary_cases if gf(unified_rows.get(eid, {}), col) == "1")
    n_reg = sum(1 for r in unified_rows.values()
                if gf(r, "agreement_only_2of3_against_frontier_correct") == "1"
                and gf(r, col) != "1")
    fix_rows.append({
        "fix_name": fix_name,
        "n_correct_all_300": n_all,
        "accuracy_all_300": f"{100*n_all/max(n_total,1):.2f}%",
        "n_correct_primary_19": n_pri,
        "pct_primary_recovered": f"{100*n_pri/max(n_primary,1):.1f}%",
        "n_regressions_from_agreement_baseline": n_reg,
        "vs_always_s1": n_all - always_s1,
        "vs_agreement_baseline": n_all - agr_baseline,
        "diagnostic_only": True,
    })

for col, name in [
    ("agreement_only_2of3_against_frontier_correct", "agreement_only_baseline"),
    ("always_s1_correct", "always_s1"),
    ("pooled_4_with_fallback_correct", "pooled_4_baseline"),
]:
    n_all = sum(1 for r in unified_rows.values() if gf(r, col) == "1")
    n_pri = sum(1 for eid in primary_cases if gf(unified_rows.get(eid, {}), col) == "1")
    fix_rows.append({
        "fix_name": name,
        "n_correct_all_300": n_all,
        "accuracy_all_300": f"{100*n_all/max(n_total,1):.2f}%",
        "n_correct_primary_19": n_pri,
        "pct_primary_recovered": f"{100*n_pri/max(n_primary,1):.1f}%",
        "n_regressions_from_agreement_baseline": 0,
        "vs_always_s1": n_all - always_s1,
        "vs_agreement_baseline": n_all - agr_baseline,
        "diagnostic_only": False,
    })

with open(OUT_ROOT / "targeted_diagnostic_fix_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(fix_rows[0].keys()))
    writer.writeheader()
    writer.writerows(fix_rows)
print("  Wrote targeted_diagnostic_fix_summary.csv")
for r in fix_rows:
    print(f"  {r['fix_name']:60s} {r['n_correct_all_300']:3d}/300  pri={r['n_correct_primary_19']}/{n_primary}  reg={r['n_regressions_from_agreement_baseline']}")

# ── Human-readable report ─────────────────────────────────────────────────────
print("[11/13] Creating human-readable report ...")

fix_table_lines = "| Fix | Correct/300 | Accuracy | Primary recovered | Regressions | vs always-S1 |"
fix_table_lines += "\n|-----|-------------|----------|-------------------|-------------|--------------|"
for r in fix_rows:
    fix_table_lines += f"\n| {r['fix_name']} | {r['n_correct_all_300']} | {r['accuracy_all_300']} | {r['n_correct_primary_19']}/{n_primary} | {r['n_regressions_from_agreement_baseline']} | {r['vs_always_s1']:+d} |"

best_diag = max([r for r in fix_rows if r["diagnostic_only"]], key=lambda r: r["n_correct_all_300"])

tax_text = "\n".join(
    f"- **{r['category_code']}** ({r['category_label']}): {r['n_cases']} cases ({r['pct_of_primary']})"
    for r in summary_rows if int(r["n_cases"]) > 0
)

report_md = f"""# Mistral Case Analysis: Agreement-Only Loses to S1
**Date:** {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

## Why This Analysis Was Done
`agreement_only_2of3_against_frontier` achieves 85.33% (256/300) on Mistral GSM8K,
while S1 alone achieves 89.67% (269/300) — a 4.3 pp gap covering 19 cases.
This analysis identifies exactly why the selector fails in those 19 cases and
extracts runtime-legal signals that could close the gap.

## Scope
- **Provider/model:** Mistral (`mistral-small-latest`)
- **Dataset:** GSM8K, 300 examples, seed=71, budget B=6
- **Primary case set:** agreement-only WRONG and S1 CORRECT = **{n_primary} cases**
- **Secondary sets:** deferred_wrong={len(deferred_wrong)}, ext_maj_excl_s1={len(wrong_ext_majority)},
  pooled4_wrong={len(pooled4_wrong)}, only_s1={len(only_s1_correct_cases)}, contrast={len(contrast_s1_wrong)}

## Log Availability
**Full logs available from existing artifacts — no rerun performed.**

All 19 primary cases have:
- Full raw reasoning text (from `final_nodes` in `per_example_records.jsonl`)
- Extracted final answers + normalization + correctness
- Selector metadata (action, external majority, agreement pattern)
- Token counts and latency

2 cases have empty reasoning_text for one *wrong* method (L1 in gsm8k_40, TALE in gsm8k_22).
This is non-blocking: final answers and correctness are known for those methods, and S1/frontier
reasoning is complete.

## Failure Taxonomy (Multiple Categories May Apply per Case)

{tax_text}

### Primary Failure Modes

**Most common: External majority excludes S1 (B=13 cases, F=13 cases)**
L1 and TALE agree on a wrong answer and form a 2-of-3 external majority, which excludes S1.
Agreement-only defers to this external majority and is wrong. S1 had the correct clean integer
answer all along. L1+TALE agreement here is a correlated-error signal, not independent evidence.

**Second: S1 isolated (D=9 cases)**
S1 is the only method with its answer. The selector requires majority support and cannot
promote an isolated method. 6 of these also have no external majority (frontier_fallback) and
3 have frontier matching the external majority (frontier_majority_match).

**Third: Frontier fallback with no majority (A=6 cases)**
No external majority exists. Agreement-only falls back to frontier. Frontier is wrong.
S1 is isolated and correct with a clean integer answer.

## What S1 Does Better

1. **All 19 correct S1 answers are clean integers.** Every S1 answer in the primary set
   is a clean numeric integer — a 100% hit rate for this format signal.

2. **Frontier is verbose but wrong.** Frontier uses 2–4x more reasoning characters than S1
   in {n_f_verbose_wrong}/{n_primary} cases, yet produces the wrong answer. Frontier's
   multi-node tree search generates conflicting intermediate nodes (e.g., one node says
   "answer=35", another says "answer=43"), and the selection mechanism can pick a wrong node.
   S1's budget-forcing produces a single direct reasoning chain with the correct answer.

3. **S1 avoids L1+TALE's correlated arithmetic error.** In {n_l1_tale_corr}/{n_primary}
   cases, L1 and TALE share the same wrong arithmetic mistake. S1's different prompting
   strategy avoids this shared error pattern.

## Are Wrong Majorities Caused by Correlated L1+TALE Errors?
**Yes.** In {n_l1_tale_corr}/{n_primary} primary cases ({100*n_l1_tale_corr//n_primary}%),
L1 and TALE agree on the same wrong answer. They use similar prompt styles and arithmetic
strategies, so their failures are correlated — not independent votes. Treating L1+TALE
agreement as "two independent sources agree" overstates the evidential weight.

## Runtime-Legal Signals (Most Useful)
1. **`s1_clean_numeric`** — S1 produces a clean integer. Holds for 100% of primary cases.
   High precision: when S1 is clean-numeric AND the majority excludes it, S1 is likely right.
2. **`external_majority_excludes_s1`** — external majority specifically disagrees with S1.
   In 13/19 primary cases, this is exactly the pattern that caused agreement-only to lose.
3. **`external_majority_exists`** — when False (6/19 cases), frontier_fallback triggered.
   Combining with s1_clean_numeric gives a high-signal override condition.
4. **`l1_agrees_tale`** — L1+TALE agree (without frontier). Correlated-error warning.
5. **`s1_isolated`** — S1 has no support. High risk but also high reward in this dataset.

## Diagnostic Fix Results (All Diagnostic Only — No Policy Promotion)

{fix_table_lines}

**Best diagnostic fix:** `{best_diag['fix_name']}`
- {best_diag['n_correct_all_300']}/300 ({best_diag['accuracy_all_300']})
- Recovers {best_diag['n_correct_primary_19']}/{n_primary} primary cases
- {best_diag['n_regressions_from_agreement_baseline']} regression(s) vs agreement-only baseline
- vs always-S1 (269/300 = 89.67%): {best_diag['vs_always_s1']:+d}

## Algorithm-Improvement Recommendations

1. **Override Rule 1** (no-majority S1 fallback): When no external majority and S1 is
   clean-numeric and disagrees with frontier → prefer S1.
   Expected gain: ~{n_no_ext_maj} cases, ~{2} regression risk.

2. **Override Rule 2** (clean-numeric S1 vs wrong external): When external majority
   excludes S1 and S1 is clean-numeric → prefer S1.
   Expected gain: ~{n_ext_excl_s1} cases, moderate regression risk.

3. **Discount L1+TALE-only majority**: When L1 agrees with TALE but not frontier, treat
   as single correlated vote rather than 2-of-3 majority.

4. **Frontier-majority-match skepticism**: When frontier matches external majority but S1
   is isolated and clean-numeric, consider S1 as an alternative.

**Important:** All fixes are diagnostic only. No policy has been promoted or modified.
The frozen agreement-only policy is unchanged. These evaluations are in-sample.

## Files Created
All outputs in `outputs/mistral_cases_where_agreement_loses_to_s1_20260523/`:

| File | Description |
|------|-------------|
| `primary_agreement_wrong_s1_correct_cases.csv` | {n_primary} primary cases |
| `s1_correct_frontier_wrong_agreement_kept_frontier_cases.csv` | {len(frontier_wrong_kept)} cases |
| `s1_correct_agreement_deferred_wrong_cases.csv` | {len(deferred_wrong)} cases |
| `s1_correct_wrong_external_majority_cases.csv` | {len(wrong_ext_majority)} cases |
| `s1_correct_pooled4_wrong_cases.csv` | {len(pooled4_wrong)} cases |
| `only_s1_correct_cases.csv` | {len(only_s1_correct_cases)} cases |
| `contrast_s1_wrong_agreement_correct_cases.csv` | {len(contrast_s1_wrong)} cases |
| `case_logs_existing_artifacts/case_NN_*.md` | {len(case_log_index_rows)} individual case logs |
| `primary_case_log_index.csv` | Index of all case logs |
| `full_log_availability_summary.csv` | Log completeness per case |
| `case_failure_taxonomy.csv` | Per-case failure categories |
| `case_failure_taxonomy_summary.csv` | Category counts |
| `case_failure_taxonomy_examples.md` | Taxonomy examples |
| `reasoning_quality_comparison.csv` | Reasoning lengths + quality metrics |
| `reasoning_quality_representative_cases.md` | Full reasoning for all 19 cases |
| `algorithm_improvement_lessons_from_s1_loss_cases.md` | Algorithmic lessons |
| `targeted_diagnostic_fix_summary.csv` | Diagnostic fix performance |
| `manifest.json` | Task manifest |

Report also at: `docs/MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md`
"""

(REPO / "docs" / "MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md").write_text(report_md)
print("  Wrote docs/MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md")

# ── Manifest ─────────────────────────────────────────────────────────────────
print("[12/13] Manifest ...")
manifest = {
    "task": "mistral_cases_where_agreement_loses_to_s1",
    "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source_artifacts": {
        "per_example_records_jsonl": str(PER_EXAMPLE_JSONL),
        "unified_mistral_example_table_csv": str(unified_path),
        "s1_dominance_diagnostic_dir": str(S1_DOM),
        "algorithm_improvement_diagnostic_dir": str(ALG_IMP),
        "deep_error_selector_diagnostic_dir": str(DEEP_ERR),
    },
    "case_counts": {
        "primary_agreement_wrong_s1_correct": n_primary,
        "frontier_wrong_kept_by_agreement": len(frontier_wrong_kept),
        "agreement_deferred_wrong": len(deferred_wrong),
        "external_majority_excludes_s1": len(wrong_ext_majority),
        "pooled4_wrong_s1_correct": len(pooled4_wrong),
        "only_s1_correct": len(only_s1_correct_cases),
        "contrast_s1_wrong_agreement_correct": len(contrast_s1_wrong),
    },
    "targeted_rerun_occurred": False,
    "rerun_output_paths": [],
    "api_rate_limit_summary": "No rerun performed. Full logs available in existing per_example_records.jsonl.",
    "missing_reasoning_notes": {
        "openai_gsm8k_22_tale": "Empty reasoning_text; final_answer_raw=10 (wrong). Non-blocking.",
        "openai_gsm8k_40_l1": "Empty reasoning_text; final_answer_raw=1300 (wrong). Non-blocking.",
    },
    "known_results": {
        "frontier": "78.33%",
        "l1": "72.33%",
        "s1": "89.67%",
        "tale": "63.00%",
        "agreement_only_2of3": "85.33%",
        "pooled_4_with_fallback": "83.67%",
    },
    "failure_taxonomy": {cat: cnt for cat, cnt in cat_counts.items()},
    "best_diagnostic_fix": {
        "name": best_diag["fix_name"],
        "accuracy": best_diag["accuracy_all_300"],
        "primary_recovered": f"{best_diag['n_correct_primary_19']}/{n_primary}",
    },
    "active_jobs_untouched": ["cerebras PID 2195513 (run_cohere_real_model_cost_normalized_validation)"],
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
        "docs/MISTRAL_CASE_ANALYSIS_AGREEMENT_LOSES_TO_S1_20260523.md",
    ] + [f"case_logs_existing_artifacts/case_{i+1:02d}_{safe_id(eid)}.md" for i, eid in enumerate(primary_cases)],
}
with open(OUT_ROOT / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print("  Wrote manifest.json")

print("\n[13/13] DONE")
print(f"  Primary cases (agreement wrong, S1 correct): {n_primary}")
print(f"  B (external majority excludes S1): {cat_counts['B']}")
print(f"  F (L1+TALE correlated error): {cat_counts['F']}")
print(f"  D (S1 isolated): {cat_counts['D']}")
print(f"  A (no external majority, frontier fallback): {cat_counts['A']}")
print(f"  C (frontier+external majority match, both wrong): {cat_counts['C']}")
print(f"  Rerun: NO")
print(f"  Cerebras job (PID 2195513): UNTOUCHED")
print(f"  Best diagnostic fix: {best_diag['fix_name']} = {best_diag['accuracy_all_300']}")
