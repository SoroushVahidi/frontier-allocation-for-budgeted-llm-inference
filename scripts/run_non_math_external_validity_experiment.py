#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import BestOfNController
from experiments.scoring import ScoreConfig, SimpleBranchScorer
from experiments.data import PilotExample, extract_final_answer
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.hf_datasets import check_git_dataset_access, sample_git_dataset_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer
import importlib.util


DEFAULT_BUDGETS = [4, 6, 8]
DEFAULT_SEEDS = [11, 23, 37, 41, 53]
DEFAULT_SUBSET_SIZE = 120
ADAPTIVE_GRID = [0, 1, 2]
REQUESTED_METHODS = [
    "strict_f3",
    "strict_gate1_cap_k6",
    "strict_f3_anti_collapse_weak_v1",
    "external_l1_max",
    "external_s1_budget_forcing",
    "self_consistency_3",
    "self_consistency_5",
]
PUBLIC_TO_RUNTIME = {
    "strict_f3": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    "strict_gate1_cap_k6": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control",
}


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_non_math", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()


def _stable_seed(*parts: Any) -> int:
    text = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _natural_plan_examples(subset_size: int, seed: int) -> list[PilotExample]:
    rows = sample_git_dataset_examples("google-deepmind/natural-plan", pilot_size=subset_size, seed=seed)
    return [
        PilotExample(example_id=r["example_id"], question=r["question"], answer=extract_final_answer(r["answer"]))
        for r in rows
    ]


def resolve_non_math_dataset(explicit_dataset: str | None) -> tuple[str, str]:
    if explicit_dataset:
        return explicit_dataset, "explicit"
    np_access = check_git_dataset_access("google-deepmind/natural-plan")
    if bool(np_access.get("ok")):
        return "google-deepmind/natural-plan", "natural_plan_preferred"
    return "TIGER-Lab/MMLU-Pro", "fallback_non_math_auto_gradable"


def load_non_math_examples(dataset: str, subset_size: int, seed: int) -> list[PilotExample]:
    if dataset == "google-deepmind/natural-plan":
        return _natural_plan_examples(subset_size=subset_size, seed=seed)
    return load_pilot_examples(dataset, subset_size, seed)


def permutation_pvalue(diffs: list[float], n_perm: int = 4000, seed: int = 0) -> float:
    if not diffs:
        return 1.0
    obs = abs(_mean(diffs))
    rng = random.Random(seed)
    geq = 0
    for _ in range(n_perm):
        signs = [1.0 if rng.random() < 0.5 else -1.0 for _ in diffs]
        stat = abs(_mean([d * s for d, s in zip(diffs, signs)]))
        if stat >= obs - 1e-12:
            geq += 1
    return float((geq + 1.0) / (n_perm + 1.0))


def bootstrap_ci(diffs: list[float], n_boot: int = 4000, seed: int = 0) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(_mean(sample))
    means.sort()
    return (means[int(0.025 * n_boot)], means[min(int(0.975 * n_boot), n_boot - 1)])


