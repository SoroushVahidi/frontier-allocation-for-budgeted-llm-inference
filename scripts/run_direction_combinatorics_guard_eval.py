#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer
from experiments.problem_type_utils import classify_problem_type

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate strict_f3_direction_combinatorics_guard_v1 diagnostics.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--max-cases", type=int, default=0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--provider", default="cohere")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--input-package", default="outputs/detailed_loss_case_package_20260425T_WULVER_COHERE_LONG_DETAIL/")
    return p.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
            return
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def failure_type(*, exact: int, gold_ever_present: bool, gold_present_final: bool) -> str:
    if exact == 1:
        return "correct"
    if not gold_ever_present:
        return "absent_from_tree"
    if gold_present_final:
        return "output_layer_mismatch"
    return "present_not_selected"


def aggregate_summary(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    n = max(1, len(rows))
    return {
        "slice": label,
        "n": len(rows),
        "accuracy": sum(as_int(r.get("is_correct")) for r in rows) / n,
        "absent_from_tree_rate": sum(1 for r in rows if r.get("failure_type") == "absent_from_tree") / n,
        "present_not_selected_rate": sum(1 for r in rows if r.get("failure_type") == "present_not_selected") / n,
        "output_layer_mismatch_rate": sum(1 for r in rows if r.get("failure_type") == "output_layer_mismatch") / n,
        "avg_actions": sum(as_float(r.get("actions_used")) for r in rows) / n,
        "avg_expansions": sum(as_float(r.get("expansions")) for r in rows) / n,
        "avg_verifications": sum(as_float(r.get("verifications")) for r in rows) / n,
        "avg_verifier_calls": sum(as_float(r.get("verifier_calls")) for r in rows) / n,
        "counting_accuracy": (
            sum(as_int(r.get("is_correct")) for r in rows if r.get("problem_type") == "counting_combinatorics")
            / max(1, sum(1 for r in rows if r.get("problem_type") == "counting_combinatorics"))
        ),
        "non_counting_accuracy": (
            sum(as_int(r.get("is_correct")) for r in rows if r.get("problem_type") != "counting_combinatorics")
            / max(1, sum(1 for r in rows if r.get("problem_type") != "counting_combinatorics"))
        ),
    }


def main() -> None:
    args = parse_args()
    input_pkg = REPO_ROOT / args.input_package
    all_cases = read_csv(input_pkg / "all_paired_cases.csv")
    if not all_cases:
        raise RuntimeError(f"Missing input cases at {input_pkg / 'all_paired_cases.csv'}")
    if args.max_cases > 0:
        all_cases = all_cases[: args.max_cases]

    out_dir = REPO_ROOT / "outputs" / f"direction_combinatorics_guard_eval_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = read_csv(out_dir / "per_case_results.csv") if args.resume else []
    done = {(r["method"], r["example_id"], as_int(r["seed"]), as_int(r["budget"])) for r in existing}
    per_case = list(existing)

    budgets = sorted({as_int(r.get("budget")) for r in all_cases})
    methods = ["strict_f3", "strict_f3_direction_combinatorics_guard_v1", "external_l1_max"]
    controllers: dict[int, dict[str, Any]] = {}
    for b in budgets:
        rng = random.Random(100 + b)
        factory = generator_factory_for_mode(
            use_openai_api=not args.dry_run,
            rng=rng,
            openai_model=args.cohere_model,
            temperature=0.1,
            max_output_tokens=220,
            timeout_seconds=45,
            api_provider=args.provider,
        )
        controllers[b] = build_frontier_strategies(
            generator_factory=factory,
            budget=b,
            adaptive_min_expand_grid=[1],
            rng=rng,
            use_openai_api=not args.dry_run,
            include_broad_diversity_aggregation_methods=True,
            include_external_l1_baseline=True,
        )

    runtime_map = {
        "strict_f3": STRICT_F3_RUNTIME,
        "strict_f3_direction_combinatorics_guard_v1": "strict_f3_direction_combinatorics_guard_v1",
        "external_l1_max": "external_l1_max",
    }
    for c in all_cases:
        q = str(c.get("question") or "")
        g = str(c.get("gold_answer") or "")
        if q in {"", "NA"} or g in {"", "NA"}:
            continue
        seed = as_int(c.get("seed"))
        budget = as_int(c.get("budget"))
        example_id = str(c.get("example_id"))
        problem_type = classify_problem_type(q)
        for m in methods:
            k = (m, example_id, seed, budget)
            if k in done:
                continue
            specs = controllers[budget]
            runtime = runtime_map[m]
            if runtime not in specs:
                continue
            res = specs[runtime].run(q, g)
            meta = res.metadata or {}
            final_nodes = list(meta.get("final_nodes") or [])
            repaired = choose_repair_answer(
                final_nodes=final_nodes,
                selected_group_hint=meta.get("selected_group"),
                dataset="openai/gsm8k",
                enable_rescue=True,
            )
            surfaced = canonicalize_answer(repaired.get("surfaced_final_answer_raw"), dataset="openai/gsm8k")
            gold_can = canonicalize_answer(g, dataset="openai/gsm8k")
            exact = int(bool(surfaced == gold_can and surfaced is not None))
            ftype = failure_type(
                exact=exact,
                gold_ever_present=bool(meta.get("gold_group_ever_present", False)),
                gold_present_final=bool(meta.get("gold_group_present_final", False)),
            )
            per_case.append(
                {
                    "method": m,
                    "seed": seed,
                    "budget": budget,
                    "example_id": example_id,
                    "pair_type_baseline": c.get("pair_type"),
                    "strict_f3_failure_type_baseline": c.get("strict_f3_failure_type"),
                    "problem_type": problem_type,
                    "is_correct": exact,
                    "failure_type": ftype,
                    "actions_used": int(res.actions_used),
                    "expansions": int(res.expansions),
                    "verifications": int(res.verifications),
                    "verifier_calls": as_int(meta.get("verifier_calls", 0)),
                    "num_strategy_families_seen": as_int(meta.get("num_strategy_families_seen", 0)),
                    "dominant_family_share": as_float(meta.get("dominant_family_share", 0.0)),
                    "family_cap_blocked_expansion": as_int(meta.get("family_cap_blocked_expansion", 0)),
                    "commit_guard_triggered_count": as_int(meta.get("commit_guard_triggered_count", 0)),
                    "verifier_pass_count": as_int(meta.get("verifier_pass_count", 0)),
                    "verifier_warn_count": as_int(meta.get("verifier_warn_count", 0)),
                    "verifier_fail_count": as_int(meta.get("verifier_fail_count", 0)),
                    "selected_family_at_commit": meta.get("selected_family_at_commit", ""),
                }
            )
            done.add(k)

    write_csv(out_dir / "per_case_results.csv", per_case)

    rows_by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_case:
        rows_by_method[str(r["method"])].append(r)

    summary = [aggregate_summary(rows_by_method.get(m, []), m) for m in methods]
    write_csv(out_dir / "summary.csv", summary)

    slices = {
        "loss_150": lambda r: str(r.get("pair_type_baseline")) == "strict_f3_wrong_external_correct",
        "all_720": lambda r: True,
        "present_not_selected_subset": lambda r: str(r.get("strict_f3_failure_type_baseline")) == "present_not_selected",
        "absent_from_tree_subset": lambda r: str(r.get("strict_f3_failure_type_baseline")) == "absent_from_tree",
    }
    slice_rows: list[dict[str, Any]] = []
    for sname, pred in slices.items():
        for m in methods:
            sr = [r for r in rows_by_method.get(m, []) if pred(r)]
            row = aggregate_summary(sr, sname)
            row["method"] = m
            slice_rows.append(row)
    write_csv(out_dir / "slice_summary.csv", slice_rows)

    transition_rows: list[dict[str, Any]] = []
    for m in ["strict_f3_direction_combinatorics_guard_v1", "external_l1_max"]:
        mr = rows_by_method.get(m, [])
        tr = Counter()
        for r in mr:
            b = str(r.get("strict_f3_failure_type_baseline") or "")
            a = str(r.get("failure_type") or "")
            if b == "absent_from_tree" and a == "correct":
                tr["absent_from_tree -> correct"] += 1
            if b == "absent_from_tree" and a == "present_not_selected":
                tr["absent_from_tree -> present_not_selected"] += 1
            if b == "absent_from_tree" and a == "absent_from_tree":
                tr["absent_from_tree -> absent_from_tree"] += 1
            if b == "present_not_selected" and a == "correct":
                tr["present_not_selected -> correct"] += 1
            if b == "present_not_selected" and a == "present_not_selected":
                tr["present_not_selected -> still_present_not_selected"] += 1
            if b == "present_not_selected" and a == "absent_from_tree":
                tr["present_not_selected -> absent_from_tree"] += 1
        for k, v in tr.items():
            transition_rows.append({"method": m, "transition": k, "count": int(v), "share": v / max(1, len(mr))})
    write_csv(out_dir / "transition_summary.csv", transition_rows)

    family_cov = []
    for m in methods:
        mr = rows_by_method.get(m, [])
        n = max(1, len(mr))
        family_cov.append(
            {
                "method": m,
                "avg_num_strategy_families_seen": sum(as_float(r.get("num_strategy_families_seen", 0)) for r in mr) / n,
                "avg_dominant_family_share": sum(as_float(r.get("dominant_family_share", 0.0)) for r in mr) / n,
                "family_cap_trigger_rate": sum(1 for r in mr if as_int(r.get("family_cap_blocked_expansion", 0)) > 0) / n,
                "commit_guard_trigger_rate": sum(1 for r in mr if as_int(r.get("commit_guard_triggered_count", 0)) > 0) / n,
            }
        )
    write_csv(out_dir / "family_coverage_summary.csv", family_cov)

    commit_guard = []
    for m in methods:
        mr = rows_by_method.get(m, [])
        n = max(1, len(mr))
        commit_guard.append(
            {
                "method": m,
                "verifier_pass_rate": sum(as_int(r.get("verifier_pass_count", 0)) for r in mr) / n,
                "verifier_warn_rate": sum(as_int(r.get("verifier_warn_count", 0)) for r in mr) / n,
                "verifier_fail_rate": sum(as_int(r.get("verifier_fail_count", 0)) for r in mr) / n,
            }
        )
    write_csv(out_dir / "commit_guard_summary.csv", commit_guard)
    write_csv(out_dir / "verifier_diagnostics.csv", commit_guard)
    write_csv(
        out_dir / "present_not_selected_repair_cases.csv",
        [r for r in rows_by_method.get("strict_f3_direction_combinatorics_guard_v1", []) if r.get("strict_f3_failure_type_baseline") == "present_not_selected" and r.get("failure_type") == "correct"],
    )
    write_csv(
        out_dir / "absent_from_tree_repair_cases.csv",
        [r for r in rows_by_method.get("strict_f3_direction_combinatorics_guard_v1", []) if r.get("strict_f3_failure_type_baseline") == "absent_from_tree" and r.get("failure_type") == "correct"],
    )

    readme = [
        f"# direction_combinatorics_guard_eval_{args.timestamp}",
        "",
        f"- input_package: `{args.input_package}`",
        f"- cases_evaluated: {len({(r['example_id'], r['seed'], r['budget']) for r in per_case})}",
        f"- dry_run: {bool(args.dry_run)}",
    ]
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    s_map = {(r["slice"], r["method"]): r for r in slice_rows}
    b = s_map.get(("loss_150", "strict_f3"), {})
    n = s_map.get(("loss_150", "strict_f3_direction_combinatorics_guard_v1"), {})
    report = REPO_ROOT / "docs" / f"DIRECTION_COMBINATORICS_GUARD_EVAL_{args.timestamp}.md"
    report.write_text(
        "\n".join(
            [
                f"# DIRECTION_COMBINATORICS_GUARD_EVAL_{args.timestamp}",
                "",
                f"1. Absent-from-tree reduced on 150 losses? {'yes' if as_float(n.get('absent_from_tree_rate',1.0)) < as_float(b.get('absent_from_tree_rate',1.0)) else 'no_or_neutral'}.",
                f"2. Present-not-selected reduced? {'yes' if as_float(n.get('present_not_selected_rate',1.0)) < as_float(b.get('present_not_selected_rate',1.0)) else 'no_or_neutral'}.",
                f"3. Counting/combinatorics accuracy improved? {'yes' if as_float(n.get('counting_accuracy',0.0)) > as_float(b.get('counting_accuracy',0.0)) else 'no_or_neutral'}.",
                f"4. Present-but-mis-scored repairs: {len(read_csv(out_dir / 'present_not_selected_repair_cases.csv'))}.",
                f"5. Cost/actions increase: baseline avg_actions={as_float(b.get('avg_actions',0.0)):.3f}, new={as_float(n.get('avg_actions',0.0)):.3f}.",
                "6. Mechanism impact: inspect family_coverage_summary.csv + commit_guard_summary.csv + transition_summary.csv.",
                "7. Candidate status: diagnostic unless gains persist in real API runs and broader slices.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "output_dir": str(out_dir.relative_to(REPO_ROOT)),
                "report": str(report.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

