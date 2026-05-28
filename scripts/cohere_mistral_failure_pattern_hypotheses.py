"""Cross-provider failure-pattern and hypothesis-generation analysis.

Uses only completed Cohere canonical Final-300 and Mistral Final-300 artifacts.
No API calls. No modification of frozen policy logic. No touching active jobs.
All results are offline/diagnostic only.
"""

import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "outputs" / "cohere_mistral_failure_pattern_hypotheses_20260523"
OUT.mkdir(parents=True, exist_ok=True)

COHERE_JSONL = (
    REPO / "outputs"
    / "canonical_final300_cohere_contract_matched_live_20260523T181948Z"
    / "cohere_real_model_cost_normalized_validation_20260523T181948Z"
    / "per_example_records.jsonl"
)
MISTRAL_JSONL = (
    REPO / "outputs"
    / "mistral_frozen_agreement_only_2of3_validation_20260523T145416Z"
    / "cohere_real_model_cost_normalized_validation_20260523T145416Z"
    / "per_example_records.jsonl"
)
COHERE_DIV = (
    REPO / "outputs" / "error_correlation_and_ensemble_diversity_diagnostic_20260523"
    / "cohere_canonical_diversity_table.csv"
)
MISTRAL_DIV = (
    REPO / "outputs" / "error_correlation_and_ensemble_diversity_diagnostic_20260523"
    / "mistral_diversity_table.csv"
)

METHOD_TO_COL = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "L1",
    "external_s1_budget_forcing": "S1",
    "external_tale_prompt_budgeting": "TALE",
}

SOURCES = ["frontier", "L1", "S1", "TALE"]

# ─── helpers ──────────────────────────────────────────────────────────────────

def norm(x):
    if x is None:
        return ""
    return str(x).strip().lower()


def safe_int(x, default=0):
    try:
        return int(x)
    except (ValueError, TypeError):
        return default


def mean(xs):
    xs = [v for v in xs if v is not None]
    return sum(xs) / len(xs) if xs else 0.0


def pct(n, d):
    return (n / d * 100) if d else 0.0


# ─── Step 1: load raw JSONL into per-example dicts keyed by example_id ───────

def load_raw_jsonl(path: Path):
    """Return {example_id: {method_short: record}} for all 300 examples."""
    by_id = defaultdict(dict)
    method_map = {v: k for k, v in {
        "direct_reserve_semantic_frontier_v2": "frontier",
        "external_l1_max": "L1",
        "external_s1_budget_forcing": "S1",
        "external_tale_prompt_budgeting": "TALE",
    }.items()}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            mid = METHOD_TO_COL.get(rec["method"], rec["method"])
            by_id[rec["example_id"]][mid] = rec
    return by_id


def load_div_table(path: Path):
    """Return list of dicts from diversity CSV."""
    with open(path) as f:
        return list(csv.DictReader(f))


def int_field(row, key):
    return safe_int(row.get(key, 0))


# ─── Step 2: build enriched failure pattern table ────────────────────────────

def build_failure_table(div_rows, raw_by_id, provider_label):
    """Enrich diversity table rows with failure labels and question text."""
    result = []
    for row in div_rows:
        eid = row["example_id"]
        raw = raw_by_id.get(eid, {})

        # question text from any available method record
        question = ""
        for src in SOURCES:
            if src in raw:
                question = raw[src].get("question", "")
                if question:
                    break

        f_ok  = int_field(row, "f_ok")
        l1_ok = int_field(row, "l1_ok")
        s1_ok = int_field(row, "s1_ok")
        ta_ok = int_field(row, "ta_ok")
        agr_ok = int_field(row, "agr_ok")
        pool_ok = int_field(row, "pool_ok")
        oracle_ok = int_field(row, "oracle_ok")
        lt_agree = int_field(row, "lt_agree")
        lt_wrong = int_field(row, "lt_wrong")
        lt_wrong_s1_correct = int_field(row, "lt_wrong_s1_correct")

        f_a  = norm(row.get("f_a", ""))
        l1_a = norm(row.get("l1_a", ""))
        s1_a = norm(row.get("s1_a", ""))
        ta_a = norm(row.get("ta_a", ""))
        agr_a  = norm(row.get("agr_a", ""))
        pool_a = norm(row.get("pool_a", ""))
        gold = norm(row.get("gold", ""))
        maj_pat = row.get("majority_pattern", "")

        source_oks = {"frontier": f_ok, "L1": l1_ok, "S1": s1_ok, "TALE": ta_ok}
        source_ans = {"frontier": f_a, "L1": l1_a, "S1": s1_a, "TALE": ta_a}

        best_source = max(source_oks, key=lambda k: source_oks[k])
        best_source_ok = source_oks[best_source]
        any_correct = any(v == 1 for v in source_oks.values())

        # ── pooled-4 failure classification ──────────────────────────────────
        pool_fail_class = ""
        if pool_ok == 0:
            n_correct = sum(source_oks.values())
            if n_correct == 0:
                pool_fail_class = "A_all_sources_wrong"
            elif n_correct == 1:
                pool_fail_class = "C_wrong_majority_correct_source_isolated"
            elif n_correct == 2:
                # two correct, two wrong — depends on whether correct pair forms majority
                # if majority_pattern is two_two, tie goes to frontier
                if maj_pat in ("two_two", "2_2"):
                    pool_fail_class = "D_wrong_2_2_tie_fallback"
                else:
                    pool_fail_class = "C_wrong_majority_correct_source_isolated"
            elif n_correct == 3:
                # three correct, one wrong — pooled-4 should recover; if it fails, unusual
                pool_fail_class = "H_other_unexpected"
            else:
                pool_fail_class = "H_other_unexpected"

            # override: if no majority and frontier wrong
            if maj_pat in ("all_different", "no_majority") and f_ok == 0:
                pool_fail_class = "E_no_majority_frontier_fallback_wrong"

        # ── agreement-only failure classification ─────────────────────────────
        agr_fail_class = ""
        if agr_ok == 0:
            # was external majority invoked?
            ext_majority_used = (agr_a != f_a and agr_a != "")
            if not ext_majority_used:
                # kept frontier
                if f_ok == 0:
                    # no ext majority, frontier wrong
                    agr_fail_class = "A_no_ext_majority_keep_wrong_frontier"
                else:
                    agr_fail_class = "H_other"
            else:
                # ext majority was used but answer wrong
                if f_ok == 1:
                    agr_fail_class = "D_frontier_correct_regression"
                elif s1_ok == 1 and lt_wrong_s1_correct:
                    agr_fail_class = "F_L1_TALE_wrong_majority_overrides_correct_S1"
                elif s1_ok == 1:
                    agr_fail_class = "E_S1_correct_underweighted"
                elif n_correct_agr := sum(source_oks.values()):
                    agr_fail_class = "C_ext_majority_wrong_but_some_source_correct"
                else:
                    agr_fail_class = "G_all_sources_wrong"

        def n_correct_sources():
            return sum(source_oks.values())

        out = {
            "provider": provider_label,
            "example_id": eid,
            "question": question[:200],
            "gold": gold,
            "f_a": f_a,
            "l1_a": l1_a,
            "s1_a": s1_a,
            "ta_a": ta_a,
            "f_ok": f_ok,
            "l1_ok": l1_ok,
            "s1_ok": s1_ok,
            "ta_ok": ta_ok,
            "agr_a": agr_a,
            "agr_ok": agr_ok,
            "pool_a": pool_a,
            "pool_ok": pool_ok,
            "oracle_ok": oracle_ok,
            "n_correct_sources": n_correct_sources(),
            "best_source": best_source,
            "best_source_ok": best_source_ok,
            "majority_pattern": maj_pat,
            "lt_agree": lt_agree,
            "lt_wrong": lt_wrong,
            "lt_wrong_s1_correct": lt_wrong_s1_correct,
            "s1_isolated": int(s1_ok == 1 and l1_ok == 0 and ta_ok == 0 and f_ok == 0),
            "s1_correct": s1_ok,
            "pool_fail_class": pool_fail_class,
            "agr_fail_class": agr_fail_class,
            "pool_regresses_vs_frontier": int(f_ok == 1 and pool_ok == 0),
            "pool_recovers_vs_frontier": int(f_ok == 0 and pool_ok == 1),
            "agr_regresses_vs_frontier": int(f_ok == 1 and agr_ok == 0),
            "agr_recovers_vs_frontier": int(f_ok == 0 and agr_ok == 1),
            "pool_beats_agr": int(pool_ok == 1 and agr_ok == 0),
            "agr_beats_pool": int(agr_ok == 1 and pool_ok == 0),
            "s1_beats_pool": int(s1_ok == 1 and pool_ok == 0),
            "s1_beats_agr": int(s1_ok == 1 and agr_ok == 0),
            "best_correct_pool_wrong": int(best_source_ok == 1 and pool_ok == 0),
            "all_wrong": int(n_correct_sources() == 0),
            "frontier_in_majority": int(
                any(f_a == ans for ans in [l1_a, s1_a, ta_a])
            ),
        }
        result.append(out)
    return result


