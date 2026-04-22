#!/usr/bin/env python3
"""Canonical-surface component ablation for strict_gate1_cap_k6 integrated controller."""

from __future__ import annotations

import csv
import importlib.util
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import choose_repair_answer


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_module(REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py", "twenty_bundle_ablation")

DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024", "olympiadbench"]
SEEDS = [11, 23]
BUDGETS = [6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [1]

FULL_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_"
    "incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_"
    "hard_max_family_expansions_cap_k6_v1_fixed_k6_control"
)
FULL_WITH_REPAIR = f"{FULL_RUNTIME}__deterministic_output_layer_repair_v1"

ABLATION_VARIANTS: list[dict[str, Any]] = [
    {"variant": "full_integrated", "runtime_method": FULL_RUNTIME, "enable_output_repair": True},
    {"variant": "no_answer_support", "runtime_method": "strict_gate1_cap_k6_ablation_no_answer_support_v1", "enable_output_repair": True},
    {"variant": "no_anti_collapse", "runtime_method": "strict_gate1_cap_k6_ablation_no_anti_collapse_v1", "enable_output_repair": True},
    {
        "variant": "no_repeat_expansion_control",
        "runtime_method": "strict_gate1_cap_k6_ablation_no_repeat_expansion_control_v1",
        "enable_output_repair": True,
    },
    {"variant": "no_output_repair", "runtime_method": FULL_RUNTIME, "enable_output_repair": False},
    {
        "variant": "allocation_only_core",
        "runtime_method": "strict_gate1_cap_k6_ablation_allocation_only_core_v1",
        "enable_output_repair": False,
    },
]


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _stable_seed(*parts: Any) -> int:
    return TW._stable_seed(*parts)


def _classify(raw: dict[str, Any], gold_raw: str, dataset: str, enable_output_repair: bool) -> dict[str, Any]:
    repaired = choose_repair_answer(
        final_nodes=list(raw["final_nodes"]),
        selected_group_hint=(raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=bool(enable_output_repair),
    )
    surfaced = repaired.get("surfaced_final_answer_raw")
    surfaced_can = TW.canonicalize_answer(surfaced, dataset=dataset)
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)
    correct = bool(surfaced_can == gold_can and surfaced_can is not None)
    gold_in_tree = bool(TW._node_ids_with_answer(raw["final_nodes"], gold_can))
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
        "failure_type": failure,
        "correct": bool(correct),
        "gold_in_tree": bool(gold_in_tree),
        "answer_raw": surfaced,
    }


