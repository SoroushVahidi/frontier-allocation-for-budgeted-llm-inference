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


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _std(xs: list[float]) -> float:
    return float(statistics.pstdev(xs)) if len(xs) > 1 else 0.0


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _ic_state(meta: dict[str, Any]) -> dict[str, Any]:
    checks = meta.get("incumbent_challenger_checks") or []
    if not checks:
        return {}
    return checks[-1]


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
        if bool(ic.get("challenger_plausible", False)) or _safe_float(ic.get("score_margin", 0.0)) <= _safe_float((ic.get("thresholds") or {}).get("challenger_plausible_gap", 0.05)) + 0.01:
            return "wrong_commit_despite_weak_challenger_separation"
        return "wrong_early_commit"

    if not bool(m.get("commit_triggered", False)) and (bool(row.get("budget_exhausted", False)) or actions >= max(1, budget - 1)):
        return "wrong_late_commit"

    if bool(ic.get("incumbent_changed_recently", False)) and _safe_float(ic.get("score_margin", 0.0)) < _safe_float((ic.get("thresholds") or {}).get("margin_threshold", 0.10)) + 0.02:
        return "wrong_incumbent_replacement"

    if near_tie_flag:
        return "wrong_commit_under_near_tie"
    if fragmented_flag:
        return "wrong_commit_under_fragmented_support"
    if bool(ic.get("challenger_plausible", False)):
        return "wrong_commit_despite_weak_challenger_separation"
    return "wrong_commit_other"


def _load_exact_bundle_datasets(bundle_name: str) -> list[str]:
    bundles_path = REPO_ROOT / "configs/dataset_experiment_readiness_bundles.json"
    payload = json.loads(bundles_path.read_text(encoding="utf-8"))
    bundles = payload.get("bundles") or {}
    info = bundles.get(bundle_name) or {}
    datasets = [str(d) for d in info.get("datasets") or []]
    return datasets


