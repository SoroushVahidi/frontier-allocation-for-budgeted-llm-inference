"""
Cohere canonical Final-300 integrity, replay, comparison, and diagnostic analysis.
Steps 3–8 of 219f49289752316cdfd55e103f92173d1797c12e.txt
No API calls. No policy modification. No touching active jobs.
"""

import json
import csv
import re
import os
import sys
import math
import random
import collections
from pathlib import Path
from datetime import datetime, timezone

random.seed(42)
OUTDIR = Path("outputs/cohere_canonical_final300_frozen_agreement_live_result_20260523")
OUTDIR.mkdir(parents=True, exist_ok=True)

NEW_PER_EXAMPLE = Path("outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/cohere_real_model_cost_normalized_validation_20260523T181948Z/per_example_records.jsonl")
OLD_PER_EXAMPLE = Path("outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/runner_output/cohere_real_model_cost_normalized_validation_final_fix24_live_20260519/per_example_records.jsonl")
EXACT_CASES = Path("outputs/canonical_final300_cohere_contract_matched_validation_prep_20260523/canonical_final300_exact_cases.jsonl")
ALLOWED_IDS = Path("outputs/canonical_final300_cohere_contract_matched_validation_prep_20260523/canonical_final300_allowed_ids.jsonl")
COMPLETION_SUMMARY = Path("outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/cohere_real_model_cost_normalized_validation_20260523T181948Z/completion_summary.json")
FAILURE_TAX = Path("outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/cohere_real_model_cost_normalized_validation_20260523T181948Z/failure_taxonomy_summary.json")

METHODS = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]
METHOD_LABELS = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "L1",
    "external_s1_budget_forcing": "S1",
    "external_tale_prompt_budgeting": "TALE",
}
CLEAN_NUM_RE = re.compile(r"^\-?\d+(\.\d+)?$")


def is_clean_numeric(s):
    if s is None:
        return False
    return bool(CLEAN_NUM_RE.match(str(s).strip()))


def load_jsonl(path):
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
    print(f"  wrote {path}")


def write_csv(path, rows, fieldnames=None):
    if not rows:
        with open(path, "w") as f:
            f.write("")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path}")


def write_md(path, text):
    with open(path, "w") as f:
        f.write(text)
    print(f"  wrote {path}")


# ───────────────────────────────────────────────────────────────────
# LOAD DATA
# ───────────────────────────────────────────────────────────────────
print("Loading new canonical per_example_records...")
new_records = load_jsonl(NEW_PER_EXAMPLE)
print(f"  {len(new_records)} records")

print("Loading exact_cases and allowed_ids...")
exact_cases = load_jsonl(EXACT_CASES)
allowed_ids_list = load_jsonl(ALLOWED_IDS)
exact_ids_ordered = [e["example_id"] for e in exact_cases]
exact_ids_set = set(exact_ids_ordered)
exact_gold = {e["example_id"]: e["gold_answer"] for e in exact_cases}
exact_question = {e["example_id"]: e["question"] for e in exact_cases}

print("Loading completion summary...")
with open(COMPLETION_SUMMARY) as f:
    completion_summary = json.load(f)
with open(FAILURE_TAX) as f:
    failure_tax = json.load(f)

print("Loading old canonical per_example_records...")
old_records = load_jsonl(OLD_PER_EXAMPLE) if OLD_PER_EXAMPLE.exists() else []
print(f"  {len(old_records)} old records")

# Build per-example × method lookup for new run
new_lookup = {}  # example_id → {method: record}
for r in new_records:
    eid = r["example_id"]
    meth = r["method"]
    if eid not in new_lookup:
        new_lookup[eid] = {}
    new_lookup[eid][meth] = r

# Build per-example × method lookup for old run
old_lookup = {}
for r in old_records:
    eid = r["example_id"]
    meth = r["method"]
    if eid not in old_lookup:
        old_lookup[eid] = {}
    old_lookup[eid][meth] = r


def get_ans(rec):
    """Normalized canonical answer from record."""
    if rec is None:
        return None
    return rec.get("final_answer_canonical") or rec.get("selected_answer_canonical")


def get_correct(rec):
    """Boolean: is this record correct?"""
    if rec is None:
        return False
    em = rec.get("exact_match")
    if em is not None:
        return bool(em)
    ans = get_ans(rec)
    gold = rec.get("gold_answer_canonical") or rec.get("gold_answer")
    if ans is not None and gold is not None:
        return str(ans).strip() == str(gold).strip()
    return False


def get_gold(rec):
    if rec is None:
        return None
    return rec.get("gold_answer_canonical") or rec.get("gold_answer")


# ───────────────────────────────────────────────────────────────────
# STEP 3 — INTEGRITY CHECK
# ───────────────────────────────────────────────────────────────────
print("\n=== STEP 3: Integrity Check ===")
total_records = len(new_records)
unique_example_ids = sorted(set(r["example_id"] for r in new_records))
unique_methods = sorted(set(r["method"] for r in new_records))
scored_rows = sum(1 for r in new_records if r.get("status") == "scored" or r.get("exact_match") is not None)
failed_rows = sum(1 for r in new_records if r.get("status") == "failed")
skipped_rows = sum(1 for r in new_records if r.get("status") == "skipped")

# per-method counts
per_method_counts = {}
for meth in METHODS:
    subset = [r for r in new_records if r["method"] == meth]
    per_method_counts[meth] = {
        "method": meth,
        "label": METHOD_LABELS[meth],
        "total": len(subset),
        "scored": sum(1 for r in subset if r.get("status") == "scored" or r.get("exact_match") is not None),
        "failed": sum(1 for r in subset if r.get("status") == "failed"),
        "unique_ids": len(set(r["example_id"] for r in subset)),
    }

# per-example completeness
per_example_completeness = []
for eid in unique_example_ids:
    methods_present = set(new_lookup[eid].keys())
    complete = len(methods_present) == 4
    per_example_completeness.append({
        "example_id": eid,
        "methods_present": len(methods_present),
        "complete": int(complete),
        "missing_methods": ",".join(m for m in METHODS if m not in methods_present),
    })