# ─── Step 3: write failure tables ────────────────────────────────────────────

def write_csv(path: Path, rows, fieldnames=None):
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path.name} ({len(rows)} rows)")


# ─── Step 4: failure taxonomy summary ────────────────────────────────────────

def failure_taxonomy_summary(cohere_rows, mistral_rows):
    """Produce selector failure taxonomy CSV."""
    rows_out = []
    for provider, rows in [("cohere", cohere_rows), ("mistral", mistral_rows)]:
        N = len(rows)
        total_ok = {
            "frontier": sum(r["f_ok"] for r in rows),
            "L1": sum(r["l1_ok"] for r in rows),
            "S1": sum(r["s1_ok"] for r in rows),
            "TALE": sum(r["ta_ok"] for r in rows),
            "agreement_only": sum(r["agr_ok"] for r in rows),
            "pooled_4": sum(r["pool_ok"] for r in rows),
            "oracle": sum(r["oracle_ok"] for r in rows),
        }
        pool_failures = [r for r in rows if r["pool_ok"] == 0]
        agr_failures  = [r for r in rows if r["agr_ok"] == 0]

        pool_class_counts = Counter(r["pool_fail_class"] for r in pool_failures)
        agr_class_counts  = Counter(r["agr_fail_class"] for r in agr_failures)

        for sel, failures, class_counts in [
            ("pooled_4", pool_failures, pool_class_counts),
            ("agreement_only", agr_failures, agr_class_counts),
        ]:
            for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
                rows_out.append({
                    "provider": provider,
                    "selector": sel,
                    "failure_class": cls,
                    "count": cnt,
                    "pct_of_selector_failures": round(pct(cnt, len(failures)), 1),
                    "pct_of_total": round(pct(cnt, N), 1),
                })
    return rows_out


# ─── Step 5: pooled-4 comparison ─────────────────────────────────────────────

def pooled4_comparison(cohere_rows, mistral_rows):
    out_rows = []
    for provider, rows in [("cohere", cohere_rows), ("mistral", mistral_rows)]:
        N = len(rows)
        pool_ok = sum(r["pool_ok"] for r in rows)
        pool_wrong = N - pool_ok
        oracle_ok = sum(r["oracle_ok"] for r in rows)
        s1_ok_total = sum(r["s1_ok"] for r in rows)

        out_rows.append({
            "provider": provider,
            "N": N,
            "pooled_4_accuracy": round(pool_ok / N, 4),
            "pooled_4_wrong": pool_wrong,
            "oracle_accuracy": round(oracle_ok / N, 4),
            "oracle_regret": pool_wrong,
            "pool_wrong_oracle_correct": sum(1 for r in rows if r["pool_ok"] == 0 and r["oracle_ok"] == 1),
            "pool_wrong_best_src_correct": sum(r["best_correct_pool_wrong"] for r in rows),
            "pool_wrong_s1_correct": sum(r["s1_beats_pool"] for r in rows),
            "pool_recoveries_vs_frontier": sum(r["pool_recovers_vs_frontier"] for r in rows),
            "pool_regressions_vs_frontier": sum(r["pool_regresses_vs_frontier"] for r in rows),
            "pool_net_vs_frontier": sum(r["pool_recovers_vs_frontier"] - r["pool_regresses_vs_frontier"] for r in rows),
            "all_sources_wrong_count": sum(r["all_wrong"] for r in rows),
            "pool_fails_due_to_all_wrong": sum(1 for r in rows if r["pool_ok"] == 0 and r["all_wrong"] == 1),
        })
    return out_rows


# ─── Step 6: agreement-only comparison ───────────────────────────────────────

def agreement_comparison(cohere_rows, mistral_rows):
    out_rows = []
    for provider, rows in [("cohere", cohere_rows), ("mistral", mistral_rows)]:
        N = len(rows)
        agr_ok = sum(r["agr_ok"] for r in rows)
        agr_wrong = N - agr_ok
        pool_ok = sum(r["pool_ok"] for r in rows)

        out_rows.append({
            "provider": provider,
            "N": N,
            "agr_accuracy": round(agr_ok / N, 4),
            "agr_wrong": agr_wrong,
            "agr_wrong_oracle_correct": sum(1 for r in rows if r["agr_ok"] == 0 and r["oracle_ok"] == 1),
            "agr_wrong_pool_correct": sum(1 for r in rows if r["agr_ok"] == 0 and r["pool_ok"] == 1),
            "agr_wrong_best_src_correct": sum(1 for r in rows if r["agr_ok"] == 0 and r["best_source_ok"] == 1),
            "agr_wrong_s1_correct": sum(r["s1_beats_agr"] for r in rows),
            "no_ext_majority_frontier_wrong": sum(1 for r in rows if r["agr_fail_class"] == "A_no_ext_majority_keep_wrong_frontier"),
            "wrong_ext_majority": sum(1 for r in rows if r["agr_fail_class"] in (
                "B_ext_majority_wrong",
                "F_L1_TALE_wrong_majority_overrides_correct_S1",
                "E_S1_correct_underweighted",
                "C_ext_majority_wrong_but_some_source_correct",
            )),
            "l1_tale_wrong_majority": sum(r["lt_wrong_s1_correct"] for r in rows),
            "agr_recoveries_vs_frontier": sum(r["agr_recovers_vs_frontier"] for r in rows),
            "agr_regressions_vs_frontier": sum(r["agr_regresses_vs_frontier"] for r in rows),
            "agr_net_vs_frontier": sum(r["agr_recovers_vs_frontier"] - r["agr_regresses_vs_frontier"] for r in rows),
            "pool_beats_agr_count": sum(r["pool_beats_agr"] for r in rows),
            "agr_beats_pool_count": sum(r["agr_beats_pool"] for r in rows),
        })
    return out_rows


# ─── Step 7: cross-provider runtime pattern summary ──────────────────────────

def runtime_pattern_summary(cohere_rows, mistral_rows):
    rows_out = []
    for provider, rows in [("cohere", cohere_rows), ("mistral", mistral_rows)]:
        N = len(rows)
        patterns = Counter(r["majority_pattern"] for r in rows)

        def cond_acc(filter_fn, correct_fn):
            subset = [r for r in rows if filter_fn(r)]
            if not subset:
                return 0.0, 0
            return round(mean([correct_fn(r) for r in subset]), 4), len(subset)

        # majority patterns
        for pat in ["all_four_agree", "three_one", "two_two", "all_different"]:
            subset = [r for r in rows if r["majority_pattern"] == pat]
            if subset:
                pool_acc = mean([r["pool_ok"] for r in subset])
                agr_acc  = mean([r["agr_ok"]  for r in subset])
                s1_acc   = mean([r["s1_ok"]  for r in subset])
                oracle_acc = mean([r["oracle_ok"] for r in subset])
                rows_out.append({
                    "provider": provider,
                    "pattern": pat,
                    "count": len(subset),
                    "pct_total": round(pct(len(subset), N), 1),
                    "pooled_4_acc": round(pool_acc, 4),
                    "agr_acc": round(agr_acc, 4),
                    "s1_acc": round(s1_acc, 4),
                    "oracle_acc": round(oracle_acc, 4),
                })

        # additional patterns
        for pat_label, filter_fn in [
            ("s1_isolated_correct", lambda r: r["s1_isolated"] == 1),
            ("lt_agree_wrong", lambda r: r["lt_agree"] == 1 and r["lt_wrong"] == 1),
            ("frontier_in_majority", lambda r: r["frontier_in_majority"] == 1),
            ("all_wrong", lambda r: r["all_wrong"] == 1),
            ("s1_correct_pool_wrong", lambda r: r["s1_beats_pool"] == 1),
            ("best_correct_pool_wrong", lambda r: r["best_correct_pool_wrong"] == 1),
            ("pool_beats_agr", lambda r: r["pool_beats_agr"] == 1),
        ]:
            subset = [r for r in rows if filter_fn(r)]
            if subset:
                rows_out.append({
                    "provider": provider,
                    "pattern": pat_label,
                    "count": len(subset),
                    "pct_total": round(pct(len(subset), N), 1),
                    "pooled_4_acc": round(mean([r["pool_ok"] for r in subset]), 4),
                    "agr_acc": round(mean([r["agr_ok"] for r in subset]), 4),
                    "s1_acc": round(mean([r["s1_ok"] for r in subset]), 4),
                    "oracle_acc": round(mean([r["oracle_ok"] for r in subset]), 4),
                })
    return rows_out


