#!/usr/bin/env python3
"""Run a small real-model fixed-budget pilot on supported HF datasets."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import re
import statistics
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator
from experiments.controllers import AdaptiveController, BestOfNController
from experiments.data import PilotExample, extract_final_answer
from experiments.hf_datasets import resolve_dataset_spec, sample_hf_examples
from experiments.scoring import (
    LearnedBranchScorerV3,
    RelativeRankBranchScorer,
    ScoreConfig,
    ScorePlusProgressBranchScorer,
    SimpleBranchScorer,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-model fixed-budget branch-allocation pilot")
    parser.add_argument("--providers", default="openai,gemini", help="Comma-separated providers")
    parser.add_argument(
        "--datasets",
        default="openai/gsm8k,EleutherAI/hendrycks_math",
        help="Comma-separated HF datasets",
    )
    parser.add_argument("--subset-size", type=int, default=3, help="Examples per provider/dataset")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-actions", type=int, default=6, help="Fixed budget per method/problem")
    parser.add_argument("--max-branches", type=int, default=3)
    parser.add_argument("--high-threshold", type=float, default=0.72)
    parser.add_argument("--low-threshold", type=float, default=0.42)
    parser.add_argument("--openai-model", default="gpt-4.1-mini")
    parser.add_argument("--gemini-model", default="gemini-2.0-flash")
    parser.add_argument("--groq-model", default="llama-3.1-8b-instant")
    parser.add_argument("--output-dir", default="output/real_model_fixed_budget_pilot")
    parser.add_argument(
        "--learned-scorer-path",
        default="outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json",
        help="Preferred learned scorer path. Falls back to sibling versions if available.",
    )
    parser.add_argument("--include-best-of-n", action="store_true", help="Include simple best-of-n baseline")
    parser.add_argument("--best-of-n-candidates", type=int, default=2)
    return parser.parse_args()


def _provider_api_key(provider: str) -> str | None:
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    if provider == "gemini":
        return os.getenv("GEMINI_API_KEY")
    if provider == "groq":
        return os.getenv("GROQ_API_KEY")
    return None


def _provider_model(provider: str, args: argparse.Namespace) -> str:
    if provider == "openai":
        return args.openai_model
    if provider == "gemini":
        return args.gemini_model
    if provider == "groq":
        return args.groq_model
    raise ValueError(f"Unsupported provider: {provider}")


def _resolve_learned_model_path(preferred: Path) -> tuple[Path | None, str]:
    candidates = [
        preferred,
        preferred.with_name("adaptive_learned_branch_score_v6.json"),
        preferred.with_name("adaptive_learned_branch_score_v5.json"),
        preferred.with_name("adaptive_learned_branch_score_v4.json"),
        preferred.with_name("adaptive_learned_branch_score_v3.json"),
    ]
    for path in candidates:
        if path.exists():
            return path, "loaded"
    return None, "missing"


def _summarize(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    if n == 0:
        return {
            "n_examples": 0,
            "accuracy": 0.0,
            "avg_actions": 0.0,
            "avg_expansions": 0.0,
            "avg_verifications": 0.0,
            "avg_surviving_branches": 0.0,
            "budget_exhaustion_rate": 0.0,
        }

    return {
        "n_examples": n,
        "accuracy": sum(1 for r in rows if r["is_correct"]) / n,
        "avg_actions": sum(r["actions_used"] for r in rows) / n,
        "avg_expansions": sum(r["expansions"] for r in rows) / n,
        "avg_verifications": sum(r["verifications"] for r in rows) / n,
        "avg_surviving_branches": sum(r["avg_surviving_branches"] for r in rows) / n,
        "budget_exhaustion_rate": sum(1 for r in rows if r["budget_exhausted"]) / n,
    }


def _action_trace(row: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        trace = metadata.get("action_trace")
        if isinstance(trace, list):
            return [t for t in trace if isinstance(t, dict)]
    return []


def _extract_failure_reason(message: str) -> str:
    lowered = message.lower()
    if "401" in lowered or "unauthorized" in lowered or "invalid api key" in lowered:
        return "auth_error"
    if "429" in lowered or "rate" in lowered or "quota" in lowered:
        return "quota_or_rate_limit"
    if "timeout" in lowered:
        return "timeout"
    if "dataset" in lowered:
        return "dataset_failure"
    if "http" in lowered:
        return "http_error_other"
    return "unknown_error"


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _row_diagnostics(row: dict[str, Any]) -> dict[str, Any]:
    trace = _action_trace(row)
    scores = [float(t.get("score_after", 0.0)) for t in trace if isinstance(t.get("score_after"), (int, float))]
    branch_ids = [str(t["branch_id"]) for t in trace if "branch_id" in t]
    unique_branch_ids = set(branch_ids)
    metadata = row.get("metadata", {})
    configured_max_branches = 1
    if isinstance(metadata, dict) and isinstance(metadata.get("max_branches"), int):
        configured_max_branches = max(1, int(metadata["max_branches"]))
    diversity = len(unique_branch_ids) / configured_max_branches
    collapse = len(unique_branch_ids) <= 1 and len(trace) > 0
    variance = statistics.pvariance(scores) if len(scores) > 1 else 0.0
    budgets = [int(t.get("remaining_budget", 0)) for t in trace if isinstance(t.get("remaining_budget"), (int, float))]
    budget_used_over_time = [row["actions_used"] - b for b in budgets] if budgets else []
    budget_usage_monotonic = all(
        budget_used_over_time[i] <= budget_used_over_time[i + 1] for i in range(len(budget_used_over_time) - 1)
    )

    steps = [str(s) for s in metadata.get("steps", []) if isinstance(s, str)] if isinstance(metadata, dict) else []
    if not steps:
        steps = [str(t.get("predicted_answer", "")) for t in trace]
    token_sets = [s for s in (_tokenize(step) for step in steps) if s]
    jaccards: list[float] = []
    for i in range(len(token_sets)):
        for j in range(i + 1, len(token_sets)):
            inter = token_sets[i] & token_sets[j]
            union = token_sets[i] | token_sets[j]
            if union:
                jaccards.append(len(inter) / len(union))
    redundancy_proxy = statistics.mean(jaccards) if jaccards else 0.0

    return {
        "branch_diversity": round(diversity, 4),
        "branch_collapse": collapse,
        "branch_score_variance": round(variance, 6),
        "budget_usage_over_time": budget_used_over_time,
        "budget_usage_monotonic": budget_usage_monotonic,
        "semantic_redundancy_proxy": round(redundancy_proxy, 6),
        "n_trace_events": len(trace),
        "n_unique_branches_touched": len(unique_branch_ids),
    }


def _collect_score_samples(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    provider_scores: dict[str, list[float]] = {}
    for row in rows:
        provider = str(row.get("provider", "unknown"))
        trace = _action_trace(row)
        for item in trace:
            val = item.get("score_after")
            if isinstance(val, (int, float)):
                provider_scores.setdefault(provider, []).append(float(val))
    stats: dict[str, dict[str, float]] = {}
    for provider, values in provider_scores.items():
        if not values:
            continue
        mean = statistics.mean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        stats[provider] = {"mean": mean, "std": std if std > 1e-8 else 1.0, "n_samples": len(values)}
    return stats


def _attach_calibrated_scores(rows: list[dict[str, Any]], provider_stats: dict[str, dict[str, float]]) -> None:
    for row in rows:
        provider = str(row.get("provider", "unknown"))
        stats = provider_stats.get(provider)
        trace = _action_trace(row)
        if not stats or not trace:
            row["calibration"] = {"provider": provider, "status": "unavailable"}
            continue

        zscores: list[float] = []
        for item in trace:
            val = item.get("score_after")
            if isinstance(val, (int, float)):
                zscores.append((float(val) - stats["mean"]) / stats["std"])

        row["calibration"] = {
            "provider": provider,
            "status": "ok" if zscores else "no_score_samples",
            "provider_mean": round(stats["mean"], 6),
            "provider_std": round(stats["std"], 6),
            "avg_zscore": round(statistics.mean(zscores), 6) if zscores else None,
        }


def _method_specs(
    provider: str,
    args: argparse.Namespace,
    learned_model_path: Path | None,
    learned_model_status: str,
) -> list[dict[str, Any]]:
    key = _provider_api_key(provider)

    def make_generator() -> APIBranchGenerator:
        return APIBranchGenerator(
            provider=provider,
            api_key=key,
            model=_provider_model(provider, args),
            temperature=0.2,
            max_tokens=180,
            timeout_seconds=45,
        )

    methods: list[dict[str, Any]] = [
        {
            "name": "adaptive_relative_rank",
            "controller": lambda: AdaptiveController(
                make_generator(),
                RelativeRankBranchScorer(),
                max_actions_per_problem=args.max_actions,
                high_threshold=args.high_threshold,
                low_threshold=args.low_threshold,
                max_branches=args.max_branches,
                allow_verify=True,
                min_expansions_before_prune=0,
                method_name="adaptive_relative_rank",
            ),
            "notes": {"scorer": "RelativeRankBranchScorer"},
        },
        {
            "name": "adaptive_score_plus_progress",
            "controller": lambda: AdaptiveController(
                make_generator(),
                ScorePlusProgressBranchScorer(),
                max_actions_per_problem=args.max_actions,
                high_threshold=args.high_threshold,
                low_threshold=args.low_threshold,
                max_branches=args.max_branches,
                allow_verify=True,
                min_expansions_before_prune=0,
                method_name="adaptive_score_plus_progress",
            ),
            "notes": {"scorer": "ScorePlusProgressBranchScorer"},
        },
    ]

    learned_scorer = None
    learned_note: dict[str, Any] = {
        "requested_path": str(args.learned_scorer_path),
        "resolved_path": str(learned_model_path) if learned_model_path else None,
        "status": learned_model_status,
    }
    if learned_model_path is not None:
        learned_scorer = LearnedBranchScorerV3(learned_model_path)
        learned_note["fallback_used"] = False
    else:
        learned_scorer = SimpleBranchScorer(ScoreConfig())
        learned_note["fallback_used"] = True
        learned_note["fallback_reason"] = "learned scorer file missing; used SimpleBranchScorer"

    methods.append(
        {
            "name": "adaptive_learned_branch_score_v4",
            "controller": lambda: AdaptiveController(
                make_generator(),
                learned_scorer,
                max_actions_per_problem=args.max_actions,
                high_threshold=args.high_threshold,
                low_threshold=args.low_threshold,
                max_branches=args.max_branches,
                allow_verify=True,
                min_expansions_before_prune=0,
                method_name="adaptive_learned_branch_score_v4",
            ),
            "notes": learned_note,
        }
    )

    if args.include_best_of_n:
        methods.append(
            {
                "name": "best_of_n",
                "controller": lambda: BestOfNController(
                    make_generator(),
                    SimpleBranchScorer(ScoreConfig()),
                    max_actions_per_problem=args.max_actions,
                    n_candidates=args.best_of_n_candidates,
                ),
                "notes": {"n_candidates": args.best_of_n_candidates},
            }
        )

    return methods


def _load_examples(dataset_name: str, subset_size: int, seed: int) -> list[PilotExample]:
    spec = resolve_dataset_spec(dataset_name)
    rows = sample_hf_examples(
        dataset_name=dataset_name,
        pilot_size=subset_size,
        seed=seed,
        split=spec.default_split,
        config_name=spec.default_config,
    )
    return [
        PilotExample(
            example_id=r["example_id"],
            question=r["question"],
            answer=extract_final_answer(r["answer"]),
        )
        for r in rows
    ]


def main() -> None:
    args = parse_args()
    providers = [p.strip().lower() for p in args.providers.split(",") if p.strip()]
    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    learned_model_path, learned_model_status = _resolve_learned_model_path(Path(args.learned_scorer_path))

    detailed_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "providers": providers,
        "datasets": datasets,
        "subset_size": args.subset_size,
        "seed": args.seed,
        "fixed_budget_max_actions": args.max_actions,
        "max_branches": args.max_branches,
        "thresholds": {"high": args.high_threshold, "low": args.low_threshold},
        "models": {"openai": args.openai_model, "gemini": args.gemini_model, "groq": args.groq_model},
        "learned_scorer": {
            "requested_path": args.learned_scorer_path,
            "resolved_path": str(learned_model_path) if learned_model_path else None,
            "status": learned_model_status,
        },
        "api_key_presence": {
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
            "GROQ_API_KEY": bool(os.getenv("GROQ_API_KEY")),
        },
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for provider in providers:
        key_present = bool(_provider_api_key(provider))
        for dataset_name in datasets:
            combo_meta = {
                "provider": provider,
                "dataset": dataset_name,
                "provider_model": _provider_model(provider, args),
                "subset_size": args.subset_size,
                "key_present": key_present,
            }
            if not key_present:
                summary_rows.append(
                    {
                        **combo_meta,
                        "method": "<skipped>",
                        "status": "skipped_missing_key",
                        "failure_reason": f"missing_{provider}_api_key",
                    }
                )
                continue

            try:
                examples = _load_examples(dataset_name, args.subset_size, args.seed)
            except Exception as exc:
                summary_rows.append(
                    {
                        **combo_meta,
                        "method": "<dataset_load_error>",
                        "status": "dataset_load_failed",
                        "error": f"{type(exc).__name__}: {exc}",
                        "failure_reason": _extract_failure_reason(f"{type(exc).__name__}: {exc}"),
                    }
                )
                continue

            method_specs = _method_specs(provider, args, learned_model_path, learned_model_status)
            for method in method_specs:
                controller = method["controller"]()
                method_name = method["name"]
                method_rows: list[dict[str, Any]] = []
                method_error: str | None = None
                for ex in examples:
                    try:
                        result = controller.run(ex.question, ex.answer)
                    except Exception as exc:
                        method_error = f"{type(exc).__name__}: {exc}"
                        break
                    row = {
                        **combo_meta,
                        "example_id": ex.example_id,
                        "method": method_name,
                        "gold_answer": ex.answer,
                        "prediction": result.prediction,
                        "is_correct": result.is_correct,
                        "actions_used": result.actions_used,
                        "expansions": result.expansions,
                        "verifications": result.verifications,
                        "avg_surviving_branches": result.avg_surviving_branches,
                        "budget_exhausted": result.budget_exhausted,
                        "metadata": result.metadata,
                        "method_notes": method["notes"],
                    }
                    method_rows.append(row)
                    detailed_rows.append(row)

                if method_error is not None:
                    summary_rows.append(
                        {
                            **combo_meta,
                            "method": method_name,
                            "status": "method_failed",
                            "error": method_error,
                            "failure_reason": _extract_failure_reason(method_error),
                            "method_notes": method["notes"],
                        }
                    )
                    continue

                method_summary = _summarize(method_rows)
                summary_rows.append(
                    {
                        **combo_meta,
                        "method": method_name,
                        "status": "ok",
                        **method_summary,
                        "failure_reason": "",
                        "method_notes": method["notes"],
                    }
                )

    for row in detailed_rows:
        diag = _row_diagnostics(row)
        row["diagnostics"] = diag
        meta = row.get("metadata", {})
        max_branches = meta.get("max_branches") if isinstance(meta, dict) else None
        row["max_branches"] = max_branches if isinstance(max_branches, int) else None

    calibration_stats = _collect_score_samples(detailed_rows)
    _attach_calibrated_scores(detailed_rows, calibration_stats)

    for summary_row in summary_rows:
        if summary_row.get("status") != "ok":
            continue
        matched = [
            r
            for r in detailed_rows
            if r.get("provider") == summary_row.get("provider")
            and r.get("dataset") == summary_row.get("dataset")
            and r.get("method") == summary_row.get("method")
            and isinstance(r.get("calibration"), dict)
            and isinstance(r["calibration"].get("avg_zscore"), (int, float))
        ]
        if matched:
            summary_row["avg_calibrated_zscore"] = round(
                statistics.mean(float(r["calibration"]["avg_zscore"]) for r in matched), 6
            )

    (run_dir / "results.json").write_text(
        json.dumps(
            {
                "manifest": manifest,
                "calibration_stats": calibration_stats,
                "summary": summary_rows,
                "rows": detailed_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    csv_path = run_dir / "summary.csv"
    csv_fields = [
        "provider",
        "dataset",
        "provider_model",
        "subset_size",
        "method",
        "status",
        "n_examples",
        "accuracy",
        "avg_actions",
        "avg_expansions",
        "avg_verifications",
        "avg_surviving_branches",
        "budget_exhaustion_rate",
        "avg_calibrated_zscore",
        "failure_reason",
        "error",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow({k: row.get(k) for k in csv_fields})

    note_lines = [
        "# Real-model fixed-budget pilot note",
        "",
        f"- Run id: `{run_id}`",
        f"- Providers: {', '.join(providers)}",
        f"- Datasets: {', '.join(datasets)}",
        f"- Subset size per provider/dataset: {args.subset_size}",
        f"- Fixed budget (max actions/problem): {args.max_actions}",
        f"- Learned scorer path preference: `{args.learned_scorer_path}`",
        "",
        "## Provider/dataset summary",
    ]

    ok_rows = [r for r in summary_rows if r.get("status") == "ok"]
    if ok_rows:
        for row in ok_rows:
            note_lines.append(
                f"- {row['provider']} | {row['dataset']} | {row['method']}: "
                f"acc={row['accuracy']:.3f}, avg_actions={row['avg_actions']:.2f}, "
                f"budget_exhaustion={row['budget_exhaustion_rate']:.2f}, "
                f"avg_calibrated_z={row.get('avg_calibrated_zscore', 'n/a')}"
            )
    else:
        note_lines.append("- No successful provider/dataset/method runs were recorded.")

    failed_rows = [r for r in summary_rows if r.get("status") != "ok"]
    if failed_rows:
        note_lines.extend(["", "## Skipped/failed combinations"])
        for row in failed_rows:
            note_lines.append(
                f"- {row.get('provider')} | {row.get('dataset')} | {row.get('method')}: "
                f"status={row.get('status')}, reason={row.get('failure_reason', 'n/a')}, error={row.get('error', 'n/a')}"
            )

    if ok_rows:
        accuracies = [float(r["accuracy"]) for r in ok_rows if isinstance(r.get("accuracy"), (int, float))]
        note_lines.extend(["", "## Pilot signal"])
        note_lines.append(
            "- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims."
        )
        if accuracies:
            note_lines.append(f"- Mean method accuracy across successful rows: {statistics.mean(accuracies):.3f}")

    if calibration_stats:
        note_lines.extend(["", "## Calibration stats (provider-specific mean/std)"])
        for provider, stats in calibration_stats.items():
            note_lines.append(
                f"- {provider}: mean={stats['mean']:.4f}, std={stats['std']:.4f}, n_score_samples={int(stats['n_samples'])}"
            )

    ranking_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in ok_rows:
        ranking_groups.setdefault((str(row["provider"]), str(row["dataset"])), []).append(row)
    if ranking_groups:
        note_lines.extend(["", "## Ranking comparison (raw accuracy vs calibrated z-score)"])
        for (provider, dataset), rows in ranking_groups.items():
            raw_rank = sorted(rows, key=lambda r: (float(r["accuracy"]), -float(r["avg_actions"])), reverse=True)
            cal_rows = [r for r in rows if isinstance(r.get("avg_calibrated_zscore"), (int, float))]
            cal_rank = sorted(cal_rows, key=lambda r: float(r["avg_calibrated_zscore"]), reverse=True)
            raw_top = raw_rank[0]["method"] if raw_rank else "n/a"
            cal_top = cal_rank[0]["method"] if cal_rank else "n/a"
            changed = raw_top != cal_top and cal_top != "n/a"
            note_lines.append(
                f"- {provider} | {dataset}: raw_top={raw_top}, calibrated_top={cal_top}, ranking_changed={changed}"
            )

    note_lines.extend(
        [
            "",
            "## Diagnostics included",
            "- branch diversity / collapse from unique branch ids touched per example",
            "- branch-score variance across action-trace score updates",
            "- budget usage over time from remaining_budget in action trace",
            "- semantic redundancy proxy as mean token-overlap (Jaccard) between recorded steps/predictions",
            "- provider/method failure reasons via lightweight error categorization",
        ]
    )

    (run_dir / "note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")
    print(str(run_dir))


if __name__ == "__main__":
    random.seed(0)
    main()