def _run_observed(runtime_method: str, row: dict[str, Any], stream_tag: str) -> dict[str, Any]:
    from experiments.branching import SimulatedBranchGenerator

    budget = int(row["budget"])
    seed = int(row["seed"])
    dataset = str(row["dataset"])
    example_id = str(row["example_id"])
    question = str(row["problem_text"])
    gold = str(row["ground_truth"])

    run_seed = _stable_seed(stream_tag, runtime_method, dataset, example_id, seed, budget)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))

    def factory() -> Any:
        return observed

    strategies = build_frontier_strategies(
        factory,
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    result = strategies[runtime_method].run(question, gold)

    for i, ev in enumerate(observed.decision_events):
        ev.remaining_budget_before = max(0, budget - i)

    parent_map: dict[str, str | None] = {}
    last_actor: str | None = None
    for e in observed.events:
        if e["event"] in {"expand", "verify"}:
            last_actor = str(e["branch_id"])
        elif e["event"] == "init_branch":
            bid = str(e["branch_id"])
            if bid not in parent_map:
                if bid.startswith("div_child") and last_actor is not None:
                    parent_map[bid] = last_actor
                else:
                    parent_map[bid] = None

    final_nodes: list[dict[str, Any]] = []
    for bid, b in sorted(observed.registry.items(), key=lambda kv: kv[0]):
        snap = observed._snapshot(b)
        snap["parent_branch_id"] = parent_map.get(bid)
        fam = bid
        cur = bid
        seen: set[str] = set()
        while parent_map.get(cur) is not None and cur not in seen:
            seen.add(cur)
            cur = str(parent_map[cur])
            fam = cur
        snap["branch_family_id"] = fam
        final_nodes.append(snap)

    return {
        "method": runtime_method,
        "run_seed": run_seed,
        "budget": budget,
        "prediction": result.prediction,
        "is_correct": bool(result.is_correct),
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "metadata": result.metadata,
        "final_nodes": final_nodes,
        "events": observed.events,
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n_cases": len(rows),
        "accuracy": _mean([1.0 if r["correct"] else 0.0 for r in rows]),
        "absent_from_tree": sum(1 for r in rows if r["failure_type"] == "absent_from_tree"),
        "present_not_selected": sum(1 for r in rows if r["failure_type"] == "present_not_selected"),
        "output_layer_mismatch": sum(1 for r in rows if r["failure_type"] == "output_layer_mismatch"),
        "repeated_same_family_present": sum(1 for r in rows if bool(r["repeated_same_family_present"])),
        "gold_in_tree": sum(1 for r in rows if bool(r["gold_in_tree"])),
        "avg_actions": _mean([float(r["actions"]) for r in rows]),
        "avg_expansions": _mean([float(r["expansions"]) for r in rows]),
        "avg_verifications": _mean([float(r["verifications"]) for r in rows]),
        "avg_max_family_expansion_share": _mean([float(r["max_family_expansion_share"]) for r in rows]),
        "avg_longest_same_family_run": _mean([float(r["longest_same_family_run"]) for r in rows]),
        "anti_collapse_trigger_count": sum(int(r["anti_collapse_triggered"]) for r in rows),
        "repeat_penalty_trigger_count": sum(int(r["repeat_penalty_triggered"]) for r in rows),
        "low_marginal_gain_trigger_count": sum(int(r["low_marginal_gain_triggered"]) for r in rows),
        "low_marginal_gain_block_count": sum(int(r["low_marginal_gain_blocked"]) for r in rows),
    }


def _select_best_reduced(aggregate_rows: list[dict[str, Any]]) -> str:
    candidates = [r for r in aggregate_rows if r["variant"] not in {"full_integrated", "no_output_repair"}]
    ranked = sorted(
        candidates,
        key=lambda r: (
            -float(r["accuracy"]),
            int(r["absent_from_tree"]),
            int(r["present_not_selected"]),
            float(r["avg_actions"]),
            str(r["variant"]),
        ),
    )
    return str(ranked[0]["variant"]) if ranked else "allocation_only_core"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_tex(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    lines = [
        "\\begin{tabular}{" + "l" * len(columns) + "}",
        "\\hline",
        " & ".join(columns) + " \\\\",
        "\\hline",
    ]
    for row in rows:
        vals = []
        for c in columns:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.4f}")
            else:
                vals.append(str(v))
        lines.append(" & ".join(vals) + " \\\\")
    lines.extend(["\\hline", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_ablation_figure(rows: list[dict[str, Any]], png_path: Path, pdf_path: Path) -> None:
    variants = [str(r["variant"]) for r in rows]
    acc = [float(r["accuracy"]) for r in rows]
    absent = [int(r["absent_from_tree"]) for r in rows]
    present = [int(r["present_not_selected"]) for r in rows]

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))
    axes[0].bar(variants, acc, color="#4e79a7")
    axes[0].set_title("Component ablation accuracy")
    axes[0].set_ylabel("Accuracy")
    axes[0].set_ylim(0.0, max(acc) + 0.08)
    axes[0].tick_params(axis="x", rotation=26)
    for t in axes[0].get_xticklabels():
        t.set_ha("right")
    axes[0].grid(True, axis="y", alpha=0.25)

    x = list(range(len(variants)))
    axes[1].bar(x, absent, label="absent_from_tree", color="#e15759")
    axes[1].bar(x, present, bottom=absent, label="present_not_selected", color="#76b7b2")
    axes[1].set_title("Failure decomposition by variant")
    axes[1].set_ylabel("Case count")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(variants, rotation=26, ha="right")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(frameon=False)

    fig.tight_layout()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=250, bbox_inches="tight")
    fig.savefig(pdf_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/integrated_controller_component_ablation_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case_rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in SEEDS:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
                for ex in examples:
                    base_case = {
                        "dataset": dataset,
                        "seed": int(seed),
                        "budget": int(budget),
                        "example_id": str(ex.example_id),
                        "ground_truth": str(ex.answer),
                        "problem_text": str(ex.question),
                    }
                    for cfg in ABLATION_VARIANTS:
                        raw = _run_observed(
                            runtime_method=str(cfg["runtime_method"]),
                            row=base_case,
                            stream_tag="integrated_component_ablation",
                        )
                        cls = _classify(
                            raw=raw,
                            gold_raw=str(ex.answer),
                            dataset=dataset,
                            enable_output_repair=bool(cfg["enable_output_repair"]),
                        )
                        md = raw.get("metadata") or {}
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
                                "gold_in_tree": bool(cls["gold_in_tree"]),
                                "actions": int(raw["actions"]),
                                "expansions": int(raw["expansions"]),
                                "verifications": int(raw["verifications"]),
                                "max_family_expansion_share": float(md.get("max_family_expansion_share", 0.0)),
                                "longest_same_family_run": int(md.get("max_consecutive_same_family_expands", 0)),
                                "repeated_same_family_present": bool(
                                    float(md.get("repeated_same_family_expansion_rate", 0.0)) > 0.0
                                ),
                                "anti_collapse_triggered": bool(
                                    (md.get("anti_collapse_repeat_penalty_trigger_count", 0) or 0) > 0
                                ),
                                "repeat_penalty_triggered": bool(
                                    (md.get("anti_collapse_repeat_penalty_trigger_count", 0) or 0) > 0
                                ),
                                "low_marginal_gain_triggered": bool(
                                    (md.get("low_marginal_gain_family_trigger_count", 0) or 0) > 0
                                ),
                                "low_marginal_gain_blocked": bool(
                                    (md.get("low_marginal_gain_family_block_count", 0) or 0) > 0
                                ),
                            }
                        )

    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_case_rows:
        by_variant[str(row["variant"])].append(row)

    aggregate_rows: list[dict[str, Any]] = []
    for variant, rows in sorted(by_variant.items()):
        agg = _aggregate(rows)
        aggregate_rows.append({"variant": variant, **agg})

    best_reduced = _select_best_reduced(aggregate_rows)
    best_row = next((r for r in aggregate_rows if r["variant"] == best_reduced), None)
    if best_row is not None:
        aggregate_rows.append(
            {
                "variant": "best_reduced_variant",
                **{k: v for k, v in best_row.items() if k != "variant"},
            }
        )

    per_dataset_rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for variant in sorted(by_variant.keys()):
            sub = [r for r in by_variant[variant] if str(r["dataset"]) == dataset]
            per_dataset_rows.append({"dataset": dataset, "variant": variant, **_aggregate(sub)})

    per_seed_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        for variant in sorted(by_variant.keys()):
            sub = [r for r in by_variant[variant] if int(r["seed"]) == int(seed)]
            per_seed_rows.append({"seed": int(seed), "variant": variant, **_aggregate(sub)})

    failure_rows: list[dict[str, Any]] = []
    for variant in sorted(by_variant.keys()):
        sub = by_variant[variant]
        counts = Counter(str(r["failure_type"]) for r in sub)
        n = max(1, len(sub))
        failure_rows.append(
            {
                "variant": variant,
                "n_cases": len(sub),
                "absent_from_tree_n": int(counts.get("absent_from_tree", 0)),
                "present_not_selected_n": int(counts.get("present_not_selected", 0)),
                "output_layer_mismatch_n": int(counts.get("output_layer_mismatch", 0)),
                "absent_from_tree_rate": float(counts.get("absent_from_tree", 0)) / n,
                "present_not_selected_rate": float(counts.get("present_not_selected", 0)) / n,
                "output_layer_mismatch_rate": float(counts.get("output_layer_mismatch", 0)) / n,
            }
        )

    diagnostics_rows: list[dict[str, Any]] = []
    for variant in sorted(by_variant.keys()):
        sub = by_variant[variant]
        diagnostics_rows.append(
            {
                "variant": variant,
                "avg_max_family_expansion_share": _mean([float(r["max_family_expansion_share"]) for r in sub]),
                "avg_longest_same_family_run": _mean([float(r["longest_same_family_run"]) for r in sub]),
                "anti_collapse_trigger_rate": _mean([1.0 if bool(r["anti_collapse_triggered"]) else 0.0 for r in sub]),
                "repeat_penalty_trigger_rate": _mean([1.0 if bool(r["repeat_penalty_triggered"]) else 0.0 for r in sub]),
                "low_marginal_gain_trigger_rate": _mean(
                    [1.0 if bool(r["low_marginal_gain_triggered"]) else 0.0 for r in sub]
                ),
            }
        )

    _write_csv(out_dir / "per_case_results.csv", per_case_rows)
    _write_csv(out_dir / "aggregate_summary.csv", aggregate_rows)
    _write_csv(out_dir / "per_dataset_metrics.csv", per_dataset_rows)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed_rows)
    _write_csv(out_dir / "failure_decomposition.csv", failure_rows)
    _write_csv(out_dir / "anti_collapse_diagnostics.csv", diagnostics_rows)

    aggregate_json = {
        "artifact_family": "integrated_controller_component_ablation",
        "timestamp_utc": now.isoformat(),
        "surface": {
            "datasets": DATASETS,
            "seeds": SEEDS,
            "budgets": BUDGETS,
            "subset_size_per_dataset_seed": SUBSET_SIZE,
            "canonical_reference_doc": "docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md",
        },
        "variants": ABLATION_VARIANTS,
        "best_reduced_variant": best_reduced,
        "total_case_evaluations": len(per_case_rows),
    }
    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate_json, indent=2), encoding="utf-8")

    manifest = {
        "name": "integrated_controller_component_ablation",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "inputs": [
            "experiments/frontier_matrix_core.py",
            "experiments/controllers.py",
            "experiments/output_layer_repair.py",
            "docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md",
        ],
        "outputs": [
            str((out_dir / "per_case_results.csv").relative_to(REPO_ROOT)),
            str((out_dir / "aggregate_summary.csv").relative_to(REPO_ROOT)),
            str((out_dir / "aggregate_summary.json").relative_to(REPO_ROOT)),
            str((out_dir / "per_dataset_metrics.csv").relative_to(REPO_ROOT)),
            str((out_dir / "per_seed_summary.csv").relative_to(REPO_ROOT)),
            str((out_dir / "failure_decomposition.csv").relative_to(REPO_ROOT)),
            str((out_dir / "anti_collapse_diagnostics.csv").relative_to(REPO_ROOT)),
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "status.json").write_text(json.dumps({"status": "ok", "n_rows": len(per_case_rows)}, indent=2), encoding="utf-8")

    # Add one paper-facing table/figure if the ablation differentiates variants meaningfully.
    acc_values = [float(r["accuracy"]) for r in aggregate_rows if r["variant"] != "best_reduced_variant"]
    spread = max(acc_values) - min(acc_values) if acc_values else 0.0
    if spread >= 0.005:
        table_rows = [
            r
            for r in aggregate_rows
            if r["variant"] in {
                "full_integrated",
                "no_answer_support",
                "no_anti_collapse",
                "no_repeat_expansion_control",
                "no_output_repair",
                "allocation_only_core",
                "best_reduced_variant",
            }
        ]
        _write_csv(REPO_ROOT / "outputs/paper_tables/table7_component_ablation.csv", table_rows)
        _write_tex(REPO_ROOT / "outputs/paper_tables/table7_component_ablation.tex", table_rows)
        _plot_ablation_figure(
            [r for r in table_rows if r["variant"] != "best_reduced_variant"],
            REPO_ROOT / "outputs/paper_figures/figure8_component_ablation.png",
            REPO_ROOT / "outputs/paper_figures/figure8_component_ablation.pdf",
        )

    report_path = REPO_ROOT / f"docs/INTEGRATED_CONTROLLER_COMPONENT_ABLATION_{ts}.md"
    lines = [
        f"# Integrated controller component ablation ({ts})",
        "",
        "## Protocol",
        "- Canonical surface: strict-phased default-decision broader matched surface.",
        f"- datasets: {DATASETS}",
        f"- seeds: {SEEDS}",
        f"- budgets: {BUDGETS}",
        f"- subset size per (dataset, seed): {SUBSET_SIZE}",
        "",
        "## Variants",
    ]
    for v in ABLATION_VARIANTS:
        lines.append(
            f"- `{v['variant']}`: runtime=`{v['runtime_method']}`, output_repair={bool(v['enable_output_repair'])}"
        )
    lines.extend(
        [
            "- `best_reduced_variant`: selected post-hoc from reduced variants by accuracy, then absent/present failure tie-breaks.",
            "",
            "## Aggregate summary",
            "",
            "| variant | accuracy | absent_from_tree | present_not_selected | output_layer_mismatch | avg_actions | avg_max_family_expansion_share | avg_longest_same_family_run |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for r in aggregate_rows:
        lines.append(
            f"| {r['variant']} | {float(r['accuracy']):.4f} | {int(r['absent_from_tree'])} | {int(r['present_not_selected'])} | {int(r['output_layer_mismatch'])} | {float(r['avg_actions']):.3f} | {float(r['avg_max_family_expansion_share']):.3f} | {float(r['avg_longest_same_family_run']):.3f} |"
        )

    lines.extend(
        [
            "",
            "## Main findings",
            f"- Full integrated accuracy: `{next(r['accuracy'] for r in aggregate_rows if r['variant'] == 'full_integrated'):.4f}`.",
            f"- Best reduced variant selected: `{best_reduced}`.",
            "- Interpret conservatively: this ablation isolates implemented toggles in current code paths; it does not claim causality beyond these operational definitions.",
            "",
            "## Artifacts",
            f"- `{out_dir.relative_to(REPO_ROOT)}/manifest.json`",
            f"- `{out_dir.relative_to(REPO_ROOT)}/aggregate_summary.csv`",
            f"- `{out_dir.relative_to(REPO_ROOT)}/aggregate_summary.json`",
            f"- `{out_dir.relative_to(REPO_ROOT)}/per_dataset_metrics.csv`",
            f"- `{out_dir.relative_to(REPO_ROOT)}/per_seed_summary.csv`",
            f"- `{out_dir.relative_to(REPO_ROOT)}/failure_decomposition.csv`",
            f"- `{out_dir.relative_to(REPO_ROOT)}/anti_collapse_diagnostics.csv`",
            f"- `{out_dir.relative_to(REPO_ROOT)}/per_case_results.csv`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print(f"report={report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

