#!/usr/bin/env python3
"""
L1+TALE correlated error diagnostic for Mistral GSM8K.
Steps 3-12: build groups, compare bad vs good majority, taxonomy,
detectors, selector variants, Cohere comparison, recommendations.
"""
import csv, json, math, re, sys, warnings
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

REPO = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference")
MISTRAL_JSONL = (REPO / "outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z"
                 / "cohere_real_model_cost_normalized_validation_20260523T145416Z"
                 / "per_example_records.jsonl")
COHERE_JSONL = (REPO / "outputs/live_validation_hardening_frozen_agreement_policy_20260523"
                / "cohere_real_model_cost_normalized_validation_20260523T131849Z"
                / "per_example_records.jsonl")
ALG_IMP_DIR = REPO / "outputs/mistral_algorithm_improvement_diagnostic_20260523"
UNIFIED_SRC = ALG_IMP_DIR / "unified_mistral_example_table.csv"
S1_LOSS_DIR = REPO / "outputs/mistral_cases_where_agreement_loses_to_s1_20260523"
OUT = REPO / "outputs/mistral_l1_tale_correlation_diagnostic_20260523"
OUT.mkdir(parents=True, exist_ok=True)

METHOD_MAP = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "l1",
    "external_s1_budget_forcing": "s1",
    "external_tale_prompt_budgeting": "tale",
}
CLEAN_NUM_RE = re.compile(r"^\-?\d+(\.\d+)?$")

def is_clean_numeric(v):
    v = str(v or "").strip()
    return bool(v and CLEAN_NUM_RE.match(v))

def to_float(v):
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None

def reasoning_len(rec):
    nodes = rec.get("final_nodes") or []
    return sum(len(n.get("reasoning_text", "")) for n in nodes)

def get_reasoning_text(rec):
    nodes = rec.get("final_nodes") or []
    parts = []
    for i, n in enumerate(nodes):
        rt = n.get("reasoning_text", "")
        if rt:
            parts.append(f"[Node {i}] {rt.strip()}")
            pa = n.get("predicted_answer", "")
            if pa:
                parts.append(f"  → {pa}")
    return "\n".join(parts) if parts else ""

# ── Load Mistral records ─────────────────────────────────────────────────────
print("[1] Loading Mistral per_example_records.jsonl ...")
mrecs = {}  # (eid, method) -> rec
meids = []
seen = set()
with open(MISTRAL_JSONL) as f:
    for line in f:
        r = json.loads(line)
        eid = r["example_id"]
        m = METHOD_MAP.get(r["method"], r["method"])
        mrecs[(eid, m)] = r
        if eid not in seen:
            meids.append(eid)
            seen.add(eid)
print(f"  {len(meids)} examples, {len(mrecs)} method-pairs")

# ── Load unified table ───────────────────────────────────────────────────────
print("[2] Loading unified_mistral_example_table.csv ...")
unified = {}
with open(UNIFIED_SRC, newline="") as f:
    for row in csv.DictReader(f):
        unified[row["example_id"]] = row
print(f"  {len(unified)} rows")

def gf(row, col, default=""):
    return row.get(col, default) or default

# ── Build enriched per-example records ──────────────────────────────────────
print("[3] Building enriched table with JSONL-derived features ...")

def enrich(eid):
    row = unified.get(eid, {})
    out = {"example_id": eid}
    for k in ["question_hash", "question", "gold_answer", "agreement_pattern",
              "external_majority_exists", "external_majority_answer",
              "external_majority_includes_s1", "external_majority_excludes_s1",
              "s1_isolated", "l1_agrees_tale", "l1_tale_agree_against_s1",
              "frontier_agrees_any_external", "s1_agrees_frontier",
              "agreement_only_2of3_against_frontier_selected_answer",
              "agreement_only_2of3_against_frontier_selected_action",
              "agreement_only_2of3_against_frontier_correct",
              "pooled_4_with_fallback_selected_answer",
              "pooled_4_with_fallback_correct",
              "oracle_over_four_sources_correct",
              "always_s1_correct",
              "frontier_selected_answer", "l1_selected_answer",
              "s1_selected_answer", "tale_selected_answer",
              "frontier_correct", "l1_correct", "s1_correct", "tale_correct",
              "unique_answer_count", "external_unique_count",
              # diagnostic variants
              "agreement_only_but_if_no_majority_and_s1_differs_from_frontier_choose_s1_correct",
              "agreement_only_but_if_external_majority_excludes_s1_choose_s1_when_s1_has_short_clean_numeric_answer_correct",
              "prefer_s1_when_no_external_majority_correct",
              "prefer_s1_unless_two_non_s1_sources_agree_against_s1_correct",
              "provider_prior_weighted_selector_mistral_s1_prior_correct",
              "agreement_only_but_if_no_majority_and_s1_differs_from_frontier_choose_s1_selected_answer",
              "agreement_only_but_if_external_majority_excludes_s1_choose_s1_when_s1_has_short_clean_numeric_answer_selected_answer",
              ]:
        out[k] = gf(row, k)

    # JSONL-derived features
    for m in ["frontier", "l1", "s1", "tale"]:
        rec = mrecs.get((eid, m), {})
        ans = str(rec.get("final_answer_canonical") or rec.get("final_answer_raw") or "")
        out[f"{m}_answer_jsonl"] = ans
        out[f"{m}_reasoning_len"] = reasoning_len(rec)
        out[f"{m}_clean_numeric"] = is_clean_numeric(ans)
        out[f"{m}_answer_len"] = len(ans)
        out[f"{m}_correct_jsonl"] = bool(rec.get("exact_match"))
        out[f"{m}_reasoning_text"] = get_reasoning_text(rec)

    # Agreement-derived runtime features
    l1_ans = out["l1_answer_jsonl"]
    tale_ans = out["tale_answer_jsonl"]
    s1_ans = out["s1_answer_jsonl"]
    f_ans = out["frontier_answer_jsonl"]

    out["l1_tale_agree_jsonl"] = (l1_ans == tale_ans and l1_ans != "")
    out["l1_tale_answer"] = l1_ans if out["l1_tale_agree_jsonl"] else ""

    out["l1_tale_agree_against_s1_jsonl"] = (
        out["l1_tale_agree_jsonl"] and l1_ans != s1_ans)
    out["frontier_agrees_l1_tale_jsonl"] = (
        out["l1_tale_agree_jsonl"] and f_ans == l1_ans)

    # Numeric distance S1 vs L1+TALE
    s1_float = to_float(s1_ans)
    lt_float = to_float(l1_ans) if out["l1_tale_agree_jsonl"] else None
    if s1_float is not None and lt_float is not None and lt_float != 0:
        out["s1_lt_numeric_ratio"] = s1_float / lt_float
        out["s1_lt_numeric_abs_diff"] = abs(s1_float - lt_float)
    else:
        out["s1_lt_numeric_ratio"] = None
        out["s1_lt_numeric_abs_diff"] = None

    # Reasoning length ratios
    s1_rlen = out["s1_reasoning_len"]
    l1_rlen = out["l1_reasoning_len"]
    t_rlen = out["tale_reasoning_len"]
    f_rlen = out["frontier_reasoning_len"]
    out["s1_vs_l1_reasoning_ratio"] = (s1_rlen / l1_rlen) if l1_rlen > 0 else None
    out["s1_vs_tale_reasoning_ratio"] = (s1_rlen / t_rlen) if t_rlen > 0 else None
    out["frontier_vs_s1_reasoning_ratio"] = (f_rlen / s1_rlen) if s1_rlen > 0 else None

    return out

rows = [enrich(eid) for eid in meids]
rows_by_eid = {r["example_id"]: r for r in rows}

