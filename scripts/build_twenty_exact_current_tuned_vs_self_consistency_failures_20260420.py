#!/usr/bin/env python3
"""Build fresh canonical 20-case failures: current promoted tuned vs self_consistency_3."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchActionResult, BranchState, SimulatedBranchGenerator
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples

OUT_ROOT = REPO_ROOT / "outputs/twenty_exact_current_tuned_vs_self_consistency_failures_20260420"
CASE_DIR = OUT_ROOT / "cases"
TEXT_DIR = OUT_ROOT / "case_text_structures"
MANIFEST_PATH = OUT_ROOT / "selected_case_manifest.json"
SUMMARY_PATH = OUT_ROOT / "summary.json"
DOC_PATH = REPO_ROOT / "docs/TWENTY_EXACT_CURRENT_TUNED_VS_SELF_CONSISTENCY_FAILURES_2026_04_20.md"

OLD_MANIFEST = REPO_ROOT / "outputs/twenty_defeat_case_trees_20260419/manifest.json"

CURRENT_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
OTHER_METHOD = "self_consistency_3"
DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024", "olympiadbench"]
SEEDS = [11, 23]
BUDGETS = [6, 8]
SUBSET_SIZE = 20
ADAPTIVE_GRID = [1]


@dataclass
class DecisionEvent:
    step: int
    action: str
    branch_id: str
    remaining_budget_before: int


class ObservedGenerator:
    """Capture branch-level observability during controller execution."""

    def __init__(self, base: SimulatedBranchGenerator) -> None:
        self.base = base
        self.events: list[dict[str, Any]] = []
        self.registry: dict[str, BranchState] = {}
        self.decision_events: list[DecisionEvent] = []
        self._step = 0

    def _snapshot(self, b: BranchState) -> dict[str, Any]:
        reasoning = "\n".join(str(x) for x in b.steps).strip() if b.steps else ""
        pred_norm = normalize_answer_text(str(b.predicted_answer) if b.predicted_answer is not None else None).get("normalized_answer")
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
            "predicted_answer_normalized": pred_norm,
            "answer_group_assignment": pred_norm,
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


def _stable_seed(*parts: Any) -> int:
    s = "||".join(str(p) for p in parts)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_id(dataset: str, example_id: str) -> str:
    return f"{dataset.replace('/', '__')}__{example_id}"


def _rank_key(rec: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(rec["loss_support_count"]),
        -int(rec["max_budget_with_loss"]),
        -int(rec["observability_priority"]),
        str(rec["dataset"]),
        str(rec["example_id"]),
    )


def _build_eval_surface() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in SEEDS:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
                run_seed = _stable_seed("eval_surface", dataset, seed, budget)
                rng = random.Random(run_seed)
                factory = lambda: SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
                specs = build_frontier_strategies(
                    factory,
                    budget,
                    ADAPTIVE_GRID,
                    rng,
                    use_openai_api=False,
                    include_broad_diversity_aggregation_methods=True,
                )
                our_ctrl = specs[CURRENT_METHOD]
                sc_ctrl = specs[OTHER_METHOD]
                for ex in examples:
                    our_res = our_ctrl.run(ex.question, ex.answer)
                    sc_res = sc_ctrl.run(ex.question, ex.answer)
                    rows.append(
                        {
                            "dataset": dataset,
                            "example_id": ex.example_id,
                            "problem_text": ex.question,
                            "ground_truth": ex.answer,
                            "seed": seed,
                            "budget": budget,
                            "our_prediction": our_res.prediction,
                            "our_prediction_normalized": normalize_answer_text(str(our_res.prediction) if our_res.prediction is not None else None).get("normalized_answer"),
                            "our_correct": bool(our_res.is_correct),
                            "our_actions_used": int(our_res.actions_used),
                            "our_metadata": our_res.metadata,
                            "sc_prediction": sc_res.prediction,
                            "sc_prediction_normalized": normalize_answer_text(str(sc_res.prediction) if sc_res.prediction is not None else None).get("normalized_answer"),
                            "sc_correct": bool(sc_res.is_correct),
                            "sc_actions_used": int(sc_res.actions_used),
                            "sc_metadata": sc_res.metadata,
                        }
                    )
    return rows


def _select_cases(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    old_ids = set()
    if OLD_MANIFEST.exists():
        old = _read_json(OLD_MANIFEST)
        for c in old.get("cases", []):
            old_ids.add(_case_id(str(c["dataset"]), str(c["example_id"])))

    eligible = [r for r in rows if (not r["our_correct"]) and r["sc_correct"]]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in eligible:
        grouped[(str(r["dataset"]), str(r["example_id"]))].append(r)

    ranked_records: list[dict[str, Any]] = []
    for (dataset, example_id), grows in grouped.items():
        cid = _case_id(dataset, example_id)
        if cid in old_ids:
            continue
        obs_score = 0
        for g in grows:
            md = g.get("our_metadata") or {}
            if str(md.get("early_divergence_failure_category", "")):
                obs_score += 1
            if str(md.get("regime_failure_category", "")):
                obs_score += 1
            if int(md.get("repeated_same_family_expansion_count", 0)) > 0:
                obs_score += 1
            if bool(md.get("gold_group_ever_present", False)):
                obs_score += 1
        rep = sorted(grows, key=lambda r: (int(r["budget"]), int(r["seed"])), reverse=True)[0]
        ranked_records.append(
            {
                "dataset": dataset,
                "example_id": example_id,
                "case_id": cid,
                "loss_support_count": len(grows),
                "max_budget_with_loss": max(int(x["budget"]) for x in grows),
                "observability_priority": obs_score,
                "representative": rep,
                "all_support_rows": [
                    {"seed": int(x["seed"]), "budget": int(x["budget"]), "our_prediction": x["our_prediction"], "sc_prediction": x["sc_prediction"]}
                    for x in sorted(grows, key=lambda z: (int(z["budget"]), int(z["seed"])), reverse=True)
                ],
            }
        )

    ranked_records.sort(key=_rank_key)
    if len(ranked_records) < 20:
        raise RuntimeError(f"Need at least 20 fresh cases excluding old manifest; found {len(ranked_records)}")

    selected = ranked_records[:20]
    policy = {
        "eligibility": "current_tuned_wrong_and_self_consistency_3_correct",
        "exclusion": "exclude_case_ids_from_outputs/twenty_defeat_case_trees_20260419/manifest.json",
        "ranking": [
            "higher loss_support_count first",
            "higher max_budget_with_loss first",
            "higher observability_priority first",
            "dataset/example_id lexical tie-break",
        ],
    }
    return selected, policy


def _run_with_observability(method_name: str, row: dict[str, Any], stream_tag: str) -> dict[str, Any]:
    budget = int(row["budget"])
    seed = int(row["seed"])
    dataset = str(row["dataset"])
    example_id = str(row["example_id"])
    question = str(row["problem_text"])
    gold = str(row["ground_truth"])

    run_seed = _stable_seed(stream_tag, method_name, dataset, example_id, seed, budget)
    rng = random.Random(run_seed)
    observed = ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))

    def factory() -> ObservedGenerator:
        return observed

    strategies = build_frontier_strategies(factory, budget, ADAPTIVE_GRID, rng, use_openai_api=False, include_broad_diversity_aggregation_methods=True)
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
        snap["branch_creation_step"] = next((int(ev["step"]) for ev in observed.events if ev["event"] == "init_branch" and ev["branch_id"] == bid), None)
        final_nodes.append(snap)

    action_history = [
        {
            "step": int(d.step),
            "action": d.action,
            "branch_id": d.branch_id,
            "branch_family_id": next((x.get("branch_family_id") for x in final_nodes if x.get("branch_id") == d.branch_id), d.branch_id),
            "remaining_budget_before": int(d.remaining_budget_before),
            "remaining_budget_after": max(0, int(d.remaining_budget_before) - 1),
        }
        for d in observed.decision_events
    ]

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
        "action_history": action_history,
        "decision_timeline": [ev.__dict__ for ev in observed.decision_events],
        "final_nodes": final_nodes,
    }


def _node_ids_with_answer(nodes: list[dict[str, Any]], normalized_answer: str | None) -> list[str]:
    if normalized_answer is None:
        return []
    return [str(n.get("branch_id")) for n in nodes if n.get("predicted_answer_normalized") == normalized_answer]


def _classify_failure_type(our_contains: bool, our_final_correct: bool, our_correct_nodes: list[str], our_nodes: list[dict[str, Any]]) -> str:
    if not our_contains:
        return "correct answer absent from our tree"
    if our_final_correct:
        return "other"
    node_by_id = {str(n.get("branch_id")): n for n in our_nodes}
    done = any(bool(node_by_id.get(i, {}).get("is_done", False)) for i in our_correct_nodes)
    if not done:
        return "present but not matured"
    all_scores = [float(n.get("score", 0.0)) for n in our_nodes]
    corr_scores = [float(node_by_id.get(i, {}).get("score", 0.0)) for i in our_correct_nodes]
    if corr_scores and all_scores and max(corr_scores) < max(all_scores):
        return "present but underweighted"
    return "present but not selected"


def _to_text_tree(nodes: list[dict[str, Any]], root_label: str) -> str:
    children: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        children[n.get("parent_branch_id")].append(n)
    for vals in children.values():
        vals.sort(key=lambda x: str(x.get("branch_id")))
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

    rows = _build_eval_surface()
    selected, selection_policy = _select_cases(rows)

    manifest_cases: list[dict[str, Any]] = []
    case_payloads: list[dict[str, Any]] = []

    for idx, pick in enumerate(selected, start=1):
        row = pick["representative"]
        dataset = str(row["dataset"])
        example_id = str(row["example_id"])
        case_id = _case_id(dataset, example_id)

        our_run = _run_with_observability(CURRENT_METHOD, row, "obs_current_tuned")
        sc_run = _run_with_observability(OTHER_METHOD, row, "obs_self_consistency")

        gold_norm = normalize_answer_text(str(row["ground_truth"]))["normalized_answer"]
        our_final_node = None
        if our_run["final_nodes"]:
            pred = our_run["prediction_normalized"]
            m = [n for n in our_run["final_nodes"] if n.get("predicted_answer_normalized") == pred]
            if m:
                our_final_node = sorted(m, key=lambda n: float(n.get("score", 0.0)), reverse=True)[0]["branch_id"]

        sc_support_nodes = [str(n["branch_id"]) for n in sc_run["final_nodes"] if n.get("predicted_answer_normalized") == sc_run["prediction_normalized"]]
        sc_vote_counts = Counter(str(n.get("predicted_answer_normalized")) for n in sc_run["final_nodes"])  # sample forest votes

        our_correct_nodes = _node_ids_with_answer(our_run["final_nodes"], gold_norm)
        sc_correct_nodes = _node_ids_with_answer(sc_run["final_nodes"], gold_norm)
        our_contains = bool(our_correct_nodes)
        sc_contains = bool(sc_correct_nodes)

        failure_type = _classify_failure_type(our_contains, bool(our_run["is_correct"]), our_correct_nodes, our_run["final_nodes"])

        c = {
            "case_id": case_id,
            "case_index": idx,
            "dataset": dataset,
            "example_id": example_id,
            "problem_statement": row["problem_text"],
            "ground_truth_answer": row["ground_truth"],
            "ground_truth_normalized": gold_norm,
            "our_method_name": CURRENT_METHOD,
            "self_consistency_method_name": OTHER_METHOD,
            "selection_evidence": {
                "support_count": int(pick["loss_support_count"]),
                "max_budget_with_loss": int(pick["max_budget_with_loss"]),
                "observability_priority": int(pick["observability_priority"]),
                "support_rows": pick["all_support_rows"],
            },
            "recorded_surface_outcome": {
                "seed": int(row["seed"]),
                "budget": int(row["budget"]),
                "our_answer": row["our_prediction"],
                "self_consistency_answer": row["sc_prediction"],
                "our_correct": bool(row["our_correct"]),
                "self_consistency_correct": bool(row["sc_correct"]),
                "source": "fresh_eval_surface_20260420",
            },
            "rerun_observability": {
                "our": our_run,
                "self_consistency": {
                    **sc_run,
                    "structure_type": "sample_forest",
                    "vote_counts": dict(sc_vote_counts),
                    "final_answer_supporting_sample_nodes": sc_support_nodes,
                    "provenance": "faithful_sample_forest_not_tree",
                },
            },
            "comparison": {
                "our_final_answer_rerun": our_run["prediction_text"],
                "self_consistency_final_answer_rerun": sc_run["prediction_text"],
                "our_contains_correct_answer": our_contains,
                "self_consistency_contains_correct_answer": sc_contains,
                "our_final_answer_node_id": our_final_node,
                "self_consistency_final_answer_supporting_node_ids": sc_support_nodes,
                "our_correct_answer_node_ids": our_correct_nodes,
                "self_consistency_correct_answer_node_ids": sc_correct_nodes,
                "failure_type": failure_type,
                "reasoning_style_labels": {
                    "our_major_families": sorted({str(n.get("branch_family_id")) for n in our_run["final_nodes"]})[:12],
                    "self_consistency_sample_ids": sorted([str(n.get("branch_id")) for n in sc_run["final_nodes"]])[:12],
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
                "our_structure": "exact_from_rerun_observability",
                "self_consistency_structure": "faithful_sample_forest",
                "correct_node_identity_our": "exact" if our_contains else "absent",
                "correct_node_identity_self_consistency": "exact" if sc_contains else "absent",
            },
        }

        (CASE_DIR / f"{case_id}.json").write_text(json.dumps(c, indent=2) + "\n", encoding="utf-8")
        (TEXT_DIR / f"{case_id}_our_tree.txt").write_text(_to_text_tree(our_run["final_nodes"], "root") + "\n", encoding="utf-8")
        (TEXT_DIR / f"{case_id}_self_consistency_forest.txt").write_text(
            _to_text_tree(sc_run["final_nodes"], "root(sample_forest)") + "\n", encoding="utf-8"
        )

        manifest_cases.append(
            {
                "case_id": case_id,
                "dataset": dataset,
                "example_id": example_id,
                "seed": int(row["seed"]),
                "budget": int(row["budget"]),
                "selection_criterion": "current_tuned_wrong_and_self_consistency_3_correct",
                "our_method": CURRENT_METHOD,
                "other_method": OTHER_METHOD,
                "support_count": int(pick["loss_support_count"]),
                "selection_source": "fresh_eval_surface_20260420",
            }
        )
        case_payloads.append(c)

    manifest = {
        "artifact_family": "twenty_exact_current_tuned_vs_self_consistency_failures",
        "artifact_date": "2026-04-20",
        "our_method": CURRENT_METHOD,
        "other_method": OTHER_METHOD,
        "selection_policy": selection_policy,
        "selected_case_count": 20,
        "cases": manifest_cases,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    absent = sum(1 for c in case_payloads if not c["comparison"]["our_contains_correct_answer"])
    present_not_selected = sum(
        1
        for c in case_payloads
        if c["comparison"]["our_contains_correct_answer"] and not c["rerun_observability"]["our"]["is_correct"]
    )
    sc_present = sum(1 for c in case_payloads if c["comparison"]["self_consistency_contains_correct_answer"])
    both_contain_choose_diff = sum(
        1
        for c in case_payloads
        if c["comparison"]["our_contains_correct_answer"]
        and c["comparison"]["self_consistency_contains_correct_answer"]
        and (c["rerun_observability"]["our"]["prediction_normalized"] != c["rerun_observability"]["self_consistency"]["prediction_normalized"])
    )
    repeat_same_family = sum(
        1
        for c in case_payloads
        if int((c["rerun_observability"]["our"]["metadata"] or {}).get("repeated_same_family_expansion_count", 0)) > 0
    )
    alt_maturation_insufficient = sum(
        1
        for c in case_payloads
        if str(c["comparison"]["failure_type"]) in {"present but not matured", "present but underweighted"}
    )
    final_selection_failure = sum(1 for c in case_payloads if str(c["comparison"]["failure_type"]) == "present but not selected")
    exact_our = sum(1 for c in case_payloads if c["provenance_labels"]["our_structure"] == "exact_from_rerun_observability")
    exact_sc = sum(1 for c in case_payloads if c["provenance_labels"]["self_consistency_structure"] == "faithful_sample_forest")
    exact_correct_any = sum(
        1
        for c in case_payloads
        if c["comparison"]["our_correct_answer_node_ids"] or c["comparison"]["self_consistency_correct_answer_node_ids"]
    )

    failure_hist = Counter(str(c["comparison"]["failure_type"]) for c in case_payloads)

    summary = {
        "our_method": CURRENT_METHOD,
        "other_method": OTHER_METHOD,
        "selected_cases": 20,
        "exactness": {
            "our_exact_structure_recovery_cases": exact_our,
            "self_consistency_faithful_sample_forest_recovery_cases": exact_sc,
            "cases_identifying_exact_correct_node_or_sample": exact_correct_any,
        },
        "counts": {
            "correct_answer_absent_from_our_tree": absent,
            "correct_answer_present_in_our_tree_but_not_selected": present_not_selected,
            "correct_answer_present_in_self_consistency_samples": sc_present,
            "both_methods_contain_correct_answer_but_choose_differently": both_contain_choose_diff,
            "repeated_same_family_expansion_still_present": repeat_same_family,
            "alternative_maturation_still_insufficient": alt_maturation_insufficient,
            "final_selection_failure_after_correct_answer_present": final_selection_failure,
        },
        "dominant_failure_pattern": max(failure_hist.items(), key=lambda kv: kv[1])[0] if failure_hist else "n/a",
        "failure_type_histogram": dict(failure_hist),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Twenty exact current tuned vs self_consistency_3 failures (2026-04-20)")
    lines.append("")
    lines.append("## Canonical method definitions")
    lines.append(f"- Current promoted tuned method: `{CURRENT_METHOD}`")
    lines.append(f"- Comparison target: `{OTHER_METHOD}`")
    lines.append("- Fresh-case constraint: exclude old canonical 20-case set from `outputs/twenty_defeat_case_trees_20260419/manifest.json`.")
    lines.append("- Selection rule: current tuned wrong and self_consistency_3 correct on a fresh bounded evaluation surface.")
    lines.append("")
    lines.append("## Deterministic ranking policy")
    lines.append("1. Higher support-count across seed/budget losses first.")
    lines.append("2. Higher max-budget loss support first.")
    lines.append("3. Higher observability-priority score first.")
    lines.append("4. Lexical dataset/example tie-break.")
    lines.append("")
    lines.append("## Aggregate summary")
    lines.append(f"- Cases: {len(case_payloads)}")
    lines.append(f"- Correct answer absent from our tree: {absent}")
    lines.append(f"- Correct answer present in our tree but not selected: {present_not_selected}")
    lines.append(f"- Correct answer present in self-consistency samples: {sc_present}")
    lines.append(f"- Both methods contain correct answer but choose differently: {both_contain_choose_diff}")
    lines.append(f"- Repeated same-family expansion still present: {repeat_same_family}")
    lines.append(f"- Alternative maturation still insufficient: {alt_maturation_insufficient}")
    lines.append(f"- Final-selection failure after correct answer already in tree: {final_selection_failure}")
    lines.append(f"- Dominant remaining failure type: `{summary['dominant_failure_pattern']}`")
    lines.append("")

    for c in case_payloads:
        cmp = c["comparison"]
        lines.append(f"## Case {c['case_index']}: `{c['dataset']} / {c['example_id']}`")
        lines.append("")
        lines.append("### Header")
        lines.append(f"- case_id: `{c['case_id']}`")
        lines.append(f"- dataset/example: `{c['dataset']} / {c['example_id']}`")
        lines.append(f"- ground_truth: `{c['ground_truth_answer']}` (normalized `{c['ground_truth_normalized']}`)")
        lines.append(f"- current tuned answer (surface): `{c['recorded_surface_outcome']['our_answer']}`")
        lines.append(f"- self_consistency_3 answer (surface): `{c['recorded_surface_outcome']['self_consistency_answer']}`")
        lines.append(f"- surface correctness gate: tuned_wrong=`{not c['recorded_surface_outcome']['our_correct']}`, sc_correct=`{c['recorded_surface_outcome']['self_consistency_correct']}`")
        lines.append(f"- support_count across seed/budget rows: `{c['selection_evidence']['support_count']}`")
        lines.append("")
        lines.append("### Problem statement")
        lines.append(c["problem_statement"])
        lines.append("")
        lines.append("### Our full discovered structure")
        lines.append("```text")
        lines.append((TEXT_DIR / f"{c['case_id']}_our_tree.txt").read_text(encoding="utf-8").rstrip())
        lines.append("```")
        lines.append("")
        lines.append("### self_consistency sample structure (faithful sample forest)")
        lines.append("```text")
        lines.append((TEXT_DIR / f"{c['case_id']}_self_consistency_forest.txt").read_text(encoding="utf-8").rstrip())
        lines.append("```")
        lines.append("")
        lines.append("### Exact nodes/samples")
        lines.append(f"- our chosen final-answer node: `{cmp['our_final_answer_node_id']}`")
        lines.append(f"- self-consistency final-answer-supporting sample nodes: `{cmp['self_consistency_final_answer_supporting_node_ids']}`")
        lines.append(f"- our correct-answer node(s): `{cmp['our_correct_answer_node_ids']}`")
        lines.append(f"- self-consistency correct-answer sample node(s): `{cmp['self_consistency_correct_answer_node_ids']}`")
        lines.append("")
        lines.append("### Failure explanation")
        lines.append(f"- failure type: `{cmp['failure_type']}`")
        lines.append(f"- our contains correct answer: `{cmp['our_contains_correct_answer']}`")
        lines.append(f"- self-consistency contains correct answer: `{cmp['self_consistency_contains_correct_answer']}`")
        lines.append(f"- reasoning-style labels (our families): `{cmp['reasoning_style_labels']['our_major_families']}`")
        lines.append(f"- reasoning-style labels (self-consistency samples): `{cmp['reasoning_style_labels']['self_consistency_sample_ids']}`")
        bu = cmp["budget_usage"]
        lines.append(
            f"- budget usage summary: budget={bu['budget']}, our(actions={bu['our_actions_used']}, expand={bu['our_expansions']}, verify={bu['our_verifications']}), self_consistency(actions={bu['self_consistency_actions_used']}, expand={bu['self_consistency_expansions']}, verify={bu['self_consistency_verifications']})"
        )
        lines.append("")

    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
