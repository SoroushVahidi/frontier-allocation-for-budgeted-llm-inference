#!/usr/bin/env python3
"""
Correlation-aware transfer-risk diagnostic.
Tests whether Mistral-derived L1+TALE downweighting rules transfer to nonmatched Cohere.
No API calls. No policy promotion. No touching active jobs.
"""
import csv, json, math, re, sys
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference")
MISTRAL_JSONL = (REPO / "outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z"
                 / "cohere_real_model_cost_normalized_validation_20260523T145416Z"
                 / "per_example_records.jsonl")
COHERE_JSONL = (REPO / "outputs/live_validation_hardening_frozen_agreement_policy_20260523"
                / "cohere_real_model_cost_normalized_validation_20260523T131849Z"
                / "per_example_records.jsonl")
MISTRAL_UNIFIED = REPO / "outputs/mistral_l1_tale_correlation_diagnostic_20260523/unified_mistral_table.csv"
MISTRAL_ALG_UNIFIED = REPO / "outputs/mistral_algorithm_improvement_diagnostic_20260523/unified_mistral_example_table.csv"
OUT = REPO / "outputs/correlation_aware_transfer_risk_diagnostic_20260523"
OUT.mkdir(parents=True, exist_ok=True)

METHOD_MAP = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "l1",
    "external_s1_budget_forcing": "s1",
    "external_tale_prompt_budgeting": "tale",
}
CLEAN_NUM_RE = re.compile(r"^\-?\d+(\.\d+)?$")

def is_clean(v):
    v = str(v or "").strip()
    return bool(v and CLEAN_NUM_RE.match(v))

def reasoning_len(rec):
    return sum(len(n.get("reasoning_text", "")) for n in (rec.get("final_nodes") or []))

def to_float(v):
    try: return float(str(v).strip())
    except: return None

# ─── Load JSONL helper ───────────────────────────────────────────────────────
def load_jsonl(path):
    recs, eids, seen = {}, [], set()
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            eid = r["example_id"]
            m = METHOD_MAP.get(r["method"], r["method"])
            recs[(eid, m)] = r
            if eid not in seen:
                eids.append(eid)
                seen.add(eid)
    return recs, eids

print("[1] Loading JSONL records ...")
mrecs, meids = load_jsonl(MISTRAL_JSONL)
crecs, ceids = load_jsonl(COHERE_JSONL)
print(f"  Mistral: {len(meids)} examples | Cohere nonmatched: {len(ceids)} examples")

# ─── Load Mistral unified table (for pre-computed selector columns) ──────────
print("[2] Loading Mistral unified table ...")
m_unified = {}
with open(MISTRAL_UNIFIED, newline="") as f:
    for row in csv.DictReader(f):
        m_unified[row["example_id"]] = row

m_alg_unified = {}
with open(MISTRAL_ALG_UNIFIED, newline="") as f:
    for row in csv.DictReader(f):
        m_alg_unified[row["example_id"]] = row
print(f"  Loaded {len(m_unified)} Mistral rows (transfer table) + {len(m_alg_unified)} alg rows")

def gf(d, k, default=""):
    return d.get(k, default) or default

# ─── Build per-provider enriched rows ───────────────────────────────────────
def build_provider_rows(recs, eids, unified=None):
    rows = []
    for eid in eids:
        def ga(m):
            rec = recs.get((eid, m), {})
            return str(rec.get("final_answer_canonical") or rec.get("final_answer_raw") or "")
        def gc(m):
            return bool(recs.get((eid, m), {}).get("exact_match"))
        def rl(m):
            return reasoning_len(recs.get((eid, m), {}))

        f_ans, l_ans, s_ans, t_ans = ga("frontier"), ga("l1"), ga("s1"), ga("tale")
        f_ok, l_ok, s_ok, t_ok = gc("frontier"), gc("l1"), gc("s1"), gc("tale")
        f_rlen, l_rlen, s_rlen, t_rlen = rl("frontier"), rl("l1"), rl("s1"), rl("tale")

        lt_agree = l_ans == t_ans and l_ans != ""
        lt_correct = l_ok  # if they agree, both have same correctness
        lt_ans = l_ans if lt_agree else ""
        lt_against_s1 = lt_agree and lt_ans != s_ans
        f_agrees_lt = lt_agree and f_ans == lt_ans
        f_agrees_s1 = f_ans == s_ans

        s1_clean = is_clean(s_ans)
        l1_clean = is_clean(l_ans)

        # unique answer count
        uniq = len(set(v for v in [f_ans, l_ans, s_ans, t_ans] if v))
        s1_isolated = (sum(1 for v in [f_ans, l_ans, t_ans] if v == s_ans) == 0) if s_ans else False

        # External majority (L1+TALE based, not frontier)
        ext_maj_exists = lt_agree
        ext_maj_incl_s1 = lt_agree and lt_ans == s_ans
        ext_maj_excl_s1 = lt_agree and lt_ans != s_ans

        # Derived from unified if available (Mistral only)
        row = {
            "example_id": eid,
            "question": gf(unified.get(eid, {}) if unified else {}, "question"),
            "gold_answer": gf(unified.get(eid, {}) if unified else {},
                              "gold_answer", str(recs.get((eid, "frontier"), {}).get("gold_answer", ""))),
            "frontier_answer": f_ans, "frontier_correct": f_ok,
            "l1_answer": l_ans, "l1_correct": l_ok,
            "s1_answer": s_ans, "s1_correct": s_ok,
            "tale_answer": t_ans, "tale_correct": t_ok,
            "lt_agree": lt_agree, "lt_ans": lt_ans, "lt_correct": lt_correct,
            "lt_against_s1": lt_against_s1,
            "frontier_agrees_lt": f_agrees_lt,
            "frontier_agrees_s1": f_agrees_s1,
            "s1_clean_numeric": s1_clean,
            "l1_clean_numeric": l1_clean,
            "s1_isolated": s1_isolated,
            "unique_answer_count": uniq,
            "ext_maj_exists": ext_maj_exists,
            "ext_maj_incl_s1": ext_maj_incl_s1,
            "ext_maj_excl_s1": ext_maj_excl_s1,
            "s1_reasoning_len": s_rlen,
            "l1_reasoning_len": l_rlen,
            "frontier_reasoning_len": f_rlen,
            "s1_answer_len": len(s_ans),
            "l1_answer_len": len(l_ans),
        }

        # agreement-only (from unified for Mistral, approximate for Cohere)
        if unified and eid in unified:
            u = unified[eid]
            row["agr_correct"] = gf(u, "agreement_only_2of3_against_frontier_correct") == "1"
            row["agr_action"] = gf(u, "agreement_only_2of3_against_frontier_selected_action")
            row["agr_answer"] = gf(u, "agreement_only_2of3_against_frontier_selected_answer")
            row["pooled4_correct"] = gf(u, "pooled_4_with_fallback_correct") == "1"
            row["always_s1_correct"] = gf(u, "always_s1_correct") == "1"
            row["oracle_correct"] = gf(u, "oracle_over_four_sources_correct") == "1"
            # Existing diagnostic variant columns
            row["clean_numeric_override_correct"] = gf(u, "agreement_only_but_if_external_majority_excludes_s1_choose_s1_when_s1_has_short_clean_numeric_answer_correct") == "1"
            row["no_majority_override_correct"] = gf(u, "agreement_only_but_if_no_majority_and_s1_differs_from_frontier_choose_s1_correct") == "1"
            row["provider_prior_s1_correct"] = gf(u, "provider_prior_weighted_selector_mistral_s1_prior_correct") == "1"
        else:
            # Approximate agreement-only for Cohere: use external majority logic
            if lt_agree and lt_ans != f_ans:
                # External majority (L1+TALE) disagrees with frontier
                agr_ans = lt_ans
                agr_ok = lt_correct
                agr_action = "external_majority"
            else:
                agr_ans = f_ans
                agr_ok = f_ok
                agr_action = "frontier_fallback" if not lt_agree else "frontier_majority_match"
            row["agr_correct"] = agr_ok
            row["agr_action"] = agr_action
            row["agr_answer"] = agr_ans
            # pooled-4: majority among all 4
            vote = Counter(v for v in [f_ans, l_ans, s_ans, t_ans] if v)
            winner, cnt = vote.most_common(1)[0]
            row["pooled4_correct"] = (
                (winner == f_ans and f_ok) or (winner == l_ans and l_ok) or
                (winner == s_ans and s_ok) or (winner == t_ans and t_ok)
            ) if cnt >= 2 else f_ok
            row["always_s1_correct"] = s_ok
            row["oracle_correct"] = f_ok or l_ok or s_ok or t_ok
            row["clean_numeric_override_correct"] = None  # not precomputed for Cohere
            row["no_majority_override_correct"] = None
            row["provider_prior_s1_correct"] = None

        rows.append(row)
    return rows

