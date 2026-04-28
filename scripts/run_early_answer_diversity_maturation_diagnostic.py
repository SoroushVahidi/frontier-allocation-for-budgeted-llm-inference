#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


@dataclass
class Example:
    example_id: str
    question: str
    answer: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cached/simulation diagnostic for early_answer_diversity_maturation_v1.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--num-examples", type=int, default=18)
    p.add_argument("--budgets", default="4,6,8")
    return p.parse_args()


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _build_examples(seed: int, n: int) -> list[Example]:
    rng = random.Random(seed)
    out: list[Example] = []
    for i in range(n):
        a = rng.randint(11, 80)
        b = rng.randint(4, 35)
        c = rng.randint(2, 20)
        q = f"A warehouse has {a} boxes, receives {b} more, and then ships out {c}. How many remain?"
        out.append(Example(example_id=f"mock_{i}", question=q, answer=str(a + b - c)))
    return out


def _runtime_key(method: str) -> str:
    return STRICT_F3_RUNTIME if method == "strict_f3" else method


def _resolve_runtime_key(method: str, specs: dict[str, Any]) -> tuple[str | None, str]:
    direct = _runtime_key(method)
    if direct in specs:
        return direct, "direct"
    if method == "strict_gate1_cap_k6":
        candidates = [
            k
            for k in specs
            if "hard_max_family_expansions_cap_k6_v1_fixed_k6_control" in str(k)
        ]
        if candidates:
            return sorted(candidates)[0], "alias_resolved_from_fixed_k6_control_runtime"
    return None, "missing_from_registry_for_budget"


def _repeated_family_early_rate(trace: list[dict[str, Any]], early_prefix: int) -> float:
    early = [t for t in trace if str(t.get("action", "")) == "expand"][:early_prefix]
    if len(early) < 2:
        return 0.0
    repeats = sum(1 for i in range(1, len(early)) if str(early[i].get("strategy_family", "")) == str(early[i - 1].get("strategy_family", "")))
    return repeats / max(1, len(early) - 1)


def _paired_delta(rows: list[dict[str, Any]], method: str, baseline: str) -> dict[str, Any]:
    keyed: dict[tuple[str, int], dict[str, Any]] = {}
    base_keyed: dict[tuple[str, int], dict[str, Any]] = {}
    for r in rows:
        k = (str(r["example_id"]), int(r["budget"]))
        if str(r["method"]) == method:
            keyed[k] = r
        elif str(r["method"]) == baseline:
            base_keyed[k] = r
    pairs = sorted(set(keyed.keys()) & set(base_keyed.keys()))
    deltas = [int(keyed[k]["is_correct"]) - int(base_keyed[k]["is_correct"]) for k in pairs]
    return {
        "method": method,
        "baseline": baseline,
        "matched_pairs": len(pairs),
        "mean_delta": (sum(deltas) / max(1, len(deltas))) if deltas else 0.0,
        "wins": sum(1 for d in deltas if d > 0),
        "losses": sum(1 for d in deltas if d < 0),
        "ties": sum(1 for d in deltas if d == 0),
    }


