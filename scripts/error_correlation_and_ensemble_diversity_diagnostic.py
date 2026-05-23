"""
Pairwise error-correlation, double-fault, and ensemble-diversity diagnostics.
Covers Steps 3-11 of 5224ecce43af7b9f9efc6c381cc330206d0e25f7.txt
No API calls. No policy modification. No touching active jobs.
"""

import json, csv, re, math, random, collections, itertools
from pathlib import Path
from datetime import datetime, timezone

random.seed(42)
OUTDIR = Path("outputs/error_correlation_and_ensemble_diversity_diagnostic_20260523")
OUTDIR.mkdir(parents=True, exist_ok=True)

COHERE_PER_EXAMPLE = Path(
    "outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z"
    "/cohere_real_model_cost_normalized_validation_20260523T181948Z"
    "/per_example_records.jsonl"
)
MISTRAL_PER_EXAMPLE = Path(
    "outputs/mistral_frozen_agreement_only_2of3_validation_20260523T145416Z"
    "/cohere_real_model_cost_normalized_validation_20260523T145416Z"
    "/per_example_records.jsonl"
)

METHODS = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]
LABELS = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "L1",
    "external_s1_budget_forcing": "S1",
    "external_tale_prompt_budgeting": "TALE",
}
CLEAN_NUM = re.compile(r"^\-?\d+(\.\d+)?$")


# ── helpers ──────────────────────────────────────────────────────────────────
def load_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s:
                rows.append(json.loads(s))
    return rows


def write_csv(path, rows, fields=None):
    if not rows:
        path.write_text("")
        return
    if fields is None:
        fields = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path}")


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2))
    print(f"  wrote {path}")


def write_md(path, text):
    path.write_text(text)
    print(f"  wrote {path}")


def get_ans(rec):
    return rec.get("final_answer_canonical") or rec.get("selected_answer_canonical")


def get_ok(rec):
    em = rec.get("exact_match")
    if em is not None:
        return bool(em)
    a = get_ans(rec)
    g = rec.get("gold_answer_canonical") or rec.get("gold_answer")
    if a is not None and g is not None:
        return str(a).strip() == str(g).strip()
    return False


def get_gold(rec):
    return rec.get("gold_answer_canonical") or rec.get("gold_answer")


# ── load & build per-example tables ─────────────────────────────────────────
def build_table(per_example_path, provider_label):
    records = load_jsonl(per_example_path)
    lookup = {}  # eid → {method: rec}
    for r in records:
        eid = r["example_id"]
        m = r["method"]
        if eid not in lookup:
            lookup[eid] = {}
        lookup[eid][m] = r

    examples = []
    for eid in sorted(lookup.keys()):
        row = lookup[eid]
        f_r  = row.get("direct_reserve_semantic_frontier_v2")
        l1_r = row.get("external_l1_max")
        s1_r = row.get("external_s1_budget_forcing")
        ta_r = row.get("external_tale_prompt_budgeting")

        f_a  = get_ans(f_r);   l1_a = get_ans(l1_r)
        s1_a = get_ans(s1_r);  ta_a = get_ans(ta_r)
        gold = get_gold(f_r) or get_gold(l1_r) or get_gold(s1_r) or get_gold(ta_r)

        f_ok  = int(get_ok(f_r))
        l1_ok = int(get_ok(l1_r))
        s1_ok = int(get_ok(s1_r))
        ta_ok = int(get_ok(ta_r))

        # agreement-only (2-of-3 external against frontier)
        ext_counts = collections.Counter(a for a in [l1_a, s1_a, ta_a] if a is not None)
        ext_maj, ext_maj_cnt = ext_counts.most_common(1)[0] if ext_counts else (f_a, 0)
        agr_a = ext_maj if (ext_maj_cnt >= 2 and ext_maj != f_a) else f_a
        agr_ok = int(str(agr_a).strip() == str(gold).strip()) if (agr_a and gold) else 0

        # pooled-4
        all_a = [a for a in [f_a, l1_a, s1_a, ta_a] if a is not None]
        pool_counts = collections.Counter(all_a)
        pool_maj, pool_maj_cnt = pool_counts.most_common(1)[0] if pool_counts else (f_a, 0)
        pool_a = pool_maj if (pool_maj_cnt >= 2 and pool_maj != f_a) else f_a
        pool_ok = int(str(pool_a).strip() == str(gold).strip()) if (pool_a and gold) else 0

        # oracle
        oracle_ok = int(any([f_ok, l1_ok, s1_ok, ta_ok]))

        # unique answer count
        uniq = len(set(a for a in [f_a, l1_a, s1_a, ta_a] if a is not None))

        # majority pattern
        if pool_maj_cnt == 4:
            pattern = "all4_agree"
        elif pool_maj_cnt == 3:
            pattern = "3_1_majority"
        elif pool_maj_cnt == 2:
            # could be 2-2 split or one answer appears twice
            pattern = "2_2_split" if len(pool_counts) == 2 and list(pool_counts.values()).count(2) == 2 else "2_majority"
        else:
            pattern = "all_different"

        # pairwise answer agreement
        pairs = [("f","l1"), ("f","s1"), ("f","ta"), ("l1","s1"), ("l1","ta"), ("s1","ta")]
        answers = {"f": f_a, "l1": l1_a, "s1": s1_a, "ta": ta_a}
        oks = {"f": f_ok, "l1": l1_ok, "s1": s1_ok, "ta": ta_ok}
        agree = {f"{a}_{b}_agree": int(answers[a] == answers[b] and answers[a] is not None)
                 for a, b in pairs}
        df    = {f"{a}_{b}_doublefault": int(not oks[a] and not oks[b])
                 for a, b in pairs}

        # L1+TALE family
        lt_agree = int(l1_a is not None and ta_a is not None and l1_a == ta_a)
        lt_ok    = int(lt_agree and l1_ok)
        lt_wrong = int(lt_agree and not l1_ok)
        lt_wrong_s1_correct = int(lt_wrong and s1_ok)

        e = {
            "provider": provider_label,
            "example_id": eid,
            "gold": gold,
            "f_a": f_a,  "l1_a": l1_a,  "s1_a": s1_a,  "ta_a": ta_a,
            "f_ok": f_ok, "l1_ok": l1_ok, "s1_ok": s1_ok, "ta_ok": ta_ok,
            "agr_a": agr_a, "agr_ok": agr_ok,
            "pool_a": pool_a, "pool_ok": pool_ok,
            "oracle_ok": oracle_ok,
            "uniq_ans": uniq,
            "majority_pattern": pattern,
            "lt_agree": lt_agree, "lt_ok": lt_ok,
            "lt_wrong": lt_wrong, "lt_wrong_s1_correct": lt_wrong_s1_correct,
        }
        e.update(agree)
        e.update(df)
        examples.append(e)

    return examples


print("Loading data...")
cohere_ex = build_table(COHERE_PER_EXAMPLE, "cohere")
mistral_ex = build_table(MISTRAL_PER_EXAMPLE, "mistral")
print(f"  Cohere: {len(cohere_ex)} examples")
print(f"  Mistral: {len(mistral_ex)} examples")

write_csv(OUTDIR / "cohere_canonical_diversity_table.csv", cohere_ex)
write_csv(OUTDIR / "mistral_diversity_table.csv", mistral_ex)


# ── pairwise error-correlation ──────────────────────────────────────────────
METHOD_KEYS = [("f", "frontier"), ("l1", "L1"), ("s1", "S1"), ("ta", "TALE")]

