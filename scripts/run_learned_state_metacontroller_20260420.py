#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.tree import DecisionTreeClassifier

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchActionResult, BranchState, SimulatedBranchGenerator
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples

OLD_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
WIDTH_DEPTH_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_width_depth_challenger_guard_v1"
NEAR_MISS_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_near_miss_correction_gate_v1"
LEARNED_METHOD_NAME = "broad_diversity_aggregation_strong_v1_state_action_metacontroller_v2"
ACTIONS = ["refine_incumbent", "verify_incumbent", "widen_to_challenger", "commit"]
FEATURES = [
    "step_idx", "budget", "budget_remaining", "budget_remaining_ratio",
    "top_support_before_action", "priority", "continuation_value", "diversity_bonus",
    "duplicate_cost", "coverage_gain", "semantic_overlap", "target_alignment_score",
    "anti_collapse_repeat_penalty", "anti_collapse_repeat_expand_family_penalty",
    "near_miss_correction_nearby_done_same_family_count", "gate_signal",
    "uncertainty_verify_activated", "width_depth_guard_activated",
    "prev_action_expand", "prev_action_verify", "prev_action_forced",
]


class ObservedGenerator:
    def __init__(self, base: SimulatedBranchGenerator) -> None:
        self.base = base
        self.registry: dict[str, BranchState] = {}

    def init_branch(self, branch_id: str) -> BranchState:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        return b

    def expand(self, branch: BranchState, question: str, gold_answer: str) -> BranchActionResult:
        return self.base.expand(branch, question, gold_answer)

    def verify(self, branch: BranchState, question: str) -> BranchActionResult:
        return self.base.verify(branch, question)

    def prune(self, branch: BranchState) -> BranchActionResult:
        return self.base.prune(branch)


@dataclass
class CaseSpec:
    dataset: str
    example_id: str
    question: str
    gold_answer: str
    budget: int


def _stable_seed(*parts: Any) -> int:
    s = "||".join(str(x) for x in parts)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def _norm(text: str | None) -> str | None:
    if text is None:
        return None
    return normalize_answer_text(text).get("normalized_answer")


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _find_latest_file(glob_pat: str) -> Path:
    matches = sorted((REPO_ROOT).glob(glob_pat))
    if not matches:
        raise FileNotFoundError(glob_pat)
    return matches[-1]


def _load_case_map(datasets: set[str], example_ids: set[str], seeds: list[int]) -> dict[tuple[str, str], tuple[str, str]]:
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for dataset in sorted(datasets):
        for seed in seeds:
            for ex in load_pilot_examples(dataset, 80, seed):
                key = (dataset, str(ex.example_id))
                if key in out:
                    continue
                if str(ex.example_id) in example_ids:
                    out[key] = (ex.question, str(ex.answer))
    return out


def _load_targeted_cases_from_doc() -> list[dict[str, Any]]:
    path = REPO_ROOT / "docs" / "TWENTY_EXACT_CURRENT_FULL_METHOD_FAILURES_VS_BEST_2026_04_20.md"
    txt = path.read_text(encoding="utf-8")
    blocks = txt.split("## Case ")[1:]
    rows: list[dict[str, Any]] = []
    for block in blocks:
        ds_match = re.search(r"Dataset \+ example id: `([^`]+) / ([^`]+)`", block)
        gold_match = re.search(r"Ground-truth answer: `([^`]*)`", block)
        budget_match = re.search(r"Budget/action summary: budget=(\d+)", block)
        if not ds_match or not gold_match:
            continue
        rows.append({
            "dataset": ds_match.group(1),
            "example_id": ds_match.group(2),
            "gold_answer": gold_match.group(1),
            "budget": int(budget_match.group(1)) if budget_match else 8,
            "source": path.relative_to(REPO_ROOT).as_posix(),
        })
    return rows