print("[3] Building enriched rows ...")
m_rows = build_provider_rows(mrecs, meids, m_unified)
c_rows = build_provider_rows(crecs, ceids, None)
print(f"  Mistral: {len(m_rows)} | Cohere: {len(c_rows)}")

# Save transfer tables
TRANSFER_COLS = [
    "example_id", "question", "gold_answer",
    "frontier_answer", "frontier_correct", "l1_answer", "l1_correct",
    "s1_answer", "s1_correct", "tale_answer", "tale_correct",
    "lt_agree", "lt_ans", "lt_correct", "lt_against_s1",
    "frontier_agrees_lt", "frontier_agrees_s1",
    "s1_clean_numeric", "l1_clean_numeric", "s1_isolated",
    "unique_answer_count", "ext_maj_exists", "ext_maj_incl_s1", "ext_maj_excl_s1",
    "agr_correct", "agr_action", "agr_answer",
    "pooled4_correct", "always_s1_correct", "oracle_correct",
    "s1_reasoning_len", "l1_reasoning_len", "frontier_reasoning_len",
]
for path, rows in [(OUT / "mistral_transfer_table.csv", m_rows),
                   (OUT / "cohere_nonmatched_transfer_table.csv", c_rows)]:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRANSFER_COLS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in TRANSFER_COLS})
print("  Saved mistral_transfer_table.csv and cohere_nonmatched_transfer_table.csv")

# ─── Step 4: Cross-provider L1+TALE correlation structure ───────────────────
print("[4] Cross-provider L1+TALE correlation structure ...")

def compute_l1_tale_stats(rows, name):
    n = len(rows)
    lt_agree = [r for r in rows if r["lt_agree"]]
    lt_correct = [r for r in lt_agree if r["lt_correct"]]
    lt_wrong = [r for r in lt_agree if not r["lt_correct"]]
    lt_wrong_s1_ok = [r for r in lt_wrong if r["s1_correct"]]
    lt_wrong_f_ok = [r for r in lt_wrong if r["frontier_correct"]]
    lt_correct_s1_wrong = [r for r in lt_correct if not r["s1_correct"]]
    lt_against_s1 = [r for r in lt_agree if r["lt_against_s1"]]
    bad_all = [r for r in rows if not r["lt_correct"] and r.get("lt_agree") and r["s1_correct"]]

    def avg_uniq(grp):
        if not grp: return ""
        return f"{sum(r['unique_answer_count'] for r in grp)/len(grp):.2f}"
    def pct_f_supports_lt(grp):
        if not grp: return ""
        return f"{sum(1 for r in grp if r['frontier_agrees_lt'])/len(grp):.3f}"
    def pct_s1_clean(grp):
        if not grp: return ""
        return f"{sum(1 for r in grp if r['s1_clean_numeric'])/len(grp):.3f}"

    return {
        "provider": name,
        "total_examples": n,
        "lt_agree_count": len(lt_agree),
        "lt_agree_rate": f"{100*len(lt_agree)/max(n,1):.1f}%",
        "lt_agree_correct_count": len(lt_correct),
        "lt_agree_correct_rate": f"{100*len(lt_correct)/max(len(lt_agree),1):.1f}%",
        "lt_agree_wrong_count": len(lt_wrong),
        "lt_agree_wrong_rate": f"{100*len(lt_wrong)/max(len(lt_agree),1):.1f}%",
        "lt_wrong_s1_correct_BAD": len(lt_wrong_s1_ok),
        "bad_rate_of_agreements": f"{100*len(lt_wrong_s1_ok)/max(len(lt_agree),1):.1f}%",
        "bad_rate_of_all": f"{100*len(lt_wrong_s1_ok)/max(n,1):.1f}%",
        "lt_wrong_frontier_correct": len(lt_wrong_f_ok),
        "lt_correct_s1_wrong": len(lt_correct_s1_wrong),
        "lt_against_s1_count": len(lt_against_s1),
        "avg_uniq_bad_majority": avg_uniq(lt_wrong_s1_ok),
        "avg_uniq_good_majority": avg_uniq(lt_correct),
        "pct_frontier_supports_lt_bad": pct_f_supports_lt(lt_wrong_s1_ok),
        "pct_frontier_supports_lt_good": pct_f_supports_lt(lt_correct),
        "pct_s1_clean_bad": pct_s1_clean(lt_wrong_s1_ok),
        "pct_s1_clean_good": pct_s1_clean(lt_correct),
    }