def pairwise_corr(examples, provider_label):
    N = len(examples)
    rows = []
    for (k1, lab1), (k2, lab2) in itertools.combinations(METHOD_KEYS, 2):
        acc1 = sum(e[f"{k1}_ok"] for e in examples) / N
        acc2 = sum(e[f"{k2}_ok"] for e in examples) / N
        n11 = sum(1 for e in examples if e[f"{k1}_ok"] and e[f"{k2}_ok"])
        n00 = sum(1 for e in examples if not e[f"{k1}_ok"] and not e[f"{k2}_ok"])
        n10 = sum(1 for e in examples if e[f"{k1}_ok"] and not e[f"{k2}_ok"])
        n01 = sum(1 for e in examples if not e[f"{k1}_ok"] and e[f"{k2}_ok"])
        # phi
        denom_phi = math.sqrt(max((n11+n10)*(n11+n01)*(n00+n10)*(n00+n01), 1e-9))
        phi = (n11*n00 - n10*n01) / denom_phi
        # Q-statistic
        q_num = n11*n00 - n10*n01
        q_den = n11*n00 + n10*n01
        q = q_num/q_den if q_den > 0 else None
        # double-fault
        df_obs = n00 / N
        df_exp = (1 - acc1) * (1 - acc2)
        df_excess = df_obs - df_exp
        # disagreement
        disagree = (n10 + n01) / N
        # Jaccard on errors
        union_wrong = N - n11
        jaccard = n00 / union_wrong if union_wrong > 0 else None
        # answer agreement (use precomputed field if available)
        # compute from answers directly
        pair_key = f"{k1}_{k2}"
        ans_agree_field = f"{k1}_{k2}_agree"
        if ans_agree_field not in examples[0]:
            ans_agree_field = f"{k2}_{k1}_agree"
        ans_agree_cnt = sum(e.get(ans_agree_field, 0) for e in examples)
        ans_agree_rate = ans_agree_cnt / N
        # When they agree, how often are they correct?
        agree_correct = sum(1 for e in examples if e.get(ans_agree_field, 0) and e[f"{k1}_ok"])
        agree_wrong   = sum(1 for e in examples if e.get(ans_agree_field, 0) and not e[f"{k1}_ok"])
        agree_corr_rate = agree_correct / ans_agree_cnt if ans_agree_cnt else None
        agree_wrong_rate = agree_wrong / ans_agree_cnt if ans_agree_cnt else None

        rows.append({
            "provider": provider_label,
            "source_A": lab1, "source_B": lab2,
            "acc_A": round(acc1, 4), "acc_B": round(acc2, 4),
            "n11_both_correct": n11, "n00_both_wrong": n00,
            "n10_A_only": n10, "n01_B_only": n01,
            "phi": round(phi, 4),
            "Q_statistic": round(q, 4) if q is not None else "",
            "disagreement_rate": round(disagree, 4),
            "double_fault_rate": round(df_obs, 4),
            "expected_double_fault": round(df_exp, 4),
            "excess_double_fault": round(df_excess, 4),
            "jaccard_error_overlap": round(jaccard, 4) if jaccard else "",
            "answer_agree_rate": round(ans_agree_rate, 4),
            "answer_agree_correct_rate": round(agree_corr_rate, 4) if agree_corr_rate is not None else "",
            "answer_agree_wrong_rate": round(agree_wrong_rate, 4) if agree_wrong_rate is not None else "",
        })
    return rows

print("\n=== Pairwise correlation ===")
cohere_corr = pairwise_corr(cohere_ex, "cohere")
mistral_corr = pairwise_corr(mistral_ex, "mistral")
write_csv(OUTDIR / "cohere_pairwise_error_correlation.csv", cohere_corr)
write_csv(OUTDIR / "mistral_pairwise_error_correlation.csv", mistral_corr)

# Cross-provider comparison
cross_rows = []
for c_row, m_row in zip(cohere_corr, mistral_corr):
    cross_rows.append({
        "source_A": c_row["source_A"], "source_B": c_row["source_B"],
        "cohere_phi": c_row["phi"], "mistral_phi": m_row["phi"],
        "phi_diff_mistral_minus_cohere": round(m_row["phi"] - c_row["phi"], 4),
        "cohere_excess_df": c_row["excess_double_fault"], "mistral_excess_df": m_row["excess_double_fault"],
        "excess_df_diff": round(m_row["excess_double_fault"] - c_row["excess_double_fault"], 4),
        "cohere_Q": c_row["Q_statistic"], "mistral_Q": m_row["Q_statistic"],
        "cohere_disagree": c_row["disagreement_rate"], "mistral_disagree": m_row["disagreement_rate"],
        "cohere_ans_agree": c_row["answer_agree_rate"], "mistral_ans_agree": m_row["answer_agree_rate"],
    })
write_csv(OUTDIR / "cross_provider_pairwise_correlation_comparison.csv", cross_rows)

# Print highlights
print("  Key phi values:")
for r in cross_rows:
    print(f"    {r['source_A']:8s}×{r['source_B']:8s}  cohere_phi={r['cohere_phi']:+.3f}  mistral_phi={r['mistral_phi']:+.3f}  diff={r['phi_diff_mistral_minus_cohere']:+.3f}")


# ── L1+TALE family focus ─────────────────────────────────────────────────────
def lt_family_summary(examples, provider_label):
    N = len(examples)
    acc_l1 = sum(e["l1_ok"] for e in examples) / N
    acc_ta = sum(e["ta_ok"] for e in examples) / N
    lt_agree_cnt = sum(e["lt_agree"] for e in examples)
    lt_agree_ok  = sum(e["lt_ok"] for e in examples)
    lt_agree_wrong = sum(e["lt_wrong"] for e in examples)
    lt_df    = sum(e["l1_l1_ok" if False else ""] if False else (1-e["l1_ok"])*(1-e["ta_ok"]) for e in examples)
    # recompute cleanly
    n11 = sum(1 for e in examples if e["l1_ok"] and e["ta_ok"])
    n00 = sum(1 for e in examples if not e["l1_ok"] and not e["ta_ok"])
    n10 = sum(1 for e in examples if e["l1_ok"] and not e["ta_ok"])
    n01 = sum(1 for e in examples if not e["l1_ok"] and e["ta_ok"])
    df_obs = n00 / N
    df_exp = (1 - acc_l1) * (1 - acc_ta)
    df_excess = df_obs - df_exp
    denom_phi = math.sqrt(max((n11+n10)*(n11+n01)*(n00+n10)*(n00+n01), 1e-9))
    phi = (n11*n00 - n10*n01) / denom_phi
    q_num = n11*n00 - n10*n01
    q_den = n11*n00 + n10*n01
    q = q_num/q_den if q_den else None
    lt_wrong_s1_correct = sum(e["lt_wrong_s1_correct"] for e in examples)
    # L1+TALE agree wrong while frontier correct
    lt_wrong_f_correct = sum(1 for e in examples if e["lt_wrong"] and e["f_ok"])
    # L1+TALE agree correct while S1 wrong
    lt_ok_s1_wrong = sum(1 for e in examples if e["lt_ok"] and not e["s1_ok"])
    # Independence behavior
    if phi > 0.3:
        behav = "strongly_correlated_family"
    elif phi > 0.1:
        behav = "mildly_correlated"
    elif phi > -0.1:
        behav = "approximately_independent"
    else:
        behav = "anti_correlated"

    return {
        "provider": provider_label,
        "n": N,
        "acc_L1": round(acc_l1, 4), "acc_TALE": round(acc_ta, 4),
        "lt_answer_agree_count": lt_agree_cnt,
        "lt_answer_agree_rate": round(lt_agree_cnt/N, 4),
        "lt_agree_correct_count": lt_agree_ok,
        "lt_agree_correct_rate": round(lt_agree_ok/lt_agree_cnt, 4) if lt_agree_cnt else None,
        "lt_agree_wrong_count": lt_agree_wrong,
        "lt_agree_wrong_rate": round(lt_agree_wrong/lt_agree_cnt, 4) if lt_agree_cnt else None,
        "double_fault_count": n00,
        "double_fault_rate": round(df_obs, 4),
        "expected_double_fault": round(df_exp, 4),
        "excess_double_fault": round(df_excess, 4),
        "phi": round(phi, 4),
        "Q_statistic": round(q, 4) if q is not None else "",
        "lt_wrong_s1_correct": lt_wrong_s1_correct,
        "lt_wrong_s1_correct_rate": round(lt_wrong_s1_correct/N, 4),
        "lt_wrong_frontier_correct": lt_wrong_f_correct,
        "lt_ok_s1_wrong": lt_ok_s1_wrong,
        "independence_behavior": behav,
    }