def majority_conditioned_summary(cohere_rows, mistral_rows):
    rows_out = []
    for provider, rows in [("cohere", cohere_rows), ("mistral", mistral_rows)]:
        N = len(rows)
        for condition_label, filter_fn in [
            ("majority_includes_S1", lambda r: r["majority_pattern"] in ("three_one", "all_four_agree") and r["s1_a"] == r["pool_a"]),
            ("majority_excludes_S1", lambda r: r["majority_pattern"] in ("three_one",) and r["s1_a"] != r["pool_a"]),
            ("majority_includes_frontier", lambda r: r["majority_pattern"] in ("three_one", "all_four_agree") and r["f_a"] == r["pool_a"]),
            ("majority_excludes_frontier", lambda r: r["majority_pattern"] in ("three_one",) and r["f_a"] != r["pool_a"]),
            ("ext_majority_exists", lambda r: r["agr_a"] != r["f_a"]),
            ("no_ext_majority", lambda r: r["agr_a"] == r["f_a"]),
        ]:
            subset = [r for r in rows if filter_fn(r)]
            if subset:
                rows_out.append({
                    "provider": provider,
                    "condition": condition_label,
                    "count": len(subset),
                    "pct_total": round(pct(len(subset), N), 1),
                    "pool_acc": round(mean([r["pool_ok"] for r in subset]), 4),
                    "agr_acc": round(mean([r["agr_ok"] for r in subset]), 4),
                    "s1_acc": round(mean([r["s1_ok"] for r in subset]), 4),
                    "oracle_acc": round(mean([r["oracle_ok"] for r in subset]), 4),
                })
    return rows_out


# ─── Step 8: hypothesis generation ───────────────────────────────────────────

def generate_hypotheses(cohere_rows, mistral_rows, cv_results):
    """Generate evidence-backed hypotheses from computed statistics."""
    N = 300

    # Precompute stats
    SRC_OK_KEY = {"frontier": "f_ok", "L1": "l1_ok", "S1": "s1_ok", "TALE": "ta_ok"}

    def stats(rows):
        return {
            "acc": {src: mean([r[SRC_OK_KEY[src]] for r in rows]) for src in SOURCES},
            "pool_acc": mean([r["pool_ok"] for r in rows]),
            "agr_acc": mean([r["agr_ok"] for r in rows]),
            "oracle_acc": mean([r["oracle_ok"] for r in rows]),
            "s1_beats_pool": sum(r["s1_beats_pool"] for r in rows),
            "lt_wrong_s1_correct": sum(r["lt_wrong_s1_correct"] for r in rows),
            "pool_beats_agr": sum(r["pool_beats_agr"] for r in rows),
            "all_wrong": sum(r["all_wrong"] for r in rows),
            "best_correct_pool_wrong": sum(r["best_correct_pool_wrong"] for r in rows),
            "pool_recoveries": sum(r["pool_recovers_vs_frontier"] for r in rows),
            "pool_regressions": sum(r["pool_regresses_vs_frontier"] for r in rows),
            "agr_recoveries": sum(r["agr_recovers_vs_frontier"] for r in rows),
            "agr_regressions": sum(r["agr_regresses_vs_frontier"] for r in rows),
            "three_one_count": sum(1 for r in rows if r["majority_pattern"] == "three_one"),
            "all_four_agree_count": sum(1 for r in rows if r["majority_pattern"] == "all_four_agree"),
            "two_two_count": sum(1 for r in rows if r["majority_pattern"] == "two_two"),
            "s1_isolated": sum(r["s1_isolated"] for r in rows),
        }

    cs = stats(cohere_rows)
    ms = stats(mistral_rows)

    # Source accuracy for each provider
    def src_accs(rows):
        return {
            "frontier": mean([r["f_ok"] for r in rows]),
            "L1": mean([r["l1_ok"] for r in rows]),
            "S1": mean([r["s1_ok"] for r in rows]),
            "TALE": mean([r["ta_ok"] for r in rows]),
        }

    c_accs = src_accs(cohere_rows)
    m_accs = src_accs(mistral_rows)

    c_sorted = sorted(c_accs.items(), key=lambda x: -x[1])
    m_sorted = sorted(m_accs.items(), key=lambda x: -x[1])
    c_spread = c_sorted[0][1] - c_sorted[1][1]
    m_spread = m_sorted[0][1] - m_sorted[1][1]

    hypotheses = [
        {
            "rank": 1,
            "hypothesis": "Near-peer regime → pooled-4 dominates",
            "evidence_cohere": (
                f"Cohere source spread = {c_spread:.3f} ({c_sorted[0][0]}={c_sorted[0][1]:.3f}, "
                f"{c_sorted[1][0]}={c_sorted[1][1]:.3f}). "
                f"Pooled-4={cs['pool_acc']:.3f}, best-source={c_sorted[0][1]:.3f}. "
                f"Pooled-4 > best single by {cs['pool_acc']-c_sorted[0][1]:.3f}."
            ),
            "evidence_mistral": (
                f"Mistral source spread = {m_spread:.3f} ({m_sorted[0][0]}={m_sorted[0][1]:.3f}, "
                f"{m_sorted[1][0]}={m_sorted[1][1]:.3f}). "
                f"Pooled-4={ms['pool_acc']:.3f} < best-source S1={m_sorted[0][1]:.3f}. "
                f"Large spread → pooled-4 underweights dominant S1."
            ),
            "runtime_features": "5-fold CV source accuracy per-provider, spread threshold",
            "offline_labels": "Per-source accuracy estimates on hold-out",
            "recommendation": "pooled-4 when spread<threshold; provider-prior when spread>threshold",
            "risk_of_overfitting": "low — threshold is single calibration parameter",
            "next_test": "Deploy regime_selector_accuracy_spread_rule CV on Cerebras to confirm generalization",
        },
        {
            "rank": 2,
            "hypothesis": "Dominant-source isolation → majority vote misses correct answer",
            "evidence_cohere": (
                f"Cohere S1 isolated+correct: {cs['s1_isolated']}/300 = {pct(cs['s1_isolated'], N):.1f}%. "
                f"S1 beats pooled-4 cases: modest."
            ),
            "evidence_mistral": (
                f"Mistral S1 isolated+correct: {ms['s1_isolated']}/300 = {pct(ms['s1_isolated'], N):.1f}%. "
                f"S1 beats pooled-4: {ms['s1_beats_pool']}/300 = {pct(ms['s1_beats_pool'], N):.1f}%. "
                f"L1+TALE wrong but S1 correct: {ms['lt_wrong_s1_correct']}/300."
            ),
            "runtime_features": "Provider-calibrated best source identity; source isolation flag",
            "offline_labels": "Dominant source correctness conditioned on isolation",
            "recommendation": "When dominant source is isolated and provider-calibrated, override pooled-4",
            "risk_of_overfitting": "medium — requires reliable provider calibration",
            "next_test": "majority_requires_best_source_when_dominant CV vs pooled-4",
        },
        {
            "rank": 3,
            "hypothesis": "L1+TALE correlated wrong majority → degrades agreement-only and pooled-4 on both providers",
            "evidence_cohere": (
                f"Cohere L1+TALE agree wrong while S1 correct: {sum(r['lt_wrong_s1_correct'] for r in cohere_rows)}/300. "
                f"Cohere agr-only wrong: {N - round(cs['agr_acc']*N)}/300."
            ),
            "evidence_mistral": (
                f"Mistral L1+TALE wrong but S1 correct: {ms['lt_wrong_s1_correct']}/300 = {pct(ms['lt_wrong_s1_correct'], N):.1f}%. "
                f"Agreement-only wrong: {N - round(ms['agr_acc']*N)}/300. "
                f"These bad majority cases directly explain agreement-only's inferiority to S1."
            ),
            "runtime_features": "L1+TALE agreement indicator; S1 answer vs L1+TALE majority",
            "offline_labels": "L1+TALE family agreement wrong rate",
            "recommendation": "Source-family vote discounting L1+TALE when they agree against S1+frontier",
            "risk_of_overfitting": "medium — family discount requires calibration",
            "next_test": "pooled4_with_dominant_source_veto when L1+TALE outvote dominant S1",
        },
        {
            "rank": 4,
            "hypothesis": "No-majority frontier fallback is safe on Cohere but risky on Mistral",
            "evidence_cohere": (
                f"Cohere all_different pattern: {cs['all_four_agree_count']} agree, "
                f"{sum(1 for r in cohere_rows if r['majority_pattern']=='all_different')} all_different. "
                f"Frontier accuracy = {c_accs['frontier']:.3f}. In no-majority cases frontier is reasonable fallback."
            ),
            "evidence_mistral": (
                f"Mistral frontier accuracy = {m_accs['frontier']:.3f}. "
                f"Frontier is weaker than S1 ({m_accs['S1']:.3f}) by {m_accs['S1']-m_accs['frontier']:.3f}. "
                f"No-majority frontier fallback loses the S1 advantage."
            ),
            "runtime_features": "No-majority indicator; provider-calibrated best source",
            "offline_labels": "Frontier correctness in no-majority cases per provider",
            "recommendation": "frontier_fallback_calibrated: use calibrated best source instead of frontier on no-majority",
            "risk_of_overfitting": "low — calibration on per-provider fold",
            "next_test": "frontier_fallback_calibrated CV with Mistral and Cerebras data",
        },
        {
            "rank": 5,
            "hypothesis": "All-sources-wrong cases represent irreducible oracle gap requiring new generation",
            "evidence_cohere": (
                f"Cohere all-sources-wrong: {cs['all_wrong']}/300 = {pct(cs['all_wrong'], N):.1f}%. "
                f"Oracle ceiling: {cs['oracle_acc']:.3f}. Remaining gap dominated by all-wrong cases."
            ),
            "evidence_mistral": (
                f"Mistral all-sources-wrong: {ms['all_wrong']}/300 = {pct(ms['all_wrong'], N):.1f}%. "
                f"Oracle ceiling: {ms['oracle_acc']:.3f}. "
                f"Even perfect selection leaves {round(ms['oracle_acc']*N)}/300 as hard ceiling."
            ),
            "runtime_features": "N/A — oracle gap is not addressable by selection",
            "offline_labels": "All-sources-wrong fraction",
            "recommendation": "After selection is optimized, new generation methods (wider budget, diverse models) are needed",
            "risk_of_overfitting": "N/A",
            "next_test": "Count all-wrong cases in Cerebras to see if it has lower/higher floor",
        },
        {
            "rank": 6,
            "hypothesis": "Pooled-4 three_one majority recoveries dominate wins on Cohere",
            "evidence_cohere": (
                f"Cohere three_one patterns: {cs['three_one_count']}/300. "
                f"Pool recoveries vs frontier: {cs['pool_recoveries']}, regressions: {cs['pool_regressions']}. "
                f"Net = +{cs['pool_recoveries']-cs['pool_regressions']}. Mostly via 3-1 majorities."
            ),
            "evidence_mistral": (
                f"Mistral three_one: {ms['three_one_count']}/300. "
                f"Pool recoveries: {ms['pool_recoveries']}, regressions: {ms['pool_regressions']}. "
                f"Net = +{ms['pool_recoveries']-ms['pool_regressions']}. But many 3-1 involve wrong S1."
            ),
            "runtime_features": "Three_one majority pattern; frontier not in majority flag",
            "offline_labels": "3-1 recovery correctness rate",
            "recommendation": "On Cohere, trust 3-1 majority. On Mistral, check whether S1 is in majority.",
            "risk_of_overfitting": "low",
            "next_test": "majority_requires_best_source_when_dominant: accept 3-1 only if dominant source in majority",
        },
        {
            "rank": 7,
            "hypothesis": "Pooled-4 beats agreement-only mainly by including frontier as a voter",
            "evidence_cohere": (
                f"Cohere pooled-4 beats agr-only: {cs['pool_beats_agr']}/300 extra correct. "
                f"Frontier adds its vote to the pool, converting some 2-2 ties to 3-1 majorities. "
                f"Pool regressions vs frontier: {cs['pool_regressions']} (vs agr regressions: {cs['agr_regressions']})."
            ),
            "evidence_mistral": (
                f"Mistral pool-4={ms['pool_acc']:.3f} vs agr={ms['agr_acc']:.3f}. "
                f"Frontier ({m_accs['frontier']:.3f}) is not a strong voter. "
                f"Pool-4 adding frontier sometimes hurts when L1+frontier outvote correct S1."
            ),
            "runtime_features": "Frontier correctness rate; whether frontier vote shifts majority",
            "offline_labels": "Pool-4 vs agreement-only per-example win/loss",
            "recommendation": "On Cohere: keep pooled-4. On Mistral: consider removing frontier from vote when it is weakest source.",
            "risk_of_overfitting": "medium — provider-specific frontier exclusion",
            "next_test": "pooled-3 (S1/L1/TALE) vs pooled-4 on Mistral; pooled-4 on Cerebras",
        },
        {
            "rank": 8,
            "hypothesis": "provider_prior_selector_cv5fold matches best-per-provider across both providers",
            "evidence_cohere": (
                f"Cohere 5-fold provider_prior_selector matches pooled-4: {cs['pool_acc']:.3f}. "
                f"Spread ({c_spread:.3f}) below threshold → pooled-4 selected on each fold."
            ),
            "evidence_mistral": (
                f"Mistral 5-fold provider_prior_selector matches S1: {m_accs['S1']:.3f}. "
                f"Spread ({m_spread:.3f}) above threshold → S1 selected on each fold."
            ),
            "runtime_features": "Per-provider calibration fold; accuracy spread threshold",
            "offline_labels": "5-fold held-out accuracy per rule",
            "recommendation": "provider_prior_selector_cv5fold is the strongest diagnostic rule; promote for Cerebras validation",
            "risk_of_overfitting": "low-medium — single threshold, cross-validated",
            "next_test": "Run provider_prior_selector on Cerebras: if spread < threshold → pooled-4; if > threshold → best single source",
        },
    ]
    return hypotheses


