#!/usr/bin/env python3
"""PRM-style partial-branch scoring audit (new-paper track).

Implements a lightweight, auditable approximation of:
- ThinkPRM-style partial process scoring,
- early-rejection partial PRM mechanics.

No true PRM training is performed here.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import statistics
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (  # noqa: E402
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
    resolve_api_key_for_provider,
)

METHODS = [
    "adaptive_min_expand_1",
    "verifier_guided_search",
    "adaptive_prm_partial",
    "adaptive_prm_partial_early_reject",
    "verifier_guided_search_prm",
    "verifier_guided_search_prm_early_reject",
    "oracle_frontier_upper_bound",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="New-paper PRM branch scoring audit")
    p.add_argument("--datasets", default="openai/gsm8k,EleutherAI/hendrycks_math")
    p.add_argument("--subset-size", type=int, default=24)
    p.add_argument("--seed", type=int, default=41)
    p.add_argument("--budgets", default="6,8")
    p.add_argument("--adaptive-min-expand-grid", default="1")
    p.add_argument("--api-backend", choices=("simulator", "openai", "groq", "gemini"), default="simulator")
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    p.add_argument("--prm-early-reject-threshold", type=float, default=0.25)
    p.add_argument("--prm-early-reject-min-expansions", type=int, default=2)
    p.add_argument("--output-dir", default="outputs/new_paper/prm_branch_scoring")
    return p.parse_args()


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_str_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _oracle_accuracy(rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    if not by_ex:
        return 0.0
    return sum(1 for r in by_ex.values() if any(bool(x["is_correct"]) for x in r)) / len(by_ex)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    args = parse_args()
    use_remote = args.api_backend != "simulator"
    if use_remote and not resolve_api_key_for_provider(args.api_backend):
        raise SystemExit(f"Missing API key for backend={args.api_backend}")

    budgets = _parse_int_list(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    method_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    diag_rows: list[dict[str, Any]] = []
    reject_rows: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []

    for i, ds in enumerate(_parse_str_list(args.datasets)):
        ds_seed = args.seed + i * 10007
        rng = random.Random(ds_seed)
        examples = load_pilot_examples(ds, args.subset_size, ds_seed)
        print(f"[prm_branch_scoring] dataset={ds} n={len(examples)}", flush=True)

        gen_factory = generator_factory_for_mode(
            use_remote,
            rng,
            args.model,
            args.temperature,
            args.max_output_tokens,
            args.timeout_seconds,
            api_provider=(args.api_backend if use_remote else None),
        )

        for b in budgets:
            try:
                strategies = build_frontier_strategies(
                    gen_factory,
                    b,
                    adaptive_grid,
                    rng,
                    use_openai_api=use_remote,
                    vgs_candidates=args.vgs_candidates,
                    vgs_min_expansions=args.vgs_min_expansions,
                    include_budget_guarded_adaptive=True,
                    include_prm_variants=True,
                    prm_early_reject_threshold=args.prm_early_reject_threshold,
                    prm_early_reject_min_expansions=args.prm_early_reject_min_expansions,
                )
                metrics, rows = evaluate_strategies_on_examples(examples, strategies)
            except Exception as exc:  # noqa: BLE001
                failed.append({"dataset": ds, "budget": str(b), "error": f"{type(exc).__name__}: {exc}"})
                print(f"[prm_branch_scoring] dataset={ds} budget={b} FAILED: {exc}", flush=True)
                continue

            oracle_acc = _oracle_accuracy(rows)
            for m in METHODS:
                if m == "oracle_frontier_upper_bound":
                    method_rows.append(
                        {
                            "dataset": ds,
                            "budget": b,
                            "method": m,
                            "n_examples": len(examples),
                            "accuracy": oracle_acc,
                            "avg_actions": "",
                            "avg_expansions": "",
                            "avg_verifications": "",
                            "budget_exhaustion_rate": "",
                            "oracle_accuracy": oracle_acc,
                            "gap_to_oracle": 0.0,
                        }
                    )
                    continue
                if m not in metrics:
                    continue
                mm = metrics[m]
                method_rows.append(
                    {
                        "dataset": ds,
                        "budget": b,
                        "method": m,
                        "n_examples": int(mm["n_examples"]),
                        "accuracy": float(mm["accuracy"]),
                        "avg_actions": float(mm["avg_actions"]),
                        "avg_expansions": float(mm["avg_expansions"]),
                        "avg_verifications": float(mm["avg_verifications"]),
                        "budget_exhaustion_rate": float(mm["budget_exhaustion_rate"]),
                        "oracle_accuracy": oracle_acc,
                        "gap_to_oracle": oracle_acc - float(mm["accuracy"]),
                    }
                )

            for row in rows:
                meta = row.get("metadata") or {}
                mname = str(row["strategy"])
                if mname in {"adaptive_prm_partial", "adaptive_prm_partial_early_reject"}:
                    for tr in meta.get("action_trace") or []:
                        if tr.get("partial_score") is None:
                            continue
                        diag_rows.append(
                            {
                                "dataset": ds,
                                "budget": b,
                                "method": mname,
                                "example_id": row["example_id"],
                                "branch_id": tr.get("branch_id"),
                                "action": tr.get("action"),
                                "partial_score": tr.get("partial_score"),
                                "fallback_score": tr.get("fallback_score"),
                                "score_source": tr.get("score_source"),
                                "score_stage": tr.get("score_stage"),
                                "early_reject_flag": int(bool(tr.get("early_reject_flag"))),
                                "forced_expand_reason": tr.get("forced_expand_reason"),
                                "remaining_budget": tr.get("remaining_budget"),
                            }
                        )
                if mname in {"verifier_guided_search_prm", "verifier_guided_search_prm_early_reject"}:
                    ps = meta.get("partial_branch_scores") or []
                    for idx, s in enumerate(ps):
                        diag_rows.append(
                            {
                                "dataset": ds,
                                "budget": b,
                                "method": mname,
                                "example_id": row["example_id"],
                                "branch_id": f"candidate_{idx}",
                                "action": "candidate_score",
                                "partial_score": s,
                                "fallback_score": "",
                                "score_source": meta.get("partial_score_source"),
                                "score_stage": "vgs_candidate",
                                "early_reject_flag": "",
                                "forced_expand_reason": "",
                                "remaining_budget": "",
                            }
                        )

            # early rejection summary rows by method
            for mname in ["adaptive_prm_partial", "adaptive_prm_partial_early_reject", "verifier_guided_search_prm", "verifier_guided_search_prm_early_reject"]:
                subset = [r for r in rows if str(r["strategy"]) == mname]
                if not subset:
                    continue
                early_flags = 0
                traces = 0
                for r in subset:
                    meta = r.get("metadata") or {}
                    for tr in meta.get("action_trace") or []:
                        traces += 1
                        early_flags += int(bool(tr.get("early_reject_flag")))
                    early_flags += int(meta.get("prm_early_rejected_candidates", 0))
                reject_rows.append(
                    {
                        "dataset": ds,
                        "budget": b,
                        "method": mname,
                        "n_examples": len(subset),
                        "early_rejection_events": early_flags,
                        "trace_events": traces,
                        "early_rejection_rate_over_trace": (early_flags / traces) if traces else 0.0,
                        "mean_actions": statistics.mean(float(r["actions_used"]) for r in subset),
                        "mean_accuracy": statistics.mean(1.0 if r["is_correct"] else 0.0 for r in subset),
                    }
                )

    # oracle gap summary
    for r in method_rows:
        gap_rows.append(
            {
                "dataset": r["dataset"],
                "budget": r["budget"],
                "method": r["method"],
                "oracle_accuracy": r["oracle_accuracy"],
                "method_accuracy": r["accuracy"],
                "gap_to_oracle": r["gap_to_oracle"],
                "avg_actions": r["avg_actions"],
                "budget_exhaustion_rate": r["budget_exhaustion_rate"],
            }
        )

    _write_csv(run_dir / "method_metrics.csv", method_rows)
    _write_csv(run_dir / "branch_score_diagnostics.csv", diag_rows)
    _write_csv(run_dir / "early_rejection_summary.csv", reject_rows)
    _write_csv(run_dir / "oracle_gap_summary.csv", gap_rows)

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "track": "new-paper",
        "datasets": _parse_str_list(args.datasets),
        "subset_size": args.subset_size,
        "seed": args.seed,
        "budgets": budgets,
        "adaptive_min_expand_grid": adaptive_grid,
        "api_backend": args.api_backend,
        "model": args.model,
        "include_prm_variants": True,
        "prm_approximation_honesty": {
            "is_true_trained_prm": False,
            "partial_scorer": "heuristic proxy over branch score/depth/step-structure/stagnation",
            "early_rejection": "threshold gate after minimum expansion floor",
        },
        "failed": failed,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # interpretation
    lines = [
        "# PRM branch scoring interpretation",
        "",
        "This run uses a lightweight PRM-style proxy scorer, not a trained process reward model.",
        "",
        "## Questions",
    ]

    def _find(ds: str, b: int, method: str) -> dict[str, Any] | None:
        return next((r for r in method_rows if r["dataset"] == ds and int(r["budget"]) == b and r["method"] == method), None)

    for ds in sorted({str(r["dataset"]) for r in method_rows}):
        lines.append(f"### {ds}")
        for b in budgets:
            base = _find(ds, b, "adaptive_min_expand_1")
            prm = _find(ds, b, "adaptive_prm_partial")
            prm_er = _find(ds, b, "adaptive_prm_partial_early_reject")
            vgs = _find(ds, b, "verifier_guided_search")
            vgs_prm = _find(ds, b, "verifier_guided_search_prm")
            vgs_prm_er = _find(ds, b, "verifier_guided_search_prm_early_reject")
            if not base:
                continue
            lines.append(f"- Budget {b}:")
            if prm:
                lines.append(
                    f"  - PRM partial scoring gap delta vs base adaptive: {float(base['gap_to_oracle']) - float(prm['gap_to_oracle']):+.4f}."
                )
            if prm_er and prm:
                lines.append(
                    f"  - Early rejection compute delta (adaptive): actions {float(prm_er['avg_actions']) - float(prm['avg_actions']):+.3f}; accuracy delta {float(prm_er['accuracy']) - float(prm['accuracy']):+.3f}."
                )
            if vgs and vgs_prm:
                lines.append(
                    f"  - PRM partial scoring head-to-head vs VGS: acc delta {float(vgs_prm['accuracy']) - float(vgs['accuracy']):+.3f}."
                )
            if vgs_prm and vgs_prm_er:
                lines.append(
                    f"  - VGS early rejection compute delta: actions {float(vgs_prm_er['avg_actions']) - float(vgs_prm['avg_actions']):+.3f}; accuracy delta {float(vgs_prm_er['accuracy']) - float(vgs_prm['accuracy']):+.3f}."
                )
        lines.append("")

    lines.extend(
        [
            "## Verdict",
            "- Treat this as mechanism-level evidence unless trends are stable across datasets/budgets and larger subsets.",
            "- If oracle-gap reductions are small or inconsistent, the next step should be stronger learned PRM targets rather than more routing complexity.",
        ]
    )
    (run_dir / "interpretation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(run_dir))


if __name__ == "__main__":
    main()