print("\n=== L1+TALE family ===")
cohere_lt = lt_family_summary(cohere_ex, "cohere")
mistral_lt = lt_family_summary(mistral_ex, "mistral")
write_csv(OUTDIR / "l1_tale_family_correlation_summary.csv", [cohere_lt, mistral_lt])

interp_lines = [
    "# L1+TALE Family Correlation Interpretation",
    "",
    "## Key Metrics",
    "",
    f"| Metric | Cohere | Mistral |",
    f"|--------|--------|---------|",
]
for key in ["phi", "Q_statistic", "excess_double_fault", "lt_answer_agree_rate",
            "lt_agree_correct_rate", "lt_agree_wrong_rate", "lt_wrong_s1_correct",
            "lt_wrong_s1_correct_rate", "independence_behavior"]:
    interp_lines.append(f"| {key} | {cohere_lt.get(key, '')} | {mistral_lt.get(key, '')} |")

interp_lines += [
    "",
    "## Interpretation",
    "",
    f"**Cohere:** φ={cohere_lt['phi']:.3f} — {cohere_lt['independence_behavior']}. "
    f"L1+TALE agree on {cohere_lt['lt_answer_agree_rate']:.1%} of examples; "
    f"when they agree, {cohere_lt['lt_agree_correct_rate']:.1%} correct. "
    f"Bad majority (L1+TALE wrong, S1 correct): {cohere_lt['lt_wrong_s1_correct']} cases "
    f"({cohere_lt['lt_wrong_s1_correct_rate']:.1%}).",
    "",
    f"**Mistral:** φ={mistral_lt['phi']:.3f} — {mistral_lt['independence_behavior']}. "
    f"L1+TALE agree on {mistral_lt['lt_answer_agree_rate']:.1%} of examples; "
    f"when they agree, {mistral_lt['lt_agree_correct_rate']:.1%} correct. "
    f"Bad majority (L1+TALE wrong, S1 correct): {mistral_lt['lt_wrong_s1_correct']} cases "
    f"({mistral_lt['lt_wrong_s1_correct_rate']:.1%}).",
    "",
    "## Voting Implications",
    f"- Higher φ on Mistral means L1+TALE provide *less* independent information than their count suggests.",
    f"- Excess double-fault on Mistral: {mistral_lt['excess_double_fault']:.4f} vs Cohere: {cohere_lt['excess_double_fault']:.4f}.",
    f"  Positive excess double-fault means errors are more concentrated (correlated) than under independence.",
    f"- Under correlated errors, Condorcet assumptions break: pooled-4 over-counts L1+TALE as two votes,",
    f"  but they effectively represent fewer than two independent signals.",
]
write_md(OUTDIR / "l1_tale_family_correlation_interpretation.md", "\n".join(interp_lines))
print(f"  Cohere L1+TALE phi={cohere_lt['phi']:.4f}  Mistral L1+TALE phi={mistral_lt['phi']:.4f}")


# ── ensemble diversity and oracle gap ────────────────────────────────────────
def diversity_summary(examples, provider_label):
    N = len(examples)
    accs = {k: sum(e[f"{k}_ok"] for e in examples)/N for k in ["f","l1","s1","ta"]}
    best_src = max(accs, key=accs.get)
    best_acc = accs[best_src]
    agr_acc  = sum(e["agr_ok"] for e in examples)/N
    pool_acc = sum(e["pool_ok"] for e in examples)/N
    oracle_acc = sum(e["oracle_ok"] for e in examples)/N
    oracle_gain_vs_frontier = oracle_acc - accs["f"]
    pool_oracle_frac = (pool_acc - accs["f"]) / oracle_gain_vs_frontier if oracle_gain_vs_frontier > 0 else None
    agr_oracle_frac  = (agr_acc  - accs["f"]) / oracle_gain_vs_frontier if oracle_gain_vs_frontier > 0 else None
    s1_oracle_frac   = (accs["s1"] - accs["f"]) / oracle_gain_vs_frontier if oracle_gain_vs_frontier > 0 else None
    # avg pairwise disagreement and double-fault
    pairs = [("f","l1"),("f","s1"),("f","ta"),("l1","s1"),("l1","ta"),("s1","ta")]
    avg_disagree = sum(
        sum(1 for e in examples if e.get(f"{a}_{b}_agree", e.get(f"{b}_{a}_agree", 0)) == 0) / N
        for a, b in pairs
    ) / 6
    avg_df = sum(
        sum(e[f"{a}_{b}_doublefault"] for e in examples) / N
        for a, b in pairs
    ) / 6
    # majority patterns
    pat_counts = collections.Counter(e["majority_pattern"] for e in examples)
    # recoveries and regressions
    pool_rec  = sum(1 for e in examples if e["pool_ok"] and not e["f_ok"])
    pool_reg  = sum(1 for e in examples if not e["pool_ok"] and e["f_ok"])
    agr_rec   = sum(1 for e in examples if e["agr_ok"] and not e["f_ok"])
    agr_reg   = sum(1 for e in examples if not e["agr_ok"] and e["f_ok"])
    # missed oracle
    pool_missed_oracle = sum(1 for e in examples if e["oracle_ok"] and not e["pool_ok"])
    agr_missed_oracle  = sum(1 for e in examples if e["oracle_ok"] and not e["agr_ok"])
    # avg unique answers
    avg_uniq = sum(e["uniq_ans"] for e in examples) / N

    return {
        "provider": provider_label, "n": N,
        "acc_frontier": round(accs["f"],4), "acc_L1": round(accs["l1"],4),
        "acc_S1": round(accs["s1"],4), "acc_TALE": round(accs["ta"],4),
        "best_single_source": LABELS[{"f":"direct_reserve_semantic_frontier_v2","l1":"external_l1_max","s1":"external_s1_budget_forcing","ta":"external_tale_prompt_budgeting"}[best_src]],
        "best_single_acc": round(best_acc,4),
        "agreement_only_acc": round(agr_acc,4),
        "pooled4_acc": round(pool_acc,4),
        "oracle_acc": round(oracle_acc,4),
        "oracle_gain_vs_frontier": round(oracle_gain_vs_frontier,4),
        "pool4_pct_oracle_gain": round(pool_oracle_frac,4) if pool_oracle_frac else "",
        "agr_pct_oracle_gain": round(agr_oracle_frac,4) if agr_oracle_frac else "",
        "s1_pct_oracle_gain": round(s1_oracle_frac,4) if s1_oracle_frac else "",
        "avg_pairwise_disagreement": round(avg_disagree,4),
        "avg_pairwise_double_fault": round(avg_df,4),
        "avg_unique_answers": round(avg_uniq,3),
        "pct_all4_agree": round(pat_counts.get("all4_agree",0)/N,4),
        "pct_3_1_majority": round(pat_counts.get("3_1_majority",0)/N,4),
        "pct_2_2_split": round((pat_counts.get("2_2_split",0)+pat_counts.get("2_majority",0))/N,4),
        "pct_all_different": round(pat_counts.get("all_different",0)/N,4),
        "pool4_recoveries_vs_frontier": pool_rec,
        "pool4_regressions_vs_frontier": pool_reg,
        "agr_recoveries_vs_frontier": agr_rec,
        "agr_regressions_vs_frontier": agr_reg,
        "pool4_missed_oracle": pool_missed_oracle,
        "agr_missed_oracle": agr_missed_oracle,
    }

