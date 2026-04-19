#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode, load_pilot_examples

BASE = "broad_diversity_aggregation_strong_v1"
ICC = "broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1"
ICC_RAW = "broad_diversity_aggregation_strong_v1_incumbent_challenger_raw_support_v1"
ICC_LATE_GUARD = "broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_late_guard_v1"
ICC_SWITCH_PERSIST = "broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_switch_persistence_v1"


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _load_exact_bundle_datasets(bundle_name: str) -> list[str]:
    payload = json.loads((REPO_ROOT / "configs/dataset_experiment_readiness_bundles.json").read_text(encoding="utf-8"))
    return [str(x) for x in (((payload.get("bundles") or {}).get(bundle_name) or {}).get("datasets") or [])]


def _ic_state(meta: dict[str, Any]) -> dict[str, Any]:
    checks = meta.get("incumbent_challenger_checks") or []
    return checks[-1] if checks else {}


def _failure_group(row: dict[str, Any]) -> str:
    if row["is_correct"]:
        return "correct"
    m = row.get("metadata") or {}
    if row.get("prediction") is None:
        return "incomplete_or_non_terminal"
    if row.get("budget_exhausted") or (not bool(m.get("commit_triggered", False)) and int(row.get("actions_used", 0)) >= int(row.get("budget", 0)) - 1):
        return "wrong_commit_timing"
    if int(m.get("unique_answer_groups_seen", 0)) <= 1 or _safe_float(m.get("answer_support_entropy", 0.0)) < 0.25:
        return "insufficient_diversity_realized"
    if _safe_float(m.get("answer_group_margin", 0.0)) <= 0.2:
        return "ambiguity_near_tie"
    if bool(m.get("aggregation_used", False)) and _safe_float(m.get("group_support_fraction", 0.0)) < 0.62:
        return "aggregation_instability"
    return "other"


def _wrong_commit_subtype(row: dict[str, Any]) -> str:
    if row.get("failure_group") != "wrong_commit_timing":
        return "not_wrong_commit_timing"
    m = row.get("metadata") or {}
    ic = _ic_state(m)
    actions = int(row.get("actions_used", 0))
    budget = int(row.get("budget", 0))
    near_tie_flag = bool(ic.get("near_tie", False) or ic.get("ambiguity_flag", False) or _safe_float(m.get("answer_group_margin", 0.0)) <= 0.20)
    fragmented_flag = bool(
        ic.get("challenger_fragmented_flag", False)
        or (int(m.get("unique_answer_groups_seen", 0)) >= 3 and _safe_float(m.get("group_support_fraction", 0.0)) <= 0.55)
        or _safe_float(m.get("answer_support_entropy", 0.0)) >= 1.0
    )

    if bool(m.get("commit_triggered", False)) and actions <= max(1, budget - 2):
        if near_tie_flag:
            return "wrong_commit_under_near_tie"
        if fragmented_flag:
            return "wrong_commit_under_fragmented_support"
        if bool(ic.get("challenger_plausible", False)):
            return "wrong_commit_despite_weak_challenger_separation"
        return "wrong_early_commit"
    if not bool(m.get("commit_triggered", False)) and (bool(row.get("budget_exhausted", False)) or actions >= max(1, budget - 1)):
        return "wrong_late_commit"
    if bool(ic.get("incumbent_changed_recently", False)):
        return "wrong_incumbent_replacement"
    if near_tie_flag:
        return "wrong_commit_under_near_tie"
    if fragmented_flag:
        return "wrong_commit_under_fragmented_support"
    if bool(ic.get("challenger_plausible", False)):
        return "wrong_commit_despite_weak_challenger_separation"
    return "wrong_commit_other"


