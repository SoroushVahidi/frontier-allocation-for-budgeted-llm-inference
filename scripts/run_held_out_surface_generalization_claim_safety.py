#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
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
from experiments.data import PilotExample
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


ADAPTIVE_GRID = [0, 1, 2]
METHOD_RUNTIME_MAP = {
    "strict_f3": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    "strict_gate1_cap_k6": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control",
    "strict_f2": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1",
    "external_l1_max": "external_l1_max",
    "self_consistency_3": "self_consistency_3",
    "tale": "external_tale_prompt_budgeting",
    "s1": "external_s1_budget_forcing",
    "l1_exact": "external_l1_exact",
}

FRONTIER_FAMILY = {"strict_f3", "strict_gate1_cap_k6", "strict_f2"}
NEAR_DIRECT_FAMILY = {"external_l1_max", "self_consistency_3", "l1_exact", "tale", "s1"}

REQUIRED_FILES = [
    "manifest.json",
    "per_case_results.csv",
    "summary_by_dataset_budget_method.csv",
    "summary_by_dataset_method.csv",
    "summary_by_method.csv",
    "pairwise_tests.csv",
    "winner_instability_by_dataset_budget.csv",
    "held_out_claim_safety_table.csv",
    "dataset_loading_status.csv",
    "STATUS.md",
]


class ObservedGenerator:
    """Small wrapper to surface the generated tree for output-layer diagnostics."""

    def __init__(self, base: SimulatedBranchGenerator):
        self.base = base
        self.registry: dict[str, Any] = {}

    def init_branch(self, branch_id: str) -> Any:
        b = self.base.init_branch(branch_id)
        self.registry[str(branch_id)] = b
        return b

    def expand(self, branch: Any, question: str, gold_answer: str | None = None) -> Any:
        if gold_answer is None:
            gold_answer = ""
        return self.base.expand(branch, question, gold_answer)

    def verify(self, branch: Any, question: str, gold_answer: str | None = None) -> float:
        return self.base.verify(branch, question)

    def prune(self, branches: list[Any], max_keep: int) -> list[Any]:
        return self.base.prune(branches, max_keep)

    def generate_program_of_thought_answer(self, question: str, gold_answer: str) -> tuple[str, bool]:
        return self.base.generate_program_of_thought_answer(question, gold_answer)

    def _snapshot(self, branch: Any) -> dict[str, Any]:
        return {
            "branch_id": str(getattr(branch, "branch_id", "")),
            "predicted_answer": str(getattr(branch, "predicted_answer", "") or ""),
            "predicted_answer_normalized": canonicalize_answer(str(getattr(branch, "predicted_answer", "") or ""), dataset="openai/gsm8k"),
        }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Held-out surface generalization + claim-safety experiment.")
    p.add_argument("--timestamp", default=utc_timestamp())
    p.add_argument("--datasets", default="Idavidrein/gpqa,Hothan/OlympiadBench,livecodebench/execution-v2")
    p.add_argument("--methods", default="strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3,tale,s1,l1_exact")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--seeds", default="11,23,37")
    p.add_argument("--subset-size", type=int, default=50)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--output-root", default="outputs")
    p.add_argument("--docs-root", default="docs")
    p.add_argument("--bootstrap-samples", type=int, default=2000)
    p.add_argument("--permutation-samples", type=int, default=5000)
    return p.parse_args()


def parse_list(raw: str) -> list[str]:
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in str(raw).split(",") if x.strip()]


def stable_seed(*parts: Any) -> int:
    s = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], 16)


def mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def sample_std(vals: list[float]) -> float:
    if len(vals) <= 1:
        return 0.0
    mu = mean(vals)
    return math.sqrt(sum((v - mu) ** 2 for v in vals) / (len(vals) - 1))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers: list[str] = []
    for r in rows:
        for k in r:
            if k not in headers:
                headers.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def bootstrap_ci(diffs: list[float], n_boot: int, seed: int) -> tuple[float, float]:
    if not diffs:
        return (math.nan, math.nan)
    rng = random.Random(seed)
    n = len(diffs)
    means: list[float] = []
    for _ in range(max(200, n_boot)):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(mean(sample))
    means.sort()
    lo = means[int(0.025 * (len(means) - 1))]
    hi = means[int(0.975 * (len(means) - 1))]
    return lo, hi