integrity_summary = {
    "total_records": total_records,
    "unique_example_ids": len(unique_example_ids),
    "unique_methods": unique_methods,
    "expected_records": 1200,
    "scored_rows": scored_rows,
    "failed_rows": failed_rows,
    "skipped_rows": skipped_rows,
    "duplicate_rows": total_records - len(unique_example_ids) * 4,
    "all_four_methods_present": all(per_method_counts[m]["total"] == 300 for m in METHODS),
    "fully_complete_examples": sum(1 for r in per_example_completeness if r["complete"]),
    "integrity_pass": (total_records == 1200 and scored_rows == 1200 and failed_rows == 0),
    "completion_summary_from_runner": completion_summary,
    "failure_taxonomy": failure_tax,
}

write_json(OUTDIR / "integrity_summary.json", integrity_summary)
write_csv(
    OUTDIR / "per_method_completion_counts.csv",
    list(per_method_counts.values()),
    fieldnames=["method", "label", "total", "scored", "failed", "unique_ids"],
)
write_csv(OUTDIR / "per_example_completeness.csv", per_example_completeness)
write_json(OUTDIR / "failure_taxonomy_summary.json", failure_tax)

print(f"  integrity_pass: {integrity_summary['integrity_pass']}")
print(f"  total={total_records}, scored={scored_rows}, failed={failed_rows}")

# ───────────────────────────────────────────────────────────────────
# STEP 4 — CANONICAL CONTRACT VERIFICATION
# ───────────────────────────────────────────────────────────────────
print("\n=== STEP 4: Canonical Contract Verification ===")
run_ids_set = set(unique_example_ids)
run_ids_ordered = sorted(unique_example_ids)

overlap = run_ids_set & exact_ids_set
extra_in_run = run_ids_set - exact_ids_set
missing_from_run = exact_ids_set - run_ids_set

canonical_overlap_summary = {
    "canonical_exact_count": len(exact_ids_set),
    "run_unique_count": len(run_ids_set),
    "overlap_count": len(overlap),
    "extra_in_run": sorted(extra_in_run),
    "missing_from_run": sorted(missing_from_run),
    "exact_match_ids": len(extra_in_run) == 0 and len(missing_from_run) == 0,
    "all_ids_train_prefix": all(eid.startswith("openai_gsm8k_train_") for eid in unique_example_ids),
    "not_test_set": all(not eid.startswith("openai_gsm8k_") or eid.startswith("openai_gsm8k_train_") for eid in unique_example_ids),
    "allowed_ids_count": len(allowed_ids_list),
}

# Order check: compare exact_ids_ordered (from prep) vs sorted run IDs
# The prep file gives one ordering; check how many match sorted order
order_check_rows = []
for idx, eid in enumerate(exact_ids_ordered):
    in_run = eid in run_ids_set
    order_check_rows.append({
        "rank_in_canonical": idx,
        "example_id": eid,
        "in_run": int(in_run),
        "question_match": int(exact_question.get(eid, "") == (new_lookup.get(eid, {}).get("direct_reserve_semantic_frontier_v2", {}) or {}).get("question", "")) if in_run else 0,
    })

write_json(OUTDIR / "canonical_overlap_summary.json", canonical_overlap_summary)
write_csv(OUTDIR / "canonical_id_order_check.csv", order_check_rows)
print(f"  overlap={len(overlap)}/300, extra={len(extra_in_run)}, missing={len(missing_from_run)}")
print(f"  exact_id_match: {canonical_overlap_summary['exact_match_ids']}")

# ───────────────────────────────────────────────────────────────────
# STEP 5 — FULL-COVERAGE REPLAY
# ───────────────────────────────────────────────────────────────────
print("\n=== STEP 5: Full-Coverage Replay ===")

# Build per-example data table
examples = []
for eid in unique_example_ids:
    row = new_lookup[eid]
    f_rec = row.get("direct_reserve_semantic_frontier_v2")
    l1_rec = row.get("external_l1_max")
    s1_rec = row.get("external_s1_budget_forcing")
    tale_rec = row.get("external_tale_prompt_budgeting")

    f_ans = get_ans(f_rec)
    l1_ans = get_ans(l1_rec)
    s1_ans = get_ans(s1_rec)
    tale_ans = get_ans(tale_rec)
    gold = get_gold(f_rec) or exact_gold.get(eid)

    f_ok = get_correct(f_rec)
    l1_ok = get_correct(l1_rec)
    s1_ok = get_correct(s1_rec)
    tale_ok = get_correct(tale_rec)

    # Agreement among external (L1, S1, TALE)
    ext_answers = []
    if l1_ans is not None:
        ext_answers.append(l1_ans)
    if s1_ans is not None:
        ext_answers.append(s1_ans)
    if tale_ans is not None:
        ext_answers.append(tale_ans)

    ext_counts = collections.Counter(ext_answers)
    ext_majority_ans = None
    ext_majority_count = 0
    if ext_counts:
        ext_majority_ans, ext_majority_count = ext_counts.most_common(1)[0]

    # agreement_only_2of3_against_frontier
    # external majority (≥2 of L1/S1/TALE agree) ≠ frontier → use external majority
    # else keep frontier
    agr_ans = f_ans
    agr_action = "kept_frontier"
    if ext_majority_count >= 2 and ext_majority_ans != f_ans:
        agr_ans = ext_majority_ans
        agr_action = "external_majority"
    elif ext_majority_count >= 2 and ext_majority_ans == f_ans:
        agr_action = "frontier_majority_match"

    agr_ok = (str(agr_ans).strip() == str(gold).strip()) if (agr_ans is not None and gold is not None) else False

    # pooled-4 with fallback: strict majority among all 4
    all_answers = [a for a in [f_ans, l1_ans, s1_ans, tale_ans] if a is not None]
    all_counts = collections.Counter(all_answers)
    pool_majority_ans, pool_majority_count = all_counts.most_common(1)[0] if all_counts else (f_ans, 0)
    pool_ans = f_ans
    pool_action = "kept_frontier"
    if pool_majority_count >= 2 and pool_majority_ans != f_ans:
        pool_ans = pool_majority_ans
        pool_action = "pooled_majority"
    elif pool_majority_count >= 2 and pool_majority_ans == f_ans:
        pool_action = "frontier_pooled_match"

    pool_ok = (str(pool_ans).strip() == str(gold).strip()) if (pool_ans is not None and gold is not None) else False

    # L1+TALE agreement
    lt_agree = (l1_ans is not None and tale_ans is not None and l1_ans == tale_ans)
    lt_ans = l1_ans if lt_agree else None
    lt_ok = (str(lt_ans).strip() == str(gold).strip()) if (lt_agree and lt_ans is not None and gold is not None) else False
    lt_agree_wrong = lt_agree and not lt_ok
    lt_agree_wrong_s1_correct = lt_agree_wrong and s1_ok

    # Feature signals
    s1_clean = is_clean_numeric(s1_ans)
    l1_clean = is_clean_numeric(l1_ans)
    tale_clean = is_clean_numeric(tale_ans)
    f_clean = is_clean_numeric(f_ans)
    frontier_agrees_lt = (lt_agree and f_ans == lt_ans)
    s1_isolated = (s1_ans != l1_ans and s1_ans != tale_ans and s1_ans != f_ans) if all(a is not None for a in [s1_ans, l1_ans, tale_ans, f_ans]) else None

    unique_ans_count = len(set(a for a in [f_ans, l1_ans, s1_ans, tale_ans] if a is not None))

    examples.append({
        "example_id": eid,
        "gold": gold,
        "question": exact_question.get(eid, ""),
        "f_ans": f_ans, "l1_ans": l1_ans, "s1_ans": s1_ans, "tale_ans": tale_ans,
        "f_ok": int(f_ok), "l1_ok": int(l1_ok), "s1_ok": int(s1_ok), "tale_ok": int(tale_ok),
        "agr_ans": agr_ans, "agr_action": agr_action, "agr_ok": int(agr_ok),
        "pool_ans": pool_ans, "pool_action": pool_action, "pool_ok": int(pool_ok),
        "ext_majority_ans": ext_majority_ans, "ext_majority_count": ext_majority_count,
        "lt_agree": int(lt_agree), "lt_ans": lt_ans, "lt_ok": int(lt_ok),
        "lt_agree_wrong": int(lt_agree_wrong),
        "lt_agree_wrong_s1_correct": int(lt_agree_wrong_s1_correct),
        "s1_clean": int(s1_clean), "l1_clean": int(l1_clean), "tale_clean": int(tale_clean), "f_clean": int(f_clean),
        "frontier_agrees_lt": int(frontier_agrees_lt),
        "s1_isolated": int(s1_isolated) if s1_isolated is not None else 0,
        "unique_ans_count": unique_ans_count,
    })

