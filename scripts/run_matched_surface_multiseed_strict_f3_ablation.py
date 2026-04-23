#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
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


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_for_ablation_multiseed", path)
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


def sample_std(xs: list[float]) -> float:
    if len(xs) <= 1:
        return 0.0
    mu = mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def ci95(xs: list[float]) -> tuple[float, float]:
    if not xs:
        return (0.0, 0.0)
    mu = mean(xs)
    sd = sample_std(xs)
    half = 1.96 * sd / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return (mu - half, mu + half)


def bootstrap_ci(diffs: list[float], n_boot: int, seed: int) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    vals = []
    for _ in range(n_boot):
        vals.append(mean([diffs[rng.randrange(n)] for _ in range(n)]))
    vals.sort()
    return (vals[int(0.025 * n_boot)], vals[min(int(0.975 * n_boot), n_boot - 1)])


def permutation_pvalue(diffs: list[float], n_perm: int, seed: int) -> float:
    if not diffs:
        return 1.0
    rng = random.Random(seed)
    obs = abs(mean(diffs))
    geq = 0
    for _ in range(n_perm):
        signs = [1.0 if rng.random() < 0.5 else -1.0 for _ in diffs]
        stat = abs(mean([d * s for d, s in zip(diffs, signs)]))
        if stat >= obs - 1e-12:
            geq += 1
    return (geq + 1.0) / (n_perm + 1.0)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def render_latex(headers: list[str], rows: list[list[str]]) -> str:
    cols = "l" + "r" * (len(headers) - 1)
    out = [f"\\begin{{tabular}}{{{cols}}}", "\\hline", " & ".join(headers) + " \\\\", "\\hline"]
    for row in rows:
        out.append(" & ".join(row) + " \\\\")
    out.extend(["\\hline", "\\end{tabular}"])
    return "\n".join(out) + "\n"