def _aggregate(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[tuple(r[k] for k in keys)].append(r)
    out = []
    for key, vals in sorted(grouped.items()):
        row = {k: v for k, v in zip(keys, key)}
        row.update(
            {
                "n_cases": len(vals),
                "mean_accuracy": _mean([float(v["is_correct"]) for v in vals]),
                "avg_actions": _mean([float(v["actions"]) for v in vals]),
                "avg_expansions": _mean([float(v["expansions"]) for v in vals]),
                "avg_verifications": _mean([float(v["verifications"]) for v in vals]),
                "absent_from_tree_rate": _mean([float(v["absent_from_tree"]) for v in vals]),
                "present_not_selected_rate": _mean([float(v["present_not_selected"]) for v in vals]),
                "output_layer_mismatch_rate": _mean([float(v["output_layer_mismatch"]) for v in vals]),
            }
        )
        out.append(row)
    return out


def _build_specs(rng: random.Random, budget: int) -> dict[str, Any]:
    specs = build_frontier_strategies(
        lambda: SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_l1_baseline=True,
    )
    specs["self_consistency_5"] = BestOfNController(
        SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        SimpleBranchScorer(ScoreConfig()),
        budget,
        n_candidates=5,
    )
    return specs


def _run_method(method_public: str, method_runtime: str, dataset: str, seed: int, budget: int, ex: PilotExample) -> dict[str, Any]:
    run_seed = _stable_seed("non_math_external_validity", method_public, dataset, seed, budget, ex.example_id)
    rng = random.Random(run_seed)
    observed = TW.ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))

    specs = build_frontier_strategies(
        lambda: observed,
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_l1_baseline=True,
    )
    if method_public == "self_consistency_5":
        specs["self_consistency_5"] = BestOfNController(observed, SimpleBranchScorer(ScoreConfig()), budget, n_candidates=5)
    if method_runtime not in specs:
        raise KeyError(f"Method unavailable: {method_public} (runtime {method_runtime})")
    result = specs[method_runtime].run(ex.question, ex.answer)

    final_nodes = [observed._snapshot(b) for _, b in sorted(observed.registry.items(), key=lambda kv: kv[0])]
    rep = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=(result.metadata or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    ans = canonicalize_answer(rep.get("surfaced_final_answer_raw"), dataset=dataset)
    gold = canonicalize_answer(str(ex.answer), dataset=dataset)
    is_correct = int(ans == gold and ans is not None)
    gold_in_tree = bool(gold is not None and any(n.get("predicted_answer_normalized") == gold for n in final_nodes))
    output_mismatch = bool(
        gold_in_tree and (rep.get("chosen_final_node_answer_canonical") == gold) and (ans != gold)
    )
    extraction_mismatch = bool(
        rep.get("chosen_final_node_answer_canonical") != rep.get("extracted_final_answer_canonical")
        or rep.get("extracted_final_answer_canonical") != rep.get("surfaced_final_answer_canonical")
    )

    if not gold_in_tree:
        failure = "absent_from_tree"
    elif output_mismatch or extraction_mismatch:
        failure = "output_layer_mismatch"
    elif is_correct:
        failure = "correct"
    else:
        failure = "present_not_selected"

    return {
        "dataset": dataset,
        "seed": seed,
        "budget": budget,
        "example_id": str(ex.example_id),
        "method": method_public,
        "is_correct": is_correct,
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "failure_type": failure,
        "absent_from_tree": int(failure == "absent_from_tree"),
        "present_not_selected": int(failure == "present_not_selected"),
        "output_layer_mismatch": int(failure == "output_layer_mismatch"),
    }


def build_pairwise_tests(rows: list[dict[str, Any]], comparisons: list[tuple[str, str]]) -> list[dict[str, Any]]:
    keyed: dict[tuple[str, int, int, str, str], int] = {}
    for r in rows:
        key = (str(r["dataset"]), int(r["budget"]), int(r["seed"]), str(r["example_id"]), str(r["method"]))
        keyed[key] = int(r["is_correct"])
    out: list[dict[str, Any]] = []
    for a, b in comparisons:
        diffs = []
        a_vals = []
        b_vals = []
        for d, budget, seed, exid, m in list(keyed.keys()):
            if m != a:
                continue
            ka = (d, budget, seed, exid, a)
            kb = (d, budget, seed, exid, b)
            if kb not in keyed:
                continue
            da = keyed[ka]
            db = keyed[kb]
            diffs.append(float(da - db))
            a_vals.append(float(da))
            b_vals.append(float(db))
        ci_low, ci_high = bootstrap_ci(diffs, seed=_stable_seed(a, b, "boot") & 0xFFFFFFFF)
        p = permutation_pvalue(diffs, seed=_stable_seed(a, b, "perm") & 0xFFFFFFFF)
        out.append(
            {
                "method_a": a,
                "method_b": b,
                "n_paired": len(diffs),
                "accuracy_a": _mean(a_vals),
                "accuracy_b": _mean(b_vals),
                "mean_difference": _mean(diffs),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "permutation_p_value": p,
            }
        )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Run non-math external-validity matched-budget experiment bundle.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--dataset", default=None)
    p.add_argument("--subset-size", type=int, default=DEFAULT_SUBSET_SIZE)
    p.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    p.add_argument("--seeds", default=",".join(str(x) for x in DEFAULT_SEEDS))
    args = p.parse_args()

    budgets = _parse_int_list(args.budgets)
    seeds = _parse_int_list(args.seeds)
    dataset, selection_mode = resolve_non_math_dataset(args.dataset)

    out_dir = REPO_ROOT / "outputs" / f"non_math_external_validity_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    probe = _build_specs(random.Random(0), budget=max(budgets))
    runnable_methods: list[tuple[str, str]] = []
    for method in REQUESTED_METHODS:
        runtime = PUBLIC_TO_RUNTIME.get(method, method)
        if runtime in probe or method == "self_consistency_5":
            runnable_methods.append((method, runtime))

    per_case = []
    for seed in seeds:
        examples = load_non_math_examples(dataset, subset_size=args.subset_size, seed=seed)
        for budget in budgets:
            for ex in examples:
                for method_public, method_runtime in runnable_methods:
                    per_case.append(
                        _run_method(
                            method_public=method_public,
                            method_runtime=method_runtime,
                            dataset=dataset,
                            seed=seed,
                            budget=budget,
                            ex=ex,
                        )
                    )

    main_summary = _aggregate(per_case, ["method"])
    per_budget = _aggregate(per_case, ["budget", "method"])
    per_dataset = _aggregate(per_case, ["dataset", "budget", "method"])
    per_seed = _aggregate(per_case, ["seed", "budget", "method"])
    failure_decomp = _aggregate(per_case, ["method", "failure_type"])
    token_latency = [
        {
            "method": r["method"],
            "budget": r["budget"],
            "seed": r["seed"],
            "example_id": r["example_id"],
            "actions": r["actions"],
            "expansions": r["expansions"],
            "verifications": r["verifications"],
        }
        for r in per_case
    ]

    best_frontier = sorted(main_summary, key=lambda r: (-float(r["mean_accuracy"]), float(r["avg_actions"]), str(r["method"])))[0]["method"]
    tests = build_pairwise_tests(
        per_case,
        comparisons=[
            (best_frontier, "self_consistency_3"),
            (best_frontier, "self_consistency_5"),
            (best_frontier, "external_l1_max"),
            ("strict_f3", "strict_gate1_cap_k6"),
            ("strict_f3_anti_collapse_weak_v1", "strict_f3"),
        ],
    )

    _write_csv(out_dir / "per_case_outcomes.csv", per_case)
    _write_csv(out_dir / "main_summary.csv", main_summary)
    _write_csv(out_dir / "per_budget_summary.csv", per_budget)
    _write_csv(out_dir / "per_dataset_summary.csv", per_dataset)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed)
    _write_csv(out_dir / "pairwise_statistical_tests.csv", tests)
    _write_csv(out_dir / "failure_decomposition.csv", failure_decomp)
    _write_csv(out_dir / "token_latency_accounting.csv", token_latency)

    manifest = {
        "artifact_family": "non_math_external_validity",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_non_math_external_validity_experiment.py",
        "dataset": dataset,
        "dataset_selection_mode": selection_mode,
        "budgets": budgets,
        "seeds": seeds,
        "subset_size": int(args.subset_size),
        "methods_requested": REQUESTED_METHODS,
        "methods_ran": [m for m, _ in runnable_methods],
        "paired_unit": "dataset,budget,seed,example_id",
        "pilot_only": bool(int(args.subset_size) < 100),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = [
        "# Non-math external-validity summary",
        "",
        f"- Dataset: `{dataset}` (selection mode: `{selection_mode}`).",
        f"- Budgets: `{budgets}`; seeds: `{seeds}`; subset size per seed: `{args.subset_size}`.",
        f"- Methods ran: {', '.join(m for m, _ in runnable_methods)}.",
        f"- Best frontier variant by aggregate mean accuracy: `{best_frontier}`.",
        "",
        "## Headline caution",
        "- Treat as **pilot** if subset size <100; otherwise this is a medium-scale non-math matched-budget external-validity bundle.",
        "- This package does not claim universal dominance; conclusions are budget/dataset matched-slice specific.",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT))}, indent=2))


if __name__ == "__main__":
    main()
