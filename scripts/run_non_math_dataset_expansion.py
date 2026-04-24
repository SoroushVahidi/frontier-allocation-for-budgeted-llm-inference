#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datasets import load_dataset

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import BestOfNController
from experiments.data import PilotExample
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.hf_datasets import check_git_dataset_access, sample_git_dataset_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer
from experiments.scoring import ScoreConfig, SimpleBranchScorer
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
    "external_tale_prompt_budgeting",
    "self_consistency_3",
    "self_consistency_5",
]
PUBLIC_TO_RUNTIME = {
    "strict_f3": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    "strict_gate1_cap_k6": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control",
}


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_non_math_expansion", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


TW = _load_twenty_module()


def _stable_seed(*parts: Any) -> int:
    text = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


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


def _ensure_natural_plan_clone() -> dict[str, Any]:
    access = check_git_dataset_access("google-deepmind/natural-plan")
    if bool(access.get("ok")):
        return {"feasible": True, "mode": "existing_clone", "access": access}
    clone_cmd = str(access.get("clone_command", "")).strip()
    if not clone_cmd:
        return {"feasible": False, "reason": "missing_clone_command", "access": access}
    try:
        subprocess.run(clone_cmd.split(), check=True, cwd=REPO_ROOT, capture_output=True, text=True)
    except Exception:
        access2 = check_git_dataset_access("google-deepmind/natural-plan")
        return {
            "feasible": bool(access2.get("ok")),
            "mode": "clone_attempted",
            "reason": "clone_failed_or_incomplete",
            "access": access2,
        }
    access2 = check_git_dataset_access("google-deepmind/natural-plan")
    return {"feasible": bool(access2.get("ok")), "mode": "cloned_now", "access": access2}


def _load_natural_plan_examples(subset_size: int, seed: int, task_name: str = "trip_planning") -> list[PilotExample]:
    rows = sample_git_dataset_examples("google-deepmind/natural-plan", pilot_size=max(subset_size * 2, subset_size), seed=seed)
    filtered = [r for r in rows if str(r.get("task_name", "")) == task_name]
    selected = filtered[:subset_size] if filtered else rows[:subset_size]
    return [
        PilotExample(example_id=str(r["example_id"]), question=str(r.get("question", "")), answer=str(r.get("answer", "")))
        for r in selected
    ]


def _load_gpqa_examples(subset_size: int, seed: int) -> list[PilotExample]:
    token = None
    for key in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        token = token or (str(__import__("os").getenv(key, "")).strip() or None)
    ds = load_dataset("Idavidrein/gpqa", "gpqa_diamond", split="train", token=token)
    ds = ds.shuffle(seed=seed)
    picked = ds.select(range(min(subset_size, len(ds))))

    out: list[PilotExample] = []
    for i, row in enumerate(picked):
        q = str(row.get("Question", "")).strip()
        correct = str(row.get("Correct Answer", "")).strip()
        wrong = [
            str(row.get("Incorrect Answer 1", "")).strip(),
            str(row.get("Incorrect Answer 2", "")).strip(),
            str(row.get("Incorrect Answer 3", "")).strip(),
        ]
        options = [correct] + [w for w in wrong if w]
        rng = random.Random(_stable_seed("gpqa_option_shuffle", seed, i, q))
        rng.shuffle(options)
        labels = ["A", "B", "C", "D"]
        if len(options) < 4:
            options += ["(missing option)"] * (4 - len(options))
        option_lines = [f"{labels[j]}. {options[j]}" for j in range(4)]
        gold_label = labels[options.index(correct)] if correct in options else "A"
        prompt = "\n".join([
            q,
            "",
            "Choose one option and answer with a single letter (A/B/C/D).",
            *option_lines,
        ])
        out.append(PilotExample(example_id=f"gpqa_diamond_{seed}_{i}", question=prompt, answer=gold_label))
    return out


def _load_fallback_non_math_examples(subset_size: int, seed: int) -> list[PilotExample]:
    return load_pilot_examples("TIGER-Lab/MMLU-Pro", subset_size, seed)


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


