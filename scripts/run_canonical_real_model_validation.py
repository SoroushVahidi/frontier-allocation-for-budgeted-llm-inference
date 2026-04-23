#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples, resolve_api_key_for_provider
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer

STRICT_F3 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
STRICT_GATE1_CAP_K6 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control"
STRICT_F2 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"

METHODS = {
    "strict_f3": {"runtime": STRICT_F3, "enable_output_repair": True, "group": "main"},
    "strict_gate1_cap_k6": {"runtime": STRICT_GATE1_CAP_K6, "enable_output_repair": True, "group": "strong_neighbor"},
    "strict_f2": {"runtime": STRICT_F2, "enable_output_repair": True, "group": "strong_neighbor"},
    "self_consistency_3": {"runtime": "self_consistency_3", "enable_output_repair": True, "group": "simple_baseline"},
    "external_l1_max": {"runtime": "external_l1_max", "enable_output_repair": True, "group": "external_baseline"},
    "strict_f3_no_anti_collapse": {"runtime": "strict_f3_ablation_no_anti_collapse_v1", "enable_output_repair": True, "group": "diagnostic"},
    "strict_f3_no_repeat_expansion_control": {"runtime": "strict_f3_ablation_no_repeat_expansion_control_v1", "enable_output_repair": True, "group": "diagnostic"},
    "strict_f3_no_output_repair": {"runtime": STRICT_F3, "enable_output_repair": False, "group": "diagnostic"},
}


class ObservedGenerator:
    def __init__(self, base: APIBranchGenerator) -> None:
        self.base = base
        self.registry: dict[str, Any] = {}

    def _snapshot(self, b: Any) -> dict[str, Any]:
        reasoning = "\n".join(str(x) for x in getattr(b, "steps", [])) if getattr(b, "steps", None) else ""
        pred = b.predicted_answer
        pred_norm = normalize_answer_text(str(pred) if pred is not None else None).get("normalized_answer")
        return {
            "branch_id": b.branch_id,
            "score": float(getattr(b, "score", 0.0)),
            "depth": int(getattr(b, "depth", 0)),
            "is_done": bool(getattr(b, "is_done", False)),
            "is_pruned": bool(getattr(b, "is_pruned", False)),
            "predicted_answer": pred,
            "predicted_answer_normalized": pred_norm,
            "reasoning_text": reasoning,
        }

    def init_branch(self, branch_id: str) -> Any:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        return b

    def expand(self, branch: Any, question: str, gold_answer: str) -> Any:
        return self.base.expand(branch, question, gold_answer)

    def verify(self, branch: Any, question: str) -> Any:
        return self.base.verify(branch, question)

    def prune(self, branch: Any) -> Any:
        return self.base.prune(branch)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Canonical bounded real-model validation for manuscript-facing claims")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--provider", default="openai")
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    p.add_argument("--subset-size", type=int, default=4)
    p.add_argument("--seeds", default="11,23")
    p.add_argument("--budgets", default="4,6")
    p.add_argument("--methods", default="strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=45)
    return p.parse_args()


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
        "rescue_applied": int(bool(repaired.get("rescue_applied", False))),
    }


