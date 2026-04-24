#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer


CANONICAL_SURFACE_ID = "canonical_full_method_ranking_20260421T212948Z"
DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
BUDGETS = [4, 6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]
DEFAULT_SEEDS = [11, 23, 37, 41, 53, 67]

VARIANTS: list[dict[str, Any]] = [
    {"variant": "anti_collapse_off", "runtime_method": "strict_f3_ablation_no_anti_collapse_v1", "enable_output_repair": True},
    {"variant": "anti_collapse_weak", "runtime_method": "strict_f3_anti_collapse_weak_v1", "enable_output_repair": True},
    {
        "variant": "anti_collapse_default",
        "runtime_method": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
        "enable_output_repair": True,
    },
    {"variant": "anti_collapse_strong", "runtime_method": "strict_f3_anti_collapse_strong_v1", "enable_output_repair": True},
    {"variant": "anti_collapse_conditional", "runtime_method": "strict_f3_anti_collapse_conditional_v1", "enable_output_repair": True},
]


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_for_anti_collapse_calibration", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def stable_seed(*parts: Any) -> int:
    s = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16)


def mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_observed(runtime_method: str, dataset: str, seed: int, budget: int, example: Any) -> dict[str, Any]:
    run_seed = stable_seed("anti_collapse_calibration_sweep", runtime_method, dataset, example.example_id, seed, budget)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(
        TW.SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    )

    def factory() -> Any:
        return observed

    specs = build_frontier_strategies(
        factory,
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    result = specs[runtime_method].run(example.question, example.answer)
    final_nodes = [observed._snapshot(b) for _, b in sorted(observed.registry.items(), key=lambda kv: kv[0])]
    return {"result": result, "final_nodes": final_nodes}


def classify(result: Any, final_nodes: list[dict[str, Any]], dataset: str, gold_raw: str, enable_output_repair: bool) -> dict[str, Any]:
    md = result.metadata or {}
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=md.get("selected_group"),
        dataset=dataset,
        enable_rescue=bool(enable_output_repair),
    )
    surfaced_can = canonicalize_answer(repaired.get("surfaced_final_answer_raw"), dataset=dataset)
    gold_can = canonicalize_answer(gold_raw, dataset=dataset)
    correct = bool(surfaced_can == gold_can and surfaced_can is not None)
    gold_in_tree = any(n.get("predicted_answer_normalized") == gold_can for n in final_nodes)

    output_mismatch = bool(
        gold_in_tree
        and (repaired.get("chosen_final_node_answer_canonical") == gold_can)
        and (surfaced_can != gold_can)
    )
    extraction_mismatch = bool(
        repaired.get("chosen_final_node_answer_canonical") != repaired.get("extracted_final_answer_canonical")
        or repaired.get("extracted_final_answer_canonical") != repaired.get("surfaced_final_answer_canonical")
    )
    if not gold_in_tree:
        failure_type = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        failure_type = "output_layer_mismatch"
    else:
        failure_type = "correct" if correct else "present_not_selected"

    return {
        "correct": int(correct),
        "failure_type": failure_type,
        "absent_from_tree": int(failure_type == "absent_from_tree"),
        "present_not_selected": int(failure_type == "present_not_selected"),
        "output_layer_mismatch": int(failure_type == "output_layer_mismatch"),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run anti-collapse calibration sweep on canonical matched manuscript-facing strict_f3 surface.")
    p.add_argument("--timestamp", default=utc_timestamp())
    p.add_argument("--seeds", default=",".join(str(s) for s in DEFAULT_SEEDS))
    p.add_argument("--budgets", default=",".join(str(b) for b in BUDGETS))
    p.add_argument("--subset-size", type=int, default=SUBSET_SIZE)
    return p.parse_args()


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    return {
        "n_cases": n,
        "mean_accuracy": mean([float(r["is_correct"]) for r in rows]),
        "absent_from_tree_count": sum(int(r["absent_from_tree"]) for r in rows),
        "absent_from_tree_rate": mean([float(r["absent_from_tree"]) for r in rows]),
        "present_not_selected_count": sum(int(r["present_not_selected"]) for r in rows),
        "present_not_selected_rate": mean([float(r["present_not_selected"]) for r in rows]),
        "output_layer_mismatch_count": sum(int(r["output_layer_mismatch"]) for r in rows),
        "output_layer_mismatch_rate": mean([float(r["output_layer_mismatch"]) for r in rows]),
        "avg_actions": mean([float(r["actions"]) for r in rows]),
        "avg_distinct_answer_groups": mean([float(r["distinct_answer_groups_explored"]) for r in rows]),
        "avg_repeated_family_concentration": mean([float(r["max_family_expansion_share"]) for r in rows]),
        "avg_repeated_family_expansion_rate": mean([float(r["repeated_same_family_expansion_rate"]) for r in rows]),
    }


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    budgets = [int(x.strip()) for x in args.budgets.split(",") if x.strip()]

    ranking_path = REPO_ROOT / f"outputs/{CANONICAL_SURFACE_ID}/overall_ranking.csv"
    if not ranking_path.exists():
        raise FileNotFoundError(f"Missing canonical manuscript-facing ranking surface: {ranking_path}")

    out_dir = REPO_ROOT / f"outputs/anti_collapse_calibration_sweep_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            for budget in budgets:
                for ex in examples:
                    for variant_cfg in VARIANTS:
                        run = run_observed(str(variant_cfg["runtime_method"]), dataset, seed, budget, ex)
                        result = run["result"]
                        cls = classify(result, run["final_nodes"], dataset, str(ex.answer), bool(variant_cfg["enable_output_repair"]))
                        md = result.metadata or {}
                        rows.append(
                            {
                                "variant": str(variant_cfg["variant"]),
                                "runtime_method": str(variant_cfg["runtime_method"]),
                                "dataset": dataset,
                                "seed": seed,
                                "budget": budget,
                                "example_id": str(ex.example_id),
                                "is_correct": int(cls["correct"]),
                                "failure_type": cls["failure_type"],
                                "absent_from_tree": int(cls["absent_from_tree"]),
                                "present_not_selected": int(cls["present_not_selected"]),
                                "output_layer_mismatch": int(cls["output_layer_mismatch"]),
                                "actions": int(result.actions_used),
                                "expansions": int(result.expansions),
                                "verifications": int(result.verifications),
                                "distinct_answer_groups_explored": int(md.get("unique_answer_groups_seen", 0)),
                                "repeated_same_family_expansion_rate": float(md.get("repeated_same_family_expansion_rate", 0.0)),
                                "max_family_expansion_share": float(md.get("max_family_expansion_share", 0.0)),
                                "longest_same_family_run": int(md.get("max_consecutive_same_family_expands", 0)),
                            }
                        )

    write_csv(out_dir / "per_case_outcomes.csv", rows)

    default_rows = [r for r in rows if r["variant"] == "anti_collapse_default"]
    default_accuracy = mean([float(r["is_correct"]) for r in default_rows])

    calibration_summary: list[dict[str, Any]] = []
    for variant in [v["variant"] for v in VARIANTS]:
        sub = [r for r in rows if r["variant"] == variant]
        agg = _aggregate(sub)
        calibration_summary.append(
            {
                "variant": variant,
                **agg,
                "delta_accuracy_vs_default": float(agg["mean_accuracy"]) - float(default_accuracy),
            }
        )
    write_csv(out_dir / "calibration_summary.csv", calibration_summary)

    def _group_summary(key: str, output_name: str) -> None:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            grouped[(str(r["variant"]), str(r[key]))].append(r)
        out_rows = []
        for (variant, key_val), bucket in sorted(grouped.items()):
            agg = _aggregate(bucket)
            out_rows.append({"variant": variant, key: key_val, **agg})
        write_csv(out_dir / output_name, out_rows)

    _group_summary("budget", "per_budget_summary.csv")
    _group_summary("dataset", "per_dataset_summary.csv")
    _group_summary("seed", "per_seed_summary.csv")

    failure_rows = []
    for variant in [v["variant"] for v in VARIANTS]:
        sub = [r for r in rows if r["variant"] == variant]
        n = max(1, len(sub))
        failure_rows.append(
            {
                "variant": variant,
                "absent_from_tree_count": sum(int(r["absent_from_tree"]) for r in sub),
                "absent_from_tree_rate": mean([float(r["absent_from_tree"]) for r in sub]),
                "present_not_selected_count": sum(int(r["present_not_selected"]) for r in sub),
                "present_not_selected_rate": mean([float(r["present_not_selected"]) for r in sub]),
                "output_layer_mismatch_count": sum(int(r["output_layer_mismatch"]) for r in sub),
                "output_layer_mismatch_rate": mean([float(r["output_layer_mismatch"]) for r in sub]),
                "n_cases": n,
            }
        )
    write_csv(out_dir / "failure_decomposition.csv", failure_rows)

    mechanism_rows = []
    for variant in [v["variant"] for v in VARIANTS]:
        sub = [r for r in rows if r["variant"] == variant]
        mechanism_rows.append(
            {
                "variant": variant,
                "avg_distinct_answer_groups_explored": mean([float(r["distinct_answer_groups_explored"]) for r in sub]),
                "avg_repeated_family_concentration": mean([float(r["max_family_expansion_share"]) for r in sub]),
                "avg_repeated_family_expansion_rate": mean([float(r["repeated_same_family_expansion_rate"]) for r in sub]),
                "avg_longest_same_family_run": mean([float(r["longest_same_family_run"]) for r in sub]),
            }
        )
    write_csv(out_dir / "mechanism_diagnostics.csv", mechanism_rows)

    best_variant = max(calibration_summary, key=lambda r: float(r["mean_accuracy"]))["variant"]
    default_row = next(r for r in calibration_summary if r["variant"] == "anti_collapse_default")
    off_row = next(r for r in calibration_summary if r["variant"] == "anti_collapse_off")
    weak_row = next(r for r in calibration_summary if r["variant"] == "anti_collapse_weak")
    conditional_row = next(r for r in calibration_summary if r["variant"] == "anti_collapse_conditional")
    if best_variant == "anti_collapse_default":
        classification = (
            "Default anti-collapse wins on this matched surface slice; earlier anti-collapse ablation concern appears seed/surface fragile "
            "and Figure 7 discussion should be revised accordingly."
        )
    elif best_variant in {"anti_collapse_weak", "anti_collapse_conditional"} or (
        float(weak_row["mean_accuracy"]) > float(default_row["mean_accuracy"]) and float(conditional_row["mean_accuracy"]) >= float(off_row["mean_accuracy"])
    ):
        classification = (
            "Default anti-collapse appears overactive/miscalibrated on this surface; weaker or conditional anti-collapse is favored over fixed default."
        )
    elif best_variant == "anti_collapse_off":
        classification = (
            "Anti-collapse is not validated as an accuracy-improving component on this matched surface slice and should be treated as a design-axis/diagnostic, "
            "not a confirmed independent contribution."
        )
    else:
        classification = (
            "Anti-collapse effects are mixed and surface-sensitive in this calibration sweep; retain as a diagnostic design axis unless further evidence stabilizes gains."
        )

    summary_lines = [
        f"# ANTI_COLLAPSE_CALIBRATION_SWEEP_{args.timestamp}",
        "",
        "Safe manuscript wording: Early tree-shape control remains important, but the fixed anti-collapse heuristic is surface-sensitive.",
        "",
        "## Classification",
        classification,
        "",
        "## Key metrics",
        f"- Default accuracy: {float(default_row['mean_accuracy']):.4f}",
        f"- Off accuracy: {float(off_row['mean_accuracy']):.4f} (delta vs default {float(off_row['delta_accuracy_vs_default']):+.4f})",
        f"- Weak accuracy: {float(weak_row['mean_accuracy']):.4f} (delta vs default {float(weak_row['delta_accuracy_vs_default']):+.4f})",
        f"- Conditional accuracy: {float(conditional_row['mean_accuracy']):.4f} (delta vs default {float(conditional_row['delta_accuracy_vs_default']):+.4f})",
        "",
        "## Safe interpretation language",
        "- Anti-collapse behavior is surface-sensitive and may require weakening or conditional activation.",
        "- Treat anti-collapse as a diagnostic design axis unless this calibrated setting remains robust across surfaces.",
        "- Do not claim every Strict-F3 subcomponent independently improves accuracy.",
        "",
        "## Forbidden wording",
        "- Anti-collapse universally improves performance.",
        "- Anti-collapse **always** improves accuracy.",
        "- Every component of Strict-F3 independently improves accuracy.",
        "- Figure 7 proves anti-collapse is beneficial.",
        "- The full controller is validated component-by-component.",
    ]
    (out_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": "anti_collapse_calibration_sweep",
        "timestamp": args.timestamp,
        "surface": {
            "canonical_surface_id": CANONICAL_SURFACE_ID,
            "datasets": DATASETS,
            "budgets": budgets,
            "seeds": seeds,
            "subset_size": args.subset_size,
        },
        "variants": VARIANTS,
        "classification": classification,
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "files": [
            "manifest.json",
            "per_case_outcomes.csv",
            "calibration_summary.csv",
            "per_budget_summary.csv",
            "per_dataset_summary.csv",
            "per_seed_summary.csv",
            "failure_decomposition.csv",
            "mechanism_diagnostics.csv",
            "summary.md",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    doc_lines = [
        f"# ANTI_COLLAPSE_CALIBRATION_SWEEP_{args.timestamp}",
        "",
        "## Why this was run",
        "The strict_f3 manuscript-facing component ablations raised a concern that removing anti-collapse could improve accuracy.",
        "This targeted sweep calibrates anti-collapse intensity/activation on the same canonical matched surface.",
        "",
        "## Outcome classification",
        classification,
        "",
        "## Manuscript-safe framing",
        "Early tree-shape control remains important, but the fixed anti-collapse heuristic is surface-sensitive.",
        "The calibration sweep indicates whether answer-distinct preservation should be weakened, conditioned, or treated as a diagnostic design axis.",
        "",
        "## Forbidden wording",
        "- Anti-collapse universally improves performance.",
        "- Anti-collapse **always** improves accuracy.",
        "- Every component of Strict-F3 independently improves accuracy.",
        "- Figure 7 proves anti-collapse is beneficial.",
        "- The full controller is validated component-by-component.",
    ]
    (REPO_ROOT / "docs" / "ANTI_COLLAPSE_CALIBRATION_SWEEP_REPORT.md").write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(out_dir.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
