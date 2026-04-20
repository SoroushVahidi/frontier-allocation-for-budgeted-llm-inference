#!/usr/bin/env python3
"""Rerun canonical 20 defeat cases under current tuned promoted method and compare vs old trees."""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchActionResult, BranchState, SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies

OLD_TREE_DIR = REPO_ROOT / "outputs/twenty_defeat_case_trees_20260419"
AUDIT_DIR = REPO_ROOT / "outputs/full_comparative_mistake_audit_vs_best_method_20260418"
OUT_DIR = REPO_ROOT / "outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420"
DOC_OUT = REPO_ROOT / "docs/TWENTY_CASE_OLD_VS_CURRENT_TUNED_TREE_COMPARISON_2026_04_20.md"

OLD_METHOD = "broad_diversity_aggregation_v1"
CURRENT_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
BEST_METHOD = "self_consistency_3"


@dataclass
class DecisionSnapshot:
    decision_index: int
    action: str
    chosen_branch_id: str
    remaining_budget_before: int
    active_frontier_before: list[str]
    branch_states_before: list[dict[str, Any]]


class ObservedGenerator:
    """Wrap SimulatedBranchGenerator and capture detailed branch observability."""

    def __init__(self, base: SimulatedBranchGenerator) -> None:
        self.base = base
        self.registry: dict[str, BranchState] = {}
        self.events: list[dict[str, Any]] = []
        self.decision_snaps: list[DecisionSnapshot] = []
        self._decision_counter = 0

    def _branch_family_id(self, branch_id: str) -> str:
        if branch_id.startswith("div_child_"):
            parts = branch_id.split("_")
            if len(parts) >= 3:
                return f"div_{parts[2]}"
        return branch_id

    def _snapshot_branch(self, b: BranchState) -> dict[str, Any]:
        return {
            "branch_id": b.branch_id,
            "branch_family_id": self._branch_family_id(b.branch_id),
            "score": float(b.score),
            "depth": int(b.depth),
            "verify_count": int(b.verify_count),
            "stalled_steps": int(b.stalled_steps),
            "recent_delta": float(b.recent_delta),
            "branch_age": int(b.branch_age),
            "is_done": bool(b.is_done),
            "is_pruned": bool(b.is_pruned),
            "predicted_answer": b.predicted_answer,
            "reasoning_text": "\n".join(b.steps),
            "action_history": list(b.action_history),
        }

    def _active_snapshot(self) -> list[dict[str, Any]]:
        active = [b for b in self.registry.values() if not b.is_pruned]
        active.sort(key=lambda x: x.branch_id)
        return [self._snapshot_branch(b) for b in active]

    def init_branch(self, branch_id: str) -> BranchState:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        self.events.append({"event": "init_branch", "branch_id": b.branch_id, "branch_family_id": self._branch_family_id(b.branch_id), "score": float(b.score)})
        return b

    def expand(self, branch: BranchState, question: str, gold_answer: str) -> BranchActionResult:
        active_before = [x["branch_id"] for x in self._active_snapshot()]
        self.decision_snaps.append(
            DecisionSnapshot(
                decision_index=self._decision_counter,
                action="expand",
                chosen_branch_id=branch.branch_id,
                remaining_budget_before=-1,
                active_frontier_before=active_before,
                branch_states_before=self._active_snapshot(),
            )
        )
        self._decision_counter += 1
        before = self._snapshot_branch(branch)
        out = self.base.expand(branch, question, gold_answer)
        after = self._snapshot_branch(branch)
        self.events.append(
            {
                "event": "expand",
                "branch_id": branch.branch_id,
                "branch_family_id": self._branch_family_id(branch.branch_id),
                "before": before,
                "after": after,
                "score_after": float(out.score_after),
                "became_done": bool(out.became_done),
            }
        )
        return out

    def verify(self, branch: BranchState, question: str) -> BranchActionResult:
        active_before = [x["branch_id"] for x in self._active_snapshot()]
        self.decision_snaps.append(
            DecisionSnapshot(
                decision_index=self._decision_counter,
                action="verify",
                chosen_branch_id=branch.branch_id,
                remaining_budget_before=-1,
                active_frontier_before=active_before,
                branch_states_before=self._active_snapshot(),
            )
        )
        self._decision_counter += 1
        before = self._snapshot_branch(branch)
        out = self.base.verify(branch, question)
        after = self._snapshot_branch(branch)
        self.events.append(
            {
                "event": "verify",
                "branch_id": branch.branch_id,
                "branch_family_id": self._branch_family_id(branch.branch_id),
                "before": before,
                "after": after,
                "score_after": float(out.score_after),
            }
        )
        return out

    def prune(self, branch: BranchState) -> BranchActionResult:
        out = self.base.prune(branch)
        self.events.append({"event": "prune", "branch_id": branch.branch_id, "branch_family_id": self._branch_family_id(branch.branch_id)})
        return out


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _stable_seed(*parts: Any) -> int:
    src = "||".join(str(x) for x in parts)
    return int(hashlib.sha256(src.encode("utf-8")).hexdigest()[:8], 16)