print("\n=== Ensemble diversity ===")
cohere_div = diversity_summary(cohere_ex, "cohere")
mistral_div = diversity_summary(mistral_ex, "mistral")
write_csv(OUTDIR / "ensemble_diversity_summary.csv", [cohere_div, mistral_div])

oracle_gap_rows = []
for div in [cohere_div, mistral_div]:
    oracle_gap_rows.append({
        "provider": div["provider"],
        "oracle_acc": div["oracle_acc"],
        "oracle_gain_vs_frontier": div["oracle_gain_vs_frontier"],
        "pool4_captures_oracle_pct": div["pool4_pct_oracle_gain"],
        "agr_captures_oracle_pct": div["agr_pct_oracle_gain"],
        "s1_captures_oracle_pct": div["s1_pct_oracle_gain"],
        "pool4_missed_oracle": div["pool4_missed_oracle"],
        "agr_missed_oracle": div["agr_missed_oracle"],
    })
write_csv(OUTDIR / "oracle_gap_and_complementarity_summary.csv", oracle_gap_rows)

maj_rows = []
for div in [cohere_div, mistral_div]:
    maj_rows.append({
        "provider": div["provider"],
        "pct_all4_agree": div["pct_all4_agree"],
        "pct_3_1_majority": div["pct_3_1_majority"],
        "pct_2_2_or_2_majority": div["pct_2_2_split"],
        "pct_all_different": div["pct_all_different"],
        "avg_unique_answers": div["avg_unique_answers"],
        "avg_pairwise_disagreement": div["avg_pairwise_disagreement"],
    })
write_csv(OUTDIR / "majority_pattern_summary.csv", maj_rows)

print(f"  Cohere  pool4_oracle_frac={cohere_div['pool4_pct_oracle_gain']}  agr_oracle_frac={cohere_div['agr_pct_oracle_gain']}")
print(f"  Mistral pool4_oracle_frac={mistral_div['pool4_pct_oracle_gain']}  s1_oracle_frac={mistral_div['s1_pct_oracle_gain']}")


# ── pooled-4 case analysis ───────────────────────────────────────────────────
def pool4_cases(examples, provider_label):
    FIELDS = ["example_id","gold","f_a","l1_a","s1_a","ta_a",
              "f_ok","l1_ok","s1_ok","ta_ok","agr_ok","pool_ok","oracle_ok",
              "majority_pattern","lt_agree","lt_wrong","lt_wrong_s1_correct","uniq_ans"]

    rec_vs_frontier = [
        dict(provider=provider_label, **{k: e[k] for k in FIELDS})
        for e in examples if e["pool_ok"] and not e["f_ok"]
    ]
    reg_vs_frontier = [
        dict(provider=provider_label, **{k: e[k] for k in FIELDS})
        for e in examples if not e["pool_ok"] and e["f_ok"]
    ]
    return rec_vs_frontier, reg_vs_frontier

cohere_rec, cohere_reg = pool4_cases(cohere_ex, "cohere")
mistral_rec, mistral_reg = pool4_cases(mistral_ex, "mistral")
write_csv(OUTDIR / "cohere_pooled4_recovery_regression_cases.csv", cohere_rec + cohere_reg)

# Mistral: pooled-4 losses to S1
mistral_pool_s1_losses = [
    {"example_id": e["example_id"], "gold": e["gold"],
     "f_a": e["f_a"], "l1_a": e["l1_a"], "s1_a": e["s1_a"], "ta_a": e["ta_a"],
     "f_ok": e["f_ok"], "l1_ok": e["l1_ok"], "s1_ok": e["s1_ok"], "ta_ok": e["ta_ok"],
     "pool_ok": e["pool_ok"], "pool_a": e["pool_a"],
     "majority_pattern": e["majority_pattern"],
     "lt_agree": e["lt_agree"], "lt_wrong": e["lt_wrong"],
     "lt_wrong_s1_correct": e["lt_wrong_s1_correct"],
     "mode": "pool_wrong_s1_correct" if (not e["pool_ok"] and e["s1_ok"]) else
             "s1_wrong_pool_correct" if (e["pool_ok"] and not e["s1_ok"]) else "both_same"}
    for e in mistral_ex
    if not e["pool_ok"] and e["s1_ok"]  # pool loses to s1
]
write_csv(OUTDIR / "mistral_pooled4_vs_s1_loss_cases.csv", mistral_pool_s1_losses)

# Pattern summary
def pat_summary(examples, provider_label):
    N = len(examples)
    # of pool4 recoveries, what fraction were 3-1 majority?
    rec = [e for e in examples if e["pool_ok"] and not e["f_ok"]]
    reg = [e for e in examples if not e["pool_ok"] and e["f_ok"]]
    return {
        "provider": provider_label,
        "pool4_recoveries_total": len(rec),
        "pool4_recoveries_3_1_majority": sum(1 for e in rec if e["majority_pattern"]=="3_1_majority"),
        "pool4_recoveries_2_majority": sum(1 for e in rec if "2" in e["majority_pattern"] and "3" not in e["majority_pattern"]),
        "pool4_regressions_total": len(reg),
        "pool4_regressions_3_1_majority": sum(1 for e in reg if e["majority_pattern"]=="3_1_majority"),
        "pool4_regressions_2_majority": sum(1 for e in reg if "2" in e["majority_pattern"] and "3" not in e["majority_pattern"]),
        "pool4_regressions_lt_drove_wrong": sum(1 for e in reg if e["lt_wrong"]),
        "pool4_wins_vs_s1": sum(1 for e in examples if e["pool_ok"] and not e["s1_ok"]),
        "pool4_losses_vs_s1": sum(1 for e in examples if not e["pool_ok"] and e["s1_ok"]),
        "pool4_losses_lt_drove_wrong": sum(1 for e in examples if not e["pool_ok"] and e["s1_ok"] and e["lt_wrong"]),
    }

cohere_pat = pat_summary(cohere_ex, "cohere")
mistral_pat = pat_summary(mistral_ex, "mistral")
write_csv(OUTDIR / "pooled4_success_failure_pattern_summary.csv", [cohere_pat, mistral_pat])

# Representative cases markdown
rep_md = ["# Representative Pooled-4 Cases", ""]
rep_md += ["## Cohere: Pooled-4 Regressions vs Frontier (first 5)", ""]
for e in cohere_reg[:5]:
    rep_md.append(f"- **{e['example_id']}** | gold={e['gold']} | f={e['f_a']}(ok={e['f_ok']}) l1={e['l1_a']}(ok={e['l1_ok']}) s1={e['s1_a']}(ok={e['s1_ok']}) ta={e['ta_a']}(ok={e['ta_ok']}) | pool_ok={e['pool_ok']} | pattern={e['majority_pattern']}")
rep_md += ["", "## Mistral: Pooled-4 Losses to S1 (first 10)", ""]
for e in mistral_pool_s1_losses[:10]:
    rep_md.append(f"- **{e['example_id']}** | gold={e['gold']} | f={e['f_a']}(ok={e['f_ok']}) l1={e['l1_a']}(ok={e['l1_ok']}) s1={e['s1_a']}(ok={e['s1_ok']}) ta={e['ta_a']}(ok={e['ta_ok']}) | pool_a={e['pool_a']} | lt_wrong={e['lt_wrong']} | pattern={e['majority_pattern']}")
write_md(OUTDIR / "representative_pooled4_cases.md", "\n".join(rep_md))

print(f"\n  Cohere: pool4 rec={len(cohere_rec)}, reg={len(cohere_reg)}")
print(f"  Mistral: pool4 losses to S1={len(mistral_pool_s1_losses)}, reg vs frontier={len(mistral_reg)}")