def _build_probe_specs(budget: int) -> dict[str, Any]:
    rng = random.Random(0)
    specs = build_frontier_strategies(
        lambda: SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12),
        budget,
        ADAPTIVE_GRID,
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
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
    run_seed = _stable_seed("non_math_dataset_expansion", method_public, dataset, seed, budget, ex.example_id)
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
        include_external_tale_baseline=True,
        include_external_l1_baseline=True,
    )
    if method_public == "self_consistency_5":
        specs["self_consistency_5"] = BestOfNController(observed, SimpleBranchScorer(ScoreConfig()), budget, n_candidates=5)
    if method_runtime not in specs:
        raise KeyError(f"Method unavailable: {method_public} ({method_runtime})")

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

    output_mismatch = bool(gold_in_tree and (rep.get("chosen_final_node_answer_canonical") == gold) and (ans != gold))
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


def _bootstrap_ci(diffs: list[float], n_boot: int, seed: int) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_boot):
        means.append(_mean([diffs[rng.randrange(n)] for _ in range(n)]))
    means.sort()
    return (means[int(0.025 * n_boot)], means[min(int(0.975 * n_boot), n_boot - 1)])


def _perm_pvalue(diffs: list[float], n_perm: int, seed: int) -> float:
    if not diffs:
        return 1.0
    rng = random.Random(seed)
    obs = abs(_mean(diffs))
    geq = 0
    for _ in range(n_perm):
        signs = [1.0 if rng.random() < 0.5 else -1.0 for _ in diffs]
        stat = abs(_mean([d * s for d, s in zip(diffs, signs)]))
        if stat >= obs - 1e-12:
            geq += 1
    return (geq + 1.0) / (n_perm + 1.0)


