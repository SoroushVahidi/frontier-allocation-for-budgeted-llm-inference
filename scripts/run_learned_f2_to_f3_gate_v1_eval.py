#!/usr/bin/env python3
"""Train/evaluate learned strict post-F2 gate (force F3 vs release after F2).

This script preserves strict phased F1->F2->F3 law by learning only the post-F2
binary decision. Training labels are derived from strict_f2 vs strict_f3 outcomes
on a broader matched surface, and final evaluation includes held-out broader cases
plus the frozen 100-case failure slice as a diagnostic stress test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import load_pilot_examples

BASE_SUFFIX = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
METHODS = {
    "baseline": None,
    "strict_f2": f"{BASE_SUFFIX}_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1",
    "strict_f3": f"{BASE_SUFFIX}_hard_early_root_depth3_coverage_forced_v1__deterministic_output_layer_repair_v1",
    "strict_gate1": f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1",
    "strict_gate2": f"{BASE_SUFFIX}_hard_early_root_depth2_then_gate_v2_budget_aware_rescue__deterministic_output_layer_repair_v1",
}

LABEL_RELEASE = "release_after_f2"
LABEL_FORCE = "force_f3"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


HM = _load_module(REPO_ROOT / "scripts/build_hundred_current_full_vs_best_failure_statistics.py", "hundred_stats_for_learned_gate")
TW = _load_module(REPO_ROOT / "scripts/build_twenty_exact_current_full_vs_best_fresh.py", "twenty_for_learned_gate")


def _parse_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _hash_u01(key: str) -> float:
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    return int(h, 16) / float(16**12 - 1)


def _mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _same_family(raw: dict[str, Any]) -> bool:
    m = raw.get("metadata") or {}
    return bool(float(m.get("repeated_same_family_expansion_rate", 0.0)) > 0.0)


def _delta(base_ok: bool, new_ok: bool) -> str:
    if base_ok and new_ok:
        return "unchanged"
    if base_ok and (not new_ok):
        return "worsened"
    if (not base_ok) and new_ok:
        return "improved"
    return "unchanged"


def _classify(raw: dict[str, Any], gold_raw: str, dataset: str) -> tuple[str, bool, bool, str]:
    rep = TW.choose_repair_answer(
        final_nodes=list(raw["final_nodes"]),
        selected_group_hint=(raw.get("metadata") or {}).get("selected_group"),
        dataset=dataset,
        enable_rescue=True,
    )
    ans = rep.get("surfaced_final_answer_raw")
    ans_can = TW.canonicalize_answer(ans, dataset=dataset)
    gold_can = TW.canonicalize_answer(gold_raw, dataset=dataset)
    correct = bool(ans_can == gold_can and ans_can is not None)
    gold_in_tree = bool(TW._node_ids_with_answer(raw["final_nodes"], gold_can))
    if not gold_in_tree:
        failure = "absent_from_tree"
    else:
        failure = "correct" if correct else "present_not_selected"
    return failure, correct, gold_in_tree, str(ans)


def _frontier_score_stats(final_nodes: list[dict[str, Any]]) -> tuple[float, float, float]:
    scores = sorted([float(n.get("score", 0.0)) for n in final_nodes], reverse=True)
    if not scores:
        return 0.0, 0.0, 0.0
    best = scores[0]
    second = scores[1] if len(scores) > 1 else scores[0]
    gap = best - second
    conc = best / max(1e-9, sum(max(0.0, s) for s in scores))
    return best, gap, conc


def _feature_row(case_id: str, dataset: str, seed: int, budget: int, strict_f2_raw: dict[str, Any], strict_f3_ok: bool, strict_f2_ok: bool, strict_f3_gold_in_tree: bool, strict_f2_gold_in_tree: bool) -> dict[str, Any]:
    m = strict_f2_raw.get("metadata") or {}
    trace = list(m.get("action_trace") or [])
    final_nodes = list(strict_f2_raw.get("final_nodes") or [])

    fam_counts: dict[str, int] = {}
    fam_depth_max: dict[str, int] = {}
    consecutive = 0
    longest_consecutive = 0
    prev_fam = None
    for ev in trace:
        bid = str(ev.get("branch_id") or "")
        fam = bid.split("_")[0] if "_" in bid else bid
        if not fam:
            continue
        fam_counts[fam] = fam_counts.get(fam, 0) + 1
        if fam == prev_fam:
            consecutive += 1
        else:
            consecutive = 1
            prev_fam = fam
        longest_consecutive = max(longest_consecutive, consecutive)
    for n in final_nodes:
        fam = str(n.get("branch_family_id") or "")
        d = int(n.get("depth") or 0)
        if fam:
            fam_depth_max[fam] = max(fam_depth_max.get(fam, 0), d)

    action_total = max(1, len(trace))
    max_family_actions = max(fam_counts.values()) if fam_counts else 0
    dominant_family_share = float(max_family_actions / action_total)
    families_expanded = int(len(fam_counts))

    answer_support = m.get("answer_support_counts") if isinstance(m.get("answer_support_counts"), dict) else {}
    sup_vals = sorted([int(v) for v in answer_support.values()], reverse=True)
    sup_total = sum(sup_vals)
    top_sup = sup_vals[0] if sup_vals else 0
    second_sup = sup_vals[1] if len(sup_vals) > 1 else 0
    top_share = float(top_sup / sup_total) if sup_total > 0 else 0.0
    top_gap = float((top_sup - second_sup) / sup_total) if sup_total > 0 else 0.0

    best_score, best_gap, score_conc = _frontier_score_stats(final_nodes)

    max_depth = max(fam_depth_max.values()) if fam_depth_max else 0
    min_depth = min(fam_depth_max.values()) if fam_depth_max else 0
    depth_asym = int(max_depth - min_depth) if fam_depth_max else 0
    shallow_alt_alive = int(sum(1 for v in fam_depth_max.values() if v <= 2 and v > 0))

    active_heads = int(sum(1 for n in final_nodes if not bool(n.get("is_done")) and not bool(n.get("is_pruned"))))
    n_groups = int(len(answer_support))

    remaining_budget_after_f2 = int(m.get("hard_early_coverage_remaining_actions", 0))
    f3_lb = max(1, int(m.get("hard_early_coverage_actions_needed_lb", 1)))
    slack_ratio = float(remaining_budget_after_f2 / f3_lb)

    label = LABEL_FORCE if (strict_f3_ok and (not strict_f2_ok)) else LABEL_RELEASE
    tie_policy_reason = "release_pref_tie_or_non_improvement"
    if strict_f3_ok and strict_f2_ok:
        if strict_f3_gold_in_tree and (not strict_f2_gold_in_tree):
            label = LABEL_FORCE
            tie_policy_reason = "force_due_to_additional_tree_coverage"

    return {
        "case_id": case_id,
        "dataset": dataset,
        "seed": int(seed),
        "budget": int(budget),
        "target_label": label,
        "label_policy_reason": tie_policy_reason,
        "strict_f2_correct": int(strict_f2_ok),
        "strict_f3_correct": int(strict_f3_ok),
        "strict_f2_gold_in_tree": int(strict_f2_gold_in_tree),
        "strict_f3_gold_in_tree": int(strict_f3_gold_in_tree),
        "max_family_action_share_upto_f2": dominant_family_share,
        "longest_consecutive_same_family_run_upto_f2": int(longest_consecutive),
        "n_families_expanded_upto_f2": families_expanded,
        "dominant_family_share_upto_f2": dominant_family_share,
        "active_root_families_after_f2": int(sum(1 for v in fam_depth_max.values() if v > 0)),
        "n_distinct_answer_groups_after_f2": n_groups,
        "top_answer_group_support_share": top_share,
        "top_vs_second_support_gap": top_gap,
        "dominant_answer_group_share": top_share,
        "plausible_alternatives_alive_but_shallow": int(shallow_alt_alive >= 1 and n_groups >= 2),
        "best_frontier_score": best_score,
        "best_vs_second_frontier_score_gap": best_gap,
        "frontier_score_concentration": score_conc,
        "dominant_incumbent_after_f2": int(top_share >= 0.70 and best_gap >= 0.05),
        "max_realized_depth_per_family_end_f2": int(max_depth),
        "depth_asymmetry_across_families": depth_asym,
        "shallow_alternative_maturity_indicators": shallow_alt_alive,
        "n_expandable_heads_remaining_after_f2": active_heads,
        "remaining_budget_after_f2": remaining_budget_after_f2,
        "lower_bound_cost_to_finish_f3": f3_lb,
        "budget_slack_ratio": slack_ratio,
        "actions_upto_f2": int(strict_f2_raw.get("actions", 0)),
        "expansions_upto_f2": int(strict_f2_raw.get("expansions", 0)),
        "verifications_upto_f2": int(strict_f2_raw.get("verifications", 0)),
        "repeated_same_family_present_upto_f2": int(float(m.get("repeated_same_family_expansion_rate", 0.0)) > 0.0),
        "anti_collapse_repeat_penalty_trigger_count": int(m.get("repeat_penalty_trigger_count", 0)),
        "uncertainty_verify_steps": int(m.get("uncertainty_verify_steps", 0)),
    }


def _matrix(rows: list[dict[str, Any]], feats: list[str]) -> list[list[float]]:
    return [[float(r.get(f, 0.0)) for f in feats] for r in rows]


def _labels(rows: list[dict[str, Any]]) -> list[int]:
    return [1 if str(r["target_label"]) == LABEL_FORCE else 0 for r in rows]


def _fit_logreg(x: list[list[float]], y: list[int], *, lr: float = 0.05, steps: int = 1500, l2: float = 1e-3) -> tuple[list[float], float]:
    if not x:
        return [], 0.0
    d = len(x[0])
    w = [0.0] * d
    b = 0.0
    n = len(x)
    for _ in range(steps):
        gw = [0.0] * d
        gb = 0.0
        for xi, yi in zip(x, y):
            z = sum(wj * xj for wj, xj in zip(w, xi)) + b
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            diff = p - yi
            for j in range(d):
                gw[j] += diff * xi[j]
            gb += diff
        for j in range(d):
            gw[j] = gw[j] / n + l2 * w[j]
            w[j] -= lr * gw[j]
        b -= lr * (gb / n)
    return w, b


def _predict_logreg(x: list[list[float]], w: list[float], b: float) -> list[int]:
    out = []
    for xi in x:
        z = sum(wj * xj for wj, xj in zip(w, xi)) + b
        p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
        out.append(1 if p >= 0.5 else 0)
    return out


def _fit_decision_stump(x: list[list[float]], y: list[int], feats: list[str]) -> dict[str, Any]:
    best = {"feature": 0, "threshold": 0.0, "left": 0, "right": 0, "acc": -1.0}
    if not x:
        return best
    n = len(x)
    for j in range(len(feats)):
        vals = sorted(set(row[j] for row in x))
        if len(vals) <= 1:
            continue
        candidates = [(vals[i] + vals[i + 1]) / 2.0 for i in range(len(vals) - 1)]
        for th in candidates[:40]:
            left_idx = [i for i, row in enumerate(x) if row[j] <= th]
            right_idx = [i for i, row in enumerate(x) if row[j] > th]
            if not left_idx or not right_idx:
                continue
            left_vote = 1 if sum(y[i] for i in left_idx) >= (len(left_idx) / 2) else 0
            right_vote = 1 if sum(y[i] for i in right_idx) >= (len(right_idx) / 2) else 0
            pred = [left_vote if i in left_idx else right_vote for i in range(n)]
            acc = sum(int(pi == yi) for pi, yi in zip(pred, y)) / n
            if acc > best["acc"]:
                best = {"feature": j, "threshold": float(th), "left": int(left_vote), "right": int(right_vote), "acc": float(acc)}
    return best


def _predict_stump(x: list[list[float]], stump: dict[str, Any]) -> list[int]:
    j = int(stump.get("feature", 0))
    th = float(stump.get("threshold", 0.0))
    lv = int(stump.get("left", 0))
    rv = int(stump.get("right", 0))
    return [lv if row[j] <= th else rv for row in x]


def _acc(y: list[int], p: list[int]) -> float:
    if not y:
        return 0.0
    return float(sum(int(a == b) for a, b in zip(y, p)) / len(y))


def _confusion(y: list[int], p: list[int]) -> dict[str, int]:
    fp = sum(1 for yt, yp in zip(y, p) if yp == 1 and yt == 0)
    fn = sum(1 for yt, yp in zip(y, p) if yp == 0 and yt == 1)
    tp = sum(1 for yt, yp in zip(y, p) if yp == 1 and yt == 1)
    tn = sum(1 for yt, yp in zip(y, p) if yp == 0 and yt == 0)
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


def _split_bucket(case_id: str) -> str:
    u = _hash_u01(case_id)
    if u < 0.6:
        return "train"
    if u < 0.8:
        return "validation"
    return "heldout"


def _aggregate(rows: list[dict[str, Any]], method_keys: list[str], methods_map: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for k in method_keys:
        outcomes = Counter(r.get(f"{k}_vs_baseline_outcome", "") for r in rows if k != "baseline")
        out.append(
            {
                "method": k,
                "method_name": methods_map.get(k, ""),
                "n_cases": len(rows),
                "accuracy": _mean([1.0 if r[f"{k}_correct"] else 0.0 for r in rows]),
                "absent_from_tree": sum(1 for r in rows if r[f"{k}_failure_type"] == "absent_from_tree"),
                "present_not_selected": sum(1 for r in rows if r[f"{k}_failure_type"] == "present_not_selected"),
                "repeated_same_family_present": sum(1 for r in rows if r[f"{k}_repeated_same_family_present"]),
                "gold_in_tree": sum(1 for r in rows if r[f"{k}_gold_in_tree"]),
                "avg_actions": _mean([float(r[f"{k}_actions"]) for r in rows]),
                "avg_expansions": _mean([float(r[f"{k}_expansions"]) for r in rows]),
                "avg_verifications": _mean([float(r[f"{k}_verifications"]) for r in rows]),
                "improved_vs_baseline": int(outcomes.get("improved", 0)),
                "worsened_vs_baseline": int(outcomes.get("worsened", 0)),
                "unchanged_vs_baseline": int(outcomes.get("unchanged", 0)),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", default="openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,olympiadbench")
    ap.add_argument("--subset-size", type=int, default=12)
    ap.add_argument("--seeds", default="11,23")
    ap.add_argument("--budgets", default="6,8")
    ap.add_argument(
        "--frozen-per-case-json",
        type=Path,
        default=REPO_ROOT / "outputs/hundred_current_full_vs_best_failure_statistics_20260420T220416Z/per_case_failure_statistics.json",
    )
    ap.add_argument("--frozen-limit", type=int, default=100)
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/learned_f2_to_f3_gate_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    methods = dict(METHODS)
    methods["baseline"] = TW._resolve_current_full_method()

    datasets = _parse_list(args.datasets)
    seeds = _parse_ints(args.seeds)
    budgets = _parse_ints(args.budgets)

    features: list[dict[str, Any]] = []
    broader_rows: list[dict[str, Any]] = []

    for dataset in datasets:
        for seed in seeds:
            examples = load_pilot_examples(dataset, int(args.subset_size), seed)
            for budget in budgets:
                for ex in examples:
                    case_id = f"{dataset}|{ex.example_id}|{seed}|{budget}"
                    raws: dict[str, dict[str, Any]] = {}
                    cls: dict[str, dict[str, Any]] = {}
                    for label, method_name in methods.items():
                        raw = HM._run_observed_with_events(
                            method_name,
                            {
                                "dataset": dataset,
                                "example_id": str(ex.example_id),
                                "problem_text": str(ex.question),
                                "ground_truth": str(ex.answer),
                                "seed": int(seed),
                                "budget": int(budget),
                            },
                            "fresh_our",
                        )
                        raws[label] = raw
                        failure, correct, gold_in_tree, answer = _classify(raw, str(ex.answer), dataset)
                        cls[label] = {
                            "failure": failure,
                            "correct": bool(correct),
                            "gold_in_tree": bool(gold_in_tree),
                            "answer": answer,
                        }

                    frow = _feature_row(
                        case_id,
                        dataset,
                        int(seed),
                        int(budget),
                        raws["strict_f2"],
                        bool(cls["strict_f3"]["correct"]),
                        bool(cls["strict_f2"]["correct"]),
                        bool(cls["strict_f3"]["gold_in_tree"]),
                        bool(cls["strict_f2"]["gold_in_tree"]),
                    )
                    frow["split"] = _split_bucket(case_id)
                    features.append(frow)

                    row: dict[str, Any] = {
                        "case_id": case_id,
                        "dataset": dataset,
                        "seed": int(seed),
                        "budget": int(budget),
                        "example_id": str(ex.example_id),
                        "gold_answer": str(ex.answer),
                    }
                    for label in methods:
                        row[f"{label}_answer"] = cls[label]["answer"]
                        row[f"{label}_correct"] = cls[label]["correct"]
                        row[f"{label}_failure_type"] = cls[label]["failure"]
                        row[f"{label}_gold_in_tree"] = cls[label]["gold_in_tree"]
                        row[f"{label}_repeated_same_family_present"] = _same_family(raws[label])
                        row[f"{label}_actions"] = int(raws[label]["actions"])
                        row[f"{label}_expansions"] = int(raws[label]["expansions"])
                        row[f"{label}_verifications"] = int(raws[label]["verifications"])

                    broader_rows.append(row)

    feature_cols = [
        c
        for c in features[0].keys()
        if c
        not in {
            "case_id",
            "dataset",
            "seed",
            "budget",
            "target_label",
            "label_policy_reason",
            "strict_f2_correct",
            "strict_f3_correct",
            "strict_f2_gold_in_tree",
            "strict_f3_gold_in_tree",
            "split",
        }
    ]

    train_rows = [r for r in features if r["split"] == "train"]
    val_rows = [r for r in features if r["split"] == "validation"]
    held_rows = [r for r in features if r["split"] == "heldout"]

    x_train, y_train = _matrix(train_rows, feature_cols), _labels(train_rows)
    x_val, y_val = _matrix(val_rows, feature_cols), _labels(val_rows)
    x_held, y_held = _matrix(held_rows, feature_cols), _labels(held_rows)

    w, b = _fit_logreg(x_train, y_train)
    val_pred_log = _predict_logreg(x_val, w, b)
    held_pred_log = _predict_logreg(x_held, w, b)

    stump = _fit_decision_stump(x_train, y_train, feature_cols)
    val_pred_tree = _predict_stump(x_val, stump)
    held_pred_tree = _predict_stump(x_held, stump)

    val_log_acc = _acc(y_val, val_pred_log)
    val_tree_acc = _acc(y_val, val_pred_tree)

    best_model = "strict_learned_f2_to_f3_gate_v1_logreg" if val_log_acc >= val_tree_acc else "strict_learned_f2_to_f3_gate_v1_tree"
    best_val_pred = val_pred_log if best_model.endswith("logreg") else val_pred_tree
    best_held_pred = held_pred_log if best_model.endswith("logreg") else held_pred_tree

    pred_by_case: dict[str, str] = {}
    for rows_src, preds in ((val_rows, best_val_pred), (held_rows, best_held_pred), (train_rows, _predict_logreg(x_train, w, b) if best_model.endswith("logreg") else _predict_stump(x_train, stump))):
        for r, p in zip(rows_src, preds):
            pred_by_case[str(r["case_id"])] = LABEL_FORCE if int(p) == 1 else LABEL_RELEASE

    for row in broader_rows:
        decision = pred_by_case[row["case_id"]]
        src = "strict_f3" if decision == LABEL_FORCE else "strict_f2"
        for field in ("answer", "correct", "failure_type", "gold_in_tree", "repeated_same_family_present", "actions", "expansions", "verifications"):
            row[f"learned_f2_to_f3_gate_v1_{field}"] = row[f"{src}_{field}"]
        row["learned_f2_to_f3_gate_v1_decision"] = decision
        row["learned_f2_to_f3_gate_v1_vs_baseline_outcome"] = _delta(bool(row["baseline_correct"]), bool(row["learned_f2_to_f3_gate_v1_correct"]))

    held_case_ids = {r["case_id"] for r in held_rows}
    held_eval_rows = [r for r in broader_rows if r["case_id"] in held_case_ids]

    method_keys = ["baseline", "strict_f2", "strict_f3", "strict_gate1", "strict_gate2", "learned_f2_to_f3_gate_v1"]
    methods_eval = dict(methods)
    methods_eval["learned_f2_to_f3_gate_v1"] = best_model
    held_summary_rows = _aggregate(held_eval_rows, method_keys, methods_eval)

    frozen_in = json.loads(Path(args.frozen_per_case_json).read_text(encoding="utf-8"))
    frozen_in = frozen_in[: int(args.frozen_limit)]

    frozen_rows: list[dict[str, Any]] = []
    frozen_feats: list[dict[str, Any]] = []

    for rec in frozen_in:
        dataset = str(rec["dataset"])
        example_id = str(rec["example_id"])
        seed = int(rec["surface_row"]["seed"])
        budget = int(rec["surface_row"]["budget"])
        gold = str(rec["compact_row"]["gold_answer"])
        ex_match = None
        for ex in load_pilot_examples(dataset, 96, seed):
            if str(ex.example_id) == example_id:
                ex_match = ex
                break
        if ex_match is None:
            continue

        case_id = f"frozen|{dataset}|{example_id}|{seed}|{budget}"
        raws: dict[str, dict[str, Any]] = {}
        cls: dict[str, dict[str, Any]] = {}
        for label, method_name in methods.items():
            raw = HM._run_observed_with_events(
                method_name,
                {
                    "dataset": dataset,
                    "example_id": example_id,
                    "problem_text": str(ex_match.question),
                    "ground_truth": gold,
                    "seed": seed,
                    "budget": budget,
                },
                "fresh_our",
            )
            raws[label] = raw
            failure, correct, gold_in_tree, answer = _classify(raw, gold, dataset)
            cls[label] = {"failure": failure, "correct": correct, "gold_in_tree": gold_in_tree, "answer": answer}

        frow = _feature_row(
            case_id,
            dataset,
            seed,
            budget,
            raws["strict_f2"],
            bool(cls["strict_f3"]["correct"]),
            bool(cls["strict_f2"]["correct"]),
            bool(cls["strict_f3"]["gold_in_tree"]),
            bool(cls["strict_f2"]["gold_in_tree"]),
        )
        frozen_feats.append(frow)

        row: dict[str, Any] = {
            "case_id": case_id,
            "dataset": dataset,
            "seed": seed,
            "budget": budget,
            "example_id": example_id,
            "gold_answer": gold,
        }
        for label in methods:
            row[f"{label}_answer"] = cls[label]["answer"]
            row[f"{label}_correct"] = cls[label]["correct"]
            row[f"{label}_failure_type"] = cls[label]["failure"]
            row[f"{label}_gold_in_tree"] = cls[label]["gold_in_tree"]
            row[f"{label}_repeated_same_family_present"] = _same_family(raws[label])
            row[f"{label}_actions"] = int(raws[label]["actions"])
            row[f"{label}_expansions"] = int(raws[label]["expansions"])
            row[f"{label}_verifications"] = int(raws[label]["verifications"])
        frozen_rows.append(row)

    x_frozen = _matrix(frozen_feats, feature_cols)
    if best_model.endswith("logreg"):
        pred_frozen = _predict_logreg(x_frozen, w, b)
    else:
        pred_frozen = _predict_stump(x_frozen, stump)

    for row, p in zip(frozen_rows, pred_frozen):
        decision = LABEL_FORCE if int(p) == 1 else LABEL_RELEASE
        src = "strict_f3" if decision == LABEL_FORCE else "strict_f2"
        for field in ("answer", "correct", "failure_type", "gold_in_tree", "repeated_same_family_present", "actions", "expansions", "verifications"):
            row[f"learned_f2_to_f3_gate_v1_{field}"] = row[f"{src}_{field}"]
        row["learned_f2_to_f3_gate_v1_decision"] = decision
        row["learned_f2_to_f3_gate_v1_vs_baseline_outcome"] = _delta(bool(row["baseline_correct"]), bool(row["learned_f2_to_f3_gate_v1_correct"]))

    frozen_summary_rows = _aggregate(frozen_rows, method_keys, methods_eval)

    cmp_rows = held_summary_rows

    train_manifest = {
        "artifact_family": "learned_f2_to_f3_gate_v1",
        "created_at_utc": now.isoformat(),
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "strict_phased_law": "finish F1 completely before any family may start F2; finish F2 completely before any family may start F3; gate decision happens only after F2 completion; in-phase ordering remains controller-driven eligibility constrained",
        "label_policy": {
            "primary_rule": "label force_f3 iff strict_f3 final correctness > strict_f2; else release_after_f2",
            "tie_rule": "prefer release_after_f2 on ties unless strict_f3 has additional tree coverage benefit",
        },
        "broader_surface": {"datasets": datasets, "subset_size": int(args.subset_size), "seeds": seeds, "budgets": budgets},
        "frozen_slice": {"path": str(args.frozen_per_case_json.relative_to(REPO_ROOT)), "limit": int(args.frozen_limit)},
        "methods": methods_eval,
        "feature_columns": feature_cols,
        "best_model": best_model,
    }

    label_dist = Counter(r["target_label"] for r in features)
    val_y = y_val
    held_y = y_held
    best_val_int = [1 if p == LABEL_FORCE else 0 for p in [LABEL_FORCE if p == 1 else LABEL_RELEASE for p in best_val_pred]]
    best_held_int = [1 if p == LABEL_FORCE else 0 for p in [LABEL_FORCE if p == 1 else LABEL_RELEASE for p in best_held_pred]]

    model_metrics = {
        "label_distribution": dict(label_dist),
        "split_sizes": {"train": len(train_rows), "validation": len(val_rows), "heldout": len(held_rows)},
        "models": {
            "strict_learned_f2_to_f3_gate_v1_logreg": {
                "validation_accuracy": val_log_acc,
                "heldout_gate_accuracy": _acc(held_y, held_pred_log),
                "coefficients": [{"feature": f, "weight": float(wi)} for f, wi in zip(feature_cols, w)],
                "bias": float(b),
                "validation_confusion": _confusion(val_y, val_pred_log),
                "heldout_confusion": _confusion(held_y, held_pred_log),
            },
            "strict_learned_f2_to_f3_gate_v1_tree": {
                "validation_accuracy": val_tree_acc,
                "heldout_gate_accuracy": _acc(held_y, held_pred_tree),
                "rule": {"feature": feature_cols[int(stump.get('feature', 0))], "threshold": stump.get("threshold"), "left_prediction": stump.get("left"), "right_prediction": stump.get("right")},
                "validation_confusion": _confusion(val_y, val_pred_tree),
                "heldout_confusion": _confusion(held_y, held_pred_tree),
            },
        },
        "best_model": best_model,
        "best_model_validation_accuracy": val_log_acc if best_model.endswith("logreg") else val_tree_acc,
        "best_model_heldout_gate_accuracy": _acc(held_y, held_pred_log if best_model.endswith("logreg") else held_pred_tree),
        "best_model_validation_confusion": _confusion(val_y, best_val_int),
        "best_model_heldout_confusion": _confusion(held_y, best_held_int),
    }

    held_summary = {
        "n_cases": len(held_eval_rows),
        "comparison": held_summary_rows,
        "learned_gate_decisions": dict(Counter(r["learned_f2_to_f3_gate_v1_decision"] for r in held_eval_rows)),
        "head_to_head": {
            "learned_vs_strict_f2": dict(Counter(_delta(bool(r["strict_f2_correct"]), bool(r["learned_f2_to_f3_gate_v1_correct"])) for r in held_eval_rows)),
            "learned_vs_strict_f3": dict(Counter(_delta(bool(r["strict_f3_correct"]), bool(r["learned_f2_to_f3_gate_v1_correct"])) for r in held_eval_rows)),
            "learned_vs_strict_gate1": dict(Counter(_delta(bool(r["strict_gate1_correct"]), bool(r["learned_f2_to_f3_gate_v1_correct"])) for r in held_eval_rows)),
            "learned_vs_strict_gate2": dict(Counter(_delta(bool(r["strict_gate2_correct"]), bool(r["learned_f2_to_f3_gate_v1_correct"])) for r in held_eval_rows)),
        },
    }

    frozen_summary = {
        "n_cases": len(frozen_rows),
        "comparison": frozen_summary_rows,
        "learned_gate_decisions": dict(Counter(r["learned_f2_to_f3_gate_v1_decision"] for r in frozen_rows)),
        "head_to_head": {
            "learned_vs_strict_f2": dict(Counter(_delta(bool(r["strict_f2_correct"]), bool(r["learned_f2_to_f3_gate_v1_correct"])) for r in frozen_rows)),
            "learned_vs_strict_f3": dict(Counter(_delta(bool(r["strict_f3_correct"]), bool(r["learned_f2_to_f3_gate_v1_correct"])) for r in frozen_rows)),
            "learned_vs_strict_gate1": dict(Counter(_delta(bool(r["strict_gate1_correct"]), bool(r["learned_f2_to_f3_gate_v1_correct"])) for r in frozen_rows)),
            "learned_vs_strict_gate2": dict(Counter(_delta(bool(r["strict_gate2_correct"]), bool(r["learned_f2_to_f3_gate_v1_correct"])) for r in frozen_rows)),
        },
    }

    with (out_dir / "train_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(train_manifest, f, indent=2)
    with (out_dir / "feature_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(features[0].keys()))
        writer.writeheader()
        for r in features:
            writer.writerow(r)
    with (out_dir / "model_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(model_metrics, f, indent=2)
    with (out_dir / "heldout_eval_summary.json").open("w", encoding="utf-8") as f:
        json.dump(held_summary, f, indent=2)
    with (out_dir / "frozen100_eval_summary.json").open("w", encoding="utf-8") as f:
        json.dump(frozen_summary, f, indent=2)
    with (out_dir / "comparison_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(cmp_rows[0].keys()))
        writer.writeheader()
        for r in cmp_rows:
            writer.writerow(r)

    report_path = REPO_ROOT / f"docs/LEARNED_F2_TO_F3_GATE_EVAL_{ts}.md"
    held_map = {r["method"]: r for r in held_summary_rows}
    frozen_map = {r["method"]: r for r in frozen_summary_rows}
    learned_held = held_map.get("learned_f2_to_f3_gate_v1", {})
    gate1_held = held_map.get("strict_gate1", {})
    gate2_held = held_map.get("strict_gate2", {})
    recommendation_keep = bool(float(learned_held.get("accuracy", 0.0)) >= max(float(gate1_held.get("accuracy", 0.0)), float(gate2_held.get("accuracy", 0.0))))

    lines = [
        f"# Learned F2→F3 gate evaluation ({ts})",
        "",
        "Strict phased law maintained: finish F1 then F2 then optional F3, with gate evaluated only after full F2 completion.",
        "",
        "## Label policy",
        "- Binary target: `force_f3` vs `release_after_f2`.",
        "- Label `force_f3` iff strict_f3 final correctness is better than strict_f2.",
        "- Label `release_after_f2` otherwise.",
        "- Tie policy: prefer `release_after_f2`, except when strict_f3 provides clear additional tree coverage benefit.",
        "",
        "## Learned model diagnostics",
        f"- Label distribution: {dict(label_dist)}",
        f"- Validation accuracy (logreg): {val_log_acc:.4f}",
        f"- Validation accuracy (tree): {val_tree_acc:.4f}",
        f"- Best model: **{best_model}**",
        f"- Best-model validation confusion: {model_metrics['best_model_validation_confusion']}",
        f"- Best-model heldout confusion: {model_metrics['best_model_heldout_confusion']}",
        "",
        "## Held-out broader matched comparison",
        "| method | accuracy | absent_from_tree | present_not_selected | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for k in ["baseline", "strict_f2", "strict_f3", "strict_gate1", "strict_gate2", "learned_f2_to_f3_gate_v1"]:
        r = held_map[k]
        lines.append(
            f"| {k} | {r['accuracy']:.4f} | {r['absent_from_tree']} | {r['present_not_selected']} | {r['repeated_same_family_present']} | {r['gold_in_tree']} | {r['avg_actions']:.3f} | {r['avg_expansions']:.3f} | {r['avg_verifications']:.3f} | {r['improved_vs_baseline']} | {r['worsened_vs_baseline']} | {r['unchanged_vs_baseline']} |"
        )

    lines.extend([
        "",
        "## Frozen 100-case stress comparison",
        "| method | accuracy | absent_from_tree | present_not_selected | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for k in ["baseline", "strict_f2", "strict_f3", "strict_gate1", "strict_gate2", "learned_f2_to_f3_gate_v1"]:
        r = frozen_map[k]
        lines.append(
            f"| {k} | {r['accuracy']:.4f} | {r['absent_from_tree']} | {r['present_not_selected']} | {r['repeated_same_family_present']} | {r['gold_in_tree']} | {r['avg_actions']:.3f} | {r['avg_expansions']:.3f} | {r['avg_verifications']:.3f} | {r['improved_vs_baseline']} | {r['worsened_vs_baseline']} | {r['unchanged_vs_baseline']} |"
        )

    lines.extend([
        "",
        "## Scientific questions",
        f"1. Learned gate beats deterministic gates on broader held-out? **{float(learned_held.get('accuracy',0.0)) > max(float(gate1_held.get('accuracy',0.0)), float(gate2_held.get('accuracy',0.0)))}**",
        f"2. Learned gate retains strict_f3-style coverage while limiting forced F3? Held-out decisions: {held_summary['learned_gate_decisions']}",
        "3. Extra complexity justification: compare learned vs strict_gate1/2 head-to-head in JSON summaries.",
        "4. Final decision anchored to held-out broader surface, frozen 100 is stress-test only.",
        "",
        "## Learned gate recommendation",
        f"- whether the learned gate is worth keeping: {'yes' if recommendation_keep else 'no'}",
        f"- whether it should replace deterministic gates: {'yes' if recommendation_keep else 'no'}",
        "- whether it is only a promising research direction: yes",
        f"- and which model should remain the default today: {'strict_learned_f2_to_f3_gate_v1' if recommendation_keep else 'strict_gate2'}",
        "",
        "## Concise run summary",
        f"- files changed: scripts/run_learned_f2_to_f3_gate_v1_eval.py, docs/LEARNED_F2_TO_F3_GATE_EVAL_{ts}.md",
        "- commands run: see shell history in PR summary",
        f"- output directory: outputs/learned_f2_to_f3_gate_{ts}",
        f"- best learned model: {best_model}",
        f"- broader held-out vs strict_f2/strict_f3/strict_gate1/strict_gate2: {held_summary['head_to_head']}",
        f"- frozen 100 vs strict_f2/strict_f3/strict_gate1/strict_gate2: {frozen_summary['head_to_head']}",
        f"- one-sentence verdict: {'learned gate is good enough for default promotion' if recommendation_keep else 'learned gate is not yet good enough to replace deterministic defaults'}.",
    ])

    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"output_dir={out_dir.relative_to(REPO_ROOT)}")
    print(f"report={report_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