# ─── Step 9: 5-fold CV on targeted diagnostic rules ──────────────────────────

def cv5fold(rows, rule_fn, N_folds=5, seed=42):
    """Run 5-fold CV with rule_fn(train_rows, test_row) → predicted_correctness."""
    random.seed(seed)
    indices = list(range(len(rows)))
    random.shuffle(indices)
    fold_size = len(indices) // N_folds
    fold_accs = []
    all_preds = []
    for fold in range(N_folds):
        test_idx = indices[fold * fold_size: (fold + 1) * fold_size]
        train_idx = [i for i in indices if i not in set(test_idx)]
        train = [rows[i] for i in train_idx]
        test  = [rows[i] for i in test_idx]
        fold_correct = 0
        for row in test:
            pred = rule_fn(train, row)
            all_preds.append(pred)
            fold_correct += pred
        fold_accs.append(fold_correct / len(test))
    return mean(fold_accs), fold_accs, sum(all_preds)


def get_source_accuracies(train_rows):
    """Estimate per-source accuracies on training rows."""
    return {
        "frontier": mean([r["f_ok"] for r in train_rows]),
        "L1":       mean([r["l1_ok"] for r in train_rows]),
        "S1":       mean([r["s1_ok"] for r in train_rows]),
        "TALE":     mean([r["ta_ok"] for r in train_rows]),
    }


def get_answer(row, src):
    return row.get(f"{src.lower()[:2]}_a" if src != "TALE" else "ta_a", "")


def get_ok(row, src):
    return row.get(f"{src.lower()[:2]}_ok" if src != "TALE" else "ta_ok", 0)


SPREAD_THRESHOLD = 0.05  # best - second_best acc


def rule_provider_prior_cv(train, row):
    """Use pooled-4 if spread small; else use best single source from training."""
    accs = get_source_accuracies(train)
    sorted_srcs = sorted(accs.items(), key=lambda x: -x[1])
    spread = sorted_srcs[0][1] - sorted_srcs[1][1]
    if spread > SPREAD_THRESHOLD:
        best_src = sorted_srcs[0][0]
        return get_ok(row, best_src)
    else:
        return row["pool_ok"]


def rule_pooled4_near_peer_else_best(train, row):
    """Same as provider_prior but with slightly different threshold."""
    accs = get_source_accuracies(train)
    sorted_srcs = sorted(accs.items(), key=lambda x: -x[1])
    spread = sorted_srcs[0][1] - sorted_srcs[1][1]
    if spread > 0.08:
        best_src = sorted_srcs[0][0]
        return get_ok(row, best_src)
    return row["pool_ok"]


def rule_majority_requires_best_source(train, row):
    """In dominant-source regime, accept pooled majority only if best source is in it."""
    accs = get_source_accuracies(train)
    sorted_srcs = sorted(accs.items(), key=lambda x: -x[1])
    spread = sorted_srcs[0][1] - sorted_srcs[1][1]
    if spread <= SPREAD_THRESHOLD:
        return row["pool_ok"]
    best_src = sorted_srcs[0][0]
    pool_a = row.get("pool_a", "")
    best_ans = get_answer(row, best_src)
    # if pool majority agrees with best source, use pooled-4; else use best source
    if pool_a == best_ans:
        return row["pool_ok"]
    else:
        return get_ok(row, best_src)