def _build_case_record(base_row: dict[str, Any], new_row: dict[str, Any], *, variant_name: str) -> dict[str, Any]:
    new_meta = new_row.get("metadata") or {}
    new_ic = _ic_state(new_meta)
    inc = new_ic.get("incumbent") or {}
    chl = new_ic.get("challenger") or {}
    return {
        "variant": variant_name,
        "dataset": new_row.get("dataset"),
        "seed": int(new_row.get("seed", 0)),
        "budget": int(new_row.get("budget", 0)),
        "example_id": new_row.get("example_id"),
        "problem_statement": new_row.get("problem_statement"),
        "gold_answer": new_row.get("gold_answer"),
        "base_answer": base_row.get("prediction"),
        "new_answer": new_row.get("prediction"),
        "base_failure_group": base_row.get("failure_group"),
        "new_failure_group": new_row.get("failure_group"),
        "base_wrong_commit_subtype": base_row.get("wrong_commit_subtype"),
        "new_wrong_commit_subtype": new_row.get("wrong_commit_subtype"),
        "incumbent_group": inc,
        "challenger_group": chl,
        "raw_support": {
            "incumbent": _safe_float(inc.get("support_fraction_raw", 0.0)),
            "challenger": _safe_float(chl.get("support_fraction_raw", 0.0)),
            "gap": _safe_float(inc.get("support_fraction_raw", 0.0)) - _safe_float(chl.get("support_fraction_raw", 0.0)),
        },
        "effective_support": {
            "incumbent": _safe_float(inc.get("support_fraction_effective", 0.0)),
            "challenger": _safe_float(chl.get("support_fraction_effective", 0.0)),
            "gap": _safe_float(new_ic.get("effective_support_gap", 0.0)),
        },
        "margin_readiness": {
            "score_margin": _safe_float(new_ic.get("score_margin", 0.0)),
            "incumbent_readiness": _safe_float(inc.get("readiness_mean", 0.0)),
            "challenger_readiness": _safe_float(chl.get("readiness_mean", 0.0)),
            "answer_group_margin": _safe_float(new_meta.get("answer_group_margin", 0.0)),
            "commit_readiness_q_commit": _safe_float(new_meta.get("commit_readiness_q_commit", 0.0)),
        },
        "ic_decision_state": {
            "decision": new_ic.get("decision"),
            "commit_ready": bool(new_ic.get("commit_ready", False)),
            "near_tie": bool(new_ic.get("near_tie", False)),
            "challenger_plausible": bool(new_ic.get("challenger_plausible", False)),
            "challenger_fragmented_flag": bool(new_ic.get("challenger_fragmented_flag", False)),
            "incumbent_changed_recently": bool(new_ic.get("incumbent_changed_recently", False)),
            "incumbent_stable_steps": int(new_ic.get("incumbent_stable_steps", 0)),
        },
        "commit_subtype": new_row.get("wrong_commit_subtype"),
        "note": "",
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Stronger matched validation for incumbent/challenger commit control")
    p.add_argument("--bundle", default="exact_answer_math_expansion")
    p.add_argument("--datasets", default="")
    p.add_argument("--subset-size", type=int, default=30)
    p.add_argument("--seeds", default="11,23,37,41,53")
    p.add_argument("--budgets", default="4,6,8,10")
    p.add_argument("--adaptive-grid", default="1")
    p.add_argument("--output-dir", default="outputs/incumbent_challenger_commit_validation_20260419")
    args = p.parse_args()

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()] if args.datasets.strip() else _load_exact_bundle_datasets(args.bundle)
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)
    adaptive_grid = _parse_ints(args.adaptive_grid)

    methods = [BASE, ICC, ICC_RAW]

    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rng_master = random.Random(20260419)
    rows: list[dict[str, Any]] = []
    dataset_load_issues: list[dict[str, str]] = []

    for dataset in datasets:
        for seed in seeds:
            try:
                examples = load_pilot_examples(dataset, args.subset_size, seed)
            except Exception as exc:
                dataset_load_issues.append({"dataset": dataset, "seed": str(seed), "error": f"{type(exc).__name__}: {exc}"})
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
                    for name, ctrl in strategies.items():
                        r = ctrl.run(ex.question, ex.answer)
                        row = {
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "example_id": ex.example_id,
                            "problem_statement": ex.question,
                            "gold_answer": ex.answer,
                            "method": name,
                            "prediction": r.prediction,
                            "is_correct": bool(r.is_correct),
                            "actions_used": int(r.actions_used),
                            "expansions": int(r.expansions),
                            "verifications": int(r.verifications),
                            "budget_exhausted": bool(r.budget_exhausted),
                            "metadata": r.metadata,
                        }
                        row["failure_group"] = _failure_group(row)
                        row["wrong_commit_subtype"] = _wrong_commit_subtype(row)
                        rows.append(row)

    (out_dir / "per_example_results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    by_method = defaultdict(list)
    for r in rows:
        by_method[r["method"]].append(r)

    per_method: dict[str, dict[str, float | int]] = {}
    for m in methods:
        mr = by_method.get(m, [])
        n = max(1, len(mr))
        near_tie_rows = [x for x in mr if _safe_float((x.get("metadata") or {}).get("answer_group_margin", 0.0)) <= 0.20]
        per_method[m] = {
            "n_examples": len(mr),
            "accuracy": sum(int(x["is_correct"]) for x in mr) / n,
            "avg_actions": sum(float(x["actions_used"]) for x in mr) / n,
            "avg_expansions": sum(float(x["expansions"]) for x in mr) / n,
            "wrong_commit_timing_count": sum(1 for x in mr if x["failure_group"] == "wrong_commit_timing"),
            "wrong_commit_timing_rate": sum(1 for x in mr if x["failure_group"] == "wrong_commit_timing") / n,
            "near_tie_count": len(near_tie_rows),
            "near_tie_accuracy": _mean([float(x["is_correct"]) for x in near_tie_rows]),
            "ic_intervention_count": sum(int((x.get("metadata") or {}).get("incumbent_challenger_intervention_count", 0)) for x in mr),
            "ic_commit_triggered_count": sum(int(bool((x.get("metadata") or {}).get("incumbent_challenger_commit_triggered", False))) for x in mr),
            "mean_regret_proxy": _mean([
                max(0.0, _safe_float((x.get("metadata") or {}).get("one_step_continuation_minus_commit", 0.0)))
                for x in mr
            ]),
        }

    aligned: dict[tuple[str, int, int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        k = (str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        aligned[k][str(r["method"])] = r

    improved_dep: list[dict[str, Any]] = []
    harmed_dep: list[dict[str, Any]] = []
    unchanged_dep: list[dict[str, Any]] = []
    improved_raw: list[dict[str, Any]] = []
    harmed_raw: list[dict[str, Any]] = []
    unchanged_raw: list[dict[str, Any]] = []

    for pair in aligned.values():
        if BASE in pair and ICC in pair:
            b = pair[BASE]
            n = pair[ICC]
            rec = _build_case_record(b, n, variant_name="dependence_aware")
            if (not b["is_correct"]) and n["is_correct"]:
                rec["note"] = "Dependence-aware incumbent/challenger state improved final selection relative to base."
                improved_dep.append(rec)
            elif b["is_correct"] and (not n["is_correct"]):
                rec["note"] = "Dependence-aware variant harmed a previously correct base case."
                harmed_dep.append(rec)
            else:
                rec["note"] = "No correctness change versus base."
                unchanged_dep.append(rec)
        if BASE in pair and ICC_RAW in pair:
            b = pair[BASE]
            n = pair[ICC_RAW]
            rec = _build_case_record(b, n, variant_name="raw_support")
            if (not b["is_correct"]) and n["is_correct"]:
                rec["note"] = "Raw-support incumbent/challenger state improved final selection relative to base."
                improved_raw.append(rec)
            elif b["is_correct"] and (not n["is_correct"]):
                rec["note"] = "Raw-support variant harmed a previously correct base case."
                harmed_raw.append(rec)
            else:
                rec["note"] = "No correctness change versus base."
                unchanged_raw.append(rec)

    (out_dir / "improved_cases_dependence_aware.json").write_text(json.dumps(improved_dep, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "harmed_cases_dependence_aware.json").write_text(json.dumps(harmed_dep, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "unchanged_cases_dependence_aware.json").write_text(json.dumps(unchanged_dep, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "improved_cases_raw_support.json").write_text(json.dumps(improved_raw, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "harmed_cases_raw_support.json").write_text(json.dumps(harmed_raw, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "unchanged_cases_raw_support.json").write_text(json.dumps(unchanged_raw, indent=2, ensure_ascii=False), encoding="utf-8")

    failure_shift = {
        "base": dict(Counter(r["failure_group"] for r in by_method[BASE])),
        "icc_dependence_aware": dict(Counter(r["failure_group"] for r in by_method[ICC])),
        "icc_raw_support": dict(Counter(r["failure_group"] for r in by_method[ICC_RAW])),
    }
    subtype_keys = [
        "wrong_early_commit",
        "wrong_late_commit",
        "wrong_incumbent_replacement",
        "wrong_commit_under_fragmented_support",
        "wrong_commit_under_near_tie",
        "wrong_commit_despite_weak_challenger_separation",
        "wrong_commit_other",
    ]
    subtype_shift = {
        "base": {k: int(Counter(r["wrong_commit_subtype"] for r in by_method[BASE] if r["failure_group"] == "wrong_commit_timing").get(k, 0)) for k in subtype_keys},
        "icc_dependence_aware": {k: int(Counter(r["wrong_commit_subtype"] for r in by_method[ICC] if r["failure_group"] == "wrong_commit_timing").get(k, 0)) for k in subtype_keys},
        "icc_raw_support": {k: int(Counter(r["wrong_commit_subtype"] for r in by_method[ICC_RAW] if r["failure_group"] == "wrong_commit_timing").get(k, 0)) for k in subtype_keys},
    }

    def _diag(rows_in: list[dict[str, Any]]) -> dict[str, float | int]:
        margins: list[float] = []
        eff_gap: list[float] = []
        raw_gap: list[float] = []
        early = 0
        late = 0
        weak_sep = 0
        frag = 0
        for r in rows_in:
            st = _ic_state(r.get("metadata") or {})
            if st:
                margins.append(_safe_float(st.get("score_margin", 0.0)))
                eff_gap.append(_safe_float(st.get("effective_support_gap", 0.0)))
                inc = st.get("incumbent") or {}
                chl = st.get("challenger") or {}
                raw_gap.append(_safe_float(inc.get("support_fraction_raw", 0.0)) - _safe_float(chl.get("support_fraction_raw", 0.0)))
            subtype = str(r.get("wrong_commit_subtype", ""))
            early += int(subtype == "wrong_early_commit")
            late += int(subtype == "wrong_late_commit")
            weak_sep += int(subtype == "wrong_commit_despite_weak_challenger_separation")
            frag += int(subtype == "wrong_commit_under_fragmented_support")
        return {
            "n_ic_states": len(margins),
            "mean_score_margin": _mean(margins),
            "std_score_margin": _std(margins),
            "mean_effective_support_gap": _mean(eff_gap),
            "mean_raw_support_gap": _mean(raw_gap),
            "wrong_early_commit": early,
            "wrong_late_commit": late,
            "wrong_commit_despite_weak_challenger_separation": weak_sep,
            "wrong_commit_under_fragmented_support": frag,
        }

    dep_diag = _diag(by_method[ICC])
    raw_diag = _diag(by_method[ICC_RAW])
    dep_vs_raw = {
        "dependence_aware": dep_diag,
        "raw_support": raw_diag,
        "delta_dependence_minus_raw": {
            "accuracy": float(per_method[ICC]["accuracy"] - per_method[ICC_RAW]["accuracy"]),
            "wrong_commit_timing_count": int(per_method[ICC]["wrong_commit_timing_count"] - per_method[ICC_RAW]["wrong_commit_timing_count"]),
            "near_tie_accuracy": float(per_method[ICC]["near_tie_accuracy"] - per_method[ICC_RAW]["near_tie_accuracy"]),
            "mean_score_margin": float(dep_diag["mean_score_margin"] - raw_diag["mean_score_margin"]),
            "mean_effective_support_gap": float(dep_diag["mean_effective_support_gap"] - raw_diag["mean_effective_support_gap"]),
        },
    }

    subtype_assignment_rules = {
        "wrong_early_commit": "wrong_commit_timing + commit_triggered + actions_used <= budget-2, unless near-tie/fragmented/weak-separation rules fire first.",
        "wrong_late_commit": "wrong_commit_timing + no commit_triggered + budget exhausted or actions_used >= budget-1.",
        "wrong_incumbent_replacement": "wrong_commit_timing + incumbent_changed_recently and low score_margin around threshold.",
        "wrong_commit_under_fragmented_support": "wrong_commit_timing + challenger_fragmented_flag or high-group-fragmentation proxy (>=3 groups with low top support or high entropy).",
        "wrong_commit_under_near_tie": "wrong_commit_timing + near_tie/ambiguity flags or low answer_group_margin proxy.",
        "wrong_commit_despite_weak_challenger_separation": "wrong_commit_timing + challenger_plausible/low-margin separation despite commit behavior.",
        "wrong_commit_other": "wrong_commit_timing with no subtype rule match.",
    }

    aggregate = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "methods": methods,
        "datasets_requested": datasets,
        "dataset_load_issues": dataset_load_issues,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "total_rows": len(rows),
        "per_method": per_method,
        "failure_shift": failure_shift,
        "wrong_commit_subtype_shift": subtype_shift,
        "wrong_commit_subtype_assignment_rules": subtype_assignment_rules,
        "dependence_vs_raw_comparison": dep_vs_raw,
        "improved_harmed_unchanged": {
            "dependence_aware": {
                "improved": len(improved_dep),
                "harmed": len(harmed_dep),
                "unchanged": len(unchanged_dep),
            },
            "raw_support": {
                "improved": len(improved_raw),
                "harmed": len(harmed_raw),
                "unchanged": len(unchanged_raw),
            },
        },
        "delta_vs_base": {
            "icc_dependence_aware": {
                "accuracy": float(per_method[ICC]["accuracy"] - per_method[BASE]["accuracy"]),
                "wrong_commit_timing_count": int(per_method[ICC]["wrong_commit_timing_count"] - per_method[BASE]["wrong_commit_timing_count"]),
                "near_tie_accuracy": float(per_method[ICC]["near_tie_accuracy"] - per_method[BASE]["near_tie_accuracy"]),
            },
            "icc_raw_support": {
                "accuracy": float(per_method[ICC_RAW]["accuracy"] - per_method[BASE]["accuracy"]),
                "wrong_commit_timing_count": int(per_method[ICC_RAW]["wrong_commit_timing_count"] - per_method[BASE]["wrong_commit_timing_count"]),
                "near_tie_accuracy": float(per_method[ICC_RAW]["near_tie_accuracy"] - per_method[BASE]["near_tie_accuracy"]),
            },
        },
    }

    (out_dir / "aggregate_comparison_metrics.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    (out_dir / "per_method_metrics.json").write_text(json.dumps(per_method, indent=2), encoding="utf-8")
    (out_dir / "wrong_commit_subtype_summary.json").write_text(json.dumps({"summary": subtype_shift, "rules": subtype_assignment_rules}, indent=2), encoding="utf-8")
    (out_dir / "failure_shift_summary.json").write_text(json.dumps(failure_shift, indent=2), encoding="utf-8")
    (out_dir / "dependence_vs_raw_comparison_diagnostics.json").write_text(json.dumps(dep_vs_raw, indent=2), encoding="utf-8")

    run_manifest = {
        "script": "scripts/run_incumbent_challenger_commit_validation_pass_20260419.py",
        "command": f"python scripts/run_incumbent_challenger_commit_validation_pass_20260419.py --output-dir {args.output_dir}",
        "bundle": args.bundle,
        "datasets_requested": datasets,
        "dataset_load_issues": dataset_load_issues,
        "seeds": seeds,
        "budgets": budgets,
        "subset_size": args.subset_size,
        "methods": methods,
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    delta_dep = aggregate["delta_vs_base"]["icc_dependence_aware"]
    delta_raw = aggregate["delta_vs_base"]["icc_raw_support"]
    dep_better_wrong_commit = int(per_method[ICC]["wrong_commit_timing_count"]) < int(per_method[ICC_RAW]["wrong_commit_timing_count"])
    dep_better_acc = float(per_method[ICC]["accuracy"]) >= float(per_method[ICC_RAW]["accuracy"])

    status = [
        "# Incumbent-vs-challenger commit stronger matched validation status (2026-04-19)",
        "",
        "## Explicit answers to required questions",
        f"- Is incumbent-vs-challenger commit control still improving on stronger validation? {'Yes' if float(delta_dep['accuracy']) >= 0.0 and int(delta_dep['wrong_commit_timing_count']) <= 0 else 'No_or_mixed'}.",
        (
            "- Which wrong-commit subtypes does it fix best? "
            + ", ".join(
                f"{k}: {int(subtype_shift['base'].get(k, 0))}->{int(subtype_shift['icc_dependence_aware'].get(k, 0))}"
                for k in [
                    "wrong_early_commit",
                    "wrong_late_commit",
                    "wrong_commit_under_near_tie",
                    "wrong_commit_under_fragmented_support",
                    "wrong_commit_despite_weak_challenger_separation",
                    "wrong_incumbent_replacement",
                ]
            )
        ),
        (
            "- What kinds of cases does it still harm? "
            f"Dependence-aware harmed={len(harmed_dep)}, raw-support harmed={len(harmed_raw)}; "
            "inspect harmed registries for near-tie/fragmented/weak-separation concentration."
        ),
        (
            "- Is dependence-aware support truly better than raw support? "
            + (
                "Mixed: better wrong-commit reduction but weaker/equal accuracy."
                if dep_better_wrong_commit and not dep_better_acc
                else "Yes" if dep_better_wrong_commit and dep_better_acc else "No_or_mixed"
            )
        ),
        (
            "- Is this now the leading serious next method line for the repo? "
            + (
                "Yes (bounded)" if float(delta_dep["accuracy"]) >= 0.0 and int(delta_dep["wrong_commit_timing_count"]) <= 0 and len(improved_dep) >= len(harmed_dep) else "Not yet"
            )
        ),
        "- What is the single best next step after this pass? Run one bounded calibration pass on dependence-discount strength and margin threshold for near-tie + fragmented slices, keeping the same incumbent/challenger family.",
        "",
        "## Key metrics",
        f"- Base accuracy={per_method[BASE]['accuracy']:.4f}, ICC(dep)={per_method[ICC]['accuracy']:.4f} (delta {delta_dep['accuracy']:+.4f}), ICC(raw)={per_method[ICC_RAW]['accuracy']:.4f} (delta {delta_raw['accuracy']:+.4f}).",
        f"- wrong_commit_timing base={per_method[BASE]['wrong_commit_timing_count']}, ICC(dep)={per_method[ICC]['wrong_commit_timing_count']} (delta {delta_dep['wrong_commit_timing_count']}), ICC(raw)={per_method[ICC_RAW]['wrong_commit_timing_count']} (delta {delta_raw['wrong_commit_timing_count']}).",
        f"- Near-tie accuracy base={per_method[BASE]['near_tie_accuracy']:.4f}, ICC(dep)={per_method[ICC]['near_tie_accuracy']:.4f}, ICC(raw)={per_method[ICC_RAW]['near_tie_accuracy']:.4f}.",
        f"- Improved/harmed/unchanged (dep): {len(improved_dep)}/{len(harmed_dep)}/{len(unchanged_dep)}.",
        f"- Improved/harmed/unchanged (raw): {len(improved_raw)}/{len(harmed_raw)}/{len(unchanged_raw)}.",
    ]
    (out_dir / "STATUS_NOTE_incumbent_challenger_commit_validation_20260419.md").write_text("\n".join(status) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