def main() -> None:
    args = parse_args()
    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    budgets = [int(x.strip()) for x in args.budgets.split(",") if x.strip()]
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    invalid = [m for m in methods if m not in METHODS]
    if invalid:
        raise ValueError(f"Unknown methods requested: {invalid}. Available={sorted(METHODS)}")

    out_dir = REPO_ROOT / f"outputs/canonical_real_model_validation_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    key = resolve_api_key_for_provider(args.provider)
    if not key:
        raise RuntimeError(f"Missing API key for provider={args.provider}")

    per_example_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, args.subset_size, seed)
            for budget in budgets:
                rng = random.Random(1000003 * seed + 97 * budget + len(dataset))

                def factory() -> Any:
                    return ObservedGenerator(
                        APIBranchGenerator(
                            provider=args.provider,
                            api_key=key,
                            model=args.model,
                            temperature=args.temperature,
                            max_tokens=args.max_output_tokens,
                            timeout_seconds=args.timeout_seconds,
                        )
                    )

                specs = build_frontier_strategies(
                    factory,
                    budget,
                    [1],
                    rng,
                    use_openai_api=True,
                    include_broad_diversity_aggregation_methods=True,
                    include_external_l1_baseline=True,
                    include_external_s1_baseline=True,
                )

                for ex in examples:
                    for method in methods:
                        cfg = METHODS[method]
                        runtime = str(cfg["runtime"])
                        if runtime not in specs:
                            error_rows.append(
                                {
                                    "dataset": dataset,
                                    "seed": seed,
                                    "budget": budget,
                                    "example_id": ex.example_id,
                                    "method": method,
                                    "runtime": runtime,
                                    "error": "runtime_missing_in_specs",
                                }
                            )
                            continue
                        try:
                            controller = specs[runtime]
                            result = controller.run(ex.question, ex.answer)
                            obs = controller.generator
                            final_nodes = [obs._snapshot(b) for _, b in sorted(obs.registry.items(), key=lambda kv: kv[0])] if hasattr(obs, "registry") else []
                            cls = classify(result, final_nodes, dataset, str(ex.answer), bool(cfg["enable_output_repair"]))
                            md = result.metadata or {}
                            per_example_rows.append(
                                {
                                    "provider": args.provider,
                                    "model": args.model,
                                    "dataset": dataset,
                                    "seed": seed,
                                    "budget": budget,
                                    "example_id": str(ex.example_id),
                                    "method": method,
                                    "runtime_method": runtime,
                                    "group": str(cfg["group"]),
                                    "enable_output_repair": int(bool(cfg["enable_output_repair"])),
                                    "is_correct": int(cls["correct"]),
                                    "failure_type": cls["failure_type"],
                                    "absent_from_tree": int(cls["absent_from_tree"]),
                                    "present_not_selected": int(cls["present_not_selected"]),
                                    "output_layer_mismatch": int(cls["output_layer_mismatch"]),
                                    "rescue_applied": int(cls["rescue_applied"]),
                                    "actions_used": int(result.actions_used),
                                    "expansions": int(result.expansions),
                                    "verifications": int(result.verifications),
                                    "budget_exhausted": int(bool(result.budget_exhausted)),
                                    "repeated_same_family_expansion_count": int(md.get("repeated_same_family_expansion_count", 0)),
                                    "repeated_same_family_expansion_rate": float(md.get("repeated_same_family_expansion_rate", 0.0)),
                                    "max_consecutive_same_family_expands": int(md.get("max_consecutive_same_family_expands", 0)),
                                    "max_family_expansion_share": float(md.get("max_family_expansion_share", 0.0)),
                                    "oracle_gap": float(md.get("oracle_gap", 0.0)),
                                    "oracle_regret": float(md.get("oracle_regret", 0.0)),
                                }
                            )
                        except Exception as exc:  # noqa: BLE001
                            error_rows.append(
                                {
                                    "dataset": dataset,
                                    "seed": seed,
                                    "budget": budget,
                                    "example_id": ex.example_id,
                                    "method": method,
                                    "runtime": runtime,
                                    "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                                }
                            )

    write_csv(out_dir / "per_example_rows.csv", per_example_rows)
    write_csv(out_dir / "retry_error_log.csv", error_rows)

    by_method = defaultdict(list)
    by_dataset = defaultdict(list)
    by_budget = defaultdict(list)
    by_seed = defaultdict(list)
    for r in per_example_rows:
        by_method[r["method"]].append(r)
        by_dataset[(r["dataset"], r["method"])].append(r)
        by_budget[(r["budget"], r["method"])].append(r)
        by_seed[(r["seed"], r["method"])].append(r)

    def summarize(rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        return {
            **extra,
            "n": len(rows),
            "accuracy": mean([float(x["is_correct"]) for x in rows]),
            "absent_from_tree_rate": mean([float(x["absent_from_tree"]) for x in rows]),
            "present_not_selected_rate": mean([float(x["present_not_selected"]) for x in rows]),
            "output_layer_mismatch_rate": mean([float(x["output_layer_mismatch"]) for x in rows]),
            "rescue_applied_rate": mean([float(x["rescue_applied"]) for x in rows]),
            "avg_actions": mean([float(x["actions_used"]) for x in rows]),
            "avg_expansions": mean([float(x["expansions"]) for x in rows]),
            "avg_verifications": mean([float(x["verifications"]) for x in rows]),
        }

    aggregate_summary = [summarize(rows, {"method": m, "group": METHODS[m]["group"]}) for m, rows in sorted(by_method.items())]
    per_dataset_summary = [summarize(rows, {"dataset": d, "method": m}) for (d, m), rows in sorted(by_dataset.items())]
    per_budget_summary = [summarize(rows, {"budget": b, "method": m}) for (b, m), rows in sorted(by_budget.items())]
    seed_summary = [summarize(rows, {"seed": s, "method": m}) for (s, m), rows in sorted(by_seed.items())]

    write_csv(out_dir / "aggregate_summary.csv", aggregate_summary)
    write_csv(out_dir / "per_dataset_summary.csv", per_dataset_summary)
    write_csv(out_dir / "per_budget_summary.csv", per_budget_summary)
    write_csv(out_dir / "seed_summary.csv", seed_summary)

    fail_rows = [r for r in per_example_rows if int(r["is_correct"]) == 0]
    failure_decomposition: list[dict[str, Any]] = []
    for m, rows in sorted(defaultdict(list, ((k, [x for x in fail_rows if x["method"] == k]) for k in {x['method'] for x in fail_rows})).items()):
        c = Counter(x["failure_type"] for x in rows)
        n = max(1, len(rows))
        failure_decomposition.append(
            {
                "method": m,
                "n_failures": len(rows),
                "absent_from_tree_share": c.get("absent_from_tree", 0) / n,
                "present_not_selected_share": c.get("present_not_selected", 0) / n,
                "output_layer_mismatch_share": c.get("output_layer_mismatch", 0) / n,
            }
        )
    write_csv(out_dir / "failure_decomposition.csv", failure_decomposition)

    anti_rows = [
        {
            "method": m,
            "n": len(rows),
            "repeat_event_rate": mean([1.0 if float(r["repeated_same_family_expansion_count"]) > 0 else 0.0 for r in rows]),
            "repeat_count_mean": mean([float(r["repeated_same_family_expansion_count"]) for r in rows]),
            "repeat_rate_mean": mean([float(r["repeated_same_family_expansion_rate"]) for r in rows]),
            "max_consecutive_same_family_mean": mean([float(r["max_consecutive_same_family_expands"]) for r in rows]),
            "max_family_expansion_share_mean": mean([float(r["max_family_expansion_share"]) for r in rows]),
        }
        for m, rows in sorted(by_method.items())
    ]
    write_csv(out_dir / "anti_collapse_diagnostics.csv", anti_rows)

    repair_impact = []
    full = [r for r in aggregate_summary if r["method"] == "strict_f3"]
    no_rep = [r for r in aggregate_summary if r["method"] == "strict_f3_no_output_repair"]
    if full and no_rep:
        repair_impact.append(
            {
                "method_pair": "strict_f3_vs_strict_f3_no_output_repair",
                "accuracy_with_repair": float(full[0]["accuracy"]),
                "accuracy_without_repair": float(no_rep[0]["accuracy"]),
                "delta": float(full[0]["accuracy"]) - float(no_rep[0]["accuracy"]),
            }
        )
    write_csv(out_dir / "repair_impact_summary.csv", repair_impact)

    methods_compared = [{"method": m, **METHODS[m]} for m in methods]
    (out_dir / "methods_compared.json").write_text(json.dumps(methods_compared, indent=2) + "\n", encoding="utf-8")
    (out_dir / "providers_and_models.json").write_text(
        json.dumps({"providers": [{"provider": args.provider, "model": args.model}]}, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "datasets_compared.json").write_text(
        json.dumps({"datasets": datasets, "subset_size": args.subset_size, "seeds": seeds, "budgets": budgets}, indent=2) + "\n",
        encoding="utf-8",
    )

    assumptions = [
        "Canonical bounded real-model validation using APIBranchGenerator.",
        f"Provider/model: {args.provider}/{args.model}.",
        "Evaluation correctness uses choose_repair_answer + canonicalize_answer as manuscript-facing contract.",
        "Failure decomposition categories: absent_from_tree, present_not_selected, output_layer_mismatch.",
        "Errors are logged in retry_error_log.csv and excluded from accuracy denominators.",
    ]
    (out_dir / "commands_assumptions_caveats.md").write_text(
        "\n".join(["# Commands / assumptions / caveats", "", "## Command", f"- python scripts/run_canonical_real_model_validation.py --timestamp {args.timestamp}", "", "## Assumptions + caveats", *[f"- {x}" for x in assumptions]])
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "artifact_family": "canonical_real_model_validation",
        "timestamp": args.timestamp,
        "provider": args.provider,
        "model": args.model,
        "datasets": datasets,
        "subset_size": args.subset_size,
        "seeds": seeds,
        "budgets": budgets,
        "files": [
            "manifest.json",
            "methods_compared.json",
            "providers_and_models.json",
            "datasets_compared.json",
            "aggregate_summary.csv",
            "per_dataset_summary.csv",
            "per_budget_summary.csv",
            "seed_summary.csv",
            "failure_decomposition.csv",
            "anti_collapse_diagnostics.csv",
            "repair_impact_summary.csv",
            "commands_assumptions_caveats.md",
            "summary.md",
            "per_example_rows.csv",
            "retry_error_log.csv",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    top = sorted(aggregate_summary, key=lambda x: float(x["accuracy"]), reverse=True)
    summary_lines = [
        "# Canonical bounded real-model validation summary",
        "",
        f"- Provider/model: `{args.provider}/{args.model}`",
        f"- Surface size: {len(per_example_rows)} evaluated method-example rows.",
        f"- Logged API/runtime errors: {len(error_rows)}",
        "",
        "## Method ranking (mean accuracy)",
    ]
    summary_lines.extend([f"- {row['method']}: {float(row['accuracy']):.4f}" for row in top])
    (out_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / f"docs/CANONICAL_REAL_MODEL_VALIDATION_{args.timestamp}.md"
    doc_lines = [
        "# Canonical real-model validation (bounded, manuscript-facing)",
        "",
        "## Real-model audit snapshot",
        "- Existing repository evidence includes bounded real-model passes (OpenAI/Cohere/Gemini/Groq paths), but no single canonical paper-facing package with strict_f3 + internal neighbor + simple baseline + fair external baseline on one explicit contract.",
        "- This run closes that packaging gap with one explicit bounded contract and full provenance.",
        "",
        "## Exact contract",
        f"- Provider/model: `{args.provider}/{args.model}`",
        f"- Datasets: {datasets}",
        f"- Subset size per dataset per seed: {args.subset_size}",
        f"- Seeds: {seeds}",
        f"- Budgets: {budgets}",
        f"- Methods: {methods}",
        "- Prompting/decoding: APIBranchGenerator JSON protocols, temperature/max token limits set in command.",
        "- Answer extraction/grading: deterministic choose_repair_answer + canonicalize_answer.",
        "- Retry/error handling: provider-level retries inside APIBranchGenerator, per-example failures logged to retry_error_log.csv.",
        "",
        "## Main bounded findings",
    ]
    for row in top:
        doc_lines.append(f"- `{row['method']}` accuracy={float(row['accuracy']):.4f}, absent_from_tree_rate={float(row['absent_from_tree_rate']):.4f}, output_layer_mismatch_rate={float(row['output_layer_mismatch_rate']):.4f}")
    if repair_impact:
        rp = repair_impact[0]
        doc_lines.append(f"- Repair delta (strict_f3): {float(rp['delta']):+.4f} (with_repair={float(rp['accuracy_with_repair']):.4f}, without={float(rp['accuracy_without_repair']):.4f})")
    doc_lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "- This is bounded validation (single backbone, small subset) and should be treated as directional evidence.",
            "- Broader decisive claims still require larger multi-backbone, larger-sample replications.",
            "",
            f"## Artifact directory\n- `outputs/canonical_real_model_validation_{args.timestamp}/`",
        ]
    )
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