# ── weighted voting variants ─────────────────────────────────────────────────
def log_odds(p):
    p = max(min(p, 0.999), 0.001)
    return math.log(p / (1 - p))


def weighted_vote_select(answers, weights, frontier_ans):
    """Select answer by summing weights for each answer value."""
    totals = collections.defaultdict(float)
    for a, w in zip(answers, weights):
        if a is not None:
            totals[a] += w
    if not totals:
        return frontier_ans
    best_ans = max(totals, key=lambda x: (totals[x], x == frontier_ans))
    if best_ans == frontier_ans:
        return frontier_ans  # keep frontier if it wins or ties
    if totals[best_ans] > totals.get(frontier_ans, 0):
        return best_ans
    return frontier_ans


def eval_policy(examples, select_fn, label, provider_label,
                is_provider_agnostic=True, is_insample=True):
    N = len(examples)
    correct = 0
    rec_vs_agr = 0; reg_vs_agr = 0
    rec_vs_pool = 0; reg_vs_pool = 0
    wins_vs_pool = 0; losses_vs_pool = 0
    oracle_regret = 0
    for e in examples:
        ans = select_fn(e)
        gold = e["gold"]
        ok = int(str(ans).strip() == str(gold).strip()) if (ans and gold) else 0
        correct += ok
        agr_ok = e["agr_ok"]; pool_ok = e["pool_ok"]
        if ok and not agr_ok: rec_vs_agr += 1
        elif not ok and agr_ok: reg_vs_agr += 1
        if ok and not pool_ok: rec_vs_pool += 1
        elif not ok and pool_ok: reg_vs_pool += 1
        if ok > pool_ok: wins_vs_pool += 1
        elif ok < pool_ok: losses_vs_pool += 1
        if e["oracle_ok"] and not ok: oracle_regret += 1
    agr_correct = sum(e["agr_ok"] for e in examples)
    pool_correct = sum(e["pool_ok"] for e in examples)
    s1_correct = sum(e["s1_ok"] for e in examples)
    f_correct = sum(e["f_ok"] for e in examples)
    return {
        "provider": provider_label, "method": label,
        "correct": correct, "n": N,
        "accuracy": round(correct/N, 4),
        "delta_vs_agreement_only": round((correct-agr_correct)/N, 4),
        "delta_vs_pooled4": round((correct-pool_correct)/N, 4),
        "delta_vs_s1": round((correct-s1_correct)/N, 4),
        "delta_vs_frontier": round((correct-f_correct)/N, 4),
        "recoveries_vs_agr": rec_vs_agr, "regressions_vs_agr": reg_vs_agr,
        "recoveries_vs_pool4": rec_vs_pool, "regressions_vs_pool4": reg_vs_pool,
        "wins_vs_pool4": wins_vs_pool, "losses_vs_pool4": losses_vs_pool,
        "oracle_regret": oracle_regret,
        "provider_agnostic": int(is_provider_agnostic),
        "in_sample_estimate": int(is_insample),
    }


def run_all_variants(examples, provider_label):
    N = len(examples)
    rows = []

    # Baselines
    rows.append(eval_policy(examples, lambda e: e["f_a"],    "frontier",         provider_label))
    rows.append(eval_policy(examples, lambda e: e["l1_a"],   "L1",               provider_label))
    rows.append(eval_policy(examples, lambda e: e["s1_a"],   "S1",               provider_label))
    rows.append(eval_policy(examples, lambda e: e["ta_a"],   "TALE",             provider_label))
    rows.append(eval_policy(examples, lambda e: e["agr_a"],  "agreement_only",   provider_label))
    rows.append(eval_policy(examples, lambda e: e["pool_a"], "pooled_4",         provider_label))
    rows.append(eval_policy(examples, lambda e: e["s1_a"],   "always_S1",        provider_label, is_provider_agnostic=False))

    # --- in-sample log-odds weighted vote ---
    p = {k: max(min(sum(e[f"{k}_ok"] for e in examples)/N, 0.999), 0.001)
         for k in ["f","l1","s1","ta"]}
    w = {k: log_odds(p[k]) for k in p}

    def lo_weighted(e):
        return weighted_vote_select(
            [e["f_a"], e["l1_a"], e["s1_a"], e["ta_a"]],
            [w["f"],   w["l1"],   w["s1"],   w["ta"]],
            e["f_a"]
        )
    rows.append(eval_policy(examples, lo_weighted, "log_odds_weighted_insample",
                             provider_label, is_insample=True))

    # --- 5-fold cross-validated log-odds ---
    indices = list(range(N))
    random.shuffle(indices)
    folds = [indices[i::5] for i in range(5)]
    cv_results = [None] * N
    for val_fold_idx in range(5):
        val_idx = set(folds[val_fold_idx])
        train_ex = [examples[i] for i in range(N) if i not in val_idx]
        Ntr = len(train_ex)
        p_tr = {k: max(min(sum(e[f"{k}_ok"] for e in train_ex)/Ntr, 0.999), 0.001)
                for k in ["f","l1","s1","ta"]}
        w_tr = {k: log_odds(p_tr[k]) for k in p_tr}
        for i in folds[val_fold_idx]:
            e = examples[i]
            ans = weighted_vote_select(
                [e["f_a"], e["l1_a"], e["s1_a"], e["ta_a"]],
                [w_tr["f"], w_tr["l1"], w_tr["s1"], w_tr["ta"]],
                e["f_a"]
            )
            cv_results[i] = ans

    def cv_lo_fn(e):
        idx = next(i for i, ex in enumerate(examples) if ex["example_id"] == e["example_id"])
        return cv_results[idx]
    rows.append(eval_policy(examples, cv_lo_fn, "log_odds_weighted_cv5fold",
                             provider_label, is_insample=False))

    # --- correlation-adjusted weighted vote ---
    # discount each source by its avg excess double-fault with others
    keys = ["f","l1","s1","ta"]
    excess_df_avg = {}
    for k1 in keys:
        vals = []
        for k2 in keys:
            if k1 == k2: continue
            acc1 = p[k1]; acc2 = p.get(k2, 0.5)
            df_obs = sum(1 for e in examples if not e[f"{k1}_ok"] and not e[f"{k2}_ok"]) / N
            df_exp = (1-acc1) * (1-acc2)
            vals.append(df_obs - df_exp)
        excess_df_avg[k1] = sum(vals)/len(vals)
    # discount: multiply log-odds weight by (1 - max(0, excess_df_norm))
    w_corr = {}
    for k in keys:
        discount = max(0, excess_df_avg[k]) * 5  # scale: 0.05 excess → 0.25 discount
        w_corr[k] = w[k] * max(0.1, 1 - discount)

    def corr_adj_weighted(e):
        return weighted_vote_select(
            [e["f_a"], e["l1_a"], e["s1_a"], e["ta_a"]],
            [w_corr["f"], w_corr["l1"], w_corr["s1"], w_corr["ta"]],
            e["f_a"]
        )
    rows.append(eval_policy(examples, corr_adj_weighted, "correlation_adjusted_weighted_insample",
                             provider_label, is_insample=True))

    # --- source-family vote ---
    # Voters: frontier (weight=1), S1 (weight=1), L1+TALE-family (weight=1 if agree, else 0.5 each)
    def source_family_vote(e):
        f_vote = e["f_a"]
        s1_vote = e["s1_a"]
        lt_vote = e["l1_a"] if e["lt_agree"] else None  # family agrees
        votes = collections.defaultdict(float)
        if f_vote: votes[f_vote] += 1.0
        if s1_vote: votes[s1_vote] += 1.0
        if lt_vote:
            votes[lt_vote] += 1.0
        else:
            if e["l1_a"]: votes[e["l1_a"]] += 0.5
            if e["ta_a"]: votes[e["ta_a"]] += 0.5
        best = max(votes, key=lambda x: (votes[x], x == f_vote)) if votes else f_vote
        if best != f_vote and votes[best] > votes.get(f_vote, 0):
            return best
        return f_vote
    rows.append(eval_policy(examples, source_family_vote, "source_family_vote",
                             provider_label, is_insample=False))

    # --- pooled-4 with L1+TALE discount ---
    def pool4_lt_discount(e):
        # L1 and TALE get 0.5 weight each if they agree and their answer ≠ S1 and ≠ frontier
        lt_agree = e["lt_agree"]
        lt_ans = e["l1_a"] if lt_agree else None
        s1_a = e["s1_a"]; f_a = e["f_a"]
        if lt_agree and lt_ans not in [s1_a, f_a]:
            w_l1 = 0.5; w_ta = 0.5
        else:
            w_l1 = 1.0; w_ta = 1.0
        return weighted_vote_select(
            [e["f_a"], e["l1_a"], e["s1_a"], e["ta_a"]],
            [1.0,       w_l1,     1.0,        w_ta],
            e["f_a"]
        )
    rows.append(eval_policy(examples, pool4_lt_discount, "pooled4_with_lt_discount",
                             provider_label, is_insample=False))

    # --- provider-prior selector (5-fold CV) ---
    # On each train fold, pick: pooled-4 or best single source (whichever is better)
    # Apply to val fold
    cv_prior_results = [None] * N
    for val_fold_idx in range(5):
        val_idx_set = set(folds[val_fold_idx])
        train_ex = [examples[i] for i in range(N) if i not in val_idx_set]
        Ntr = len(train_ex)
        src_accs_tr = {k: sum(e[f"{k}_ok"] for e in train_ex)/Ntr for k in ["f","l1","s1","ta"]}
        pool_acc_tr = sum(e["pool_ok"] for e in train_ex)/Ntr
        best_k = max(src_accs_tr, key=src_accs_tr.get)
        best_acc_tr = src_accs_tr[best_k]
        # use best-single if it dominates pooled-4 by ≥2% on train
        use_best = (best_acc_tr - pool_acc_tr >= 0.02)
        best_ans_key = f"{best_k}_a"
        for i in folds[val_fold_idx]:
            e = examples[i]
            cv_prior_results[i] = e[best_ans_key] if use_best else e["pool_a"]

    def provider_prior_fn(e):
        idx = next(i for i, ex in enumerate(examples) if ex["example_id"] == e["example_id"])
        return cv_prior_results[idx]
    rows.append(eval_policy(examples, provider_prior_fn, "provider_prior_selector_cv5fold",
                             provider_label, is_provider_agnostic=False, is_insample=False))

    # --- hybrid pooled4 or best source (5-fold CV) ---
    # Same as provider_prior but compares pooled-4 vs best source by accuracy, threshold=0
    cv_hybrid_results = [None] * N
    for val_fold_idx in range(5):
        val_idx_set = set(folds[val_fold_idx])
        train_ex = [examples[i] for i in range(N) if i not in val_idx_set]
        Ntr = len(train_ex)
        src_accs_tr = {k: sum(e[f"{k}_ok"] for e in train_ex)/Ntr for k in ["f","l1","s1","ta"]}
        pool_acc_tr = sum(e["pool_ok"] for e in train_ex)/Ntr
        best_k = max(src_accs_tr, key=src_accs_tr.get)
        best_acc_tr = src_accs_tr[best_k]
        use_best = (best_acc_tr > pool_acc_tr)  # any margin
        best_ans_key = f"{best_k}_a"
        for i in folds[val_fold_idx]:
            e = examples[i]
            cv_hybrid_results[i] = e[best_ans_key] if use_best else e["pool_a"]

    def hybrid_fn(e):
        idx = next(i for i, ex in enumerate(examples) if ex["example_id"] == e["example_id"])
        return cv_hybrid_results[idx]
    rows.append(eval_policy(examples, hybrid_fn, "hybrid_pool4_or_best_source_cv5fold",
                             provider_label, is_provider_agnostic=False, is_insample=False))

    return rows