def _case_id(dataset: str, example_id: str) -> str:
    return f"{dataset.replace('/', '__')}__{example_id}"


def _select_cases_from_old_manifest() -> list[dict[str, Any]]:
    manifest = _read_json(OLD_TREE_DIR / "manifest.json")
    rows = manifest.get("cases", [])
    if len(rows) != 20:
        raise RuntimeError(f"Expected exactly 20 canonical cases in old manifest, got {len(rows)}")
    return rows


def _load_old_case_json(dataset: str, example_id: str) -> dict[str, Any]:
    cid = _case_id(dataset, example_id)
    return _read_json(OLD_TREE_DIR / f"{cid}.json")


def _find_old_record(dataset: str, example_id: str, seed: int, budget: int) -> dict[str, Any]:
    rows = _read_jsonl(AUDIT_DIR / "all_mistake_records.jsonl")
    matches = [r for r in rows if str(r.get("dataset")) == dataset and str(r.get("example_id")) == example_id and int(r.get("seed", -1)) == seed and int(r.get("budget", -1)) == budget]
    if matches:
        return matches[0]
    fallback = [r for r in rows if str(r.get("dataset")) == dataset and str(r.get("example_id")) == example_id]
    if fallback:
        return sorted(fallback, key=lambda r: (int(r.get("seed", 0)), int(r.get("budget", 0))), reverse=True)[0]
    raise RuntimeError(f"No old mistake record found for {dataset}/{example_id}")


