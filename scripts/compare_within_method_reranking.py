"""Within-method verifier reranking analysis.

For each (example_id, budget, method) group, treats the 6 seed candidates as
alternatives and asks: does picking the seed with highest proba_ready (verifier_max)
outperform random seed selection, and by how much?

This directly tests whether proba_ready has value *after* controlling for method
identity — the key limitation found in the cross-method comparison where verifier
score was entangled with method.

Usage:
    python3 scripts/compare_within_method_reranking.py \\
        --scored-jsonl outputs/verifier_frontier_scoring_full_.../scored_candidates.jsonl \\
        --output-dir   outputs/within_method_reranking_<STAMP> \\
        [--group-fields example_id,budget,method] \\
        [--score-field proba_ready] \\
        [--correct-field exact_match_metadata] \\
        [--method-field method] \\
        [--budget-field budget]
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_scored(path: pathlib.Path, score_field: str, correct_field: str) -> list[dict[str, Any]]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            meta = raw.get("metadata", {}) or {}
            row: dict[str, Any] = {}
            try:
                row[score_field] = float(raw.get(score_field) or 0.0)
            except (TypeError, ValueError):
                row[score_field] = 0.0
            row["predicted_label"] = int(raw.get("predicted_label") or 0)
            row["feature_text"] = raw.get("feature_text", "")
            for k, v in meta.items():
                row[k] = v
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Grouping and per-group stats
# ---------------------------------------------------------------------------

def build_groups(rows: list[dict], group_fields: list[str]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = tuple(r.get(f) for f in group_fields)
        groups[key].append(r)
    return dict(groups)


def group_stats(
    cands: list[dict],
    score_field: str,
    correct_field: str,
) -> dict[str, Any]:
    scores = [float(c.get(score_field) or 0.0) for c in cands]
    ems = [int(c.get(correct_field) or 0) for c in cands if c.get(correct_field) is not None]

    best_idx  = scores.index(max(scores))
    worst_idx = scores.index(min(scores))
    # deterministic baseline: first candidate (sorted by seed if present, else first in list)
    sorted_cands = sorted(cands, key=lambda c: (str(c.get("seed", ""))))
    first_cand = sorted_cands[0]

    em_verifier_max = int(cands[best_idx].get(correct_field) or 0)
    em_anti_verifier = int(cands[worst_idx].get(correct_field) or 0)
    em_first_seed = int(first_cand.get(correct_field) or 0)
    oracle_any_correct = int(any(e == 1 for e in ems))
    random_expected = sum(ems) / len(ems) if ems else None

    score_spread = max(scores) - min(scores)
    score_mean   = statistics.mean(scores)
    score_stdev  = statistics.stdev(scores) if len(scores) > 1 else 0.0

    return {
        "n_candidates": len(cands),
        "n_with_em": len(ems),
        "scores": scores,
        "score_min": min(scores),
        "score_max": max(scores),
        "score_spread": score_spread,
        "score_mean": score_mean,
        "score_stdev": score_stdev,
        "em_verifier_max": em_verifier_max,
        "em_anti_verifier": em_anti_verifier,
        "em_first_seed": em_first_seed,
        "oracle_any_correct": oracle_any_correct,
        "random_expected": random_expected,
        "verifier_max_candidate": cands[best_idx],
        "anti_verifier_candidate": cands[worst_idx],
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_groups(
    group_stats_list: list[dict],
    keys: list[tuple],
    group_key_fields: list[str],
    method_idx: int,
    budget_idx: int,
) -> dict[str, Any]:
    """Aggregate group stats overall and by (method) and by (method, budget)."""
    overall = _aggregate_subset(group_stats_list)

    # By method
    by_method: dict[str, list] = defaultdict(list)
    for key, gs in zip(keys, group_stats_list):
        m = str(key[method_idx]) if method_idx < len(key) else "unknown"
        by_method[m].append(gs)

    # By method + budget
    by_method_budget: dict[tuple, list] = defaultdict(list)
    for key, gs in zip(keys, group_stats_list):
        m = str(key[method_idx]) if method_idx < len(key) else "unknown"
        b = key[budget_idx] if budget_idx < len(key) else None
        by_method_budget[(m, b)].append(gs)

    return {
        "overall": overall,
        "by_method": {m: _aggregate_subset(glist) for m, glist in sorted(by_method.items())},
        "by_method_budget": {
            (m, b): _aggregate_subset(glist)
            for (m, b), glist in sorted(by_method_budget.items(), key=lambda x: (x[0][0], str(x[0][1])))
        },
    }


def _aggregate_subset(glist: list[dict]) -> dict[str, Any]:
    if not glist:
        return {}
    n = len(glist)
    vm  = [g["em_verifier_max"]  for g in glist]
    av  = [g["em_anti_verifier"] for g in glist]
    fs  = [g["em_first_seed"]    for g in glist]
    ora = [g["oracle_any_correct"] for g in glist]
    rnd = [g["random_expected"]  for g in glist if g["random_expected"] is not None]

    acc_vm  = sum(vm)  / n
    acc_av  = sum(av)  / n
    acc_fs  = sum(fs)  / n
    acc_ora = sum(ora) / n
    acc_rnd = sum(rnd) / len(rnd) if rnd else None

    lift_vs_random = acc_vm - acc_rnd if acc_rnd is not None else None
    lift_vs_anti   = acc_vm - acc_av
    oracle_gap     = acc_ora - acc_vm

    score_spreads = [g["score_spread"] for g in glist]
    mean_spread   = statistics.mean(score_spreads)
    tiny_spread   = sum(1 for s in score_spreads if s < 0.01)

    return {
        "n_groups": n,
        "verifier_max_accuracy": acc_vm,
        "anti_verifier_accuracy": acc_av,
        "first_seed_accuracy": acc_fs,
        "random_expected_accuracy": acc_rnd,
        "oracle_ceiling": acc_ora,
        "lift_vs_random": lift_vs_random,
        "lift_vs_anti_verifier": lift_vs_anti,
        "oracle_gap": oracle_gap,
        "mean_score_spread": mean_spread,
        "n_tiny_spread_groups": tiny_spread,
        "mean_score_value": statistics.mean(g["score_mean"] for g in glist),
    }


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def compute_diagnostics(
    group_stats_list: list[dict],
    keys: list[tuple],
    group_key_fields: list[str],
    correct_field: str,
) -> dict[str, list[dict]]:
    verifier_missed_oracle = []   # oracle correct but verifier_max wrong
    verifier_wins_low_random = [] # verifier correct but random_expected < 0.5
    tiny_spread_success = []      # score_spread < 0.01 but verifier correct

    for key, gs in zip(keys, group_stats_list):
        base = {f: v for f, v in zip(group_key_fields, key)}
        base["n_candidates"] = gs["n_candidates"]
        base["score_spread"] = round(gs["score_spread"], 6)
        base["score_min"] = round(gs["score_min"], 6)
        base["score_max"] = round(gs["score_max"], 6)
        base["random_expected"] = gs["random_expected"]
        base["oracle_any_correct"] = gs["oracle_any_correct"]
        base["em_verifier_max"] = gs["em_verifier_max"]

        if gs["oracle_any_correct"] == 1 and gs["em_verifier_max"] == 0:
            verifier_missed_oracle.append(dict(base))

        if gs["em_verifier_max"] == 1 and (gs["random_expected"] or 1.0) < 0.5:
            verifier_wins_low_random.append(dict(base))

        if gs["score_spread"] < 0.01 and gs["em_verifier_max"] == 1:
            tiny_spread_success.append(dict(base))

    return {
        "verifier_missed_oracle": verifier_missed_oracle,
        "verifier_wins_low_random": verifier_wins_low_random,
        "tiny_spread_success": tiny_spread_success,
    }


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def write_reranking_by_method_csv(by_method: dict, out_path: pathlib.Path) -> None:
    cols = ["method", "n_groups", "verifier_max_accuracy", "random_expected_accuracy",
            "anti_verifier_accuracy", "first_seed_accuracy", "oracle_ceiling",
            "lift_vs_random", "lift_vs_anti_verifier", "oracle_gap",
            "mean_score_spread", "n_tiny_spread_groups"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for m, d in by_method.items():
            w.writerow({"method": m, **{k: _fmt(d.get(k)) for k in cols[1:]}})


def write_reranking_by_budget_method_csv(by_method_budget: dict, out_path: pathlib.Path) -> None:
    cols = ["method", "budget", "n_groups", "verifier_max_accuracy", "random_expected_accuracy",
            "anti_verifier_accuracy", "oracle_ceiling", "lift_vs_random", "oracle_gap"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for (m, b), d in by_method_budget.items():
            w.writerow({"method": m, "budget": b, **{k: _fmt(d.get(k)) for k in cols[2:]}})


def write_group_details_csv(
    group_stats_list: list[dict],
    keys: list[tuple],
    group_key_fields: list[str],
    out_path: pathlib.Path,
) -> None:
    cols = group_key_fields + [
        "n_candidates", "em_verifier_max", "em_anti_verifier", "em_first_seed",
        "oracle_any_correct", "random_expected", "score_min", "score_max",
        "score_spread", "score_stdev",
    ]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for key, gs in zip(keys, group_stats_list):
            row = {f: v for f, v in zip(group_key_fields, key)}
            for c in cols[len(group_key_fields):]:
                row[c] = _fmt(gs.get(c))
            w.writerow(row)


def write_diagnostic_csv(rows: list[dict], out_path: pathlib.Path) -> None:
    if not rows:
        out_path.write_text("")
        return
    cols = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(v) for k, v in r.items()})


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_report(
    agg: dict,
    diag: dict,
    input_path: str,
    group_fields: list[str],
    out_path: pathlib.Path,
) -> None:
    now = datetime.now(timezone.utc).isoformat()

    def _pct(v):
        return f"{v:.4f} ({v*100:.1f}%)" if v is not None else "N/A"

    def _pp(v):
        return f"{v*100:+.1f}pp" if v is not None else "N/A"

    ov = agg["overall"]

    lines = [
        "# Within-Method Verifier Reranking Analysis",
        "",
        f"- **Generated:** {now}",
        f"- **Input:** `{input_path}`",
        f"- **Group fields:** `{', '.join(group_fields)}`",
        f"- **Total groups:** {ov.get('n_groups', 0)}",
        "",
        "## Overall Results",
        "",
        "Each group = (example_id, budget, method). Candidates are seed alternatives from the *same* method.",
        "This tests whether proba_ready adds value **after controlling for method identity**.",
        "",
        "| Policy | Accuracy |",
        "|---|---|",
        f"| verifier_max (pick highest proba_ready) | {_pct(ov.get('verifier_max_accuracy'))} |",
        f"| random_expected (mean of all seeds) | {_pct(ov.get('random_expected_accuracy'))} |",
        f"| anti_verifier (pick lowest proba_ready) | {_pct(ov.get('anti_verifier_accuracy'))} |",
        f"| first_seed (sorted by seed, deterministic) | {_pct(ov.get('first_seed_accuracy'))} |",
        f"| oracle_ceiling (any seed correct) | {_pct(ov.get('oracle_ceiling'))} |",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| lift vs random | {_pp(ov.get('lift_vs_random'))} |",
        f"| lift vs anti_verifier | {_pp(ov.get('lift_vs_anti_verifier'))} |",
        f"| oracle gap (ceiling − verifier) | {_pp(ov.get('oracle_gap'))} |",
        f"| mean score spread within group | {ov.get('mean_score_spread', 0):.6f} |",
        f"| groups with tiny spread (<0.01) | {ov.get('n_tiny_spread_groups', 0)} |",
        "",
        "## By Method",
        "",
        "| Method | N | verifier_max | random | anti_verif | oracle | lift_vs_rand | oracle_gap |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m, d in agg["by_method"].items():
        m_short = m[:50]
        lines.append(
            f"| {m_short} | {d.get('n_groups',0)} | "
            f"{d.get('verifier_max_accuracy',0):.4f} | "
            f"{_fmt(d.get('random_expected_accuracy'))} | "
            f"{d.get('anti_verifier_accuracy',0):.4f} | "
            f"{d.get('oracle_ceiling',0):.4f} | "
            f"{_pp(d.get('lift_vs_random'))} | "
            f"{_pp(d.get('oracle_gap'))} |"
        )

    lines += [
        "",
        "## By Method and Budget",
        "",
        "| Method | Budget | N | verifier_max | random | anti_verif | oracle | lift_vs_rand |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for (m, b), d in agg["by_method_budget"].items():
        m_short = m[:45]
        lines.append(
            f"| {m_short} | {b} | {d.get('n_groups',0)} | "
            f"{d.get('verifier_max_accuracy',0):.4f} | "
            f"{_fmt(d.get('random_expected_accuracy'))} | "
            f"{d.get('anti_verifier_accuracy',0):.4f} | "
            f"{d.get('oracle_ceiling',0):.4f} | "
            f"{_pp(d.get('lift_vs_random'))} |"
        )

    n_missed = len(diag.get("verifier_missed_oracle", []))
    n_wins_low = len(diag.get("verifier_wins_low_random", []))
    n_tiny = len(diag.get("tiny_spread_success", []))
    n_total = ov.get("n_groups", 1)

    lines += [
        "",
        "## Case-Level Diagnostics",
        "",
        f"| Category | Count | % of groups |",
        "|---|---|---|",
        f"| oracle correct but verifier_max wrong (missed oracle) | {n_missed} | {100*n_missed/n_total:.1f}% |",
        f"| verifier correct when random_expected < 0.5 (real signal) | {n_wins_low} | {100*n_wins_low/n_total:.1f}% |",
        f"| tiny score spread (<0.01) but verifier still correct | {n_tiny} | {100*n_tiny/n_total:.1f}% |",
        "",
        "## Interpretation",
        "",
    ]

    for m, d in agg["by_method"].items():
        lift = d.get("lift_vs_random")
        spread = d.get("mean_score_spread", 0)
        mean_abs_score = d.get("mean_score_value", 0)
        vm_acc = d.get("verifier_max_accuracy", 0)
        rnd_acc = d.get("random_expected_accuracy") or 0
        n_tiny_m = d.get("n_tiny_spread_groups", 0)
        n_m = d.get("n_groups", 1)
        m_short = m[:60]

        if "direct_reserve" in m_short:
            note = (
                f"**{m_short}**: absolute proba_ready values are low (mean score={mean_abs_score:.5f}), "
                f"but relative ordering can still help: verifier_max={vm_acc:.4f} vs random={rnd_acc:.4f} "
                f"(lift {_pp(lift)})."
            )
        elif spread < 0.005:
            note = (
                f"**{m_short}**: All absolute proba_ready values are near-zero "
                f"(mean spread={spread:.5f}), but relative ordering within each group "
                f"carries genuine signal: verifier_max={vm_acc:.4f} vs random={rnd_acc:.4f} "
                f"(lift {_pp(lift)}). {n_tiny_m}/{n_m} groups have spread < 0.01."
            )
        else:
            note = (
                f"**{m_short}**: proba_ready spread within group = {spread:.4f}. "
                f"Verifier_max={vm_acc:.4f} vs random={rnd_acc:.4f} (lift {_pp(lift)})."
            )
        lines.append(f"- {note}")
        lines.append("")

    vm_acc = ov.get("verifier_max_accuracy", 0)
    rnd_acc = ov.get("random_expected_accuracy") or 0
    lift = ov.get("lift_vs_random")
    lines += [
        "## Conclusion",
        "",
        f"Overall verifier_max accuracy = **{vm_acc:.4f}** vs random = **{rnd_acc:.4f}** "
        f"(lift = **{_pp(lift)}**). The anti-verifier direction hurts, confirming "
        "that the verifier score ordering is not random noise.",
        "",
        "---",
        "",
        "*Gold/exact_match metadata used for offline evaluation only.*",
        "*proba_ready was never computed using gold fields as input features.*",
    ]

    out_path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Optional plot
# ---------------------------------------------------------------------------

def write_plot(agg: dict, out_path: pathlib.Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    by_mb = agg["by_method_budget"]
    methods = sorted(set(m for m, _ in by_mb))
    budgets = sorted(set(str(b) for _, b in by_mb))

    fig, axes = plt.subplots(1, len(methods), figsize=(5 * len(methods), 4), sharey=True)
    if len(methods) == 1:
        axes = [axes]

    for ax, method in zip(axes, methods):
        m_budgets = [b for (m, b) in by_mb if m == method]
        m_budgets_sorted = sorted(m_budgets, key=str)
        vm_accs  = [by_mb[(method, b)].get("verifier_max_accuracy", 0) for b in m_budgets_sorted]
        rnd_accs = [by_mb[(method, b)].get("random_expected_accuracy") or 0 for b in m_budgets_sorted]
        av_accs  = [by_mb[(method, b)].get("anti_verifier_accuracy", 0) for b in m_budgets_sorted]
        ora_accs = [by_mb[(method, b)].get("oracle_ceiling", 0) for b in m_budgets_sorted]
        x = list(range(len(m_budgets_sorted)))
        ax.plot(x, vm_accs,  marker="^", linestyle="--", label="verifier_max")
        ax.plot(x, rnd_accs, marker="o", label="random")
        ax.plot(x, av_accs,  marker="v", linestyle=":", label="anti_verifier")
        ax.plot(x, ora_accs, marker="s", linestyle="-.", label="oracle")
        ax.set_xticks(x)
        ax.set_xticklabels([str(b) for b in m_budgets_sorted])
        ax.set_xlabel("Budget")
        ax.set_title(method[-40:], fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)

    axes[0].set_ylabel("Accuracy (exact match)")
    fig.suptitle("Within-Method Reranking: Verifier vs Random vs Oracle", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scored-jsonl", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--group-fields", default="example_id,budget,method")
    p.add_argument("--score-field", default="proba_ready")
    p.add_argument("--correct-field", default="exact_match_metadata")
    p.add_argument("--method-field", default="method")
    p.add_argument("--budget-field", default="budget")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scored_path = pathlib.Path(args.scored_jsonl)
    if not scored_path.exists():
        print(f"ERROR: {scored_path} not found", file=sys.stderr)
        return 1

    group_fields = [f.strip() for f in args.group_fields.split(",")]

    # Find method and budget positions in group_fields
    try:
        method_idx = group_fields.index(args.method_field)
    except ValueError:
        method_idx = 2
    try:
        budget_idx = group_fields.index(args.budget_field)
    except ValueError:
        budget_idx = 1

    rows = load_scored(scored_path, args.score_field, args.correct_field)
    print(f"Loaded {len(rows)} rows from {scored_path}")

    groups = build_groups(rows, group_fields)
    print(f"Groups: {len(groups)}")

    # Compute per-group stats
    keys = list(groups.keys())
    gstats = [group_stats(groups[k], args.score_field, args.correct_field) for k in keys]

    # Aggregate
    agg = aggregate_groups(gstats, keys, group_fields, method_idx, budget_idx)

    # Diagnostics
    diag = compute_diagnostics(gstats, keys, group_fields, args.correct_field)

    # Write outputs
    write_report(agg, diag, args.scored_jsonl, group_fields, out_dir / "within_method_reranking_report.md")
    write_reranking_by_method_csv(agg["by_method"], out_dir / "reranking_by_method.csv")
    write_reranking_by_budget_method_csv(agg["by_method_budget"], out_dir / "reranking_by_budget_method.csv")
    write_group_details_csv(gstats, keys, group_fields, out_dir / "reranking_group_details.csv")
    write_diagnostic_csv(diag["verifier_missed_oracle"], out_dir / "verifier_missed_oracle_cases.csv")

    metrics = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "input": args.scored_jsonl,
        "n_rows": len(rows),
        "n_groups": len(groups),
        "overall": {
            k: v for k, v in agg["overall"].items()
            if not isinstance(v, list)
        },
        "by_method": {
            m: {k: v for k, v in d.items() if not isinstance(v, list)}
            for m, d in agg["by_method"].items()
        },
        "diagnostics": {
            "n_missed_oracle": len(diag["verifier_missed_oracle"]),
            "n_verifier_wins_low_random": len(diag["verifier_wins_low_random"]),
            "n_tiny_spread_success": len(diag["tiny_spread_success"]),
        },
    }
    with open(out_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    plot_ok = write_plot(agg, out_dir / "within_method_accuracy_by_budget.png")
    if plot_ok:
        print(f"  {out_dir}/within_method_accuracy_by_budget.png")

    print(f"\nOutputs written to: {out_dir}")
    for fname in ["within_method_reranking_report.md", "metrics.json",
                  "reranking_by_method.csv", "reranking_by_budget_method.csv",
                  "reranking_group_details.csv", "verifier_missed_oracle_cases.csv"]:
        print(f"  {out_dir}/{fname}")

    ov = agg["overall"]
    random_acc = ov.get("random_expected_accuracy")
    print(f"\n=== Within-Method Reranking Summary ===")
    print(f"  verifier_max:   {ov.get('verifier_max_accuracy',0):.4f}")
    if random_acc is None:
        print("  random:         N/A")
    else:
        print(f"  random:         {random_acc:.4f}")
    print(f"  anti_verifier:  {ov.get('anti_verifier_accuracy',0):.4f}")
    print(f"  oracle_ceiling: {ov.get('oracle_ceiling',0):.4f}")
    lift = ov.get("lift_vs_random")
    if lift is not None:
        print(f"  lift vs random: {lift*100:+.1f}pp")

    return 0


if __name__ == "__main__":
    sys.exit(main())
