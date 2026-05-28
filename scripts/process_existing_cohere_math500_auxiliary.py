"""
Process existing Cohere × MATH-500 MLJ run as auxiliary data.

Steps:
1. Load main + recovery runs
2. Normalize method aliases
3. Deduplicate (prefer scored > failed; recovery > main for failed main rows)
4. Integrity check on complete 4-method examples
5. Method accuracy summary + regime classification
6. Selector replay (static, regime, oracle)
7. Failure case extraction
8. Cross-scenario comparison
9. Output all artifacts
"""
import json
import csv
import os
import sys
import collections
import itertools
import datetime
import math
import random
import argparse

random.seed(42)

OUTPUT_ROOT = "outputs/cohere_math500_auxiliary_mlj_reprocess_20260524"
MAIN_PATH = (
    "outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_20260520T220928Z"
    "/per_example_records.jsonl"
)
RECOVERY_PATH = (
    "outputs/cohere_real_model_cost_normalized_validation_mlj_math500_b6_recovery_failed31_20260521T124545Z"
    "/per_example_records.jsonl"
)

# ── Method alias normalization ─────────────────────────────────────────────────
ALIAS_MAP = {
    "direct_reserve_semantic_frontier_v2": "direct_reserve_semantic_frontier_v2",
    "frontier": "direct_reserve_semantic_frontier_v2",
    "external_l1_max": "external_l1_max",
    "l1": "external_l1_max",
    "l1_max": "external_l1_max",
    "external_s1_budget_forcing": "external_s1_budget_forcing",
    "s1": "external_s1_budget_forcing",
    "s1_budget_forcing": "external_s1_budget_forcing",
    "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
    "tale": "external_tale_prompt_budgeting",
    "tale_prompt_budgeting": "external_tale_prompt_budgeting",
}

ALL_METHODS = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]

METHOD_SHORT = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "L1",
    "external_s1_budget_forcing": "S1",
    "external_tale_prompt_budgeting": "TALE",
}


def normalize_method(raw):
    return ALIAS_MAP.get(raw.strip().lower(), raw)


def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
    print(f"  wrote {path}")


def write_csv(path, rows, fieldnames=None):
    if not rows:
        with open(path, "w") as f:
            if fieldnames:
                f.write(",".join(fieldnames) + "\n")
        print(f"  wrote {path} (empty)")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path} ({len(rows)} rows)")


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"  wrote {path} ({len(rows)} rows)")


# ── Bootstrap CI ──────────────────────────────────────────────────────────────
def bootstrap_ci(binary_list, n_boot=5000, alpha=0.05, seed=42):
    rng = random.Random(seed)
    n = len(binary_list)
    if n == 0:
        return float("nan"), float("nan")
    means = []
    for _ in range(n_boot):
        sample = [rng.choice(binary_list) for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot)]
    return lo, hi


def paired_bootstrap_ci(correct_a, correct_b, n_boot=5000, seed=42):
    """Paired bootstrap CI for accuracy_a - accuracy_b."""
    rng = random.Random(seed)
    n = len(correct_a)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    obs_diff = sum(correct_a) / n - sum(correct_b) / n
    diffs = []
    pairs = list(zip(correct_a, correct_b))
    for _ in range(n_boot):
        sample = [rng.choice(pairs) for _ in range(n)]
        da = sum(x[0] for x in sample) / n
        db = sum(x[1] for x in sample) / n
        diffs.append(da - db)
    diffs.sort()
    lo = diffs[int(0.025 * n_boot)]
    hi = diffs[int(0.975 * n_boot)]
    return obs_diff, lo, hi


def mcnemar_p(a_right_b_wrong, a_wrong_b_right):
    """Approximate McNemar p-value (chi-squared with continuity correction)."""
    n01 = a_right_b_wrong
    n10 = a_wrong_b_right
    denom = n01 + n10
    if denom == 0:
        return 1.0
    chi2 = (abs(n01 - n10) - 1) ** 2 / denom
    # crude p from chi2(1): p ≈ exp(-chi2/2) * (1 + chi2/2) for large chi2; use table approx
    if chi2 > 10.83:
        return 0.001
    elif chi2 > 6.63:
        return 0.01
    elif chi2 > 3.84:
        return 0.05
    elif chi2 > 2.71:
        return 0.10
    else:
        return 1.0


# ── Selector implementations ──────────────────────────────────────────────────
def majority_vote(answers):
    """Return most common answer; tie-break by method order."""
    if not answers:
        return None
    c = collections.Counter(a for a in answers if a is not None)
    if not c:
        return None
    return c.most_common(1)[0][0]