def _case_record(a_row: dict[str, Any], b_row: dict[str, Any], *, a_name: str, b_name: str) -> dict[str, Any]:
    b_meta = b_row.get("metadata") or {}
    b_ic = _ic_state(b_meta)
    inc = b_ic.get("incumbent") or {}
    chl = b_ic.get("challenger") or {}
    return {
        "dataset": b_row.get("dataset"),
        "seed": int(b_row.get("seed", 0)),
        "budget": int(b_row.get("budget", 0)),
        "example_id": b_row.get("example_id"),
        "problem_statement": b_row.get("problem_statement"),
        "gold_answer": b_row.get("gold_answer"),
        "answer_a": a_row.get("prediction"),
        "answer_b": b_row.get("prediction"),
        "method_a": a_name,
        "method_b": b_name,
        "a_failure_group": a_row.get("failure_group"),
        "b_failure_group": b_row.get("failure_group"),
        "a_subtype": a_row.get("wrong_commit_subtype"),
        "b_subtype": b_row.get("wrong_commit_subtype"),
        "incumbent_group": inc,
        "challenger_group": chl,
        "raw_support": {
            "incumbent": _safe_float(inc.get("support_fraction_raw", 0.0)),
            "challenger": _safe_float(chl.get("support_fraction_raw", 0.0)),
        },
        "effective_support": {
            "incumbent": _safe_float(inc.get("support_fraction_effective", 0.0)),
            "challenger": _safe_float(chl.get("support_fraction_effective", 0.0)),
            "gap": _safe_float(b_ic.get("effective_support_gap", 0.0)),
        },
        "margin": {
            "score_margin": _safe_float(b_ic.get("score_margin", 0.0)),
            "answer_group_margin": _safe_float(b_meta.get("answer_group_margin", 0.0)),
        },
        "switch_behavior": {
            "incumbent_changed_recently": bool(b_ic.get("incumbent_changed_recently", False)),
            "incumbent_stable_steps": int(b_ic.get("incumbent_stable_steps", 0)),
            "decision": str(b_ic.get("decision", "")),
        },
        "note": "",
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Bounded ICC refinement pass focused on wrong-commit subtype residuals")
    p.add_argument("--bundle", default="exact_answer_math_expansion")
    p.add_argument("--datasets", default="")
    p.add_argument("--subset-size", type=int, default=30)
    p.add_argument("--seeds", default="11,23,37,41,53")
    p.add_argument("--budgets", default="4,6,8,10")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/incumbent_challenger_refinement_pass_20260419")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()] if args.datasets.strip() else _load_exact_bundle_datasets(args.bundle)
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)
    adaptive_grid = _parse_ints(args.adaptive_grid)

    methods = [BASE, ICC, ICC_RAW, ICC_LATE_GUARD, ICC_SWITCH_PERSIST]
    refinement_methods = [ICC_LATE_GUARD, ICC_SWITCH_PERSIST]

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    dataset_load_issues: list[dict[str, str]] = []
    rng_master = random.Random(20260419)

    for ds in datasets:
        for seed in seeds:
            try:
                examples = load_pilot_examples(ds, args.subset_size, seed)
            except Exception as exc:
                dataset_load_issues.append({"dataset": ds, "seed": str(seed), "error": f"{type(exc).__name__}: {exc}"})
                continue
            rng = random.Random(rng_master.randint(0, 10**9))
            factory = generator_factory_for_mode(False, rng, "gpt-4.1-mini", 0.2, 180, 45)
            for budget in budgets:
                strategies = build_frontier_strategies(
                    factory,
                    budget,
                    adaptive_grid,
                    rng,
                    use_openai_api=False,
                    include_selective_sc_hybrid_methods=True,
                    include_broad_diversity_aggregation_methods=True,
                )
                strategies = {k: v for k, v in strategies.items() if k in methods}
                for ex in examples:
                    for m, ctrl in strategies.items():
                        run = ctrl.run(ex.question, ex.answer)
                        row = {
                            "dataset": ds,
                            "seed": int(seed),
                            "budget": int(budget),
                            "example_id": ex.example_id,
                            "problem_statement": ex.question,
                            "gold_answer": ex.answer,
                            "method": m,
                            "prediction": run.prediction,
                            "is_correct": bool(run.is_correct),
                            "actions_used": int(run.actions_used),
                            "expansions": int(run.expansions),
                            "verifications": int(run.verifications),
                            "budget_exhausted": bool(run.budget_exhausted),
                            "metadata": run.metadata,
                        }
                        row["failure_group"] = _failure_group(row)
                        row["wrong_commit_subtype"] = _wrong_commit_subtype(row)
                        rows.append(row)

    (out_dir / "per_example_results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_method[str(r["method"])].append(r)

    subtype_keys = [
        "wrong_early_commit",
        "wrong_late_commit",
        "wrong_incumbent_replacement",
        "wrong_commit_under_fragmented_support",
        "wrong_commit_under_near_tie",
        "wrong_commit_despite_weak_challenger_separation",
        "wrong_commit_other",
    ]

    per_method: dict[str, dict[str, Any]] = {}
    for m in methods:
        mr = by_method.get(m, [])
        n = max(1, len(mr))
        near_tie_rows = [x for x in mr if _safe_float((x.get("metadata") or {}).get("answer_group_margin", 0.0)) <= 0.20]
        subtype_counter = Counter(x["wrong_commit_subtype"] for x in mr if x["failure_group"] == "wrong_commit_timing")
        per_method[m] = {
            "n_examples": len(mr),
            "accuracy": sum(int(x["is_correct"]) for x in mr) / n,
            "wrong_commit_timing_count": sum(1 for x in mr if x["failure_group"] == "wrong_commit_timing"),
            "near_tie_accuracy": _mean([float(x["is_correct"]) for x in near_tie_rows]),
            "intervention_count": sum(int((x.get("metadata") or {}).get("incumbent_challenger_intervention_count", 0)) for x in mr),
            "incumbent_switch_recent_count": sum(int(bool((_ic_state(x.get("metadata") or {})).get("incumbent_changed_recently", False))) for x in mr),
            "wrong_commit_subtypes": {k: int(subtype_counter.get(k, 0)) for k in subtype_keys},
        }

    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        key = (str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        aligned[key][str(r["method"])] = r

    # subtype-level diagnosis: base vs dep, dep vs raw
    subtype_shift = {
        "base_to_dependence_aware": {k: int(per_method[ICC]["wrong_commit_subtypes"][k] - per_method[BASE]["wrong_commit_subtypes"][k]) for k in subtype_keys},
        "dependence_aware_to_raw_support": {k: int(per_method[ICC_RAW]["wrong_commit_subtypes"][k] - per_method[ICC]["wrong_commit_subtypes"][k]) for k in subtype_keys},
    }

    subtype_dataset_concentration: dict[str, dict[str, dict[str, int]]] = {}
    for m in [BASE, ICC, ICC_RAW, *refinement_methods]:
        counts: dict[str, Counter[str]] = {k: Counter() for k in subtype_keys}
        for r in by_method[m]:
            st = str(r.get("wrong_commit_subtype", ""))
            if st in counts:
                counts[st][str(r.get("dataset"))] += 1
        subtype_dataset_concentration[m] = {k: dict(v) for k, v in counts.items()}

    subtype_context_concentration: dict[str, dict[str, dict[str, int]]] = {}
    for m in [BASE, ICC, ICC_RAW, *refinement_methods]:
        bucket = {k: {"near_tie": 0, "fragmented": 0, "switch_recent": 0} for k in subtype_keys}
        for r in by_method[m]:
            st = str(r.get("wrong_commit_subtype", ""))
            if st not in bucket:
                continue
            meta = r.get("metadata") or {}
            ic = _ic_state(meta)
            bucket[st]["near_tie"] += int(bool(ic.get("near_tie", False) or _safe_float(meta.get("answer_group_margin", 1.0)) <= 0.20))
            bucket[st]["fragmented"] += int(bool(ic.get("challenger_fragmented_flag", False)))
            bucket[st]["switch_recent"] += int(bool(ic.get("incumbent_changed_recently", False)))
        subtype_context_concentration[m] = bucket

    # harmed-case mining for dependence-aware vs base
    harmed_dep_vs_base: list[dict[str, Any]] = []
    for pair in aligned.values():
        if BASE not in pair or ICC not in pair:
            continue
        b = pair[BASE]
        d = pair[ICC]
        if bool(b["is_correct"]) and not bool(d["is_correct"]):
            rec = _case_record(b, d, a_name=BASE, b_name=ICC)
            rec["note"] = "Dependence-aware ICC harmed this base-correct case."
            harmed_dep_vs_base.append(rec)

    harmed_dep_groups = {
        "by_subtype": dict(Counter(str(r.get("b_subtype", "")) for r in harmed_dep_vs_base)),
        "by_dataset": dict(Counter(str(r.get("dataset", "")) for r in harmed_dep_vs_base)),
        "by_margin_regime": {
            "very_low_margin_le_0.02": sum(1 for r in harmed_dep_vs_base if _safe_float((r.get("margin") or {}).get("score_margin", 0.0)) <= 0.02),
            "low_margin_0.02_0.05": sum(1 for r in harmed_dep_vs_base if 0.02 < _safe_float((r.get("margin") or {}).get("score_margin", 0.0)) <= 0.05),
            "higher_margin_gt_0.05": sum(1 for r in harmed_dep_vs_base if _safe_float((r.get("margin") or {}).get("score_margin", 0.0)) > 0.05),
        },
        "support_disagreement": {
            "eff_minus_raw_gap_gt_0.05": sum(
                1
                for r in harmed_dep_vs_base
                if abs(
                    _safe_float((r.get("effective_support") or {}).get("incumbent", 0.0))
                    - _safe_float((r.get("raw_support") or {}).get("incumbent", 0.0))
                ) > 0.05
            ),
            "eff_minus_raw_gap_le_0.05": sum(
                1
                for r in harmed_dep_vs_base
                if abs(
                    _safe_float((r.get("effective_support") or {}).get("incumbent", 0.0))
                    - _safe_float((r.get("raw_support") or {}).get("incumbent", 0.0))
                ) <= 0.05
            ),
        },
        "switch_behavior": {
            "incumbent_changed_recently": sum(1 for r in harmed_dep_vs_base if bool((r.get("switch_behavior") or {}).get("incumbent_changed_recently", False))),
            "stable_no_recent_change": sum(1 for r in harmed_dep_vs_base if not bool((r.get("switch_behavior") or {}).get("incumbent_changed_recently", False))),
        },
    }

    # registries for each refinement vs dependence-aware ICC
    refinement_registry_summary: dict[str, dict[str, int]] = {}
    refinement_diagnostics: dict[str, dict[str, Any]] = {}
    for refined in refinement_methods:
        improved: list[dict[str, Any]] = []
        harmed: list[dict[str, Any]] = []
        unchanged: list[dict[str, Any]] = []
        for pair in aligned.values():
            if ICC not in pair or refined not in pair:
                continue
            d = pair[ICC]
            r = pair[refined]
            rec = _case_record(d, r, a_name=ICC, b_name=refined)
            if (not bool(d["is_correct"])) and bool(r["is_correct"]):
                rec["note"] = "Refinement fixed a dependence-aware ICC miss."
                improved.append(rec)
            elif bool(d["is_correct"]) and (not bool(r["is_correct"])):
                rec["note"] = "Refinement harmed a dependence-aware ICC correct case."
                harmed.append(rec)
            else:
                rec["note"] = "No correctness change versus dependence-aware ICC."
                unchanged.append(rec)

        (out_dir / f"improved_cases_{refined}_vs_icc_dep.json").write_text(json.dumps(improved, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / f"harmed_cases_{refined}_vs_icc_dep.json").write_text(json.dumps(harmed, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / f"unchanged_cases_{refined}_vs_icc_dep.json").write_text(json.dumps(unchanged, indent=2, ensure_ascii=False), encoding="utf-8")

        refinement_registry_summary[refined] = {"improved": len(improved), "harmed": len(harmed), "unchanged": len(unchanged)}
        refinement_diagnostics[refined] = {
            "delta_accuracy_vs_icc_dep": float(per_method[refined]["accuracy"] - per_method[ICC]["accuracy"]),
            "delta_wrong_commit_timing_vs_icc_dep": int(per_method[refined]["wrong_commit_timing_count"] - per_method[ICC]["wrong_commit_timing_count"]),
            "delta_near_tie_accuracy_vs_icc_dep": float(per_method[refined]["near_tie_accuracy"] - per_method[ICC]["near_tie_accuracy"]),
            "delta_wrong_commit_subtypes_vs_icc_dep": {
                k: int(per_method[refined]["wrong_commit_subtypes"][k] - per_method[ICC]["wrong_commit_subtypes"][k]) for k in subtype_keys
            },
            "improved_harmed_unchanged_vs_icc_dep": refinement_registry_summary[refined],
            "harmed_by_dataset_vs_icc_dep": dict(Counter(str(r.get("dataset", "")) for r in harmed)),
        }

    failure_shift = {m: dict(Counter(str(r.get("failure_group", "")) for r in by_method[m])) for m in methods}

    aggregate = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "datasets": datasets,
        "dataset_load_issues": dataset_load_issues,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "methods": methods,
        "refinement_methods": refinement_methods,
        "per_method": per_method,
        "failure_shift": failure_shift,
        "subtype_shift": subtype_shift,
        "subtype_dataset_concentration": subtype_dataset_concentration,
        "subtype_context_concentration": subtype_context_concentration,
        "harmed_case_mining_dependence_aware_vs_base": harmed_dep_groups,
        "refinement_registry_summary": refinement_registry_summary,
        "refinement_diagnostics": refinement_diagnostics,
        "delta_vs_base": {
            m: {
                "accuracy": float(per_method[m]["accuracy"] - per_method[BASE]["accuracy"]),
                "wrong_commit_timing_count": int(per_method[m]["wrong_commit_timing_count"] - per_method[BASE]["wrong_commit_timing_count"]),
            }
            for m in methods
            if m != BASE
        },
    }

    (out_dir / "aggregate_comparison_metrics.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    (out_dir / "per_method_metrics.json").write_text(json.dumps(per_method, indent=2), encoding="utf-8")
    (out_dir / "subtype_shift_summary.json").write_text(json.dumps({"subtype_shift": subtype_shift, "subtype_keys": subtype_keys}, indent=2), encoding="utf-8")
    (out_dir / "refinement_specific_diagnostics.json").write_text(json.dumps(refinement_diagnostics, indent=2), encoding="utf-8")
    (out_dir / "harmed_case_mining_dependence_aware_vs_base.json").write_text(json.dumps(harmed_dep_groups, indent=2), encoding="utf-8")

    run_manifest = {
        "script": "scripts/run_incumbent_challenger_refinement_pass_20260419.py",
        "command": f"python scripts/run_incumbent_challenger_refinement_pass_20260419.py --output-dir {args.output_dir}",
        "bundle": args.bundle,
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "methods": methods,
        "refinement_methods": refinement_methods,
        "refinement_rationale": {
            ICC_LATE_GUARD: "Residual wrong-late-commit dominates; reduce commit delay and margin threshold to permit earlier commits when incumbent is stable.",
            ICC_SWITCH_PERSIST: "Protect against harmed replacement commits by requiring stronger incumbent stability persistence before commit.",
        },
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    # status note with required explicit answers
    residual = sorted(per_method[ICC]["wrong_commit_subtypes"].items(), key=lambda kv: kv[1], reverse=True)[0]
    best_ref = max(refinement_methods, key=lambda m: (per_method[m]["accuracy"] - per_method[ICC]["accuracy"], -(per_method[m]["wrong_commit_timing_count"] - per_method[ICC]["wrong_commit_timing_count"])))
    beats_icc = [
        m
        for m in refinement_methods
        if float(per_method[m]["accuracy"]) >= float(per_method[ICC]["accuracy"])
        and int(per_method[m]["wrong_commit_timing_count"]) <= int(per_method[ICC]["wrong_commit_timing_count"])
    ]

    status = [
        "# ICC bounded refinement-and-diagnosis status (2026-04-19)",
        "",
        "## Required direct answers",
        f"- Which wrong-commit subtype is now the main residual bottleneck? `{residual[0]}` with count {residual[1]} under dependence-aware ICC.",
        f"- Which refinement helped most? `{best_ref}` by the bounded comparison objective (accuracy first, then wrong-commit reduction).",
        f"- Did any refinement beat the current dependence-aware ICC? {'yes: ' + ', '.join(beats_icc) if beats_icc else 'no'}.",
        f"- Is ICC now strong enough to be treated as the canonical leading method line? {'yes' if float(per_method[ICC]['accuracy']) >= float(per_method[BASE]['accuracy']) and int(per_method[ICC]['wrong_commit_timing_count']) < int(per_method[BASE]['wrong_commit_timing_count']) else 'not yet'}.",
        "- What is the single best next step after this pass? Run one bounded calibration around the winning refinement on the residual subtype only (small margin/stability grid).",
        "",
        "## Key deltas",
        f"- Dependence-aware ICC vs base: accuracy {per_method[ICC]['accuracy']-per_method[BASE]['accuracy']:+.4f}, wrong_commit_timing {int(per_method[ICC]['wrong_commit_timing_count'])-int(per_method[BASE]['wrong_commit_timing_count'])}.",
        f"- Raw ICC vs base: accuracy {per_method[ICC_RAW]['accuracy']-per_method[BASE]['accuracy']:+.4f}, wrong_commit_timing {int(per_method[ICC_RAW]['wrong_commit_timing_count'])-int(per_method[BASE]['wrong_commit_timing_count'])}.",
    ]
    for m in refinement_methods:
        status.append(
            f"- {m} vs dependence-aware ICC: accuracy {per_method[m]['accuracy']-per_method[ICC]['accuracy']:+.4f}, wrong_commit_timing {int(per_method[m]['wrong_commit_timing_count'])-int(per_method[ICC]['wrong_commit_timing_count'])}."
        )
    (out_dir / "STATUS_NOTE_icc_refinement_pass_20260419.md").write_text("\n".join(status) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