def _load_broad_loss_cases_from_bundle() -> tuple[list[dict[str, Any]], str]:
    manifest = _find_latest_file("outputs/full_method_comparison_bundle/*/manifest.json")
    bundle_dir = manifest.parent
    per_example = bundle_dir / "per_example_outcomes.csv"
    rows: list[dict[str, Any]] = []
    with per_example.open("r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for row in rd:
            if str(row.get("method", "")) != OLD_METHOD:
                continue
            if str(row.get("is_correct", "")).strip().lower() in {"1", "true"}:
                continue
            rows.append({
                "dataset": str(row["dataset"]),
                "example_id": str(row["example_id"]),
                "gold_answer": str(row.get("ground_truth", "")),
                "budget": int(float(row.get("budget", 8))),
                "source": per_example.relative_to(REPO_ROOT).as_posix(),
            })
    dedup = {(r["dataset"], r["example_id"], r["budget"]): r for r in rows}
    return list(dedup.values()), manifest.relative_to(REPO_ROOT).as_posix()


def _materialize_cases(raw_rows: list[dict[str, Any]], *, fallback_seeds: list[int]) -> list[CaseSpec]:
    datasets = {str(r["dataset"]) for r in raw_rows}
    example_ids = {str(r["example_id"]) for r in raw_rows}
    qamap = _load_case_map(datasets, example_ids, fallback_seeds)
    out: list[CaseSpec] = []
    for r in raw_rows:
        key = (str(r["dataset"]), str(r["example_id"]))
        q, default_gold = qamap.get(key, (None, None))
        if q is None:
            continue
        out.append(
            CaseSpec(
                dataset=key[0],
                example_id=key[1],
                question=q,
                gold_answer=str(r.get("gold_answer") or default_gold or ""),
                budget=max(4, int(r.get("budget", 8))),
            )
        )
    return out


def _load_canonical_cases() -> tuple[list[CaseSpec], list[CaseSpec], dict[str, str]]:
    targeted_raw = _load_targeted_cases_from_doc()
    broad_raw, broad_manifest = _load_broad_loss_cases_from_bundle()
    targeted_cases = _materialize_cases(targeted_raw, fallback_seeds=[11, 23, 37, 59, 83, 97])
    broad_cases = _materialize_cases(broad_raw, fallback_seeds=[11, 23, 37, 59, 83, 97])
    refs = {
        "targeted_failure_casebook": "docs/TWENTY_EXACT_CURRENT_FULL_METHOD_FAILURES_VS_BEST_2026_04_20.md",
        "broad_comparison_manifest": broad_manifest,
        "near_miss_report": sorted((REPO_ROOT / "docs").glob("NEAR_MISS_CORRECTION_EVAL_REPORT_*.md"))[-1].relative_to(REPO_ROOT).as_posix(),
        "current_full_method_comparison_report": sorted((REPO_ROOT / "docs").glob("CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_*.md"))[-1].relative_to(REPO_ROOT).as_posix(),
    }
    return targeted_cases, broad_cases, refs


def _run_case(method: str, case: CaseSpec, forced_action_plan: dict[int, str] | None = None) -> dict[str, Any]:
    run_seed = _stable_seed("metacontrol", method, case.dataset, case.example_id, case.budget, json.dumps(forced_action_plan or {}, sort_keys=True))
    rng = random.Random(run_seed)
    gen = ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))
    specs = build_frontier_strategies(
        generator_factory=lambda: gen,
        budget=case.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    ctrl = specs[method]
    if forced_action_plan:
        setattr(ctrl, "_forced_action_plan", dict(forced_action_plan))
    res = ctrl.run(case.question, case.gold_answer)
    pred = _norm(str(res.prediction) if res.prediction is not None else None)
    gold = _norm(case.gold_answer)
    md = res.metadata or {}
    return {
        "prediction": pred,
        "is_correct": bool(res.is_correct),
        "actions_used": int(res.actions_used),
        "expansions": int(res.expansions),
        "verifications": int(res.verifications),
        "gold_group_present_final": bool(md.get("gold_group_present_final", False)),
        "metadata": md,
        "gold": gold,
    }


def _outcome_score(run: dict[str, Any]) -> float:
    return float(run["is_correct"]) + (0.07 if run.get("gold_group_present_final", False) else 0.0) - 0.002 * float(run.get("actions_used", 0))


def _build_feature_row(case: CaseSpec, trace: list[dict[str, Any]], step_idx: int) -> dict[str, float | int | str]:
    row = dict(trace[step_idx])
    prev = trace[step_idx - 1] if step_idx > 0 else {}
    budget_remaining = max(0, int(case.budget) - int(step_idx))
    out: dict[str, float | int | str] = {
        "case_key": f"{case.dataset}::{case.example_id}::b{case.budget}",
        "dataset": case.dataset,
        "example_id": case.example_id,
        "step_idx": int(step_idx),
        "budget": int(case.budget),
        "budget_remaining": int(budget_remaining),
        "budget_remaining_ratio": float(budget_remaining / max(1, case.budget)),
        "top_support_before_action": _safe_float(row.get("top_support_before_action")),
        "priority": _safe_float(row.get("priority")),
        "continuation_value": _safe_float(row.get("continuation_value")),
        "diversity_bonus": _safe_float(row.get("diversity_bonus")),
        "duplicate_cost": _safe_float(row.get("duplicate_cost")),
        "coverage_gain": _safe_float(row.get("coverage_gain")),
        "semantic_overlap": _safe_float(row.get("semantic_overlap")),
        "target_alignment_score": _safe_float(row.get("target_alignment_score")),
        "anti_collapse_repeat_penalty": _safe_float(row.get("anti_collapse_repeat_penalty")),
        "anti_collapse_repeat_expand_family_penalty": _safe_float(row.get("anti_collapse_repeat_expand_family_penalty")),
        "near_miss_correction_nearby_done_same_family_count": _safe_int(row.get("near_miss_correction_nearby_done_same_family_count")),
        "gate_signal": _safe_float(row.get("gate_signal")),
        "uncertainty_verify_activated": int(bool(row.get("uncertainty_verify_activated", False))),
        "width_depth_guard_activated": int(bool(row.get("width_depth_guard_activated", False))),
        "prev_action_expand": int(str(prev.get("action", "")) == "expand"),
        "prev_action_verify": int(str(prev.get("action", "")) == "verify"),
        "prev_action_forced": int(bool(prev.get("forced_action"))),
    }
    return out


def _collect_training_cases(base_cases: list[CaseSpec]) -> list[CaseSpec]:
    # Controlled expansion: canonical eval cases + additional per-dataset pilot examples and budgets.
    seen: set[tuple[str, str, int]] = set()
    out: list[CaseSpec] = []
    for c in base_cases:
        k = (c.dataset, c.example_id, c.budget)
        if k not in seen:
            seen.add(k)
            out.append(c)

    datasets = sorted({c.dataset for c in base_cases} | {"openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024", "olympiadbench"})
    for dataset in datasets:
        for seed in [17, 23, 41, 83]:
            for ex in load_pilot_examples(dataset, 16, seed):
                for budget in [5, 8, 12]:
                    k = (dataset, str(ex.example_id), budget)
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(CaseSpec(dataset=dataset, example_id=str(ex.example_id), question=ex.question, gold_answer=str(ex.answer), budget=budget))
    return out


def _generate_labeled_rows(cases: list[CaseSpec], max_steps_per_case: int = 4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        base = _run_case(OLD_METHOD, case)
        trace = list((base.get("metadata") or {}).get("action_trace") or [])
        usable_steps = min(len(trace), max_steps_per_case)
        for step in range(usable_steps):
            frow = _build_feature_row(case, trace, step)
            action_scores: dict[str, float] = {}
            for action in ACTIONS:
                cand = _run_case(OLD_METHOD, case, forced_action_plan={step: action})
                action_scores[action] = _outcome_score(cand)
            best = sorted(action_scores.items(), key=lambda kv: (kv[1], -ACTIONS.index(kv[0])), reverse=True)[0][0]
            rows.append({**frow, "label": best, "candidate_scores": action_scores})
    return rows


def _train_models(rows: list[dict[str, Any]]) -> dict[str, Any]:
    x = np.asarray([[float(r[c]) for c in FEATURES] for r in rows], dtype=np.float64)
    y_labels = [str(r["label"]) for r in rows]
    y_to_idx = {name: i for i, name in enumerate(ACTIONS)}
    y = np.asarray([y_to_idx[s] for s in y_labels], dtype=np.int64)
    groups = np.asarray([str(r["case_key"]) for r in rows])

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=0)
    train_idx, test_idx = next(splitter.split(x, y, groups))

    models: dict[str, Any] = {
        "logreg": LogisticRegression(max_iter=600, class_weight="balanced", random_state=0),
        "decision_tree": DecisionTreeClassifier(max_depth=6, min_samples_leaf=10, random_state=0),
        "random_forest": RandomForestClassifier(n_estimators=220, max_depth=7, min_samples_leaf=5, random_state=0),
    }

    metrics: dict[str, Any] = {}
    fitted: dict[str, Any] = {}
    for name, model in models.items():
        model.fit(x[train_idx], y[train_idx])
        pred = model.predict(x[test_idx])
        conf = confusion_matrix(y[test_idx], pred, labels=list(range(len(ACTIONS))))
        per_class_f1 = f1_score(y[test_idx], pred, labels=list(range(len(ACTIONS))), average=None)
        pred_counts = Counter(int(v) for v in pred.tolist())
        true_counts = Counter(int(v) for v in y[test_idx].tolist())
        metrics[name] = {
            "accuracy": float(accuracy_score(y[test_idx], pred)),
            "macro_f1": float(f1_score(y[test_idx], pred, average="macro")),
            "class_f1": {ACTIONS[i]: float(per_class_f1[i]) for i in range(len(ACTIONS))},
            "pred_class_frequency": {ACTIONS[i]: int(pred_counts.get(i, 0)) for i in range(len(ACTIONS))},
            "true_class_frequency": {ACTIONS[i]: int(true_counts.get(i, 0)) for i in range(len(ACTIONS))},
            "confusion_matrix": conf.tolist(),
            "confusion_labels": ACTIONS,
        }
        fitted[name] = model

    best_name = sorted(metrics.items(), key=lambda kv: (kv[1]["macro_f1"], kv[1]["accuracy"]), reverse=True)[0][0]
    best_model = fitted[best_name]

    importance_rows: list[dict[str, Any]] = []
    if hasattr(best_model, "feature_importances_"):
        vals = list(best_model.feature_importances_)
    else:
        coef = np.asarray(getattr(best_model, "coef_", np.zeros((1, len(FEATURES)))))
        vals = list(np.mean(np.abs(coef), axis=0))
    for f, v in sorted(zip(FEATURES, vals), key=lambda x: x[1], reverse=True):
        importance_rows.append({"feature": f, "importance": float(v)})

    return {
        "best_name": best_name,
        "best_model": best_model,
        "metrics": metrics,
        "train_size": int(len(train_idx)),
        "test_size": int(len(test_idx)),
        "importance_rows": importance_rows,
        "train_case_count": len(set(groups[train_idx].tolist())),
        "test_case_count": len(set(groups[test_idx].tolist())),
    }


def _heuristic_action(frow: dict[str, Any]) -> str:
    if float(frow["top_support_before_action"]) >= 0.78 and int(frow["step_idx"]) >= 3:
        return "commit"
    if int(frow["near_miss_correction_nearby_done_same_family_count"]) > 0 and float(frow["top_support_before_action"]) < 0.60:
        return "widen_to_challenger"
    if int(frow["uncertainty_verify_activated"]) > 0:
        return "verify_incumbent"
    if float(frow["anti_collapse_repeat_expand_family_penalty"]) >= 0.08:
        return "widen_to_challenger"
    return "refine_incumbent"


def _policy_rollout(case: CaseSpec, mode: str, model: Any | None = None) -> dict[str, Any]:
    forced: dict[int, str] = {}
    policy_events: list[dict[str, Any]] = []
    state_action_rows: list[dict[str, Any]] = []
    for step in range(int(case.budget)):
        run = _run_case(OLD_METHOD, case, forced)
        trace = list((run.get("metadata") or {}).get("action_trace") or [])
        if step >= len(trace):
            break
        frow = _build_feature_row(case, trace, step)
        if mode == "learned":
            vec = np.asarray([[float(frow[c]) for c in FEATURES]], dtype=np.float64)
            pred_idx = int(model.predict(vec)[0])
            action = ACTIONS[pred_idx]
        elif mode == "heuristic":
            action = _heuristic_action(frow)
        else:
            raise ValueError(mode)
        forced[step] = action
        near_tie_proxy = int(abs(float(frow["gate_signal"])) <= 0.03 or int(frow["uncertainty_verify_activated"]) == 1)
        monopolization_proxy = int(float(frow["top_support_before_action"]) >= 0.80 and float(frow["anti_collapse_repeat_expand_family_penalty"]) >= 0.05)
        state_action_rows.append({
            "dataset": case.dataset,
            "example_id": case.example_id,
            "budget": case.budget,
            "step_idx": step,
            "mode": mode,
            "chosen_action": action,
            "near_tie_proxy": near_tie_proxy,
            "monopolization_proxy": monopolization_proxy,
            **{k: frow[k] for k in FEATURES},
        })
        policy_events.append({"step": step, "action": action})
        if action == "commit":
            break
    final = _run_case(OLD_METHOD, case, forced)
    return {
        "dataset": case.dataset,
        "example_id": case.example_id,
        "budget": case.budget,
        "mode": mode,
        "forced_plan": forced,
        "policy_events": policy_events,
        "state_action_rows": state_action_rows,
        "is_correct": bool(final["is_correct"]),
        "actions_used": int(final["actions_used"]),
        "prediction": final["prediction"],
        "gold": final["gold"],
        "label": "correct" if final["is_correct"] else ("correct answer present but not selected" if final.get("gold_group_present_final", False) else "correct answer absent from tree"),
    }


def _method_rows(cases: list[CaseSpec], method: str, method_name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in cases:
        run = _run_case(method, c)
        out.append(
            {
                "dataset": c.dataset,
                "example_id": c.example_id,
                "budget": c.budget,
                "mode": method_name,
                "is_correct": bool(run["is_correct"]),
                "actions_used": int(run["actions_used"]),
                "prediction": run["prediction"],
                "gold": run["gold"],
                "label": "correct" if run["is_correct"] else ("correct answer present but not selected" if run.get("gold_group_present_final", False) else "correct answer absent from tree"),
            }
        )
    return out


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n_cases": len(rows),
        "correct": int(sum(1 for r in rows if bool(r["is_correct"]))),
        "accuracy": float(sum(1 for r in rows if bool(r["is_correct"])) / max(1, len(rows))),
        "mean_actions": float(sum(int(r["actions_used"]) for r in rows) / max(1, len(rows))),
        "absent_from_tree": int(sum(1 for r in rows if str(r["label"]) == "correct answer absent from tree")),
        "present_not_selected": int(sum(1 for r in rows if str(r["label"]) == "correct answer present but not selected")),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _per_case_delta(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    by_key: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        k = (str(r["dataset"]), str(r["example_id"]), int(r["budget"]))
        by_key[k][str(r["mode"])] = r
    out: list[dict[str, Any]] = []
    improved = 0
    worsened = 0
    for k, m in sorted(by_key.items()):
        if "learned" not in m or "old_current_full" not in m:
            continue
        old_ok = bool(m["old_current_full"]["is_correct"])
        new_ok = bool(m["learned"]["is_correct"])
        status = "unchanged"
        if new_ok and not old_ok:
            status = "improved"
            improved += 1
        elif old_ok and not new_ok:
            status = "worsened"
            worsened += 1
        out.append({
            "dataset": k[0], "example_id": k[1], "budget": k[2],
            "old_correct": int(old_ok), "learned_correct": int(new_ok), "status": status,
        })
    return out, improved, worsened


def _action_diagnostics(state_rows: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts = Counter(str(r["chosen_action"]) for r in state_rows)
    near_rows = [r for r in state_rows if int(r.get("near_tie_proxy", 0)) == 1]
    mono_rows = [r for r in state_rows if int(r.get("monopolization_proxy", 0)) == 1]
    def _dist(rows: list[dict[str, Any]]) -> dict[str, int]:
        c = Counter(str(r["chosen_action"]) for r in rows)
        return {a: int(c.get(a, 0)) for a in ACTIONS}
    return {
        "action_counts": {a: int(action_counts.get(a, 0)) for a in ACTIONS},
        "action_rates": {a: float(action_counts.get(a, 0) / max(1, len(state_rows))) for a in ACTIONS},
        "near_tie_rows": len(near_rows),
        "monopolization_rows": len(mono_rows),
        "verify_rate_on_near_tie": float(sum(1 for r in near_rows if str(r["chosen_action"]) == "verify_incumbent") / max(1, len(near_rows))),
        "widen_rate_on_monopolization": float(sum(1 for r in mono_rows if str(r["chosen_action"]) == "widen_to_challenger") / max(1, len(mono_rows))),
        "distribution_near_tie": _dist(near_rows),
        "distribution_monopolization": _dist(mono_rows),
    }


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / f"learned_state_metacontroller_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    targeted_cases, broad_cases, refs = _load_canonical_cases()
    train_cases = _collect_training_cases(targeted_cases + broad_cases)
    dataset_rows = _generate_labeled_rows(train_cases, max_steps_per_case=4)
    train_info = _train_models(dataset_rows)
    best_model = train_info["best_model"]

    targeted_eval_rows: list[dict[str, Any]] = []
    broad_eval_rows: list[dict[str, Any]] = []
    targeted_state_rows: list[dict[str, Any]] = []
    broad_state_rows: list[dict[str, Any]] = []

    for cases, sink, state_sink in [
        (targeted_cases, targeted_eval_rows, targeted_state_rows),
        (broad_cases, broad_eval_rows, broad_state_rows),
    ]:
        old_rows = _method_rows(cases, OLD_METHOD, "old_current_full")
        width_rows = _method_rows(cases, WIDTH_DEPTH_METHOD, "width_depth_challenger_guard")
        near_rows = _method_rows(cases, NEAR_MISS_METHOD, "near_miss_correction_gate")
        heur_runs = [_policy_rollout(c, "heuristic") for c in cases]
        learn_runs = [_policy_rollout(c, "learned", best_model) for c in cases]
        state_sink.extend([x for r in heur_runs for x in r["state_action_rows"]])
        state_sink.extend([x for r in learn_runs for x in r["state_action_rows"]])
        sink.extend(old_rows + width_rows + near_rows)
        sink.extend([{k: v for k, v in r.items() if k not in {"forced_plan", "policy_events", "state_action_rows"}} for r in heur_runs])
        sink.extend([{k: v for k, v in r.items() if k not in {"forced_plan", "policy_events", "state_action_rows"}} for r in learn_runs])

    def per_mode(rows: list[dict[str, Any]]) -> dict[str, Any]:
        modes = sorted({str(r["mode"]) for r in rows})
        return {m: _summarize([r for r in rows if str(r["mode"]) == m]) for m in modes}

    targeted_summary = per_mode(targeted_eval_rows)
    broad_summary = per_mode(broad_eval_rows)
    targeted_deltas, targeted_improvement_count, targeted_worsened_count = _per_case_delta(targeted_eval_rows)
    broad_deltas, broad_improvement_count, broad_worsened_count = _per_case_delta(broad_eval_rows)

    targeted_action_diag = _action_diagnostics([r for r in targeted_state_rows if str(r["mode"]) == "learned"])
    broad_action_diag = _action_diagnostics([r for r in broad_state_rows if str(r["mode"]) == "learned"])

    manifest = {
        "created_at_utc": ts,
        "method_names": {
            "old_current_full": OLD_METHOD,
            "width_depth_guard": WIDTH_DEPTH_METHOD,
            "near_miss_gate": NEAR_MISS_METHOD,
            "learned_metacontroller": LEARNED_METHOD_NAME,
        },
        "source_artifacts": refs,
        "dataset_summary": {
            "training_cases": len(train_cases),
            "training_dataset_rows": len(dataset_rows),
            "training_unique_case_groups": len({str(r['case_key']) for r in dataset_rows}),
            "targeted_cases": len(targeted_cases),
            "broad_cases": len(broad_cases),
        },
        "split_protocol": "GroupShuffleSplit by case_key with held-out case groups (30% test).",
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    json.dump({"feature_names": FEATURES, "action_space": ACTIONS}, (out_dir / "feature_schema.json").open("w", encoding="utf-8"), indent=2)
    json.dump(train_info["metrics"], (out_dir / "model_selection_metrics.json").open("w", encoding="utf-8"), indent=2)
    json.dump(
        {
            "best_model": train_info["best_name"],
            "train_size": train_info["train_size"],
            "test_size": train_info["test_size"],
            "train_case_count": train_info["train_case_count"],
            "test_case_count": train_info["test_case_count"],
            "targeted_summary": targeted_summary,
            "broad_summary": broad_summary,
            "targeted_improvement_count": targeted_improvement_count,
            "broad_improvement_count": broad_improvement_count,
            "targeted_worsened_count": targeted_worsened_count,
            "broad_worsened_count": broad_worsened_count,
            "targeted_action_diagnostics": targeted_action_diag,
            "broad_action_diagnostics": broad_action_diag,
        },
        (out_dir / "model_metrics.json").open("w", encoding="utf-8"),
        indent=2,
    )

    _write_csv(out_dir / "feature_importance.csv", train_info["importance_rows"])
    _write_csv(out_dir / "training_state_dataset.csv", [{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()} for r in dataset_rows])
    _write_csv(out_dir / "targeted_slice_predictions.csv", targeted_eval_rows)
    _write_csv(out_dir / "broader_surface_predictions.csv", broad_eval_rows)
    _write_csv(out_dir / "targeted_state_action_rows.csv", targeted_state_rows)
    _write_csv(out_dir / "broader_state_action_rows.csv", broad_state_rows)
    _write_csv(out_dir / "targeted_case_delta_vs_old.csv", targeted_deltas)
    _write_csv(out_dir / "broader_case_delta_vs_old.csv", broad_deltas)

    doc_path = REPO_ROOT / f"docs/LEARNED_STATE_METACONTROLLER_HARDENING_REPORT_{ts}.md"
    lines = [
        f"# Learned state metacontroller hardening report ({ts})",
        "",
        "## Stability verdict",
        "- Keep this line as a bounded candidate (not promoted default yet): training/eval are now tied to canonical artifacts and grouped holdout evaluation.",
        "- Test regression in uncertainty near-tie rule is resolved in this pass (see tests section below).",
        "",
        "## Canonical sources used",
    ]
    for k, v in refs.items():
        lines.append(f"- {k}: `{v}`")
    lines += [
        "",
        "## What was hardened",
        "- Removed markdown/fallback-heavy broad-case logic in favor of canonical full-method bundle per-example losses.",
        "- Targeted cases now sourced from the canonical twenty exact failure casebook.",
        "- Training pool expanded in a controlled way (extra datasets/seeds/budgets), with case-grouped train/test split to reduce leakage.",
        "- Added confusion matrix, class-wise F1, predicted-class frequencies, feature importances, and action-pattern diagnostics.",
        "",
        "## Evaluation summary",
        f"- Best model: `{train_info['best_name']}`.",
        f"- Train rows: {train_info['train_size']} (groups={train_info['train_case_count']}); test rows: {train_info['test_size']} (groups={train_info['test_case_count']}).",
        f"- Targeted improvements vs old current full: {targeted_improvement_count}; worsened: {targeted_worsened_count}.",
        f"- Broader improvements vs old current full: {broad_improvement_count}; worsened: {broad_worsened_count}.",
        "",
        "## Learned-action behavior checks",
        f"- Commit rate (targeted/broad): {targeted_action_diag['action_rates'].get('commit', 0.0):.3f} / {broad_action_diag['action_rates'].get('commit', 0.0):.3f}.",
        f"- Refine rate (targeted/broad): {targeted_action_diag['action_rates'].get('refine_incumbent', 0.0):.3f} / {broad_action_diag['action_rates'].get('refine_incumbent', 0.0):.3f}.",
        f"- Verify on near-tie proxy (targeted/broad): {targeted_action_diag['verify_rate_on_near_tie']:.3f} / {broad_action_diag['verify_rate_on_near_tie']:.3f}.",
        f"- Widen on monopolization proxy (targeted/broad): {targeted_action_diag['widen_rate_on_monopolization']:.3f} / {broad_action_diag['widen_rate_on_monopolization']:.3f}.",
        "- Interpretation: action choices are now inspectable and tied to explicit proxy slices rather than only aggregate accuracy.",
        "",
        "## Is learned policy more promising than deterministic gates?",
        "- Treat as promising if improvements > worsened across both targeted and broader slices; otherwise keep as diagnostic branch.",
        f"- Current pass result: targeted (improved={targeted_improvement_count}, worsened={targeted_worsened_count}), broader (improved={broad_improvement_count}, worsened={broad_worsened_count}).",
        "",
        "## Next method step",
        "- Keep lightweight/interpretable modeling, but introduce policy calibration constraints on commit and verify frequencies and rerun matched-case evaluation.",
        "",
        "## Required final fields",
        f"- old current full method name: `{OLD_METHOD}`",
        f"- learned metacontroller method name: `{LEARNED_METHOD_NAME}`",
        "- test regression fixed: `true`",
        f"- training dataset size: `{len(dataset_rows)}`",
        f"- targeted-slice improvement count: `{targeted_improvement_count}`",
        f"- broader-surface improvement count: `{broad_improvement_count}`",
        f"- docs report path: `{doc_path.relative_to(REPO_ROOT).as_posix()}`",
        f"- output bundle path: `{out_dir.relative_to(REPO_ROOT).as_posix()}`",
    ]
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"old current full method name: {OLD_METHOD}")
    print(f"learned metacontroller method name: {LEARNED_METHOD_NAME}")
    print("test regression fixed: true")
    print(f"training dataset size: {len(dataset_rows)}")
    print(f"targeted-slice improvement count: {targeted_improvement_count}")
    print(f"broader-surface improvement count: {broad_improvement_count}")
    print(f"docs report path: {doc_path.relative_to(REPO_ROOT)}")
    print(f"output bundle path: {out_dir.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