N = len(examples)
print(f"  Built example table: {N} rows")


def acc(col):
    return sum(e[col] for e in examples) / N


def bootstrap_ci(col_a, col_b, n_boot=2000, alpha=0.05):
    """Paired bootstrap 95% CI for accuracy(col_a) - accuracy(col_b)."""
    diffs = [e[col_a] - e[col_b] for e in examples]
    obs_diff = sum(diffs) / N
    boot_diffs = []
    for _ in range(n_boot):
        sample = random.choices(diffs, k=N)
        boot_diffs.append(sum(sample) / N)
    boot_diffs.sort()
    lo = boot_diffs[int(alpha / 2 * n_boot)]
    hi = boot_diffs[int((1 - alpha / 2) * n_boot)]
    return obs_diff, lo, hi


def mcnemar(col_a, col_b):
    """McNemar test: b=a wins, c=b wins."""
    b = sum(1 for e in examples if e[col_a] and not e[col_b])
    c = sum(1 for e in examples if not e[col_a] and e[col_b])
    if b + c == 0:
        return b, c, None, None
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)
    # p approx from chi2(1)
    import math
    p = math.exp(-chi2 / 2) if chi2 < 50 else 0.0
    return b, c, chi2, p


def win_loss_tie(col_a, col_b):
    wins = sum(1 for e in examples if e[col_a] and not e[col_b])
    losses = sum(1 for e in examples if not e[col_a] and e[col_b])
    ties = sum(1 for e in examples if e[col_a] == e[col_b])
    return wins, losses, ties


# Method accuracies
cols = {
    "frontier": "f_ok",
    "L1": "l1_ok",
    "S1": "s1_ok",
    "TALE": "tale_ok",
    "agreement_only": "agr_ok",
    "pooled_4": "pool_ok",
}

method_acc_rows = []
for label, col in cols.items():
    correct = sum(e[col] for e in examples)
    method_acc_rows.append({
        "method": label,
        "correct": correct,
        "total": N,
        "accuracy": round(correct / N, 6),
    })

# Oracle
oracle_correct = sum(1 for e in examples if any(e[c] for c in ["f_ok", "l1_ok", "s1_ok", "tale_ok"]))
method_acc_rows.append({"method": "oracle", "correct": oracle_correct, "total": N, "accuracy": round(oracle_correct / N, 6)})

write_csv(OUTDIR / "method_accuracy_summary.csv", method_acc_rows)

# Frozen replay summary
replay_rows = []
for label, col in cols.items():
    d_frontier = acc(col) - acc("f_ok")
    d_s1 = acc(col) - acc("s1_ok")
    d_l1 = acc(col) - acc("l1_ok")
    d_pool = acc(col) - acc("pool_ok")
    wins_vs_f, losses_vs_f, ties_vs_f = win_loss_tie(col, "f_ok")
    wins_vs_s1, losses_vs_s1, _ = win_loss_tie(col, "s1_ok")
    wins_vs_l1, losses_vs_l1, _ = win_loss_tie(col, "l1_ok")
    wins_vs_pool, losses_vs_pool, _ = win_loss_tie(col, "pool_ok")
    obs_f, lo_f, hi_f = bootstrap_ci(col, "f_ok")
    obs_s1, lo_s1, hi_s1 = bootstrap_ci(col, "s1_ok")
    obs_l1, lo_l1, hi_l1 = bootstrap_ci(col, "l1_ok")
    obs_pool, lo_pool, hi_pool = bootstrap_ci(col, "pool_ok")
    replay_rows.append({
        "method": label,
        "correct": sum(e[col] for e in examples),
        "accuracy": round(acc(col), 6),
        "delta_vs_frontier": round(d_frontier, 6),
        "delta_vs_s1": round(d_s1, 6),
        "delta_vs_l1": round(d_l1, 6),
        "delta_vs_pool4": round(d_pool, 6),
        "wins_vs_frontier": wins_vs_f,
        "losses_vs_frontier": losses_vs_f,
        "wins_vs_s1": wins_vs_s1,
        "losses_vs_s1": losses_vs_s1,
        "wins_vs_l1": wins_vs_l1,
        "losses_vs_l1": losses_vs_l1,
        "wins_vs_pool4": wins_vs_pool,
        "losses_vs_pool4": losses_vs_pool,
        "bootstrap_diff_vs_frontier": round(obs_f, 6),
        "bootstrap_ci95_lo_vs_frontier": round(lo_f, 6),
        "bootstrap_ci95_hi_vs_frontier": round(hi_f, 6),
        "bootstrap_diff_vs_s1": round(obs_s1, 6),
        "bootstrap_ci95_lo_vs_s1": round(lo_s1, 6),
        "bootstrap_ci95_hi_vs_s1": round(hi_s1, 6),
        "bootstrap_diff_vs_l1": round(obs_l1, 6),
        "bootstrap_ci95_lo_vs_l1": round(lo_l1, 6),
        "bootstrap_ci95_hi_vs_l1": round(hi_l1, 6),
        "bootstrap_diff_vs_pool4": round(obs_pool, 6),
        "bootstrap_ci95_lo_vs_pool4": round(lo_pool, 6),
        "bootstrap_ci95_hi_vs_pool4": round(hi_pool, 6),
    })