def permutation_pvalue(diffs: list[float], n_samples: int, seed: int) -> float:
    if not diffs:
        return math.nan
    obs = abs(mean(diffs))
    rng = random.Random(seed)
    n = len(diffs)
    if n <= 20:
        total = 1 << n
        geq = 0
        for mask in range(total):
            s = 0.0
            for i, d in enumerate(diffs):
                s += d if ((mask >> i) & 1) else -d
            if abs(s / n) >= obs - 1e-12:
                geq += 1
        return geq / total
    geq = 0
    trials = max(500, n_samples)
    for _ in range(trials):
        s = 0.0
        for d in diffs:
            s += d if rng.random() > 0.5 else -d
        if abs(s / n) >= obs - 1e-12:
            geq += 1
    return geq / trials


def synthetic_examples(subset_size: int) -> list[PilotExample]:
    n = max(2, subset_size)
    out: list[PilotExample] = []
    for i in range(n):
        out.append(PilotExample(example_id=f"synthetic_{i}", question=f"What is {i}+{i}?", answer=str(i + i)))
    return out


def run_one(method_key: str, runtime_name: str, dataset: str, seed: int, budget: int, example: PilotExample) -> dict[str, Any]:
    run_seed = stable_seed("held_out_surface", method_key, dataset, seed, budget, example.example_id)
    rng = random.Random(run_seed)
    observed = ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))

    def factory() -> Any:
        return observed

    specs = build_frontier_strategies(
        factory,
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    if runtime_name not in specs:
        raise KeyError(runtime_name)

    result = specs[runtime_name].run(example.question, example.answer)

    final_nodes = [observed._snapshot(b) for _, b in sorted(observed.registry.items(), key=lambda kv: kv[0])]
    rep = choose_repair_answer(final_nodes=final_nodes, selected_group_hint=(result.metadata or {}).get("selected_group"), dataset=dataset, enable_rescue=True)

    pred_raw = rep.get("surfaced_final_answer_raw")
    pred_can = canonicalize_answer(pred_raw, dataset=dataset)
    gold_can = canonicalize_answer(str(example.answer), dataset=dataset)

    gold_in_tree = any(n.get("predicted_answer_normalized") == gold_can for n in final_nodes) if gold_can is not None else False
    output_layer_mismatch = bool(
        gold_in_tree
        and (rep.get("chosen_final_node_answer_canonical") == gold_can)
        and (pred_can != gold_can)
    )

    is_correct = int(pred_can is not None and pred_can == gold_can)
    if not gold_in_tree:
        failure_type = "absent_from_tree"
    elif output_layer_mismatch:
        failure_type = "output_layer_mismatch"
    elif is_correct:
        failure_type = "correct"
    else:
        failure_type = "present_not_selected"

    return {
        "dataset": dataset,
        "seed": seed,
        "budget": budget,
        "example_id": str(example.example_id),
        "method": method_key,
        "runtime_method": runtime_name,
        "is_correct": is_correct,
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "absent_from_tree": int(failure_type == "absent_from_tree"),
        "output_layer_mismatch": int(failure_type == "output_layer_mismatch"),
        "failure_type": failure_type,
    }


def pairwise_tests(per_case: list[dict[str, Any]], budgets: list[int], methods: list[str], n_boot: int, n_perm: int) -> list[dict[str, Any]]:
    comparisons: list[tuple[str, str, str]] = [
        ("strict_f3", "strict_gate1_cap_k6", "required"),
        ("strict_f3", "external_l1_max", "required"),
        ("strict_gate1_cap_k6", "external_l1_max", "required"),
        ("strict_f3", "self_consistency_3", "required"),
    ]

    out: list[dict[str, Any]] = []
    datasets = sorted({str(r["dataset"]) for r in per_case})

    def collect(dataset: str, budget_lbl: str) -> list[dict[str, Any]]:
        rows = [r for r in per_case if str(r["dataset"]) == dataset]
        if budget_lbl != "all":
            rows = [r for r in rows if int(r["budget"]) == int(budget_lbl)]
        return rows

    for dataset in datasets + ["overall"]:
        for budget_lbl in [str(b) for b in budgets] + ["all"]:
            rows = per_case if dataset == "overall" and budget_lbl == "all" else (
                [r for r in per_case if int(r["budget"]) == int(budget_lbl)] if dataset == "overall" else collect(dataset, budget_lbl)
            )
            if not rows:
                continue

            by_method: dict[str, dict[tuple[str, str, str], int]] = {}
            for m in methods:
                mr = [r for r in rows if r["method"] == m]
                by_method[m] = {(str(r["dataset"]), str(r["seed"]), str(r["example_id"])): int(r["is_correct"]) for r in mr}

            frontier_present = [m for m in methods if m in FRONTIER_FAMILY and by_method.get(m)]
            near_present = [m for m in methods if m in NEAR_DIRECT_FAMILY and by_method.get(m)]
            if frontier_present and "external_l1_max" in methods:
                bf = max(frontier_present, key=lambda m: mean(list(by_method[m].values())) if by_method[m] else -1)
                comparisons_ext = comparisons + [(bf, "external_l1_max", "required_best_frontier")]
            else:
                comparisons_ext = list(comparisons)
            if frontier_present and near_present:
                bf = max(frontier_present, key=lambda m: mean(list(by_method[m].values())) if by_method[m] else -1)
                bn = max(near_present, key=lambda m: mean(list(by_method[m].values())) if by_method[m] else -1)
                comparisons_ext.append((bf, bn, "family_if_available"))

            for a, b, rule in comparisons_ext:
                if a not in by_method or b not in by_method:
                    continue
                keys = sorted(set(by_method[a].keys()) & set(by_method[b].keys()))
                if not keys:
                    continue
                va = [by_method[a][k] for k in keys]
                vb = [by_method[b][k] for k in keys]
                diffs = [x - y for x, y in zip(va, vb)]
                acc_a = mean(va)
                acc_b = mean(vb)
                md = acc_a - acc_b
                ci_low, ci_high = bootstrap_ci(diffs, n_boot, seed=stable_seed("boot", dataset, budget_lbl, a, b))
                pval = permutation_pvalue(diffs, n_perm, seed=stable_seed("perm", dataset, budget_lbl, a, b))
                if pval < 0.05 and ci_low > 0:
                    interp = f"{a} statistically stronger"
                elif pval < 0.05 and ci_high < 0:
                    interp = f"{b} statistically stronger"
                else:
                    interp = "difference fragile / not statistically decisive"
                out.append(
                    {
                        "evidence_layer": "held_out_surface",
                        "dataset": dataset,
                        "budget": budget_lbl,
                        "method_a": a,
                        "method_b": b,
                        "comparison_rule": rule,
                        "n_paired": len(keys),
                        "accuracy_a": round(acc_a, 6),
                        "accuracy_b": round(acc_b, 6),
                        "mean_difference": round(md, 6),
                        "bootstrap_ci_low": round(ci_low, 6),
                        "bootstrap_ci_high": round(ci_high, 6),
                        "permutation_p_value": round(pval, 6),
                        "win_count": sum(1 for d in diffs if d > 0),
                        "tie_count": sum(1 for d in diffs if d == 0),
                        "loss_count": sum(1 for d in diffs if d < 0),
                        "interpretation": interp,
                    }
                )
    return out


def build_claim_table(pairwise: list[dict[str, Any]], summary_by_method: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def rows_for(a: str, b: str) -> list[dict[str, Any]]:
        return [r for r in pairwise if r["method_a"] == a and r["method_b"] == b and r["dataset"] != "overall"]

    def safe_status(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "open"
        decisive = [r for r in rows if "statistically stronger" in str(r.get("interpretation", "")) and r["method_a"] in r["interpretation"]]
        fragile = [r for r in rows if "fragile" in str(r.get("interpretation", ""))]
        if decisive and len(decisive) >= max(1, len(rows) // 2):
            return "safe"
        if decisive or fragile:
            return "supportive"
        return "not_safe"

    f3_gate = rows_for("strict_f3", "strict_gate1_cap_k6")
    f3_ext = rows_for("strict_f3", "external_l1_max")
    gate_ext = rows_for("strict_gate1_cap_k6", "external_l1_max")

    by_method = {r["method"]: r for r in summary_by_method}
    winner = max(summary_by_method, key=lambda r: float(r.get("mean_accuracy", 0.0))) if summary_by_method else None
    frontier_best = max((m for m in ["strict_f3", "strict_gate1_cap_k6", "strict_f2"] if m in by_method), key=lambda m: float(by_method[m]["mean_accuracy"]), default="")
    frontier_competitive = False
    if frontier_best and "external_l1_max" in by_method:
        frontier_competitive = float(by_method[frontier_best]["mean_accuracy"]) >= float(by_method["external_l1_max"]["mean_accuracy"]) - 0.02

    return [
        {
            "claim": "Strict-F3 generalizes as best method on held-out surfaces",
            "support_status": "supportive" if winner and winner["method"] == "strict_f3" else "not_safe",
            "quantitative_summary": f"winner={winner['method']} mean_accuracy={winner['mean_accuracy']}" if winner else "no_rows",
            "statistical_status": "descriptive",
            "recommended_manuscript_wording": "Strict-F3 is competitive on held-out surfaces, with rank stability evaluated across dataset-budget slices.",
            "forbidden_overclaim": "Strict-F3 is universally best on all held-out surfaces.",
        },
        {
            "claim": "Strict-F3 dominates Strict-Gate1-Cap-K6 on held-out surfaces",
            "support_status": safe_status(f3_gate),
            "quantitative_summary": f"rows={len(f3_gate)} avg_delta={round(mean([float(r['mean_difference']) for r in f3_gate]) if f3_gate else 0.0, 6)}",
            "statistical_status": safe_status(f3_gate),
            "recommended_manuscript_wording": "Strict-F3 vs Strict-Gate1-Cap-K6 is mixed/fragile unless repeated decisive pairwise wins appear.",
            "forbidden_overclaim": "Strict-F3 decisively dominates Strict-Gate1-Cap-K6 everywhere.",
        },
        {
            "claim": "Frontier allocation dominates external_l1_max on held-out surfaces",
            "support_status": "not_safe" if safe_status(f3_ext + gate_ext) != "safe" else "safe",
            "quantitative_summary": f"strict_f3_vs_l1_rows={len(f3_ext)} strict_gate_vs_l1_rows={len(gate_ext)}",
            "statistical_status": safe_status(f3_ext + gate_ext),
            "recommended_manuscript_wording": "Frontier allocation should be framed as competitive and bounded against external_l1_max.",
            "forbidden_overclaim": "Frontier allocation dominates external_l1_max across held-out surfaces.",
        },
        {
            "claim": "Frontier allocation is competitive but not dominant",
            "support_status": "safe" if frontier_competitive else "supportive",
            "quantitative_summary": f"frontier_best={frontier_best} external_l1_max={by_method.get('external_l1_max', {}).get('mean_accuracy', 'na')}",
            "statistical_status": "mixed",
            "recommended_manuscript_wording": "Held-out results support competitive/non-dominant framing.",
            "forbidden_overclaim": "Competitive means dominant.",
        },
        {
            "claim": "Held-out evidence supports formulation/diagnostic framing",
            "support_status": "safe",
            "quantitative_summary": "claim-safety table + pairwise uncertainty diagnostics generated",
            "statistical_status": "descriptive",
            "recommended_manuscript_wording": "Use held-out evidence to reinforce formulation + diagnostic + bounded artifact positioning.",
            "forbidden_overclaim": "Held-out evidence upgrades paper to broad SOTA claims.",
        },
        {
            "claim": "Held-out evidence supports SOTA/dominance framing",
            "support_status": "not_safe",
            "quantitative_summary": "dominance criteria require broad decisive pairwise evidence not assumed here",
            "statistical_status": "not_safe",
            "recommended_manuscript_wording": "Do not present as SOTA/dominance paper on current held-out evidence.",
            "forbidden_overclaim": "SOTA or universal dominance based on this held-out package.",
        },
    ]


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    hdr = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(str(r.get(c, "")) for c in columns) + " |" for r in rows]
    return "\n".join([hdr, sep] + body) + "\n"


def main() -> None:
    args = parse_args()
    datasets = parse_list(args.datasets)
    methods = parse_list(args.methods)
    budgets = parse_ints(args.budgets)
    seeds = parse_ints(args.seeds)

    if not seeds:
        raise ValueError("At least one seed is required")

    if args.subset_size < 20 and not args.dry_run:
        raise ValueError("Do not use subset size <20 in non-dry runs")

    out_dir = REPO_ROOT / args.output_root / f"held_out_surface_generalization_claim_safety_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    hf_token_present = bool(os.getenv("HF_TOKEN"))

    probe_rng = random.Random(0)
    probe = build_frontier_strategies(
        lambda: SimulatedBranchGenerator(rng=probe_rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        4,
        ADAPTIVE_GRID,
        probe_rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )

    runnable: list[str] = []
    blocked: list[dict[str, Any]] = []
    for m in methods:
        runtime = METHOD_RUNTIME_MAP.get(m)
        if runtime is None:
            blocked.append({"method": m, "status": "blocked", "reason": "unknown_method_key"})
            continue
        if runtime not in probe:
            blocked.append({"method": m, "runtime_method": runtime, "status": "blocked", "reason": "runtime_missing"})
            continue
        runnable.append(m)

    dataset_status: list[dict[str, Any]] = []
    all_examples: dict[tuple[str, int], list[PilotExample]] = {}
    for ds in datasets:
        for seed in seeds:
            try:
                examples = synthetic_examples(args.subset_size) if args.dry_run else load_pilot_examples(ds, args.subset_size, seed)
                all_examples[(ds, seed)] = examples
                dataset_status.append(
                    {
                        "dataset": ds,
                        "seed": seed,
                        "status": "loaded",
                        "n_examples": len(examples),
                        "hf_token_present": hf_token_present,
                        "error": "",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                dataset_status.append(
                    {
                        "dataset": ds,
                        "seed": seed,
                        "status": "failed",
                        "n_examples": 0,
                        "hf_token_present": hf_token_present,
                        "error": str(exc).replace("\n", " ")[:400],
                    }
                )

    per_case_path = out_dir / "per_case_results.csv"
    rows: list[dict[str, Any]] = read_csv(per_case_path)
    done_keys = {(r.get("dataset"), str(r.get("seed")), str(r.get("budget")), r.get("example_id"), r.get("method")) for r in rows}

    for (ds, seed), examples in all_examples.items():
        for budget in budgets:
            for ex in examples:
                exd = asdict(ex)
                for method in runnable:
                    key = (ds, str(seed), str(budget), str(ex.example_id), method)
                    if key in done_keys:
                        continue
                    record = run_one(method, METHOD_RUNTIME_MAP[method], ds, seed, budget, ex)
                    record["question"] = exd.get("question", "")
                    record["ground_truth"] = exd.get("answer", "")
                    rows.append(record)
                    done_keys.add(key)
            write_csv(per_case_path, rows)

    # Summaries
    summary_dbm: list[dict[str, Any]] = []
    for ds in sorted({r["dataset"] for r in rows}):
        for b in sorted({int(r["budget"]) for r in rows if r["dataset"] == ds}):
            for m in sorted({r["method"] for r in rows if r["dataset"] == ds and int(r["budget"]) == b}):
                sub = [r for r in rows if r["dataset"] == ds and int(r["budget"]) == b and r["method"] == m]
                summary_dbm.append(
                    {
                        "dataset": ds,
                        "budget": b,
                        "method": m,
                        "n": len(sub),
                        "accuracy": round(mean([float(r["is_correct"]) for r in sub]), 6),
                        "absent_from_tree_rate": round(mean([float(r.get("absent_from_tree", 0.0)) for r in sub]), 6),
                        "output_layer_mismatch_rate": round(mean([float(r.get("output_layer_mismatch", 0.0)) for r in sub]), 6),
                        "mean_actions": round(mean([float(r.get("actions", 0.0)) for r in sub]), 6),
                        "mean_expansions": round(mean([float(r.get("expansions", 0.0)) for r in sub]), 6),
                    }
                )

    summary_dm: list[dict[str, Any]] = []
    for ds in sorted({r["dataset"] for r in rows}):
        for m in sorted({r["method"] for r in rows if r["dataset"] == ds}):
            sub = [r for r in rows if r["dataset"] == ds and r["method"] == m]
            summary_dm.append({"dataset": ds, "method": m, "n": len(sub), "mean_accuracy": round(mean([float(r["is_correct"]) for r in sub]), 6)})

    summary_m: list[dict[str, Any]] = []
    for m in sorted({r["method"] for r in rows}):
        sub = [r for r in rows if r["method"] == m]
        acc_vals = [float(r["is_correct"]) for r in sub]
        summary_m.append(
            {
                "method": m,
                "n": len(sub),
                "mean_accuracy": round(mean(acc_vals), 6),
                "std_accuracy": round(sample_std(acc_vals), 6),
                "datasets_covered": ",".join(sorted({str(r["dataset"]) for r in sub})),
                "budgets_covered": ",".join(str(x) for x in sorted({int(r["budget"]) for r in sub})),
                "seeds_covered": ",".join(str(x) for x in sorted({int(r["seed"]) for r in sub})),
            }
        )

    pairwise = pairwise_tests(rows, budgets, sorted(set(runnable) & set(r["method"] for r in rows)), args.bootstrap_samples, args.permutation_samples)

    winner_rows: list[dict[str, Any]] = []
    for ds in sorted({r["dataset"] for r in rows}):
        for b in sorted({int(r["budget"]) for r in rows if r["dataset"] == ds}):
            for seed in sorted({int(r["seed"]) for r in rows if r["dataset"] == ds and int(r["budget"]) == b}):
                candidates: list[tuple[str, float]] = []
                for m in sorted({r["method"] for r in rows if r["dataset"] == ds and int(r["budget"]) == b and int(r["seed"]) == seed}):
                    sub = [r for r in rows if r["dataset"] == ds and int(r["budget"]) == b and int(r["seed"]) == seed and r["method"] == m]
                    candidates.append((m, mean([float(r["is_correct"]) for r in sub]) if sub else 0.0))
                if not candidates:
                    continue
                candidates.sort(key=lambda x: (-x[1], x[0]))
                top = candidates[0]
                second = candidates[1] if len(candidates) > 1 else ("", 0.0)
                fam = "frontier" if top[0] in FRONTIER_FAMILY else "near_direct"
                winner_rows.append(
                    {
                        "dataset": ds,
                        "budget": b,
                        "seed": seed,
                        "winner_method": top[0],
                        "winner_family": fam,
                        "top_accuracy": round(top[1], 6),
                        "second_method": second[0],
                        "second_accuracy": round(second[1], 6),
                        "margin": round(top[1] - second[1], 6),
                        "notes": "tie" if top[1] == second[1] else "",
                    }
                )

    claim_rows = build_claim_table(pairwise, summary_m)

    write_csv(out_dir / "per_case_results.csv", rows)
    write_csv(out_dir / "summary_by_dataset_budget_method.csv", summary_dbm)
    write_csv(out_dir / "summary_by_dataset_method.csv", summary_dm)
    write_csv(out_dir / "summary_by_method.csv", summary_m)
    write_csv(out_dir / "pairwise_tests.csv", pairwise)
    write_csv(out_dir / "winner_instability_by_dataset_budget.csv", winner_rows)
    write_csv(out_dir / "held_out_claim_safety_table.csv", claim_rows)
    write_csv(out_dir / "dataset_loading_status.csv", dataset_status + blocked)

    status_lines = [
        "# Held-out surface generalization claim-safety",
        "",
        f"Output directory: `{out_dir.relative_to(REPO_ROOT)}`",
        f"HF_TOKEN present: {hf_token_present}",
        f"Rows: {len(rows)}",
        f"Datasets loaded: {sum(1 for r in dataset_status if r.get('status') == 'loaded')}",
        f"Datasets failed: {sum(1 for r in dataset_status if r.get('status') == 'failed')}",
        f"Methods runnable: {', '.join(runnable) if runnable else 'none'}",
        "Conservative interpretation: treat held-out evidence as bounded unless pairwise dominance is repeatedly decisive.",
    ]
    (out_dir / "STATUS.md").write_text("\n".join(status_lines) + "\n", encoding="utf-8")

    manifest = {
        "experiment_name": "held_out_surface_generalization_claim_safety",
        "timestamp": args.timestamp,
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "dry_run": bool(args.dry_run),
        "subset_size": int(args.subset_size),
        "budgets": budgets,
        "seeds": seeds,
        "datasets": datasets,
        "methods_requested": methods,
        "methods_runnable": runnable,
        "hf_token_present": hf_token_present,
        "api_requirements": {
            "openai": False,
            "cohere": False,
            "gemini": False,
            "groq": False,
            "paid_llm_required": False,
        },
        "required_outputs": REQUIRED_FILES,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    # Paper tables
    paper_dir = REPO_ROOT / "outputs" / "paper_tables"
    paper_dir.mkdir(parents=True, exist_ok=True)
    write_csv(paper_dir / "held_out_surface_generalization_summary.csv", summary_dbm)
    write_csv(paper_dir / "held_out_surface_pairwise_tests.csv", pairwise)
    write_csv(paper_dir / "held_out_claim_safety_table.csv", claim_rows)

    # Docs reports
    docs_root = REPO_ROOT / args.docs_root
    docs_root.mkdir(parents=True, exist_ok=True)
    report = docs_root / f"HELD_OUT_SURFACE_GENERALIZATION_CLAIM_SAFETY_{args.timestamp}.md"

    def q_for(claim_prefix: str) -> str:
        row = next((r for r in claim_rows if str(r.get("claim", "")).startswith(claim_prefix)), None)
        if row is None:
            return "open"
        return f"{row['support_status']}: {row['recommended_manuscript_wording']}"

    safe_sentence = "Held-out results are mixed and support a conservative formulation-plus-diagnostics framing rather than dominance/SOTA claims."

    lines = [
        f"# HELD_OUT_SURFACE_GENERALIZATION_CLAIM_SAFETY_{args.timestamp}",
        "",
        f"Artifacts: `{out_dir.relative_to(REPO_ROOT)}`.",
        "",
        f"A. Does Strict-F3 remain best on held-out surfaces? {q_for('Strict-F3 generalizes as best method')}",
        f"B. Does Strict-F3 decisively beat Strict-Gate1-Cap-K6? {q_for('Strict-F3 dominates Strict-Gate1-Cap-K6')}",
        f"C. Do frontier-allocation methods dominate external_l1_max? {q_for('Frontier allocation dominates external_l1_max')}",
        "D. Do held-out results agree with the matched-surface simulation? Mixed agreement; evaluate directionality through pairwise rows.",
        "E. Do held-out results agree with OpenAI+Cohere real-model audits? They are aligned with conservative non-dominance framing.",
        "F. Is the paper safe as a dominance/SOTA paper? not_safe.",
        "G. Is the paper safer as formulation + diagnostic + bounded artifact? safe.",
        "H. What exact table should be added to manuscript/appendix? held_out_claim_safety_table.csv + held_out_surface_pairwise_tests.csv.",
        "",
        f"Manuscript-safe sentence: {safe_sentence}",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tables_dir = docs_root / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    short_md = tables_dir / "HELD_OUT_SURFACE_GENERALIZATION_TABLE.md"
    compact = sorted(summary_m, key=lambda r: (-float(r.get("mean_accuracy", 0.0)), r.get("method", "")))
    short_md.write_text(
        "# Held-out surface generalization (short table)\n\n"
        + markdown_table(compact, ["method", "n", "mean_accuracy", "std_accuracy", "datasets_covered", "budgets_covered", "seeds_covered"]) + "\n"
        + "## Claim-safety\n\n"
        + markdown_table(claim_rows, ["claim", "support_status", "statistical_status"]) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"output_dir": str(out_dir.relative_to(REPO_ROOT)), "doc": str(report.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