def run_observed(runtime_method: str, dataset: str, seed: int, budget: int, example: Any) -> dict[str, Any]:
    run_seed = stable_seed("matched_surface_multiseed_strict_f3_ablation", runtime_method, dataset, example.example_id, seed, budget)
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
        "gold_in_tree": int(gold_in_tree),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run matched-surface multi-seed strict_f3 ablation rerun.")
    p.add_argument("--timestamp", default=utc_timestamp())
    p.add_argument("--seeds", default=",".join(str(s) for s in DEFAULT_SEEDS))
    p.add_argument("--n-perm", type=int, default=4000)
    p.add_argument("--n-boot", type=int, default=4000)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]

    ranking_path = REPO_ROOT / f"outputs/{CANONICAL_SURFACE_ID}/overall_ranking.csv"
    if not ranking_path.exists():
        raise FileNotFoundError(f"Missing canonical manuscript-facing ranking surface: {ranking_path}")

    out_dir = REPO_ROOT / f"outputs/matched_surface_multiseed_strict_f3_ablation_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in seeds:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
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
                                "enable_output_repair": int(bool(variant_cfg["enable_output_repair"])),
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
                                "oracle_gap": float(md.get("oracle_gap", float("nan"))),
                                "oracle_regret": float(md.get("oracle_regret", float("nan"))),
                                "repeated_same_family_present": int(
                                    float(md.get("repeated_same_family_expansion_rate", 0.0)) > 0.0
                                    or int(md.get("repeated_same_family_expansion_count", 0)) > 0
                                ),
                                "max_family_expansion_share": float(md.get("max_family_expansion_share", 0.0)),
                                "longest_same_family_run": int(md.get("max_consecutive_same_family_expands", 0)),
                            }
                        )

    write_csv(out_dir / "raw_case_results.csv", rows)

    per_seed_results: list[dict[str, Any]] = []
    for variant in [v["variant"] for v in VARIANTS]:
        for seed in seeds:
            sub = [r for r in rows if r["variant"] == variant and int(r["seed"]) == seed]
            if not sub:
                continue
            per_seed_results.append(
                {
                    "variant": variant,
                    "seed": seed,
                    "n_cases": len(sub),
                    "accuracy": mean([float(r["is_correct"]) for r in sub]),
                    "absent_from_tree_rate": mean([float(r["absent_from_tree"]) for r in sub]),
                    "present_not_selected_rate": mean([float(r["present_not_selected"]) for r in sub]),
                    "output_layer_mismatch_rate": mean([float(r["output_layer_mismatch"]) for r in sub]),
                    "oracle_gap_mean": mean([float(r["oracle_gap"]) for r in sub if not math.isnan(float(r["oracle_gap"]))]),
                    "oracle_regret_mean": mean([float(r["oracle_regret"]) for r in sub if not math.isnan(float(r["oracle_regret"]))]),
                    "repeated_same_family_rate": mean([float(r["repeated_same_family_present"]) for r in sub]),
                    "max_family_expansion_share_mean": mean([float(r["max_family_expansion_share"]) for r in sub]),
                }
            )

    write_csv(out_dir / "per_seed_results.csv", per_seed_results)

    per_variant_summary: list[dict[str, Any]] = []
    for variant in [v["variant"] for v in VARIANTS]:
        sub_seed = [r for r in per_seed_results if r["variant"] == variant]
        acc = [float(r["accuracy"]) for r in sub_seed]
        aft = [float(r["absent_from_tree_rate"]) for r in sub_seed]
        pns = [float(r["present_not_selected_rate"]) for r in sub_seed]
        rep = [float(r["repeated_same_family_rate"]) for r in sub_seed]
        og = [float(r["oracle_gap_mean"]) for r in sub_seed]
        og_valid = [x for x in og if not math.isnan(x)]
        orr = [float(r["oracle_regret_mean"]) for r in sub_seed]
        orr_valid = [x for x in orr if not math.isnan(x)]
        acc_ci = ci95(acc)
        per_variant_summary.append(
            {
                "variant": variant,
                "n_seeds": len(sub_seed),
                "n_cases": sum(int(r["n_cases"]) for r in sub_seed),
                "mean_accuracy": mean(acc),
                "std_accuracy": sample_std(acc),
                "ci95_accuracy_low": acc_ci[0],
                "ci95_accuracy_high": acc_ci[1],
                "mean_absent_from_tree_rate": mean(aft),
                "mean_present_not_selected_rate": mean(pns),
                "mean_output_layer_mismatch_rate": mean([float(r["output_layer_mismatch_rate"]) for r in sub_seed]),
                "mean_oracle_gap": mean(og_valid) if og_valid else float("nan"),
                "mean_oracle_regret": mean(orr_valid) if orr_valid else float("nan"),
                "mean_repeated_same_family_rate": mean(rep),
                "mean_max_family_expansion_share": mean([float(r["max_family_expansion_share_mean"]) for r in sub_seed]),
            }
        )

    write_csv(out_dir / "per_variant_summary.csv", per_variant_summary)

    full_lookup = {int(r["seed"]): r for r in per_seed_results if r["variant"] == "full_method"}
    pairwise_rows: list[dict[str, Any]] = []
    for variant in [v["variant"] for v in VARIANTS if v["variant"] != "full_method"]:
        variant_lookup = {int(r["seed"]): r for r in per_seed_results if r["variant"] == variant}
        shared = sorted(set(full_lookup).intersection(variant_lookup))
        d_acc = [float(variant_lookup[s]["accuracy"]) - float(full_lookup[s]["accuracy"]) for s in shared]
        d_aft = [float(variant_lookup[s]["absent_from_tree_rate"]) - float(full_lookup[s]["absent_from_tree_rate"]) for s in shared]
        d_pns = [float(variant_lookup[s]["present_not_selected_rate"]) - float(full_lookup[s]["present_not_selected_rate"]) for s in shared]

        acc_ci = bootstrap_ci(d_acc, n_boot=args.n_boot, seed=stable_seed("acc", variant))
        aft_ci = bootstrap_ci(d_aft, n_boot=args.n_boot, seed=stable_seed("aft", variant))
        pns_ci = bootstrap_ci(d_pns, n_boot=args.n_boot, seed=stable_seed("pns", variant))

        pairwise_rows.append(
            {
                "variant": variant,
                "n_shared_seeds": len(shared),
                "accuracy_delta_vs_full": mean(d_acc),
                "accuracy_delta_ci_low": acc_ci[0],
                "accuracy_delta_ci_high": acc_ci[1],
                "accuracy_pvalue_permutation": permutation_pvalue(d_acc, n_perm=args.n_perm, seed=stable_seed("p", variant)),
                "absent_from_tree_delta_vs_full": mean(d_aft),
                "absent_from_tree_delta_ci_low": aft_ci[0],
                "absent_from_tree_delta_ci_high": aft_ci[1],
                "present_not_selected_delta_vs_full": mean(d_pns),
                "present_not_selected_delta_ci_low": pns_ci[0],
                "present_not_selected_delta_ci_high": pns_ci[1],
            }
        )

    write_csv(out_dir / "pairwise_vs_full.csv", pairwise_rows)

    paper_ablation_rows = []
    for row in per_variant_summary:
        variant = str(row["variant"])
        pair = next((p for p in pairwise_rows if p["variant"] == variant), None)
        paper_ablation_rows.append(
            {
                "variant": variant,
                "mean_accuracy": f"{float(row['mean_accuracy']):.4f}",
                "std_accuracy": f"{float(row['std_accuracy']):.4f}",
                "ci95_accuracy": f"[{float(row['ci95_accuracy_low']):.4f}, {float(row['ci95_accuracy_high']):.4f}]",
                "delta_accuracy_vs_full": "0.0000" if pair is None else f"{float(pair['accuracy_delta_vs_full']):.4f}",
            }
        )
    write_csv(out_dir / "paper_ablation_table.csv", paper_ablation_rows)
    paper_ablation_tex = render_latex(
        ["Variant", "Mean Acc", "Std", "95% CI", "Δ vs Full"],
        [[r["variant"], r["mean_accuracy"], r["std_accuracy"], r["ci95_accuracy"], r["delta_accuracy_vs_full"]] for r in paper_ablation_rows],
    )
    (out_dir / "paper_ablation_table.tex").write_text(paper_ablation_tex, encoding="utf-8")

    failure_rows = [
        {
            "variant": str(r["variant"]),
            "absent_from_tree_rate": f"{float(r['mean_absent_from_tree_rate']):.4f}",
            "present_not_selected_rate": f"{float(r['mean_present_not_selected_rate']):.4f}",
            "output_layer_mismatch_rate": f"{float(r['mean_output_layer_mismatch_rate']):.4f}",
        }
        for r in per_variant_summary
    ]
    write_csv(out_dir / "paper_failure_decomposition_table.csv", failure_rows)
    failure_tex = render_latex(
        ["Variant", "Absent", "Present-not-selected", "Output mismatch"],
        [[r["variant"], r["absent_from_tree_rate"], r["present_not_selected_rate"], r["output_layer_mismatch_rate"]] for r in failure_rows],
    )
    (out_dir / "paper_failure_decomposition_table.tex").write_text(failure_tex, encoding="utf-8")

    oracle_rows = [
        {
            "variant": str(r["variant"]),
            "mean_oracle_gap": "NA" if math.isnan(float(r["mean_oracle_gap"])) else f"{float(r['mean_oracle_gap']):.4f}",
            "mean_oracle_regret": "NA" if math.isnan(float(r["mean_oracle_regret"])) else f"{float(r['mean_oracle_regret']):.4f}",
        }
        for r in per_variant_summary
    ]
    write_csv(out_dir / "paper_oracle_gap_table.csv", oracle_rows)
    (out_dir / "paper_oracle_gap_table.tex").write_text(
        render_latex(["Variant", "Mean oracle gap", "Mean oracle regret"], [[r["variant"], r["mean_oracle_gap"], r["mean_oracle_regret"]] for r in oracle_rows]),
        encoding="utf-8",
    )

    anti_rows = [
        {
            "variant": str(r["variant"]),
            "repeated_same_family_rate": f"{float(r['mean_repeated_same_family_rate']):.4f}",
            "max_family_expansion_share": f"{float(r['mean_max_family_expansion_share']):.4f}",
        }
        for r in per_variant_summary
    ]
    write_csv(out_dir / "paper_anti_collapse_table.csv", anti_rows)
    (out_dir / "paper_anti_collapse_table.tex").write_text(
        render_latex(["Variant", "Repeated-family rate", "Max family share"], [[r["variant"], r["repeated_same_family_rate"], r["max_family_expansion_share"]] for r in anti_rows]),
        encoding="utf-8",
    )

    pair_lookup = {r["variant"]: r for r in pairwise_rows}
    strongest_supported = min(pairwise_rows, key=lambda r: float(r["accuracy_delta_vs_full"]))["variant"] if pairwise_rows else "NA"

    notes = [
        "Matched-surface strict_f3 multi-seed component ablation rerun.",
        f"Canonical surface: outputs/{CANONICAL_SURFACE_ID}",
        f"Seeds: {seeds}",
        f"Datasets: {DATASETS}",
        f"Budgets: {BUDGETS}",
        f"Most accuracy-critical ablation by mean delta vs full: {strongest_supported}",
        "Interpretation rule: negative delta_accuracy_vs_full means removal hurt and therefore supports the removed component.",
    ]
    (out_dir / "notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")

    config_snapshot = {
        "canonical_surface_id": CANONICAL_SURFACE_ID,
        "datasets": DATASETS,
        "budgets": BUDGETS,
        "subset_size": SUBSET_SIZE,
        "adaptive_grid": ADAPTIVE_GRID,
        "seeds": seeds,
        "variants": VARIANTS,
        "n_perm": args.n_perm,
        "n_boot": args.n_boot,
    }
    (out_dir / "config_snapshot.json").write_text(json.dumps(config_snapshot, indent=2) + "\n", encoding="utf-8")

    aggregate_summary = {
        "artifact_family": "matched_surface_multiseed_strict_f3_ablation",
        "timestamp": args.timestamp,
        "strict_rerun_on_manuscript_surface": True,
        "surface": {
            "canonical_surface_id": CANONICAL_SURFACE_ID,
            "our_method_lock": "strict_f3",
            "datasets": DATASETS,
            "budgets": BUDGETS,
            "subset_size": SUBSET_SIZE,
            "seeds": seeds,
        },
        "variants": [v["variant"] for v in VARIANTS],
        "per_variant_summary": per_variant_summary,
        "pairwise_vs_full": pairwise_rows,
        "main_findings": {
            "most_accuracy_critical_component": strongest_supported,
            "most_upstream_sensitive_component": min(pairwise_rows, key=lambda r: float(r["absent_from_tree_delta_vs_full"]))["variant"] if pairwise_rows else "NA",
            "most_downstream_sensitive_component": max(pairwise_rows, key=lambda r: abs(float(r["present_not_selected_delta_vs_full"]))) ["variant"] if pairwise_rows else "NA",
        },
    }
    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate_summary, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "artifact_family": "matched_surface_multiseed_strict_f3_ablation",
        "command": f"python scripts/run_matched_surface_multiseed_strict_f3_ablation.py --timestamp {args.timestamp} --seeds {','.join(str(s) for s in seeds)} --n-perm {args.n_perm} --n-boot {args.n_boot}",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "files": [
            "manifest.json",
            "config_snapshot.json",
            "aggregate_summary.json",
            "per_seed_results.csv",
            "per_variant_summary.csv",
            "pairwise_vs_full.csv",
            "paper_ablation_table.csv",
            "paper_ablation_table.tex",
            "paper_failure_decomposition_table.csv",
            "paper_failure_decomposition_table.tex",
            "paper_oracle_gap_table.csv",
            "paper_oracle_gap_table.tex",
            "paper_anti_collapse_table.csv",
            "paper_anti_collapse_table.tex",
            "notes.txt",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    full = next(r for r in per_variant_summary if r["variant"] == "full_method")
    lines = [
        f"# MATCHED_SURFACE_MULTI_SEED_STRICT_F3_ABLATION_{args.timestamp}",
        "",
        "## Purpose",
        "Run a materially stronger multi-seed component ablation rerun for strict_f3 on the canonical manuscript-facing matched surface.",
        "",
        "## Exact matched surface used",
        f"- Canonical matched surface: `outputs/{CANONICAL_SURFACE_ID}`",
        "- This run is a strict rerun of the manuscript-facing ablation surface: `True`.",
        f"- Datasets: {DATASETS}",
        f"- Budgets: {BUDGETS}",
        f"- Seeds: {seeds}",
        f"- Subset size per (dataset, seed): {SUBSET_SIZE}",
        "",
        "## Exact ablation variants used",
    ]
    lines.extend([f"- `{v['variant']}` (`{v['runtime_method']}`, output_repair={v['enable_output_repair']})" for v in VARIANTS])
    lines.extend(
        [
            "",
            "## Main findings (plain language)",
            f"- Full strict_f3 mean accuracy = {float(full['mean_accuracy']):.4f} across {len(seeds)} seeds.",
        ]
    )
    for p in pairwise_rows:
        lines.append(
            f"- Removing `{p['variant']}`: Δaccuracy={float(p['accuracy_delta_vs_full']):+.4f}, Δabsent_from_tree={float(p['absent_from_tree_delta_vs_full']):+.4f}, Δpresent_not_selected={float(p['present_not_selected_delta_vs_full']):+.4f}."
        )
    lines.extend(
        [
            "",
            f"Most clearly supported component (largest accuracy drop when removed): `{strongest_supported}`.",
            "",
            "## Mechanism-story recommendation",
            "- If only one component shows robust negative deltas when removed, narrow the manuscript mechanism claim to that component and treat others as mixed/secondary.",
            "- If multiple removals improve or remain near-zero, avoid broad all-component benefit claims on this matched surface.",
            "- Recommended paper-writing action for this run: narrow to a smaller claim unless all major removals are consistently harmful.",
        ]
    )
    doc_path = REPO_ROOT / f"docs/MATCHED_SURFACE_MULTI_SEED_STRICT_F3_ABLATION_{args.timestamp}.md"
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(out_dir.relative_to(REPO_ROOT))
    print(doc_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