write_csv(OUTDIR / "frozen_replay_summary.csv", replay_rows)

# Win/loss/tie summary
wlt_rows = []
pairs = [("agreement_only", "f_ok"), ("agreement_only", "s1_ok"), ("agreement_only", "l1_ok"), ("agreement_only", "pool_ok"),
         ("pooled_4", "f_ok"), ("pooled_4", "s1_ok"), ("S1", "f_ok"), ("L1", "f_ok"), ("TALE", "f_ok")]
for a_label, b_col in pairs:
    a_col = cols[a_label]
    b_label = b_col.replace("_ok", "")
    wins, losses, ties = win_loss_tie(a_col, b_col)
    wlt_rows.append({"A": a_label, "B": b_label, "A_wins": wins, "A_losses": losses, "ties": ties})
write_csv(OUTDIR / "win_loss_tie_summary.csv", wlt_rows)

# Paired CI summary
ci_rows = []
for a_label, a_col in cols.items():
    for b_label, b_col in cols.items():
        if a_label == b_label:
            continue
        obs, lo, hi = bootstrap_ci(a_col, b_col)
        ci_rows.append({
            "A": a_label, "B": b_label,
            "obs_diff": round(obs, 6),
            "ci95_lo": round(lo, 6),
            "ci95_hi": round(hi, 6),
            "significant": int(lo > 0 or hi < 0),
        })
write_csv(OUTDIR / "paired_ci_summary.csv", ci_rows)

# McNemar summary
mcn_rows = []
for a_label, a_col in cols.items():
    for b_label, b_col in cols.items():
        if a_label >= b_label:
            continue
        b, c, chi2, p = mcnemar(a_col, b_col)
        mcn_rows.append({
            "A": a_label, "B": b_label,
            "A_wins": b, "B_wins": c,
            "chi2": round(chi2, 4) if chi2 is not None else "",
            "p_approx": round(p, 6) if p is not None else "",
        })
write_csv(OUTDIR / "mcnemar_summary.csv", mcn_rows)

print("  Replay results:")
for row in method_acc_rows:
    print(f"    {row['method']:25s}  {row['correct']}/{row['total']}  acc={row['accuracy']:.4f}")

# ───────────────────────────────────────────────────────────────────
# STEP 6 — OLD VS NEW CANONICAL COMPARISON
# ───────────────────────────────────────────────────────────────────
print("\n=== STEP 6: Old vs New Canonical Comparison ===")

old_ids = sorted(set(r["example_id"] for r in old_records))
old_lookup_simple = {}
for r in old_records:
    eid = r["example_id"]
    meth = r["method"]
    if eid not in old_lookup_simple:
        old_lookup_simple[eid] = {}
    old_lookup_simple[eid][meth] = r

overlap_ids = set(unique_example_ids) & set(old_ids)
old_methods = sorted(set(r["method"] for r in old_records))
old_provider = old_records[0].get("provider") if old_records else "unknown"
old_model = old_records[0].get("model") if old_records else "unknown"
new_provider = new_records[0].get("provider") if new_records else "unknown"
new_model = new_records[0].get("model") if new_records else "unknown"

# Per-method accuracies for old
old_method_acc = {}
for meth in (METHODS if old_methods else []):
    subset = [r for r in old_records if r["method"] == meth]
    if subset:
        correct = sum(1 for r in subset if get_correct(r))
        old_method_acc[meth] = {"correct": correct, "total": len(subset), "accuracy": round(correct / len(subset), 6)}

new_method_acc = {}
for meth in METHODS:
    subset = [r for r in new_records if r["method"] == meth]
    if subset:
        correct = sum(1 for r in subset if get_correct(r))
        new_method_acc[meth] = {"correct": correct, "total": len(subset), "accuracy": round(correct / len(subset), 6)}

comparison_rows = []
for meth in METHODS:
    label = METHOD_LABELS[meth]
    old = old_method_acc.get(meth, {})
    new = new_method_acc.get(meth, {})
    comparison_rows.append({
        "method": meth,
        "label": label,
        "old_correct": old.get("correct", "N/A"),
        "old_total": old.get("total", "N/A"),
        "old_accuracy": old.get("accuracy", "N/A"),
        "new_correct": new.get("correct", "N/A"),
        "new_total": new.get("total", "N/A"),
        "new_accuracy": new.get("accuracy", "N/A"),
        "delta_new_minus_old": round(new.get("accuracy", 0) - old.get("accuracy", 0), 6) if old and new else "N/A",
    })

overlap_summary = {
    "new_unique_example_ids": len(unique_example_ids),
    "old_unique_example_ids": len(old_ids),
    "overlap_count": len(overlap_ids),
    "new_methods": sorted(set(r["method"] for r in new_records)),
    "old_methods": old_methods,
    "new_provider": new_provider,
    "old_provider": old_provider,
    "new_model": new_model,
    "old_model": old_model,
    "same_example_set": len(overlap_ids) == len(unique_example_ids) == len(old_ids),
    "note": "New run uses openai_gsm8k_train_* IDs (contract-matched Final-300). Old run used different example IDs. Direct per-example correctness diff is only meaningful if overlap is large.",
}
write_json(OUTDIR / "old_vs_new_example_overlap_summary.json", overlap_summary)
write_csv(OUTDIR / "old_vs_new_canonical_comparison.csv", comparison_rows)

