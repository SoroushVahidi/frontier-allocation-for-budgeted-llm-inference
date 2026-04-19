#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples

BASE = "broad_diversity_aggregation_strong_v1"
ICC = "broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1"
ICC_RAW = "broad_diversity_aggregation_strong_v1_incumbent_challenger_raw_support_v1"
CANONICAL = ["self_consistency_3", "adaptive_min_expand_1", "selective_sc_hybrid_v1", "broad_diversity_aggregation_v1"]
DIAG = ["broad_diversity_aggregation_strong_v1_diversity_needed_gate"]


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _failure_group(row: dict[str, Any]) -> str:
    if row["is_correct"]:
        return "correct"
    m = row.get("metadata") or {}
    if row.get("prediction") is None:
        return "incomplete_or_non_terminal"
    if row.get("budget_exhausted") or (not bool(m.get("commit_triggered", False)) and int(row.get("actions_used", 0)) >= int(row.get("budget", 0)) - 1):
        return "wrong_commit_timing"
    if int(m.get("unique_answer_groups_seen", 0)) <= 1 or _safe_float(m.get("answer_support_entropy", 0.0)) < 0.25:
        return "insufficient_diversity_realized"
    if _safe_float(m.get("answer_group_margin", 0.0)) <= 0.2:
        return "ambiguity_near_tie"
    if bool(m.get("aggregation_used", False)) and _safe_float(m.get("group_support_fraction", 0.0)) < 0.62:
        return "aggregation_instability"
    return "other"


def _ic_state(meta: dict[str, Any]) -> dict[str, Any]:
    checks = meta.get("incumbent_challenger_checks") or []
    if not checks:
        return {}
    return checks[-1]