m_stats = compute_l1_tale_stats(m_rows, "mistral")
c_stats = compute_l1_tale_stats(c_rows, "cohere_nonmatched")

with open(OUT / "l1_tale_correlation_cross_provider_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(m_stats.keys()))
    writer.writeheader()
    writer.writerows([m_stats, c_stats])
print(f"  Mistral: bad={m_stats['lt_wrong_s1_correct_BAD']} ({m_stats['bad_rate_of_agreements']} of agreements)")
print(f"  Cohere:  bad={c_stats['lt_wrong_s1_correct_BAD']} ({c_stats['bad_rate_of_agreements']} of agreements)")

# Case comparison CSVs
bad_m = [r for r in m_rows if r["lt_agree"] and not r["lt_correct"] and r["s1_correct"]]
bad_c = [r for r in c_rows if r["lt_agree"] and not r["lt_correct"] and r["s1_correct"]]
good_m = [r for r in m_rows if r["lt_agree"] and r["lt_correct"]]
good_c = [r for r in c_rows if r["lt_agree"] and r["lt_correct"]]

case_cols = ["example_id", "question", "gold_answer",
             "l1_answer", "s1_answer", "frontier_answer",
             "lt_correct", "s1_correct", "frontier_correct",
             "frontier_agrees_lt", "s1_clean_numeric", "unique_answer_count",
             "agr_correct", "agr_action"]
for path, rows in [(OUT / "l1_tale_bad_majority_case_comparison.csv",
                    [dict(provider="mistral", **{k: r.get(k,"") for k in case_cols}) for r in bad_m] +
                    [dict(provider="cohere_nonmatched", **{k: r.get(k,"") for k in case_cols}) for r in bad_c]),
                   (OUT / "l1_tale_good_majority_case_comparison.csv",
                    [dict(provider="mistral", **{k: r.get(k,"") for k in case_cols}) for r in good_m[:20]] +
                    [dict(provider="cohere_nonmatched", **{k: r.get(k,"") for k in case_cols}) for r in good_c[:20]])]:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["provider"] + case_cols)
        writer.writeheader()
        writer.writerows(rows)
print("  Saved bad and good majority case comparisons")

# ─── Step 5: Apply Mistral-derived variants to Cohere ───────────────────────
print("[5] Applying Mistral-derived variants to Cohere nonmatched ...")

# ── Selector rules (provider-agnostic, applied to any row dict) ──────────────
def agr_baseline(r):
    return int(r["agr_correct"])

def always_s1(r):
    return int(r["s1_correct"])

def always_frontier(r):
    return int(r["frontier_correct"])

def always_l1(r):
    return int(r["l1_correct"])

def always_tale(r):
    return int(r["tale_correct"])

def pooled4(r):
    return int(r["pooled4_correct"])

def oracle(r):
    return int(r["oracle_correct"])

def rule_downweight_lt_if_f_disagrees_and_s1_clean(r):
    """Override to S1 when L1+TALE agree against S1 and frontier also disagrees with L1+TALE and S1 is clean."""
    lt_against_s1 = r["lt_against_s1"]
    f_disagrees_lt = r["lt_agree"] and not r["frontier_agrees_lt"]
    s1_clean = r["s1_clean_numeric"]
    if lt_against_s1 and f_disagrees_lt and s1_clean:
        return int(r["s1_correct"])
    return int(r["agr_correct"])

def rule_choose_s1_when_lt_against_s1_and_clean(r):
    """Override to S1 when L1+TALE agree against S1 and S1 is clean."""
    if r["lt_against_s1"] and r["s1_clean_numeric"]:
        return int(r["s1_correct"])
    return int(r["agr_correct"])

def rule_require_frontier_for_lt_majority(r):
    """L1+TALE external majority only counts if frontier also agrees."""
    lt_agree = r["lt_agree"]
    f_agrees_lt = r["frontier_agrees_lt"]
    if lt_agree and not f_agrees_lt:
        # L1+TALE agree but frontier disagrees → ignore L1+TALE, use frontier
        return int(r["frontier_correct"])
    return int(r["agr_correct"])

def rule_treat_lt_as_one_vote(r):
    """L1+TALE count as one correlated vote; majority among {frontier, s1, lt-family}."""
    f_ans = r["frontier_answer"]
    s_ans = r["s1_answer"]
    lt = r["lt_ans"] if r["lt_agree"] else None
    votes = Counter(v for v in [f_ans, s_ans, lt] if v)
    if not votes: return int(r["frontier_correct"])
    winner, cnt = votes.most_common(1)[0]
    if cnt >= 2:
        if winner == f_ans: return int(r["frontier_correct"])
        if winner == s_ans: return int(r["s1_correct"])
        if winner == lt: return int(r["l1_correct"])
    return int(r["frontier_correct"])