# Per-example correctness diff for overlapping IDs
diff_rows = []
for eid in sorted(overlap_ids):
    for meth in METHODS:
        old_rec = old_lookup_simple.get(eid, {}).get(meth)
        new_rec = new_lookup.get(eid, {}).get(meth)
        old_ok = get_correct(old_rec) if old_rec else None
        new_ok = get_correct(new_rec) if new_rec else None
        old_ans = get_ans(old_rec) if old_rec else None
        new_ans = get_ans(new_rec) if new_rec else None
        if old_ok is not None and new_ok is not None:
            diff_rows.append({
                "example_id": eid,
                "method": meth,
                "label": METHOD_LABELS[meth],
                "old_correct": int(old_ok),
                "new_correct": int(new_ok),
                "changed": int(old_ok != new_ok),
                "old_ans": old_ans,
                "new_ans": new_ans,
                "direction": "new_better" if (not old_ok and new_ok) else ("old_better" if (old_ok and not new_ok) else "same"),
            })

write_csv(OUTDIR / "old_vs_new_method_correctness_diff.csv", diff_rows)

print(f"  overlap examples: {len(overlap_ids)}")
print(f"  old provider/model: {old_provider}/{old_model}")
print(f"  new provider/model: {new_provider}/{new_model}")
for row in comparison_rows:
    print(f"    {row['label']:10s}  old={row['old_accuracy']}  new={row['new_accuracy']}  delta={row['delta_new_minus_old']}")

# Live reproduction diagnostic markdown
repro_lines = [
    "# Live Reproduction Diagnostic: Old vs New Canonical Cohere Run",
    "",
    f"**New run:** contract-matched Final-300, {new_provider}/{new_model}, seed=71",
    f"**Old run:** final_fix24, {old_provider}/{old_model}, seed=71 (estimated)",
    "",
    "## Example Set Overlap",
    f"- New unique IDs: {len(unique_example_ids)} (all `openai_gsm8k_train_*`)",
    f"- Old unique IDs: {len(old_ids)}",
    f"- Overlap: {len(overlap_ids)}",
    "",
    "## Method Accuracy Comparison",
    "| Method | Old acc | New acc | Delta |",
    "|--------|---------|---------|-------|",
]
for row in comparison_rows:
    repro_lines.append(f"| {row['label']} | {row['old_accuracy']} | {row['new_accuracy']} | {row['delta_new_minus_old']} |")

if len(overlap_ids) == 0:
    repro_lines += [
        "",
        "## Diagnosis",
        "The new contract-matched run uses a **different set of examples** than the old final_fix24 run.",
        "The new run uses `openai_gsm8k_train_*` examples from the canonical Final-300 prep contract,",
        "while the old run used a different sample (likely test or a different train split).",
        "Per-example correctness comparison is not meaningful without overlapping IDs.",
        "The accuracy differences reflect both the different example set and any model/policy changes.",
    ]
elif len(overlap_ids) < 50:
    repro_lines += [
        "",
        f"## Diagnosis",
        f"Only {len(overlap_ids)} overlapping examples — insufficient for reliable per-example comparison.",
    ]
else:
    n_diff = sum(1 for r in diff_rows if r["changed"])
    repro_lines += [
        "",
        f"## Per-Example Correctness Changes (on {len(overlap_ids)} overlapping examples)",
        f"- Changed: {n_diff} of {len(diff_rows)} (example×method rows)",
    ]

write_md(OUTDIR / "live_reproduction_diagnostic.md", "\n".join(repro_lines))

# ───────────────────────────────────────────────────────────────────
# STEP 7 — RECOVERY/REGRESSION CASE LISTS
# ───────────────────────────────────────────────────────────────────
print("\n=== STEP 7: Case Lists ===")

CASE_FIELDS = ["example_id", "gold", "f_ans", "l1_ans", "s1_ans", "tale_ans",
               "f_ok", "l1_ok", "s1_ok", "tale_ok", "agr_ans", "agr_action", "agr_ok",
               "pool_ans", "pool_action", "pool_ok", "lt_agree", "lt_ans", "lt_ok",
               "lt_agree_wrong", "lt_agree_wrong_s1_correct"]

def case_subset(condition_fn):
    return [{k: e[k] for k in CASE_FIELDS if k in e} for e in examples if condition_fn(e)]

# agreement recovers frontier: frontier wrong, agreement correct
agr_recoveries = case_subset(lambda e: not e["f_ok"] and e["agr_ok"])
# agreement regresses from frontier: frontier correct, agreement wrong
agr_regressions = case_subset(lambda e: e["f_ok"] and not e["agr_ok"])
# pooled-4 recovers frontier
pool_recoveries = case_subset(lambda e: not e["f_ok"] and e["pool_ok"])
# pooled-4 regresses from frontier
pool_regressions = case_subset(lambda e: e["f_ok"] and not e["pool_ok"])
# S1 beats agreement: agreement wrong, S1 correct
s1_beats_agr = case_subset(lambda e: not e["agr_ok"] and e["s1_ok"])
# agreement beats S1: S1 wrong, agreement correct
agr_beats_s1 = case_subset(lambda e: e["agr_ok"] and not e["s1_ok"])
# L1+TALE agree wrong, S1 correct
lt_wrong_s1_correct = case_subset(lambda e: e["lt_agree_wrong_s1_correct"])
# external majority excludes correct S1: agr chose external majority that's wrong, but S1 correct
ext_excl_s1 = case_subset(lambda e: e["agr_action"] == "external_majority" and not e["agr_ok"] and e["s1_ok"])
# agreement keeps wrong frontier: frontier wrong, agr kept frontier (no external majority), and some external is correct
agr_keeps_wrong_frontier = case_subset(lambda e: not e["f_ok"] and e["agr_action"] in ("kept_frontier", "frontier_majority_match") and not e["agr_ok"] and any(e[c] for c in ["l1_ok", "s1_ok", "tale_ok"]))