def main() -> None:
    p = argparse.ArgumentParser(description="Bounded incumbent-vs-challenger commit feasibility pass")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/incumbent_challenger_commit_feasibility_20260419")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)
    adaptive_grid = _parse_ints(args.adaptive_grid)

    methods = [BASE, ICC, ICC_RAW, *CANONICAL, *DIAG]

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rng_master = random.Random(20260419)
    rows: list[dict[str, Any]] = []

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            rng = random.Random(rng_master.randint(0, 10**9))
            factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
            for budget in budgets:
                strategies = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    include_selective_sc_hybrid_methods=True,
                    include_broad_diversity_aggregation_methods=True,
                )
                strategies = {k: v for k, v in strategies.items() if k in methods}
                for ex in examples:
                    for name, ctrl in strategies.items():
                        r = ctrl.run(ex.question, ex.answer)
                        row = {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": ex.example_id,
                            "problem_statement": ex.question,
                            "gold_answer": ex.answer,
                            "method": name,
                            "prediction": r.prediction,
                            "is_correct": bool(r.is_correct),
                            "actions_used": int(r.actions_used),
                            "expansions": int(r.expansions),
                            "verifications": int(r.verifications),
                            "budget_exhausted": bool(r.budget_exhausted),
                            "metadata": r.metadata,
                        }
                        row["failure_group"] = _failure_group(row)
                        rows.append(row)

    (out_dir / "per_example_results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    by_method = defaultdict(list)
    for r in rows:
        by_method[r["method"]].append(r)

    per_method: dict[str, dict[str, float]] = {}
    for m in methods:
        mr = by_method.get(m, [])
        n = max(1, len(mr))
        per_method[m] = {
            "n_examples": len(mr),
            "accuracy": sum(int(x["is_correct"]) for x in mr) / n,
            "avg_actions": sum(float(x["actions_used"]) for x in mr) / n,
            "wrong_commit_timing_count": sum(1 for x in mr if x["failure_group"] == "wrong_commit_timing"),
            "wrong_commit_timing_rate": sum(1 for x in mr if x["failure_group"] == "wrong_commit_timing") / n,
            "near_tie_accuracy": _mean([float(x["is_correct"]) for x in mr if _safe_float((x.get("metadata") or {}).get("answer_group_margin", 0.0)) <= 0.20]),
            "ic_intervention_count": sum(int((x.get("metadata") or {}).get("incumbent_challenger_intervention_count", 0)) for x in mr),
            "ic_commit_triggered_count": sum(int(bool((x.get("metadata") or {}).get("incumbent_challenger_commit_triggered", False))) for x in mr),
        }

    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        k = (str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        aligned[k][str(r["method"])] = r

    improved: list[dict[str, Any]] = []
    harmed: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    for pair in aligned.values():
        if BASE not in pair or ICC not in pair:
            continue
        b = pair[BASE]
        n = pair[ICC]
        b_state = _ic_state(b.get("metadata") or {})
        n_state = _ic_state(n.get("metadata") or {})
        rec = {
            "dataset": n["dataset"],
            "seed": n["seed"],
            "budget": n["budget"],
            "example_id": n["example_id"],
            "problem_statement": n["problem_statement"],
            "gold_answer": n["gold_answer"],
            "base_answer": b["prediction"],
            "new_answer": n["prediction"],
            "base_failure_group": b["failure_group"],
            "new_failure_group": n["failure_group"],
            "incumbent_group": n_state.get("incumbent"),
            "challenger_group": n_state.get("challenger"),
            "score_margin": n_state.get("score_margin"),
            "effective_support_gap": n_state.get("effective_support_gap"),
            "note": "",
        }
        if (not b["is_correct"]) and n["is_correct"]:
            rec["note"] = "incumbent/challenger commit logic likely avoided a commit-timing miss or resolved near tie"
            improved.append(rec)
        elif b["is_correct"] and (not n["is_correct"]):
            rec["note"] = "new commit rule likely committed/continued at a suboptimal point"
            harmed.append(rec)
        else:
            rec["note"] = "no final correctness change"
            unchanged.append(rec)

    (out_dir / "improved_cases.json").write_text(json.dumps(improved, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "harmed_cases.json").write_text(json.dumps(harmed, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "unchanged_cases.json").write_text(json.dumps(unchanged, indent=2, ensure_ascii=False), encoding="utf-8")

    # dependence-aware vs raw-support diagnostics
    ic_rows = [r for r in rows if r["method"] == ICC]
    ic_raw_rows = [r for r in rows if r["method"] == ICC_RAW]
    def _eff_vs_raw(rows_in: list[dict[str, Any]]) -> dict[str, float]:
        margins = []
        eff_gap = []
        for r in rows_in:
            st = _ic_state(r.get("metadata") or {})
            if not st:
                continue
            margins.append(float(st.get("score_margin", 0.0)))
            eff_gap.append(float(st.get("effective_support_gap", 0.0)))
        return {"mean_score_margin": _mean(margins), "mean_effective_support_gap": _mean(eff_gap), "n": len(margins)}

    dep_diag = {"dependence_aware": _eff_vs_raw(ic_rows), "raw_support_only": _eff_vs_raw(ic_raw_rows)}

    summary = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "methods": methods,
        "per_method": per_method,
        "delta_accuracy_ic_minus_base": float(per_method[ICC]["accuracy"] - per_method[BASE]["accuracy"]),
        "delta_wrong_commit_timing_ic_minus_base": int(per_method[ICC]["wrong_commit_timing_count"] - per_method[BASE]["wrong_commit_timing_count"]),
        "delta_accuracy_ic_raw_minus_base": float(per_method[ICC_RAW]["accuracy"] - per_method[BASE]["accuracy"]),
        "delta_wrong_commit_timing_ic_raw_minus_base": int(per_method[ICC_RAW]["wrong_commit_timing_count"] - per_method[BASE]["wrong_commit_timing_count"]),
        "improved_count": len(improved),
        "harmed_count": len(harmed),
        "unchanged_count": len(unchanged),
        "dependence_vs_raw_diagnostics": dep_diag,
        "failure_shift": {
            "base": dict(Counter(r["failure_group"] for r in by_method[BASE])),
            "icc": dict(Counter(r["failure_group"] for r in by_method[ICC])),
            "icc_raw": dict(Counter(r["failure_group"] for r in by_method[ICC_RAW])),
        },
        "is_serious_integration_candidate": bool(
            per_method[ICC]["accuracy"] >= per_method[BASE]["accuracy"]
            and per_method[ICC]["wrong_commit_timing_count"] <= per_method[BASE]["wrong_commit_timing_count"]
            and len(improved) >= len(harmed)
        ),
    }

    (out_dir / "comparison_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "per_method_metrics.json").write_text(json.dumps(per_method, indent=2), encoding="utf-8")
    (out_dir / "failure_shift_summary.json").write_text(json.dumps(summary["failure_shift"], indent=2), encoding="utf-8")
    run_manifest = {
        "script": "scripts/run_incumbent_challenger_commit_feasibility_pass_20260419.py",
        "command": f"python scripts/run_incumbent_challenger_commit_feasibility_pass_20260419.py --output-dir {args.output_dir}",
        "config": "configs/incumbent_challenger_commit_feasibility_20260419_v1.json",
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "methods": methods,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    note = [
        "# Incumbent-vs-challenger commit feasibility status (2026-04-19)",
        "",
        f"- Base accuracy: {per_method[BASE]['accuracy']:.4f}",
        f"- ICC accuracy: {per_method[ICC]['accuracy']:.4f} (delta {summary['delta_accuracy_ic_minus_base']:+.4f})",
        f"- ICC raw-support accuracy: {per_method[ICC_RAW]['accuracy']:.4f} (delta {summary['delta_accuracy_ic_raw_minus_base']:+.4f})",
        f"- wrong_commit_timing base -> ICC: {per_method[BASE]['wrong_commit_timing_count']} -> {per_method[ICC]['wrong_commit_timing_count']}",
        f"- wrong_commit_timing base -> ICC raw: {per_method[BASE]['wrong_commit_timing_count']} -> {per_method[ICC_RAW]['wrong_commit_timing_count']}",
        f"- improved/harmed/unchanged: {len(improved)}/{len(harmed)}/{len(unchanged)}",
        "",
        f"- Serious next integration candidate? {'yes' if summary['is_serious_integration_candidate'] else 'not yet'}",
        f"- Did it reduce wrong commit timing? {'yes' if per_method[ICC]['wrong_commit_timing_count'] < per_method[BASE]['wrong_commit_timing_count'] else 'no'}",
        (
            "- Did dependence-aware support help? yes"
            if per_method[ICC]["accuracy"] >= per_method[ICC_RAW]["accuracy"] and per_method[ICC]["wrong_commit_timing_count"] <= per_method[ICC_RAW]["wrong_commit_timing_count"]
            else "- Did dependence-aware support help? mixed_or_no"
        ),
        "- Best next step: run one deeper bounded threshold/stability calibration pass focused on commit timing without changing family.",
    ]
    (out_dir / "STATUS_NOTE_incumbent_challenger_commit_20260419.md").write_text("\n".join(note) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