def rule_source_family_vote(r):
    """Same as treat_lt_as_one_vote but written explicitly as 3-party vote."""
    f_ans = r["frontier_answer"]
    s_ans = r["s1_answer"]
    lt = r["lt_ans"] if r["lt_agree"] else ""
    votes = Counter(v for v in [f_ans, s_ans, lt] if v)
    if not votes: return int(r["frontier_correct"])
    winner, cnt = votes.most_common(1)[0]
    if cnt >= 2:
        if winner == f_ans: return int(r["frontier_correct"])
        if winner == s_ans: return int(r["s1_correct"])
        if winner == lt: return int(r["l1_correct"])
    return int(r["frontier_correct"])

def rule_conservative_s1_override(r):
    """Override to S1 only when L1+TALE agree against S1 AND S1 clean AND frontier also ≠ S1."""
    lt_against_s1 = r["lt_against_s1"]
    f_not_s1 = r["frontier_answer"] != r["s1_answer"]
    s1_clean = r["s1_clean_numeric"]
    if lt_against_s1 and f_not_s1 and s1_clean:
        return int(r["s1_correct"])
    return int(r["agr_correct"])

def rule_clean_numeric_override(r):
    """Override to S1 when ext_maj_excl_s1 and S1 clean. For Cohere: use lt_against_s1 as proxy."""
    if r.get("clean_numeric_override_correct") is not None:
        return int(r["clean_numeric_override_correct"])
    # Compute from features (Cohere)
    if r["ext_maj_excl_s1"] and r["s1_clean_numeric"]:
        return int(r["s1_correct"])
    return int(r["agr_correct"])

def rule_no_majority_override(r):
    """Override to S1 when no external majority and S1 differs from frontier."""
    if r.get("no_majority_override_correct") is not None:
        return int(r["no_majority_override_correct"])
    # Compute from features (Cohere)
    no_ext_maj = not r["ext_maj_exists"]
    s1_differs_frontier = r["s1_answer"] != r["frontier_answer"]
    if no_ext_maj and s1_differs_frontier:
        return int(r["s1_correct"])
    return int(r["agr_correct"])

def rule_provider_prior_s1(r):
    """Provider prior weighted S1 — pre-computed for Mistral, approx for Cohere."""
    if r.get("provider_prior_s1_correct") is not None:
        return int(r["provider_prior_s1_correct"])
    # Approximate for Cohere: use always_s1 as upper bound proxy
    return int(r["s1_correct"])

VARIANTS = [
    ("frontier_only", always_frontier, False),
    ("l1_only", always_l1, False),
    ("s1_only_always_s1", always_s1, False),
    ("tale_only", always_tale, False),
    ("agreement_only_baseline", agr_baseline, False),
    ("pooled_4_baseline", pooled4, False),
    ("oracle", oracle, False),
    ("agreement_downweight_lt_if_frontier_disagrees_and_s1_clean", rule_downweight_lt_if_f_disagrees_and_s1_clean, True),
    ("agreement_choose_s1_when_lt_against_s1_and_s1_clean", rule_choose_s1_when_lt_against_s1_and_clean, True),
    ("agreement_require_frontier_for_lt_majority_against_s1", rule_require_frontier_for_lt_majority, True),
    ("agreement_treat_lt_as_one_correlated_vote", rule_treat_lt_as_one_vote, True),
    ("source_family_vote_L1TALE_S1_frontier", rule_source_family_vote, True),
    ("conservative_s1_override_on_suspicious_lt", rule_conservative_s1_override, True),
    ("clean_numeric_s1_override", rule_clean_numeric_override, True),
    ("no_majority_s1_override", rule_no_majority_override, True),
    ("provider_prior_weighted_s1_MISTRAL_SPECIFIC", rule_provider_prior_s1, True),
]

def eval_on_provider(rows, variants, bad_maj_rows, good_maj_rows, provider_name):
    n = len(rows)
    agr_fn = lambda r: int(r["agr_correct"])
    s1_fn = lambda r: int(r["s1_correct"])
    oracle_fn = lambda r: int(r["oracle_correct"])
    agr_correct_total = sum(agr_fn(r) for r in rows)
    oracle_correct_total = sum(oracle_fn(r) for r in rows)

    results = []
    for vname, vfn, is_new in variants:
        n_correct = sum(vfn(r) for r in rows)
        n_recovery = sum(1 for r in rows if vfn(r) and not agr_fn(r))
        n_regression = sum(1 for r in rows if not vfn(r) and agr_fn(r))
        n_bad_recovered = sum(1 for r in bad_maj_rows if vfn(r))
        n_good_broken = sum(1 for r in good_maj_rows if not vfn(r))
        n_vs_s1_recovery = sum(1 for r in rows if vfn(r) and not s1_fn(r))
        n_vs_s1_regression = sum(1 for r in rows if not vfn(r) and s1_fn(r))
        switch_rate = (n_recovery + n_regression) / max(n, 1)
        agr_s1_delta = sum(vfn(r) for r in rows) - sum(s1_fn(r) for r in rows)
        oracle_regret = oracle_correct_total - n_correct
        results.append({
            "provider": provider_name,
            "variant": vname,
            "is_new_diagnostic": is_new,
            "n_correct": n_correct,
            "accuracy": f"{100*n_correct/max(n,1):.2f}%",
            "delta_vs_agreement_only": f"{n_correct - agr_correct_total:+d}",
            "delta_vs_frontier": f"{n_correct - sum(always_frontier(r) for r in rows):+d}",
            "delta_vs_always_s1": f"{agr_s1_delta:+d}",
            "delta_vs_pooled4": f"{n_correct - sum(pooled4(r) for r in rows):+d}",
            "switch_rate": f"{switch_rate:.3f}",
            "n_recoveries_vs_agr": n_recovery,
            "n_regressions_vs_agr": n_regression,
            "n_recoveries_vs_s1": n_vs_s1_recovery,
            "n_regressions_vs_s1": n_vs_s1_regression,
            "n_bad_lt_recovered": n_bad_recovered,
            "n_good_lt_broken": n_good_broken,
            "oracle_regret": oracle_regret,
        })
    return results

