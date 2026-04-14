#!/usr/bin/env python3
"""Matched-budget comparative audit: primary adaptive allocator vs baselines (new-paper track).

Writes outputs/comparative_frontier_audit/<run_id>/:
  run_manifest.json
  method_metrics.csv
  oracle_gap_summary.csv
  comparison_summary.csv
  selector_audit.csv (optional, if calibration split used)
  main_drawbacks_report.md
"""

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
import traceback
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    evaluate_strategies_on_examples,
    generator_factory_for_mode,
    load_pilot_examples,
    resolve_api_key_for_provider,
)

# Runnable in-repo simulator/API controllers only (see main_drawbacks_report for external baselines).
INTERNAL_METHODS = [
    "reasoning_greedy",
    "self_consistency_3",
    "reasoning_beam2",
    "adaptive_min_expand_0",
    "adaptive_min_expand_1",
    "adaptive_min_expand_2",
    "verifier_guided_search",
    "program_of_thought",
    "adaptive_prm_partial",
    "adaptive_prm_partial_early_reject",
    "verifier_guided_search_prm",
    "verifier_guided_search_prm_early_reject",
]

DEFAULT_PRIMARY = "adaptive_min_expand_1"
DEFAULT_BASELINES = [
    "reasoning_greedy",
    "self_consistency_3",
    "reasoning_beam2",
    "verifier_guided_search",
    "program_of_thought",
]
PRM_BASELINES = [
    "adaptive_prm_partial",
    "adaptive_prm_partial_early_reject",
    "verifier_guided_search_prm",
    "verifier_guided_search_prm_early_reject",
]

EXTERNAL_NOT_RUNNABLE = [
    {
        "name": "eth-sri/cascade-routing",
        "note": "Apache-2.0 upstream; not vendored or wrapped—clone separately.",
    },
    {
        "name": "nishadsinghi/sc-genrm-scaling (When To Solve / When To Verify)",
        "note": "Linked from paper; heavy stack; not integrated as a subprocess runner here.",
    },
    {
        "name": "RyanLiu112/compute-optimal-tts",
        "note": "Related MIT repo; not verified as Snell author release; not wired.",
    },
    {
        "name": "arakhsha/mob (Majority-of-the-Bests)",
        "note": "Separate codebase; link-only in external/.",
    },
]