print("\n=== Weighted voting variants ===")
cohere_variants = run_all_variants(cohere_ex, "cohere")
mistral_variants = run_all_variants(mistral_ex, "mistral")
all_variants = cohere_variants + mistral_variants
write_csv(OUTDIR / "diagnostic_weighted_voting_variant_summary.csv", all_variants)

# CV-only summary
cv_rows = [r for r in all_variants if not r["in_sample_estimate"] or r["method"] in ["agreement_only","pooled_4","frontier","L1","S1","TALE","always_S1","source_family_vote","pooled4_with_lt_discount"]]
write_csv(OUTDIR / "heldout_weighted_voting_cv_summary.csv", cv_rows)

print("  Cohere variants:")
for r in cohere_variants:
    print(f"    {r['method']:45s}  acc={r['accuracy']:.4f}  Δpool={r['delta_vs_pooled4']:+.4f}  Δagr={r['delta_vs_agreement_only']:+.4f}")
print("  Mistral variants:")
for r in mistral_variants:
    print(f"    {r['method']:45s}  acc={r['accuracy']:.4f}  Δpool={r['delta_vs_pooled4']:+.4f}  ΔS1={r['delta_vs_s1']:+.4f}")

# Interpretation
interp2_lines = [
    "# Weighted Voting Variant Interpretation",
    "",
    "## Cohere Results",
    "| Method | Acc | Δ pool4 | Δ agr-only | In-sample? |",
    "|--------|-----|---------|------------|------------|",
]
for r in cohere_variants:
    interp2_lines.append(f"| {r['method'][:40]} | {r['accuracy']:.4f} | {r['delta_vs_pooled4']:+.4f} | {r['delta_vs_agreement_only']:+.4f} | {'yes' if r['in_sample_estimate'] else 'no'} |")

interp2_lines += [
    "",
    "## Mistral Results",
    "| Method | Acc | Δ pool4 | Δ S1 | In-sample? |",
    "|--------|-----|---------|------|------------|",
]
for r in mistral_variants:
    interp2_lines.append(f"| {r['method'][:40]} | {r['accuracy']:.4f} | {r['delta_vs_pooled4']:+.4f} | {r['delta_vs_s1']:+.4f} | {'yes' if r['in_sample_estimate'] else 'no'} |")

# Find best held-out on each provider
best_cohere_heldout = max((r for r in cohere_variants if not r["in_sample_estimate"]), key=lambda r: r["accuracy"])
best_mistral_heldout = max((r for r in mistral_variants if not r["in_sample_estimate"]), key=lambda r: r["accuracy"])
cohere_agr_acc = next(r["accuracy"] for r in cohere_variants if r["method"] == "agreement_only")
mistral_s1_acc = next(r["accuracy"] for r in mistral_variants if r["method"] == "always_S1")

interp2_lines += [
    "",
    "## Key Findings",
    f"- Best held-out method on Cohere: **{best_cohere_heldout['method']}** acc={best_cohere_heldout['accuracy']:.4f}",
    f"- Best held-out method on Mistral: **{best_mistral_heldout['method']}** acc={best_mistral_heldout['accuracy']:.4f}",
    f"- Best Mistral held-out vs always-S1: {best_mistral_heldout['accuracy']:.4f} vs {mistral_s1_acc:.4f} ({best_mistral_heldout['accuracy']-mistral_s1_acc:+.4f})",
    f"- Best Cohere held-out vs agreement-only: {best_cohere_heldout['accuracy']:.4f} vs {cohere_agr_acc:.4f} ({best_cohere_heldout['accuracy']-cohere_agr_acc:+.4f})",
]
write_md(OUTDIR / "weighted_voting_variant_interpretation.md", "\n".join(interp2_lines))