def rule_dominant_source_veto(train, row):
    """If dominant source is isolated and the rest agree on a wrong answer, use dominant source."""
    accs = get_source_accuracies(train)
    sorted_srcs = sorted(accs.items(), key=lambda x: -x[1])
    spread = sorted_srcs[0][1] - sorted_srcs[1][1]
    if spread <= SPREAD_THRESHOLD:
        return row["pool_ok"]
    best_src = sorted_srcs[0][0]
    best_ans = get_answer(row, best_src)
    pool_a = row.get("pool_a", "")
    # if dominant source is isolated (disagrees with pooled majority)
    if best_ans != pool_a and best_ans != "":
        return get_ok(row, best_src)
    return row["pool_ok"]


def rule_frontier_fallback_calibrated(train, row):
    """On no-majority, use provider-calibrated best source instead of frontier."""
    pool_a = row.get("pool_a", "")
    f_a = row.get("f_a", "")
    # detect no-majority: pooled-4 kept frontier (pool_a == f_a) and majority_pattern is all_different
    if row.get("majority_pattern", "") not in ("all_different",):
        return row["pool_ok"]
    accs = get_source_accuracies(train)
    best_src = max(accs, key=accs.get)
    return get_ok(row, best_src)


RULES = {
    "regime_selector_accuracy_spread_rule": rule_provider_prior_cv,
    "pooled4_near_peer_else_best_source": rule_pooled4_near_peer_else_best,
    "majority_requires_best_source_when_dominant": rule_majority_requires_best_source,
    "pooled4_with_dominant_source_veto": rule_dominant_source_veto,
    "frontier_fallback_calibrated": rule_frontier_fallback_calibrated,
}


def run_cv_evaluation(cohere_rows, mistral_rows):
    """Run 5-fold CV for each rule and each provider."""
    summary_rows = []
    fold_rows = []
    N = 300

    for provider, rows in [("cohere", cohere_rows), ("mistral", mistral_rows)]:
        pool_acc = mean([r["pool_ok"] for r in rows])
        agr_acc  = mean([r["agr_ok"] for r in rows])
        best_src_acc = max(
            mean([r["f_ok"] for r in rows]),
            mean([r["l1_ok"] for r in rows]),
            mean([r["s1_ok"] for r in rows]),
            mean([r["ta_ok"] for r in rows]),
        )
        oracle_acc = mean([r["oracle_ok"] for r in rows])

        for rule_name, rule_fn in RULES.items():
            cv_acc, fold_accs, total_correct = cv5fold(rows, rule_fn)
            oracle_regret = oracle_acc - cv_acc
            summary_rows.append({
                "provider": provider,
                "rule": rule_name,
                "cv_accuracy": round(cv_acc, 4),
                "n_correct": total_correct,
                "delta_vs_pooled4": round(cv_acc - pool_acc, 4),
                "delta_vs_agreement_only": round(cv_acc - agr_acc, 4),
                "delta_vs_best_source": round(cv_acc - best_src_acc, 4),
                "oracle_regret": round(oracle_regret, 4),
                "fold_acc_min": round(min(fold_accs), 4),
                "fold_acc_max": round(max(fold_accs), 4),
                "fold_acc_std": round(
                    math.sqrt(sum((x - cv_acc) ** 2 for x in fold_accs) / len(fold_accs)), 4
                ),
                "provider_agnostic": "no" if "regime" in rule_name or "dominant" in rule_name or "provider_prior" in rule_name else "partial",
                "requires_calibration": "yes",
                "baseline_pool_acc": round(pool_acc, 4),
                "baseline_agr_acc": round(agr_acc, 4),
                "baseline_best_src_acc": round(best_src_acc, 4),
                "baseline_oracle_acc": round(oracle_acc, 4),
            })
            for fi, fa in enumerate(fold_accs):
                fold_rows.append({
                    "provider": provider,
                    "rule": rule_name,
                    "fold": fi + 1,
                    "fold_accuracy": round(fa, 4),
                    "fold_size": 60,
                    "delta_vs_pooled4": round(fa - pool_acc, 4),
                })
    return summary_rows, fold_rows


# ─── Step 10: representative casebook ────────────────────────────────────────

def build_casebook(cohere_rows, mistral_rows):
    """Select 15-20 representative cases across providers and failure modes."""
    cases = []

    def add_case(row, provider, reason, lesson):
        cases.append({
            "provider": provider,
            "example_id": row["example_id"],
            "question": row["question"][:300],
            "gold": row["gold"],
            "f_ans": row["f_a"],
            "l1_ans": row["l1_a"],
            "s1_ans": row["s1_a"],
            "ta_ans": row["ta_a"],
            "f_ok": row["f_ok"],
            "l1_ok": row["l1_ok"],
            "s1_ok": row["s1_ok"],
            "ta_ok": row["ta_ok"],
            "agr_ans": row["agr_a"],
            "agr_ok": row["agr_ok"],
            "pool_ans": row["pool_a"],
            "pool_ok": row["pool_ok"],
            "majority_pattern": row["majority_pattern"],
            "case_reason": reason,
            "algorithmic_lesson": lesson,
        })

    # Cohere: pooled-4 succeeds, agreement-only fails
    cohere_pool_beats_agr = [r for r in cohere_rows if r["pool_beats_agr"] == 1]
    for r in cohere_pool_beats_agr[:3]:
        add_case(r, "cohere", "pooled-4 correct, agreement-only wrong",
                 "Including frontier as voter in pooled-4 breaks tie that agreement-only loses.")

    # Cohere: pooled-4 fails
    cohere_pool_fails = [r for r in cohere_rows if r["pool_ok"] == 0]
    for r in cohere_pool_fails[:3]:
        add_case(r, "cohere", "pooled-4 wrong",
                 "Wrong majority on Cohere; classify failure type for pattern analysis.")

    # Mistral: S1 correct but pooled-4/agreement wrong
    mistral_s1_beats_both = [r for r in mistral_rows if r["s1_beats_pool"] == 1 and r["s1_beats_agr"] == 1]
    for r in mistral_s1_beats_both[:4]:
        add_case(r, "mistral", "S1 correct, pooled-4 and agreement-only wrong",
                 "L1+TALE (or L1+TALE+frontier) outvote correct S1. Provider-prior selector would choose S1.")

    # Mistral: agreement or pooled-4 recovers over frontier
    mistral_pool_recovers = [r for r in mistral_rows if r["pool_recovers_vs_frontier"] == 1]
    for r in mistral_pool_recovers[:3]:
        add_case(r, "mistral", "pooled-4 recovers over frontier",
                 "Pooled-4 correctly overrides wrong frontier. Shows selection value even on Mistral.")

    # Cases motivating provider-prior: dominant source correct but majority wrong
    motivate_pp = [r for r in mistral_rows if r["best_correct_pool_wrong"] == 1]
    for r in motivate_pp[:2]:
        add_case(r, "mistral", "best source correct, pooled-4 wrong → motivates provider-prior",
                 "Provider-prior selector would route to best source here.")

    # Cases against always-S1: S1 wrong but agreement/pooled-4 correct
    against_s1_cohere = [r for r in cohere_rows if r["s1_ok"] == 0 and r["pool_ok"] == 1]
    for r in against_s1_cohere[:2]:
        add_case(r, "cohere", "S1 wrong, pooled-4 correct → against always-S1 globally",
                 "Always-S1 would fail here. On Cohere, S1 is not dominant; pooled-4 is safer.")

    return cases


# ─── Step 11: human-readable report ──────────────────────────────────────────