def _run_case_current(row: dict[str, Any], old_case: dict[str, Any]) -> dict[str, Any]:
    dataset = str(row["dataset"])
    example_id = str(row["example_id"])
    question = str(old_case["problem_statement"])
    gold = str(old_case["ground_truth_answer"])
    budget = int(old_case["original_failure_record"]["budget"])
    seed = int(old_case["original_failure_record"]["seed"])

    replay_seed = _stable_seed("current_tuned_compare", dataset, example_id, seed, budget)
    rng = random.Random(replay_seed)
    observed_gen = ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))

    def factory() -> ObservedGenerator:
        return observed_gen

    strategies = build_frontier_strategies(factory, budget, [1], rng, use_openai_api=False, include_broad_diversity_aggregation_methods=True)
    current = strategies[CURRENT_METHOD].run(question, gold)

    best_rng = random.Random(_stable_seed("current_tuned_compare_best", dataset, example_id, seed, budget))

    def best_factory() -> SimulatedBranchGenerator:
        return SimulatedBranchGenerator(rng=best_rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)

    best_strategies = build_frontier_strategies(best_factory, budget, [1], best_rng, use_openai_api=False, include_broad_diversity_aggregation_methods=True)
    best = best_strategies[BEST_METHOD].run(question, gold)

    for i, snap in enumerate(observed_gen.decision_snaps):
        snap.remaining_budget_before = max(0, budget - i)

    parent_map: dict[str, str] = {}
    last_expand: str | None = None
    for ev in observed_gen.events:
        if ev["event"] == "expand":
            last_expand = str(ev["branch_id"])
        elif ev["event"] == "init_branch" and last_expand is not None and str(ev["branch_id"]).startswith("div_child_"):
            parent_map[str(ev["branch_id"])] = last_expand

    action_trace = list(current.metadata.get("action_trace", []))
    decisions: list[dict[str, Any]] = []
    for i, snap in enumerate(observed_gen.decision_snaps):
        trace = action_trace[i] if i < len(action_trace) else {}
        chosen_family = observed_gen._branch_family_id(snap.chosen_branch_id)
        decisions.append(
            {
                "decision_index": int(snap.decision_index),
                "action": snap.action,
                "chosen_branch_id": snap.chosen_branch_id,
                "chosen_branch_family_id": chosen_family,
                "remaining_budget_before": int(snap.remaining_budget_before),
                "remaining_budget_after": max(0, int(snap.remaining_budget_before) - 1),
                "budget_used_this_step": 1,
                "active_frontier_before": list(snap.active_frontier_before),
                "active_branch_states_before": snap.branch_states_before,
                "trace_metadata": {
                    "priority": trace.get("priority"),
                    "continuation_value": trace.get("continuation_value"),
                    "target_alignment_score": trace.get("target_alignment_score"),
                    "target_alignment_category": trace.get("target_alignment_category"),
                    "group_key": trace.get("group_key"),
                    "anti_collapse_repeat_penalty": trace.get("anti_collapse_repeat_penalty"),
                    "anti_collapse_repeat_expand_exact_penalty": trace.get("anti_collapse_repeat_expand_exact_penalty"),
                    "anti_collapse_repeat_expand_family_penalty": trace.get("anti_collapse_repeat_expand_family_penalty"),
                    "anti_collapse_repeat_expand_override_applied": trace.get("anti_collapse_repeat_expand_override_applied"),
                },
            }
        )

    final_branches = []
    for b in sorted(observed_gen.registry.values(), key=lambda x: x.branch_id):
        final_branches.append(
            {
                "branch_id": b.branch_id,
                "branch_family_id": observed_gen._branch_family_id(b.branch_id),
                "parent_branch_id": parent_map.get(b.branch_id),
                "depth": int(b.depth),
                "verify_count": int(b.verify_count),
                "is_done": bool(b.is_done),
                "is_pruned": bool(b.is_pruned),
                "predicted_answer": b.predicted_answer,
                "normalized_answer": None if b.predicted_answer is None else str(b.predicted_answer).strip(),
                "answer_group_assignment": None if b.predicted_answer is None else str(b.predicted_answer).strip(),
                "reasoning_text": "\n".join(b.steps),
                "action_history": list(b.action_history),
            }
        )

    gold_norm = gold.strip()
    gold_present_nodes = [b["branch_id"] for b in final_branches if (b.get("normalized_answer") == gold_norm)]

    by_family = defaultdict(int)
    for d in decisions:
        by_family[str(d.get("chosen_branch_family_id"))] += 1
    max_family_repeat = max(by_family.values()) if by_family else 0

    metadata = current.metadata
    return {
        "dataset": dataset,
        "example_id": example_id,
        "problem_statement": question,
        "ground_truth_answer": gold,
        "run_setup": {
            "seed": seed,
            "budget": budget,
            "replay_seed": replay_seed,
            "method": CURRENT_METHOD,
        },
        "outputs": {
            "current_method_prediction": current.prediction,
            "current_method_prediction_normalized": None if current.prediction is None else str(current.prediction).strip(),
            "current_method_correct": bool(current.is_correct),
            "self_consistency_3_prediction": best.prediction,
            "self_consistency_3_correct": bool(best.is_correct),
            "selected_group": metadata.get("selected_group"),
            "final_selected_branch_or_node": metadata.get("selected_branch_id"),
        },
        "observability": {
            "provenance": "exact_from_rerun_observability",
            "decisions": decisions,
            "events": observed_gen.events,
            "final_tree": {
                "parent_links_inference": "inferred_from_child_creation_events_after_expand",
                "branches": final_branches,
            },
        },
        "tree_summary": {
            "branches_created": len([e for e in observed_gen.events if e.get("event") == "init_branch"]),
            "max_depth": max((int(b["depth"]) for b in final_branches), default=0),
            "expand_actions": sum(1 for d in decisions if d["action"] == "expand"),
            "verify_actions": sum(1 for d in decisions if d["action"] == "verify"),
            "surviving_frontier_end": len([b for b in final_branches if not b["is_pruned"] and not b["is_done"]]),
            "repeated_same_family_expansion_count": metadata.get("repeated_same_family_expansion_count"),
            "repeated_same_family_expansion_rate": metadata.get("repeated_same_family_expansion_rate"),
            "matured_alternative_count": metadata.get("matured_alternative_count"),
            "max_family_repeat_count_from_decisions": max_family_repeat,
        },
        "correct_answer_in_tree": {
            "exists": bool(gold_present_nodes),
            "node_ids": gold_present_nodes,
        },
        "metadata": {
            "unique_answer_groups_seen": metadata.get("unique_answer_groups_seen"),
            "answer_group_diversity_realized": metadata.get("answer_group_diversity_realized"),
            "repeated_same_branch_expansion_count": metadata.get("repeated_same_branch_expansion_count"),
            "repeated_same_branch_expansion_rate": metadata.get("repeated_same_branch_expansion_rate"),
            "repeat_penalty_trigger_count": metadata.get("repeat_penalty_trigger_count"),
            "repeat_penalty_override_count": metadata.get("repeat_penalty_override_count"),
            "repeat_penalty_alternative_selected_count": metadata.get("repeat_penalty_alternative_selected_count"),
            "gold_group_ever_present": metadata.get("gold_group_ever_present"),
            "gold_group_present_final": metadata.get("gold_group_present_final"),
        },
    }


