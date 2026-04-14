#!/usr/bin/env python3
"""Integrated lightweight allocator audit (new-paper track).

Combines:
- controller-family routing
- difficulty-adaptive two-level allocation (B-1 / B+1, same mean budget)
- anti-collapse-aware adaptive-controller override

Outputs under outputs/integrated_allocator_audit/<run_id>/.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import re
import statistics
import sys
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

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
from experiments.frontier_router import fit_lightweight_router

BASELINES = [
    "adaptive_min_expand_1",
    "adaptive_budget_guarded",
    "router_only_family_selector",
    "difficulty_adaptive_only",
    "integrated_router_difficulty_anticollapse",
    "reasoning_greedy",
    "self_consistency_3",
    "reasoning_beam2",
    "verifier_guided_search",
    "program_of_thought",
    "oracle_frontier_upper_bound",
]

ROUTER_CANDIDATES = [
    "reasoning_beam2",
    "self_consistency_3",
    "adaptive_min_expand_1",
    "adaptive_budget_guarded",
]


class ConstantDifficultyModel:
    def __init__(self, p_hard: float):
        self.p_hard = p_hard

    def predict_proba(self, questions: list[str]) -> list[float]:
        return [self.p_hard for _ in questions]


@dataclass
class DifficultyModelArtifacts:
    model: Any
    mode: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Integrated lightweight allocator audit (new-paper)")
    p.add_argument("--datasets", default="openai/gsm8k,EleutherAI/hendrycks_math")
    p.add_argument("--subset-size", type=int, default=16)
    p.add_argument("--seed", type=int, default=123)
    p.add_argument("--budget", type=int, default=8)
    p.add_argument("--calibration-ratio", type=float, default=0.5)
    p.add_argument("--adaptive-min-expand-grid", default="0,1,2")
    p.add_argument("--api-backend", choices=("simulator", "openai", "groq", "gemini"), default="openai")
    p.add_argument("--model", default="gpt-4.1-mini")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--vgs-candidates", type=int, default=3)
    p.add_argument("--vgs-min-expansions", type=int, default=1)
    p.add_argument("--output-dir", default="outputs/integrated_allocator_audit")
    return p.parse_args()


def _parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _parse_str_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _row_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        out[(str(row["example_id"]), str(row["strategy"]))] = row
    return out


def _fit_difficulty_model(questions: list[str], hard_labels: list[int], seed: int) -> DifficultyModelArtifacts:
    n = max(1, len(hard_labels))
    pos = sum(hard_labels)
    if pos == 0 or pos == n:
        return DifficultyModelArtifacts(model=ConstantDifficultyModel(pos / n), mode="constant")
    model = make_pipeline(
        TfidfVectorizer(lowercase=True, ngram_range=(1, 2), max_features=512),
        LogisticRegression(max_iter=400, class_weight="balanced", random_state=seed),
    )
    model.fit(questions, hard_labels)
    return DifficultyModelArtifacts(model=model, mode="tfidf_logreg")


def _cheap_proxy_features(question: str) -> dict[str, float]:
    tokens = question.split()
    return {
        "char_len": float(len(question)),
        "token_len": float(len(tokens)),
        "digit_count": float(sum(ch.isdigit() for ch in question)),
        "operator_count": float(len(re.findall(r"[+\-*/=]", question))),
    }


def _pick_oracle_family(rows: list[dict[str, Any]], candidates: list[str]) -> dict[str, str]:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    rank = {m: i for i, m in enumerate(candidates)}
    for r in rows:
        if str(r["strategy"]) not in rank:
            continue
        by_ex.setdefault(str(r["example_id"]), []).append(r)
    out: dict[str, str] = {}
    for ex_id, erows in by_ex.items():
        best = min(
            erows,
            key=lambda r: (
                0 if r["is_correct"] else 1,
                float(r["actions_used"]),
                float(r["expansions"]),
                float(r["verifications"]),
                rank[str(r["strategy"])],
            ),
        )
        out[ex_id] = str(best["strategy"])
    return out


def _oracle_accuracy(eval_rows: list[dict[str, Any]]) -> float:
    by_ex: dict[str, list[dict[str, Any]]] = {}
    for row in eval_rows:
        by_ex.setdefault(str(row["example_id"]), []).append(row)
    if not by_ex:
        return 0.0
    return sum(1 for erows in by_ex.values() if any(bool(r["is_correct"]) for r in erows)) / len(by_ex)


def _prune_share(rows: list[dict[str, Any]]) -> float:
    vals: list[float] = []
    for row in rows:
        trace = ((row.get("metadata") or {}).get("action_trace") or [])
        if not trace:
            continue
        n = len(trace)
        p = sum(1 for t in trace if t.get("action") == "prune")
        vals.append(p / n)
    return statistics.mean(vals) if vals else 1.0


def _metrics_from_rows(rows: list[dict[str, Any]], oracle_acc: float, budget_mean: float, method: str, dataset: str, budget: int) -> dict[str, Any]:
    n = max(1, len(rows))
    acc = sum(1 for r in rows if bool(r["is_correct"])) / n
    avg_actions = sum(float(r["actions_used"]) for r in rows) / n
    avg_exp = sum(float(r["expansions"]) for r in rows) / n
    avg_ver = sum(float(r["verifications"]) for r in rows) / n
    ex_rate = sum(1 for r in rows if bool(r["budget_exhausted"])) / n
    return {
        "dataset": dataset,
        "budget": budget,
        "method": method,
        "n_eval_examples": n,
        "accuracy": acc,
        "avg_actions": avg_actions,
        "avg_expansions": avg_exp,
        "avg_verifications": avg_ver,
        "budget_exhaustion_rate": ex_rate,
        "avg_allocated_budget": budget_mean,
        "oracle_accuracy": oracle_acc,
        "gap_to_oracle": oracle_acc - acc,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def run_for_dataset(args: argparse.Namespace, dataset: str, ds_seed: int) -> dict[str, Any]:
    rng = random.Random(ds_seed)
    examples = load_pilot_examples(dataset, args.subset_size, ds_seed)
    split_idx = max(1, min(len(examples) - 1, int(len(examples) * args.calibration_ratio)))
    calib_examples = examples[:split_idx]
    eval_examples = examples[split_idx:]
    qmap = {str(ex.example_id): ex.question for ex in examples}

    budget = int(args.budget)
    b_low = max(1, budget - 1)
    b_high = budget + 1
    adaptive_grid = _parse_int_list(args.adaptive_min_expand_grid)

    use_remote = args.api_backend != "simulator"
    api_provider = None if not use_remote else args.api_backend

    gen_factory = generator_factory_for_mode(
        use_remote,
        rng,
        args.model,
        args.temperature,
        args.max_output_tokens,
        args.timeout_seconds,
        api_provider=api_provider,
    )

    per_budget: dict[int, dict[str, Any]] = {}
    for b in sorted({b_low, budget, b_high}):
        strategies_calib = build_frontier_strategies(
            gen_factory,
            b,
            adaptive_grid,
            rng,
            use_openai_api=use_remote,
            vgs_candidates=args.vgs_candidates,
            vgs_min_expansions=args.vgs_min_expansions,
            include_budget_guarded_adaptive=True,
        )
        c_metrics, c_rows = evaluate_strategies_on_examples(calib_examples, strategies_calib)
        strategies_eval = build_frontier_strategies(
            gen_factory,
            b,
            adaptive_grid,
            rng,
            use_openai_api=use_remote,
            vgs_candidates=args.vgs_candidates,
            vgs_min_expansions=args.vgs_min_expansions,
            include_budget_guarded_adaptive=True,
        )
        e_metrics, e_rows = evaluate_strategies_on_examples(eval_examples, strategies_eval)
        per_budget[b] = {
            "calib_metrics": c_metrics,
            "calib_rows": c_rows,
            "eval_metrics": e_metrics,
            "eval_rows": e_rows,
            "eval_index": _row_index(e_rows),
        }

    base_eval_rows = per_budget[budget]["eval_rows"]
    oracle_acc = _oracle_accuracy(base_eval_rows)

    method_rows: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []
    ablation_rows: list[dict[str, Any]] = []

    # Direct fixed-method metrics (base budget)
    base_metrics = per_budget[budget]["eval_metrics"]
    for m in [
        "adaptive_min_expand_1",
        "adaptive_budget_guarded",
        "reasoning_greedy",
        "self_consistency_3",
        "reasoning_beam2",
        "verifier_guided_search",
        "program_of_thought",
    ]:
        if m in base_metrics:
            mm = base_metrics[m]
            method_rows.append(
                {
                    "dataset": dataset,
                    "budget": budget,
                    "method": m,
                    "n_eval_examples": int(mm["n_examples"]),
                    "accuracy": float(mm["accuracy"]),
                    "avg_actions": float(mm["avg_actions"]),
                    "avg_expansions": float(mm["avg_expansions"]),
                    "avg_verifications": float(mm["avg_verifications"]),
                    "budget_exhaustion_rate": float(mm["budget_exhaustion_rate"]),
                    "avg_allocated_budget": float(budget),
                    "oracle_accuracy": oracle_acc,
                    "gap_to_oracle": oracle_acc - float(mm["accuracy"]),
                }
            )

    # router-only (base budget family selection)
    calib_rows_base = per_budget[budget]["calib_rows"]
    oracle_fam = _pick_oracle_family(calib_rows_base, ROUTER_CANDIDATES)
    train_q = [qmap[k] for k in sorted(oracle_fam)]
    train_y = [oracle_fam[k] for k in sorted(oracle_fam)]
    router_fit = fit_lightweight_router(train_q, train_y, seed=ds_seed + budget)

    eval_ids = [str(ex.example_id) for ex in eval_examples]
    eval_q = [qmap[eid] for eid in eval_ids]
    router_preds = router_fit.model.predict(eval_q)
    router_rows: list[dict[str, Any]] = []
    for eid, pred in zip(eval_ids, router_preds):
        row = per_budget[budget]["eval_index"][(eid, str(pred))]
        router_rows.append(row)
    method_rows.append(_metrics_from_rows(router_rows, oracle_acc, float(budget), "router_only_family_selector", dataset, budget))

    # difficulty-adaptive-only: budget split + fixed controllers from calibration
    def best_feasible(calib_metrics: dict[str, dict[str, float]], b: int) -> str:
        feasible = [k for k, v in calib_metrics.items() if float(v["avg_actions"]) <= float(b)]
        return max(feasible, key=lambda k: float(calib_metrics[k]["accuracy"])) if feasible else max(calib_metrics, key=lambda k: float(calib_metrics[k]["accuracy"]))

    low_ctrl = best_feasible(per_budget[b_low]["calib_metrics"], b_low)
    high_ctrl = best_feasible(per_budget[b_high]["calib_metrics"], b_high)

    calib_index_base = _row_index(calib_rows_base)
    calib_ids = [str(ex.example_id) for ex in calib_examples]
    hard_labels = []
    for eid in calib_ids:
        r = calib_index_base[(eid, "adaptive_min_expand_1")]
        hard_labels.append(int((not bool(r["is_correct"])) or bool(r["budget_exhausted"])))

    dfit = _fit_difficulty_model([qmap[eid] for eid in calib_ids], hard_labels, seed=ds_seed + 17)
    if dfit.mode == "constant":
        hard_probs = dfit.model.predict_proba(eval_q)
    else:
        hard_probs = [float(x[1]) for x in dfit.model.predict_proba(eval_q)]

    n_high = len(eval_ids) // 2
    ranked = sorted(zip(eval_ids, hard_probs), key=lambda x: x[1], reverse=True)
    hard_set = {eid for eid, _ in ranked[:n_high]}

    diff_rows: list[dict[str, Any]] = []
    for eid in eval_ids:
        alloc_b = b_high if eid in hard_set else b_low
        ctrl = high_ctrl if alloc_b == b_high else low_ctrl
        diff_rows.append(per_budget[alloc_b]["eval_index"][(eid, ctrl)])
    method_rows.append(_metrics_from_rows(diff_rows, oracle_acc, float(budget), "difficulty_adaptive_only", dataset, budget))

    # integrated: difficulty split + router + anti-collapse override
    # anti-collapse signal from calibration hard subset at base budget
    hard_calib_ids = {eid for eid, y in zip(calib_ids, hard_labels) if y == 1}
    c_guard = [r for r in calib_rows_base if str(r["strategy"]) == "adaptive_budget_guarded" and str(r["example_id"]) in hard_calib_ids]
    c_min1 = [r for r in calib_rows_base if str(r["strategy"]) == "adaptive_min_expand_1" and str(r["example_id"]) in hard_calib_ids]
    guard_preferred = False
    if c_guard and c_min1:
        guard_preferred = (
            statistics.mean([1.0 if r["is_correct"] else 0.0 for r in c_guard]) >= statistics.mean([1.0 if r["is_correct"] else 0.0 for r in c_min1])
            and _prune_share(c_guard) <= _prune_share(c_min1)
        )

    integrated_rows: list[dict[str, Any]] = []
    for eid, q, p in zip(eval_ids, eval_q, hard_probs):
        alloc_b = b_high if eid in hard_set else b_low
        routed = str(router_fit.model.predict([q])[0])
        # anti-collapse override for hard/high examples
        if alloc_b == b_high and p >= 0.5 and routed.startswith("adaptive_min_expand") and guard_preferred:
            routed = "adaptive_budget_guarded"
        if routed not in per_budget[alloc_b]["eval_metrics"]:
            routed = high_ctrl if alloc_b == b_high else low_ctrl
        integrated_rows.append(per_budget[alloc_b]["eval_index"][(eid, routed)])
        ablation_rows.append(
            {
                "dataset": dataset,
                "budget": budget,
                "example_id": eid,
                "difficulty_hard_probability": p,
                "allocated_budget": alloc_b,
                "router_predicted_controller": str(router_fit.model.predict([q])[0]),
                "guard_preferred_on_calib_hard": int(guard_preferred),
                "integrated_selected_controller": routed,
                **_cheap_proxy_features(q),
            }
        )

    method_rows.append(
        _metrics_from_rows(
            integrated_rows,
            oracle_acc,
            float(budget),
            "integrated_router_difficulty_anticollapse",
            dataset,
            budget,
        )
    )

    oracle_rows.extend(
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
        for r in method_rows
    )

    method_rows.append(
        {
            "dataset": dataset,
            "budget": budget,
            "method": "oracle_frontier_upper_bound",
            "n_eval_examples": len(eval_examples),
            "accuracy": oracle_acc,
            "avg_actions": "",
            "avg_expansions": "",
            "avg_verifications": "",
            "budget_exhaustion_rate": "",
            "avg_allocated_budget": float(budget),
            "oracle_accuracy": oracle_acc,
            "gap_to_oracle": 0.0,
        }
    )

    return {
        "dataset": dataset,
        "method_rows": method_rows,
        "oracle_rows": oracle_rows,
        "ablation_rows": ablation_rows,
        "n_calib": len(calib_examples),
        "n_eval": len(eval_examples),
        "router_mode": router_fit.mode,
        "difficulty_mode": dfit.mode,
    }


def main() -> None:
    args = parse_args()
    if args.api_backend != "simulator" and not resolve_api_key_for_provider(args.api_backend):
        raise SystemExit(f"Missing API key for backend={args.api_backend}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    all_methods: list[dict[str, Any]] = []
    all_oracle: list[dict[str, Any]] = []
    all_ablate: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []

    for i, ds in enumerate(_parse_str_list(args.datasets)):
        ds_seed = args.seed + i * 1009
        print(f"[integrated_audit] dataset={ds} start", flush=True)
        try:
            out = run_for_dataset(args, ds, ds_seed)
        except Exception as exc:  # noqa: BLE001
            failed.append({"dataset": ds, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[integrated_audit] dataset={ds} FAILED: {exc}", flush=True)
            continue
        all_methods.extend(out["method_rows"])
        all_oracle.extend(out["oracle_rows"])
        all_ablate.extend(out["ablation_rows"])
        print(f"[integrated_audit] dataset={ds} done", flush=True)

    primary = "integrated_router_difficulty_anticollapse"
    by_key: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for row in all_methods:
        by_key.setdefault((str(row["dataset"]), int(row["budget"])), {})[str(row["method"])] = row

    comp_rows: list[dict[str, Any]] = []
    for (ds, b), methods in by_key.items():
        if primary not in methods:
            continue
        p = methods[primary]
        for bl in [m for m in BASELINES if m not in {primary, "oracle_frontier_upper_bound"}]:
            if bl not in methods:
                continue
            r = methods[bl]
            da = float(p["accuracy"]) - float(r["accuracy"])
            comp_rows.append(
                {
                    "dataset": ds,
                    "budget": b,
                    "primary_method": primary,
                    "primary_accuracy": p["accuracy"],
                    "primary_avg_actions": p["avg_actions"],
                    "primary_gap_to_oracle": p["gap_to_oracle"],
                    "baseline_method": bl,
                    "baseline_accuracy": r["accuracy"],
                    "baseline_avg_actions": r["avg_actions"],
                    "baseline_gap_to_oracle": r["gap_to_oracle"],
                    "delta_accuracy_primary_minus_baseline": da,
                    "winner": primary if da > 0 else (bl if da < 0 else "tie"),
                }
            )

    _write_csv(run_dir / "method_metrics.csv", all_methods)
    _write_csv(run_dir / "oracle_gap_summary.csv", all_oracle)
    _write_csv(run_dir / "comparison_summary.csv", comp_rows)
    _write_csv(run_dir / "integrated_ablation_trace.csv", all_ablate)

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "track": "new-paper",
        "datasets_requested": _parse_str_list(args.datasets),
        "datasets_completed": sorted({r["dataset"] for r in all_methods}),
        "datasets_failed": failed,
        "subset_size": args.subset_size,
        "seed": args.seed,
        "budget": args.budget,
        "calibration_ratio": args.calibration_ratio,
        "api_backend": args.api_backend,
        "model": args.model,
        "integrated_method_name": primary,
        "integrated_components": {
            "router": "lightweight tfidf/logreg family router with constant fallback",
            "difficulty": "two-level B-1/B+1 allocation at fixed mean budget",
            "anti_collapse": "guarded adaptive override on hard/high subset when calibration supports lower prune share",
        },
        "comparators_targeted": BASELINES,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # report
    def mget(ds: str, method: str) -> dict[str, Any] | None:
        return next((r for r in all_methods if r["dataset"] == ds and r["method"] == method), None)

    lines = [
        "# Integrated lightweight allocator report",
        "",
        "## Setup",
        f"- Backend: {args.api_backend} / {args.model}",
        f"- Budget: {args.budget} (integrated method uses B-1/B+1 with same mean)",
        f"- Subset size: {args.subset_size}, calibration_ratio={args.calibration_ratio}",
        "",
        "## Final questions",
    ]

    for ds in sorted({r["dataset"] for r in all_methods}):
        lines.append(f"### Dataset: {ds}")
        integ = mget(ds, primary)
        base = mget(ds, "adaptive_min_expand_1")
        best_simple = None
        simple_set = ["reasoning_greedy", "self_consistency_3", "reasoning_beam2", "verifier_guided_search", "program_of_thought", "adaptive_budget_guarded", "router_only_family_selector", "difficulty_adaptive_only"]
        avail = [mget(ds, m) for m in simple_set if mget(ds, m) is not None]
        if avail:
            best_simple = max(avail, key=lambda r: float(r["accuracy"]))
        if integ and base:
            lines.append(
                f"- Oracle gap vs adaptive_min_expand_1: integrated={float(integ['gap_to_oracle']):.4f}, base={float(base['gap_to_oracle']):.4f}, delta={float(base['gap_to_oracle'])-float(integ['gap_to_oracle']):+.4f}."
            )
        if integ and best_simple:
            lines.append(
                f"- Beats strongest simple baseline? integrated_acc={float(integ['accuracy']):.4f}, best_simple={best_simple['method']} ({float(best_simple['accuracy']):.4f}) => {'YES' if float(integ['accuracy']) > float(best_simple['accuracy']) else 'NO'}.")
        rtr = mget(ds, "router_only_family_selector")
        dif = mget(ds, "difficulty_adaptive_only")
        grd = mget(ds, "adaptive_budget_guarded")
        if integ and rtr and dif and grd:
            deltas = {
                "routing": float(integ["accuracy"]) - float(dif["accuracy"]),
                "difficulty": float(integ["accuracy"]) - float(rtr["accuracy"]),
                "anti_collapse": float(integ["accuracy"]) - float(grd["accuracy"]),
            }
            key = max(deltas, key=deltas.get)
            lines.append(
                f"- Main gain attribution (rough): strongest delta axis={key} with delta={deltas[key]:+.4f}; full deltas={deltas}."
            )
        lines.append("- Evidence scale: pilot-scale unless both datasets completed with non-trivial n.")
        lines.append("")

    if failed:
        lines.append("## Failures")
        for f in failed:
            lines.append(f"- {f['dataset']}: {f['error']}")

    (run_dir / "integrated_method_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(run_dir))


if __name__ == "__main__":
    main()
