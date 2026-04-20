#!/usr/bin/env python3
"""Build canonical exact 20-case observability comparison: our method vs self_consistency_3."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchActionResult, BranchState, SimulatedBranchGenerator
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import build_frontier_strategies

AUDIT_DIR = REPO_ROOT / "outputs/full_comparative_mistake_audit_vs_best_method_20260418"
OUT_ROOT = REPO_ROOT / "outputs/twenty_exact_ours_vs_self_consistency_tree_comparison_20260420"
CASE_DIR = OUT_ROOT / "cases"
TEXT_DIR = OUT_ROOT / "case_text_structures"
MANIFEST_PATH = OUT_ROOT / "selected_case_manifest.json"
SUMMARY_PATH = OUT_ROOT / "summary.json"
DOC_PATH = REPO_ROOT / "docs/TWENTY_EXACT_OURS_VS_SELF_CONSISTENCY_TREE_COMPARISON_2026_04_20.md"

OUR_METHOD = "broad_diversity_aggregation_v1"
OTHER_METHOD = "self_consistency_3"


@dataclass
class DecisionEvent:
    step: int
    action: str
    branch_id: str
    remaining_budget_before: int


class ObservedGenerator:
    """Captures rich branch-level observability around a branch generator."""

    def __init__(self, base: SimulatedBranchGenerator) -> None:
        self.base = base
        self.events: list[dict[str, Any]] = []
        self.registry: dict[str, BranchState] = {}
        self.decision_events: list[DecisionEvent] = []
        self._step = 0

    def _snapshot(self, b: BranchState) -> dict[str, Any]:
        reasoning = "\n".join(str(x) for x in b.steps).strip() if b.steps else ""
        return {
            "branch_id": b.branch_id,
            "score": float(b.score),
            "depth": int(b.depth),
            "verify_count": int(b.verify_count),
            "stalled_steps": int(b.stalled_steps),
            "recent_delta": float(b.recent_delta),
            "branch_age": int(b.branch_age),
            "is_done": bool(b.is_done),
            "is_pruned": bool(b.is_pruned),
            "predicted_answer": b.predicted_answer,
            "predicted_answer_normalized": normalize_answer_text(str(b.predicted_answer) if b.predicted_answer is not None else None).get("normalized_answer"),
            "action_history": list(b.action_history),
            "score_history": [float(x) for x in b.score_history],
            "depth_history": [int(x) for x in b.depth_history],
            "reasoning_text": reasoning,
        }

    def init_branch(self, branch_id: str) -> BranchState:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        self.events.append({"event": "init_branch", "step": self._step, "branch_id": b.branch_id, "snapshot": self._snapshot(b)})
        return b

    def expand(self, branch: BranchState, question: str, gold_answer: str) -> BranchActionResult:
        before = self._snapshot(branch)
        self.decision_events.append(DecisionEvent(self._step, "expand", branch.branch_id, -1))
        out = self.base.expand(branch, question, gold_answer)
        after = self._snapshot(branch)
        self.events.append(
            {
                "event": "expand",
                "step": self._step,
                "branch_id": branch.branch_id,
                "before": before,
                "after": after,
                "score_after": float(out.score_after),
                "became_done": bool(out.became_done),
            }
        )
        self._step += 1
        return out

    def verify(self, branch: BranchState, question: str) -> BranchActionResult:
        before = self._snapshot(branch)
        self.decision_events.append(DecisionEvent(self._step, "verify", branch.branch_id, -1))
        out = self.base.verify(branch, question)
        after = self._snapshot(branch)
        self.events.append(
            {
                "event": "verify",
                "step": self._step,
                "branch_id": branch.branch_id,
                "before": before,
                "after": after,
                "score_after": float(out.score_after),
            }
        )
        self._step += 1
        return out

    def prune(self, branch: BranchState) -> BranchActionResult:
        out = self.base.prune(branch)
        self.events.append({"event": "prune", "step": self._step, "branch_id": branch.branch_id, "snapshot": self._snapshot(branch)})
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
    s = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def _case_id(dataset: str, example_id: str) -> str:
    return f"{dataset.replace('/', '__')}__{example_id}"


def _select_twenty_cases() -> list[dict[str, Any]]:
    ranked = _read_json(AUDIT_DIR / "ranked_casebook_records.json")
    mistakes = _read_jsonl(AUDIT_DIR / "all_mistake_records.jsonl")
    failures = [
        r for r in mistakes if bool(r.get("best_method_correct")) and (not bool(r.get("our_method_correct")))
    ]
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in failures:
        key = (str(row.get("dataset")), str(row.get("example_id")))
        by_key.setdefault(key, []).append(row)

    selected: list[dict[str, Any]] = []
    for rr in ranked:
        key = (str(rr.get("dataset")), str(rr.get("example_id")))
        rows = by_key.get(key, [])
        if not rows:
            continue
        representative = sorted(rows, key=lambda r: (int(r.get("budget", 0)), int(r.get("seed", 0))), reverse=True)[0]
        selected.append(representative)
        if len(selected) >= 20:
            break
    if len(selected) != 20:
        raise RuntimeError(f"expected 20 selected cases but found {len(selected)}")
    return selected


def _run_with_observability(method_name: str, row: dict[str, Any]) -> dict[str, Any]:
    budget = int(row["budget"])
    seed = int(row["seed"])
    dataset = str(row["dataset"])
    example_id = str(row["example_id"])
    question = str(row["problem_text"])
    gold = str(row["ground_truth"])

    run_seed = _stable_seed("exact_obs", method_name, dataset, example_id, seed, budget)
    rng = random.Random(run_seed)
    observed = ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))

    def factory() -> ObservedGenerator:
        return observed

    strategies = build_frontier_strategies(
        factory,
        budget,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    result = strategies[method_name].run(question, gold)

    for i, ev in enumerate(observed.decision_events):
        ev.remaining_budget_before = max(0, budget - i)

    parent_map: dict[str, str | None] = {}
    last_actor: str | None = None
    for e in observed.events:
        if e["event"] in {"expand", "verify"}:
            last_actor = str(e["branch_id"])
        elif e["event"] == "init_branch":
            bid = str(e["branch_id"])
            if bid not in parent_map:
                if bid.startswith("div_child") and last_actor is not None:
                    parent_map[bid] = last_actor
                else:
                    parent_map[bid] = None

    final_nodes: list[dict[str, Any]] = []
    for bid, b in sorted(observed.registry.items(), key=lambda kv: kv[0]):
        snap = observed._snapshot(b)
        snap["parent_branch_id"] = parent_map.get(bid)
        fam = bid
        cur = bid
        seen = set()
        while parent_map.get(cur) is not None and cur not in seen:
            seen.add(cur)
            cur = str(parent_map[cur])
            fam = cur
        snap["branch_family_id"] = fam
        final_nodes.append(snap)

    norm_pred = normalize_answer_text(str(result.prediction) if result.prediction is not None else None).get("normalized_answer")
    norm_gold = normalize_answer_text(gold).get("normalized_answer")

    return {
        "method": method_name,
        "run_seed": run_seed,
        "budget": budget,
        "prediction_text": result.prediction,
        "prediction_normalized": norm_pred,
        "gold_normalized": norm_gold,
        "is_correct": bool(result.is_correct),
        "actions_used": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "budget_exhausted": bool(result.budget_exhausted),
        "avg_surviving_branches": float(result.avg_surviving_branches),
        "metadata": result.metadata,
        "events": observed.events,
        "decision_timeline": [ev.__dict__ for ev in observed.decision_events],
        "final_nodes": final_nodes,
    }


def _node_ids_with_answer(nodes: list[dict[str, Any]], normalized_answer: str | None) -> list[str]:
    if normalized_answer is None:
        return []
    ids: list[str] = []
    for n in nodes:
        if n.get("predicted_answer_normalized") == normalized_answer:
            ids.append(str(n.get("branch_id")))
    return ids


def _classify_divergence(our_contains: bool, our_final_correct: bool, our_supporting_nodes: list[str], our_nodes: list[dict[str, Any]], sc_contains: bool) -> str:
    if not our_contains:
        return "absent from frontier"
    if our_final_correct:
        return "other"
    score_map = {str(n.get("branch_id")): float(n.get("score", 0.0)) for n in our_nodes}
    if our_supporting_nodes:
        top_correct_score = max(score_map.get(x, -1e9) for x in our_supporting_nodes)
        top_any_score = max(score_map.values()) if score_map else -1e9
        if top_correct_score < top_any_score:
            return "present but underweighted"
        done_flags = [bool(next((n for n in our_nodes if str(n.get("branch_id")) == x), {}).get("is_done", False)) for x in our_supporting_nodes]
        if not any(done_flags):
            return "present but not matured"
        if sc_contains:
            return "lost by final commit"
    return "other"


def _to_text_tree(nodes: list[dict[str, Any]], root_label: str) -> str:
    children: dict[str | None, list[dict[str, Any]]] = {}
    for n in nodes:
        p = n.get("parent_branch_id")
        children.setdefault(p, []).append(n)
    for v in children.values():
        v.sort(key=lambda x: str(x.get("branch_id")))

    lines = [root_label]

    def rec(parent: str | None, indent: str) -> None:
        for n in children.get(parent, []):
            lines.append(
                f"{indent}- {n.get('branch_id')} [fam={n.get('branch_family_id')}, depth={n.get('depth')}, score={float(n.get('score',0.0)):.4f}, done={n.get('is_done')}, ans={n.get('predicted_answer_normalized')}]"
            )
            rec(str(n.get("branch_id")), indent + "  ")

    rec(None, "")
    return "\n".join(lines)


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    selected = _select_twenty_cases()

    manifest_cases: list[dict[str, Any]] = []
    case_payloads: list[dict[str, Any]] = []

    for idx, row in enumerate(selected, start=1):
        dataset = str(row["dataset"])
        example_id = str(row["example_id"])
        case_id = _case_id(dataset, example_id)

        our_run = _run_with_observability(OUR_METHOD, row)
        sc_run = _run_with_observability(OTHER_METHOD, row)

        gold_norm = normalize_answer_text(str(row["ground_truth"]))["normalized_answer"]
        our_final_node_id = None
        if our_run["final_nodes"]:
            pred = our_run.get("prediction_normalized")
            match_nodes = [n for n in our_run["final_nodes"] if n.get("predicted_answer_normalized") == pred]
            if match_nodes:
                our_final_node_id = str(sorted(match_nodes, key=lambda n: float(n.get("score", 0.0)), reverse=True)[0]["branch_id"])

        sc_vote_counts: dict[str, int] = {}
        for n in sc_run["final_nodes"]:
            ans = str(n.get("predicted_answer_normalized"))
            sc_vote_counts[ans] = sc_vote_counts.get(ans, 0) + 1

        sc_support_nodes = [
            str(n.get("branch_id"))
            for n in sc_run["final_nodes"]
            if n.get("predicted_answer_normalized") == sc_run.get("prediction_normalized")
        ]
        our_correct_nodes = _node_ids_with_answer(our_run["final_nodes"], gold_norm)
        sc_correct_nodes = _node_ids_with_answer(sc_run["final_nodes"], gold_norm)

        our_contains = len(our_correct_nodes) > 0
        sc_contains = len(sc_correct_nodes) > 0
        divergence = _classify_divergence(
            our_contains,
            bool(our_run.get("is_correct")),
            our_correct_nodes,
            our_run["final_nodes"],
            sc_contains,
        )

        case_payload = {
            "case_id": case_id,
            "case_index": idx,
            "dataset": dataset,
            "example_id": example_id,
            "problem_statement": row["problem_text"],
            "ground_truth_answer": row["ground_truth"],
            "ground_truth_normalized": gold_norm,
            "our_method_name": OUR_METHOD,
            "self_consistency_method_name": OTHER_METHOD,
            "recorded_original_outcome": {
                "seed": int(row["seed"]),
                "budget": int(row["budget"]),
                "our_answer": row["our_method_final_answer"],
                "self_consistency_answer": row["best_method_final_answer"],
                "our_correct": bool(row["our_method_correct"]),
                "self_consistency_correct": bool(row["best_method_correct"]),
                "provenance": "exact-directly-recorded",
            },
            "rerun_observability": {
                "our": our_run,
                "self_consistency": {
                    **sc_run,
                    "structure_type": "sample_forest",
                    "vote_counts": sc_vote_counts,
                    "final_answer_supporting_sample_nodes": sc_support_nodes,
                    "provenance": "structurally faithful but non-tree",
                },
            },
            "comparison": {
                "our_final_answer_rerun": our_run.get("prediction_text"),
                "self_consistency_final_answer_rerun": sc_run.get("prediction_text"),
                "our_contains_correct_answer": our_contains,
                "self_consistency_contains_correct_answer": sc_contains,
                "our_final_answer_node_id": our_final_node_id,
                "self_consistency_final_answer_supporting_node_ids": sc_support_nodes,
                "our_correct_answer_node_ids": our_correct_nodes,
                "self_consistency_correct_answer_node_ids": sc_correct_nodes,
                "divergence_category": divergence,
                "major_reasoning_style_labels": {
                    "our": sorted({str(n.get("branch_family_id")) for n in our_run["final_nodes"]})[:8],
                    "self_consistency": sorted({str(n.get("branch_id")) for n in sc_run["final_nodes"]})[:8],
                },
                "budget_usage": {
                    "budget": int(row["budget"]),
                    "our_actions_used": int(our_run["actions_used"]),
                    "self_consistency_actions_used": int(sc_run["actions_used"]),
                    "our_expansions": int(our_run["expansions"]),
                    "self_consistency_expansions": int(sc_run["expansions"]),
                    "our_verifications": int(our_run["verifications"]),
                    "self_consistency_verifications": int(sc_run["verifications"]),
                },
            },
            "provenance_labels": {
                "selected_case_membership": "exact-directly-recorded",
                "problem_and_ground_truth": "exact-directly-recorded",
                "our_structure": "exact-from-rerun-observability",
                "self_consistency_structure": "structurally faithful but non-tree",
                "correct_node_identity_our": "exact-from-rerun-observability" if our_contains else "unavailable",
                "correct_node_identity_self_consistency": "exact-from-rerun-observability" if sc_contains else "unavailable",
            },
        }

        (CASE_DIR / f"{case_id}.json").write_text(json.dumps(case_payload, indent=2) + "\n", encoding="utf-8")

        our_text = _to_text_tree(our_run["final_nodes"], "root")
        sc_text = _to_text_tree(sc_run["final_nodes"], "root(sample_forest)")
        (TEXT_DIR / f"{case_id}_our_tree.txt").write_text(our_text + "\n", encoding="utf-8")
        (TEXT_DIR / f"{case_id}_self_consistency_forest.txt").write_text(sc_text + "\n", encoding="utf-8")

        manifest_cases.append(
            {
                "case_id": case_id,
                "dataset": dataset,
                "example_id": example_id,
                "seed": int(row["seed"]),
                "budget": int(row["budget"]),
                "selection_criterion": "our_wrong_and_self_consistency_3_correct",
                "our_method": OUR_METHOD,
                "other_method": OTHER_METHOD,
                "source": "outputs/full_comparative_mistake_audit_vs_best_method_20260418/all_mistake_records.jsonl",
                "provenance": "exact-directly-recorded",
            }
        )
        case_payloads.append(case_payload)

    manifest = {
        "artifact_family": "twenty_exact_ours_vs_self_consistency_tree_comparison",
        "artifact_date": "2026-04-20",
        "our_method": OUR_METHOD,
        "other_method": OTHER_METHOD,
        "selection_policy": "deterministic_ranked_failure_selection",
        "selected_case_count": 20,
        "cases": manifest_cases,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    our_absent = sum(1 for c in case_payloads if not c["comparison"]["our_contains_correct_answer"])
    our_present_lost = sum(
        1
        for c in case_payloads
        if c["comparison"]["our_contains_correct_answer"] and (not c["rerun_observability"]["our"]["is_correct"])
    )
    sc_present = sum(1 for c in case_payloads if c["comparison"]["self_consistency_contains_correct_answer"])
    both_contain_choose_diff = sum(
        1
        for c in case_payloads
        if c["comparison"]["our_contains_correct_answer"]
        and c["comparison"]["self_consistency_contains_correct_answer"]
        and (c["rerun_observability"]["our"]["prediction_normalized"] != c["rerun_observability"]["self_consistency"]["prediction_normalized"])
    )
    exact_our = sum(1 for c in case_payloads if c["provenance_labels"]["our_structure"] == "exact-from-rerun-observability")
    exact_sc = sum(1 for c in case_payloads if c["provenance_labels"]["self_consistency_structure"] == "structurally faithful but non-tree")
    exact_correct_nodes = sum(
        1
        for c in case_payloads
        if c["provenance_labels"]["correct_node_identity_our"].startswith("exact")
        and c["provenance_labels"]["correct_node_identity_self_consistency"].startswith("exact")
    )

    divergence_hist: dict[str, int] = {}
    for c in case_payloads:
        k = str(c["comparison"]["divergence_category"])
        divergence_hist[k] = divergence_hist.get(k, 0) + 1

    summary = {
        "our_method": OUR_METHOD,
        "other_method": OTHER_METHOD,
        "selected_cases": 20,
        "exactness": {
            "our_exact_structure_recovery_cases": exact_our,
            "self_consistency_exact_structure_recovery_cases": exact_sc,
            "cases_with_exact_correct_node_or_sample_identified_for_both": exact_correct_nodes,
        },
        "counts": {
            "correct_answer_absent_in_our_tree": our_absent,
            "correct_answer_present_in_our_tree_but_lost": our_present_lost,
            "correct_answer_present_in_self_consistency_samples": sc_present,
            "both_methods_contain_correct_answer_but_choose_differently": both_contain_choose_diff,
        },
        "divergence_category_histogram": divergence_hist,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Twenty exact ours vs self_consistency_3 tree/sample comparison (2026-04-20)")
    lines.append("")
    lines.append("## Canonical method definitions")
    lines.append(f"- Our method: `{OUR_METHOD}`")
    lines.append(f"- Comparison target: `{OTHER_METHOD}`")
    lines.append("- Selection rule: exact direct records where our method is wrong and self_consistency_3 is correct.")
    lines.append("")
    lines.append("## Cross-case summary")
    lines.append(f"- Cases: {len(case_payloads)}")
    lines.append(f"- Our exact-from-rerun structure recovery: {exact_our}/20")
    lines.append(f"- self_consistency structurally faithful sample-forest recovery: {exact_sc}/20")
    lines.append(f"- Correct node/sample identified for both methods: {exact_correct_nodes}/20")
    lines.append(f"- Dominant divergence category: {max(divergence_hist.items(), key=lambda kv: kv[1])[0] if divergence_hist else 'n/a'}")
    lines.append("")

    for c in case_payloads:
        cmp = c["comparison"]
        lines.append(f"## Case {c['case_index']}: `{c['dataset']} / {c['example_id']}`")
        lines.append("")
        lines.append("### Header")
        lines.append(f"- case_id: `{c['case_id']}`")
        lines.append(f"- ground_truth: `{c['ground_truth_answer']}` (normalized `{c['ground_truth_normalized']}`)")
        lines.append(f"- recorded original answers: ours=`{c['recorded_original_outcome']['our_answer']}`, self_consistency_3=`{c['recorded_original_outcome']['self_consistency_answer']}`")
        lines.append(f"- rerun answers: ours=`{cmp['our_final_answer_rerun']}`, self_consistency_3=`{cmp['self_consistency_final_answer_rerun']}`")
        lines.append(f"- provenance labels: ours_structure=`{c['provenance_labels']['our_structure']}`, self_consistency_structure=`{c['provenance_labels']['self_consistency_structure']}`")
        lines.append("")
        lines.append("### Problem statement")
        lines.append(c["problem_statement"])
        lines.append("")
        lines.append("### Our method structure")
        lines.append("```text")
        lines.append((TEXT_DIR / f"{c['case_id']}_our_tree.txt").read_text(encoding="utf-8").rstrip())
        lines.append("```")
        lines.append("")
        lines.append("### self_consistency structure (sample forest)")
        lines.append("```text")
        lines.append((TEXT_DIR / f"{c['case_id']}_self_consistency_forest.txt").read_text(encoding="utf-8").rstrip())
        lines.append("```")
        lines.append("")
        lines.append("### Correct vs chosen nodes")
        lines.append(f"- our final node: `{cmp['our_final_answer_node_id']}`")
        lines.append(f"- self_consistency final-answer-supporting nodes: `{cmp['self_consistency_final_answer_supporting_node_ids']}`")
        lines.append(f"- our correct-answer nodes: `{cmp['our_correct_answer_node_ids']}`")
        lines.append(f"- self_consistency correct-answer nodes: `{cmp['self_consistency_correct_answer_node_ids']}`")
        lines.append("")
        lines.append("### What exactly went wrong")
        lines.append(f"- divergence category: `{cmp['divergence_category']}`")
        lines.append(f"- our contains correct answer in discovered structure: `{cmp['our_contains_correct_answer']}`")
        lines.append(f"- self_consistency contains correct answer in samples: `{cmp['self_consistency_contains_correct_answer']}`")
        lines.append(f"- budget usage: ours actions={cmp['budget_usage']['our_actions_used']}, sc actions={cmp['budget_usage']['self_consistency_actions_used']}, budget={cmp['budget_usage']['budget']}")
        lines.append("")

    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