for fname, data in [
    ("agreement_vs_frontier_recoveries.csv", agr_recoveries),
    ("agreement_vs_frontier_regressions.csv", agr_regressions),
    ("pooled4_vs_frontier_recoveries.csv", pool_recoveries),
    ("pooled4_vs_frontier_regressions.csv", pool_regressions),
    ("s1_beats_agreement_cases.csv", s1_beats_agr),
    ("agreement_beats_s1_cases.csv", agr_beats_s1),
    ("l1_tale_wrong_s1_correct_cases.csv", lt_wrong_s1_correct),
    ("external_majority_excludes_correct_s1_cases.csv", ext_excl_s1),
    ("agreement_keeps_wrong_frontier_cases.csv", agr_keeps_wrong_frontier),
]:
    write_csv(OUTDIR / fname, data)

print(f"  agr recoveries vs frontier: {len(agr_recoveries)}")
print(f"  agr regressions vs frontier: {len(agr_regressions)}")
print(f"  pool recoveries vs frontier: {len(pool_recoveries)}")
print(f"  pool regressions vs frontier: {len(pool_regressions)}")
print(f"  S1 beats agreement: {len(s1_beats_agr)}")
print(f"  agreement beats S1: {len(agr_beats_s1)}")
print(f"  L1+TALE wrong, S1 correct: {len(lt_wrong_s1_correct)}")
print(f"  ext majority excludes correct S1: {len(ext_excl_s1)}")
print(f"  agreement keeps wrong frontier: {len(agr_keeps_wrong_frontier)}")

# ───────────────────────────────────────────────────────────────────
# STEP 8 — MISTRAL-DERIVED CORRELATION-AWARE RULES ON COHERE CANONICAL
# ───────────────────────────────────────────────────────────────────
print("\n=== STEP 8: Correlation-Aware Diagnostic Rules ===")

def rule_agr_downweight_lt_if_frontier_disagrees_and_s1_clean(e):
    """If L1+TALE agree against frontier AND S1 is clean numeric, override with S1."""
    lt_agree = e["lt_agree"]
    if lt_agree and not e["frontier_agrees_lt"] and e["s1_clean"]:
        return e["s1_ans"], "s1_override"
    return e["agr_ans"], e["agr_action"]

def rule_choose_s1_when_lt_against_s1_and_s1_clean(e):
    """If L1+TALE agree and their answer ≠ S1 and S1 is clean numeric, pick S1."""
    lt_agree = e["lt_agree"]
    if lt_agree and e["lt_ans"] != e["s1_ans"] and e["s1_clean"]:
        return e["s1_ans"], "s1_clean_override"
    return e["agr_ans"], e["agr_action"]

def rule_clean_numeric_s1_override(e):
    """Always prefer S1 when S1 is clean numeric and agreement would pick differently."""
    if e["s1_clean"] and e["agr_ans"] != e["s1_ans"]:
        return e["s1_ans"], "s1_clean_global_override"
    return e["agr_ans"], e["agr_action"]

def rule_provider_prior_s1(e):
    """Always-S1 prior (Mistral-specific reference)."""
    return e["s1_ans"], "always_s1"

def rule_source_family_vote(e):
    """Treat L1+TALE as one vote, S1 as one vote, frontier as one vote (3 voters)."""
    lt_vote = e["lt_ans"] if e["lt_agree"] else None
    f_vote = e["f_ans"]
    s1_vote = e["s1_ans"]
    votes = [v for v in [lt_vote, f_vote, s1_vote] if v is not None]
    vote_counts = collections.Counter(votes)
    best_ans, best_count = vote_counts.most_common(1)[0] if vote_counts else (f_vote, 0)
    if best_count >= 2 and best_ans != f_vote:
        return best_ans, "family_majority"
    elif best_count >= 2:
        return f_vote, "family_frontier_match"
    return f_vote, "family_fallback"

# Oracle
def oracle_pick(e):
    for ans, ok in [(e["agr_ans"], e["agr_ok"]), (e["f_ans"], e["f_ok"]),
                    (e["l1_ans"], e["l1_ok"]), (e["s1_ans"], e["s1_ok"]), (e["tale_ans"], e["tale_ok"])]:
        if ok:
            return ans, "oracle"
    return e["agr_ans"], "oracle_all_wrong"

def eval_rule(rule_fn, label, is_runtime_legal=True, is_provider_agnostic=True):
    correct = 0
    recoveries_vs_agr = 0
    regressions_vs_agr = 0
    recoveries_vs_frontier = 0
    regressions_vs_frontier = 0
    wins_vs_agr = 0
    losses_vs_agr = 0
    wins_vs_s1 = 0
    losses_vs_s1 = 0
    bad_lt_recovered = 0
    good_lt_broken = 0
    oracle_regret = 0

    results = []
    for e in examples:
        ans, action = rule_fn(e)
        gold = e["gold"]
        ok = int(str(ans).strip() == str(gold).strip()) if (ans is not None and gold is not None) else 0
        agr_ok = e["agr_ok"]
        f_ok = e["f_ok"]
        s1_ok = e["s1_ok"]

        correct += ok
        if ok and not agr_ok:
            recoveries_vs_agr += 1
        elif agr_ok and not ok:
            regressions_vs_agr += 1
        if ok and not f_ok:
            recoveries_vs_frontier += 1
        elif f_ok and not ok:
            regressions_vs_frontier += 1

        if ok > agr_ok:
            wins_vs_agr += 1
        elif ok < agr_ok:
            losses_vs_agr += 1

        if ok > s1_ok:
            wins_vs_s1 += 1
        elif ok < s1_ok:
            losses_vs_s1 += 1

        oracle_ok = int(any(e[c] for c in ["f_ok", "l1_ok", "s1_ok", "tale_ok"]))
        if oracle_ok and not ok:
            oracle_regret += 1

        # Bad L1+TALE recovered: lt_agree_wrong_s1_correct and now ok
        if e["lt_agree_wrong_s1_correct"] and ok:
            bad_lt_recovered += 1
        # Good L1+TALE broken: lt_agree and lt_ok and now not ok
        if e["lt_agree"] and e["lt_ok"] and not ok:
            good_lt_broken += 1

        results.append(ok)

    agr_correct = sum(e["agr_ok"] for e in examples)
    s1_correct = sum(e["s1_ok"] for e in examples)
    f_correct = sum(e["f_ok"] for e in examples)
    pool_correct = sum(e["pool_ok"] for e in examples)

    return {
        "rule": label,
        "correct": correct,
        "accuracy": round(correct / N, 6),
        "delta_vs_agreement_only": round((correct - agr_correct) / N, 6),
        "delta_vs_frontier": round((correct - f_correct) / N, 6),
        "delta_vs_s1": round((correct - s1_correct) / N, 6),
        "delta_vs_pool4": round((correct - pool_correct) / N, 6),
        "recoveries_vs_agreement": recoveries_vs_agr,
        "regressions_vs_agreement": regressions_vs_agr,
        "recoveries_vs_frontier": recoveries_vs_frontier,
        "regressions_vs_frontier": regressions_vs_frontier,
        "wins_vs_agreement": wins_vs_agr,
        "losses_vs_agreement": losses_vs_agr,
        "wins_vs_s1": wins_vs_s1,
        "losses_vs_s1": losses_vs_s1,
        "oracle_regret": oracle_regret,
        "bad_lt_majority_recovered": bad_lt_recovered,
        "good_lt_majority_broken": good_lt_broken,
        "runtime_legal": int(is_runtime_legal),
        "provider_agnostic": int(is_provider_agnostic),
    }

