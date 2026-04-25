#!/usr/bin/env python3
"""Run matched-budget ToT-style adapter baselines alongside frontier methods (simulator by default).

This script is **not** an official Tree-of-Thoughts reproduction. It records bounded,
manuscript-facing comparisons under the repository's shared action-budget ledger.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import random
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datasets import load_dataset

from experiments.branching import SimulatedBranchGenerator
from experiments.controllers import BestOfNController
from experiments.data import PilotExample
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples
from experiments.hf_datasets import check_git_dataset_access, sample_git_dataset_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer
from experiments.scoring import ScoreConfig, SimpleBranchScorer
from experiments.tot_matched_budget_adapters import attach_tot_matched_budget_methods

ADAPTIVE_GRID = [0, 1, 2]
DEFAULT_BUDGETS = [4, 6, 8]
DEFAULT_SEEDS = [11, 23, 37, 41, 53]
DEFAULT_SUBSET_SIZE = 40
REQUESTED_METHODS = [
    "strict_f3_anti_collapse_weak_v1",
    "strict_f3",
    "strict_gate1_cap_k6",
    "tot_bfs_matched_budget",
    "tot_beam_matched_budget",
    "tot_dfs_matched_budget",
    "self_consistency_3",
    "self_consistency_5",
    "external_l1_max",
]
PUBLIC_TO_RUNTIME = {
    "strict_f3": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1",
    "strict_gate1_cap_k6": "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control",
}
DESIRED_DATASETS = [
    "openai/gsm8k",
    "HuggingFaceH4/MATH-500",
    "HuggingFaceH4/aime_2024",
    "google-deepmind/natural-plan",
    "Idavidrein/gpqa",
    "TIGER-Lab/MMLU-Pro",
]


def _load_twenty_module() -> Any:
    path = REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py"
    spec = importlib.util.spec_from_file_location("twenty_exact_bundle_for_tot_baseline", path)
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
        prompt = "\n".join([q, "", "Choose one option and answer with a single letter (A/B/C/D).", *option_lines])
        out.append(PilotExample(example_id=f"gpqa_diamond_{seed}_{i}", question=prompt, answer=gold_label))
    return out


def _load_examples_for_dataset(dataset: str, subset_size: int, seed: int, natural_plan_task: str) -> list[PilotExample]:
    if dataset == "google-deepmind/natural-plan":
        return _load_natural_plan_examples(subset_size, seed, task_name=natural_plan_task)
    if dataset == "Idavidrein/gpqa":
        return _load_gpqa_examples(subset_size, seed)
    return load_pilot_examples(dataset, subset_size, seed)


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


def _runtime_for_method(method: str) -> str:
    return PUBLIC_TO_RUNTIME.get(method, method)


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


def _pairwise_tests(
    rows: list[dict[str, Any]],
    comparisons: list[tuple[str, str]],
    *,
    n_boot: int = 2000,
    n_perm: int = 2000,
) -> list[dict[str, Any]]:
    idx = {
        (str(r["dataset"]), int(r["budget"]), int(r["seed"]), str(r["example_id"]), str(r["method"])): int(r["is_correct"])
        for r in rows
    }
    out: list[dict[str, Any]] = []
    for a, b in comparisons:
        diffs: list[float] = []
        a_vals: list[float] = []
        b_vals: list[float] = []
        for key in idx:
            d, bdg, s, ex, m = key
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


def _best_tot_method(main_summary: list[dict[str, Any]]) -> str:
    tot_rows = [r for r in main_summary if str(r["method"]).startswith("tot_")]
    if not tot_rows:
        return "tot_beam_matched_budget"
    best = max(tot_rows, key=lambda r: float(r["mean_accuracy"]))
    return str(best["method"])


def _run_example_bundle(
    *,
    dataset: str,
    seed: int,
    budget: int,
    ex: PilotExample,
    runnable_methods: list[str],
    use_openai: bool,
    model: str,
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: int,
    api_backend: str | None,
) -> list[dict[str, Any]]:
    """One strategy build per (example, budget); each controller owns an independent generator instance."""
    rng_loop = random.Random(_stable_seed("tot_cell_rng", dataset, seed, budget, ex.example_id) & 0xFFFFFFFF)

    def generator_factory() -> Any:
        if use_openai:
            inner = generator_factory_for_mode(
                True,
                rng_loop,
                model,
                temperature,
                max_output_tokens,
                timeout_seconds,
                api_provider=api_backend,
            )()
            return TW.ObservedGenerator(inner)  # type: ignore[attr-defined]
        rng_cell = random.Random(_stable_seed("tot_sim", dataset, seed, budget, ex.example_id) & 0xFFFFFFFF)
        return TW.ObservedGenerator(SimulatedBranchGenerator(rng=rng_cell, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))  # type: ignore[attr-defined]

    specs = build_frontier_strategies(
        generator_factory,
        budget,
        ADAPTIVE_GRID,
        rng_loop,
        use_openai_api=use_openai,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    scorer = SimpleBranchScorer(ScoreConfig())
    specs["self_consistency_5"] = BestOfNController(generator_factory(), scorer, budget, n_candidates=5)
    attach_tot_matched_budget_methods(specs, generator_factory, scorer, budget)

    out_rows: list[dict[str, Any]] = []
    for method_public in runnable_methods:
        runtime = _runtime_for_method(method_public)
        if runtime not in specs:
            raise KeyError(f"Method unavailable: {method_public} ({runtime})")
        ctrl = specs[runtime]
        result = ctrl.run(ex.question, ex.answer)
        if int(result.actions_used) > int(budget):
            raise RuntimeError(f"Budget exceeded: method={method_public} actions={result.actions_used} budget={budget}")

        gen = getattr(ctrl, "generator", None)
        if gen is None:
            raise RuntimeError(f"Controller missing generator for repair: {method_public}")
        final_nodes = [gen._snapshot(b) for _, b in sorted(gen.registry.items(), key=lambda kv: kv[0])]  # type: ignore[attr-defined]
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

        out_rows.append(
            {
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
        )
    return out_rows


def _resolve_datasets(desired: list[str], natural_plan_task: str) -> tuple[list[str], list[dict[str, Any]]]:
    feasible: list[str] = []
    infeasible: list[dict[str, Any]] = []
    np_status = _ensure_natural_plan_clone()
    gpqa_ok = False
    try:
        _ = _load_gpqa_examples(2, 0)
        gpqa_ok = True
    except Exception as e:
        infeasible.append({"dataset": "Idavidrein/gpqa", "reason": f"load_failed:{type(e).__name__}:{e}"})

    for ds in desired:
        if ds == "google-deepmind/natural-plan":
            if bool(np_status.get("feasible")):
                feasible.append(ds)
            else:
                infeasible.append({"dataset": ds, "reason": str(np_status.get("reason", "natural_plan_unavailable"))})
            continue
        if ds == "Idavidrein/gpqa":
            if gpqa_ok:
                feasible.append(ds)
            continue
        try:
            _ = load_pilot_examples(ds, min(3, 20), 0)
            feasible.append(ds)
        except Exception as e:
            infeasible.append({"dataset": ds, "reason": f"load_failed:{type(e).__name__}"})
    if not feasible:
        feasible = ["openai/gsm8k"]
        infeasible.append({"dataset": "_fallback", "reason": "no_dataset_loaded_using_gsm8k"})
    return feasible, infeasible


def main() -> None:
    p = argparse.ArgumentParser(description="Matched-budget ToT-style baseline bundle (simulator default).")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--subset-size", type=int, default=DEFAULT_SUBSET_SIZE)
    p.add_argument("--budgets", default=",".join(str(x) for x in DEFAULT_BUDGETS))
    p.add_argument("--seeds", default=",".join(str(x) for x in DEFAULT_SEEDS))
    p.add_argument("--datasets", default=",".join(DESIRED_DATASETS), help="Comma-separated dataset ids to attempt.")
    p.add_argument("--natural-plan-task", default="trip_planning")
    p.add_argument("--api-backend", default="simulator", help="simulator | openai | cohere | ...")
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=1024)
    p.add_argument("--timeout-seconds", type=int, default=60)
    args = p.parse_args()

    budgets = _parse_int_list(args.budgets)
    seeds = _parse_int_list(args.seeds)
    desired = [x.strip() for x in str(args.datasets).split(",") if x.strip()]
    datasets_to_run, infeasible = _resolve_datasets(desired, str(args.natural_plan_task))

    use_openai = str(args.api_backend).strip().lower() != "simulator"
    natural_plan_status = _ensure_natural_plan_clone()

    probe_rng = random.Random(0)

    def _probe_factory() -> Any:
        return TW.ObservedGenerator(SimulatedBranchGenerator(rng=random.Random(0), max_depth=7, finish_prob_base=0.16, answer_noise=0.12))  # type: ignore[attr-defined]

    probe_specs = build_frontier_strategies(
        _probe_factory,
        max(budgets),
        ADAPTIVE_GRID,
        probe_rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    scorer = SimpleBranchScorer(ScoreConfig())
    probe_specs["self_consistency_5"] = BestOfNController(_probe_factory(), scorer, max(budgets), n_candidates=5)
    attach_tot_matched_budget_methods(probe_specs, _probe_factory, scorer, max(budgets))

    runnable_methods: list[str] = []
    for method in REQUESTED_METHODS:
        rt = _runtime_for_method(method)
        if method.startswith("tot_") or method == "self_consistency_5":
            runnable_methods.append(method)
        elif rt in probe_specs:
            runnable_methods.append(method)

    out_dir = REPO_ROOT / "outputs" / f"tot_matched_budget_baseline_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case: list[dict[str, Any]] = []
    for dataset in datasets_to_run:
        for seed in seeds:
            examples = _load_examples_for_dataset(dataset, int(args.subset_size), seed, str(args.natural_plan_task))
            for budget in budgets:
                for ex in examples:
                    per_case.extend(
                        _run_example_bundle(
                            dataset=dataset,
                            seed=seed,
                            budget=budget,
                            ex=ex,
                            runnable_methods=runnable_methods,
                            use_openai=use_openai,
                            model=str(args.model),
                            temperature=float(args.temperature),
                            max_output_tokens=int(args.max_output_tokens),
                            timeout_seconds=int(args.timeout_seconds),
                            api_backend=None if not use_openai else str(args.api_backend),
                        )
                    )

    main_summary = _aggregate(per_case, ["method"])
    per_dataset = _aggregate(per_case, ["dataset", "method"])
    per_dataset_budget = _aggregate(per_case, ["dataset", "budget", "method"])
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

    best_tot = _best_tot_method(main_summary)
    pairwise = _pairwise_tests(
        per_case,
        comparisons=[
            ("strict_f3_anti_collapse_weak_v1", "tot_bfs_matched_budget"),
            ("strict_f3_anti_collapse_weak_v1", "tot_beam_matched_budget"),
            ("strict_f3_anti_collapse_weak_v1", "tot_dfs_matched_budget"),
            ("strict_f3_anti_collapse_weak_v1", "self_consistency_5"),
            ("strict_f3_anti_collapse_weak_v1", "self_consistency_3"),
            ("strict_f3_anti_collapse_weak_v1", "external_l1_max"),
            ("strict_f3_anti_collapse_weak_v1", "strict_f3"),
            (best_tot, "self_consistency_5"),
            (best_tot, "external_l1_max"),
        ],
        n_boot=2000,
        n_perm=2000,
    )

    _write_csv(out_dir / "per_case_outcomes.csv", per_case)
    _write_csv(out_dir / "main_summary.csv", main_summary)
    _write_csv(out_dir / "per_dataset_summary.csv", per_dataset)
    _write_csv(out_dir / "per_dataset_budget_summary.csv", per_dataset_budget)
    _write_csv(out_dir / "per_budget_summary.csv", per_budget)
    _write_csv(out_dir / "per_seed_summary.csv", per_seed)
    _write_csv(out_dir / "pairwise_statistical_tests.csv", pairwise)
    _write_csv(out_dir / "failure_decomposition.csv", failure)
    _write_csv(out_dir / "token_latency_accounting.csv", token_latency)

    manifest = {
        "artifact_family": "tot_matched_budget_baseline",
        "wording_note": "Matched-budget ToT-style adapter baselines; not an official ToT reproduction.",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/run_tot_matched_budget_baseline.py",
        "datasets_ran": datasets_to_run,
        "datasets_desired": desired,
        "infeasible_datasets": infeasible,
        "natural_plan_status": {
            "feasible": bool(natural_plan_status.get("feasible")),
            "mode": natural_plan_status.get("mode", ""),
        },
        "budgets": budgets,
        "seeds": seeds,
        "subset_size_per_dataset_seed": int(args.subset_size),
        "api_backend": str(args.api_backend),
        "methods_requested": REQUESTED_METHODS,
        "methods_ran": runnable_methods,
        "best_tot_variant_by_mean_accuracy": best_tot,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    anti = next((r for r in main_summary if r["method"] == "strict_f3_anti_collapse_weak_v1"), None)
    best_overall = sorted(main_summary, key=lambda r: (-float(r["mean_accuracy"]), float(r["avg_actions"]), str(r["method"])))[0]
    lines = [
        "# Matched-budget ToT-style baseline summary",
        "",
        "This bundle compares frontier allocation methods against **matched-budget ToT-style BFS/beam/DFS adapters** under the shared action ledger.",
        "It is **not** an official Tree-of-Thoughts reproduction.",
        "",
        f"- Datasets ran: {datasets_to_run}",
        f"- Budgets: {budgets}; seeds: {seeds}; subset size: {int(args.subset_size)}",
        f"- Best overall method by mean accuracy: **{best_overall['method']}** (acc={float(best_overall['mean_accuracy']):.4f})",
        f"- Best ToT adapter by mean accuracy: **{best_tot}**",
    ]
    if anti:
        lines.append(
            f"- `strict_f3_anti_collapse_weak_v1` mean accuracy: **{float(anti['mean_accuracy']):.4f}** "
            f"(avg actions {float(anti['avg_actions']):.2f})"
        )
    lines.extend(
        [
            "",
            "## Manuscript-safe wording",
            "- We compare against matched-budget ToT-style BFS/beam/DFS adapters under the same action-budget ledger.",
            "- The result supports comparison against a recognizable search-style baseline under matched-budget adapter conditions.",
            "- This is not an official ToT reproduction; do not claim universal dominance over all search-based reasoning.",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "output_dir": str(out_dir.relative_to(REPO_ROOT)), "datasets_ran": datasets_to_run}, indent=2))


if __name__ == "__main__":
    main()
