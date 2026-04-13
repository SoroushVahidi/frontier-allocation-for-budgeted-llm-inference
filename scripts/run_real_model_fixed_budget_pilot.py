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
    return None


def _provider_model(provider: str, args: argparse.Namespace) -> str:
    return args.openai_model if provider == "openai" else args.gemini_model


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
        "models": {"openai": args.openai_model, "gemini": args.gemini_model},
        "learned_scorer": {
            "requested_path": args.learned_scorer_path,
            "resolved_path": str(learned_model_path) if learned_model_path else None,
            "status": learned_model_status,
        },
        "api_key_presence": {
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
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
                summary_rows.append({**combo_meta, "method": "<skipped>", "status": "skipped_missing_key"})
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
                        "method_notes": method["notes"],
                    }
                )

    (run_dir / "results.json").write_text(
        json.dumps({"manifest": manifest, "summary": summary_rows, "rows": detailed_rows}, indent=2),
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
                f"budget_exhaustion={row['budget_exhaustion_rate']:.2f}"
            )
    else:
        note_lines.append("- No successful provider/dataset/method runs were recorded.")

    failed_rows = [r for r in summary_rows if r.get("status") != "ok"]
    if failed_rows:
        note_lines.extend(["", "## Skipped/failed combinations"])
        for row in failed_rows:
            note_lines.append(
                f"- {row.get('provider')} | {row.get('dataset')} | {row.get('method')}: "
                f"status={row.get('status')}, error={row.get('error', 'n/a')}"
            )

    if ok_rows:
        accuracies = [float(r["accuracy"]) for r in ok_rows if isinstance(r.get("accuracy"), (int, float))]
        note_lines.extend(["", "## Pilot signal"])
        note_lines.append(
            "- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims."
        )
        if accuracies:
            note_lines.append(f"- Mean method accuracy across successful rows: {statistics.mean(accuracies):.3f}")

    (run_dir / "note.md").write_text("\n".join(note_lines) + "\n", encoding="utf-8")
    print(str(run_dir))


if __name__ == "__main__":
    random.seed(0)
    main()
