"""Offline allocation policy comparison using verifier-scored frontier candidates.

Compares accuracy of:
  1. direct_reserve (baseline frontier method)
  2. external_l1_max (strong external baseline)
  3. verifier_guided (pick candidate with highest proba_ready per group)

Uses only metadata fields for evaluation. No API calls, no training.

Usage:
    python3 scripts/compare_allocation_policies.py \\
        --scored-jsonl outputs/verifier_frontier_scoring_full_.../scored_candidates.jsonl \\
        --output-dir   outputs/allocation_policy_comparison_<STAMP> \\
        [--group-fields example_id,budget,seed] \\
        [--budget-field budget] \\
        [--method-field method] \\
        [--score-field proba_ready] \\
        [--correct-field exact_match_metadata] \\
        [--mode report]
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
# Data loading
# ---------------------------------------------------------------------------

def load_scored(path: pathlib.Path, score_field: str, correct_field: str) -> list[dict[str, Any]]:
    """Load scored JSONL, flattening metadata into each row."""
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            meta = raw.get("metadata", {})
            row: dict[str, Any] = {}
            # top-level fields
            row["feature_text"] = raw.get("feature_text", "")
            row[score_field] = float(raw.get(score_field) or 0.0)
            row["predicted_label"] = int(raw.get("predicted_label") or 0)
            # metadata fields
            for k, v in meta.items():
                row[k] = v
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Per-method accuracy
# ---------------------------------------------------------------------------

def per_method_accuracy(
    rows: list[dict],
    method_field: str,
    correct_field: str,
) -> dict[str, dict]:
    by_method: dict[str, list] = defaultdict(list)
    for r in rows:
        m = str(r.get(method_field, ""))
        c = r.get(correct_field)
        if c is not None:
            by_method[m].append(int(c))
    return {
        m: {
            "n": len(vals),
            "n_correct": sum(vals),
            "accuracy": sum(vals) / len(vals) if vals else 0.0,
        }
        for m, vals in sorted(by_method.items())
    }


def per_method_budget_accuracy(
    rows: list[dict],
    method_field: str,
    budget_field: str,
    correct_field: str,
) -> dict[tuple, dict]:
    """Returns dict keyed by (method, budget)."""
    by: dict[tuple, list] = defaultdict(list)
    for r in rows:
        m = str(r.get(method_field, ""))
        b = r.get(budget_field)
        c = r.get(correct_field)
        if c is not None:
            by[(m, b)].append(int(c))
    return {
        k: {
            "method": k[0],
            "budget": k[1],
            "n": len(v),
            "n_correct": sum(v),
            "accuracy": sum(v) / len(v) if v else 0.0,
        }
        for k, v in sorted(by.items())
    }


# ---------------------------------------------------------------------------
# Pairwise group selection
# ---------------------------------------------------------------------------

def build_groups(
    rows: list[dict],
    group_fields: list[str],
) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = tuple(r.get(f) for f in group_fields)
        groups[key].append(r)
    return dict(groups)


def pairwise_policy_comparison(
    groups: dict[tuple, list[dict]],
    score_field: str,
    correct_field: str,
    method_field: str,
    budget_field: str,
    direct_reserve_name: str,
    external_name: str,
) -> dict[str, Any]:
    """For each group, compare: direct_reserve, external_l1_max, verifier_guided."""
    results = []
    for key, cands in groups.items():
        if len(cands) < 2:
            continue

        budget = next((c.get(budget_field) for c in cands), None)

        # Find candidates by method
        direct = next((c for c in cands if c.get(method_field) == direct_reserve_name), None)
        external = next((c for c in cands if c.get(method_field) == external_name), None)
        # Verifier-guided: highest score
        best_verifier = max(cands, key=lambda c: float(c.get(score_field) or 0.0))

        em_direct = int(direct.get(correct_field) or 0) if direct else None
        em_external = int(external.get(correct_field) or 0) if external else None
        em_verifier = int(best_verifier.get(correct_field) or 0)
        verifier_chose = best_verifier.get(method_field, "")

        disagree = (em_direct is not None and em_external is not None and em_direct != em_external)

        results.append({
            "group_key": key,
            "budget": budget,
            "em_direct_reserve": em_direct,
            "em_external_l1_max": em_external,
            "em_verifier_guided": em_verifier,
            "verifier_chose_method": verifier_chose,
            "disagree": disagree,
            "verifier_correct_on_disagree": em_verifier if disagree else None,
        })

    return _aggregate_pairwise(results, budget_field, direct_reserve_name, external_name)


def _aggregate_pairwise(results: list[dict], budget_field: str, direct_name: str, ext_name: str) -> dict[str, Any]:
    def _acc(vals):
        v = [x for x in vals if x is not None]
        return sum(v) / len(v) if v else None

    def _count_none(vals):
        return sum(1 for x in vals if x is not None)

    overall = {
        "n_groups": len(results),
        "direct_reserve": {
            "n": _count_none(r["em_direct_reserve"] for r in results),
            "accuracy": _acc(r["em_direct_reserve"] for r in results),
        },
        "external_l1_max": {
            "n": _count_none(r["em_external_l1_max"] for r in results),
            "accuracy": _acc(r["em_external_l1_max"] for r in results),
        },
        "verifier_guided": {
            "n": len(results),
            "accuracy": _acc(r["em_verifier_guided"] for r in results),
        },
    }

    # By budget
    by_budget: dict[Any, list] = defaultdict(list)
    for r in results:
        by_budget[r["budget"]].append(r)

    budget_breakdown = {}
    for b, brows in sorted(by_budget.items()):
        budget_breakdown[str(b)] = {
            "n": len(brows),
            "direct_reserve_accuracy": _acc(r["em_direct_reserve"] for r in brows),
            "external_l1_max_accuracy": _acc(r["em_external_l1_max"] for r in brows),
            "verifier_guided_accuracy": _acc(r["em_verifier_guided"] for r in brows),
        }

    # Disagreement analysis
    disagree_rows = [r for r in results if r["disagree"]]
    n_disagree = len(disagree_rows)
    verifier_wins = sum(1 for r in disagree_rows if r["verifier_correct_on_disagree"] == 1)

    # Verifier method choice frequency
    method_choices = defaultdict(int)
    for r in results:
        method_choices[r["verifier_chose_method"]] += 1

    return {
        "overall": overall,
        "by_budget": budget_breakdown,
        "disagreement": {
            "n_disagree": n_disagree,
            "verifier_correct": verifier_wins,
            "verifier_correct_rate": verifier_wins / n_disagree if n_disagree else None,
        },
        "verifier_method_choice": dict(method_choices),
        "raw": results,
    }


# ---------------------------------------------------------------------------
# Method-entanglement diagnostics
# ---------------------------------------------------------------------------

def method_entanglement_diagnostics(
    rows: list[dict],
    score_field: str,
    correct_field: str,
    method_field: str,
) -> dict[str, Any]:
    methods = sorted(set(str(r.get(method_field, "")) for r in rows))
    result = {}
    for m in methods:
        subset = [r for r in rows if str(r.get(method_field, "")) == m]
        scores = [float(r.get(score_field) or 0.0) for r in subset]
        sorted_s = sorted(scores)
        n = len(scores)

        def q(frac):
            idx = frac * (n - 1)
            lo, hi = int(idx), min(int(idx) + 1, n - 1)
            return sorted_s[lo] + (idx - lo) * (sorted_s[hi] - sorted_s[lo])

        bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
        bin_stats = []
        for lo, hi in bins:
            in_bin = [r for r in subset if lo <= float(r.get(score_field) or 0.0) < hi]
            em_vals = [int(r.get(correct_field) or 0) for r in in_bin if r.get(correct_field) is not None]
            bin_stats.append({
                "bin": f"[{lo:.1f},{min(hi,1.0):.1f}]",
                "n": len(in_bin),
                "accuracy": sum(em_vals) / len(em_vals) if em_vals else None,
            })

        result[m] = {
            "n": n,
            "mean": statistics.mean(scores) if scores else None,
            "median": statistics.median(scores) if scores else None,
            "q10": q(0.1) if n >= 2 else None,
            "q25": q(0.25) if n >= 2 else None,
            "q75": q(0.75) if n >= 2 else None,
            "q90": q(0.9) if n >= 2 else None,
            "n_above_0_5": sum(1 for s in scores if s >= 0.5),
            "bins": bin_stats,
        }

    # Entanglement warning
    method_names = list(result.keys())
    entangled = False
    entanglement_note = ""
    if len(method_names) == 2:
        m_a, m_b = method_names
        sep_a = result[m_a].get("n_above_0_5", 0) / result[m_a]["n"] if result[m_a]["n"] else 0
        sep_b = result[m_b].get("n_above_0_5", 0) / result[m_b]["n"] if result[m_b]["n"] else 0
        if sep_a < 0.05 and sep_b > 0.75:
            entangled = True
            entanglement_note = (
                f"WARNING: verifier has learned method identity. "
                f"{m_a}: {sep_a:.1%} above 0.5 vs {m_b}: {sep_b:.1%} above 0.5. "
                f"Verifier-guided selection will mostly reproduce {m_b} choices."
            )
        elif sep_b < 0.05 and sep_a > 0.75:
            entangled = True
            entanglement_note = (
                f"WARNING: verifier has learned method identity. "
                f"{m_b}: {sep_b:.1%} above 0.5 vs {m_a}: {sep_a:.1%} above 0.5. "
                f"Verifier-guided selection will mostly reproduce {m_a} choices."
            )

    result["__entanglement__"] = {
        "entangled": entangled,
        "note": entanglement_note,
    }
    return result


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def write_accuracy_by_budget_csv(
    by_budget: dict[str, dict],
    out_path: pathlib.Path,
) -> None:
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["budget", "n", "direct_reserve_accuracy",
                                           "external_l1_max_accuracy", "verifier_guided_accuracy"])
        w.writeheader()
        for b, row in sorted(by_budget.items(), key=lambda x: x[0]):
            w.writerow({
                "budget": b,
                "n": row["n"],
                "direct_reserve_accuracy": f"{row['direct_reserve_accuracy']:.4f}" if row['direct_reserve_accuracy'] is not None else "",
                "external_l1_max_accuracy": f"{row['external_l1_max_accuracy']:.4f}" if row['external_l1_max_accuracy'] is not None else "",
                "verifier_guided_accuracy": f"{row['verifier_guided_accuracy']:.4f}" if row['verifier_guided_accuracy'] is not None else "",
            })


def write_policy_pairwise_csv(
    overall: dict,
    out_path: pathlib.Path,
) -> None:
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["policy", "n", "accuracy"])
        w.writeheader()
        for policy, d in [
            ("direct_reserve", overall["direct_reserve"]),
            ("external_l1_max", overall["external_l1_max"]),
            ("verifier_guided", overall["verifier_guided"]),
        ]:
            w.writerow({
                "policy": policy,
                "n": d["n"],
                "accuracy": f"{d['accuracy']:.4f}" if d.get("accuracy") is not None else "",
            })


def write_score_bins_by_method_csv(
    entanglement: dict,
    out_path: pathlib.Path,
) -> None:
    rows = []
    for method, stats in entanglement.items():
        if method.startswith("__"):
            continue
        for b in stats.get("bins", []):
            rows.append({
                "method": method,
                "bin": b["bin"],
                "n": b["n"],
                "accuracy": f"{b['accuracy']:.4f}" if b["accuracy"] is not None else "",
            })
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["method", "bin", "n", "accuracy"])
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_report(
    overall: dict,
    by_budget: dict,
    disagree: dict,
    method_choices: dict,
    entanglement: dict,
    per_method: dict,
    input_path: str,
    out_path: pathlib.Path,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    ov = overall["overall"]

    def _pct(v):
        return f"{v:.4f} ({v*100:.1f}%)" if v is not None else "N/A"

    lines = [
        "# Offline Allocation Policy Comparison",
        "",
        f"- **Generated:** {now}",
        f"- **Input:** `{input_path}`",
        f"- **Groups:** {ov['n_groups']} (example_id × budget × seed)",
        "",
        "## 1. Per-Method Accuracy (all candidates)",
        "",
        "| Method | n | exact_match_rate |",
        "|---|---|---|",
    ]
    for m, d in per_method.items():
        lines.append(f"| {m} | {d['n']} | {d['accuracy']:.4f} ({d['accuracy']*100:.1f}%) |")

    lines += [
        "",
        "## 2. Pairwise Policy Selection (per group)",
        "",
        "Each group = one (example_id, budget, seed). One candidate per method per group.",
        "",
        "| Policy | n | Accuracy |",
        "|---|---|---|",
        f"| direct_reserve | {ov['direct_reserve']['n']} | {_pct(ov['direct_reserve']['accuracy'])} |",
        f"| external_l1_max | {ov['external_l1_max']['n']} | {_pct(ov['external_l1_max']['accuracy'])} |",
        f"| verifier_guided | {ov['verifier_guided']['n']} | {_pct(ov['verifier_guided']['accuracy'])} |",
        "",
        "## 3. Accuracy by Budget",
        "",
        "| Budget | n | direct_reserve | external_l1_max | verifier_guided |",
        "|---|---|---|---|---|",
    ]
    for b, bd in sorted(by_budget.items(), key=lambda x: x[0]):
        dr = f"{bd['direct_reserve_accuracy']:.4f}" if bd['direct_reserve_accuracy'] is not None else "N/A"
        ex = f"{bd['external_l1_max_accuracy']:.4f}" if bd['external_l1_max_accuracy'] is not None else "N/A"
        vg = f"{bd['verifier_guided_accuracy']:.4f}" if bd['verifier_guided_accuracy'] is not None else "N/A"
        lines.append(f"| {b} | {bd['n']} | {dr} | {ex} | {vg} |")

    lines += [
        "",
        "## 4. Disagreement Analysis",
        "",
        f"- Groups where methods disagree in exact_match: **{disagree['n_disagree']}**",
    ]
    if disagree["n_disagree"] > 0:
        lines.append(
            f"- Verifier picks correct candidate: "
            f"**{disagree['verifier_correct']}/{disagree['n_disagree']} = "
            f"{disagree['verifier_correct_rate']:.4f} ({disagree['verifier_correct_rate']*100:.1f}%)**"
        )

    lines += [
        "",
        "## 5. Verifier Method Choice",
        "",
        "| Method chosen by verifier | n | % |",
        "|---|---|---|",
    ]
    total_choices = sum(method_choices.values())
    for m, cnt in sorted(method_choices.items(), key=lambda x: -x[1]):
        lines.append(f"| {m} | {cnt} | {100*cnt/total_choices:.1f}% |")

    lines += ["", "## 6. Method-Entanglement Diagnostics", ""]
    ent = entanglement.get("__entanglement__", {})
    if ent.get("entangled"):
        lines.append(f"> **{ent['note']}**")
        lines.append("")
    else:
        lines.append("> No strong entanglement detected.")
        lines.append("")

    lines += [
        "| Method | n | mean proba | median | q10 | q25 | q75 | q90 | n≥0.5 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m, s in entanglement.items():
        if m.startswith("__"):
            continue
        def _f(v):
            return f"{v:.4f}" if v is not None else "N/A"
        lines.append(
            f"| {m} | {s['n']} | {_f(s.get('mean'))} | {_f(s.get('median'))} | "
            f"{_f(s.get('q10'))} | {_f(s.get('q25'))} | {_f(s.get('q75'))} | "
            f"{_f(s.get('q90'))} | {s.get('n_above_0_5',0)} |"
        )

    lines += ["", "### Score bins by method", "", "| Method | Bin | n | exact_match_rate |", "|---|---|---|---|"]
    for m, s in entanglement.items():
        if m.startswith("__"):
            continue
        for b in s.get("bins", []):
            acc = f"{b['accuracy']:.4f}" if b["accuracy"] is not None else "N/A"
            lines.append(f"| {m} | {b['bin']} | {b['n']} | {acc} |")

    lines += [
        "",
        "## 7. Interpretation",
        "",
        "- **verifier_guided vs external_l1_max**: gap = "
        + (f"{(ov['verifier_guided']['accuracy'] - ov['external_l1_max']['accuracy'])*100:+.1f}pp"
           if ov['verifier_guided']['accuracy'] is not None and ov['external_l1_max']['accuracy'] is not None
           else "N/A"),
        "- **verifier_guided vs direct_reserve**: gap = "
        + (f"{(ov['verifier_guided']['accuracy'] - ov['direct_reserve']['accuracy'])*100:+.1f}pp"
           if ov['verifier_guided']['accuracy'] is not None and ov['direct_reserve']['accuracy'] is not None
           else "N/A"),
        "",
        "---",
        "*Gold/correctness metadata used for offline evaluation only.*",
        "*Verifier scores (proba_ready) never include gold fields as input features.*",
    ]

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Matplotlib plot (optional)
# ---------------------------------------------------------------------------

def write_budget_plot(by_budget: dict, out_path: pathlib.Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    budgets = sorted(by_budget.keys(), key=lambda x: (str(x),))
    dr  = [by_budget[b]["direct_reserve_accuracy"] for b in budgets]
    ext = [by_budget[b]["external_l1_max_accuracy"] for b in budgets]
    vg  = [by_budget[b]["verifier_guided_accuracy"] for b in budgets]

    x = list(range(len(budgets)))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, dr,  marker="o", label="direct_reserve")
    ax.plot(x, ext, marker="s", label="external_l1_max")
    ax.plot(x, vg,  marker="^", linestyle="--", label="verifier_guided")
    ax.set_xticks(x)
    ax.set_xticklabels([str(b) for b in budgets])
    ax.set_xlabel("Budget")
    ax.set_ylabel("Accuracy (exact match)")
    ax.set_title("Policy Accuracy by Budget")
    ax.legend()
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scored-jsonl", required=True, help="Path to scored_candidates.jsonl")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--group-fields", default="example_id,budget,seed",
                   help="Comma-separated metadata fields that define a comparison group.")
    p.add_argument("--budget-field", default="budget")
    p.add_argument("--method-field", default="method")
    p.add_argument("--score-field", default="proba_ready")
    p.add_argument("--correct-field", default="exact_match_metadata",
                   help="Field name for correctness (1=correct). Falls back to 'exact_match'.")
    p.add_argument("--direct-reserve-name", default="direct_reserve_semantic_frontier_v2")
    p.add_argument("--external-name", default="external_l1_max")
    p.add_argument("--mode", choices=["report"], default="report")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scored_path = pathlib.Path(args.scored_jsonl)
    if not scored_path.exists():
        print(f"ERROR: scored JSONL not found: {scored_path}", file=sys.stderr)
        return 1

    group_fields = [f.strip() for f in args.group_fields.split(",")]

    # Load
    rows = load_scored(scored_path, args.score_field, args.correct_field)
    print(f"Loaded {len(rows)} rows from {scored_path}")

    # Correct-field fallback
    correct_field = args.correct_field
    if not any(correct_field in r for r in rows[:5]):
        alt = "exact_match"
        if any(alt in r for r in rows[:5]):
            correct_field = alt
            print(f"Using fallback correct-field: '{alt}'")

    # Per-method accuracy
    per_method = per_method_accuracy(rows, args.method_field, correct_field)
    per_method_bud = per_method_budget_accuracy(rows, args.method_field, args.budget_field, correct_field)

    # Groups
    groups = build_groups(rows, group_fields)
    print(f"Groups: {len(groups)}")

    # Pairwise
    pairwise = pairwise_policy_comparison(
        groups,
        score_field=args.score_field,
        correct_field=correct_field,
        method_field=args.method_field,
        budget_field=args.budget_field,
        direct_reserve_name=args.direct_reserve_name,
        external_name=args.external_name,
    )

    # Entanglement
    entanglement = method_entanglement_diagnostics(rows, args.score_field, correct_field, args.method_field)

    # Write outputs
    write_report(
        overall=pairwise,
        by_budget=pairwise["by_budget"],
        disagree=pairwise["disagreement"],
        method_choices=pairwise["verifier_method_choice"],
        entanglement=entanglement,
        per_method=per_method,
        input_path=args.scored_jsonl,
        out_path=out_dir / "policy_comparison_report.md",
    )

    write_accuracy_by_budget_csv(pairwise["by_budget"], out_dir / "accuracy_by_budget.csv")
    write_policy_pairwise_csv(pairwise["overall"], out_dir / "policy_pairwise_accuracy.csv")
    write_score_bins_by_method_csv(entanglement, out_dir / "score_bins_by_method.csv")

    metrics = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "input": args.scored_jsonl,
        "n_rows": len(rows),
        "n_groups": pairwise["overall"]["n_groups"],
        "per_method_accuracy": {m: d["accuracy"] for m, d in per_method.items()},
        "pairwise_accuracy": {
            "direct_reserve": pairwise["overall"]["direct_reserve"]["accuracy"],
            "external_l1_max": pairwise["overall"]["external_l1_max"]["accuracy"],
            "verifier_guided": pairwise["overall"]["verifier_guided"]["accuracy"],
        },
        "disagreement": pairwise["disagreement"],
        "verifier_method_choice": pairwise["verifier_method_choice"],
        "entanglement_warning": entanglement.get("__entanglement__", {}).get("note", ""),
    }
    with open(out_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    # Optional plot
    plot_ok = write_budget_plot(pairwise["by_budget"], out_dir / "accuracy_by_budget.png")
    if plot_ok:
        print(f"  {out_dir}/accuracy_by_budget.png")

    print(f"\nOutputs written to: {out_dir}")
    for fname in ["policy_comparison_report.md", "metrics.json", "accuracy_by_budget.csv",
                  "policy_pairwise_accuracy.csv", "score_bins_by_method.csv"]:
        print(f"  {out_dir}/{fname}")

    # Summary to stdout
    ov = pairwise["overall"]
    print(f"\n=== Policy Summary ===")
    for policy, key in [("direct_reserve", "direct_reserve"), ("external_l1_max", "external_l1_max"),
                         ("verifier_guided", "verifier_guided")]:
        acc = ov[key]["accuracy"]
        n = ov[key]["n"]
        print(f"  {policy:<45} {acc:.4f}  (n={n})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