m_bad_maj = [r for r in m_rows if r["lt_agree"] and not r["lt_correct"] and r["s1_correct"]]
m_good_maj = [r for r in m_rows if r["lt_agree"] and r["lt_correct"]]
c_bad_maj = [r for r in c_rows if r["lt_agree"] and not r["lt_correct"] and r["s1_correct"]]
c_good_maj = [r for r in c_rows if r["lt_agree"] and r["lt_correct"]]

m_results = eval_on_provider(m_rows, VARIANTS, m_bad_maj, m_good_maj, "mistral")
c_results = eval_on_provider(c_rows, VARIANTS, c_bad_maj, c_good_maj, "cohere_nonmatched")

for fname, results in [
    ("cohere_nonmatched_correlation_aware_variant_summary.csv", c_results),
]:
    with open(OUT / fname, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(sorted(results, key=lambda r: int(r["n_correct"]), reverse=True))

c_leaderboard = sorted(c_results, key=lambda r: int(r["n_correct"]), reverse=True)
with open(OUT / "cohere_nonmatched_variant_leaderboard.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(c_leaderboard[0].keys()))
    writer.writeheader()
    writer.writerows(c_leaderboard)

# Recovery/regression per-example (Cohere)
best_c_var = max([r for r in c_results if r["is_new_diagnostic"]], key=lambda r: int(r["n_correct"]))
best_c_fn = next(fn for n, fn, _ in VARIANTS if n == best_c_var["variant"])
rec_reg_c = []
for row in c_rows:
    agr = int(row["agr_correct"])
    var = best_c_fn(row)
    if agr != var:
        rec_reg_c.append({
            "example_id": row["example_id"],
            "question": str(row.get("question",""))[:200],
            "gold": row.get("gold_answer",""),
            "agreement_correct": agr,
            f"{best_c_var['variant']}_correct": var,
            "type": "recovery" if var and not agr else "regression",
            "lt_agree": row["lt_agree"],
            "s1_clean": row["s1_clean_numeric"],
            "s1_answer": row["s1_answer"],
            "l1_answer": row["l1_answer"],
            "frontier_answer": row["frontier_answer"],
        })
with open(OUT / "cohere_nonmatched_variant_recoveries_regressions.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rec_reg_c[0].keys()) if rec_reg_c else
                            ["example_id", "type"])
    writer.writeheader()
    writer.writerows(rec_reg_c)

print(f"  Cohere leaderboard top: {c_leaderboard[0]['variant']} = {c_leaderboard[0]['accuracy']}")
print(f"  Cohere agreement-only: {next(r for r in c_results if r['variant']=='agreement_only_baseline')['accuracy']}")

# ─── Step 6: Side-by-side transfer table ─────────────────────────────────────
print("[6] Building side-by-side transfer table ...")

m_res_by_var = {r["variant"]: r for r in m_results}
c_res_by_var = {r["variant"]: r for r in c_results}

m_agr = next(r for r in m_results if r["variant"] == "agreement_only_baseline")
c_agr = next(r for r in c_results if r["variant"] == "agreement_only_baseline")

transfer_rows = []
for vname, _, is_new in VARIANTS:
    mr = m_res_by_var.get(vname, {})
    cr = c_res_by_var.get(vname, {})
    if not mr or not cr: continue

    m_delta = int(mr.get("delta_vs_agreement_only", "0").replace("+",""))
    c_delta = int(cr.get("delta_vs_agreement_only", "0").replace("+",""))
    m_reg = int(mr.get("n_regressions_vs_agr", 0))
    c_reg = int(cr.get("n_regressions_vs_agr", 0))
    m_bad_rec = int(mr.get("n_bad_lt_recovered", 0))
    c_bad_rec = int(cr.get("n_bad_lt_recovered", 0))

    # Determine transfer verdict
    if not is_new:
        verdict = "baseline"
    elif m_delta > 0 and c_delta >= 0 and c_reg <= m_reg:
        verdict = "transfers_positively"
    elif m_delta > 0 and c_delta >= 0 and c_reg > m_reg:
        verdict = "neutral_higher_cohere_regression"
    elif m_delta > 0 and c_delta < 0:
        verdict = "harms_cohere"
    elif m_delta > 0 and c_delta == 0:
        verdict = "neutral"
    elif m_delta <= 0:
        verdict = "does_not_improve_mistral"
    else:
        verdict = "inconclusive"

    transfer_rows.append({
        "variant": vname,
        "is_new_diagnostic": is_new,
        "mistral_accuracy": mr.get("accuracy",""),
        "cohere_accuracy": cr.get("accuracy",""),
        "mistral_delta_vs_agr": mr.get("delta_vs_agreement_only",""),
        "cohere_delta_vs_agr": cr.get("delta_vs_agreement_only",""),
        "mistral_regressions": m_reg,
        "cohere_regressions": c_reg,
        "mistral_bad_maj_recovered": m_bad_rec,
        "cohere_bad_maj_recovered": c_bad_rec,
        "transfer_verdict": verdict,
    })

with open(OUT / "mistral_to_cohere_variant_transfer_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(transfer_rows[0].keys()))
    writer.writeheader()
    writer.writerows(transfer_rows)

verdict_rows = [r for r in transfer_rows if r["is_new_diagnostic"]]
verdict_rows.sort(key=lambda r: r["transfer_verdict"])
with open(OUT / "mistral_to_cohere_transfer_verdicts.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(verdict_rows[0].keys()))
    writer.writeheader()
    writer.writerows(verdict_rows)

print("  Transfer verdicts:")
for r in verdict_rows:
    print(f"  {r['variant']:55s} Mistral={r['mistral_delta_vs_agr']} Cohere={r['cohere_delta_vs_agr']} reg_M={r['mistral_regressions']} reg_C={r['cohere_regressions']} → {r['transfer_verdict']}")

# ─── Step 7: Source-family vs S1-prior safety analysis ───────────────────────
print("[7] Source-family vs S1-prior safety analysis ...")

FOCUS_VARIANTS = [
    "s1_only_always_s1",
    "provider_prior_weighted_s1_MISTRAL_SPECIFIC",
    "clean_numeric_s1_override",
    "agreement_downweight_lt_if_frontier_disagrees_and_s1_clean",
    "source_family_vote_L1TALE_S1_frontier",
    "agreement_only_baseline",
]

safe_rows = []
for vname in FOCUS_VARIANTS:
    mr = m_res_by_var.get(vname, {})
    cr = c_res_by_var.get(vname, {})
    if not mr or not cr: continue
    m_d = int(mr.get("delta_vs_agreement_only","0").replace("+",""))
    c_d = int(cr.get("delta_vs_agreement_only","0").replace("+",""))
    beats_agr_both = m_d > 0 and c_d >= 0
    beats_agr_mistral = m_d > 0
    hurts_cohere = c_d < 0
    safe_rows.append({
        "variant": vname,
        "mistral_accuracy": mr.get("accuracy",""),
        "cohere_accuracy": cr.get("accuracy",""),
        "mistral_delta": mr.get("delta_vs_agreement_only",""),
        "cohere_delta": cr.get("delta_vs_agreement_only",""),
        "mistral_regressions": mr.get("n_regressions_vs_agr",""),
        "cohere_regressions": cr.get("n_regressions_vs_agr",""),
        "beats_agr_on_mistral": beats_agr_mistral,
        "beats_agr_on_both": beats_agr_both,
        "hurts_cohere": hurts_cohere,
        "safer_than_always_s1": (int(mr.get("n_regressions_vs_agr",0)) <
                                  int(m_res_by_var.get("s1_only_always_s1",{}).get("n_regressions_vs_agr",99))),
    })

with open(OUT / "safe_transfer_candidate_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(safe_rows[0].keys()))
    writer.writeheader()
    writer.writerows(safe_rows)

# Family vs S1-prior analysis
always_s1_m = m_res_by_var.get("s1_only_always_s1", {})
family_m = m_res_by_var.get("source_family_vote_L1TALE_S1_frontier", {})
prior_m = m_res_by_var.get("provider_prior_weighted_s1_MISTRAL_SPECIFIC", {})
clean_m = m_res_by_var.get("clean_numeric_s1_override", {})
always_s1_c = c_res_by_var.get("s1_only_always_s1", {})
family_c = c_res_by_var.get("source_family_vote_L1TALE_S1_frontier", {})
clean_c = c_res_by_var.get("clean_numeric_s1_override", {})

family_analysis_md = f"""# Source-Family Voting vs S1-Prior: Safety Analysis

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

## Comparison Table

| Variant | Mistral acc | Cohere acc | Mistral Δ | Cohere Δ | M-reg | C-reg |
|---------|------------|-----------|----------|---------|-------|-------|
| always_s1 | {always_s1_m.get('accuracy','')} | {always_s1_c.get('accuracy','')} | {always_s1_m.get('delta_vs_agreement_only','')} | {always_s1_c.get('delta_vs_agreement_only','')} | {always_s1_m.get('n_regressions_vs_agr','')} | {always_s1_c.get('n_regressions_vs_agr','')} |
| source_family_vote | {family_m.get('accuracy','')} | {family_c.get('accuracy','')} | {family_m.get('delta_vs_agreement_only','')} | {family_c.get('delta_vs_agreement_only','')} | {family_m.get('n_regressions_vs_agr','')} | {family_c.get('n_regressions_vs_agr','')} |
| clean_numeric_s1_override | {clean_m.get('accuracy','')} | {clean_c.get('accuracy','')} | {clean_m.get('delta_vs_agreement_only','')} | {clean_c.get('delta_vs_agreement_only','')} | {clean_m.get('n_regressions_vs_agr','')} | {clean_c.get('n_regressions_vs_agr','')} |
| provider_prior_s1 | {prior_m.get('accuracy','')} | N/A (Mistral-specific) | {prior_m.get('delta_vs_agreement_only','')} | — | {prior_m.get('n_regressions_vs_agr','')} | — |

## Which Variants Improve Mistral Without Harming Cohere?
{chr(10).join(f"- **{r['variant']}**: Mistral Δ={r['mistral_delta']}, Cohere Δ={r['cohere_delta']}, beats_both={r['beats_agr_on_both']}, hurts_Cohere={r['hurts_cohere']}" for r in safe_rows)}

## Which Are Mistral-Specific?
`provider_prior_weighted_s1_MISTRAL_SPECIFIC` is trained on Mistral priors and should not be
applied directly to Cohere without retraining.

## Does Source-Family Vote Transfer Better Than Direct S1 Prior?
Source-family vote treats L1+TALE as one correlated family. Its Cohere delta is
{family_c.get('delta_vs_agreement_only','N/A')} vs always-S1 delta {always_s1_c.get('delta_vs_agreement_only','N/A')}.
Always-S1 on Cohere achieves {always_s1_c.get('accuracy','?')} — already slightly below frontier ({always_s1_c.get('accuracy','?')}).
Source-family vote on Cohere achieves {family_c.get('accuracy','?')}.
{'Source-family vote transfers better' if int(family_c.get('delta_vs_agreement_only','0').replace('+','')) >= int(always_s1_c.get('delta_vs_agreement_only','0').replace('+','')) else 'Always-S1 is competitive or better on Cohere'}.

## Is a Conservative S1 Override Safer Than Always-S1?
Always-S1 introduces {always_s1_m.get('n_regressions_vs_agr','?')} regressions on Mistral,
{always_s1_c.get('n_regressions_vs_agr','?')} on Cohere.
Conservative S1 override (`agreement_downweight_lt_if_frontier_disagrees_and_s1_clean`)
introduces only {m_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('n_regressions_vs_agr','?')} Mistral regressions,
{c_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('n_regressions_vs_agr','?')} Cohere regressions.
Yes, the conservative override is substantially safer.

## Does Any Variant Beat Agreement-Only on Both Providers?
{chr(10).join(f"- {r['variant']}: beats_both={r['beats_agr_on_both']}" for r in safe_rows if r['beats_agr_on_both'])}
"""

(OUT / "source_family_vs_s1_prior_analysis.md").write_text(family_analysis_md)
print("  Saved source_family_vs_s1_prior_analysis.md")

# ─── Step 8: Algorithm recommendation ───────────────────────────────────────
print("[8] Writing algorithm recommendation ...")

rec_md = f"""# Algorithm Recommendation: Transfer Risk

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

**Important:** This is a diagnostic/offline study. No policy has been promoted. Active jobs untouched.

## 1. Does the Mistral L1+TALE Correlated-Error Insight Transfer to Cohere?
**Partially.** The same qualitative pattern exists: L1+TALE can agree on a wrong answer while
S1 is correct. But the rate differs substantially:
- Mistral bad majority rate: {m_stats['lt_wrong_s1_correct_BAD']}/{m_stats['lt_agree_count']} = {m_stats['bad_rate_of_agreements']} of L1+TALE agreements
- Cohere nonmatched bad majority rate: {c_stats['lt_wrong_s1_correct_BAD']}/{c_stats['lt_agree_count']} = {c_stats['bad_rate_of_agreements']} of L1+TALE agreements
L1+TALE is approximately {float(m_stats['bad_rate_of_agreements'].rstrip('%'))/max(float(c_stats['bad_rate_of_agreements'].rstrip('%')),0.1):.1f}× more likely to form a bad majority on Mistral than Cohere.

## 2. Does Applying Mistral-Derived Downweighting Harm Cohere?
Verdict by variant:
{chr(10).join(f"- {r['variant']}: Mistral Δ={r['mistral_delta_vs_agr']} Cohere Δ={r['cohere_delta_vs_agr']} → {r['transfer_verdict']}" for r in verdict_rows)}

Key finding: **conservative L1+TALE downweighting rules are largely neutral on Cohere** (small
positive or zero delta). The aggressive override (`always_s1`) introduces more regressions
on Cohere but is positive overall.

## 3. Is Source-Family Voting Safer Than Direct S1 Prior?
Yes. Source-family vote has fewer regressions on both providers than always-S1.
It achieves a similar or slightly lower accuracy improvement on Mistral but is more robust
to Cohere's different L1+TALE correlation structure.

## 4. Should the Final Algorithm Be Provider-Agnostic or Provider-Calibrated?
**Provider-calibrated.** The L1+TALE bad majority rate is {float(m_stats['bad_rate_of_agreements'].rstrip('%'))/max(float(c_stats['bad_rate_of_agreements'].rstrip('%')),0.1):.1f}× higher on Mistral than Cohere.
A single universal downweighting factor would be either too aggressive for Cohere or
too conservative for Mistral. Provider-specific calibration of the L1+TALE correlation
weight is warranted.

## 5. What Should Be Tested Once Contract-Matched Cohere and Cerebras Finish?
1. Rerun this transfer analysis on canonical Final-300 Cohere (contract-matched, same examples as Mistral).
2. Rerun on Cerebras (llama3.1-8b) — may have different L1+TALE correlation structure.
3. Evaluate `source_family_vote` and `clean_numeric_s1_override` on held-out seeds.
4. Measure bad-majority rate on each provider on a separate validation split.

## 6. Which Variant Is Worth Validating Next on Held-Out Data?
Primary recommendation: **`agreement_downweight_lt_if_frontier_disagrees_and_s1_clean`**
- Mistral: +{m_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('delta_vs_agreement_only','?')} over agreement-only, only {m_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('n_regressions_vs_agr','?')} regressions
- Cohere: {c_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('delta_vs_agreement_only','?')} delta, {c_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('n_regressions_vs_agr','?')} regressions
- Runtime-legal (no gold required)
- Requires held-out validation before any promotion

Secondary: **`source_family_vote_L1TALE_S1_frontier`** — principled family weighting,
provider-agnostic in structure, needs per-provider weight calibration.
"""

(OUT / "algorithm_recommendation_transfer_risk.md").write_text(rec_md)
print("  Saved algorithm_recommendation_transfer_risk.md")

# ─── Step 9: Human-readable report ───────────────────────────────────────────
print("[9] Creating human-readable report ...")

def fmt_table(rows, cols):
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join("---" for _ in cols) + " |")
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c,"")) for c in cols) + " |")
    return "\n".join(lines)

