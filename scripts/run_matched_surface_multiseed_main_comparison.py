#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer


def _load_twenty_module() -> Any:
    import importlib.util

    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_multiseed", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()

CANONICAL_SURFACE_ID = "canonical_full_method_ranking_20260421T212948Z"
DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
BUDGETS = [4, 6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [0, 1, 2]
DEFAULT_SEEDS = [11, 23, 37, 41, 53, 67, 79, 97, 101, 131]

METHOD_RUNTIME_MAP = {
    "strict_f3": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    "strict_gate1_cap_k6": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control",
    "strict_f2": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1",
    "l1_max": "external_l1_max",
    "tale": "external_tale_prompt_budgeting",
    "s1": "external_s1_budget_forcing",
    "l1_exact": "external_l1_exact",
    "zhai_cpo_mode_a": "external_zhai_cpo_mode_a",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def stable_seed(*parts: Any) -> int:
    s = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(s.encode()).hexdigest()[:16], 16)


def mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def sample_std(xs: list[float]) -> float:
    if len(xs) <= 1:
        return 0.0
    mu = mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def ci95_from_values(xs: list[float]) -> tuple[float, float]:
    if not xs:
        return (0.0, 0.0)
    mu = mean(xs)
    sd = sample_std(xs)
    half = 1.96 * sd / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return (mu - half, mu + half)


def node_ids_with_answer(nodes: list[dict[str, Any]], normalized_answer: str | None) -> list[str]:
    if normalized_answer is None:
        return []
    out = []
    for n in nodes:
        a = n.get("predicted_answer_normalized")
        if a == normalized_answer:
            out.append(str(n.get("branch_id")))
    return out


def run_observed(method_short: str, runtime_name: str, dataset: str, seed: int, budget: int, example: Any) -> dict[str, Any]:
    run_seed = stable_seed("matched_surface_multiseed_main", method_short, dataset, example.example_id, seed, budget)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))

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
        include_external_zhai_cpo_baseline=True,
    )
    if runtime_name not in specs:
        raise KeyError(runtime_name)

    result = specs[runtime_name].run(example.question, example.answer)
    final_nodes: list[dict[str, Any]] = []
    for _, branch in sorted(observed.registry.items(), key=lambda kv: kv[0]):
        final_nodes.append(observed._snapshot(branch))

    rep = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=(result.metadata or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    ans = rep.get("surfaced_final_answer_raw")
    ans_can = canonicalize_answer(ans, dataset=dataset)
    gold_can = canonicalize_answer(str(example.answer), dataset=dataset)

    gold_in_tree = bool(node_ids_with_answer(final_nodes, gold_can))
    output_mismatch = bool(
        gold_in_tree
        and (rep.get("chosen_final_node_answer_canonical") == gold_can)
        and (ans_can != gold_can)
    )
    extraction_mismatch = bool(
        (rep.get("chosen_final_node_answer_canonical") != rep.get("extracted_final_answer_canonical"))
        or (rep.get("extracted_final_answer_canonical") != rep.get("surfaced_final_answer_canonical"))
    )

    is_correct = bool(ans_can == gold_can and ans_can is not None)
    if not gold_in_tree:
        failure_type = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        failure_type = "output_layer_mismatch"
    elif is_correct:
        failure_type = "correct"
    else:
        failure_type = "present_not_selected"

    md = result.metadata or {}
    repeated = bool(
        float(md.get("repeated_same_family_expansion_rate", 0.0)) > 0.0
        or int(md.get("repeated_same_family_expansion_count", 0)) > 0
    )

    return {
        "dataset": dataset,
        "seed": seed,
        "budget": budget,
        "example_id": str(example.example_id),
        "method": method_short,
        "runtime_method": runtime_name,
        "is_correct": int(is_correct),
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "failure_type": failure_type,
        "absent_from_tree": int(failure_type == "absent_from_tree"),
        "present_not_selected": int(failure_type == "present_not_selected"),
        "output_layer_mismatch": int(failure_type == "output_layer_mismatch"),
        "gold_in_tree": int(gold_in_tree),
        "repeated_same_family_present": int(repeated),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def permutation_pvalue(diffs: list[float], n_perm: int = 5000, seed: int = 0) -> float:
    if not diffs:
        return 1.0
    obs = abs(mean(diffs))
    rng = random.Random(seed)
    geq = 0
    for _ in range(n_perm):
        signs = [1.0 if rng.random() < 0.5 else -1.0 for _ in diffs]
        stat = abs(mean([d * s for d, s in zip(diffs, signs)]))
        if stat >= obs - 1e-12:
            geq += 1
    return (geq + 1.0) / (n_perm + 1.0)


def bootstrap_ci(diffs: list[float], n_boot: int = 5000, seed: int = 0) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(mean(sample))
    means.sort()
    lo_idx = int(0.025 * n_boot)
    hi_idx = int(0.975 * n_boot)
    return (means[lo_idx], means[min(hi_idx, n_boot - 1)])


def render_simple_latex(headers: list[str], rows: list[list[str]]) -> str:
    cols = "l" + "r" * (len(headers) - 1)
    out = [f"\\begin{{tabular}}{{{cols}}}", "\\hline", " & ".join(headers) + " \\\\", "\\hline"]
    for row in rows:
        out.append(" & ".join(row) + " \\\\")
    out.extend(["\\hline", "\\end{tabular}"])
    return "\n".join(out) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run manuscript matched-surface multi-seed main comparison.")
    p.add_argument("--timestamp", default=utc_timestamp())
    p.add_argument("--seeds", default=",".join(str(s) for s in DEFAULT_SEEDS))
    p.add_argument("--n-perm", type=int, default=5000)
    p.add_argument("--n-boot", type=int, default=5000)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    methods_requested = ["strict_f3", "strict_gate1_cap_k6", "strict_f2", "l1_max", "tale", "s1", "l1_exact", "zhai_cpo_mode_a"]

    out_dir = REPO_ROOT / f"outputs/matched_surface_multiseed_main_comparison_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    probe_rng = random.Random(0)
    probe = build_frontier_strategies(
        lambda: SimulatedBranchGenerator(rng=probe_rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        4,
        ADAPTIVE_GRID,
        probe_rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
        include_external_zhai_cpo_baseline=True,
    )

    methods_runnable = []
    blocked = []
    for m in methods_requested:
        rt = METHOD_RUNTIME_MAP[m]
        if rt in probe:
            methods_runnable.append(m)
        else:
            blocked.append({"method": m, "runtime_method": rt, "reason": "runtime_missing_on_matched_surface"})

    rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in seeds:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            example_lookup = {str(ex.example_id): asdict(ex) for ex in examples}
            for budget in BUDGETS:
                for ex in examples:
                    for method in methods_runnable:
                        record = run_observed(method, METHOD_RUNTIME_MAP[method], dataset, seed, budget, ex)
                        ex_meta = example_lookup[record["example_id"]]
                        record["question"] = ex_meta["question"]
                        record["ground_truth"] = ex_meta["answer"]
                        rows.append(record)

    per_seed_records = []
    for method in methods_runnable:
        for seed in seeds:
            sub = [r for r in rows if r["method"] == method and int(r["seed"]) == seed]
            if not sub:
                continue
            per_seed_records.append(
                {
                    "method": method,
                    "seed": seed,
                    "n": len(sub),
                    "accuracy": mean([float(r["is_correct"]) for r in sub]),
                    "absent_from_tree_rate": mean([float(r["absent_from_tree"]) for r in sub]),
                    "present_not_selected_rate": mean([float(r["present_not_selected"]) for r in sub]),
                    "mean_actions": mean([float(r["actions"]) for r in sub]),
                    "mean_expansions": mean([float(r["expansions"]) for r in sub]),
                    "mean_verifications": mean([float(r["verifications"]) for r in sub]),
                }
            )

    summary_rows = []
    for method in methods_runnable:
        method_seed = [r for r in per_seed_records if r["method"] == method]
        acc = [float(r["accuracy"]) for r in method_seed]
        aft = [float(r["absent_from_tree_rate"]) for r in method_seed]
        pns = [float(r["present_not_selected_rate"]) for r in method_seed]
        acc_ci = ci95_from_values(acc)
        aft_ci = ci95_from_values(aft)
        pns_ci = ci95_from_values(pns)

        method_rows = [r for r in rows if r["method"] == method]
        summary_rows.append(
            {
                "method": method,
                "n_rows": len(method_rows),
                "n_seeds": len(method_seed),
                "mean_accuracy": mean(acc),
                "std_accuracy": sample_std(acc),
                "ci95_low_accuracy": acc_ci[0],
                "ci95_high_accuracy": acc_ci[1],
                "mean_absent_from_tree_rate": mean(aft),
                "std_absent_from_tree_rate": sample_std(aft),
                "ci95_low_absent_from_tree_rate": aft_ci[0],
                "ci95_high_absent_from_tree_rate": aft_ci[1],
                "mean_present_not_selected_rate": mean(pns),
                "std_present_not_selected_rate": sample_std(pns),
                "ci95_low_present_not_selected_rate": pns_ci[0],
                "ci95_high_present_not_selected_rate": pns_ci[1],
                "mean_actions": mean([float(r["actions"]) for r in method_rows]),
                "mean_expansions": mean([float(r["expansions"]) for r in method_rows]),
                "mean_verifications": mean([float(r["verifications"]) for r in method_rows]),
            }
        )

    summary_rows.sort(key=lambda r: (-float(r["mean_accuracy"]), str(r["method"])))

    keys = [(r["dataset"], int(r["seed"]), int(r["budget"]), r["example_id"]) for r in rows]
    unique_keys = sorted(set(keys))
    by_key_method = {(r["dataset"], int(r["seed"]), int(r["budget"]), r["example_id"], r["method"]): r for r in rows}

    pair_specs = [("strict_f3", "strict_gate1_cap_k6"), ("strict_f3", "l1_max")]
    pairwise_rows = []
    for a, b in pair_specs:
        if a not in methods_runnable or b not in methods_runnable:
            pairwise_rows.append(
                {
                    "method_a": a,
                    "method_b": b,
                    "status": "blocked",
                    "reason": "one_or_both_methods_not_runnable",
                }
            )
            continue
        diffs = []
        for seed in seeds:
            a_seed = [r for r in rows if r["method"] == a and int(r["seed"]) == seed]
            b_seed = [r for r in rows if r["method"] == b and int(r["seed"]) == seed]
            if not a_seed or not b_seed:
                continue
            a_acc = mean([float(r["is_correct"]) for r in a_seed])
            b_acc = mean([float(r["is_correct"]) for r in b_seed])
            diffs.append(a_acc - b_acc)
        diff_mean = mean(diffs)
        ci_low, ci_high = bootstrap_ci(diffs, n_boot=args.n_boot, seed=stable_seed(a, b, "boot"))
        pval = permutation_pvalue(diffs, n_perm=args.n_perm, seed=stable_seed(a, b, "perm"))
        pairwise_rows.append(
            {
                "method_a": a,
                "method_b": b,
                "status": "ok",
                "n_seed_pairs": len(diffs),
                "mean_accuracy_diff_a_minus_b": diff_mean,
                "ci95_low_diff": ci_low,
                "ci95_high_diff": ci_high,
                "permutation_pvalue_two_sided": pval,
            }
        )

    oracle_rows = []
    for method in methods_runnable:
        regrets = []
        for k in unique_keys:
            vals = [float(by_key_method[(k[0], k[1], k[2], k[3], m)]["is_correct"]) for m in methods_runnable]
            oracle = max(vals)
            cur = float(by_key_method[(k[0], k[1], k[2], k[3], method)]["is_correct"])
            regrets.append(oracle - cur)
        oracle_rows.append(
            {
                "method": method,
                "mean_oracle_gap_regret": mean(regrets),
                "std_oracle_gap_regret": sample_std(regrets),
                "ci95_low_oracle_gap_regret": ci95_from_values(regrets)[0],
                "ci95_high_oracle_gap_regret": ci95_from_values(regrets)[1],
            }
        )
    oracle_rows.sort(key=lambda r: (float(r["mean_oracle_gap_regret"]), str(r["method"])))

    write_csv(out_dir / "per_seed_results.csv", sorted(per_seed_records, key=lambda r: (r["method"], int(r["seed"]))))
    write_csv(out_dir / "per_method_summary.csv", summary_rows)
    write_csv(out_dir / "pairwise_significance.csv", pairwise_rows)
    write_csv(out_dir / "paper_ready_oracle_gap_table.csv", oracle_rows)

    main_table_rows = []
    failure_table_rows = []
    for r in summary_rows:
        main_table_rows.append(
            {
                "method": r["method"],
                "mean_accuracy": f"{r['mean_accuracy']:.4f}",
                "std_accuracy": f"{r['std_accuracy']:.4f}",
                "ci95_accuracy": f"[{r['ci95_low_accuracy']:.4f}, {r['ci95_high_accuracy']:.4f}]",
                "mean_actions": f"{r['mean_actions']:.3f}",
                "mean_expansions": f"{r['mean_expansions']:.3f}",
                "mean_verifications": f"{r['mean_verifications']:.3f}",
            }
        )
        failure_table_rows.append(
            {
                "method": r["method"],
                "mean_absent_from_tree_rate": f"{r['mean_absent_from_tree_rate']:.4f}",
                "std_absent_from_tree_rate": f"{r['std_absent_from_tree_rate']:.4f}",
                "ci95_absent_from_tree": f"[{r['ci95_low_absent_from_tree_rate']:.4f}, {r['ci95_high_absent_from_tree_rate']:.4f}]",
                "mean_present_not_selected_rate": f"{r['mean_present_not_selected_rate']:.4f}",
                "std_present_not_selected_rate": f"{r['std_present_not_selected_rate']:.4f}",
                "ci95_present_not_selected": f"[{r['ci95_low_present_not_selected_rate']:.4f}, {r['ci95_high_present_not_selected_rate']:.4f}]",
            }
        )

    write_csv(out_dir / "paper_ready_main_table.csv", main_table_rows)
    write_csv(out_dir / "paper_ready_failure_table.csv", failure_table_rows)

    main_tex_rows = [[r["method"], r["mean_accuracy"], r["std_accuracy"], r["ci95_accuracy"], r["mean_actions"]] for r in main_table_rows]
    (out_dir / "paper_ready_main_table.tex").write_text(
        render_simple_latex(["Method", "MeanAcc", "StdAcc", "CI95", "MeanActions"], main_tex_rows),
        encoding="utf-8",
    )

    failure_tex_rows = [
        [
            r["method"],
            r["mean_absent_from_tree_rate"],
            r["std_absent_from_tree_rate"],
            r["ci95_absent_from_tree"],
            r["mean_present_not_selected_rate"],
            r["std_present_not_selected_rate"],
            r["ci95_present_not_selected"],
        ]
        for r in failure_table_rows
    ]
    (out_dir / "paper_ready_failure_table.tex").write_text(
        render_simple_latex(
            [
                "Method",
                "AbsentMean",
                "AbsentStd",
                "AbsentCI95",
                "PresentNotSelMean",
                "PresentNotSelStd",
                "PresentNotSelCI95",
            ],
            failure_tex_rows,
        ),
        encoding="utf-8",
    )

    aggregate_summary = {
        "surface_id": CANONICAL_SURFACE_ID,
        "strict_rerun_of_manuscript_matched_surface": True,
        "datasets": DATASETS,
        "budgets": BUDGETS,
        "seeds": seeds,
        "methods_requested": methods_requested,
        "methods_runnable": methods_runnable,
        "blocked_methods": blocked,
        "winner_by_mean_accuracy": summary_rows[0]["method"] if summary_rows else None,
        "strict_f3_still_wins_on_mean": bool(summary_rows and summary_rows[0]["method"] == "strict_f3"),
        "pairwise_significance": pairwise_rows,
    }

    manifest = {
        "artifact_family": "matched_surface_multiseed_main_comparison",
        "timestamp": args.timestamp,
        "command": f"python scripts/run_matched_surface_multiseed_main_comparison.py --timestamp {args.timestamp} --seeds {','.join(str(s) for s in seeds)} --n-perm {args.n_perm} --n-boot {args.n_boot}",
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "files": sorted([p.name for p in out_dir.iterdir() if p.is_file()]),
    }

    config_snapshot = {
        "surface_id": CANONICAL_SURFACE_ID,
        "datasets": DATASETS,
        "budgets": BUDGETS,
        "subset_size": SUBSET_SIZE,
        "adaptive_grid": ADAPTIVE_GRID,
        "seeds": seeds,
        "methods_requested": methods_requested,
        "method_runtime_map": METHOD_RUNTIME_MAP,
        "n_perm": args.n_perm,
        "n_boot": args.n_boot,
    }

    (out_dir / "aggregate_summary.json").write_text(json.dumps(aggregate_summary, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "config_snapshot.json").write_text(json.dumps(config_snapshot, indent=2, sort_keys=True), encoding="utf-8")

    write_csv(
        out_dir / "raw_case_results.csv",
        rows,
    )

    notes = [
        f"Surface: {CANONICAL_SURFACE_ID}",
        "This is a strict rerun of the manuscript-facing matched contract (same datasets/budgets/protocol, larger seed set).",
        f"Requested methods: {', '.join(methods_requested)}",
        f"Runnable methods: {', '.join(methods_runnable)}",
        f"Blocked methods: {', '.join(b['method'] for b in blocked) if blocked else 'none'}",
        "Paired significance uses paired permutation test on per-seed mean-accuracy deltas (two-sided).",
    ]
    (out_dir / "notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")

    report_path = REPO_ROOT / "docs" / f"MATCHED_SURFACE_MULTI_SEED_MAIN_COMPARISON_{args.timestamp}.md"
    summary_by_method = {r["method"]: r for r in summary_rows}
    f3 = summary_by_method.get("strict_f3")
    gate = summary_by_method.get("strict_gate1_cap_k6")
    l1 = summary_by_method.get("l1_max")

    def _gap(a: dict[str, Any] | None, b: dict[str, Any] | None) -> str:
        if not a or not b:
            return "NA"
        return f"{(float(a['mean_accuracy']) - float(b['mean_accuracy'])):+.4f}"

    p_f3_gate = next((r for r in pairwise_rows if r.get("method_a") == "strict_f3" and r.get("method_b") == "strict_gate1_cap_k6"), None)
    p_f3_l1 = next((r for r in pairwise_rows if r.get("method_a") == "strict_f3" and r.get("method_b") == "l1_max"), None)

    interpretation = "mixed / fragile support"
    if f3 and summary_rows and summary_rows[0]["method"] == "strict_f3":
        if p_f3_gate and p_f3_gate.get("status") == "ok" and float(p_f3_gate["permutation_pvalue_two_sided"]) < 0.05:
            interpretation = "strengthened support"
    if f3 and gate and float(f3["mean_accuracy"]) < float(gate["mean_accuracy"]):
        interpretation = "weakened support"

    lines = [
        f"# MATCHED SURFACE MULTI-SEED MAIN COMPARISON ({args.timestamp})",
        "",
        "## Purpose",
        "Run a materially stronger multi-seed rerun of the manuscript-facing matched-surface main comparison to stress-test winner stability and uncertainty.",
        "",
        "## Exact matched surface used",
        f"- Canonical surface contract: `{CANONICAL_SURFACE_ID}`",
        "- Strict rerun status: yes (same datasets, budgets, matched protocol, and simulation substrate; only seed count expanded).",
        "",
        "## Methods included",
        f"- Requested: {', '.join(methods_requested)}",
        f"- Runnable: {', '.join(methods_runnable)}",
        f"- Blocked: {', '.join(b['method'] for b in blocked) if blocked else 'none'}",
        "",
        "## Seed list used",
        f"- {seeds}",
        "",
        "## Datasets and budgets",
        f"- Datasets: {DATASETS}",
        f"- Budgets: {BUDGETS}",
        "",
        "## Main findings (plain language)",
        f"- Winner by mean accuracy: `{aggregate_summary['winner_by_mean_accuracy']}`.",
        f"- strict_f3 mean accuracy: {f3['mean_accuracy']:.4f} (std {f3['std_accuracy']:.4f}, CI95 [{f3['ci95_low_accuracy']:.4f}, {f3['ci95_high_accuracy']:.4f}])." if f3 else "- strict_f3 missing.",
        f"- strict_gate1_cap_k6 mean accuracy: {gate['mean_accuracy']:.4f} (std {gate['std_accuracy']:.4f}, CI95 [{gate['ci95_low_accuracy']:.4f}, {gate['ci95_high_accuracy']:.4f}])." if gate else "- strict_gate1_cap_k6 missing.",
        f"- l1_max mean accuracy: {l1['mean_accuracy']:.4f} (std {l1['std_accuracy']:.4f}, CI95 [{l1['ci95_low_accuracy']:.4f}, {l1['ci95_high_accuracy']:.4f}])." if l1 else "- l1_max missing.",
        f"- strict_f3 minus strict_gate1_cap_k6 mean gap: {_gap(f3, gate)}.",
        f"- strict_f3 minus l1_max mean gap: {_gap(f3, l1)}.",
        "",
        "## Uncertainty and significance",
        f"- strict_f3 vs strict_gate1_cap_k6 paired permutation p-value: {p_f3_gate.get('permutation_pvalue_two_sided', 'NA') if p_f3_gate else 'NA'}.",
        f"- strict_f3 vs l1_max paired permutation p-value: {p_f3_l1.get('permutation_pvalue_two_sided', 'NA') if p_f3_l1 else 'NA'}.",
        "",
        "## Honest interpretation for paper-writing",
        f"- Assessment: **{interpretation}**.",
        "- This conclusion is bounded to the matched manuscript-facing surface and should not be generalized beyond it.",
        "",
        "## Artifact bundle",
        f"- `outputs/matched_surface_multiseed_main_comparison_{args.timestamp}/`",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"output_dir": str(out_dir.relative_to(REPO_ROOT)), "report": str(report_path.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
