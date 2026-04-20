#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
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
LEARNED_METHOD_NAME = "broad_diversity_aggregation_strong_v1_state_action_metacontroller_v1"
ACTIONS = ["refine_incumbent", "verify_incumbent", "widen_to_challenger", "commit"]
FEATURES = [
    "step_idx",
    "budget",
    "budget_remaining",
    "budget_remaining_ratio",
    "top_support_before_action",
    "priority",
    "continuation_value",
    "diversity_bonus",
    "duplicate_cost",
    "coverage_gain",
    "semantic_overlap",
    "target_alignment_score",
    "anti_collapse_repeat_penalty",
    "anti_collapse_repeat_expand_family_penalty",
    "near_miss_correction_nearby_done_same_family_count",
    "gate_signal",
    "uncertainty_verify_activated",
    "width_depth_guard_activated",
    "prev_action_expand",
    "prev_action_verify",
    "prev_action_forced",
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


def _find_latest_dir(glob_pat: str) -> Path:
    xs = sorted((REPO_ROOT / "outputs").glob(glob_pat))
    if not xs:
        raise FileNotFoundError(glob_pat)
    return xs[-1]


def _load_canonical_cases() -> tuple[list[CaseSpec], list[CaseSpec], dict[str, str]]:
    targeted_rows: list[dict[str, Any]] = []
    broad_rows: list[dict[str, Any]] = []
    targeted_dir = None
    imp_dir = None
    try:
        targeted_dir = _find_latest_dir("targeted_failure_bundle_*/")
        targeted_rows = json.loads((targeted_dir / "per_case.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        targeted_rows = []
    try:
        imp_dir = _find_latest_dir("twenty_exact_current_full_improvement_eval_*/")
        broad_rows = json.loads((imp_dir / "per_case_before_after.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        broad_rows = []
    if not broad_rows:
        src_doc = REPO_ROOT / "docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md"
        txt = src_doc.read_text(encoding="utf-8")
        for block in txt.split("\n## Case ")[1:]:
            ds = None
            ex = None
            gold = None
            budget = 8
            for ln in block.splitlines():
                ls = ln.strip()
                if ls.startswith("- dataset: `"):
                    ds = ls.split("`")[1]
                elif ls.startswith("- example_id: `"):
                    ex = ls.split("`")[1]
                elif ls.startswith("- gold answer: `"):
                    gold = ls.split("`")[1]
                elif ls.startswith("- our budget/actions/expansions/verifications: `"):
                    try:
                        budget = int(ls.split("{'budget':")[1].split(",")[0].strip())
                    except Exception:
                        budget = 8
            if ds and ex and gold is not None:
                broad_rows.append({"dataset": ds, "example_id": ex, "gold_answer": gold, "budget": budget})
    if not targeted_rows:
        targeted_rows = broad_rows[:7]

    def mk(rows: list[dict[str, Any]]) -> list[CaseSpec]:
        out: list[CaseSpec] = []
        for r in rows:
            q = None
            for seed in [11, 23, 37, 59, 71, 83, 97, 109]:
                for ex in load_pilot_examples(str(r["dataset"]), 40, seed):
                    if ex.example_id == str(r["example_id"]):
                        q = ex.question
                        break
                if q:
                    break
            if q is None:
                continue
            out.append(CaseSpec(dataset=str(r["dataset"]), example_id=str(r["example_id"]), question=q, gold_answer=str(r["gold_answer"]), budget=int(r["budget"])))
        return out

    refs = {
        "fresh_loss_bundle": "docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md",
        "twenty_case_improvement_report": sorted((REPO_ROOT / "docs").glob("TWENTY_CASE_CURRENT_FULL_IMPROVEMENT_REPORT_*.md"))[-1].relative_to(REPO_ROOT).as_posix(),
        "targeted_failure_bundle_report": sorted((REPO_ROOT / "docs").glob("TARGETED_FAILURE_BUNDLE_REPORT_*.md"))[-1].relative_to(REPO_ROOT).as_posix(),
        "near_miss_report": sorted((REPO_ROOT / "docs").glob("NEAR_MISS_CORRECTION_EVAL_REPORT_*.md"))[-1].relative_to(REPO_ROOT).as_posix(),
        "broad_comparison_artifact": sorted((REPO_ROOT / "outputs/full_method_comparison_bundle").glob("*/manifest.json"))[-1].relative_to(REPO_ROOT).as_posix(),
    }
    return mk(targeted_rows), mk(broad_rows), refs


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


def _collect_training_cases() -> list[CaseSpec]:
    out: list[CaseSpec] = []
    datasets = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024", "olympiadbench"]
    for dataset in datasets:
        examples = load_pilot_examples(dataset, 10, 83)
        for budget in [5, 8]:
            for ex in examples:
                out.append(CaseSpec(dataset=dataset, example_id=ex.example_id, question=ex.question, gold_answer=ex.answer, budget=budget))
    return out


def _generate_labeled_rows(cases: list[CaseSpec], max_steps_per_case: int = 3) -> list[dict[str, Any]]:
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

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=0)
    train_idx, test_idx = next(splitter.split(x, y, groups))

    models: dict[str, Any] = {
        "logreg": LogisticRegression(max_iter=500, class_weight="balanced", random_state=0),
        "decision_tree": DecisionTreeClassifier(max_depth=5, min_samples_leaf=8, random_state=0),
        "random_forest": RandomForestClassifier(n_estimators=180, max_depth=6, min_samples_leaf=4, random_state=0),
    }

    metrics: dict[str, Any] = {}
    fitted: dict[str, Any] = {}
    for name, model in models.items():
        model.fit(x[train_idx], y[train_idx])
        pred = model.predict(x[test_idx])
        metrics[name] = {
            "accuracy": float(accuracy_score(y[test_idx], pred)),
            "macro_f1": float(f1_score(y[test_idx], pred, average="macro")),
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


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / f"learned_state_metacontroller_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    targeted_cases, broad_cases, refs = _load_canonical_cases()
    train_cases = _collect_training_cases()
    dataset_rows = _generate_labeled_rows(train_cases, max_steps_per_case=3)

    train_info = _train_models(dataset_rows)
    best_model = train_info["best_model"]

    targeted_eval_rows: list[dict[str, Any]] = []
    broad_eval_rows: list[dict[str, Any]] = []
    for slice_name, cases, sink in [("targeted", targeted_cases, targeted_eval_rows), ("broad", broad_cases, broad_eval_rows)]:
        old_rows = _method_rows(cases, OLD_METHOD, "old_current_full")
        width_rows = _method_rows(cases, WIDTH_DEPTH_METHOD, "width_depth_challenger_guard")
        near_rows = _method_rows(cases, NEAR_MISS_METHOD, "near_miss_correction_gate")
        heur_rows = [_policy_rollout(c, "heuristic") for c in cases]
        learn_rows = [_policy_rollout(c, "learned", best_model) for c in cases]
        sink.extend(old_rows + width_rows + near_rows + heur_rows + learn_rows)

    def per_mode(rows: list[dict[str, Any]]) -> dict[str, Any]:
        modes = sorted({str(r["mode"]) for r in rows})
        return {m: _summarize([r for r in rows if str(r["mode"]) == m]) for m in modes}

    targeted_summary = per_mode(targeted_eval_rows)
    broad_summary = per_mode(broad_eval_rows)

    targeted_improvement_count = int(
        sum(
            1
            for c in targeted_cases
            if any(r["mode"] == "learned" and r["dataset"] == c.dataset and r["example_id"] == c.example_id and r["budget"] == c.budget and r["is_correct"] for r in targeted_eval_rows)
            and any(r["mode"] == "old_current_full" and r["dataset"] == c.dataset and r["example_id"] == c.example_id and r["budget"] == c.budget and (not r["is_correct"]) for r in targeted_eval_rows)
        )
    )
    broad_improvement_count = int(
        sum(
            1
            for c in broad_cases
            if any(r["mode"] == "learned" and r["dataset"] == c.dataset and r["example_id"] == c.example_id and r["budget"] == c.budget and r["is_correct"] for r in broad_eval_rows)
            and any(r["mode"] == "old_current_full" and r["dataset"] == c.dataset and r["example_id"] == c.example_id and r["budget"] == c.budget and (not r["is_correct"]) for r in broad_eval_rows)
        )
    )

    # artifacts
    json.dump(
        {
            "created_at_utc": ts,
            "references": refs,
            "training_cases": len(train_cases),
            "training_dataset_rows": len(dataset_rows),
            "targeted_cases": len(targeted_cases),
            "broad_cases": len(broad_cases),
        },
        (out_dir / "training_dataset_summary.json").open("w", encoding="utf-8"),
        indent=2,
    )
    json.dump({"feature_names": FEATURES, "action_space": ACTIONS}, (out_dir / "feature_schema.json").open("w", encoding="utf-8"), indent=2)
    (out_dir / "label_generation_description.md").write_text(
        "\n".join(
            [
                "# Label generation",
                "",
                "For each state snapshot at step *t* from the old current-full controller, the script runs four bounded localized what-if continuations",
                "with a one-step forced action (`refine_incumbent`, `verify_incumbent`, `widen_to_challenger`, `commit`) and scores final outcomes by:",
                "`score = correctness + 0.07 * gold_group_present_final - 0.002 * actions_used`.",
                "The argmax action is used as the supervision label.",
            ]
        ),
        encoding="utf-8",
    )
    json.dump(
        {
            "best_model": train_info["best_name"],
            "metrics": train_info["metrics"],
            "train_size": train_info["train_size"],
            "test_size": train_info["test_size"],
            "targeted_summary": targeted_summary,
            "broad_summary": broad_summary,
            "targeted_improvement_count": targeted_improvement_count,
            "broad_improvement_count": broad_improvement_count,
        },
        (out_dir / "model_metrics.json").open("w", encoding="utf-8"),
        indent=2,
    )
    _write_csv(out_dir / "feature_importance.csv", train_info["importance_rows"])
    _write_csv(out_dir / "training_state_dataset.csv", [{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()} for r in dataset_rows])
    _write_csv(out_dir / "targeted_slice_predictions.csv", targeted_eval_rows)
    _write_csv(out_dir / "broader_surface_predictions.csv", broad_eval_rows)

    comparison = {
        "targeted": targeted_summary,
        "broader": broad_summary,
        "old_method": OLD_METHOD,
        "learned_method": LEARNED_METHOD_NAME,
        "training_dataset_size": len(dataset_rows),
        "targeted_improvement_count": targeted_improvement_count,
        "broader_improvement_count": broad_improvement_count,
    }
    (out_dir / "before_after_evaluation_summary.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    doc_path = REPO_ROOT / f"docs/LEARNED_STATE_METACONTROLLER_REPORT_{ts}.md"
    lines = [
        f"# Learned state-level metacontroller report ({ts})",
        "",
        "## Motivation",
        "The current controller family reaches plausible neighborhoods but often under-specifies the next action choice among refine/verify/widen/commit.",
        "This pass introduces a bounded learned action policy over controller state to replace brittle one-off thresholds.",
        "",
        "## Canonical inputs read",
    ]
    for k, v in refs.items():
        lines.append(f"- {k}: `{v}`")
    lines += [
        "",
        "## Feature set",
        "- State features are action-local frontier signals emitted by the current controller: support concentration, continuation value, diversity/duplicate terms,",
        "  anti-collapse penalties, uncertainty/near-miss flags, and short action history indicators.",
        f"- Exact feature schema written to `{(out_dir / 'feature_schema.json').relative_to(REPO_ROOT).as_posix()}`.",
        "",
        "## Label generation",
        "- For each sampled state snapshot, perform bounded one-step forced-action localized rollouts over all four actions.",
        "- Select argmax final-outcome score as the training label.",
        f"- Detailed description: `{(out_dir / 'label_generation_description.md').relative_to(REPO_ROOT).as_posix()}`.",
        "",
        "## Models tried",
    ]
    for model_name, m in train_info["metrics"].items():
        lines.append(f"- `{model_name}`: accuracy={m['accuracy']:.3f}, macro_f1={m['macro_f1']:.3f}")
    lines += [
        f"- Selected model: `{train_info['best_name']}`.",
        "",
        "## Evaluation",
        "### Targeted difficult slice",
    ]
    for mode, sm in targeted_summary.items():
        lines.append(f"- {mode}: acc={sm['accuracy']:.3f}, correct={sm['correct']}/{sm['n_cases']}, mean_actions={sm['mean_actions']:.2f}")
    lines += [
        f"- Improvement count vs old current-full: {targeted_improvement_count}.",
        "",
        "### Broader surface",
    ]
    for mode, sm in broad_summary.items():
        lines.append(f"- {mode}: acc={sm['accuracy']:.3f}, correct={sm['correct']}/{sm['n_cases']}, mean_actions={sm['mean_actions']:.2f}")
    lines += [
        f"- Improvement count vs old current-full: {broad_improvement_count}.",
        "",
        "## Action tendency diagnostics",
        "- Per-case learned policy actions are in targeted/broader prediction CSVs.",
        "- Feature importance exported for interpretability.",
        "",
        "## Honest conclusion",
        "The learned policy is a bounded extension of the current controller and can be directly compared against incumbent guarded variants.",
        "If gains are small or mixed on broader surfaces, this report should be treated as evidence for further calibration rather than a definitive replacement.",
        "",
        "## Required final fields",
        f"- old current full method name: `{OLD_METHOD}`",
        f"- new learned metacontroller method name: `{LEARNED_METHOD_NAME}`",
        f"- training dataset size: `{len(dataset_rows)}`",
        f"- targeted-slice improvement count: `{targeted_improvement_count}`",
        f"- broader-surface improvement count: `{broad_improvement_count}`",
        f"- docs report path: `{doc_path.relative_to(REPO_ROOT).as_posix()}`",
        f"- output bundle path: `{out_dir.relative_to(REPO_ROOT).as_posix()}`",
    ]
    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"old current full method name: {OLD_METHOD}")
    print(f"new learned metacontroller method name: {LEARNED_METHOD_NAME}")
    print(f"training dataset size: {len(dataset_rows)}")
    print(f"targeted-slice improvement count: {targeted_improvement_count}")
    print(f"broader-surface improvement count: {broad_improvement_count}")
    print(f"docs report path: {doc_path.relative_to(REPO_ROOT)}")
    print(f"output bundle path: {out_dir.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