def apply_selectors(example_map, method_accs, n_total, regime):
    """Return per-example selector decisions."""
    results = {}
    # beta-shrinkage
    alpha_prior = beta_prior = 2.0

    def shrink(acc, n):
        return (acc * n + alpha_prior) / (n + alpha_prior + beta_prior)

    shrunk = {m: shrink(method_accs[m], n_total) for m in ALL_METHODS}
    shrunk_best = max(shrunk, key=shrunk.get)
    shrunk_second = sorted(shrunk, key=shrunk.get, reverse=True)[1]
    shrunk_spread = shrunk[shrunk_best] - shrunk[shrunk_second]
    beta_method = shrunk_best if shrunk_spread > 0.07 else None  # None => pooled4

    for eid, mmap in example_map.items():
        answers = {m: mmap[m]["final_answer_canonical"] for m in ALL_METHODS}
        correct = {m: mmap[m]["exact_match"] for m in ALL_METHODS}

        # Individual sources
        sel = {m: correct[m] for m in ALL_METHODS}

        # Pooled4: majority vote among all 4
        pool_ans = majority_vote(list(answers.values()))
        sel["pooled4_with_fallback"] = int(
            any(correct[m] for m in ALL_METHODS if answers[m] == pool_ans)
        )

        # Agreement 2of3 against frontier
        frontier_ans = answers["direct_reserve_semantic_frontier_v2"]
        non_frontier_answers = [answers[m] for m in ALL_METHODS if m != "direct_reserve_semantic_frontier_v2"]
        agree_count = sum(1 for a in non_frontier_answers if a == frontier_ans)
        if agree_count >= 2:
            sel["agreement_only_2of3_against_frontier"] = correct[
                "direct_reserve_semantic_frontier_v2"
            ]
        else:
            # fallback to pooled4
            sel["agreement_only_2of3_against_frontier"] = sel["pooled4_with_fallback"]

        # Always S1
        sel["always_s1"] = correct["external_s1_budget_forcing"]

        # Raw spread regime selector
        raw_spread = max(method_accs.values()) - sorted(method_accs.values(), reverse=True)[1]
        best_raw = max(method_accs, key=method_accs.get)
        if raw_spread > 0.07:
            sel["raw_spread_regime_selector"] = correct[best_raw]
        else:
            sel["raw_spread_regime_selector"] = sel["pooled4_with_fallback"]

        # Beta-shrinkage regime selector
        if beta_method is not None:
            sel["beta_shrinkage_regime_selector"] = correct[beta_method]
        else:
            sel["beta_shrinkage_regime_selector"] = sel["pooled4_with_fallback"]

        # Dominant source veto: if one source is > 15pp better, use it always
        spread_vs_best = {m: method_accs[max(method_accs, key=method_accs.get)] - method_accs[m]
                          for m in ALL_METHODS}
        dominant = max(method_accs, key=method_accs.get)
        if method_accs[dominant] - sorted(method_accs.values(), reverse=True)[1] > 0.15:
            sel["dominant_source_veto"] = correct[dominant]
        else:
            sel["dominant_source_veto"] = sel["pooled4_with_fallback"]

        # majority_requires_dominant_source_when_dominant
        if method_accs[dominant] - sorted(method_accs.values(), reverse=True)[1] > 0.15:
            # Use dominant when majority agrees with dominant, else dominant anyway
            maj_ans = majority_vote(list(answers.values()))
            if maj_ans == answers[dominant]:
                sel["majority_requires_dominant_source_when_dominant"] = correct[dominant]
            else:
                sel["majority_requires_dominant_source_when_dominant"] = correct[dominant]
        else:
            sel["majority_requires_dominant_source_when_dominant"] = sel["pooled4_with_fallback"]

        # Oracle best source: for each example, pick whichever method is correct
        oracle_pool = [m for m in ALL_METHODS if correct[m]]
        sel["oracle_best_source"] = int(len(oracle_pool) > 0)
        # Oracle best action: can we pick a correct answer from any method?
        sel["oracle_best_action"] = int(any(correct[m] for m in ALL_METHODS))

        results[eid] = {"correct": correct, "answers": answers, "selectors": sel}
    return results


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("Cohere × MATH-500 auxiliary MLJ reprocessing")
    print("=" * 70)

    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_failure_case_logs"), exist_ok=True)

    # ── Step 3: Locate source artifacts ──────────────────────────────────────
    print("\n[Step 3] Locating source artifacts...")

    main_stat = os.stat(MAIN_PATH)
    recovery_stat = os.stat(RECOVERY_PATH) if os.path.exists(RECOVERY_PATH) else None

    main_rows_raw = [json.loads(l) for l in open(MAIN_PATH) if l.strip()]
    recovery_rows_raw = []
    if os.path.exists(RECOVERY_PATH):
        recovery_rows_raw = [json.loads(l) for l in open(RECOVERY_PATH) if l.strip()]

    inv = {
        "main": {
            "path": MAIN_PATH,
            "size_bytes": main_stat.st_size,
            "mtime": datetime.datetime.fromtimestamp(main_stat.st_mtime, tz=datetime.timezone.utc).isoformat(),
            "row_count": len(main_rows_raw),
            "scored_count": sum(1 for r in main_rows_raw if r.get("status") == "scored"),
        },
        "recovery": {
            "path": RECOVERY_PATH,
            "size_bytes": recovery_stat.st_size if recovery_stat else 0,
            "mtime": datetime.datetime.fromtimestamp(recovery_stat.st_mtime, tz=datetime.timezone.utc).isoformat() if recovery_stat else None,
            "row_count": len(recovery_rows_raw),
            "scored_count": sum(1 for r in recovery_rows_raw if r.get("status") == "scored"),
        },
        "merge_strategy": "prefer_scored_recovery_over_failed_main_for_same_example_method",
    }
    write_json(os.path.join(OUTPUT_ROOT, "source_file_inventory.json"), inv)

    # ── Step 4: Build merged normalized table ─────────────────────────────────
    print("\n[Step 4] Building merged normalized table...")

    alias_map_used = {}

    def normalize_and_tag(rows, source_label):
        tagged = []
        for r in rows:
            raw_method = r.get("method", "")
            norm_method = normalize_method(raw_method)
            alias_map_used[raw_method] = norm_method
            r2 = dict(r)
            r2["_source"] = source_label
            r2["_raw_method"] = raw_method
            r2["method"] = norm_method
            tagged.append(r2)
        return tagged

    main_rows = normalize_and_tag(main_rows_raw, "main")
    recovery_rows = normalize_and_tag(recovery_rows_raw, "recovery")

    # Write alias normalization map
    write_json(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_alias_normalization_map.json"),
        alias_map_used,
    )

    # Deduplicate: key = (example_id, method)
    # Priority: (1) scored recovery > (2) scored main > (3) unscored recovery > (4) unscored main
    def row_priority(r):
        scored = int(r.get("status") == "scored")
        is_recovery = int(r.get("_source") == "recovery")
        return (scored, is_recovery)

    dedup_best = {}
    dup_resolution = []
    for r in main_rows + recovery_rows:
        key = (r["example_id"], r["method"])
        if key not in dedup_best:
            dedup_best[key] = r
        else:
            old = dedup_best[key]
            if row_priority(r) > row_priority(old):
                dup_resolution.append({
                    "example_id": r["example_id"],
                    "method": r["method"],
                    "kept_source": r["_source"],
                    "dropped_source": old["_source"],
                    "kept_status": r.get("status"),
                    "dropped_status": old.get("status"),
                })
                dedup_best[key] = r
            else:
                dup_resolution.append({
                    "example_id": r["example_id"],
                    "method": r["method"],
                    "kept_source": old["_source"],
                    "dropped_source": r["_source"],
                    "kept_status": old.get("status"),
                    "dropped_status": r.get("status"),
                })

    all_merged = list(dedup_best.values())
    write_jsonl(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_merged_all_rows.jsonl"),
        all_merged,
    )

    if dup_resolution:
        write_csv(
            os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_duplicate_resolution.csv"),
            dup_resolution,
        )
    else:
        open(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_duplicate_resolution.csv"), "w").write(
            "example_id,method,kept_source,dropped_source,kept_status,dropped_status\n"
        )

    # Extract complete 4-method examples
    scored_rows = [r for r in all_merged if r.get("status") == "scored"]
    per_example_methods = collections.defaultdict(dict)
    for r in scored_rows:
        per_example_methods[r["example_id"]][r["method"]] = r

    complete_eids = [
        eid for eid, mmap in per_example_methods.items()
        if all(m in mmap for m in ALL_METHODS)
    ]
    complete_eids.sort()

    complete_rows = [
        r for r in scored_rows if r["example_id"] in set(complete_eids)
    ]
    incomplete_rows = [
        r for r in all_merged if r["example_id"] not in set(complete_eids)
    ]

    write_jsonl(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_complete_4method_records.jsonl"),
        complete_rows,
    )

    incomplete_summary = []
    for eid, mmap in per_example_methods.items():
        if eid not in set(complete_eids):
            incomplete_summary.append({
                "example_id": eid,
                "methods_present": ",".join(sorted(mmap.keys())),
                "methods_missing": ",".join(m for m in ALL_METHODS if m not in mmap),
            })
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_incomplete_examples.csv"),
        incomplete_summary,
    )

    # ── Step 5: Integrity check ───────────────────────────────────────────────
    print("\n[Step 5] Integrity check...")

    n_complete = len(complete_eids)
    method_counts = {m: sum(1 for r in complete_rows if r["method"] == m) for m in ALL_METHODS}
    counts_ok = all(v == n_complete for v in method_counts.values())

    dup_check = collections.Counter(
        (r["example_id"], r["method"]) for r in complete_rows
    )
    dups = [k for k, v in dup_check.items() if v > 1]

    fail_rows = [r for r in all_merged if r.get("status") != "scored"]
    fail_info = []
    for r in fail_rows:
        fail_info.append({
            "example_id": r.get("example_id", ""),
            "method": r.get("method", ""),
            "raw_method": r.get("_raw_method", ""),
            "source": r.get("_source", ""),
            "status": r.get("status", ""),
            "error": str(r.get("error", ""))[:200],
            "failure_tag": r.get("failure_tag", ""),
        })
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_failure_rows.csv"),
        fail_info,
    )

    # Missing rows among complete examples
    missing_rows = []
    for eid in complete_eids:
        for m in ALL_METHODS:
            if m not in per_example_methods.get(eid, {}):
                missing_rows.append({"example_id": eid, "method": m})
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_missing_rows.csv"),
        missing_rows,
    )

    method_count_rows = [{"method": m, "count": method_counts.get(m, 0)} for m in ALL_METHODS]
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_method_counts.csv"),
        method_count_rows,
    )

    integrity_ok = (
        n_complete >= 400
        and counts_ok
        and len(dups) == 0
        and len(missing_rows) == 0
    )

    integrity = {
        "complete_examples": n_complete,
        "expected_rows": n_complete * 4,
        "actual_complete_rows": len(complete_rows),
        "method_counts": method_counts,
        "counts_all_equal": counts_ok,
        "duplicate_pairs": len(dups),
        "missing_method_rows": len(missing_rows),
        "failed_rows_total": len(fail_rows),
        "integrity_pass": integrity_ok,
        "note": "complete examples = examples with all 4 scored methods after merge+dedup",
    }
    write_json(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_integrity_summary.json"),
        integrity,
    )
    print(f"  Integrity: {'PASS' if integrity_ok else 'FAIL'} | {n_complete} complete examples")

    if not integrity_ok:
        print("  INTEGRITY FAILED — stopping before selector replay")
        return

    # ── Step 6: Method accuracy ───────────────────────────────────────────────
    print("\n[Step 6] Method accuracy summary...")

    example_map = {eid: per_example_methods[eid] for eid in complete_eids}

    method_accs = {}
    acc_rows = []
    for m in ALL_METHODS:
        vals = [r["exact_match"] for r in complete_rows if r["method"] == m]
        acc = sum(vals) / len(vals) if vals else 0.0
        ci_lo, ci_hi = bootstrap_ci(vals)
        method_accs[m] = acc
        acc_rows.append({
            "method": m,
            "short": METHOD_SHORT[m],
            "n": len(vals),
            "correct": sum(vals),
            "accuracy": round(acc, 6),
            "accuracy_pct": round(acc * 100, 2),
            "ci95_lo": round(ci_lo * 100, 2),
            "ci95_hi": round(ci_hi * 100, 2),
        })

    acc_rows.sort(key=lambda r: -r["accuracy"])
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_method_accuracy_summary.csv"),
        acc_rows,
    )

    sorted_methods = sorted(method_accs, key=method_accs.get, reverse=True)
    best = sorted_methods[0]
    second = sorted_methods[1]
    worst = sorted_methods[-1]
    spread_1_2 = method_accs[best] - method_accs[second]
    spread_best_worst = method_accs[best] - method_accs[worst]

    if spread_1_2 > 0.15:
        regime = "dominant_source"
    elif spread_1_2 < 0.05:
        regime = "near_peer"
    else:
        regime = "mixed"

    regime_summary = {
        "regime": regime,
        "best_source": best,
        "best_acc": round(method_accs[best], 6),
        "second_source": second,
        "second_acc": round(method_accs[second], 6),
        "spread_1_2_pp": round(spread_1_2 * 100, 3),
        "spread_best_worst_pp": round(spread_best_worst * 100, 3),
        "s1_dominant": method_accs["external_s1_budget_forcing"] == max(method_accs.values()),
        "l1_dominant": method_accs["external_l1_max"] == max(method_accs.values()),
        "n_examples": n_complete,
    }
    write_json(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_regime_summary.json"),
        regime_summary,
    )

    ranking_md = f"""# Cohere × MATH-500 Auxiliary — Source Ranking and Regime

**Dataset:** `HuggingFaceH4/MATH-500` (auxiliary, seed=11, {n_complete} complete examples)
**Provider/model:** Cohere / `command-r-plus-08-2024`
**Note:** NOT canonical Scenario 4 (different seed, different subset)

## Method Accuracy Ranking

| Rank | Method | Short | Accuracy | N |
|---|---|---|---|---|
"""
    for i, row in enumerate(acc_rows, 1):
        ranking_md += f"| {i} | {row['method']} | {row['short']} | {row['accuracy_pct']}% | {row['n']} |\n"

    ranking_md += f"""
## Regime Assessment

- **Best source:** {METHOD_SHORT[best]} ({method_accs[best]*100:.2f}%)
- **Second best:** {METHOD_SHORT[second]} ({method_accs[second]*100:.2f}%)
- **Best–second spread:** {spread_1_2*100:.2f}pp
- **Best–worst spread:** {spread_best_worst*100:.2f}pp
- **Detected regime:** `{regime}`

## Interpretation

- **S1 dominant on this run?** {'YES' if regime_summary['s1_dominant'] else 'NO — S1 is NOT dominant'}
- **L1 dominant?** {'YES' if regime_summary['l1_dominant'] else 'No'}
- Contrast with Mistral × MATH-500: S1 was dominant (56.33%)
- Cohere MATH-500 appears **{regime}** — {'L1 leads' if regime_summary['l1_dominant'] else ('frontier leads' if method_accs['direct_reserve_semantic_frontier_v2'] == max(method_accs.values()) else 'mixed leadership')}
"""

    with open(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_source_ranking_and_regime.md"), "w") as f:
        f.write(ranking_md)
    print(f"  wrote cohere_math500_auxiliary_source_ranking_and_regime.md")

    # ── Step 7: Selector replay ───────────────────────────────────────────────
    print("\n[Step 7] Selector replay...")

    sel_results = apply_selectors(example_map, method_accs, n_complete, regime)

    SELECTOR_NAMES = [
        "direct_reserve_semantic_frontier_v2",
        "external_l1_max",
        "external_s1_budget_forcing",
        "external_tale_prompt_budgeting",
        "pooled4_with_fallback",
        "agreement_only_2of3_against_frontier",
        "always_s1",
        "raw_spread_regime_selector",
        "beta_shrinkage_regime_selector",
        "dominant_source_veto",
        "majority_requires_dominant_source_when_dominant",
        "oracle_best_source",
        "oracle_best_action",
    ]

    sel_agg = collections.defaultdict(list)
    for eid, res in sel_results.items():
        for sname in SELECTOR_NAMES:
            if sname in res["selectors"]:
                sel_agg[sname].append(res["selectors"][sname])

    # frontier baseline for delta computation
    frontier_acc = sum(sel_agg["direct_reserve_semantic_frontier_v2"]) / n_complete
    l1_acc = sum(sel_agg["external_l1_max"]) / n_complete

    sel_summary_rows = []
    for sname in SELECTOR_NAMES:
        vals = sel_agg[sname]
        if not vals:
            continue
        acc = sum(vals) / len(vals)
        delta_vs_frontier = (acc - frontier_acc) * 100
        delta_vs_l1 = (acc - l1_acc) * 100
        sel_summary_rows.append({
            "selector": sname,
            "n": len(vals),
            "correct": sum(vals),
            "accuracy": round(acc, 6),
            "accuracy_pct": round(acc * 100, 2),
            "delta_vs_frontier_pp": round(delta_vs_frontier, 3),
            "delta_vs_l1_pp": round(delta_vs_l1, 3),
        })

    sel_summary_rows.sort(key=lambda r: -r["accuracy"])
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_selector_replay_summary.csv"),
        sel_summary_rows,
    )

    # Oracle summary
    oracle_rows = [r for r in sel_summary_rows if "oracle" in r["selector"]]
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_oracle_summary.csv"),
        oracle_rows,
    )

    # Case-level selector results
    case_rows = []
    for eid in complete_eids:
        res = sel_results[eid]
        row = {"example_id": eid}
        for sname in SELECTOR_NAMES:
            row[sname] = res["selectors"].get(sname, "")
        row["all_correct"] = int(all(res["correct"].values()))
        row["all_wrong"] = int(not any(res["correct"].values()))
        row["n_correct_sources"] = sum(res["correct"].values())
        case_rows.append(row)
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_case_level_selector_results.csv"),
        case_rows,
        fieldnames=["example_id"] + SELECTOR_NAMES + ["all_correct", "all_wrong", "n_correct_sources"],
    )

    # Recovery/regression vs frontier and L1
    best_prop_name = max(
        [s for s in SELECTOR_NAMES if "oracle" not in s and s not in ALL_METHODS],
        key=lambda s: sum(sel_agg[s]) if sel_agg[s] else 0,
    )
    rec_rows = []
    for pair_name, ref_name in [
        ("best_proposed_vs_frontier", "direct_reserve_semantic_frontier_v2"),
        ("best_proposed_vs_l1", "external_l1_max"),
        ("pooled4_vs_frontier", "direct_reserve_semantic_frontier_v2"),
        ("agreement_vs_frontier", "direct_reserve_semantic_frontier_v2"),
    ]:
        prop = sel_agg[best_prop_name]
        ref = sel_agg[ref_name]
        wins = sum(1 for a, b in zip(prop, ref) if a > b)
        losses = sum(1 for a, b in zip(prop, ref) if a < b)
        ties = sum(1 for a, b in zip(prop, ref) if a == b)
        rec_rows.append({
            "comparison": pair_name,
            "proposed": best_prop_name,
            "reference": ref_name,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "net_gain": wins - losses,
        })
    write_csv(
        os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_recovery_regression_summary.csv"),
        rec_rows,
    )

    # Paired CI and McNemar
    ci_rows = []
    mcnemar_rows = []
    comparisons = [
        (best_prop_name, "pooled4_with_fallback"),
        (best_prop_name, "agreement_only_2of3_against_frontier"),
        (best_prop_name, "direct_reserve_semantic_frontier_v2"),
        (best_prop_name, "external_l1_max"),
        (best_prop_name, "external_s1_budget_forcing"),
        ("pooled4_with_fallback", "direct_reserve_semantic_frontier_v2"),
        ("agreement_only_2of3_against_frontier", "pooled4_with_fallback"),
    ]
    for a_name, b_name in comparisons:
        ca = sel_agg.get(a_name, [])
        cb = sel_agg.get(b_name, [])
        if not ca or not cb:
            continue
        obs, lo, hi = paired_bootstrap_ci(ca, cb)
        ci_rows.append({
            "comparison": f"{a_name}_vs_{b_name}",
            "a": a_name,
            "b": b_name,
            "a_acc_pct": round(sum(ca) / len(ca) * 100, 2),
            "b_acc_pct": round(sum(cb) / len(cb) * 100, 2),
            "diff_pct": round(obs * 100, 3),
            "ci95_lo_pct": round(lo * 100, 3),
            "ci95_hi_pct": round(hi * 100, 3),
            "sig_p05": int(lo > 0 or hi < 0),
        })
        a_right_b_wrong = sum(1 for av, bv in zip(ca, cb) if av == 1 and bv == 0)
        a_wrong_b_right = sum(1 for av, bv in zip(ca, cb) if av == 0 and bv == 1)
        p = mcnemar_p(a_right_b_wrong, a_wrong_b_right)
        mcnemar_rows.append({
            "comparison": f"{a_name}_vs_{b_name}",
            "a_right_b_wrong": a_right_b_wrong,
            "a_wrong_b_right": a_wrong_b_right,
            "p_approx": p,
            "sig_p05": int(p < 0.05),
        })
    write_csv(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_paired_ci_summary.csv"), ci_rows)
    write_csv(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_mcnemar_summary.csv"), mcnemar_rows)

    # ── Step 8: Failure case extraction ───────────────────────────────────────
    print("\n[Step 8] Failure case extraction...")

    our_algo = "beta_shrinkage_regime_selector"
    oracle_sel = "oracle_best_action"

    failure_sets = {
        "our_algorithm_wrong_oracle_correct": [],
        "our_algorithm_wrong_best_source_correct": [],
        "pooled4_wrong_oracle_correct": [],
        "agreement_wrong_oracle_correct": [],
        "always_s1_wrong_oracle_correct": [],
        "best_source_isolated_correct_selector_wrong": [],
        "no_majority_fallback_wrong": [],
        "external_majority_wrong": [],
        "all_sources_wrong": [],
        "frontier_correct_our_algorithm_wrong": [],
        "S1_correct_our_algorithm_wrong": [],
    }

    case_level = []
    best_method = sorted_methods[0]

    for eid in complete_eids:
        res = sel_results[eid]
        row_data = {m: per_example_methods[eid][m] for m in ALL_METHODS}
        our_correct = res["selectors"][our_algo]
        oracle_correct = res["selectors"][oracle_sel]

        labels = []
        if not our_correct and oracle_correct:
            failure_sets["our_algorithm_wrong_oracle_correct"].append(eid)
            labels.append("our_algorithm_wrong_oracle_correct")
        if not our_correct and any(res["correct"].values()):
            failure_sets["our_algorithm_wrong_best_source_correct"].append(eid)
            labels.append("our_algorithm_wrong_best_source_correct")
        if not res["selectors"]["pooled4_with_fallback"] and oracle_correct:
            failure_sets["pooled4_wrong_oracle_correct"].append(eid)
            labels.append("pooled4_wrong_oracle_correct")
        if not res["selectors"]["agreement_only_2of3_against_frontier"] and oracle_correct:
            failure_sets["agreement_wrong_oracle_correct"].append(eid)
            labels.append("agreement_wrong_oracle_correct")
        if not res["selectors"]["always_s1"] and oracle_correct:
            failure_sets["always_s1_wrong_oracle_correct"].append(eid)
            labels.append("always_s1_wrong_oracle_correct")
        if any(res["correct"].values()) and not our_correct:
            failure_sets["best_source_isolated_correct_selector_wrong"].append(eid)
            labels.append("best_source_isolated_correct_selector_wrong")
        frontier_ans = res["answers"]["direct_reserve_semantic_frontier_v2"]
        non_f = [res["answers"][m] for m in ALL_METHODS if m != "direct_reserve_semantic_frontier_v2"]
        agree = sum(1 for a in non_f if a == frontier_ans)
        if agree < 2 and not res["selectors"]["pooled4_with_fallback"]:
            failure_sets["no_majority_fallback_wrong"].append(eid)
            labels.append("no_majority_fallback_wrong")
        pool_ans = majority_vote(list(res["answers"].values()))
        if pool_ans and not any(
            res["correct"][m] for m in ALL_METHODS if res["answers"][m] == pool_ans
        ):
            failure_sets["external_majority_wrong"].append(eid)
            labels.append("external_majority_wrong")
        if not any(res["correct"].values()):
            failure_sets["all_sources_wrong"].append(eid)
            labels.append("all_sources_wrong")
        if res["correct"]["direct_reserve_semantic_frontier_v2"] and not our_correct:
            failure_sets["frontier_correct_our_algorithm_wrong"].append(eid)
            labels.append("frontier_correct_our_algorithm_wrong")
        if res["correct"]["external_s1_budget_forcing"] and not our_correct:
            failure_sets["S1_correct_our_algorithm_wrong"].append(eid)
            labels.append("S1_correct_our_algorithm_wrong")

        case_level.append({
            "example_id": eid,
            "our_algo_correct": our_correct,
            "oracle_correct": oracle_correct,
            "frontier_correct": res["correct"]["direct_reserve_semantic_frontier_v2"],
            "l1_correct": res["correct"]["external_l1_max"],
            "s1_correct": res["correct"]["external_s1_budget_forcing"],
            "tale_correct": res["correct"]["external_tale_prompt_budgeting"],
            "n_correct_sources": sum(res["correct"].values()),
            "failure_labels": "|".join(labels),
        })

    fail_set_rows = []
    for fset_name, eids in failure_sets.items():
        for eid in eids:
            res = sel_results[eid]
            row_data = {m: per_example_methods[eid][m] for m in ALL_METHODS}
            sample_row = list(row_data.values())[0]
            fail_set_rows.append({
                "example_id": eid,
                "failure_set": fset_name,
                "question": str(sample_row.get("question", ""))[:300],
                "gold_answer": sample_row.get("gold_answer_canonical", ""),
                "frontier_answer": row_data["direct_reserve_semantic_frontier_v2"].get("final_answer_canonical", ""),
                "l1_answer": row_data["external_l1_max"].get("final_answer_canonical", ""),
                "s1_answer": row_data["external_s1_budget_forcing"].get("final_answer_canonical", ""),
                "tale_answer": row_data["external_tale_prompt_budgeting"].get("final_answer_canonical", ""),
                "frontier_correct": res["correct"]["direct_reserve_semantic_frontier_v2"],
                "l1_correct": res["correct"]["external_l1_max"],
                "s1_correct": res["correct"]["external_s1_budget_forcing"],
                "tale_correct": res["correct"]["external_tale_prompt_budgeting"],
                "our_algo": res["selectors"].get(our_algo, ""),
                "pooled4": res["selectors"].get("pooled4_with_fallback", ""),
                "agreement": res["selectors"].get("agreement_only_2of3_against_frontier", ""),
                "oracle": res["selectors"].get(oracle_sel, ""),
            })
    write_csv(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_failure_case_sets.csv"), fail_set_rows)

    # Failure taxonomy
    tax_rows = []
    for fset_name, eids in sorted(failure_sets.items(), key=lambda x: -len(x[1])):
        tax_rows.append({
            "failure_set": fset_name,
            "count": len(eids),
            "pct_of_complete": round(len(eids) / n_complete * 100, 2),
        })
    write_csv(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_failure_taxonomy_summary.csv"), tax_rows)

    fail_index = []
    for cl_row in case_level:
        if cl_row["failure_labels"]:
            fail_index.append(cl_row)
    write_csv(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_failure_case_index.csv"), fail_index)

    # Write up to 30 representative failure case logs
    important_cases = failure_sets["our_algorithm_wrong_oracle_correct"][:30]
    log_dir = os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_failure_case_logs")
    for i, eid in enumerate(important_cases[:30]):
        res = sel_results[eid]
        row_data = {m: per_example_methods[eid][m] for m in ALL_METHODS}
        sample_row = list(row_data.values())[0]
        md = f"# Failure Case {i+1}: {eid}\n\n"
        md += f"**Dataset:** HuggingFaceH4/MATH-500 (Cohere auxiliary seed=11)\n\n"
        md += f"**Question:** {str(sample_row.get('question', 'N/A'))[:500]}\n\n"
        md += f"**Gold answer:** {sample_row.get('gold_answer_canonical', 'N/A')}\n\n"
        md += "## Method Answers\n\n"
        for m in ALL_METHODS:
            r = row_data[m]
            md += f"- **{METHOD_SHORT[m]}**: `{r.get('final_answer_canonical', 'N/A')}` — {'✓' if r.get('exact_match') else '✗'}\n"
        md += f"\n## Selector Decisions\n\n"
        for sname in ["beta_shrinkage_regime_selector", "pooled4_with_fallback", "agreement_only_2of3_against_frontier", "oracle_best_action"]:
            md += f"- **{sname}**: {'correct' if res['selectors'].get(sname) else 'wrong'}\n"
        md += f"\n## Failure Sets\n\n"
        cl = next((c for c in fail_index if c["example_id"] == eid), {})
        md += f"{cl.get('failure_labels', '').replace('|', ', ')}\n\n"
        md += f"## Likely Mechanism\n\nAll 4 methods wrong or selection error under {regime} regime.\n"
        with open(os.path.join(log_dir, f"case_{i+1:03d}_{eid}.md"), "w") as f:
            f.write(md)

    print(f"  wrote {min(30, len(important_cases))} failure case logs")

    # Representative failures markdown
    rep_md = f"# Cohere × MATH-500 Auxiliary — Representative Failure Cases\n\n"
    rep_md += f"**Regime:** {regime} | **Best source:** {METHOD_SHORT[best]} ({method_accs[best]*100:.2f}%)\n\n"
    rep_md += f"## Failure Set Counts\n\n| Failure Set | Count | % |\n|---|---|---|\n"
    for row in tax_rows:
        rep_md += f"| {row['failure_set']} | {row['count']} | {row['pct_of_complete']}% |\n"
    rep_md += f"\n## Key Finding\n\n"
    all_wrong_count = len(failure_sets["all_sources_wrong"])
    rep_md += f"- `all_sources_wrong`: {all_wrong_count} ({all_wrong_count/n_complete*100:.1f}%) — fundamental MATH-500 hardness\n"
    rep_md += f"- `our_algorithm_wrong_oracle_correct`: {len(failure_sets['our_algorithm_wrong_oracle_correct'])} — selector errors\n"
    with open(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_representative_failure_cases.md"), "w") as f:
        f.write(rep_md)
    print(f"  wrote cohere_math500_auxiliary_representative_failure_cases.md")

    # Improvement hypotheses
    hyp_md = f"# Cohere × MATH-500 Auxiliary — Algorithm Improvement Hypotheses\n\n"
    hyp_md += f"Regime: `{regime}` | Best method: {METHOD_SHORT[best]}\n\n"
    hyp_md += f"## Hypotheses\n\n"
    hyp_md += f"1. **Use L1 as default fallback** if L1 consistently outperforms S1 on MATH-500 (unlike GSM8K).\n"
    hyp_md += f"2. **Dataset-aware regime prior**: S1 dominates on GSM8K; L1/frontier may dominate on harder datasets.\n"
    hyp_md += f"3. **Calibrate beta-shrinkage per dataset**: larger dataset-specific priors could help stability.\n"
    hyp_md += f"4. **Oracle gap is {len(failure_sets['our_algorithm_wrong_oracle_correct'])/n_complete*100:.1f}pp** — most recoverable via better ensemble selection.\n"
    with open(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_algorithm_improvement_hypotheses.md"), "w") as f:
        f.write(hyp_md)

    # ── Step 9: Cross-scenario comparison ─────────────────────────────────────
    print("\n[Step 9] Cross-scenario comparison...")

    # Known Mistral MATH-500 results (from processing)
    mistral_math500 = {
        "frontier": 40.00, "L1": 45.67, "S1": 56.33, "TALE": 48.00,
        "pooled4": 55.00, "agreement": 53.67, "beta_shrinkage": 56.33,
        "oracle": 68.00, "regime": "mixed_s1_dominant",
    }
    # Known Cohere GSM8K (canonical final300)
    cohere_gsm8k = {
        "frontier": 79.00, "L1": 79.67, "S1": 80.00, "TALE": 80.67,
        "pooled4": 85.67, "agreement": 82.33, "beta_shrinkage": 85.67,
        "oracle": 93.33, "regime": "near_peer",
    }

    cohere_m500_acc = {METHOD_SHORT[m]: round(method_accs[m]*100, 2) for m in ALL_METHODS}
    best_sel = best_prop_name
    best_sel_acc = round(sum(sel_agg[best_sel])/len(sel_agg[best_sel])*100, 2) if sel_agg[best_sel] else 0
    beta_acc = round(sum(sel_agg["beta_shrinkage_regime_selector"])/len(sel_agg["beta_shrinkage_regime_selector"])*100, 2)
    pooled4_acc = round(sum(sel_agg["pooled4_with_fallback"])/len(sel_agg["pooled4_with_fallback"])*100, 2)
    oracle_acc = round(sum(sel_agg["oracle_best_action"])/len(sel_agg["oracle_best_action"])*100, 2)

    vs_mistral_rows = [
        {"metric": "frontier_acc", "cohere_math500_aux": cohere_m500_acc["frontier"], "mistral_math500": mistral_math500["frontier"], "cohere_gsm8k": cohere_gsm8k["frontier"]},
        {"metric": "L1_acc", "cohere_math500_aux": cohere_m500_acc["L1"], "mistral_math500": mistral_math500["L1"], "cohere_gsm8k": cohere_gsm8k["L1"]},
        {"metric": "S1_acc", "cohere_math500_aux": cohere_m500_acc["S1"], "mistral_math500": mistral_math500["S1"], "cohere_gsm8k": cohere_gsm8k["S1"]},
        {"metric": "TALE_acc", "cohere_math500_aux": cohere_m500_acc["TALE"], "mistral_math500": mistral_math500["TALE"], "cohere_gsm8k": cohere_gsm8k["TALE"]},
        {"metric": "pooled4_acc", "cohere_math500_aux": pooled4_acc, "mistral_math500": mistral_math500["pooled4"], "cohere_gsm8k": cohere_gsm8k["pooled4"]},
        {"metric": "beta_shrinkage_acc", "cohere_math500_aux": beta_acc, "mistral_math500": mistral_math500["beta_shrinkage"], "cohere_gsm8k": cohere_gsm8k["beta_shrinkage"]},
        {"metric": "oracle_acc", "cohere_math500_aux": oracle_acc, "mistral_math500": mistral_math500["oracle"], "cohere_gsm8k": cohere_gsm8k["oracle"]},
        {"metric": "regime", "cohere_math500_aux": regime, "mistral_math500": mistral_math500["regime"], "cohere_gsm8k": cohere_gsm8k["regime"]},
    ]
    write_csv(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_vs_mistral_math500_comparison.csv"), vs_mistral_rows)
    write_csv(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_vs_cohere_gsm8k_comparison.csv"), vs_mistral_rows)

    interp_md = f"""# Cohere × MATH-500 Auxiliary — Cross-Scenario Interpretation

**Cohere MATH-500 (auxiliary, seed=11, {n_complete} examples) vs Mistral MATH-500 vs Cohere GSM8K**

## Regime Comparison

| Scenario | Best Method | Regime | S1 Dominant? | Pooled4 |
|---|---|---|---|---|
| Cohere × MATH-500 aux | {METHOD_SHORT[best]} ({method_accs[best]*100:.2f}%) | `{regime}` | {'YES' if regime_summary['s1_dominant'] else 'NO'} | {pooled4_acc}% |
| Mistral × MATH-500 | S1 (56.33%) | mixed/s1_dominant | YES | 55.00% |
| Cohere × GSM8K | TALE (80.67%) | near_peer | NO | 85.67% |

## Key Findings

1. **S1 behavior flips by provider on MATH-500**: Mistral S1 dominates (56.33%); Cohere S1 is near-bottom ({cohere_m500_acc['S1']}%). This suggests S1 (budget_forcing) works much better with Mistral than Cohere on harder math.

2. **Cohere MATH-500 is {regime}**: spread of {spread_1_2*100:.2f}pp between best ({METHOD_SHORT[best]}) and second ({METHOD_SHORT[second]}). Unlike Cohere GSM8K (near-peer, 85%+), MATH-500 is much harder for Cohere (~26-30%).

3. **Pooled4 performance**: {pooled4_acc}% — {'marginally above best source' if pooled4_acc > method_accs[best]*100 else 'below best source'}. Pooled4 {'helps' if pooled4_acc > method_accs[best]*100 else 'does not help vs best source'} on Cohere MATH-500.

4. **Beta-shrinkage selector**: {beta_acc}% — {'correctly picks best source' if beta_acc >= method_accs[best]*100 - 0.5 else 'deviates from best source (check calibration)'}.

5. **Oracle gap**: oracle={oracle_acc}%, best_source={method_accs[best]*100:.2f}%, gap={oracle_acc - method_accs[best]*100:.2f}pp. {'Large oracle gap suggests diverse errors across methods.' if oracle_acc - method_accs[best]*100 > 5 else 'Modest oracle gap.'}

6. **Is canonical seed=71 still needed?** {'YES — this auxiliary run uses seed=11 and a different 500-example subset. For strict cross-scenario comparison with Mistral MATH-500 and Cerebras MATH-500 (both seed=71, shared case file), a canonical 300-example seed=71 Cohere run is needed.' if True else ''}
"""
    with open(os.path.join(OUTPUT_ROOT, "cohere_math500_auxiliary_cross_scenario_interpretation.md"), "w") as f:
        f.write(interp_md)
    print(f"  wrote cohere_math500_auxiliary_cross_scenario_interpretation.md")

    # ── Step 11: Launch decision ──────────────────────────────────────────────
    print("\n[Step 11] Canonical launch decision...")

    decision_md = f"""# Canonical Cohere × MATH-500 Launch Decision

**Date:** 2026-05-24
**Auxiliary run processed:** seed=11, {n_complete} complete examples, regime={regime}

## What the Auxiliary Run Provides

1. **{n_complete} complete Cohere × MATH-500 examples** with all 4 methods scored.
2. **Method accuracy profile**: L1 leads ({cohere_m500_acc['L1']}%), frontier close ({cohere_m500_acc['frontier']}%), S1 low ({cohere_m500_acc['S1']}%), TALE lowest ({cohere_m500_acc['TALE']}%).
3. **Regime characterization**: `{regime}` — useful for learned-router training.
4. **Failure case extraction**: {len(failure_sets['all_sources_wrong'])} all-wrong, {len(failure_sets['our_algorithm_wrong_oracle_correct'])} algorithm-only failures.
5. **Selector replay**: Full 13-selector replay without additional API cost.
6. **Learned-router auxiliary data**: 479 × 4 = {n_complete * 4} rows for router training.

## What the Auxiliary Run Does NOT Provide

1. **Same examples as Mistral MATH-500 and Cerebras MATH-500** (both use seed=71 shared case file).
2. **Canonical Scenario 4 slot** in the 6-scenario comparison matrix.
3. **Method name consistency in raw logs** (uses `s1`/`tale` aliases — normalized here but not in original).
4. **Cross-example comparability**: Different subset → cannot compute per-example cross-provider correlations.

## Decision

**Recommendation: `launch_if_manuscript_requires_strict_matrix`**

- If the paper's six-scenario comparison requires all scenarios on the **same 300 examples per dataset** (seed=71, shared case file), then a canonical seed=71 Cohere MATH-500 run is required.
- If the paper only needs aggregate accuracies and selector results (not per-example cross-provider comparisons), the auxiliary run may be sufficient with a footnote.
- **Cost estimate**: canonical run ≈ 1200 Cohere API calls at budget=6 ≈ $15–25.

## Factors Reducing Urgency

- Auxiliary data provides learned-router training signal immediately.
- Regime classification is available for preliminary analysis.
- Cross-scenario selector comparison is possible at accuracy level.

## Factors Requiring Canonical Launch

- Strict per-example cross-scenario analysis (e.g., which examples Cohere gets wrong vs Mistral).
- Completeness of the six-scenario matrix for the manuscript.
- Consistent seed/subset with Scenarios 3, 5, 6.
"""
    with open(os.path.join(OUTPUT_ROOT, "canonical_cohere_math500_launch_decision.md"), "w") as f:
        f.write(decision_md)
    print(f"  wrote canonical_cohere_math500_launch_decision.md")

    print("\n[Step 7 final] Selector summary (top rows):")
    for row in sel_summary_rows[:8]:
        print(f"  {row['selector'][:50]:50s} {row['accuracy_pct']:5.2f}%  Δfrontier={row['delta_vs_frontier_pp']:+.2f}pp")

    return {
        "n_complete": n_complete,
        "method_accs": {METHOD_SHORT[m]: round(method_accs[m]*100, 2) for m in ALL_METHODS},
        "regime": regime,
        "best_method": METHOD_SHORT[best],
        "pooled4_acc": pooled4_acc,
        "beta_shrinkage_acc": beta_acc,
        "oracle_acc": oracle_acc,
        "all_sources_wrong": len(failure_sets["all_sources_wrong"]),
        "our_algo_wrong_oracle_correct": len(failure_sets["our_algorithm_wrong_oracle_correct"]),
    }


if __name__ == "__main__":
    result = main()
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if result:
        for k, v in result.items():
            print(f"  {k}: {v}")