def _compact_tree_summary(case: dict[str, Any]) -> str:
    ts = case["tree_summary"]
    return (
        f"created={ts['branches_created']}, depth={ts['max_depth']}, expand={ts['expand_actions']}, "
        f"verify={ts['verify_actions']}, surviving_end={ts['surviving_frontier_end']}"
    )


def _verdict(structural_improved: bool, final_improved: bool, changed: bool) -> str:
    if structural_improved and final_improved:
        return "improved structurally"
    if final_improved and not structural_improved:
        return "improved only in final answer"
    if changed and not (structural_improved or final_improved):
        return "regressed"
    if structural_improved:
        return "improved structurally"
    return "unchanged"


def _write_text_tree(case: dict[str, Any], out_path: Path) -> None:
    lines = [f"Case: {case['dataset']} / {case['example_id']}", "root"]
    branches = case["observability"]["final_tree"]["branches"]
    by_parent: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for b in branches:
        by_parent[b.get("parent_branch_id")].append(b)
    for k in by_parent:
        by_parent[k] = sorted(by_parent[k], key=lambda x: str(x["branch_id"]))

    def rec(node: str | None, indent: int) -> None:
        for b in by_parent.get(node, []):
            status = "done" if b["is_done"] else ("pruned" if b["is_pruned"] else "active")
            lines.append(
                "  " * indent
                + f"- {b['branch_id']} [family={b['branch_family_id']}, depth={b['depth']}, verify={b['verify_count']}, status={status}, answer={b['normalized_answer']}]"
            )
            rec(b["branch_id"], indent + 1)

    rec(None, 1)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text_tree_dir = OUT_DIR / "text_trees"
    text_tree_dir.mkdir(parents=True, exist_ok=True)

    case_manifest = _select_cases_from_old_manifest()

    per_case_current_tree: list[dict[str, Any]] = []
    per_case_comparison: list[dict[str, Any]] = []

    changed_final_answer = 0
    materially_changed_tree = 0
    reduced_same_family = 0
    increased_matured_alternatives = 0
    contain_correct_now = 0
    select_correct_now = 0
    improved_structural_count = 0
    improved_final_correctness_count = 0

    for m in case_manifest:
        dataset = str(m["dataset"])
        example_id = str(m["example_id"])
        old_case = _load_old_case_json(dataset, example_id)
        seed = int(old_case["original_failure_record"]["seed"])
        budget = int(old_case["original_failure_record"]["budget"])
        old_record = _find_old_record(dataset, example_id, seed, budget)

        current_case = _run_case_current(m, old_case)
        per_case_current_tree.append(current_case)

        old_answer = str(old_case["original_failure_record"].get("our_method_final_answer"))
        current_answer = str(current_case["outputs"].get("current_method_prediction"))
        self_consistency_answer = str(old_record.get("best_method_final_answer"))
        gt = str(current_case["ground_truth_answer"])

        old_repeat = old_case.get("recovered_run", {}).get("our_method_metadata", {}).get("repeated_same_family_expansion_rate")
        curr_repeat = current_case["tree_summary"].get("repeated_same_family_expansion_rate")
        old_matured = old_case.get("recovered_run", {}).get("our_method_metadata", {}).get("matured_alternative_count")
        curr_matured = current_case["tree_summary"].get("matured_alternative_count")

        final_changed = old_answer != current_answer
        if final_changed:
            changed_final_answer += 1

        tree_changed = _compact_tree_summary(old_case) != _compact_tree_summary(current_case)
        if tree_changed:
            materially_changed_tree += 1

        repeat_reduced = (curr_repeat is not None and (old_repeat is None or float(curr_repeat) < float(old_repeat)))
        if repeat_reduced:
            reduced_same_family += 1

        matured_increased = (curr_matured is not None and (old_matured is None or float(curr_matured) > float(old_matured)))
        if matured_increased:
            increased_matured_alternatives += 1

        correct_in_current_tree = bool(current_case["correct_answer_in_tree"]["exists"])
        if correct_in_current_tree:
            contain_correct_now += 1

        current_selected_correct = current_answer.strip() == gt.strip()
        if current_selected_correct:
            select_correct_now += 1

        structural_improved = repeat_reduced or matured_increased or tree_changed
        final_improved = (old_answer.strip() != gt.strip()) and current_selected_correct
        changed_any = final_changed or tree_changed
        verdict = _verdict(structural_improved, final_improved, changed_any)

        if structural_improved:
            improved_structural_count += 1
        if final_improved:
            improved_final_correctness_count += 1

        if not old_case.get("recovered_run", {}).get("our_method_metadata", {}).get("gold_group_present_final", False):
            old_correct_status = "absent from old tree"
        elif not correct_in_current_tree:
            old_correct_status = "absent from current tree"
        elif correct_in_current_tree and not current_selected_correct:
            old_correct_status = "present in current tree but not selected"
        else:
            old_correct_status = "selected in current tree"

        comparison = {
            "dataset": dataset,
            "example_id": example_id,
            "problem_statement": current_case["problem_statement"],
            "ground_truth_answer": gt,
            "old_method_name": OLD_METHOD,
            "old_method_answer": old_answer,
            "current_method_name": CURRENT_METHOD,
            "current_tuned_method_answer": current_answer,
            "self_consistency_3_answer": self_consistency_answer,
            "old_method_tree_summary": _compact_tree_summary(old_case),
            "current_method_tree_summary": _compact_tree_summary(current_case),
            "current_repeats_same_family_too_much": bool(curr_repeat is not None and float(curr_repeat) >= 0.55),
            "alternatives_matured_better_than_before": matured_increased,
            "correct_answer_status": old_correct_status,
            "verdict": verdict,
            "metrics": {
                "old_repeated_same_family_expansion_rate": old_repeat,
                "current_repeated_same_family_expansion_rate": curr_repeat,
                "old_matured_alternative_count": old_matured,
                "current_matured_alternative_count": curr_matured,
                "old_gold_group_present_final": old_case.get("recovered_run", {}).get("our_method_metadata", {}).get("gold_group_present_final"),
                "current_correct_in_tree": correct_in_current_tree,
                "current_selected_correct": current_selected_correct,
            },
        }
        per_case_comparison.append(comparison)

        cid = _case_id(dataset, example_id)
        _write_text_tree(current_case, text_tree_dir / f"{cid}.txt")

    summary = {
        "method_identities": {
            "old_method": OLD_METHOD,
            "current_method": CURRENT_METHOD,
            "comparison_target": BEST_METHOD,
        },
        "case_set_source": str(OLD_TREE_DIR / "manifest.json"),
        "total_cases": len(case_manifest),
        "changed_final_answer_count": changed_final_answer,
        "materially_changed_tree_shape_count": materially_changed_tree,
        "reduced_repeated_same_family_expansion_count": reduced_same_family,
        "increased_matured_alternatives_count": increased_matured_alternatives,
        "current_contains_correct_answer_in_tree_count": contain_correct_now,
        "current_selects_correct_answer_count": select_correct_now,
        "improved_structurally_count": improved_structural_count,
        "improved_final_correctness_count": improved_final_correctness_count,
        "dominant_old_failure_pattern_status": (
            "reduced" if reduced_same_family >= 10 else "still_dominant"
        ),
    }

    manifest = {
        "description": "Frozen canonical 20-case manifest for old-vs-current tuned rerun",
        "method_identities": summary["method_identities"],
        "cases": [
            {
                "dataset": str(c["dataset"]),
                "example_id": str(c["example_id"]),
                "case_id": _case_id(str(c["dataset"]), str(c["example_id"])),
            }
            for c in case_manifest
        ],
    }

    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "per_case_current_tree.json").write_text(json.dumps({"cases": per_case_current_tree}, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "per_case_comparison.json").write_text(json.dumps({"cases": per_case_comparison}, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Twenty-case old-vs-current tuned tree comparison (2026-04-20)",
        "",
        "## Method identities",
        f"- Old method: `{OLD_METHOD}`",
        f"- Current method (promoted tuned): `{CURRENT_METHOD}`",
        f"- Comparison target: `{BEST_METHOD}`",
        "",
        "## Case-set freeze",
        "- Source manifest: `outputs/twenty_defeat_case_trees_20260419/manifest.json`.",
        f"- Case count: **{len(case_manifest)}** (exactly frozen; unchanged).",
        "",
        "## Aggregate summary",
        f"- Changed final answer: **{summary['changed_final_answer_count']} / {summary['total_cases']}**",
        f"- Materially changed tree shape: **{summary['materially_changed_tree_shape_count']} / {summary['total_cases']}**",
        f"- Reduced repeated same-family expansion: **{summary['reduced_repeated_same_family_expansion_count']} / {summary['total_cases']}**",
        f"- Increased matured alternatives: **{summary['increased_matured_alternatives_count']} / {summary['total_cases']}**",
        f"- Current tree contains correct answer: **{summary['current_contains_correct_answer_in_tree_count']} / {summary['total_cases']}**",
        f"- Current method selects correct answer: **{summary['current_selects_correct_answer_count']} / {summary['total_cases']}**",
        f"- Main old failure pattern status: **{summary['dominant_old_failure_pattern_status']}**",
        "",
        "## Per-case compact comparison",
    ]

    for idx, c in enumerate(per_case_comparison, start=1):
        lines.extend(
            [
                f"### Case {idx}: `{c['dataset']} / {c['example_id']}`",
                f"1. Ground truth: `{c['ground_truth_answer']}`",
                f"2. Old method answer (`{OLD_METHOD}`): `{c['old_method_answer']}`",
                f"3. Current tuned answer (`{CURRENT_METHOD}`): `{c['current_tuned_method_answer']}`",
                f"4. `self_consistency_3` answer: `{c['self_consistency_3_answer']}`",
                f"5. Old tree summary: `{c['old_method_tree_summary']}`",
                f"6. Current tree summary: `{c['current_method_tree_summary']}`",
                f"7. Current repeats same family too much: `{c['current_repeats_same_family_too_much']}`",
                f"8. Alternatives matured better: `{c['alternatives_matured_better_than_before']}`",
                f"9. Correct-answer status: `{c['correct_answer_status']}`",
                f"10. Verdict: `{c['verdict']}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Key success question answer",
            (
                "On the same 20 old defeat cases, the current tuned promoted method shows "
                f"**{summary['dominant_old_failure_pattern_status']}** branch-family collapse behavior "
                f"(reduced same-family expansion in {summary['reduced_repeated_same_family_expansion_count']}/{summary['total_cases']} cases)."
            ),
            "",
            "## Output artifacts",
            "- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/manifest.json`",
            "- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/per_case_current_tree.json`",
            "- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/per_case_comparison.json`",
            "- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/summary.json`",
            "- `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/text_trees/*.txt`",
        ]
    )

    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