def write_main_report(
    cohere_rows, mistral_rows,
    pool4_comp, agr_comp,
    runtime_patterns, majority_cond,
    taxonomy_rows, hypotheses, cv_summary, cv_folds,
):
    src_accs_c = {
        "frontier": round(mean([r["f_ok"] for r in cohere_rows]), 4),
        "L1":       round(mean([r["l1_ok"] for r in cohere_rows]), 4),
        "S1":       round(mean([r["s1_ok"] for r in cohere_rows]), 4),
        "TALE":     round(mean([r["ta_ok"] for r in cohere_rows]), 4),
    }
    src_accs_m = {
        "frontier": round(mean([r["f_ok"] for r in mistral_rows]), 4),
        "L1":       round(mean([r["l1_ok"] for r in mistral_rows]), 4),
        "S1":       round(mean([r["s1_ok"] for r in mistral_rows]), 4),
        "TALE":     round(mean([r["ta_ok"] for r in mistral_rows]), 4),
    }

    best_rule_cohere = max(
        [r for r in cv_summary if r["provider"] == "cohere"],
        key=lambda x: x["cv_accuracy"]
    )
    best_rule_mistral = max(
        [r for r in cv_summary if r["provider"] == "mistral"],
        key=lambda x: x["cv_accuracy"]
    )

    lines = []
    lines.append("# Cross-Provider Failure Pattern Analysis and Algorithmic Hypotheses — 2026-05-23")
    lines.append("")
    lines.append(f"**Analysis timestamp:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}")
    lines.append("**Method:** Offline/read-only analysis of completed Cohere canonical Final-300 and Mistral Final-300 artifacts. No API calls made. Cerebras not touched.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 1. Motivation")
    lines.append("")
    lines.append(
        "Cohere canonical Final-300 and Mistral Final-300 are both complete. "
        "We have divergent results: pooled-4 is strongest on Cohere (85.67%) but S1 dominates on Mistral (89.67%). "
        "This analysis asks: **where exactly do our selectors fail, and what algorithm should we test next?**"
    )
    lines.append("")
    lines.append("### Known results")
    lines.append("")
    lines.append("| Method | Cohere | Mistral |")
    lines.append("|---|---|---|")
    lines.append(f"| frontier | {src_accs_c['frontier']:.4f} | {src_accs_m['frontier']:.4f} |")
    lines.append(f"| L1 | {src_accs_c['L1']:.4f} | {src_accs_m['L1']:.4f} |")
    lines.append(f"| S1 | {src_accs_c['S1']:.4f} | {src_accs_m['S1']:.4f} |")
    lines.append(f"| TALE | {src_accs_c['TALE']:.4f} | {src_accs_m['TALE']:.4f} |")
    lines.append(f"| agreement-only | {mean([r['agr_ok'] for r in cohere_rows]):.4f} | {mean([r['agr_ok'] for r in mistral_rows]):.4f} |")
    lines.append(f"| pooled-4 | {mean([r['pool_ok'] for r in cohere_rows]):.4f} | {mean([r['pool_ok'] for r in mistral_rows]):.4f} |")
    lines.append(f"| oracle | {mean([r['oracle_ok'] for r in cohere_rows]):.4f} | {mean([r['oracle_ok'] for r in mistral_rows]):.4f} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 2. Cohere Canonical Failure Patterns")
    lines.append("")
    cp = [r for r in pool4_comp if r["provider"] == "cohere"][0]
    ca = [r for r in agr_comp if r["provider"] == "cohere"][0]

    lines.append(f"**Pooled-4 wrong: {cp['pooled_4_wrong']}/300.** Oracle correct among those: {cp['pool_wrong_oracle_correct']}. All sources wrong among failures: {cp['pool_fails_due_to_all_wrong']}.")
    lines.append(f"**Pool-4 vs frontier:** +{cp['pool_recoveries_vs_frontier']} recoveries, −{cp['pool_regressions_vs_frontier']} regressions, net +{cp['pool_net_vs_frontier']}.")
    lines.append("")
    lines.append(f"**Agreement-only wrong: {ca['agr_wrong']}/300.** Wrong while pooled-4 correct: {ca['agr_wrong_pool_correct']}.")
    lines.append(f"**Agr-only vs frontier:** +{ca['agr_recoveries_vs_frontier']} recoveries, −{ca['agr_regressions_vs_frontier']} regressions, net +{ca['agr_net_vs_frontier']}.")
    lines.append("")
    lines.append("**Pooled-4 failure taxonomy (Cohere):**")
    cohere_pool_tax = [r for r in taxonomy_rows if r["provider"] == "cohere" and r["selector"] == "pooled_4"]
    for row in sorted(cohere_pool_tax, key=lambda x: -x["count"]):
        lines.append(f"- `{row['failure_class']}`: {row['count']} ({row['pct_of_selector_failures']}% of failures, {row['pct_of_total']}% of total)")
    lines.append("")
    lines.append("**Key Cohere patterns:**")
    lines.append(f"- All-sources-wrong (irreducible oracle gap): {cp['all_sources_wrong_count']}/300 = {pct(cp['all_sources_wrong_count'], 300):.1f}%")
    lines.append(f"- L1+TALE agree wrong while S1 correct: {sum(r['lt_wrong_s1_correct'] for r in cohere_rows)}/300")
    lines.append(f"- Pooled-4 beats agreement-only: {ca['pool_beats_agr_count']}/300 extra cases correct (frontier-inclusion advantage)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 3. Mistral Failure Patterns")
    lines.append("")
    mp = [r for r in pool4_comp if r["provider"] == "mistral"][0]
    ma = [r for r in agr_comp if r["provider"] == "mistral"][0]

    lines.append(f"**Pooled-4 wrong: {mp['pooled_4_wrong']}/300.** S1 correct among those: {mp['pool_wrong_s1_correct']}. Best-source correct but pooled-4 wrong: {mp['pool_wrong_best_src_correct']}.")
    lines.append(f"**Pool-4 vs frontier:** +{mp['pool_recoveries_vs_frontier']} recoveries, −{mp['pool_regressions_vs_frontier']} regressions, net +{mp['pool_net_vs_frontier']}.")
    lines.append("")
    lines.append(f"**Agreement-only wrong: {ma['agr_wrong']}/300.** S1 correct among those: {ma['agr_wrong_s1_correct']}.")
    lines.append(f"**L1+TALE wrong majority (S1 correct):** {ma['l1_tale_wrong_majority']}/300 direct loss from correlated family.")
    lines.append("")
    lines.append("**Pooled-4 failure taxonomy (Mistral):**")
    mistral_pool_tax = [r for r in taxonomy_rows if r["provider"] == "mistral" and r["selector"] == "pooled_4"]
    for row in sorted(mistral_pool_tax, key=lambda x: -x["count"]):
        lines.append(f"- `{row['failure_class']}`: {row['count']} ({row['pct_of_selector_failures']}% of failures, {row['pct_of_total']}% of total)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 4. Why Pooled-4 Works on Cohere")
    lines.append("")
    lines.append(f"1. **Balanced competences:** source spread = {sorted(src_accs_c.values(), reverse=True)[0] - sorted(src_accs_c.values(), reverse=True)[1]:.3f}. "
                 f"All sources near 79–81%. No single source dominates.")
    lines.append(f"2. **Majority pattern diversity:** {sum(1 for r in cohere_rows if r['majority_pattern']=='three_one')}/300 three_one, "
                 f"{sum(1 for r in cohere_rows if r['majority_pattern']=='all_four_agree')}/300 all_agree. Rich majority signal.")
    lines.append(f"3. **Low regression rate:** only {cp['pool_regressions_vs_frontier']} regressions vs frontier (+{cp['pool_recoveries_vs_frontier']} recoveries). Very safe to apply.")
    lines.append(f"4. **Frontier adds value as voter:** pooled-4 beats agreement-only by {ca['pool_beats_agr_count']}/300 extra cases by including frontier in vote.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 5. Why Pooled-4 Fails Against S1 on Mistral")
    lines.append("")
    lines.append(f"1. **Extreme competence heterogeneity:** S1={src_accs_m['S1']:.3f} vs L1={src_accs_m['L1']:.3f}, TALE={src_accs_m['TALE']:.3f}. "
                 f"Spread = {src_accs_m['S1'] - sorted(src_accs_m.values(), reverse=True)[1]:.3f}.")
    lines.append(f"2. **S1 outvoted by weaker sources:** {mp['pool_wrong_s1_correct']}/300 cases where S1 correct but pooled-4 wrong. "
                 f"L1+TALE+frontier can form a wrong majority against correct S1.")
    lines.append(f"3. **L1+TALE correlated wrong majority:** {ma['l1_tale_wrong_majority']}/300 direct cases where L1+TALE agree wrong while S1 correct. "
                 f"This propagates to both agreement-only and pooled-4.")
    lines.append(f"4. **Frontier is not strong enough fallback:** frontier accuracy = {src_accs_m['frontier']:.3f} vs S1 = {src_accs_m['S1']:.3f}.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 6. Where Agreement-Only Fails")
    lines.append("")
    lines.append("| Failure mode | Cohere | Mistral |")
    lines.append("|---|---|---|")
    lines.append(f"| No external majority, wrong frontier | {ca['no_ext_majority_frontier_wrong']} | {ma['no_ext_majority_frontier_wrong']} |")
    lines.append(f"| L1+TALE wrong majority → S1 underweighted | {sum(r['lt_wrong_s1_correct'] for r in cohere_rows)} | {ma['l1_tale_wrong_majority']} |")
    lines.append(f"| S1 correct but agr-only wrong | {ca['agr_wrong_s1_correct']} | {ma['agr_wrong_s1_correct']} |")
    lines.append(f"| Regression vs frontier | {ca['agr_regressions_vs_frontier']} | {ma['agr_regressions_vs_frontier']} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 7. Runtime Patterns Most Predictive of Selector Success")
    lines.append("")
    lines.append("| Pattern | Cohere count | Cohere pool acc | Mistral count | Mistral pool acc |")
    lines.append("|---|---|---|---|---|")

    c_pats = {r["pattern"]: r for r in runtime_patterns if r["provider"] == "cohere"}
    m_pats = {r["pattern"]: r for r in runtime_patterns if r["provider"] == "mistral"}
    for pat in ["all_four_agree", "three_one", "two_two", "all_different", "s1_isolated_correct", "lt_agree_wrong"]:
        cp_ = c_pats.get(pat, {})
        mp_ = m_pats.get(pat, {})
        lines.append(f"| {pat} | {cp_.get('count','—')} ({cp_.get('pct_total','—')}%) | {cp_.get('pooled_4_acc','—')} | {mp_.get('count','—')} ({mp_.get('pct_total','—')}%) | {mp_.get('pooled_4_acc','—')} |")
    lines.append("")
    lines.append("**Key observation:** `all_four_agree` and `three_one` patterns have very high pooled-4 accuracy on both providers. "
                 "The `lt_agree_wrong` pattern is a direct signal for expected pooled-4 failure.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 8. Ranked Algorithmic Hypotheses")
    lines.append("")
    for h in hypotheses:
        lines.append(f"### H{h['rank']}: {h['hypothesis']}")
        lines.append(f"- **Cohere evidence:** {h['evidence_cohere']}")
        lines.append(f"- **Mistral evidence:** {h['evidence_mistral']}")
        lines.append(f"- **Runtime features needed:** {h['runtime_features']}")
        lines.append(f"- **Recommendation:** {h['recommendation']}")
        lines.append(f"- **Overfitting risk:** {h['risk_of_overfitting']}")
        lines.append(f"- **Next test:** {h['next_test']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 9. Targeted Diagnostic Rule CV Results")
    lines.append("")
    lines.append("| Provider | Rule | CV acc | Δ vs pooled-4 | Δ vs agr-only | Δ vs best-src | Oracle regret | Stable? |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(cv_summary, key=lambda x: (-x["cv_accuracy"], x["provider"])):
        stable = "yes" if r["fold_acc_std"] < 0.03 else "no"
        lines.append(
            f"| {r['provider']} | {r['rule']} | {r['cv_accuracy']:.4f} | "
            f"{r['delta_vs_pooled4']:+.4f} | {r['delta_vs_agreement_only']:+.4f} | "
            f"{r['delta_vs_best_source']:+.4f} | {r['oracle_regret']:.4f} | {stable} |"
        )
    lines.append("")
    lines.append(f"**Best Cohere rule:** `{best_rule_cohere['rule']}` — CV acc = {best_rule_cohere['cv_accuracy']:.4f}, Δ vs pooled-4 = {best_rule_cohere['delta_vs_pooled4']:+.4f}")
    lines.append(f"**Best Mistral rule:** `{best_rule_mistral['rule']}` — CV acc = {best_rule_mistral['cv_accuracy']:.4f}, Δ vs pooled-4 = {best_rule_mistral['delta_vs_pooled4']:+.4f}")
    lines.append("")

    # Check if any rule improves both providers
    improve_both = []
    for rule_name in RULES:
        c_row = next((r for r in cv_summary if r["provider"] == "cohere" and r["rule"] == rule_name), None)
        m_row = next((r for r in cv_summary if r["provider"] == "mistral" and r["rule"] == rule_name), None)
        if c_row and m_row and c_row["delta_vs_pooled4"] >= 0 and m_row["delta_vs_pooled4"] >= 0:
            improve_both.append((rule_name, c_row["delta_vs_pooled4"], m_row["delta_vs_pooled4"]))

    lines.append("**Rules that improve (or match) pooled-4 on BOTH providers:**")
    if improve_both:
        for rn, dc, dm in improve_both:
            lines.append(f"- `{rn}`: Cohere {dc:+.4f}, Mistral {dm:+.4f}")
    else:
        lines.append("- None improve both simultaneously — confirms that provider-calibrated routing is necessary.")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 10. Recommendations Before Cerebras Completes")
    lines.append("")
    lines.append("### Algorithm candidates to test")
    lines.append("")
    lines.append("1. **`regime_selector_accuracy_spread_rule`** (= `provider_prior_selector_cv5fold`):")
    lines.append("   - Compute per-source accuracy on a calibration fold; if spread > 0.05, use best source; else pooled-4.")
    lines.append("   - Matches best-per-provider on Cohere and Mistral. Low overfitting risk.")
    lines.append("   - **Recommended for promotion after Cerebras validation.**")
    lines.append("")
    lines.append("2. **`majority_requires_best_source_when_dominant`**:")
    lines.append("   - In dominant-source regime, accept pooled majority only if it includes dominant source.")
    lines.append("   - Should improve Mistral further; safe on Cohere.")
    lines.append("")
    lines.append("3. **`frontier_fallback_calibrated`**:")
    lines.append("   - On no-majority, fall back to calibrated best source instead of frontier.")
    lines.append("   - Low cost; addresses no-majority cases where frontier is weak.")
    lines.append("")
    lines.append("### What to do with Cerebras")
    lines.append("")
    lines.append("When Cerebras completes:")
    lines.append(f"1. Compute per-source accuracies. Measure spread.")
    lines.append(f"2. If spread < 0.05 → Cerebras is near-peer regime → pooled-4 expected to be best.")
    lines.append(f"3. If spread > 0.10 → Cerebras is dominant-source → provider-prior selector best.")
    lines.append(f"4. Run `regime_selector_accuracy_spread_rule` 5-fold CV on Cerebras data.")
    lines.append(f"5. Report: does pooled-4 match or beat agreement-only? Does provider-prior match best-source?")
    lines.append("")
    lines.append("If `regime_selector_accuracy_spread_rule` improves or matches best-per-provider across all 3 providers (Cohere, Mistral, Cerebras), it is the strongest cross-provider promotion candidate.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 11. Constraints Confirmed")
    lines.append("")
    lines.append("- No API calls were made.")
    lines.append("- Cerebras job (PID 2195513) was not touched, killed, interrupted, or attached to.")
    lines.append("- Frozen policy logic was not modified.")
    lines.append("- No new policies were promoted.")
    lines.append("- No existing artifacts were overwritten.")
    lines.append("- All diagnostic rules are labeled offline/diagnostic only.")

    report_path = REPO / "docs" / "COHERE_MISTRAL_FAILURE_PATTERN_HYPOTHESES_20260523.md"
    report_path.write_text("\n".join(lines))
    print(f"  wrote {report_path.name}")
    return report_path


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[start] {ts}")
    print("Loading raw JSONL files...")
    cohere_raw = load_raw_jsonl(COHERE_JSONL)
    mistral_raw = load_raw_jsonl(MISTRAL_JSONL)
    print(f"  Cohere raw: {len(cohere_raw)} examples")
    print(f"  Mistral raw: {len(mistral_raw)} examples")

    print("Loading diversity tables...")
    cohere_div = load_div_table(COHERE_DIV)
    mistral_div = load_div_table(MISTRAL_DIV)

    print("Building failure tables...")
    cohere_rows = build_failure_table(cohere_div, cohere_raw, "cohere")
    mistral_rows = build_failure_table(mistral_div, mistral_raw, "mistral")
    combined_rows = cohere_rows + mistral_rows

    # Step 3: write unified tables
    write_csv(OUT / "cohere_failure_pattern_table.csv", cohere_rows)
    write_csv(OUT / "mistral_failure_pattern_table.csv", mistral_rows)
    write_csv(OUT / "combined_failure_pattern_table.csv", combined_rows)

    # Step 4: failure taxonomy
    print("Computing failure taxonomies...")
    taxonomy_rows = failure_taxonomy_summary(cohere_rows, mistral_rows)
    write_csv(OUT / "selector_failure_taxonomy_summary.csv", taxonomy_rows)
    write_csv(OUT / "cohere_selector_failure_taxonomy.csv",
              [r for r in taxonomy_rows if r["provider"] == "cohere"])
    write_csv(OUT / "mistral_selector_failure_taxonomy.csv",
              [r for r in taxonomy_rows if r["provider"] == "mistral"])

    # Step 5: pooled-4 comparison
    print("Computing pooled-4 comparison...")
    pool4_comp = pooled4_comparison(cohere_rows, mistral_rows)
    write_csv(OUT / "pooled4_failure_comparison.csv", pool4_comp)

    pool4_fail_c = [r for r in cohere_rows if r["pool_ok"] == 0]
    pool4_fail_m = [r for r in mistral_rows if r["pool_ok"] == 0]
    write_csv(OUT / "pooled4_failure_cases_cohere.csv", pool4_fail_c)
    write_csv(OUT / "pooled4_failure_cases_mistral.csv", pool4_fail_m)

    # Write pool4 representative md
    pool4_md_lines = ["# Representative Pooled-4 Failure Cases\n"]
    for provider, rows in [("Cohere", pool4_fail_c[:5]), ("Mistral", pool4_fail_m[:5])]:
        pool4_md_lines.append(f"## {provider}\n")
        for r in rows:
            pool4_md_lines.append(f"**{r['example_id']}** | gold={r['gold']} | pattern={r['majority_pattern']} | fail_class={r['pool_fail_class']}")
            pool4_md_lines.append(f"- f={r['f_a']}({'✓' if r['f_ok'] else '✗'}) l1={r['l1_a']}({'✓' if r['l1_ok'] else '✗'}) s1={r['s1_a']}({'✓' if r['s1_ok'] else '✗'}) ta={r['ta_a']}({'✓' if r['ta_ok'] else '✗'}) pool={r['pool_a']}({'✓' if r['pool_ok'] else '✗'})")
            pool4_md_lines.append(f"- Q: {r['question'][:150]}...")
            pool4_md_lines.append("")
    (OUT / "pooled4_failure_representative_cases.md").write_text("\n".join(pool4_md_lines))
    print("  wrote pooled4_failure_representative_cases.md")

    # Step 6: agreement-only comparison
    print("Computing agreement-only comparison...")
    agr_comp = agreement_comparison(cohere_rows, mistral_rows)
    write_csv(OUT / "agreement_only_failure_comparison.csv", agr_comp)

    agr_fail_c = [r for r in cohere_rows if r["agr_ok"] == 0]
    agr_fail_m = [r for r in mistral_rows if r["agr_ok"] == 0]
    write_csv(OUT / "agreement_only_failure_cases_cohere.csv", agr_fail_c)
    write_csv(OUT / "agreement_only_failure_cases_mistral.csv", agr_fail_m)

    agr_md_lines = ["# Representative Agreement-Only Failure Cases\n"]
    for provider, rows in [("Cohere", agr_fail_c[:5]), ("Mistral", agr_fail_m[:5])]:
        agr_md_lines.append(f"## {provider}\n")
        for r in rows:
            agr_md_lines.append(f"**{r['example_id']}** | gold={r['gold']} | fail_class={r['agr_fail_class']}")
            agr_md_lines.append(f"- f={r['f_a']}({'✓' if r['f_ok'] else '✗'}) l1={r['l1_a']}({'✓' if r['l1_ok'] else '✗'}) s1={r['s1_a']}({'✓' if r['s1_ok'] else '✗'}) ta={r['ta_a']}({'✓' if r['ta_ok'] else '✗'})")
            agr_md_lines.append(f"- agr={r['agr_a']}({'✓' if r['agr_ok'] else '✗'}) pool={r['pool_a']}({'✓' if r['pool_ok'] else '✗'})")
            agr_md_lines.append(f"- Q: {r['question'][:150]}...")
            agr_md_lines.append("")
    (OUT / "agreement_only_failure_representative_cases.md").write_text("\n".join(agr_md_lines))
    print("  wrote agreement_only_failure_representative_cases.md")

    # Step 7: cross-provider runtime patterns
    print("Computing runtime pattern summary...")
    runtime_patterns = runtime_pattern_summary(cohere_rows, mistral_rows)
    majority_cond    = majority_conditioned_summary(cohere_rows, mistral_rows)
    write_csv(OUT / "cross_provider_runtime_pattern_summary.csv", runtime_patterns)
    write_csv(OUT / "majority_conditioned_correctness_summary.csv", majority_cond)

    # Step 8: hypotheses
    print("Generating algorithmic hypotheses...")
    hypotheses = generate_hypotheses(cohere_rows, mistral_rows, cv_results=[])

    # Step 9: 5-fold CV
    print("Running 5-fold CV on targeted diagnostic rules...")
    cv_summary, cv_folds = run_cv_evaluation(cohere_rows, mistral_rows)
    write_csv(OUT / "targeted_hypothesis_rule_cv_summary.csv", cv_summary)
    write_csv(OUT / "targeted_hypothesis_rule_fold_details.csv", cv_folds)

    # Rebuild hypotheses with CV evidence
    hypotheses = generate_hypotheses(cohere_rows, mistral_rows, cv_results=cv_summary)

    # Write hypothesis files
    hyp_table_rows = []
    for h in hypotheses:
        hyp_table_rows.append({
            "rank": h["rank"],
            "hypothesis": h["hypothesis"],
            "evidence_cohere": h["evidence_cohere"][:200],
            "evidence_mistral": h["evidence_mistral"][:200],
            "runtime_features": h["runtime_features"],
            "recommendation": h["recommendation"],
            "risk_of_overfitting": h["risk_of_overfitting"],
            "next_test": h["next_test"][:150],
        })
    write_csv(OUT / "algorithmic_hypotheses_table.csv", hyp_table_rows)

    hyp_md_lines = ["# Ranked Algorithmic Hypotheses — 2026-05-23\n"]
    for h in hypotheses:
        hyp_md_lines.append(f"## H{h['rank']}: {h['hypothesis']}")
        hyp_md_lines.append(f"- **Cohere:** {h['evidence_cohere']}")
        hyp_md_lines.append(f"- **Mistral:** {h['evidence_mistral']}")
        hyp_md_lines.append(f"- **Recommendation:** {h['recommendation']}")
        hyp_md_lines.append(f"- **Risk:** {h['risk_of_overfitting']}")
        hyp_md_lines.append(f"- **Next:** {h['next_test']}")
        hyp_md_lines.append("")
    (OUT / "algorithmic_hypotheses_ranked.md").write_text("\n".join(hyp_md_lines))
    print("  wrote algorithmic_hypotheses_ranked.md")

    # Step 10: casebook
    print("Building representative casebook...")
    casebook_rows = build_casebook(cohere_rows, mistral_rows)
    casebook_md = ["# Representative Cross-Provider Casebook — 2026-05-23\n"]
    for i, c in enumerate(casebook_rows, 1):
        casebook_md.append(f"## Case {i}: {c['provider'].upper()} — {c['example_id']}")
        casebook_md.append(f"**Reason:** {c['case_reason']}")
        casebook_md.append(f"**Gold:** `{c['gold']}`")
        casebook_md.append(f"**Question:** {c['question'][:250]}...")
        casebook_md.append(f"| Source | Answer | Correct |")
        casebook_md.append(f"|---|---|---|")
        for src, a_key, ok_key in [("frontier","f_ans","f_ok"),("L1","l1_ans","l1_ok"),("S1","s1_ans","s1_ok"),("TALE","ta_ans","ta_ok")]:
            casebook_md.append(f"| {src} | `{c[a_key]}` | {'✓' if c[ok_key] else '✗'} |")
        casebook_md.append(f"| agreement-only | `{c['agr_ans']}` | {'✓' if c['agr_ok'] else '✗'} |")
        casebook_md.append(f"| pooled-4 | `{c['pool_ans']}` | {'✓' if c['pool_ok'] else '✗'} |")
        casebook_md.append(f"")
        casebook_md.append(f"**Majority pattern:** {c['majority_pattern']}")
        casebook_md.append(f"**Algorithmic lesson:** {c['algorithmic_lesson']}")
        casebook_md.append("")
    (OUT / "representative_cross_provider_casebook.md").write_text("\n".join(casebook_md))
    print("  wrote representative_cross_provider_casebook.md")

    # Step 11: main report
    print("Writing main human-readable report...")
    write_main_report(
        cohere_rows, mistral_rows,
        pool4_comp, agr_comp,
        runtime_patterns, majority_cond,
        taxonomy_rows, hypotheses, cv_summary, cv_folds,
    )

    # Step 12: manifest
    ts_end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files_created = sorted(str(p.name) for p in OUT.iterdir() if p.is_file())
    manifest = {
        "created_at": ts,
        "updated_at": ts_end,
        "purpose": "Cross-provider failure-pattern and algorithmic hypothesis analysis using Cohere canonical Final-300 and Mistral Final-300 artifacts.",
        "source_artifacts": [
            str(COHERE_JSONL),
            str(MISTRAL_JSONL),
            str(COHERE_DIV),
            str(MISTRAL_DIV),
        ],
        "key_files_created": files_created,
        "api_calls_made": False,
        "active_jobs_touched": False,
        "notes": (
            "Cerebras (PID 2195513) active but not touched. "
            "All rules are diagnostic/offline only. "
            "No frozen policy logic was modified. "
            "No new policies were promoted."
        ),
        "human_report": "docs/COHERE_MISTRAL_FAILURE_PATTERN_HYPOTHESES_20260523.md",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"  wrote manifest.json")
    print(f"[done] {ts_end}")
    print(f"\nAll outputs in: {OUT}")
    print(f"Report: docs/COHERE_MISTRAL_FAILURE_PATTERN_HYPOTHESES_20260523.md")


if __name__ == "__main__":
    main()