def _pairwise_tests(rows: list[dict[str, Any]], comparisons: list[tuple[str, str]], n_boot: int = 3000, n_perm: int = 3000) -> list[dict[str, Any]]:
    idx = {
        (str(r["dataset"]), int(r["budget"]), int(r["seed"]), str(r["example_id"]), str(r["method"])): int(r["is_correct"])
        for r in rows
    }
    out = []
    for a, b in comparisons:
        diffs = []
        a_vals = []
        b_vals = []
        for d, bdg, s, ex, m in list(idx.keys()):
            if m != a:
                continue
            k_other = (d, bdg, s, ex, b)
            if k_other not in idx:
                continue
            aa = idx[(d, bdg, s, ex, a)]
            bb = idx[k_other]
            diffs.append(float(aa - bb))
            a_vals.append(float(aa))
            b_vals.append(float(bb))
        ci_low, ci_high = _bootstrap_ci(diffs, n_boot=n_boot, seed=_stable_seed(a, b, "boot") & 0xFFFFFFFF)
        p = _perm_pvalue(diffs, n_perm=n_perm, seed=_stable_seed(a, b, "perm") & 0xFFFFFFFF)
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
    p = argparse.ArgumentParser(description="Run selective non-math dataset expansion external-validity bundle.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--subset-size", type=int, default=DEFAULT_SUBSET_SIZE)
    p.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    p.add_argument("--seeds", default=",".join(str(x) for x in DEFAULT_SEEDS))
    p.add_argument("--natural-plan-task", default="trip_planning")
    args = p.parse_args()

    budgets = _parse_int_list(args.budgets)
    seeds = _parse_int_list(args.seeds)

    natural_plan_status = _ensure_natural_plan_clone()
    gpqa_status: dict[str, Any] = {"feasible": False, "reason": "not_checked"}
    try:
        _ = _load_gpqa_examples(subset_size=min(2, int(args.subset_size)), seed=seeds[0])
        gpqa_status = {"feasible": True, "reason": "loaded"}
    except Exception as e:
        gpqa_status = {"feasible": False, "reason": f"load_failed:{type(e).__name__}"}

    datasets_to_run: list[str] = []
    infeasible: list[dict[str, Any]] = []
    if bool(natural_plan_status.get("feasible")):
        datasets_to_run.append("google-deepmind/natural-plan")
    else:
        infeasible.append({"dataset": "google-deepmind/natural-plan", "reason": natural_plan_status.get("reason", "unavailable")})

    if bool(gpqa_status.get("feasible")):
        datasets_to_run.append("Idavidrein/gpqa")
    else:
        infeasible.append({"dataset": "Idavidrein/gpqa", "reason": gpqa_status.get("reason", "unavailable")})

    if not datasets_to_run:
        datasets_to_run = ["TIGER-Lab/MMLU-Pro"]
        infeasible.append({"dataset": "fallback_choice", "reason": "natural_plan_and_gpqa_unavailable"})

    probe = _build_probe_specs(budget=max(budgets))
    runnable_methods: list[tuple[str, str]] = []
    for method in REQUESTED_METHODS:
        runtime = PUBLIC_TO_RUNTIME.get(method, method)
        if runtime in probe or method == "self_consistency_5":
            runnable_methods.append((method, runtime))

    out_dir = REPO_ROOT / "outputs" / f"non_math_dataset_expansion_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case: list[dict[str, Any]] = []
    for dataset in datasets_to_run:
        for seed in seeds:
            if dataset == "google-deepmind/natural-plan":
                examples = _load_natural_plan_examples(subset_size=int(args.subset_size), seed=seed, task_name=str(args.natural_plan_task))
            elif dataset == "Idavidrein/gpqa":
                examples = _load_gpqa_examples(subset_size=int(args.subset_size), seed=seed)
            else:
                examples = _load_fallback_non_math_examples(subset_size=int(args.subset_size), seed=seed)

            for budget in budgets:
                for ex in examples:
                    for m_public, m_runtime in runnable_methods:
                        per_case.append(
                            _run_method(method_public=m_public, method_runtime=m_runtime, dataset=dataset, seed=seed, budget=budget, ex=ex)
                        )

    main_summary = _aggregate(per_case, ["method"])
    per_dataset = _aggregate(per_case, ["dataset", "method"])
    per_budget = _aggregate(per_case, ["budget", "method"])
    per_seed = _aggregate(per_case, ["seed", "method"])
    failure = _aggregate(per_case, ["method", "failure_type"])
    token_latency = [
        {
            "dataset": r["dataset"],
            "seed": r["seed"],
            "budget": r["budget"],
            "example_id": r["example_id"],
            "method": r["method"],
            "actions": r["actions"],
            "expansions": r["expansions"],
            "verifications": r["verifications"],
        }
        for r in per_case
    ]

    best_frontier = sorted(main_summary, key=lambda r: (-float(r["mean_accuracy"]), float(r["avg_actions"]), str(r["method"])))[0]["method"]
    pairwise = _pairwise_tests(
        per_case,
        comparisons=[
            (best_frontier, "self_consistency_3"),
            (best_frontier, "self_consistency_5"),
            (best_frontier, "external_l1_max"),
            ("strict_f3_anti_collapse_weak_v1", "strict_f3"),
            ("strict_f3", "strict_gate1_cap_k6"),
        ],
    )

    _write_csv(out_dir / "per_case_outcomes.csv", per_case)
    _write_csv(out_dir / "main_summary.csv", main_summary)
    _write_csv(out_dir / "per_dataset_summary.csv", per_dataset)
    _write_csv(out_dir / "per_budget_summary.csv", per_budget)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed)
    _write_csv(out_dir / "pairwise_statistical_tests.csv", pairwise)
    _write_csv(out_dir / "failure_decomposition.csv", failure)
    _write_csv(out_dir / "token_latency_accounting.csv", token_latency)

    manifest = {
        "artifact_family": "non_math_dataset_expansion",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_non_math_dataset_expansion.py",
        "datasets_ran": datasets_to_run,
        "infeasible_datasets": infeasible,
        "natural_plan_status": {
            "feasible": bool(natural_plan_status.get("feasible")),
            "mode": natural_plan_status.get("mode", ""),
            "reason": natural_plan_status.get("reason", ""),
        },
        "gpqa_status": gpqa_status,
        "natural_plan_task": str(args.natural_plan_task),
        "budgets": budgets,
        "seeds": seeds,
        "subset_size_per_dataset_seed": int(args.subset_size),
        "pilot_only": bool(int(args.subset_size) < 100),
        "methods_requested": REQUESTED_METHODS,
        "methods_ran": [m for m, _ in runnable_methods],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = [
        "# Non-math dataset expansion summary",
        "",
        f"- Datasets ran: {datasets_to_run}",
        f"- Natural Plan feasible: {bool(natural_plan_status.get('feasible'))}",
        f"- GPQA Diamond feasible: {bool(gpqa_status.get('feasible'))}",
        f"- Infeasible datasets (if any): {infeasible}",
        f"- Budgets: {budgets}; seeds: {seeds}; subset size: {int(args.subset_size)}",
        f"- Best frontier variant (mean accuracy): {best_frontier}",
        "",
        "## Caution",
        "- This output should be treated as pilot evidence when subset size is below 100.",
        "- No universal dominance claim is supported by this bundle.",
    ]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT)), "datasets_ran": datasets_to_run}, indent=2))


if __name__ == "__main__":
    main()