variant_rows = []
variant_rows.append(eval_rule(lambda e: (e["f_ans"], "frontier"), "frontier"))
variant_rows.append(eval_rule(lambda e: (e["l1_ans"], "l1"), "L1"))
variant_rows.append(eval_rule(lambda e: (e["s1_ans"], "s1"), "S1"))
variant_rows.append(eval_rule(lambda e: (e["tale_ans"], "tale"), "TALE"))
variant_rows.append(eval_rule(lambda e: (e["agr_ans"], e["agr_action"]), "agreement_only"))
variant_rows.append(eval_rule(lambda e: (e["pool_ans"], e["pool_action"]), "pooled_4"))
variant_rows.append(eval_rule(rule_agr_downweight_lt_if_frontier_disagrees_and_s1_clean, "agreement_downweight_lt_if_frontier_disagrees_and_s1_clean"))
variant_rows.append(eval_rule(rule_choose_s1_when_lt_against_s1_and_s1_clean, "agreement_choose_s1_when_lt_against_s1_and_s1_clean"))
variant_rows.append(eval_rule(rule_clean_numeric_s1_override, "clean_numeric_s1_override"))
variant_rows.append(eval_rule(rule_provider_prior_s1, "always_s1_provider_prior", is_provider_agnostic=False))
variant_rows.append(eval_rule(rule_source_family_vote, "source_family_vote_L1TALE_family_plus_S1_plus_frontier"))
variant_rows.append(eval_rule(oracle_pick, "oracle", is_runtime_legal=False))

write_csv(OUTDIR / "correlation_aware_variant_summary.csv", variant_rows)

# Recoveries/regressions detail
rr_rows = []
for rule_fn, label in [
    (rule_agr_downweight_lt_if_frontier_disagrees_and_s1_clean, "downweight_lt_if_frontier_disagrees_s1_clean"),
    (rule_choose_s1_when_lt_against_s1_and_s1_clean, "choose_s1_when_lt_against_s1_s1_clean"),
    (rule_clean_numeric_s1_override, "clean_numeric_s1_override"),
    (rule_source_family_vote, "source_family_vote"),
]:
    for e in examples:
        ans, action = rule_fn(e)
        gold = e["gold"]
        ok = int(str(ans).strip() == str(gold).strip()) if (ans is not None and gold is not None) else 0
        agr_ok = e["agr_ok"]
        if ok != agr_ok:
            rr_rows.append({
                "rule": label,
                "example_id": e["example_id"],
                "direction": "recovery" if (ok and not agr_ok) else "regression",
                "rule_ans": ans,
                "agr_ans": e["agr_ans"],
                "gold": gold,
                "f_ok": e["f_ok"], "s1_ok": e["s1_ok"], "l1_ok": e["l1_ok"], "tale_ok": e["tale_ok"],
                "lt_agree": e["lt_agree"], "lt_agree_wrong_s1_correct": e["lt_agree_wrong_s1_correct"],
                "s1_clean": e["s1_clean"],
            })
write_csv(OUTDIR / "correlation_aware_variant_recoveries_regressions.csv", rr_rows)

# Transfer verdict
transfer_verdict_lines = [
    "# Correlation-Aware Rule Transfer Verdict: Cohere Canonical Final-300",
    "",
    "All variants evaluated **offline/diagnostic only** on new contract-matched Cohere Final-300 data.",
    "",
    "## Results Table",
    "",
    "| Rule | Acc | Δ agr-only | Recoveries | Regressions | Verdict |",
    "|------|-----|-----------|------------|-------------|---------|",
]
agr_acc = next(r["accuracy"] for r in variant_rows if r["rule"] == "agreement_only")

for row in variant_rows:
    if row["rule"] in ["frontier", "L1", "S1", "TALE", "agreement_only", "pooled_4", "oracle"]:
        verdict = "baseline"
    elif row["delta_vs_agreement_only"] > 0 and row["regressions_vs_agreement"] <= row["recoveries_vs_agreement"]:
        verdict = "transfers_positively"
    elif row["delta_vs_agreement_only"] > 0 and row["regressions_vs_agreement"] > row["recoveries_vs_agreement"]:
        verdict = "net_positive_but_fragile"
    elif row["delta_vs_agreement_only"] == 0:
        verdict = "neutral"
    elif row["delta_vs_agreement_only"] < 0:
        verdict = "harms_cohere"
    else:
        verdict = "inconclusive"
    transfer_verdict_lines.append(
        f"| {row['rule'][:45]} | {row['accuracy']:.4f} | {row['delta_vs_agreement_only']:+.4f} | {row['recoveries_vs_agreement']} | {row['regressions_vs_agreement']} | {verdict} |"
    )

transfer_verdict_lines += [
    "",
    "## Summary",
    "",
    f"- Agreement-only baseline: {agr_acc:.4f} ({int(agr_acc*300)}/300)",
    "",
    "### Notes",
    "- `agreement_downweight_lt_if_frontier_disagrees_and_s1_clean`: triggers when L1+TALE agree against frontier AND S1 is clean numeric → overrides with S1.",
    "- `agreement_choose_s1_when_lt_against_s1_and_s1_clean`: triggers when L1+TALE agree and their answer differs from S1 AND S1 is clean → picks S1.",
    "- `clean_numeric_s1_override`: always overrides agreement with S1 when S1 is clean and agreement differs.",
    "- `source_family_vote`: treats L1+TALE as one family vote, giving 3 voters total; majority of 3 wins.",
    "- All rules labeled diagnostic/offline only. No policy was promoted or modified.",
]