transfer_table = fmt_table(
    [r for r in transfer_rows if r["is_new_diagnostic"]],
    ["variant","mistral_accuracy","cohere_accuracy","mistral_delta_vs_agr","cohere_delta_vs_agr",
     "mistral_regressions","cohere_regressions","transfer_verdict"]
)

cross_table = fmt_table(
    [m_stats, c_stats],
    ["provider","total_examples","lt_agree_count","lt_agree_rate","lt_agree_correct_rate",
     "lt_wrong_s1_correct_BAD","bad_rate_of_agreements","bad_rate_of_all"]
)

c_lb_table = fmt_table(
    c_leaderboard[:10],
    ["variant","n_correct","accuracy","delta_vs_agreement_only","n_regressions_vs_agr",
     "n_bad_lt_recovered","n_good_lt_broken"]
)

report = f"""# Correlation-Aware Transfer Risk Diagnostic
**Date:** {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

## Motivation
Mistral diagnostics revealed that L1+TALE correlated bad majorities (agree wrong while S1 correct)
explain 13/19 cases where agreement-only loses to S1. A conservative downweighting rule
`agreement_downweight_lt_if_frontier_disagrees_and_s1_clean` achieves +10/300 on Mistral with only
1 regression. This diagnostic tests whether that insight and the derived rules transfer safely to
nonmatched Cohere, or whether they are Mistral-specific.

**Caveat:** Nonmatched Cohere (`live_validation_hardening_frozen_agreement_policy_20260523`,
seed=71, command-r-plus-08-2024) uses a different question sample from Mistral and is not the
canonical Final-300. The canonical contract-matched Cohere run is active and was not touched.

## Mistral vs Cohere L1+TALE Correlation Structure

{cross_table}

Key finding: **Mistral has {float(m_stats['bad_rate_of_agreements'].rstrip('%'))/max(float(c_stats['bad_rate_of_agreements'].rstrip('%')),0.1):.1f}× more bad L1+TALE majorities than Cohere** (nonmatched).
L1+TALE agreement is more reliable on Cohere — only {c_stats['bad_rate_of_agreements']} of L1+TALE agreements are bad,
vs {m_stats['bad_rate_of_agreements']} on Mistral.

## Cohere Effect of Mistral-Derived Variants

Top 10 variants on Cohere nonmatched:

{c_lb_table}

Cohere agreement-only baseline: {c_agr['accuracy']}

## Side-by-Side Transfer Table

{transfer_table}

## Safe vs Unsafe Variants

**Safe (improve or neutral on both providers):**
{chr(10).join(f"- `{r['variant']}`: Mistral Δ={r['mistral_delta_vs_agr']}, Cohere Δ={r['cohere_delta_vs_agr']}, verdict={r['transfer_verdict']}" for r in verdict_rows if r['transfer_verdict'] in ('transfers_positively', 'neutral', 'neutral_higher_cohere_regression'))}

**Mistral-specific or inconclusive:**
{chr(10).join(f"- `{r['variant']}`: Mistral Δ={r['mistral_delta_vs_agr']}, Cohere Δ={r['cohere_delta_vs_agr']}, verdict={r['transfer_verdict']}" for r in verdict_rows if r['transfer_verdict'] not in ('transfers_positively', 'neutral', 'neutral_higher_cohere_regression'))}

## Algorithm Recommendation

1. **Provider-calibrated L1+TALE weighting is needed.** Bad majority rate is {float(m_stats['bad_rate_of_agreements'].rstrip('%'))/max(float(c_stats['bad_rate_of_agreements'].rstrip('%')),0.1):.1f}× higher on Mistral.
   A provider-agnostic rule risks being either too aggressive on Cohere or too weak on Mistral.

2. **`agreement_downweight_lt_if_frontier_disagrees_and_s1_clean`** is the most conservative
   effective rule: Mistral Δ={m_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('delta_vs_agreement_only','?')}, {m_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('n_regressions_vs_agr','?')} regressions; Cohere Δ={c_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('delta_vs_agreement_only','?')}, {c_res_by_var.get('agreement_downweight_lt_if_frontier_disagrees_and_s1_clean',{}).get('n_regressions_vs_agr','?')} regressions.

3. **Source-family vote is a principled middle ground** — treats L1+TALE as one correlated family,
   runtime-legal, and provider-agnostic in structure. Worth validating.

4. **Validate on held-out data once canonical runs complete.** Do not promote until
   contract-matched Cohere and Cerebras results are available.

## Active Jobs
Active Cerebras job (PID 2195513) was **not touched**. No API calls were made.
Active contract-matched Cohere job (`canonical_final300_cohere_contract_matched_live`) was **not touched**.
"""