def main() -> None:
    args = parse_args()
    budgets = [int(x.strip()) for x in args.budgets.split(",") if x.strip()]
    methods = [
        "strict_f3",
        "early_answer_diversity_maturation_v1",
        "early_answer_diversity_maturation_gated_v1",
        "strict_f3_anti_collapse_weak_v1",
        "strict_gate1_cap_k6",
        "external_l1_max",
    ]
    examples = _build_examples(seed=args.seed, n=args.num_examples)
    per_case: list[dict[str, Any]] = []
    excluded: dict[str, str] = {}

    for budget in budgets:
        rng = random.Random(args.seed + budget)
        factory = generator_factory_for_mode(
            use_openai_api=False,
            rng=rng,
            openai_model="command-r-plus-08-2024",
            temperature=0.1,
            max_output_tokens=256,
            timeout_seconds=45,
            api_provider="cohere",
        )
        specs = build_frontier_strategies(
            generator_factory=factory,
            budget=budget,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=False,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=True,
        )
        for method in methods:
            rk, status = _resolve_runtime_key(method, specs)
            if rk is None:
                excluded[method] = status
                continue
            controller = specs[rk]
            for ex in examples:
                result = controller.run(ex.question, ex.answer)
                meta = result.metadata or {}
                trace = list(meta.get("action_trace", [])) if isinstance(meta.get("action_trace", []), list) else []
                trigger_hits: dict[str, int] = {}
                for step in trace:
                    for trig in list(step.get("early_gated_override_triggers", []) or []):
                        t = str(trig)
                        trigger_hits[t] = trigger_hits.get(t, 0) + 1
                early_prefix = _safe_int(meta.get("early_prefix", min(3, max(1, budget // 2))), min(3, max(1, budget // 2)))
                failure = str(meta.get("early_divergence_failure_category", ""))
                per_case.append(
                    {
                        "example_id": ex.example_id,
                        "budget": budget,
                        "method": method,
                        "runtime_method": rk,
                        "prediction": result.prediction,
                        "is_correct": int(result.is_correct),
                        "actions": int(result.actions_used),
                        "expansions": int(result.expansions),
                        "absent_from_tree": int(failure == "absent_from_tree"),
                        "present_not_selected": int(failure == "present_not_selected"),
                        "early_prefix": early_prefix,
                        "early_unique_answer_groups": _safe_int(meta.get("unique_answer_groups_seen_early", 0), 0),
                        "early_repeated_family_expansions": _safe_int(meta.get("repeated_family_expansions_early", 0), 0),
                        "early_repeated_family_expansion_rate": _repeated_family_early_rate(trace, early_prefix),
                        "early_maturation_actions": _safe_int(meta.get("early_maturation_actions", 0), 0),
                        "early_gated_override_considered": _safe_int(meta.get("early_gated_override_considered", 0), 0),
                        "early_gated_override_applied": _safe_int(meta.get("early_gated_override_applied", 0), 0),
                        "early_gated_override_skipped_reason": str(meta.get("early_gated_override_skipped_reason", "")),
                        "early_gated_override_triggers": ";".join(sorted(trigger_hits.keys())),
                    }
                )

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_case:
        by_method[str(row["method"])].append(row)
    summary_rows: list[dict[str, Any]] = []
    for method in methods:
        rows = by_method.get(method, [])
        if not rows:
            continue
        n = max(1, len(rows))
        summary_rows.append(
            {
                "method": method,
                "n": len(rows),
                "accuracy": sum(_safe_int(r["is_correct"]) for r in rows) / n,
                "absent_from_tree_rate": sum(_safe_int(r["absent_from_tree"]) for r in rows) / n,
                "present_not_selected_rate": sum(_safe_int(r["present_not_selected"]) for r in rows) / n,
                "avg_actions": sum(_safe_float(r["actions"]) for r in rows) / n,
                "avg_expansions": sum(_safe_float(r["expansions"]) for r in rows) / n,
                "avg_early_unique_answer_groups": sum(_safe_float(r["early_unique_answer_groups"]) for r in rows) / n,
                "avg_early_repeated_family_expansion_rate": sum(_safe_float(r["early_repeated_family_expansion_rate"]) for r in rows) / n,
                "override_rate": sum(1 for r in rows if _safe_int(r.get("early_gated_override_applied"), 0) > 0) / n,
            }
        )

    paired_rows = []
    for method in ("early_answer_diversity_maturation_v1", "early_answer_diversity_maturation_gated_v1"):
        for baseline in ("strict_f3", "external_l1_max"):
            if baseline != method:
                paired_rows.append(_paired_delta(per_case, method, baseline))

    trigger_distribution_rows: list[dict[str, Any]] = []
    trigger_counts: defaultdict[str, int] = defaultdict(int)
    for row in per_case:
        if str(row.get("method")) != "early_answer_diversity_maturation_gated_v1":
            continue
        for trig in [t for t in str(row.get("early_gated_override_triggers", "")).split(";") if t]:
            trigger_counts[trig] += 1
    for k, v in sorted(trigger_counts.items()):
        trigger_distribution_rows.append({"trigger": k, "count": v})

    out_dir = REPO_ROOT / "outputs" / f"early_answer_diversity_maturation_diagnostic_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out_dir / "per_case_results.csv",
        per_case,
        [
            "example_id",
            "budget",
            "method",
            "runtime_method",
            "prediction",
            "is_correct",
            "actions",
            "expansions",
            "absent_from_tree",
            "present_not_selected",
            "early_prefix",
            "early_unique_answer_groups",
            "early_repeated_family_expansions",
            "early_repeated_family_expansion_rate",
            "early_maturation_actions",
            "early_gated_override_considered",
            "early_gated_override_applied",
            "early_gated_override_skipped_reason",
            "early_gated_override_triggers",
        ],
    )
    _write_csv(
        out_dir / "method_summary.csv",
        summary_rows,
        [
            "method",
            "n",
            "accuracy",
            "absent_from_tree_rate",
            "present_not_selected_rate",
            "avg_actions",
            "avg_expansions",
            "avg_early_unique_answer_groups",
            "avg_early_repeated_family_expansion_rate",
            "override_rate",
        ],
    )
    _write_csv(
        out_dir / "paired_deltas.csv",
        paired_rows,
        ["method", "baseline", "matched_pairs", "mean_delta", "wins", "losses", "ties"],
    )
    _write_csv(
        out_dir / "methods_excluded.csv",
        [{"method": m, "reason": r} for m, r in sorted(excluded.items())],
        ["method", "reason"],
    )
    _write_csv(
        out_dir / "trigger_distribution.csv",
        trigger_distribution_rows,
        ["trigger", "count"],
    )

    def _summary_for(method_name: str) -> dict[str, Any]:
        return next((r for r in summary_rows if str(r.get("method")) == method_name), {})

    gated_summary = _summary_for("early_answer_diversity_maturation_gated_v1")
    strict_summary = _summary_for("strict_f3")
    l1_summary = _summary_for("external_l1_max")
    gate1_status = (
        f"included (n={_summary_for('strict_gate1_cap_k6').get('n', 0)})"
        if _summary_for("strict_gate1_cap_k6")
        else f"excluded ({excluded.get('strict_gate1_cap_k6', 'unknown_reason')})"
    )
    acc_delta_vs_strict = _safe_float(gated_summary.get("accuracy")) - _safe_float(strict_summary.get("accuracy"))
    absent_delta_vs_strict = _safe_float(gated_summary.get("absent_from_tree_rate")) - _safe_float(
        strict_summary.get("absent_from_tree_rate")
    )
    acc_delta_vs_l1 = _safe_float(gated_summary.get("accuracy")) - _safe_float(l1_summary.get("accuracy"))
    recommendation = "keep diagnostic"
    if acc_delta_vs_strict < -0.03:
        recommendation = "discard"
    elif acc_delta_vs_strict > 0.01 and absent_delta_vs_strict <= 0.0:
        recommendation = "scale up"

    doc_path = REPO_ROOT / "docs" / f"EARLY_ANSWER_DIVERSITY_MATURATION_GATED_DIAGNOSTIC_{args.timestamp}.md"
    doc_path.write_text(
        "\n".join(
            [
                "# Early answer diversity maturation gated diagnostic",
                "",
                "- Status: experimental / diagnostic only",
                "- Why v1 was modified: unconditional early override was too disruptive and showed lower accuracy vs strict_f3 on prior simulation slice.",
                f"- Output directory: `{out_dir.relative_to(REPO_ROOT)}`",
                f"- Budgets: {budgets}",
                f"- Exact method list: {', '.join(methods)}",
                f"- strict_gate1_cap_k6: {gate1_status}",
                "- Data mode: cached/simulation only (deterministic mock arithmetic, no live API calls)",
                "",
                "## Key deltas (gated vs baselines)",
                f"- accuracy delta vs strict_f3: {acc_delta_vs_strict:.4f}",
                f"- absent-from-tree delta vs strict_f3: {absent_delta_vs_strict:.4f}",
                f"- accuracy delta vs external_l1_max: {acc_delta_vs_l1:.4f}",
                f"- override rate: {_safe_float(gated_summary.get('override_rate')):.4f}",
                f"- trigger distribution: {dict(trigger_counts)}",
                "",
                "## Recommendation",
                f"- {recommendation}",
                "- Keep v1 as provenance-only experimental method; do not promote either variant without consistent gains.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote diagnostic outputs to: {out_dir}")
    print(f"Wrote note: {doc_path}")


if __name__ == "__main__":
    main()