def _parse_budgets(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_datasets(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _oracle_accuracy(eval_rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in eval_rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    n = len(by_ex)
    if n == 0:
        return 0.0
    correct = sum(1 for rows in by_ex.values() if any(r["is_correct"] for r in rows))
    return correct / n


def _gap_to_oracle(oracle_acc: float, method_acc: float) -> float:
    return float(oracle_acc) - float(method_acc)


def run_dataset_audit(
    dataset: str,
    *,
    subset_size: int,
    seed: int,
    budgets: list[int],
    calibration_ratio: float,
    eval_only: bool,
    adaptive_grid: list[int],
    use_openai_api: bool,
    openai_model: str,
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: int,
    vgs_candidates: int,
    vgs_min_expansions: int,
    rng: random.Random,
    api_provider: str | None = None,
    include_prm_variants: bool = False,
    prm_early_reject_threshold: float = 0.25,
    prm_early_reject_min_expansions: int = 2,
) -> dict[str, Any]:
    examples = load_pilot_examples(dataset, subset_size, seed)
    if eval_only:
        calib_examples: list = []
        eval_examples = examples
    else:
        split_idx = max(1, min(len(examples) - 1, int(len(examples) * calibration_ratio)))
        calib_examples = examples[:split_idx]
        eval_examples = examples[split_idx:]

    gen_factory = generator_factory_for_mode(
        use_openai_api,
        rng,
        openai_model,
        temperature,
        max_output_tokens,
        timeout_seconds,
        api_provider=api_provider,
    )

    method_rows: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    selector_rows: list[dict[str, Any]] = []

    for budget in budgets:
        strategies = build_frontier_strategies(
            gen_factory,
            budget,
            adaptive_grid,
            rng,
            use_openai_api=use_openai_api,
            vgs_candidates=vgs_candidates,
            vgs_min_expansions=vgs_min_expansions,
            include_prm_variants=include_prm_variants,
            prm_early_reject_threshold=prm_early_reject_threshold,
            prm_early_reject_min_expansions=prm_early_reject_min_expansions,
        )

        if not eval_only and calib_examples:
            calib_metrics, _ = evaluate_strategies_on_examples(calib_examples, strategies)
            feasible = [s for s, m in calib_metrics.items() if m["avg_actions"] <= float(budget)]
            chosen = max(feasible, key=lambda s: calib_metrics[s]["accuracy"]) if feasible else max(
                calib_metrics, key=lambda s: calib_metrics[s]["accuracy"]
            )
            eval_metrics, eval_rows = evaluate_strategies_on_examples(eval_examples, strategies)
            chosen_eval = eval_metrics[chosen]
            oracle_acc = _oracle_accuracy(eval_rows)
            selector_rows.append(
                {
                    "dataset": dataset,
                    "budget": budget,
                    "selected_strategy": chosen,
                    "selector_calib_accuracy": calib_metrics[chosen]["accuracy"],
                    "selector_eval_accuracy": chosen_eval["accuracy"],
                    "selector_eval_avg_actions": chosen_eval["avg_actions"],
                    "oracle_eval_accuracy": oracle_acc,
                    "oracle_gap_selector": oracle_acc - float(chosen_eval["accuracy"]),
                }
            )
        else:
            eval_metrics, eval_rows = evaluate_strategies_on_examples(eval_examples, strategies)
            oracle_acc = _oracle_accuracy(eval_rows)

        for name, m in eval_metrics.items():
            gap = _gap_to_oracle(oracle_acc, m["accuracy"])
            method_rows.append(
                {
                    "dataset": dataset,
                    "budget": budget,
                    "method": name,
                    "n_eval_examples": int(m["n_examples"]),
                    "accuracy": m["accuracy"],
                    "avg_actions": m["avg_actions"],
                    "avg_expansions": m["avg_expansions"],
                    "avg_verifications": m["avg_verifications"],
                    "budget_exhaustion_rate": m["budget_exhaustion_rate"],
                    "oracle_accuracy": oracle_acc,
                    "gap_to_oracle": gap,
                }
            )
            oracle_rows.append(
                {
                    "dataset": dataset,
                    "budget": budget,
                    "method": name,
                    "oracle_accuracy": oracle_acc,
                    "method_accuracy": m["accuracy"],
                    "gap_to_oracle": gap,
                    "avg_actions": m["avg_actions"],
                    "budget_exhaustion_rate": m["budget_exhaustion_rate"],
                }
            )

    return {
        "dataset": dataset,
        "n_examples_used_eval": len(eval_examples),
        "n_examples_used_calib": len(calib_examples),
        "method_rows": method_rows,
        "oracle_rows": oracle_rows,
        "selector_rows": selector_rows,
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _build_comparison_rows(
    method_rows: list[dict[str, Any]],
    primary: str,
    baselines: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_key: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for row in method_rows:
        ds = row["dataset"]
        b = int(row["budget"])
        m = row["method"]
        by_key.setdefault((ds, b), {})[m] = row

    for (ds, b), methods in by_key.items():
        if primary not in methods:
            continue
        p = methods[primary]
        for bl in baselines:
            if bl not in methods:
                continue
            brow = methods[bl]
            da = float(p["accuracy"]) - float(brow["accuracy"])
            winner = primary if da > 0 else (bl if da < 0 else "tie")
            out.append(
                {
                    "dataset": ds,
                    "budget": b,
                    "primary_method": primary,
                    "primary_accuracy": p["accuracy"],
                    "primary_avg_actions": p["avg_actions"],
                    "primary_gap_to_oracle": p["gap_to_oracle"],
                    "baseline_method": bl,
                    "baseline_accuracy": brow["accuracy"],
                    "baseline_avg_actions": brow["avg_actions"],
                    "baseline_gap_to_oracle": brow["gap_to_oracle"],
                    "delta_accuracy_primary_minus_baseline": da,
                    "winner": winner,
                }
            )
    return out


def _generate_drawbacks_report(
    run_id: str,
    manifest: dict[str, Any],
    method_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    primary: str,
    failed: list[dict[str, str]],
) -> str:
    api_back = str(manifest.get("api_backend", "simulator"))
    model = str(manifest.get("model", ""))
    backend_line = (
        f"- **Backend**: **real API** — `{api_back}` model `{model}` (expand/verify/PoT share this generator)."
        if api_back != "simulator"
        else "- **Backend**: **simulator** — `SimulatedBranchGenerator` (process proxy, not LLM SOTA)."
    )
    lines = [
        f"# Main drawbacks report — comparative frontier audit (`{run_id}`)",
        "",
        "## Scope",
        "",
        "- **New-paper track**: matched-budget comparison of in-repo controller families on the same eval slices and budgets.",
        f"- **Primary “ours” method** (proposed adaptive anti-collapse allocator): `{primary}`.",
        backend_line,
        "- **External baselines** (cascade routing, MoB, paper-linked codebases): **not runnable inside this repository**; see `run_manifest.json` → `external_baselines_not_integrated`.",
        "",
        "## 1) Where the primary method wins (accuracy vs listed baselines)",
        "",
    ]

    wins = sum(1 for r in comparison_rows if r["winner"] == primary)
    losses = sum(1 for r in comparison_rows if r["winner"] != primary and r["winner"] != "tie")
    ties = sum(1 for r in comparison_rows if r["winner"] == "tie")
    lines.append(
        f"- Head-to-head cells (dataset × budget × baseline): **wins={wins}**, **losses={losses}**, **ties={ties}** "
        f"(see `comparison_summary.csv`)."
    )

    if comparison_rows:
        by_bl: dict[str, list[float]] = {}
        for r in comparison_rows:
            bl = str(r["baseline_method"])
            by_bl.setdefault(bl, []).append(float(r["delta_accuracy_primary_minus_baseline"]))
        lines.append("")
        lines.append("| Baseline | Mean Δ acc (ours − baseline) |")
        lines.append("|---|---|")
        for bl, deltas in sorted(by_bl.items()):
            lines.append(f"| `{bl}` | {statistics.mean(deltas):.4f} |")
        lines.append("")

    lines.extend(
        [
            "## 2) Where the primary method loses",
            "",
            "Any negative mean Δ in the table above indicates systematic losses against that baseline on average over the audited cells.",
            "",
            "## 3) Oracle gap (headroom — not ‘our bug’ alone)",
            "",
        ]
    )

    prim_oracle = [float(r["gap_to_oracle"]) for r in method_rows if r["method"] == primary]
    if prim_oracle:
        lines.append(
            f"- Mean **gap to oracle** for `{primary}`: **{statistics.mean(prim_oracle):.4f}** "
            f"(oracle = best per-example strategy across all eight families)."
        )
    best_baseline_gaps: dict[str, list[float]] = {}
    for r in method_rows:
        m = r["method"]
        if m == primary or m.startswith("adaptive_min_expand"):
            continue
        if m in DEFAULT_BASELINES:
            best_baseline_gaps.setdefault(m, []).append(float(r["gap_to_oracle"]))
    if best_baseline_gaps:
        means = {k: statistics.mean(v) for k, v in best_baseline_gaps.items()}
        tightest = min(means, key=means.get)
        lines.append(
            f"- Tightest baseline to oracle on average: **`{tightest}`** (mean gap ≈ **{means[tightest]:.4f}**)."
        )
    lines.append(
        "- Large oracle gaps for **everyone** suggest diverse per-example winners (frontier heterogeneity), not only a failure of the adaptive policy."
    )

    lines.extend(
        [
            "",
            "## 4) Budget usage / under-spend / exhaustion",
            "",
        ]
    )
    pa = [float(r["avg_actions"]) for r in method_rows if r["method"] == primary]
    pb = [float(r["budget"]) for r in method_rows if r["method"] == primary]
    if pa and pb:
        lines.append(
            f"- `{primary}` mean realized **avg_actions / budget**: "
            f"{statistics.mean([a / b for a, b in zip(pa, pb)]):.3f} (see `method_metrics.csv`)."
        )
    ex = [float(r["budget_exhaustion_rate"]) for r in method_rows if r["method"] == primary]
    if ex:
        lines.append(f"- Mean **budget_exhaustion_rate** for `{primary}`: **{statistics.mean(ex):.4f}**.")

    vgs_line = (
        "- **verifier_guided_search**: uses **LLM verify** as ranking proxy on the same backend — meaningful for routing test-time compute, but still **not** a trained PRM."
        if api_back != "simulator"
        else "- **verifier_guided_search**: uses `SimulatedScorerVerifier` in simulation (or API verify proxy). This is a **ranking proxy**, not a trained PRM."
    )
    pot_line = (
        "- **program_of_thought**: uses **codegen + sandbox** on the same API path; quality depends on model and JSON fidelity (see `method_metrics.csv`)."
        if api_back != "simulator"
        else "- **program_of_thought**: simulator uses trivial numeric code from regex; many items get **~0 accuracy** in sim — **not** a fair PoT benchmark."
    )
    lines.extend(
        [
            "",
            "## 5) Verifier-guided search & program-of-thought (maturity)",
            "",
            vgs_line,
            pot_line,
            "",
            "## 6) Inferred drawbacks (evidence-based — check CSVs)",
            "",
        ]
    )

    drawbacks: list[str] = []
    if prim_oracle and statistics.mean(prim_oracle) > 0.15:
        drawbacks.append(
            "**Gap to oracle**: Primary method leaves substantial per-example headroom vs the best-of-frontier upper bound — allocation may be **suboptimal vs an oracle meta-policy** (see `oracle_gap_summary.csv`)."
        )
    if comparison_rows and losses > wins:
        rank_ctx = "this API-backed run" if api_back != "simulator" else "the simulator"
        drawbacks.append(
            f"**Head-to-head**: Primary method loses more cells than it wins against the listed baselines — **marginal ranking in {rank_ctx}** may favor simpler families (beam / self-consistency / VGS) in several regimes."
        )
    # Adaptive ablation: compare gaps for 0 vs 1 vs 2
    adp = {0: [], 1: [], 2: []}
    for r in method_rows:
        for k in (0, 1, 2):
            if r["method"] == f"adaptive_min_expand_{k}":
                adp[k].append(float(r["gap_to_oracle"]))
    if all(adp[k] for k in (0, 1, 2)):
        gaps_mean = {k: statistics.mean(adp[k]) for k in (0, 1, 2)}
        drawbacks.append(
            f"**Anti-collapse knob**: Mean gap-to-oracle across budgets/datasets: "
            f"k=0 → {gaps_mean[0]:.3f}, k=1 → {gaps_mean[1]:.3f}, k=2 → {gaps_mean[2]:.3f}. "
            f"If k=1 is not uniformly best, **min-expand is regime-dependent** (see ablation in `method_metrics.csv`)."
        )
    if pa and pb and statistics.mean([a / b for a, b in zip(pa, pb)]) < 0.65:
        drawbacks.append(
            "**Under-spend**: Primary method often uses **far below the budget cap** — opportunity cost if other families would convert extra actions into accuracy."
        )

    if not drawbacks:
        drawbacks.append(
            "**No strong automated verdict** from aggregate rules — inspect `comparison_summary.csv` and per-dataset splits manually."
        )

    for i, d in enumerate(drawbacks, 1):
        lines.append(f"{i}. {d}")
    lines.append("")

    if failed:
        lines.extend(["## Blocked datasets", ""])
        for f in failed:
            lines.append(f"- **{f.get('dataset')}**: {f.get('error', '')}")
        lines.append("")

    lines.extend(
        [
            "## Scale honesty",
            "",
            f"- Subset size / budgets / datasets: see `run_manifest.json`.",
            "- Even with a real API, small `--subset-size` and few budgets yield **pilot-scale** statistical power; scale up for publication-grade means.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Matched-budget comparative frontier audit (new-paper track)")
    p.add_argument("--datasets", default="openai/gsm8k,EleutherAI/hendrycks_math")
    p.add_argument("--try-gpqa", action="store_true")
    p.add_argument("--subset-size", type=int, default=64)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--budgets", default="6,8,10,12")
    p.add_argument("--adaptive-min-expand-grid", default="0,1,2")
    p.add_argument("--primary-method", default=DEFAULT_PRIMARY, help="Tagged as ‘our’ allocator for comparisons.")
    p.add_argument(
        "--with-selector-split",
        action="store_true",
        help="Reserve a calibration fraction and write selector_audit.csv; otherwise all examples are eval (strict matched-budget comparison).",
    )
    p.add_argument("--calibration-ratio", type=float, default=0.5)
    p.add_argument(
        "--api-backend",
        choices=("simulator", "openai", "groq", "gemini"),
        default="simulator",
        help="Remote LLM for all controller families (single provider per run). Loads .env for keys.",
    )
    p.add_argument("--use-openai-api", action="store_true", help="Shortcut for --api-backend openai")
    p.add_argument("--model", "--openai-model", dest="model", default="gpt-4.1-mini", help="Model id for the selected API backend")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-dir", default="outputs/comparative_frontier_audit")
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    p.add_argument("--include-prm-variants", action="store_true")
    p.add_argument("--prm-early-reject-threshold", type=float, default=0.25)
    p.add_argument("--prm-early-reject-min-expansions", type=int, default=2)
    return p.parse_args()


def _load_dotenv_repo() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass


def main() -> None:
    _load_dotenv_repo()
    args = parse_args()
    if args.use_openai_api:
        args.api_backend = "openai"
    use_remote_api = args.api_backend != "simulator"
    if use_remote_api:
        key = resolve_api_key_for_provider(args.api_backend)
        if not key:
            print(
                f"ERROR: No API key in environment for backend `{args.api_backend}` "
                f"(after loading {REPO_ROOT / '.env'}). Set the appropriate env var and retry.",
                file=sys.stderr,
            )
            sys.exit(2)
    budgets = _parse_budgets(args.budgets)
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)
    datasets = _parse_datasets(args.datasets)
    if args.try_gpqa and "Idavidrein/gpqa" not in datasets:
        datasets.append("Idavidrein/gpqa")

    eval_only = not args.with_selector_split

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    api_provider: str | None = None if not use_remote_api else args.api_backend

    all_method: list[dict[str, Any]] = []
    all_oracle: list[dict[str, Any]] = []
    all_selector: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []

    for i, ds in enumerate(datasets):
        ds_seed = args.seed + i * 10007
        rng = random.Random(ds_seed)
        print(f"[comparative_frontier_audit] dataset={ds} starting...", flush=True)
        try:
            block = run_dataset_audit(
                ds,
                subset_size=args.subset_size,
                seed=ds_seed,
                budgets=budgets,
                calibration_ratio=args.calibration_ratio,
                eval_only=eval_only,
                adaptive_grid=adaptive_grid,
                use_openai_api=use_remote_api,
                openai_model=args.model,
                temperature=args.temperature,
                max_output_tokens=args.max_output_tokens,
                timeout_seconds=args.timeout_seconds,
                vgs_candidates=args.vgs_candidates,
                vgs_min_expansions=args.vgs_min_expansions,
                rng=rng,
                api_provider=api_provider,
                include_prm_variants=args.include_prm_variants,
                prm_early_reject_threshold=args.prm_early_reject_threshold,
                prm_early_reject_min_expansions=args.prm_early_reject_min_expansions,
            )
        except Exception as exc:  # noqa: BLE001
            failed.append({"dataset": ds, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})
            print(f"[comparative_frontier_audit] dataset={ds} FAILED: {exc}", flush=True)
            continue

        print(f"[comparative_frontier_audit] dataset={ds} done ({len(block['method_rows'])} metric rows).", flush=True)
        all_method.extend(block["method_rows"])
        all_oracle.extend(block["oracle_rows"])
        all_selector.extend(block["selector_rows"])

    primary = args.primary_method
    baselines = DEFAULT_BASELINES + (PRM_BASELINES if args.include_prm_variants else [])
    comparison = _build_comparison_rows(all_method, primary, baselines)

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "internal_methods_runnable": INTERNAL_METHODS,
        "primary_method_tagged_ours": primary,
        "baselines_compared": baselines,
        "adaptive_ablations": [f"adaptive_min_expand_{k}" for k in adaptive_grid],
        "external_baselines_not_integrated": EXTERNAL_NOT_RUNNABLE,
        "datasets_requested": datasets,
        "datasets_completed": sorted({r["dataset"] for r in all_method}),
        "datasets_failed": failed,
        "subset_size": args.subset_size,
        "seed": args.seed,
        "budgets": budgets,
        "eval_only": eval_only,
        "calibration_ratio": args.calibration_ratio,
        "api_backend": args.api_backend,
        "model": args.model,
        "use_remote_api": use_remote_api,
        "keys_available_after_dotenv": {
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "gemini_or_google": bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")),
        },
        "comparison_principle": "Same eval examples, same budget cap per method, same RNG policy per dataset seed; single API provider per run.",
        "include_prm_variants": args.include_prm_variants,
        "prm_early_reject_threshold": args.prm_early_reject_threshold,
        "prm_early_reject_min_expansions": args.prm_early_reject_min_expansions,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    _write_csv(
        out_dir / "method_metrics.csv",
        [
            "dataset",
            "budget",
            "method",
            "n_eval_examples",
            "accuracy",
            "avg_actions",
            "avg_expansions",
            "avg_verifications",
            "budget_exhaustion_rate",
            "oracle_accuracy",
            "gap_to_oracle",
        ],
        all_method,
    )
    _write_csv(
        out_dir / "oracle_gap_summary.csv",
        ["dataset", "budget", "method", "oracle_accuracy", "method_accuracy", "gap_to_oracle", "avg_actions", "budget_exhaustion_rate"],
        all_oracle,
    )
    _write_csv(
        out_dir / "comparison_summary.csv",
        [
            "dataset",
            "budget",
            "primary_method",
            "primary_accuracy",
            "primary_avg_actions",
            "primary_gap_to_oracle",
            "baseline_method",
            "baseline_accuracy",
            "baseline_avg_actions",
            "baseline_gap_to_oracle",
            "delta_accuracy_primary_minus_baseline",
            "winner",
        ],
        comparison,
    )
    if all_selector:
        _write_csv(
            out_dir / "selector_audit.csv",
            [
                "dataset",
                "budget",
                "selected_strategy",
                "selector_calib_accuracy",
                "selector_eval_accuracy",
                "selector_eval_avg_actions",
                "oracle_eval_accuracy",
                "oracle_gap_selector",
            ],
            all_selector,
        )

    report = _generate_drawbacks_report(run_id, manifest, all_method, comparison, primary, failed)
    (out_dir / "main_drawbacks_report.md").write_text(report, encoding="utf-8")

    print(str(out_dir))
    if failed:
        for f in failed:
            print(f"WARN failed dataset {f['dataset']}: {f['error']}", file=sys.stderr)


if __name__ == "__main__":
    main()