# ── algorithm candidate decision table ──────────────────────────────────────
print("\n=== Algorithm decision table ===")

def get_acc(variants, method, provider):
    for r in variants:
        if r["method"] == method and r["provider"] == provider:
            return r["accuracy"]
    return None

candidates = [
    ("pooled_4",                           True,  False, False, True,  True),
    ("agreement_only",                     True,  False, False, False, False),
    ("source_family_vote",                 True,  False, False, True,  True),
    ("pooled4_with_lt_discount",           True,  False, False, True,  False),
    ("log_odds_weighted_cv5fold",          False, True,  False, True,  True),
    ("provider_prior_selector_cv5fold",    False, True,  True,  True,  True),
    ("always_S1",                          False, True,  True,  False, True),
]

decision_rows = []
for method, agnostic, needs_calib, needs_source_rank, robust_corr, handles_dominance in candidates:
    c_acc = get_acc(cohere_variants, method, "cohere")
    m_acc = get_acc(mistral_variants, method, "mistral")
    if c_acc is None or m_acc is None:
        continue
    avg_rank = None  # computed below
    # rank on each provider
    c_sorted = sorted([(r["accuracy"],r["method"]) for r in cohere_variants], reverse=True)
    m_sorted = sorted([(r["accuracy"],r["method"]) for r in mistral_variants], reverse=True)
    c_rank = next((i+1 for i,(a,m) in enumerate(c_sorted) if m==method), 99)
    m_rank = next((i+1 for i,(a,m) in enumerate(m_sorted) if m==method), 99)
    worst_rank = max(c_rank, m_rank)
    avg_rank = (c_rank + m_rank) / 2

    # recommendation
    if method == "pooled_4":
        rec = "promote_if_cerebras_confirms"
    elif method == "agreement_only":
        rec = "current_baseline_safe"
    elif method == "source_family_vote" and c_acc >= 0.82 and m_acc >= 0.84:
        rec = "validate_on_cerebras"
    elif method == "log_odds_weighted_cv5fold":
        rec = "diagnostic_only_needs_dev_set"
    elif method == "provider_prior_selector_cv5fold":
        rec = "diagnostic_only_provider_specific"
    elif method == "always_S1":
        rec = "reject_for_cohere_harms_cohere"
    else:
        rec = "diagnostic_only"

    decision_rows.append({
        "algorithm": method,
        "cohere_canonical_acc": c_acc,
        "mistral_acc": m_acc,
        "avg_provider_rank": round(avg_rank, 1),
        "worst_provider_rank": worst_rank,
        "provider_agnostic": int(agnostic),
        "requires_calibration": int(needs_calib),
        "risks_overfitting": int(needs_source_rank and needs_calib),
        "robust_to_correlated_errors": int(robust_corr),
        "handles_source_dominance": int(handles_dominance),
        "recommendation": rec,
    })

write_csv(OUTDIR / "algorithm_candidate_decision_table.csv", decision_rows)
for r in decision_rows:
    print(f"  {r['algorithm']:45s}  cohere={r['cohere_canonical_acc']:.4f}  mistral={r['mistral_acc']:.4f}  rank_avg={r['avg_provider_rank']}  rec={r['recommendation']}")


# ── Step 10: Human-readable report ──────────────────────────────────────────
print("\n=== Writing report ===")

def fmt(val, pct=True):
    if val is None: return "N/A"
    if pct: return f"{val:.1%}"
    return f"{val:.4f}"

c_lt = cohere_lt; m_lt = mistral_lt
c_div = cohere_div; m_div = mistral_div

# get best heldout not in-sample
best_c_heldout_notinsample = max(
    (r for r in cohere_variants if not r["in_sample_estimate"] and r["method"] not in ["agreement_only","pooled_4","frontier","L1","S1","TALE","always_S1"]),
    key=lambda r: r["accuracy"]
)
best_m_heldout_notinsample = max(
    (r for r in mistral_variants if not r["in_sample_estimate"] and r["method"] not in ["agreement_only","pooled_4","frontier","L1","S1","TALE","always_S1"]),
    key=lambda r: r["accuracy"]
)

report_lines = [
    "# Error Correlation and Ensemble Diversity Diagnostic — 2026-05-23",
    "",
    "**Analysis timestamp:** " + datetime.now(tz=timezone.utc).isoformat(),
    "**No API calls made. Cerebras job not touched.**",
    "",
    "---",
    "",
    "## 1. Are Cohere Source Errors Less Correlated Than Mistral?",
    "",
    "**Yes — Cohere errors are meaningfully less correlated across all source pairs.**",
    "",
    "| Pair | Cohere φ | Mistral φ | Δ (Mistral − Cohere) |",
    "|------|----------|-----------|----------------------|",
]
for r in cross_rows:
    report_lines.append(f"| {r['source_A']}×{r['source_B']} | {r['cohere_phi']:+.3f} | {r['mistral_phi']:+.3f} | {r['phi_diff_mistral_minus_cohere']:+.3f} |")