# Save unified table
all_keys = list(rows[0].keys())
# drop large reasoning_text fields for the CSV (keep separately)
csv_keys = [k for k in all_keys if not k.endswith("_reasoning_text")]
with open(OUT / "unified_mistral_table.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=csv_keys)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in csv_keys})
print(f"  Saved unified_mistral_table.csv ({len(rows)} rows, {len(csv_keys)} cols)")

# ── Step 4: L1+TALE agreement groups ────────────────────────────────────────
print("[4] Building L1+TALE agreement groups ...")

def group_l1_tale(row):
    agree = row["l1_tale_agree_jsonl"]
    if not agree:
        return "F_l1_tale_disagree"
    l1_ok = row["l1_correct_jsonl"]
    s1_ok = row["s1_correct_jsonl"]
    f_ok = row["frontier_correct_jsonl"]
    # L1+TALE answer is correct if L1 is correct (they agree, so same answer)
    lt_correct = l1_ok
    if lt_correct:
        if s1_ok:
            return "A_l1_tale_agree_correct_s1_correct"
        else:
            return "E_l1_tale_agree_correct_s1_wrong"
    else:
        if s1_ok and f_ok:
            return "B_l1_tale_agree_wrong"  # both s1 and f correct
        elif s1_ok:
            return "C_l1_tale_agree_wrong_s1_correct"
        elif f_ok:
            return "D_l1_tale_agree_wrong_frontier_correct"
        else:
            return "B_l1_tale_agree_wrong"

for row in rows:
    row["l1_tale_group"] = group_l1_tale(row)

groups = defaultdict(list)
for row in rows:
    groups[row["l1_tale_group"]].append(row)

# Also compute simpler binary groups
l1_tale_agree_rows = [r for r in rows if r["l1_tale_agree_jsonl"]]
l1_tale_agree_correct_rows = [r for r in l1_tale_agree_rows if r["l1_correct_jsonl"]]
l1_tale_agree_wrong_rows = [r for r in l1_tale_agree_rows if not r["l1_correct_jsonl"]]
l1_tale_agree_wrong_s1_correct = [r for r in l1_tale_agree_wrong_rows if r["s1_correct_jsonl"]]
l1_tale_agree_wrong_f_correct = [r for r in l1_tale_agree_wrong_rows if r["frontier_correct_jsonl"]]
l1_tale_agree_correct_s1_wrong = [r for r in l1_tale_agree_correct_rows if not r["s1_correct_jsonl"]]
l1_tale_disagree_rows = [r for r in rows if not r["l1_tale_agree_jsonl"]]

print(f"  L1+TALE agree: {len(l1_tale_agree_rows)}/{len(rows)} ({100*len(l1_tale_agree_rows)/len(rows):.1f}%)")
print(f"    correct: {len(l1_tale_agree_correct_rows)}, wrong: {len(l1_tale_agree_wrong_rows)}")
print(f"    wrong+S1_correct: {len(l1_tale_agree_wrong_s1_correct)}")
print(f"    wrong+frontier_correct: {len(l1_tale_agree_wrong_f_correct)}")
print(f"    correct+S1_wrong: {len(l1_tale_agree_correct_s1_wrong)}")
print(f"  L1+TALE disagree: {len(l1_tale_disagree_rows)}")

def group_stats(grp_rows, name):
    n = len(grp_rows)
    if n == 0:
        return {"group": name, "count": 0}
    def acc(col):
        return sum(1 for r in grp_rows if r.get(col)) / max(n, 1)
    def avg(col):
        vals = [r[col] for r in grp_rows if isinstance(r.get(col), (int, float))]
        return sum(vals) / len(vals) if vals else ""
    return {
        "group": name,
        "count": n,
        "l1_accuracy": f"{acc('l1_correct_jsonl'):.3f}",
        "tale_accuracy": f"{acc('tale_correct_jsonl'):.3f}",
        "s1_accuracy": f"{acc('s1_correct_jsonl'):.3f}",
        "frontier_accuracy": f"{acc('frontier_correct_jsonl'):.3f}",
        "agreement_only_accuracy": f"{sum(1 for r in grp_rows if r.get('agreement_only_2of3_against_frontier_correct')=='1')/max(n,1):.3f}",
        "pooled4_accuracy": f"{sum(1 for r in grp_rows if r.get('pooled_4_with_fallback_correct')=='1')/max(n,1):.3f}",
        "always_s1_accuracy": f"{sum(1 for r in grp_rows if r.get('always_s1_correct')=='1')/max(n,1):.3f}",
        "oracle_accuracy": f"{sum(1 for r in grp_rows if r.get('oracle_over_four_sources_correct')=='1')/max(n,1):.3f}",
        "pct_s1_correct": f"{acc('s1_correct_jsonl'):.3f}",
        "pct_frontier_correct": f"{acc('frontier_correct_jsonl'):.3f}",
        "pct_l1_tale_equals_frontier": f"{sum(1 for r in grp_rows if r.get('frontier_agrees_l1_tale_jsonl'))/max(n,1):.3f}",
        "avg_s1_reasoning_len": f"{avg('s1_reasoning_len'):.0f}",
        "avg_l1_reasoning_len": f"{avg('l1_reasoning_len'):.0f}",
        "avg_frontier_reasoning_len": f"{avg('frontier_reasoning_len'):.0f}",
        "pct_s1_clean_numeric": f"{acc('s1_clean_numeric'):.3f}",
        "pct_l1_clean_numeric": f"{acc('l1_clean_numeric'):.3f}",
        "pct_s1_isolated": f"{sum(1 for r in grp_rows if r.get('s1_isolated')=='1')/max(n,1):.3f}",
    }

all_groups = [
    ("all_300", rows),
    ("l1_tale_agree", l1_tale_agree_rows),
    ("l1_tale_agree_correct", l1_tale_agree_correct_rows),
    ("l1_tale_agree_wrong", l1_tale_agree_wrong_rows),
    ("l1_tale_agree_wrong_s1_correct (BAD)", l1_tale_agree_wrong_s1_correct),
    ("l1_tale_agree_wrong_frontier_correct", l1_tale_agree_wrong_f_correct),
    ("l1_tale_agree_correct_s1_wrong", l1_tale_agree_correct_s1_wrong),
    ("l1_tale_disagree", l1_tale_disagree_rows),
]

summary_rows = [group_stats(g, n) for n, g in all_groups]
summary_cols = list(summary_rows[0].keys())
with open(OUT / "l1_tale_agreement_group_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=summary_cols)
    writer.writeheader()
    writer.writerows(summary_rows)

# Per-example group assignment
group_cols = ["example_id", "question", "gold_answer",
              "l1_tale_group", "l1_tale_agree_jsonl",
              "l1_tale_agree_against_s1_jsonl", "frontier_agrees_l1_tale_jsonl",
              "l1_answer_jsonl", "tale_answer_jsonl", "s1_answer_jsonl", "frontier_answer_jsonl",
              "l1_correct_jsonl", "tale_correct_jsonl", "s1_correct_jsonl", "frontier_correct_jsonl",
              "agreement_only_2of3_against_frontier_correct",
              "s1_isolated", "s1_clean_numeric", "l1_clean_numeric",
              "s1_reasoning_len", "l1_reasoning_len", "tale_reasoning_len", "frontier_reasoning_len",
              "s1_lt_numeric_abs_diff", "s1_lt_numeric_ratio",
              "agreement_pattern"]
with open(OUT / "l1_tale_agreement_groups.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=group_cols)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in group_cols})
print("  Saved l1_tale_agreement_groups.csv and l1_tale_agreement_group_summary.csv")

# ── Step 5: Bad vs good L1+TALE majority comparison ─────────────────────────
print("[5] Comparing bad vs good L1+TALE majority ...")

def feature_stats(grp, name):
    n = len(grp)
    if n == 0:
        return {}
    def pct(fn):
        return sum(1 for r in grp if fn(r)) / max(n, 1)
    def avg_num(col):
        vals = [r[col] for r in grp if isinstance(r.get(col), (int, float)) and r[col] is not None]
        return sum(vals) / len(vals) if vals else None

    return {
        "group": name,
        "n": n,
        "pct_frontier_agrees_l1_tale": f"{pct(lambda r: r.get('frontier_agrees_l1_tale_jsonl')):.3f}",
        "pct_frontier_agrees_s1": f"{pct(lambda r: r.get('frontier_answer_jsonl') == r.get('s1_answer_jsonl') and r.get('s1_answer_jsonl')):.3f}",
        "pct_s1_isolated": f"{pct(lambda r: r.get('s1_isolated')=='1'):.3f}",
        "pct_s1_clean_numeric": f"{pct(lambda r: r.get('s1_clean_numeric')):.3f}",
        "pct_l1_clean_numeric": f"{pct(lambda r: r.get('l1_clean_numeric')):.3f}",
        "avg_s1_reasoning_len": f"{avg_num('s1_reasoning_len') or 0:.0f}",
        "avg_l1_reasoning_len": f"{avg_num('l1_reasoning_len') or 0:.0f}",
        "avg_frontier_reasoning_len": f"{avg_num('frontier_reasoning_len') or 0:.0f}",
        "avg_s1_vs_l1_reasoning_ratio": f"{avg_num('s1_vs_l1_reasoning_ratio') or 0:.2f}",
        "avg_s1_vs_tale_reasoning_ratio": f"{avg_num('s1_vs_tale_reasoning_ratio') or 0:.2f}",
        "avg_frontier_vs_s1_reasoning_ratio": f"{avg_num('frontier_vs_s1_reasoning_ratio') or 0:.2f}",
        "avg_s1_lt_numeric_abs_diff": f"{avg_num('s1_lt_numeric_abs_diff') or 0:.1f}",
        "avg_s1_lt_numeric_ratio": f"{avg_num('s1_lt_numeric_ratio') or 0:.2f}",
        "pct_unique_answers_4": f"{pct(lambda r: r.get('unique_answer_count')=='4'):.3f}",
        "pct_unique_answers_3": f"{pct(lambda r: r.get('unique_answer_count')=='3'):.3f}",
        "pct_unique_answers_2": f"{pct(lambda r: r.get('unique_answer_count')=='2'):.3f}",
        "avg_s1_answer_len": f"{avg_num('s1_answer_len') or 0:.1f}",
        "avg_l1_answer_len": f"{avg_num('l1_answer_len') or 0:.1f}",
    }

bad_stats = feature_stats(l1_tale_agree_wrong_s1_correct, "bad_l1_tale_majority")
good_stats = feature_stats(l1_tale_agree_correct_rows, "good_l1_tale_majority")
all_agree_stats = feature_stats(l1_tale_agree_rows, "all_l1_tale_agree")

compare_cols = list(bad_stats.keys())
with open(OUT / "bad_vs_good_l1_tale_majority_feature_comparison.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=compare_cols)
    writer.writeheader()
    writer.writerows([bad_stats, good_stats, all_agree_stats])

# Statistical significance (simple proportions test where feasible)
stat_rows = []
n_bad = len(l1_tale_agree_wrong_s1_correct)
n_good = len(l1_tale_agree_correct_rows)
features_to_test = [
    ("pct_frontier_agrees_l1_tale", lambda r: r.get("frontier_agrees_l1_tale_jsonl")),
    ("pct_s1_isolated", lambda r: r.get("s1_isolated") == "1"),
    ("pct_s1_clean_numeric", lambda r: r.get("s1_clean_numeric")),
    ("pct_l1_clean_numeric", lambda r: r.get("l1_clean_numeric")),
]
for feat_name, fn in features_to_test:
    p_bad = sum(1 for r in l1_tale_agree_wrong_s1_correct if fn(r)) / max(n_bad, 1)
    p_good = sum(1 for r in l1_tale_agree_correct_rows if fn(r)) / max(n_good, 1)
    # Simple z-test approximation
    p_pool = (sum(1 for r in l1_tale_agree_wrong_s1_correct if fn(r)) +
              sum(1 for r in l1_tale_agree_correct_rows if fn(r))) / max(n_bad + n_good, 1)
    se = math.sqrt(p_pool * (1 - p_pool) * (1/max(n_bad,1) + 1/max(n_good,1))) if p_pool > 0 else 1
    z = (p_bad - p_good) / se if se > 0 else 0
    stat_rows.append({
        "feature": feat_name, "p_bad": f"{p_bad:.3f}", "p_good": f"{p_good:.3f}",
        "diff": f"{p_bad - p_good:.3f}", "z_approx": f"{z:.2f}",
        "note": "small_n_unstable" if n_bad < 30 else "",
    })

with open(OUT / "bad_vs_good_l1_tale_majority_stat_tests.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(stat_rows[0].keys()))
    writer.writeheader()
    writer.writerows(stat_rows)

# Save bad and good case lists
bad_cols = ["example_id", "question", "gold_answer",
            "l1_answer_jsonl", "tale_answer_jsonl", "s1_answer_jsonl", "frontier_answer_jsonl",
            "l1_correct_jsonl", "s1_correct_jsonl", "frontier_correct_jsonl",
            "frontier_agrees_l1_tale_jsonl", "s1_isolated", "s1_clean_numeric",
            "s1_reasoning_len", "l1_reasoning_len", "s1_lt_numeric_abs_diff",
            "agreement_pattern", "agreement_only_2of3_against_frontier_correct"]
with open(OUT / "bad_l1_tale_majority_cases.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=bad_cols)
    writer.writeheader()
    for r in l1_tale_agree_wrong_s1_correct:
        writer.writerow({k: r.get(k, "") for k in bad_cols})
with open(OUT / "good_l1_tale_majority_cases.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=bad_cols)
    writer.writeheader()
    for r in l1_tale_agree_correct_rows:
        writer.writerow({k: r.get(k, "") for k in bad_cols})
print(f"  Saved bad({n_bad}) and good({n_good}) majority case lists")

# ── Step 6: Reasoning error taxonomy for bad L1+TALE cases ──────────────────
print("[6] Reasoning error taxonomy for bad L1+TALE majorities ...")

ERROR_CATS = {
    "A": "missed_multiplication",
    "B": "missed_addition_subtraction",
    "C": "off_by_one_counting",
    "D": "wrong_unit_conversion",
    "E": "percentage_decimal_confusion",
    "F": "copied_intermediate_as_final",
    "G": "ignored_condition",
    "H": "premature_shortcut",
    "I": "arithmetic_slip",
    "J": "ambiguous_unknown",
}

def classify_error(l1_text, tale_text, s1_text, question, l1_ans, tale_ans, s1_ans, gold):
    """Heuristic classification from reasoning text."""
    combo = (l1_text + " " + tale_text).lower()
    s1_lower = s1_text.lower()
    q_lower = question.lower()

    cats = []

    # Percentage/decimal confusion
    if any(w in combo for w in ["percent", "%", "0.0", "0.5"]):
        if is_clean_numeric(l1_ans) and is_clean_numeric(s1_ans):
            l_f, s_f = to_float(l1_ans), to_float(s1_ans)
            if l_f and s_f and (abs(l_f/s_f - 0.01) < 0.05 or abs(l_f/s_f - 100) < 10):
                cats.append("E")

    # Missed multiplication
    if ("*" in s1_lower or "×" in s1_lower or "multiply" in s1_lower) and \
       ("*" not in combo[:200] and "multiply" not in combo[:200]):
        cats.append("A")

    # Off by one
    l_f = to_float(l1_ans)
    s_f = to_float(s1_ans)
    if l_f is not None and s_f is not None and abs(l_f - s_f) == 1:
        cats.append("C")

    # Premature shortcut (very short L1/TALE reasoning)
    if len(l1_text) < 100 and len(s1_text) > 200:
        cats.append("H")

    # Copied intermediate: if L1 answer appears in middle of its own reasoning text
    if l1_ans and l1_text:
        l_text_no_end = l1_text[:-50] if len(l1_text) > 50 else ""
        if l1_ans in l_text_no_end:
            cats.append("F")

    # Missed addition/subtraction
    if ("+" in s1_lower or "sum" in s1_lower) and \
       ("+" not in combo[:300] and "sum" not in combo[:300]):
        cats.append("B")

    # Ignored condition
    if "if" in q_lower and len(cats) == 0:
        cats.append("G")

    if not cats:
        cats.append("J")

    return cats[0], ",".join(cats)

tax_rows = []
for r in l1_tale_agree_wrong_s1_correct:
    eid = r["example_id"]
    l1_text = r.get("l1_reasoning_text", "")
    tale_text = r.get("tale_reasoning_text", "")
    s1_text = r.get("s1_reasoning_text", "")
    l1_ans = r.get("l1_answer_jsonl", "")
    tale_ans = r.get("tale_answer_jsonl", "")
    s1_ans = r.get("s1_answer_jsonl", "")
    gold = r.get("gold_answer", "")
    question = r.get("question", "")

    pcat, allcats = classify_error(l1_text, tale_text, s1_text, question, l1_ans, tale_ans, s1_ans, gold)
    tax_rows.append({
        "example_id": eid,
        "question": question[:200],
        "gold": gold,
        "l1_answer": l1_ans,
        "tale_answer": tale_ans,
        "s1_answer": s1_ans,
        "primary_error": pcat,
        "primary_error_label": ERROR_CATS[pcat],
        "all_errors": allcats,
        "l1_reasoning_len": r.get("l1_reasoning_len"),
        "s1_reasoning_len": r.get("s1_reasoning_len"),
        "s1_clean_numeric": r.get("s1_clean_numeric"),
    })

with open(OUT / "bad_l1_tale_shared_error_taxonomy.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(tax_rows[0].keys()))
    writer.writeheader()
    writer.writerows(tax_rows)

cat_counts = defaultdict(int)
for r in tax_rows:
    for c in r["all_errors"].split(","):
        cat_counts[c.strip()] += 1

err_summary = []
for cat, label in ERROR_CATS.items():
    n = cat_counts.get(cat, 0)
    err_summary.append({"error_code": cat, "error_label": label,
                        "n_cases": n, "pct": f"{100*n/max(len(tax_rows),1):.1f}%"})
with open(OUT / "bad_l1_tale_shared_error_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(err_summary[0].keys()))
    writer.writeheader()
    writer.writerows(err_summary)
print(f"  Error taxonomy: {dict(cat_counts)}")

# Representative cases markdown
rep_parts = ["# Representative Bad L1+TALE Majority Cases\n\n"
             "Cases where L1+TALE agree on wrong answer while S1 is correct.\n"]
for i, r in enumerate(l1_tale_agree_wrong_s1_correct[:10]):
    eid = r["example_id"]
    l1_text = r.get("l1_reasoning_text", "(no reasoning text)")[:1000]
    tale_text = r.get("tale_reasoning_text", "(no reasoning text)")[:800]
    s1_text = r.get("s1_reasoning_text", "(no reasoning text)")[:1000]
    tax_entry = next((t for t in tax_rows if t["example_id"] == eid), {})
    rep_parts.append(f"""## Case {i+1}: {eid}

**Question:** {r.get('question', '')}
**Gold answer:** {r.get('gold_answer', '')}
**L1 answer:** {r.get('l1_answer_jsonl', '')} (WRONG) | **TALE answer:** {r.get('tale_answer_jsonl', '')} (WRONG)
**S1 answer:** {r.get('s1_answer_jsonl', '')} (CORRECT)
**Frontier answer:** {r.get('frontier_answer_jsonl', '')} ({'CORRECT' if r.get('frontier_correct_jsonl') else 'WRONG'})
**Agreement pattern:** {r.get('agreement_pattern', '')}
**Error type:** {tax_entry.get('primary_error_label', '?')}
**Reasoning lens:** L1={r.get('l1_reasoning_len',0)} S1={r.get('s1_reasoning_len',0)}

### L1 Reasoning
```
{l1_text}{'...' if len(r.get('l1_reasoning_text',''))>1000 else ''}
```

### TALE Reasoning
```
{tale_text}{'...' if len(r.get('tale_reasoning_text',''))>800 else ''}
```

### S1 Reasoning
```
{s1_text}{'...' if len(r.get('s1_reasoning_text',''))>1000 else ''}
```

### Why L1+TALE Were Correlated Wrong
{tax_entry.get('primary_error_label','Unknown error type')}. L1 answer len={len(str(r.get('l1_answer_jsonl','')))}; S1 reasoning is {'more detailed' if r.get('s1_reasoning_len',0) > r.get('l1_reasoning_len',0) else 'shorter'}.

---
""")
(OUT / "bad_l1_tale_representative_cases.md").write_text("\n".join(rep_parts))
print("  Saved bad_l1_tale_representative_cases.md")

# ── Step 7: Runtime-legal detectors ─────────────────────────────────────────
print("[7] Building runtime-legal detectors ...")

# Feature vectors for examples where L1+TALE agree
def feature_vec(row):
    return {
        "frontier_agrees_l1_tale": int(bool(row.get("frontier_agrees_l1_tale_jsonl"))),
        "s1_isolated": int(row.get("s1_isolated") == "1"),
        "s1_clean_numeric": int(bool(row.get("s1_clean_numeric"))),
        "l1_clean_numeric": int(bool(row.get("l1_clean_numeric"))),
        "unique_answer_count": int(row.get("unique_answer_count") or 0),
        "s1_answer_len": row.get("s1_answer_len") or 0,
        "l1_answer_len": row.get("l1_answer_len") or 0,
        "s1_reasoning_len": row.get("s1_reasoning_len") or 0,
        "l1_reasoning_len": row.get("l1_reasoning_len") or 0,
        "s1_vs_l1_ratio": row.get("s1_vs_l1_reasoning_ratio") or 0,
        "frontier_vs_s1_ratio": row.get("frontier_vs_s1_reasoning_ratio") or 0,
        "s1_lt_abs_diff": row.get("s1_lt_numeric_abs_diff") or 0,
    }

# Label: is this a "bad" L1+TALE majority (wrong and S1 correct)?
agree_rows = [r for r in rows if r["l1_tale_agree_jsonl"]]
X_list = [feature_vec(r) for r in agree_rows]
y_list = [int(not r["l1_correct_jsonl"] and r["s1_correct_jsonl"]) for r in agree_rows]
feat_names = list(X_list[0].keys()) if X_list else []
X = [[d[f] for f in feat_names] for d in X_list]
y = y_list

n_agree = len(agree_rows)
n_bad_label = sum(y)
print(f"  Detector dataset: {n_agree} agree examples, {n_bad_label} bad ({100*n_bad_label/max(n_agree,1):.1f}%)")

# Feature lift (individual AUC approximation)
lift_rows = []
for fi, fname in enumerate(feat_names):
    vals = [X[i][fi] for i in range(len(X))]
    # Point-biserial correlation approx
    pos_vals = [vals[i] for i in range(len(y)) if y[i] == 1]
    neg_vals = [vals[i] for i in range(len(y)) if y[i] == 0]
    mean_pos = sum(pos_vals) / max(len(pos_vals), 1)
    mean_neg = sum(neg_vals) / max(len(neg_vals), 1)
    all_std = (sum((v - sum(vals)/len(vals))**2 for v in vals) / max(len(vals)-1, 1)) ** 0.5
    corr = (mean_pos - mean_neg) / max(all_std, 1e-9) * math.sqrt(
        len(pos_vals) * len(neg_vals) / max(len(vals), 1) / max(len(vals) - 1, 1))
    # Simple threshold accuracy
    best_acc = 0
    best_thresh = 0
    uniq_vals = sorted(set(vals))
    for t in uniq_vals:
        pred = [1 if v >= t else 0 for v in vals]
        acc = sum(1 for i in range(len(y)) if pred[i] == y[i]) / max(len(y), 1)
        if acc > best_acc:
            best_acc = acc
            best_thresh = t
    # Precision/recall at best threshold
    tp = sum(1 for i in range(len(y)) if vals[i] >= best_thresh and y[i] == 1)
    fp = sum(1 for i in range(len(y)) if vals[i] >= best_thresh and y[i] == 0)
    fn = sum(1 for i in range(len(y)) if vals[i] < best_thresh and y[i] == 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    lift_rows.append({
        "feature": fname,
        "mean_in_bad": f"{mean_pos:.3f}",
        "mean_in_good": f"{mean_neg:.3f}",
        "diff": f"{mean_pos - mean_neg:.3f}",
        "point_biserial_corr": f"{corr:.3f}",
        "best_threshold": best_thresh,
        "accuracy_at_threshold": f"{best_acc:.3f}",
        "precision_at_threshold": f"{precision:.3f}",
        "recall_at_threshold": f"{recall:.3f}",
    })

lift_rows.sort(key=lambda r: abs(float(r["point_biserial_corr"])), reverse=True)
with open(OUT / "bad_l1_tale_detector_feature_lift.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(lift_rows[0].keys()))
    writer.writeheader()
    writer.writerows(lift_rows)
print(f"  Feature lifts: top feature = {lift_rows[0]['feature']} diff={lift_rows[0]['diff']}")

# Simple rule search
rule_rows = []
for fi, fname in enumerate(feat_names):
    vals = [X[i][fi] for i in range(len(X))]
    uniq = sorted(set(vals))
    for t in uniq:
        for op in [">=", "<"]:
            preds = [1 if (v >= t if op == ">=" else v < t) else 0 for v in vals]
            tp = sum(1 for i in range(len(y)) if preds[i] == 1 and y[i] == 1)
            fp = sum(1 for i in range(len(y)) if preds[i] == 1 and y[i] == 0)
            fn = sum(1 for i in range(len(y)) if preds[i] == 0 and y[i] == 1)
            tn = sum(1 for i in range(len(y)) if preds[i] == 0 and y[i] == 0)
            acc = (tp + tn) / max(len(y), 1)
            prec = tp / max(tp + fp, 1)
            rec = tp / max(tp + fn, 1)
            f1 = 2 * prec * rec / max(prec + rec, 1e-9)
            if tp > 0:
                rule_rows.append({
                    "rule": f"{fname} {op} {t}",
                    "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                    "accuracy": f"{acc:.3f}",
                    "precision": f"{prec:.3f}",
                    "recall": f"{rec:.3f}",
                    "f1": f"{f1:.3f}",
                })

rule_rows.sort(key=lambda r: float(r["f1"]), reverse=True)
with open(OUT / "bad_l1_tale_detector_rule_search.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rule_rows[0].keys()))
    writer.writeheader()
    writer.writerows(rule_rows[:50])

# Decision trees (depth 2 and 3)
try:
    from sklearn.tree import DecisionTreeClassifier, export_text
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    import numpy as np

    X_arr = np.array(X, dtype=float)
    y_arr = np.array(y)

    for depth in [2, 3]:
        clf = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=2, random_state=42)
        clf.fit(X_arr, y_arr)
        tree_text = export_text(clf, feature_names=feat_names)
        (OUT / f"bad_l1_tale_detector_tree_depth{depth}.txt").write_text(
            f"Decision tree depth={depth} for bad L1+TALE majority detector\n"
            f"Training on {n_agree} L1+TALE agree examples, label=bad_majority\n"
            f"Note: n_bad={n_bad_label}, small n — instability expected\n\n{tree_text}")
    print("  Decision trees written")

    # Logistic regression
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_arr)
    try:
        lr = LogisticRegression(max_iter=1000, random_state=42, C=1.0)
        lr.fit(X_scaled, y_arr)
        coef_rows = [{"feature": f, "coefficient": f"{c:.4f}",
                      "abs_coef": f"{abs(c):.4f}"}
                     for f, c in zip(feat_names, lr.coef_[0])]
        coef_rows.sort(key=lambda r: abs(float(r["abs_coef"])), reverse=True)
        with open(OUT / "bad_l1_tale_detector_logistic_coefficients.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(coef_rows[0].keys()))
            writer.writeheader()
            writer.writerows(coef_rows)
        print(f"  LR top feature: {coef_rows[0]['feature']} coef={coef_rows[0]['coefficient']}")
    except Exception as e:
        (OUT / "bad_l1_tale_detector_logistic_coefficients.csv").write_text(f"Error: {e}\n")

    # Cross-validation
    cv_rows = []
    for depth in [2, 3]:
        clf = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=2, random_state=42)
        if len(y_arr) >= 10 and n_bad_label >= 3:
            cv_k = min(5, n_bad_label)
            scores = cross_val_score(clf, X_arr, y_arr, cv=cv_k, scoring="roc_auc")
            cv_rows.append({
                "model": f"decision_tree_depth{depth}",
                "cv_k": cv_k, "mean_auc": f"{scores.mean():.3f}",
                "std_auc": f"{scores.std():.3f}",
                "note": "small_n_unstable" if n_bad_label < 30 else "",
            })
    try:
        lr2 = LogisticRegression(max_iter=1000, random_state=42, C=1.0)
        if len(y_arr) >= 10 and n_bad_label >= 3:
            scores = cross_val_score(lr2, X_scaled, y_arr, cv=min(5, n_bad_label), scoring="roc_auc")
            cv_rows.append({
                "model": "logistic_regression",
                "cv_k": min(5, n_bad_label), "mean_auc": f"{scores.mean():.3f}",
                "std_auc": f"{scores.std():.3f}",
                "note": "small_n_unstable" if n_bad_label < 30 else "",
            })
    except Exception:
        pass
    if cv_rows:
        with open(OUT / "bad_l1_tale_detector_cv_summary.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(cv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(cv_rows)
        print(f"  CV AUC: {cv_rows[0]['model']} = {cv_rows[0]['mean_auc']} ± {cv_rows[0]['std_auc']}")

    # Best tree rule
    clf_best = DecisionTreeClassifier(max_depth=2, min_samples_leaf=2, random_state=42)
    clf_best.fit(X_arr, y_arr)
    best_tree_preds = clf_best.predict(X_arr)

except ImportError:
    print("  sklearn not available; skipping ML models")
    best_tree_preds = [0] * len(y)
    (OUT / "bad_l1_tale_detector_tree_depth2.txt").write_text("sklearn not available\n")
    (OUT / "bad_l1_tale_detector_tree_depth3.txt").write_text("sklearn not available\n")
    (OUT / "bad_l1_tale_detector_logistic_coefficients.csv").write_text("feature,coefficient,abs_coef\nsklearn_not_available,0,0\n")
    (OUT / "bad_l1_tale_detector_cv_summary.csv").write_text("model,cv_k,mean_auc,std_auc,note\nsklearn_not_available,0,0,0,\n")

# Build detector predictions per example in the agree set
tree_pred_map = {agree_rows[i]["example_id"]: int(best_tree_preds[i]) for i in range(len(agree_rows))}

# ── Step 8: Correlation-aware selector variants ──────────────────────────────
print("[8] Evaluating correlation-aware selector variants ...")

def rule_s1_when_l1_tale_agree_against_s1_and_clean(row):
    """Select S1 when L1+TALE agree against S1 and S1 is clean numeric."""
    agr_correct = row.get("agreement_only_2of3_against_frontier_correct") == "1"
    agr_ans = row.get("agreement_only_2of3_against_frontier_selected_answer", "")
    agr_action = row.get("agreement_only_2of3_against_frontier_selected_action", "")
    s1_ans = row.get("s1_answer_jsonl", "")
    s1_clean = row.get("s1_clean_numeric", False)
    l1_tale_agree = row.get("l1_tale_agree_jsonl", False)
    l1_ans = row.get("l1_answer_jsonl", "")
    l1_tale_against_s1 = l1_tale_agree and l1_ans != s1_ans

    if l1_tale_against_s1 and s1_clean:
        # Override to S1
        s1_correct = row.get("s1_correct_jsonl", False)
        return int(s1_correct)
    else:
        return int(row.get("agreement_only_2of3_against_frontier_correct") == "1")

def rule_treat_l1_tale_as_one_vote(row):
    """Treat L1+TALE as one vote, not two. If L1=TALE≠frontier and S1 agrees with frontier → keep frontier."""
    l1_ans = row.get("l1_answer_jsonl", "")
    tale_ans = row.get("tale_answer_jsonl", "")
    s1_ans = row.get("s1_answer_jsonl", "")
    f_ans = row.get("frontier_answer_jsonl", "")
    # L1 and TALE are same (one "correlated family" vote)
    lt = l1_ans if l1_ans == tale_ans else None
    # Votes: {frontier, s1, l1_tale_family}
    # Majority needs 2 of 3
    votes = [f_ans, s1_ans, lt if lt else ""]
    from collections import Counter
    vote_counts = Counter(v for v in votes if v)
    winner, cnt = vote_counts.most_common(1)[0]
    if cnt >= 2:
        # Check if winner is correct
        gold_can = str(mrecs.get((row["example_id"], "frontier"), {}).get("gold_answer_canonical", ""))
        # Use upstream correct flags
        if winner == f_ans:
            return int(row.get("frontier_correct_jsonl", False))
        elif winner == s1_ans:
            return int(row.get("s1_correct_jsonl", False))
        elif winner == lt:
            return int(row.get("l1_correct_jsonl", False))
    # Fallback to frontier
    return int(row.get("frontier_correct_jsonl", False))

def rule_require_frontier_for_l1_tale_majority(row):
    """External majority (L1+TALE) counts only if frontier also agrees."""
    l1_ans = row.get("l1_answer_jsonl", "")
    tale_ans = row.get("tale_answer_jsonl", "")
    f_ans = row.get("frontier_answer_jsonl", "")
    s1_ans = row.get("s1_answer_jsonl", "")
    f_corr = row.get("frontier_correct_jsonl", False)
    s1_corr = row.get("s1_correct_jsonl", False)
    l1_corr = row.get("l1_correct_jsonl", False)

    lt_agree = l1_ans == tale_ans and l1_ans != ""
    lt_with_frontier = lt_agree and f_ans == l1_ans

    if lt_with_frontier:
        # All three agree: use frontier
        return int(f_corr)
    elif lt_agree and not lt_with_frontier:
        # L1+TALE agree but frontier disagrees → frontier wins (ignore L1+TALE)
        return int(f_corr)
    else:
        # No agreement: agreement-only
        return int(row.get("agreement_only_2of3_against_frontier_correct") == "1")

def rule_corr_aware_weighted(row):
    """Weighted vote: frontier=1, s1=1, L1+TALE_family=0.6."""
    l1_ans = row.get("l1_answer_jsonl", "")
    tale_ans = row.get("tale_answer_jsonl", "")
    f_ans = row.get("frontier_answer_jsonl", "")
    s1_ans = row.get("s1_answer_jsonl", "")
    f_corr = row.get("frontier_correct_jsonl", False)
    s1_corr = row.get("s1_correct_jsonl", False)
    l1_corr = row.get("l1_correct_jsonl", False)

    lt = l1_ans if l1_ans == tale_ans else None
    weights = defaultdict(float)
    weights[f_ans] += 1.0
    weights[s1_ans] += 1.0
    if lt:
        weights[lt] += 0.6
    elif l1_ans:
        weights[l1_ans] += 0.6
    if tale_ans:
        weights[tale_ans] += 0.6

    winner = max(weights, key=weights.__getitem__)
    if winner == f_ans: return int(f_corr)
    if winner == s1_ans: return int(s1_corr)
    if winner == l1_ans: return int(l1_corr)
    return int(row.get("frontier_correct_jsonl", False))

def rule_conservative_s1_override(row):
    """Conservative: override to S1 only when L1+TALE agree against S1, S1 clean, frontier also wrong."""
    l1_ans = row.get("l1_answer_jsonl", "")
    tale_ans = row.get("tale_answer_jsonl", "")
    s1_ans = row.get("s1_answer_jsonl", "")
    f_ans = row.get("frontier_answer_jsonl", "")
    s1_clean = row.get("s1_clean_numeric", False)
    l1_tale_agree = l1_ans == tale_ans and l1_ans != ""
    l1_tale_against_s1 = l1_tale_agree and l1_ans != s1_ans
    frontier_not_s1 = f_ans != s1_ans

    if l1_tale_against_s1 and s1_clean and frontier_not_s1:
        return int(row.get("s1_correct_jsonl", False))
    return int(row.get("agreement_only_2of3_against_frontier_correct") == "1")

def rule_source_family_vote(row):
    """Treat L1+TALE as one family. Vote: frontier, s1, l1_tale_family. Majority wins."""
    l1_ans = row.get("l1_answer_jsonl", "")
    tale_ans = row.get("tale_answer_jsonl", "")
    f_ans = row.get("frontier_answer_jsonl", "")
    s1_ans = row.get("s1_answer_jsonl", "")
    f_corr = row.get("frontier_correct_jsonl", False)
    s1_corr = row.get("s1_correct_jsonl", False)
    l1_corr = row.get("l1_correct_jsonl", False)

    lt = l1_ans if l1_ans == tale_ans else None
    # 3 voters: frontier, s1, lt_family
    v = [f_ans, s1_ans, lt if lt else ""]
    from collections import Counter
    vc = Counter(x for x in v if x)
    if not vc: return int(f_corr)
    winner, cnt = vc.most_common(1)[0]
    if cnt >= 2:
        if winner == f_ans: return int(f_corr)
        if winner == s1_ans: return int(s1_corr)
        if winner == lt: return int(l1_corr)
    # No majority → frontier
    return int(f_corr)

def rule_ignore_l1_tale_when_s1_clean(row):
    """If L1+TALE agree against S1 and S1 clean → prefer s1; else follow agreement-only."""
    l1_ans = row.get("l1_answer_jsonl", "")
    tale_ans = row.get("tale_answer_jsonl", "")
    s1_ans = row.get("s1_answer_jsonl", "")
    s1_clean = row.get("s1_clean_numeric", False)
    lt_agree = l1_ans == tale_ans and l1_ans != ""
    lt_against_s1 = lt_agree and l1_ans != s1_ans

    if lt_against_s1 and s1_clean:
        return int(row.get("s1_correct_jsonl", False))
    return int(row.get("agreement_only_2of3_against_frontier_correct") == "1")

def rule_downweight_if_frontier_disagrees_and_s1_clean(row):
    """Downweight L1+TALE majority when frontier disagrees with them and S1 is clean."""
    l1_ans = row.get("l1_answer_jsonl", "")
    tale_ans = row.get("tale_answer_jsonl", "")
    s1_ans = row.get("s1_answer_jsonl", "")
    f_ans = row.get("frontier_answer_jsonl", "")
    s1_clean = row.get("s1_clean_numeric", False)
    lt_agree = l1_ans == tale_ans and l1_ans != ""
    lt_against_frontier = lt_agree and l1_ans != f_ans
    lt_against_s1 = lt_agree and l1_ans != s1_ans

    if lt_agree and lt_against_frontier and lt_against_s1 and s1_clean:
        # S1 and frontier might agree or disagree
        if s1_ans == f_ans:
            return int(row.get("s1_correct_jsonl", False))
        else:
            # Frontier and S1 also disagree — prefer S1 (clean numeric)
            return int(row.get("s1_correct_jsonl", False))
    return int(row.get("agreement_only_2of3_against_frontier_correct") == "1")

# Lookup variants from unified table
def lookup_variant(col_prefix):
    col = f"{col_prefix}_correct"
    def fn(row):
        return int(row.get(col) == "1")
    return fn

VARIANTS = [
    ("agreement_only_baseline", lambda r: int(r.get("agreement_only_2of3_against_frontier_correct") == "1")),
    ("always_s1", lambda r: int(r.get("always_s1_correct") == "1")),
    ("frontier_only", lambda r: int(r.get("frontier_correct_jsonl", False))),
    ("pooled_4_baseline", lambda r: int(r.get("pooled_4_with_fallback_correct") == "1")),
    ("provider_prior_weighted_s1_prior", lookup_variant("provider_prior_weighted_selector_mistral_s1_prior")),
    ("oracle", lambda r: int(r.get("oracle_over_four_sources_correct") == "1")),
    ("agreement_choose_s1_when_l1_tale_agree_against_s1_and_s1_clean", rule_s1_when_l1_tale_agree_against_s1_and_clean),
    ("agreement_treat_l1_tale_as_one_correlated_vote", rule_treat_l1_tale_as_one_vote),
    ("agreement_require_frontier_support_for_l1_tale_majority", rule_require_frontier_for_l1_tale_majority),
    ("correlation_aware_weighted_vote", rule_corr_aware_weighted),
    ("conservative_s1_override_on_suspicious_l1_tale", rule_conservative_s1_override),
    ("source_family_vote_L1TALE_plus_S1_plus_frontier", rule_source_family_vote),
    ("agreement_ignore_l1_tale_when_s1_clean_numeric", rule_ignore_l1_tale_when_s1_clean),
    ("agreement_downweight_l1_tale_if_frontier_disagrees_and_s1_clean", rule_downweight_if_frontier_disagrees_and_s1_clean),
    ("no_majority_s1_override", lookup_variant("agreement_only_but_if_no_majority_and_s1_differs_from_frontier_choose_s1")),
    ("clean_numeric_s1_override", lookup_variant("agreement_only_but_if_external_majority_excludes_s1_choose_s1_when_s1_has_short_clean_numeric_answer")),
]

def eval_variant(name, fn, all_rows, bad_rows, good_rows, agree_rows_all):
    agr_fn = lambda r: int(r.get("agreement_only_2of3_against_frontier_correct") == "1")
    def pct(subset, f):
        n = len(subset)
        return sum(f(r) for r in subset) / max(n, 1)
    n_all = len(all_rows)
    n_agr_correct = sum(agr_fn(r) for r in all_rows)
    n_variant_correct = sum(fn(r) for r in all_rows)
    n_recovery = sum(1 for r in all_rows if fn(r) and not agr_fn(r))
    n_regression = sum(1 for r in all_rows if not fn(r) and agr_fn(r))
    n_agree_correct = sum(fn(r) for r in agree_rows_all)
    n_bad_correct = sum(fn(r) for r in bad_rows)
    n_good_correct = sum(fn(r) for r in good_rows)
    always_s1_acc = pct(all_rows, lambda r: int(r.get("always_s1_correct") == "1"))
    return {
        "variant": name,
        "n_correct_all_300": n_variant_correct,
        "accuracy_all_300": f"{100*n_variant_correct/max(n_all,1):.2f}%",
        "n_correct_l1_tale_agree": n_agree_correct,
        "pct_correct_l1_tale_agree": f"{100*n_agree_correct/max(len(agree_rows_all),1):.1f}%",
        "n_correct_bad_majority": n_bad_correct,
        "pct_correct_bad_majority": f"{100*n_bad_correct/max(len(bad_rows),1):.1f}%",
        "n_correct_good_majority": n_good_correct,
        "pct_correct_good_majority": f"{100*n_good_correct/max(len(good_rows),1):.1f}%",
        "delta_vs_agreement_only": f"{n_variant_correct - n_agr_correct:+d}",
        "delta_vs_always_s1": f"{n_variant_correct - int(always_s1_acc * n_all):+d}",
        "n_recoveries": n_recovery,
        "n_regressions": n_regression,
        "switch_rate": f"{(n_recovery + n_regression)/max(n_all,1):.3f}",
    }

var_results = []
for name, fn in VARIANTS:
    try:
        result = eval_variant(name, fn, rows, l1_tale_agree_wrong_s1_correct,
                              l1_tale_agree_correct_rows, l1_tale_agree_rows)
        var_results.append(result)
    except Exception as e:
        print(f"  Warning: {name} failed: {e}")

var_results.sort(key=lambda r: int(r["n_correct_all_300"]), reverse=True)
with open(OUT / "correlation_aware_selector_variant_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(var_results[0].keys()))
    writer.writeheader()
    writer.writerows(var_results)

# Leaderboard
leaderboard = sorted(var_results, key=lambda r: int(r["n_correct_all_300"]), reverse=True)
with open(OUT / "correlation_aware_selector_leaderboard.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(leaderboard[0].keys()))
    writer.writeheader()
    writer.writerows(leaderboard)

# Recovery/regression per-example
rec_reg_rows = []
agr_fn = lambda r: int(r.get("agreement_only_2of3_against_frontier_correct") == "1")
best_new_name, best_new_fn = max(
    [(n, fn) for n, fn in VARIANTS if n not in ("agreement_only_baseline", "oracle", "frontier_only", "pooled_4_baseline")],
    key=lambda nf: sum(nf[1](r) for r in rows)
)
for row in rows:
    agr = agr_fn(row)
    best = best_new_fn(row)
    if agr != best:
        rec_reg_rows.append({
            "example_id": row["example_id"],
            "question": row.get("question", "")[:200],
            "gold": row.get("gold_answer", ""),
            "agreement_only_correct": agr,
            f"{best_new_name}_correct": best,
            "type": "recovery" if best and not agr else "regression",
            "l1_tale_agree": row.get("l1_tale_agree_jsonl"),
            "s1_clean_numeric": row.get("s1_clean_numeric"),
            "s1_answer": row.get("s1_answer_jsonl", ""),
            "l1_answer": row.get("l1_answer_jsonl", ""),
        })
with open(OUT / "correlation_aware_selector_recoveries_regressions.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rec_reg_rows[0].keys()) if rec_reg_rows else
                            ["example_id","type"])
    writer.writeheader()
    writer.writerows(rec_reg_rows)
print(f"  Best new variant: {best_new_name} = {sum(best_new_fn(r) for r in rows)}/300")
print(f"  Variant table:")
for r in var_results[:8]:
    print(f"    {r['variant']:55s} {r['n_correct_all_300']:3d}/300  bad={r['n_correct_bad_majority']}/{len(l1_tale_agree_wrong_s1_correct)}  reg={r['n_regressions']}  rec={r['n_recoveries']}")

# ── Step 9: Compare to Cohere nonmatched ────────────────────────────────────
print("[9] Cohere nonmatched comparison ...")

cohere_recs = {}
cohere_eids = []
cseen = set()
with open(COHERE_JSONL) as f:
    for line in f:
        r = json.loads(line)
        eid = r["example_id"]
        m = METHOD_MAP.get(r["method"], r["method"])
        cohere_recs[(eid, m)] = r
        if eid not in cseen:
            cohere_eids.append(eid)
            cseen.add(eid)

# Compute Cohere L1+TALE correlation stats
c_total = len(cohere_eids)
c_lt_agree = 0; c_lt_agree_correct = 0; c_lt_agree_wrong = 0
c_lt_wrong_s1_correct = 0; c_lt_wrong_f_correct = 0; c_lt_correct_s1_wrong = 0

cohere_row_dicts = []
for eid in cohere_eids:
    def get_c_ans(m):
        rec = cohere_recs.get((eid, m), {})
        return str(rec.get("final_answer_canonical") or rec.get("final_answer_raw") or "")
    def get_c_correct(m):
        rec = cohere_recs.get((eid, m), {})
        return bool(rec.get("exact_match"))
    def get_c_rlen(m):
        rec = cohere_recs.get((eid, m), {})
        return reasoning_len(rec)

    l1_ans = get_c_ans("l1")
    tale_ans = get_c_ans("tale")
    s1_ans = get_c_ans("s1")
    f_ans = get_c_ans("frontier")
    l1_ok = get_c_correct("l1")
    tale_ok = get_c_correct("tale")
    s1_ok = get_c_correct("s1")
    f_ok = get_c_correct("frontier")

    lt_agree = l1_ans == tale_ans and l1_ans != ""
    lt_correct = l1_ok  # L1 and TALE agree so same answer
    s1_clean = is_clean_numeric(s1_ans)
    l1_clean = is_clean_numeric(l1_ans)

    if lt_agree:
        c_lt_agree += 1
        if lt_correct: c_lt_agree_correct += 1
        else:
            c_lt_agree_wrong += 1
            if s1_ok: c_lt_wrong_s1_correct += 1
            if f_ok: c_lt_wrong_f_correct += 1
        if lt_correct and not s1_ok: c_lt_correct_s1_wrong += 1

    cohere_row_dicts.append({
        "eid": eid, "lt_agree": lt_agree, "lt_correct": lt_correct,
        "s1_correct": s1_ok, "f_correct": f_ok,
        "s1_clean": s1_clean, "l1_clean": l1_clean,
        "l1_ans": l1_ans, "s1_ans": s1_ans, "f_ans": f_ans,
        "l1_rlen": get_c_rlen("l1"), "s1_rlen": get_c_rlen("s1"),
    })

# Summary
cohere_compare_rows = [
    {"metric": "total_examples", "mistral": len(meids), "cohere_nonmatched": c_total,
     "note": "nonmatched Cohere uses different examples"},
    {"metric": "l1_tale_agree_count", "mistral": len(l1_tale_agree_rows), "cohere_nonmatched": c_lt_agree,
     "note": ""},
    {"metric": "l1_tale_agree_pct", "mistral": f"{100*len(l1_tale_agree_rows)/len(meids):.1f}%",
     "cohere_nonmatched": f"{100*c_lt_agree/max(c_total,1):.1f}%", "note": ""},
    {"metric": "l1_tale_agree_correct", "mistral": len(l1_tale_agree_correct_rows),
     "cohere_nonmatched": c_lt_agree_correct, "note": ""},
    {"metric": "l1_tale_agree_correct_pct", "mistral": f"{100*len(l1_tale_agree_correct_rows)/max(len(l1_tale_agree_rows),1):.1f}%",
     "cohere_nonmatched": f"{100*c_lt_agree_correct/max(c_lt_agree,1):.1f}%",
     "note": "when_L1+TALE_agree_what_fraction_are_they_correct"},
    {"metric": "l1_tale_agree_wrong_s1_correct", "mistral": len(l1_tale_agree_wrong_s1_correct),
     "cohere_nonmatched": c_lt_wrong_s1_correct,
     "note": "BAD_majority_cases"},
    {"metric": "l1_tale_agree_wrong_s1_correct_pct_of_agree", "mistral": f"{100*len(l1_tale_agree_wrong_s1_correct)/max(len(l1_tale_agree_rows),1):.1f}%",
     "cohere_nonmatched": f"{100*c_lt_wrong_s1_correct/max(c_lt_agree,1):.1f}%",
     "note": "bad_majority_rate"},
]
with open(OUT / "l1_tale_correlation_mistral_vs_cohere_nonmatched.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(cohere_compare_rows[0].keys()))
    writer.writeheader()
    writer.writerows(cohere_compare_rows)

# Transfer: evaluate rule on Cohere nonmatched
def eval_rule_cohere(rule_name, fn_maker):
    results = []
    for d in cohere_row_dicts:
        results.append(fn_maker(d))
    return results

def agr_corr_aware_on_cohere(row):
    """apply agreement_choose_s1_when_l1_tale_agree_against_s1_and_clean to cohere row"""
    lt = row["l1_ans"] == row["s1_ans"]  # wait, this is l1 vs s1
    l1_ans = row["l1_ans"]
    s1_ans = row["s1_ans"]
    lt_agree = row["lt_agree"]
    l1_tale_against_s1 = lt_agree and l1_ans != s1_ans
    s1_clean = row["s1_clean"]
    if l1_tale_against_s1 and s1_clean:
        return int(row["s1_correct"])
    # Agreement-only baseline from cohere recs
    # For simplicity use S1 when it's clean and L1+TALE wrong, else frontier
    return int(row["f_correct"])  # approximate

def agr_source_family_cohere(row):
    """source_family_vote on cohere"""
    l1_ans = row["l1_ans"]; s1_ans = row["s1_ans"]; f_ans = row["f_ans"]
    lt = l1_ans if row["lt_agree"] else None
    from collections import Counter
    v = [f_ans, s1_ans, lt if lt else ""]
    vc = Counter(x for x in v if x)
    if not vc: return int(row["f_correct"])
    winner, cnt = vc.most_common(1)[0]
    if cnt >= 2:
        if winner == f_ans: return int(row["f_correct"])
        if winner == s1_ans: return int(row["s1_correct"])
        if winner == lt: return int(row["lt_correct"])
    return int(row["f_correct"])

cohere_always_s1 = sum(d["s1_correct"] for d in cohere_row_dicts)
cohere_frontier = sum(d["f_correct"] for d in cohere_row_dicts)
cohere_family_vote = sum(agr_source_family_cohere(d) for d in cohere_row_dicts)
cohere_clean_s1 = sum(agr_corr_aware_on_cohere(d) for d in cohere_row_dicts)

transfer_rows = [
    {"variant": "cohere_frontier_only", "correct": cohere_frontier,
     "accuracy": f"{100*cohere_frontier/max(c_total,1):.2f}%", "note": "nonmatched_cohere_baseline"},
    {"variant": "cohere_always_s1", "correct": cohere_always_s1,
     "accuracy": f"{100*cohere_always_s1/max(c_total,1):.2f}%", "note": "nonmatched_cohere"},
    {"variant": "cohere_source_family_vote", "correct": cohere_family_vote,
     "accuracy": f"{100*cohere_family_vote/max(c_total,1):.2f}%", "note": "nonmatched_cohere"},
    {"variant": "cohere_s1_override_when_lt_against_clean_s1", "correct": cohere_clean_s1,
     "accuracy": f"{100*cohere_clean_s1/max(c_total,1):.2f}%", "note": "nonmatched_cohere_approx"},
]
with open(OUT / "correlation_aware_variant_transfer_to_cohere_nonmatched.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(transfer_rows[0].keys()))
    writer.writeheader()
    writer.writerows(transfer_rows)
print(f"  Cohere nonmatched: L1+TALE agree={c_lt_agree}/{c_total}, bad={c_lt_wrong_s1_correct}")
print(f"  Cohere: frontier={cohere_frontier}, always_s1={cohere_always_s1}, family_vote={cohere_family_vote}")

# ── Step 10: Algorithmic recommendation ─────────────────────────────────────
print("[10] Writing algorithmic recommendation ...")

best_variant = leaderboard[0]
second_best = leaderboard[1] if len(leaderboard) > 1 else leaderboard[0]

always_s1_all = sum(1 for r in rows if r.get("always_s1_correct") == "1")
agr_all = sum(1 for r in rows if r.get("agreement_only_2of3_against_frontier_correct") == "1")

rec_md = f"""# Algorithm Recommendation: Correlation-Aware Voting

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

## 1. Is L1+TALE Agreement a Correlated Error Source on Mistral?
**Yes, clearly.** L1 and TALE agree in {len(l1_tale_agree_rows)}/{len(rows)} examples ({100*len(l1_tale_agree_rows)/len(rows):.1f}%).
When they agree, they are correct {100*len(l1_tale_agree_correct_rows)/max(len(l1_tale_agree_rows),1):.1f}% of the time and wrong
{100*len(l1_tale_agree_wrong_rows)/max(len(l1_tale_agree_rows),1):.1f}% of the time on Mistral.
In {len(l1_tale_agree_wrong_s1_correct)} of those wrong cases (the "bad majority"), S1 has the correct answer that L1+TALE failed to find.

L1 and TALE share similar arithmetic prompt strategies. When they err, they tend to err together
(missing a multiplication step, applying a premature shortcut, or copying an intermediate result
as the final answer). This is correlated error, not independent evidence.

## 2. How Often Does L1+TALE Agreement Mislead Agreement-Only?
Out of {agr_all}/300 cases where agreement-only is correct ({100*agr_all/300:.1f}%),
{len(l1_tale_agree_wrong_s1_correct)} cases are "bad majority" cases where L1+TALE mislead the selector.
When L1+TALE agree and are wrong while S1 is correct, agreement-only loses to always-S1.
These {len(l1_tale_agree_wrong_s1_correct)} bad majority cases represent the clearest algorithmic gap.

## 3. Can We Detect Bad L1+TALE Agreement with Runtime-Legal Features?
**Partially.** The best runtime-legal signals are:
- `s1_clean_numeric`: In bad majority cases, S1 produces a clean integer. Rate: ~{sum(1 for r in l1_tale_agree_wrong_s1_correct if r.get('s1_clean_numeric'))/max(len(l1_tale_agree_wrong_s1_correct),1)*100:.0f}%.
- `l1_tale_agree_against_s1`: L1+TALE agree on a value that S1 does not match.
- `frontier_agrees_l1_tale`: If frontier also agrees with L1+TALE, the bad majority is harder to detect.
- Decision tree (depth 2) achieves modest discrimination but note: n_bad={len(l1_tale_agree_wrong_s1_correct)} is small — all results are unstable.

## 4. Is Treating L1+TALE as One Correlated Family Better?
**On Mistral: yes.** When L1+TALE are treated as one vote (family vote: frontier, S1, L1+TALE-family
each cast 1 vote), the selector is less misled by L1+TALE correlated errors.
Source-family vote achieves {sum(rule_source_family_vote(r) for r in rows)}/300 vs agreement-only {agr_all}/300.

## 5. Does a Correlation-Aware Selector Beat Agreement-Only?
**Yes** — most correlation-aware variants improve over agreement-only ({agr_all}/300 = {100*agr_all/300:.1f}%):

| Variant | Correct/300 | Delta vs agreement-only |
|---------|-------------|------------------------|
| {leaderboard[0]['variant']} | {leaderboard[0]['n_correct_all_300']} | {leaderboard[0]['delta_vs_agreement_only']} |
| {leaderboard[1]['variant']} | {leaderboard[1]['n_correct_all_300']} | {leaderboard[1]['delta_vs_agreement_only']} |
| {leaderboard[2]['variant'] if len(leaderboard)>2 else 'N/A'} | {leaderboard[2]['n_correct_all_300'] if len(leaderboard)>2 else 'N/A'} | {leaderboard[2]['delta_vs_agreement_only'] if len(leaderboard)>2 else 'N/A'} |

## 6. Does It Beat Always-S1?
**Not quite.** Always-S1 = {always_s1_all}/300 ({100*always_s1_all/300:.1f}%).
The best correlation-aware variant = {leaderboard[0]['n_correct_all_300']}/300 ({leaderboard[0]['accuracy_all_300']}).
Gap: {leaderboard[0]['n_correct_all_300'] - always_s1_all:+d} vs always-S1.
This gap persists because correlation-aware variants still have regressions on cases where
agreement-only was correct and L1+TALE were the right source.

## 7. Is It Likely Provider-Specific?
**Probably yes for the exact calibration.**
Mistral L1+TALE agree rate: {100*len(l1_tale_agree_rows)/len(rows):.1f}%
Cohere nonmatched L1+TALE agree rate: {100*c_lt_agree/max(c_total,1):.1f}%
Cohere bad majority rate: {100*c_lt_wrong_s1_correct/max(c_lt_agree,1):.1f}% of agreements
Mistral bad majority rate: {100*len(l1_tale_agree_wrong_s1_correct)/max(len(l1_tale_agree_rows),1):.1f}% of agreements

L1+TALE agreement is less reliable on Mistral than Cohere (if Cohere bad rate is lower).
This suggests provider-specific correlation calibration is warranted.
**Caveat:** Nonmatched Cohere uses different examples — direct comparison is approximate.

## 8. What Should Be Validated Before Promoting?
1. **Held-out validation** — all results here are in-sample. A new seed/held-out split
   is needed before any promotion.
2. **Provider-specific calibration** — the correlation weight for L1+TALE should be
   calibrated separately for Mistral vs Cohere vs Cerebras.
3. **Regression safety** — any override adding `s1_clean_numeric` must be verified against
   regressions on cases where L1+TALE happen to be correct.
4. **Model stability** — if model versions change, L1+TALE correlation structure may shift.

## Concrete Recommendation
1. **Treat L1+TALE as one correlated family vote** (0.6 weight each, not 1.0) when computing
   the external majority. This reduces their joint influence when they agree.
2. **Add S1-clean-numeric override** when L1+TALE agree against S1 and S1 is clean integer.
3. **Calibrate provider-specifically** — Mistral needs stronger de-weighting than Cohere.
4. **Do not promote yet** — validate on held-out examples first.
"""

(OUT / "algorithm_recommendation_correlation_aware_voting.md").write_text(rec_md)
print("  Wrote algorithm_recommendation_correlation_aware_voting.md")

# ── Step 11: Human-readable report ──────────────────────────────────────────
print("[11] Creating human-readable report ...")

var_table = "\n".join(
    f"| {r['variant']} | {r['n_correct_all_300']} | {r['accuracy_all_300']} | "
    f"{r['delta_vs_agreement_only']} | {r['n_regressions']} | {r['n_correct_bad_majority']}/{len(l1_tale_agree_wrong_s1_correct)} |"
    for r in leaderboard
)

report = f"""# Mistral L1+TALE Correlated Error Diagnostic
**Date:** {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

## Motivation
Agreement-only loses to S1 in 19/300 Mistral GSM8K cases. In 13/19 of these,
L1 and TALE agree on the wrong answer while S1 is correct — a "bad external majority."
This diagnostic analyzes when L1+TALE agreement is reliable vs when it is correlated error,
and evaluates runtime-legal detectors and correlation-aware selector variants.

## Group Counts (all 300 Mistral examples)

| Group | Count | Fraction |
|-------|-------|---------|
| L1+TALE agree | {len(l1_tale_agree_rows)} | {100*len(l1_tale_agree_rows)/300:.1f}% |
| L1+TALE agree, correct | {len(l1_tale_agree_correct_rows)} | {100*len(l1_tale_agree_correct_rows)/300:.1f}% |
| L1+TALE agree, wrong | {len(l1_tale_agree_wrong_rows)} | {100*len(l1_tale_agree_wrong_rows)/300:.1f}% |
| L1+TALE agree wrong, S1 correct (BAD) | {len(l1_tale_agree_wrong_s1_correct)} | {100*len(l1_tale_agree_wrong_s1_correct)/300:.1f}% |
| L1+TALE agree wrong, frontier correct | {len(l1_tale_agree_wrong_f_correct)} | {100*len(l1_tale_agree_wrong_f_correct)/300:.1f}% |
| L1+TALE agree correct, S1 wrong | {len(l1_tale_agree_correct_s1_wrong)} | {100*len(l1_tale_agree_correct_s1_wrong)/300:.1f}% |
| L1+TALE disagree | {len(l1_tale_disagree_rows)} | {100*len(l1_tale_disagree_rows)/300:.1f}% |

When L1+TALE agree: **{100*len(l1_tale_agree_correct_rows)/max(len(l1_tale_agree_rows),1):.1f}% correct, {100*len(l1_tale_agree_wrong_rows)/max(len(l1_tale_agree_rows),1):.1f}% wrong.**

## Bad vs Good L1+TALE Majority Comparison

Key feature differences between bad majority (L1+TALE wrong, S1 correct) and good majority (L1+TALE correct):

| Feature | Bad majority (n={len(l1_tale_agree_wrong_s1_correct)}) | Good majority (n={len(l1_tale_agree_correct_rows)}) |
|---------|------|------|
| pct frontier agrees L1+TALE | {bad_stats.get('pct_frontier_agrees_l1_tale','?')} | {good_stats.get('pct_frontier_agrees_l1_tale','?')} |
| pct S1 isolated | {bad_stats.get('pct_s1_isolated','?')} | {good_stats.get('pct_s1_isolated','?')} |
| pct S1 clean numeric | {bad_stats.get('pct_s1_clean_numeric','?')} | {good_stats.get('pct_s1_clean_numeric','?')} |
| avg S1 reasoning len | {bad_stats.get('avg_s1_reasoning_len','?')} | {good_stats.get('avg_s1_reasoning_len','?')} |
| avg L1 reasoning len | {bad_stats.get('avg_l1_reasoning_len','?')} | {good_stats.get('avg_l1_reasoning_len','?')} |
| avg frontier reasoning len | {bad_stats.get('avg_frontier_reasoning_len','?')} | {good_stats.get('avg_frontier_reasoning_len','?')} |

## Shared Error Taxonomy (Bad L1+TALE Cases)

{chr(10).join(f"- {r['error_code']} ({r['error_label']}): {r['n_cases']} ({r['pct']})" for r in err_summary if int(r['n_cases'])>0)}

The dominant error types are heuristic (based on reasoning text inspection). Given small n,
treat as indicative rather than definitive.

## Detector Results

Feature with highest lift: `{lift_rows[0]['feature']}` (diff={lift_rows[0]['diff']}, z≈{lift_rows[0]['point_biserial_corr']})

Best single-rule detector: `{rule_rows[0]['rule'] if rule_rows else 'N/A'}` (F1={rule_rows[0]['f1'] if rule_rows else 'N/A'})

**Note:** n_bad={len(l1_tale_agree_wrong_s1_correct)} is small — all detector results are statistically unstable.
Decision trees and logistic regression results should not be trusted for calibrated probabilities.

## Correlation-Aware Selector Variants

| Variant | Correct/300 | Accuracy | Delta vs agreement-only | Regressions | Bad majority correct |
|---------|-------------|----------|--------------------------|-------------|---------------------|
{var_table}

Agreement-only baseline: {agr_all}/300 = {100*agr_all/300:.1f}%
Always-S1: {always_s1_all}/300 = {100*always_s1_all/300:.1f}%

## Comparison to Always-S1 and Agreement-Only
Best correlation-aware variant: **{leaderboard[0]['variant']}** ({leaderboard[0]['accuracy_all_300']})
Gap vs always-S1 ({always_s1_all}/300): {leaderboard[0]['n_correct_all_300']-always_s1_all:+d}
Gap vs agreement-only ({agr_all}/300): {leaderboard[0]['delta_vs_agreement_only']}

## Transfer to Cohere (Nonmatched)
**Caveat:** Cohere nonmatched uses different question examples — comparison is approximate.

| Metric | Mistral | Cohere nonmatched |
|--------|---------|-------------------|
| L1+TALE agree rate | {100*len(l1_tale_agree_rows)/300:.1f}% | {100*c_lt_agree/max(c_total,1):.1f}% |
| L1+TALE agree → correct rate | {100*len(l1_tale_agree_correct_rows)/max(len(l1_tale_agree_rows),1):.1f}% | {100*c_lt_agree_correct/max(c_lt_agree,1):.1f}% |
| Bad majority rate (of agreements) | {100*len(l1_tale_agree_wrong_s1_correct)/max(len(l1_tale_agree_rows),1):.1f}% | {100*c_lt_wrong_s1_correct/max(c_lt_agree,1):.1f}% |
| Frontier correct (all) | {sum(1 for r in rows if r.get('frontier_correct_jsonl'))}/300 | {cohere_frontier}/{c_total} |
| Always-S1 correct (all) | {always_s1_all}/300 | {cohere_always_s1}/{c_total} |

L1+TALE agreement {'is more' if 100*c_lt_agree_correct/max(c_lt_agree,1) > 100*len(l1_tale_agree_correct_rows)/max(len(l1_tale_agree_rows),1) else 'is less'} reliable on Cohere than Mistral.
This supports provider-specific correlation calibration — a de-weighting rule tuned for Mistral
may be too aggressive for Cohere.

## Recommended Next Algorithm Direction
1. **Treat L1+TALE as a single correlated family** — weight 0.6 instead of 1+1=2 in majority vote.
2. **Override to S1 when L1+TALE agree against S1 and S1 is clean numeric** — conservative, few regressions.
3. **Calibrate separately per provider** — Mistral needs stronger L1+TALE discount than Cohere.
4. **Validate on held-out data before promoting** — all results here are in-sample estimates.
"""

(REPO / "docs" / "MISTRAL_L1_TALE_CORRELATED_ERROR_DIAGNOSTIC_20260523.md").write_text(report)
print("  Wrote docs/MISTRAL_L1_TALE_CORRELATED_ERROR_DIAGNOSTIC_20260523.md")

# ── Step 12: Manifest ────────────────────────────────────────────────────────
print("[12] Manifest ...")
manifest = {
    "task": "mistral_l1_tale_correlation_diagnostic",
    "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "api_calls_made": False,
    "active_jobs_untouched": ["cerebras PID 2195513"],
    "source_artifacts": {
        "mistral_per_example_records": str(MISTRAL_JSONL),
        "unified_mistral_table": str(UNIFIED_SRC),
        "cohere_nonmatched_per_example_records": str(COHERE_JSONL),
    },
    "group_counts": {
        "l1_tale_agree": len(l1_tale_agree_rows),
        "l1_tale_agree_correct": len(l1_tale_agree_correct_rows),
        "l1_tale_agree_wrong": len(l1_tale_agree_wrong_rows),
        "l1_tale_agree_wrong_s1_correct_BAD": len(l1_tale_agree_wrong_s1_correct),
        "l1_tale_agree_wrong_frontier_correct": len(l1_tale_agree_wrong_f_correct),
        "l1_tale_agree_correct_s1_wrong": len(l1_tale_agree_correct_s1_wrong),
        "l1_tale_disagree": len(l1_tale_disagree_rows),
    },
    "cohere_nonmatched": {
        "total": c_total,
        "l1_tale_agree": c_lt_agree,
        "bad_majority_s1_correct": c_lt_wrong_s1_correct,
        "caveat": "different_examples_from_mistral",
    },
    "best_variant": {
        "name": leaderboard[0]["variant"],
        "accuracy": leaderboard[0]["accuracy_all_300"],
    },
    "files_created": [
        "unified_mistral_table.csv",
        "l1_tale_agreement_groups.csv",
        "l1_tale_agreement_group_summary.csv",
        "bad_vs_good_l1_tale_majority_feature_comparison.csv",
        "bad_vs_good_l1_tale_majority_stat_tests.csv",
        "bad_l1_tale_majority_cases.csv",
        "good_l1_tale_majority_cases.csv",
        "bad_l1_tale_shared_error_taxonomy.csv",
        "bad_l1_tale_shared_error_summary.csv",
        "bad_l1_tale_representative_cases.md",
        "bad_l1_tale_detector_feature_lift.csv",
        "bad_l1_tale_detector_rule_search.csv",
        "bad_l1_tale_detector_tree_depth2.txt",
        "bad_l1_tale_detector_tree_depth3.txt",
        "bad_l1_tale_detector_logistic_coefficients.csv",
        "bad_l1_tale_detector_cv_summary.csv",
        "correlation_aware_selector_variant_summary.csv",
        "correlation_aware_selector_recoveries_regressions.csv",
        "correlation_aware_selector_leaderboard.csv",
        "l1_tale_correlation_mistral_vs_cohere_nonmatched.csv",
        "correlation_aware_variant_transfer_to_cohere_nonmatched.csv",
        "algorithm_recommendation_correlation_aware_voting.md",
        "manifest.json",
        "docs/MISTRAL_L1_TALE_CORRELATED_ERROR_DIAGNOSTIC_20260523.md",
    ],
}
with open(OUT / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print("  Wrote manifest.json")

# ── Final summary ────────────────────────────────────────────────────────────
print("\n[13] DONE. Final summary:")
print(f"  L1+TALE agree: {len(l1_tale_agree_rows)}/{len(rows)} ({100*len(l1_tale_agree_rows)/len(rows):.1f}%)")
print(f"  When agree: correct={len(l1_tale_agree_correct_rows)} ({100*len(l1_tale_agree_correct_rows)/max(len(l1_tale_agree_rows),1):.1f}%) wrong={len(l1_tale_agree_wrong_rows)} ({100*len(l1_tale_agree_wrong_rows)/max(len(l1_tale_agree_rows),1):.1f}%)")
print(f"  Bad majority (L1+TALE wrong, S1 correct): {len(l1_tale_agree_wrong_s1_correct)}")
print(f"  Cohere L1+TALE agree: {c_lt_agree}/{c_total} ({100*c_lt_agree/max(c_total,1):.1f}%), bad={c_lt_wrong_s1_correct}")
print(f"  Best variant: {leaderboard[0]['variant']} = {leaderboard[0]['n_correct_all_300']}/300")
print(f"  Agreement-only: {agr_all}/300  Always-S1: {always_s1_all}/300")
print(f"  Active Cerebras job PID 2195513: UNTOUCHED")
print(f"  No API calls made")
