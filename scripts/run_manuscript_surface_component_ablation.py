#!/usr/bin/env python3
"""Component ablation on manuscript-facing canonical strict_f3 surface."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import importlib.util

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_for_manuscript_ablation", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()

DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
SEEDS = [11, 23]
BUDGETS = [4, 6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]

FULL_METHOD_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_"
    "incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)

VARIANTS: list[dict[str, Any]] = [
    {"variant": "full_method", "runtime_method": FULL_METHOD_RUNTIME, "enable_output_repair": True},
    {
        "variant": "no_answer_support_aggregation",
        "runtime_method": "strict_f3_ablation_no_answer_support_aggregation_v1",
        "enable_output_repair": True,
    },
    {
        "variant": "no_anti_collapse",
        "runtime_method": "strict_f3_ablation_no_anti_collapse_v1",
        "enable_output_repair": True,
    },
    {
        "variant": "no_repeat_expansion_control",
        "runtime_method": "strict_f3_ablation_no_repeat_expansion_control_v1",
        "enable_output_repair": True,
    },
    {"variant": "no_output_repair", "runtime_method": FULL_METHOD_RUNTIME, "enable_output_repair": False},
    {
        "variant": "upstream_only_core",
        "runtime_method": "strict_f3_ablation_upstream_only_core_v1",
        "enable_output_repair": False,
    },
]


def _stable_seed(*parts: Any) -> int:
    s = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16)


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _run_observed(runtime_method: str, dataset: str, seed: int, budget: int, example: Any) -> dict[str, Any]:
    run_seed = _stable_seed(
        "manuscript_surface_component_ablation",
        runtime_method,
        dataset,
        example.example_id,
        seed,
        budget,
    )
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
    final_nodes = []
    for _, b in sorted(observed.registry.items(), key=lambda kv: kv[0]):
        final_nodes.append(observed._snapshot(b))

    return {
        "result": result,
        "runtime_method": runtime_method,
        "final_nodes": final_nodes,
    }


def _classify(
    result: Any,
    final_nodes: list[dict[str, Any]],
    dataset: str,
    gold_raw: str,
    enable_output_repair: bool,
) -> dict[str, Any]:
    md = result.metadata or {}
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=md.get("selected_group"),
        dataset=dataset,
        enable_rescue=bool(enable_output_repair),
    )
    surfaced = repaired.get("surfaced_final_answer_raw")
    surfaced_can = canonicalize_answer(surfaced, dataset=dataset)
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
        failure = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        failure = "output_layer_mismatch"
    else:
        failure = "correct" if correct else "present_not_selected"
    return {
        "correct": bool(correct),
        "failure_type": failure,
        "gold_in_tree": int(gold_in_tree),
        "output_layer_mismatch": int(failure == "output_layer_mismatch"),
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n_cases": len(rows),
        "accuracy": _mean([1.0 if bool(r["correct"]) else 0.0 for r in rows]),
        "absent_from_tree": sum(1 for r in rows if r["failure_type"] == "absent_from_tree"),
        "present_not_selected": sum(1 for r in rows if r["failure_type"] == "present_not_selected"),
        "output_layer_mismatch": sum(1 for r in rows if r["failure_type"] == "output_layer_mismatch"),
        "avg_actions": _mean([float(r["actions"]) for r in rows]),
        "avg_expansions": _mean([float(r["expansions"]) for r in rows]),
        "avg_verifications": _mean([float(r["verifications"]) for r in rows]),
        "repeated_same_family_present": sum(1 for r in rows if int(r["repeated_same_family_present"]) > 0),
        "avg_max_family_expansion_share": _mean([float(r["max_family_expansion_share"]) for r in rows]),
        "avg_longest_same_family_run": _mean([float(r["longest_same_family_run"]) for r in rows]),
        "low_marginal_gain_trigger_count": sum(int(r["low_marginal_gain_triggered"]) for r in rows),
    }


def _pick_strongest_reduced(aggregate_rows: list[dict[str, Any]]) -> str:
    reduced = [r for r in aggregate_rows if r["variant"] not in {"full_method", "no_output_repair"}]
    reduced.sort(
        key=lambda r: (
            -float(r["accuracy"]),
            int(r["absent_from_tree"]),
            int(r["present_not_selected"]),
            float(r["avg_actions"]),
            str(r["variant"]),
        )
    )
    return str(reduced[0]["variant"]) if reduced else "upstream_only_core"


def main() -> None:
    # Pre-flight: verify this is manuscript-facing strict_f3 surface.
    ranking_path = REPO_ROOT / "outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv"
    if not ranking_path.exists():
        raise FileNotFoundError(f"Missing canonical manuscript-facing ranking surface: {ranking_path}")

    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/manuscript_surface_component_ablation_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case_rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in SEEDS:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
                for ex in examples:
                    for cfg in VARIANTS:
                        run = _run_observed(
                            runtime_method=str(cfg["runtime_method"]),
                            dataset=dataset,
                            seed=seed,
                            budget=budget,
                            example=ex,
                        )
                        result = run["result"]
                        md = result.metadata or {}
                        cls = _classify(
                            result=result,
                            final_nodes=list(run["final_nodes"]),
                            dataset=dataset,
                            gold_raw=str(ex.answer),
                            enable_output_repair=bool(cfg["enable_output_repair"]),
                        )
                        per_case_rows.append(
                            {
                                "variant": str(cfg["variant"]),
                                "runtime_method": str(cfg["runtime_method"]),
                                "enable_output_repair": bool(cfg["enable_output_repair"]),
                                "dataset": dataset,
                                "seed": int(seed),
                                "budget": int(budget),
                                "example_id": str(ex.example_id),
                                "correct": bool(cls["correct"]),
                                "failure_type": str(cls["failure_type"]),
                                "gold_in_tree": int(cls["gold_in_tree"]),
                                "output_layer_mismatch": int(cls["output_layer_mismatch"]),
                                "actions": int(result.actions_used),
                                "expansions": int(result.expansions),
                                "verifications": int(result.verifications),
                                "repeated_same_family_present": int(
                                    float(md.get("repeated_same_family_expansion_rate", 0.0)) > 0.0
                                ),
                                "max_family_expansion_share": float(md.get("max_family_expansion_share", 0.0)),
                                "longest_same_family_run": int(md.get("max_consecutive_same_family_expands", 0)),
                                "low_marginal_gain_triggered": int(
                                    int(md.get("low_marginal_gain_family_trigger_count", 0)) > 0
                                ),
                            }
                        )

    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_case_rows:
        by_variant[str(row["variant"])].append(row)

    aggregate_rows: list[dict[str, Any]] = []
    for variant, rows in sorted(by_variant.items()):
        aggregate_rows.append({"variant": variant, **_aggregate(rows)})

    strongest_reduced = _pick_strongest_reduced(aggregate_rows)
    strongest_row = next((r for r in aggregate_rows if r["variant"] == strongest_reduced), None)
    if strongest_row:
        aggregate_rows.append({"variant": "strongest_reduced_variant", **{k: v for k, v in strongest_row.items() if k != "variant"}})

    per_dataset_rows: list[dict[str, Any]] = []
    for ds in DATASETS:
        for variant in sorted(by_variant):
            sub = [r for r in by_variant[variant] if r["dataset"] == ds]
            per_dataset_rows.append({"dataset": ds, "variant": variant, **_aggregate(sub)})

    per_seed_rows: list[dict[str, Any]] = []
    for sd in SEEDS:
        for variant in sorted(by_variant):
            sub = [r for r in by_variant[variant] if int(r["seed"]) == sd]
            per_seed_rows.append({"seed": int(sd), "variant": variant, **_aggregate(sub)})

    failure_rows: list[dict[str, Any]] = []
    for variant in sorted(by_variant):
        sub = by_variant[variant]
        c = Counter(str(r["failure_type"]) for r in sub)
        n = max(1, len(sub))
        failure_rows.append(
            {
                "variant": variant,
                "n_cases": len(sub),
                "absent_from_tree_n": int(c.get("absent_from_tree", 0)),
                "present_not_selected_n": int(c.get("present_not_selected", 0)),
                "output_layer_mismatch_n": int(c.get("output_layer_mismatch", 0)),
                "absent_from_tree_rate": float(c.get("absent_from_tree", 0)) / n,
                "present_not_selected_rate": float(c.get("present_not_selected", 0)) / n,
                "output_layer_mismatch_rate": float(c.get("output_layer_mismatch", 0)) / n,
            }
        )

    diagnostics_rows: list[dict[str, Any]] = []
    for variant in sorted(by_variant):
        sub = by_variant[variant]
        diagnostics_rows.append(
            {
                "variant": variant,
                "avg_actions": _mean([float(r["actions"]) for r in sub]),
                "avg_expansions": _mean([float(r["expansions"]) for r in sub]),
                "avg_verifications": _mean([float(r["verifications"]) for r in sub]),
                "avg_max_family_expansion_share": _mean([float(r["max_family_expansion_share"]) for r in sub]),
                "avg_longest_same_family_run": _mean([float(r["longest_same_family_run"]) for r in sub]),
                "repeated_same_family_case_rate": _mean([1.0 if int(r["repeated_same_family_present"]) else 0.0 for r in sub]),
                "low_marginal_gain_trigger_rate": _mean([1.0 if int(r["low_marginal_gain_triggered"]) else 0.0 for r in sub]),
            }
        )

    _write_csv(out_dir / "per_case_results.csv", per_case_rows)
    _write_csv(out_dir / "aggregate_summary.csv", aggregate_rows)
    _write_csv(out_dir / "per_dataset_summary.csv", per_dataset_rows)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed_rows)
    _write_csv(out_dir / "failure_decomposition.csv", failure_rows)
    _write_csv(out_dir / "compute_allocation_diagnostics.csv", diagnostics_rows)

    summary_json = {
        "artifact_family": "manuscript_surface_component_ablation",
        "run_id": run_id,
        "surface": {
            "canonical_source": "outputs/canonical_full_method_ranking_20260421T212948Z",
            "our_method_lock": "strict_f3",
            "datasets": DATASETS,
            "seeds": SEEDS,
            "budgets": BUDGETS,
            "subset_size": SUBSET_SIZE,
        },
        "variants": VARIANTS,
        "strongest_reduced_variant": strongest_reduced,
        "total_case_evaluations": len(per_case_rows),
    }
    (out_dir / "aggregate_summary.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "name": "manuscript_surface_component_ablation",
                "run_id": run_id,
                "output_dir": str(out_dir.relative_to(REPO_ROOT)),
                "outputs": [
                    "aggregate_summary.csv",
                    "aggregate_summary.json",
                    "per_dataset_summary.csv",
                    "per_seed_summary.csv",
                    "failure_decomposition.csv",
                    "compute_allocation_diagnostics.csv",
                    "per_case_results.csv",
                    "status.json",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "status.json").write_text(json.dumps({"status": "ok", "n_rows": len(per_case_rows)}, indent=2), encoding="utf-8")

    report_path = REPO_ROOT / f"docs/MANUSCRIPT_SURFACE_COMPONENT_ABLATION_{run_id}.md"
    by_variant_agg = {r["variant"]: r for r in aggregate_rows}
    full = by_variant_agg["full_method"]
    no_ans = by_variant_agg["no_answer_support_aggregation"]
    no_anti = by_variant_agg["no_anti_collapse"]
    no_rep = by_variant_agg["no_repeat_expansion_control"]
    no_repair = by_variant_agg["no_output_repair"]
    lines = [
        f"# Manuscript-surface component ablation ({run_id})",
        "",
        "## Surface and method lock",
        "- Canonical manuscript-facing method lock: `strict_f3`.",
        "- Canonical fairness/matched surface: `outputs/canonical_full_method_ranking_20260421T212948Z/`.",
        f"- Datasets: {DATASETS}",
        f"- Seeds: {SEEDS}",
        f"- Budgets: {BUDGETS}",
        f"- Subset size per (dataset, seed): {SUBSET_SIZE}",
        "",
        "## Component-to-code mapping",
        "- answer-support aggregation: `experiments/controllers.py` (`_group_support_summary`, `_final_prediction_from_groups`; weights `answer_support_weight`, `value_weight`).",
        "- anti-collapse: `experiments/controllers.py` (`_anti_collapse_priority_adjustments`, `enable_anti_collapse_answer_group_refinement`).",
        "- repeat-expansion moderation: `experiments/controllers.py` (`repeat_expand_*`, low-marginal-gain cooldown signals).",
        "- bounded output repair: `experiments/output_layer_repair.py` (`choose_repair_answer(..., enable_rescue=...)`).",
        "",
        "## Aggregate summary",
        "",
        "| variant | accuracy | absent_from_tree | present_not_selected | output_layer_mismatch | avg_actions |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate_rows:
        lines.append(
            f"| {row['variant']} | {float(row['accuracy']):.4f} | {int(row['absent_from_tree'])} | {int(row['present_not_selected'])} | {int(row['output_layer_mismatch'])} | {float(row['avg_actions']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Explicit answers",
            f"- Component contributing most to final accuracy (drop vs full): `{min([('no_answer_support_aggregation', full['accuracy']-no_ans['accuracy']), ('no_anti_collapse', full['accuracy']-no_anti['accuracy']), ('no_repeat_expansion_control', full['accuracy']-no_rep['accuracy']), ('no_output_repair', full['accuracy']-no_repair['accuracy'])], key=lambda x: -x[1])[0]}`.",
            f"- Component most reducing `absent_from_tree` failures: `{min([('no_answer_support_aggregation', no_ans['absent_from_tree']-full['absent_from_tree']), ('no_anti_collapse', no_anti['absent_from_tree']-full['absent_from_tree']), ('no_repeat_expansion_control', no_rep['absent_from_tree']-full['absent_from_tree']), ('no_output_repair', no_repair['absent_from_tree']-full['absent_from_tree'])], key=lambda x: -x[1])[0]}`.",
            f"- Output repair appears secondary on this canonical surface: `{abs(float(full['accuracy']) - float(no_repair['accuracy'])) <= 0.01}`.",
            "- Manuscript claims support status: component-level support is partial and variant-dependent; avoid overclaiming universal gains from every component.",
            "",
            "## Artifacts",
            f"- `outputs/{out_dir.name}/aggregate_summary.csv`",
            f"- `outputs/{out_dir.name}/per_dataset_summary.csv`",
            f"- `outputs/{out_dir.name}/per_seed_summary.csv`",
            f"- `outputs/{out_dir.name}/failure_decomposition.csv`",
            f"- `outputs/{out_dir.name}/compute_allocation_diagnostics.csv`",
            f"- `outputs/{out_dir.name}/per_case_results.csv`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print(f"report={report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