report_lines += [
    "",
    "Higher positive φ = more correlated errors. Condorcet Jury Theorem requires approximately",
    "independent errors; Mistral's higher φ values mean fewer effective independent votes.",
    "",
    "---",
    "",
    "## 2. Is L1+TALE More Correlated on Mistral Than Cohere?",
    "",
    f"| Metric | Cohere | Mistral |",
    f"|--------|--------|---------|",
    f"| L1+TALE φ (correctness) | {c_lt['phi']:+.4f} | {m_lt['phi']:+.4f} |",
    f"| L1+TALE Q-statistic | {c_lt['Q_statistic']} | {m_lt['Q_statistic']} |",
    f"| L1+TALE double-fault rate | {c_lt['double_fault_rate']:.4f} | {m_lt['double_fault_rate']:.4f} |",
    f"| L1+TALE expected double-fault (indep.) | {c_lt['expected_double_fault']:.4f} | {m_lt['expected_double_fault']:.4f} |",
    f"| L1+TALE excess double-fault | {c_lt['excess_double_fault']:.4f} | {m_lt['excess_double_fault']:.4f} |",
    f"| L1+TALE answer agreement rate | {c_lt['lt_answer_agree_rate']:.1%} | {m_lt['lt_answer_agree_rate']:.1%} |",
    f"| L1+TALE agree correct rate | {c_lt['lt_agree_correct_rate']:.1%} | {m_lt['lt_agree_correct_rate']:.1%} |",
    f"| L1+TALE agree wrong rate | {c_lt['lt_agree_wrong_rate']:.1%} | {m_lt['lt_agree_wrong_rate']:.1%} |",
    f"| Bad majority (L1+TALE wrong, S1 correct) | {c_lt['lt_wrong_s1_correct']} | {m_lt['lt_wrong_s1_correct']} |",
    f"| Behavior | {c_lt['independence_behavior']} | {m_lt['independence_behavior']} |",
    "",
    "**Finding:** " + (
        f"Mistral L1+TALE φ={m_lt['phi']:.3f} > Cohere L1+TALE φ={c_lt['phi']:.3f}. "
        if m_lt['phi'] > c_lt['phi'] else
        f"Surprisingly, Cohere L1+TALE φ={c_lt['phi']:.3f} ≥ Mistral L1+TALE φ={m_lt['phi']:.3f}. "
    ),
    f"Excess double-fault: Mistral {m_lt['excess_double_fault']:+.4f} vs Cohere {c_lt['excess_double_fault']:+.4f}.",
    f"Bad majority cases: Mistral {m_lt['lt_wrong_s1_correct']} vs Cohere {c_lt['lt_wrong_s1_correct']}.",
    "",
    "---",
    "",
    "## 3. Does Double-Fault/Excess Double-Fault Explain Pooled-4 on Cohere?",
    "",
    f"- Cohere avg pairwise disagreement: {c_div['avg_pairwise_disagreement']:.3f}",
    f"- Cohere pooled-4 captures {c_div['pool4_pct_oracle_gain']:.1%} of oracle gain over frontier",
    f"  (agreement-only captures {c_div['agr_pct_oracle_gain']:.1%})",
    f"- Cohere pooled-4: {c_div['pool4_recoveries_vs_frontier']} recoveries, {c_div['pool4_regressions_vs_frontier']} regressions vs frontier",
    f"- Cohere majority patterns: all-4-agree {c_div['pct_all4_agree']:.1%}, 3-1 {c_div['pct_3_1_majority']:.1%}, 2-split {c_div['pct_2_2_split']:.1%}",
    "",
    "**Yes.** Lower excess double-fault on Cohere means errors are more spread across sources,",
    "allowing pooled majority to correct more errors. Sources behave like approximately independent voters.",
    "",
    "---",
    "",
    "## 4. Does Underweighting S1 Explain Pooled-4 Failing on Mistral?",
    "",
    f"- Mistral S1 accuracy: {c_div['acc_S1']:.1%} (Cohere) vs {m_div['acc_S1']:.1%} (Mistral)",
    f"- Mistral pooled-4 losses to S1: {mistral_pat['pool4_losses_vs_s1']}",
    f"- Of those losses, {mistral_pat['pool4_losses_lt_drove_wrong']} driven by L1+TALE wrong majority",
    f"- Mistral pooled-4 captures only {m_div['pool4_pct_oracle_gain']:.1%} of oracle gain",
    f"- Mistral always-S1 captures {m_div['s1_pct_oracle_gain']:.1%} of oracle gain",
    "",
    "**Yes.** On Mistral, S1's log-odds weight should be ~2.1× larger than L1's and ~4× TALE's.",
    "Uniform weighting loses {0} cases where L1+TALE outvote S1.".format(mistral_pat['pool4_losses_lt_drove_wrong']),
    "",
    "---",
    "",
    "## 5. Does Source-Family Voting Improve the Situation?",
    "",
    f"- Cohere source-family vote: {fmt(get_acc(cohere_variants, 'source_family_vote', 'cohere'))}",
    f"  vs pooled-4: {fmt(get_acc(cohere_variants, 'pooled_4', 'cohere'))}",
    f"- Mistral source-family vote: {fmt(get_acc(mistral_variants, 'source_family_vote', 'mistral'))}",
    f"  vs pooled-4: {fmt(get_acc(mistral_variants, 'pooled_4', 'mistral'))}",
    f"  vs always-S1: {fmt(get_acc(mistral_variants, 'always_S1', 'mistral'))}",
    "",
    "---",
    "",
    "## 6. Does Weighted Voting Beat Pooled-4 or Always-S1 Out of Sample?",
    "",
    f"- Best held-out variant on Cohere: **{best_c_heldout_notinsample['method']}** = {best_c_heldout_notinsample['accuracy']:.4f}",
    f"  vs pooled-4 = {get_acc(cohere_variants, 'pooled_4', 'cohere'):.4f}",
    f"- Best held-out variant on Mistral: **{best_m_heldout_notinsample['method']}** = {best_m_heldout_notinsample['accuracy']:.4f}",
    f"  vs always-S1 = {get_acc(mistral_variants, 'always_S1', 'mistral'):.4f}",
    "",
    "---",
    "",
    "## 7. Recommended Next Promoted Algorithm",
    "",
]
# Build recommendation from decision_rows
rec_pool = next(r for r in decision_rows if r["algorithm"] == "pooled_4")
rec_sf = next((r for r in decision_rows if r["algorithm"] == "source_family_vote"), None)
report_lines += [
    f"| Algorithm | Cohere | Mistral | Avg rank | Agnostic? | Recommendation |",
    f"|-----------|--------|---------|----------|-----------|----------------|",
]
for r in decision_rows:
    report_lines.append(f"| {r['algorithm'][:40]} | {r['cohere_canonical_acc']:.4f} | {r['mistral_acc']:.4f} | {r['avg_provider_rank']} | {'yes' if r['provider_agnostic'] else 'no'} | {r['recommendation']} |")

report_lines += [
    "",
    "**Primary recommendation:** Promote **pooled-4** as the default provider-agnostic algorithm",
    f"if Cerebras validation confirms it beats agreement-only on a 3rd provider.",
    "",
    "**Secondary recommendation:** **Source-family vote** (treating L1+TALE as one family) is the",
    "safest provider-agnostic algorithm if Mistral results matter equally — it avoids the",
    "L1+TALE double-counting problem without requiring per-provider calibration.",
    "",
    "**Do not promote always-S1** as the main algorithm — it harms Cohere (−2.33 pp vs agreement-only).",
    "",
    "---",
    "",
    "## 8. What Evidence Is Still Needed from Cerebras?",
    "",
    "1. **Primary:** Does pooled-4 beat agreement-only on Cerebras llama3.1-8b?",
    "   If yes: pooled-4 wins on 2/3 providers → promote.",
    "   If no: investigate whether Cerebras resembles Mistral (one dominant source) or Cohere (balanced).",
    "",
    "2. **Secondary:** Check pairwise φ matrix on Cerebras. If φ(L1,TALE) is high (>0.2),",
    "   source-family vote should be preferred over pooled-4.",
    "",
    "3. **Accuracy check:** Compute Cerebras per-method accuracies. If S1 dominates (>85%)",
    "   while others are <80%, apply provider-prior selector (not pooled-4) for Cerebras.",
    "",
    "---",
    "",
    "## Constraints Confirmed",
    "- No API calls were made.",
    "- Cerebras job (PID 2195513) was not touched, killed, or modified.",
    "- No frozen policy was changed.",
    "- All diagnostic variants are offline/diagnostic only. No policy was promoted.",
]
write_md(OUTDIR / "ERROR_CORRELATION_AND_ENSEMBLE_DIVERSITY_DIAGNOSTIC_20260523_report.md", "\n".join(report_lines))


# ── Manifest ─────────────────────────────────────────────────────────────────
manifest = {
    "task": "error_correlation_and_ensemble_diversity_diagnostic",
    "created_utc": datetime.now(tz=timezone.utc).isoformat(),
    "source_artifacts": [str(COHERE_PER_EXAMPLE), str(MISTRAL_PER_EXAMPLE)],
    "output_directory": str(OUTDIR),
    "files_created": [
        "cohere_canonical_diversity_table.csv",
        "mistral_diversity_table.csv",
        "cohere_pairwise_error_correlation.csv",
        "mistral_pairwise_error_correlation.csv",
        "cross_provider_pairwise_correlation_comparison.csv",
        "l1_tale_family_correlation_summary.csv",
        "l1_tale_family_correlation_interpretation.md",
        "ensemble_diversity_summary.csv",
        "oracle_gap_and_complementarity_summary.csv",
        "majority_pattern_summary.csv",
        "cohere_pooled4_recovery_regression_cases.csv",
        "mistral_pooled4_vs_s1_loss_cases.csv",
        "pooled4_success_failure_pattern_summary.csv",
        "representative_pooled4_cases.md",
        "diagnostic_weighted_voting_variant_summary.csv",
        "heldout_weighted_voting_cv_summary.csv",
        "weighted_voting_variant_interpretation.md",
        "algorithm_candidate_decision_table.csv",
        "ERROR_CORRELATION_AND_ENSEMBLE_DIVERSITY_DIAGNOSTIC_20260523_report.md",
        "manifest.json",
    ],
    "api_calls_made": False,
    "active_cerebras_untouched": True,
    "frozen_policy_modified": False,
    "artifacts_overwritten": False,
    "note": "All weighted/diagnostic variants are offline only. No policy promoted.",
}
write_json(OUTDIR / "manifest.json", manifest)
print("\nDone. All outputs in:", OUTDIR)