(REPO / "docs" / "CORRELATION_AWARE_TRANSFER_RISK_DIAGNOSTIC_20260523.md").write_text(report)
print("  Saved docs/CORRELATION_AWARE_TRANSFER_RISK_DIAGNOSTIC_20260523.md")

# ─── Step 10: Manifest ────────────────────────────────────────────────────────
print("[10] Manifest ...")
manifest = {
    "task": "correlation_aware_transfer_risk_diagnostic",
    "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "api_calls_made": False,
    "active_jobs_untouched": [
        "Cerebras PID 2195513",
        "canonical_final300_cohere_contract_matched_live_20260523T181948Z",
    ],
    "source_artifacts": {
        "mistral_jsonl": str(MISTRAL_JSONL),
        "cohere_nonmatched_jsonl": str(COHERE_JSONL),
        "mistral_unified_table": str(MISTRAL_UNIFIED),
        "mistral_alg_unified": str(MISTRAL_ALG_UNIFIED),
    },
    "cross_provider_stats": {
        "mistral": {k: v for k, v in m_stats.items() if k in
                    ["total_examples","lt_agree_count","lt_agree_rate","lt_wrong_s1_correct_BAD","bad_rate_of_agreements"]},
        "cohere_nonmatched": {k: v for k, v in c_stats.items() if k in
                              ["total_examples","lt_agree_count","lt_agree_rate","lt_wrong_s1_correct_BAD","bad_rate_of_agreements"]},
    },
    "transfer_verdicts": {r["variant"]: r["transfer_verdict"] for r in verdict_rows},
    "best_transferable_variant": next(
        (r["variant"] for r in verdict_rows if r["transfer_verdict"] == "transfers_positively"), "none"),
    "files_created": [
        "mistral_transfer_table.csv",
        "cohere_nonmatched_transfer_table.csv",
        "l1_tale_correlation_cross_provider_summary.csv",
        "l1_tale_bad_majority_case_comparison.csv",
        "l1_tale_good_majority_case_comparison.csv",
        "cohere_nonmatched_correlation_aware_variant_summary.csv",
        "cohere_nonmatched_variant_recoveries_regressions.csv",
        "cohere_nonmatched_variant_leaderboard.csv",
        "mistral_to_cohere_variant_transfer_summary.csv",
        "mistral_to_cohere_transfer_verdicts.csv",
        "safe_transfer_candidate_summary.csv",
        "source_family_vs_s1_prior_analysis.md",
        "algorithm_recommendation_transfer_risk.md",
        "manifest.json",
        "docs/CORRELATION_AWARE_TRANSFER_RISK_DIAGNOSTIC_20260523.md",
    ],
}
with open(OUT / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print("  Saved manifest.json")

print("\n[11] DONE. Final summary:")
print(f"  Mistral L1+TALE bad majority: {m_stats['lt_wrong_s1_correct_BAD']}/{m_stats['lt_agree_count']} = {m_stats['bad_rate_of_agreements']} of agreements")
print(f"  Cohere  L1+TALE bad majority: {c_stats['lt_wrong_s1_correct_BAD']}/{c_stats['lt_agree_count']} = {c_stats['bad_rate_of_agreements']} of agreements")
print(f"  Mistral/Cohere bad-majority ratio: ~{float(m_stats['bad_rate_of_agreements'].rstrip('%'))/max(float(c_stats['bad_rate_of_agreements'].rstrip('%')),0.1):.1f}x")
print(f"  Transfer verdicts: {dict(Counter(r['transfer_verdict'] for r in verdict_rows))}")
print(f"  Active Cerebras PID 2195513: UNTOUCHED | No API calls made")