write_md(OUTDIR / "correlation_aware_transfer_verdict.md", "\n".join(transfer_verdict_lines))

print("  Variant results:")
for row in variant_rows:
    print(f"    {row['rule'][:50]:50s}  acc={row['accuracy']:.4f}  delta_agr={row['delta_vs_agreement_only']:+.4f}  rec={row['recoveries_vs_agreement']}  reg={row['regressions_vs_agreement']}")

# ───────────────────────────────────────────────────────────────────
# STEP 9 — CEREBRAS MONITOR (non-invasive read)
# ───────────────────────────────────────────────────────────────────
print("\n=== STEP 9: Cerebras Non-Invasive Monitor ===")

cerebras_log = Path("outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/live_validation_20260523T144414Z.log")
cerebras_heartbeat = Path("outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/cohere_real_model_cost_normalized_validation_20260523T144414Z/progress_heartbeat.jsonl")
cerebras_per_example = Path("outputs/cerebras_frozen_agreement_only_2of3_validation_20260523/cohere_real_model_cost_normalized_validation_20260523T144414Z/per_example_records.jsonl")

def file_mtime(p):
    if p.exists():
        return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
    return None

log_mtime = file_mtime(cerebras_log)
hb_mtime = file_mtime(cerebras_heartbeat)
pe_mtime = file_mtime(cerebras_per_example)

pe_count = 0
if cerebras_per_example.exists():
    with open(cerebras_per_example) as f:
        pe_count = sum(1 for _ in f)

# Last heartbeat event
last_hb = None
last_hb_event = None
attempted = None
scored = None
if cerebras_heartbeat.exists():
    with open(cerebras_heartbeat) as f:
        for line in f:
            try:
                last_hb = json.loads(line)
            except:
                pass
    if last_hb:
        last_hb_event = last_hb.get("event")
        attempted = last_hb.get("attempted_so_far")
        scored = last_hb.get("scored_so_far")

# Last log line
last_log_line = None
if cerebras_log.exists():
    with open(cerebras_log) as f:
        for line in f:
            if line.strip():
                last_log_line = line.strip()

now_utc = datetime.now(tz=timezone.utc).isoformat()

cerebras_status = {
    "check_timestamp_utc": now_utc,
    "log_path": str(cerebras_log),
    "log_mtime_utc": log_mtime,
    "heartbeat_mtime_utc": hb_mtime,
    "per_example_mtime_utc": pe_mtime,
    "per_example_line_count": pe_count,
    "last_heartbeat_event": last_hb_event,
    "last_heartbeat_attempted": attempted,
    "last_heartbeat_scored": scored,
    "last_log_line": last_log_line,
    "status_assessment": "possibly_stalled" if pe_count < 300 else "progressing_or_complete",
    "note": "Process PID 2195513 was still alive at prior check (stat=Sl+, 0% CPU). Log has not updated in 50+ min as of 21:56Z. May have recovered or may still be stuck on openai_gsm8k_164 (direct_reserve_semantic_frontier_v2).",
    "action": "monitor_only_do_not_touch",
}

write_json(OUTDIR / "cerebras_status_during_cohere_processing.json", cerebras_status)
print(f"  Cerebras per_example count: {pe_count}")
print(f"  Last heartbeat: event={last_hb_event}, attempted={attempted}, scored={scored}")
print(f"  Log last modified: {log_mtime}")

# ───────────────────────────────────────────────────────────────────
# STEP 11 — MANIFEST
# ───────────────────────────────────────────────────────────────────
print("\n=== Writing Manifest ===")
manifest = {
    "task": "cohere_canonical_final300_frozen_agreement_live_result",
    "created_utc": datetime.now(tz=timezone.utc).isoformat(),
    "source_artifacts": [
        str(NEW_PER_EXAMPLE),
        str(EXACT_CASES),
        str(ALLOWED_IDS),
        str(COMPLETION_SUMMARY),
        str(FAILURE_TAX),
        str(OLD_PER_EXAMPLE),
    ],
    "output_directory": str(OUTDIR),
    "files_created": [
        "integrity_summary.json",
        "per_method_completion_counts.csv",
        "per_example_completeness.csv",
        "failure_taxonomy_summary.json",
        "canonical_overlap_summary.json",
        "canonical_id_order_check.csv",
        "method_accuracy_summary.csv",
        "frozen_replay_summary.csv",
        "win_loss_tie_summary.csv",
        "paired_ci_summary.csv",
        "mcnemar_summary.csv",
        "old_vs_new_canonical_comparison.csv",
        "old_vs_new_example_overlap_summary.json",
        "old_vs_new_method_correctness_diff.csv",
        "live_reproduction_diagnostic.md",
        "agreement_vs_frontier_recoveries.csv",
        "agreement_vs_frontier_regressions.csv",
        "pooled4_vs_frontier_recoveries.csv",
        "pooled4_vs_frontier_regressions.csv",
        "s1_beats_agreement_cases.csv",
        "agreement_beats_s1_cases.csv",
        "l1_tale_wrong_s1_correct_cases.csv",
        "external_majority_excludes_correct_s1_cases.csv",
        "agreement_keeps_wrong_frontier_cases.csv",
        "correlation_aware_variant_summary.csv",
        "correlation_aware_variant_recoveries_regressions.csv",
        "correlation_aware_transfer_verdict.md",
        "cerebras_status_during_cohere_processing.json",
        "manifest.json",
    ],
    "replay_policies_evaluated": [
        "frontier", "L1", "S1", "TALE",
        "agreement_only_2of3_against_frontier",
        "pooled_4_with_fallback",
        "agreement_downweight_lt_if_frontier_disagrees_and_s1_clean",
        "agreement_choose_s1_when_lt_against_s1_and_s1_clean",
        "clean_numeric_s1_override",
        "always_s1_provider_prior",
        "source_family_vote_L1TALE_family_plus_S1_plus_frontier",
        "oracle",
    ],
    "api_calls_made": False,
    "active_cerebras_untouched": True,
    "frozen_policy_modified": False,
    "artifacts_overwritten": False,
    "note": "All diagnostic variants are offline/diagnostic only. No policy was promoted or modified.",
}
write_json(OUTDIR / "manifest.json", manifest)

print("\nAll steps complete.")
print(f"Outputs: {OUTDIR}")
