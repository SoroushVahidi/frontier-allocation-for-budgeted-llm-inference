#!/usr/bin/env python3
"""Build fresh canonical 20-case current full-method failures vs current best comparison method."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchActionResult, BranchState, SimulatedBranchGenerator
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer

OUT_ROOT = REPO_ROOT / "outputs/twenty_exact_current_full_method_failures_vs_best_20260420"
CASE_DIR = OUT_ROOT / "cases"
TEXT_DIR = OUT_ROOT / "case_text_structures"
MANIFEST_PATH = OUT_ROOT / "selected_case_manifest.json"
SUMMARY_PATH = OUT_ROOT / "summary.json"
DOC_PATH = REPO_ROOT / "docs/TWENTY_EXACT_CURRENT_FULL_METHOD_FAILURES_VS_BEST_2026_04_20.md"

CURRENT_FULL_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024", "olympiadbench"]
SEEDS = [11, 23, 37, 59, 71, 83, 97, 109]
BUDGETS = [3, 4, 5, 6, 7, 8, 10, 12]
SUBSET_SIZE = 40
ADAPTIVE_GRID = [1]

EXCLUSION_MANIFESTS = [
    REPO_ROOT / "outputs/twenty_defeat_case_trees_20260419/manifest.json",
    REPO_ROOT / "outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/selected_case_manifest.json",
    REPO_ROOT / "outputs/current_failure_output_layer_repair_20260420/per_case_results.jsonl",
]


@dataclass
class DecisionEvent:
    step: int
    action: str
    branch_id: str
    remaining_budget_before: int


class ObservedGenerator:
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
        self.events.append({"event": "expand", "step": self._step, "branch_id": branch.branch_id, "before": before, "after": after, "score_after": float(out.score_after), "became_done": bool(out.became_done)})
        self._step += 1
        return out

    def verify(self, branch: BranchState, question: str) -> BranchActionResult:
        before = self._snapshot(branch)
        self.decision_events.append(DecisionEvent(self._step, "verify", branch.branch_id, -1))
        out = self.base.verify(branch, question)
        after = self._snapshot(branch)
        self.events.append({"event": "verify", "step": self._step, "branch_id": branch.branch_id, "before": before, "after": after, "score_after": float(out.score_after)})
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


def _resolve_best_method() -> tuple[str, dict[str, Any]]:
    # Determine best direct in-surface comparator among currently registered direct methods.
    method = "self_consistency_3"
    candidate_methods = ["self_consistency_3", "reasoning_beam2", "reasoning_greedy"]
    eval_rows = _build_eval_surface(CURRENT_FULL_METHOD, "self_consistency_3")
    method_correct: dict[str, list[int]] = {m: [] for m in candidate_methods}
    for r in eval_rows:
        dataset = str(r["dataset"])
        seed = int(r["seed"])
        budget = int(r["budget"])
        run_seed = _stable_seed("best_method_resolution", dataset, seed, budget)
        rng = random.Random(run_seed)
        factory = lambda: SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
        specs = build_frontier_strategies(factory, budget, ADAPTIVE_GRID, rng, use_openai_api=False, include_broad_diversity_aggregation_methods=True)
        for m in candidate_methods:
            res = specs[m].run(str(r["problem_text"]), str(r["ground_truth"]))
            method_correct[m].append(int(bool(res.is_correct)))
    ranked = sorted(candidate_methods, key=lambda m: (sum(method_correct[m]) / max(1, len(method_correct[m])), m), reverse=True)
    method = ranked[0]
    evidence = {
        "best_method": method,
        "resolution_rule": "best_direct_registered_method_on_current_eval_surface",
        "evidence_files": [
            "README.md",
            "docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md",
            "docs/FULL_METHOD_COMPARISON_STATUS_2026_04_18.md",
        ],
        "surface_means": {m: (sum(method_correct[m]) / max(1, len(method_correct[m]))) for m in candidate_methods},
        "candidate_methods": candidate_methods,
        "note": "Best comparator resolved from currently registered direct methods on the same evaluation surface.",
    }
    return method, evidence


def _collect_excluded_case_ids() -> set[str]:
    excluded: set[str] = set()
    for p in EXCLUSION_MANIFESTS:
        if not p.exists():
            continue
        if p.suffix == ".json":
            data = _read_json(p)
            for c in data.get("cases", []):
                if "case_id" in c:
                    excluded.add(str(c["case_id"]))
                elif "dataset" in c and "example_id" in c:
                    excluded.add(_case_id(str(c["dataset"]), str(c["example_id"])))
        elif p.suffix == ".jsonl":
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if "case_id" in row:
                    excluded.add(str(row["case_id"]))
    return excluded


def _rank_key(rec: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(rec["loss_support_count"]),
        -int(rec["max_budget_with_loss"]),
        -int(rec["observability_priority"]),
        str(rec["dataset"]),
        str(rec["example_id"]),
    )


def _build_eval_surface(current_method: str, best_method: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for seed in SEEDS:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
                run_seed = _stable_seed("eval_surface", dataset, seed, budget)
                rng = random.Random(run_seed)
                factory = lambda: SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
                specs = build_frontier_strategies(factory, budget, ADAPTIVE_GRID, rng, use_openai_api=False, include_broad_diversity_aggregation_methods=True)
                our_ctrl = specs[current_method]
                best_ctrl = specs[best_method]
                for ex in examples:
                    our_res = our_ctrl.run(ex.question, ex.answer)
                    best_res = best_ctrl.run(ex.question, ex.answer)
                    rows.append(
                        {
                            "dataset": dataset,
                            "example_id": ex.example_id,
                            "problem_text": ex.question,
                            "ground_truth": ex.answer,
                            "seed": seed,
                            "budget": budget,
                            "our_prediction": our_res.prediction,
                            "our_correct": bool(our_res.is_correct),
                            "our_metadata": our_res.metadata,
                            "best_prediction": best_res.prediction,
                            "best_correct": bool(best_res.is_correct),
                            "best_metadata": best_res.metadata,
                        }
                    )
    return rows


def _select_candidates(rows: list[dict[str, Any]], excluded_ids: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = [r for r in rows if (not r["our_correct"]) and r["best_correct"]]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in eligible:
        grouped[(str(r["dataset"]), str(r["example_id"]))].append(r)

    ranked_records: list[dict[str, Any]] = []
    for (dataset, example_id), grows in grouped.items():
        cid = _case_id(dataset, example_id)
        if cid in excluded_ids:
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
                    {"seed": int(x["seed"]), "budget": int(x["budget"]), "our_prediction": x["our_prediction"], "best_prediction": x["best_prediction"]}
                    for x in sorted(grows, key=lambda z: (int(z["budget"]), int(z["seed"])), reverse=True)
                ],
            }
        )

    ranked_records.sort(key=_rank_key)
    policy = {
        "eligibility": "our_current_full_method_wrong_and_best_method_correct",
        "exclusion_sources": [str(p.relative_to(REPO_ROOT)) for p in EXCLUSION_MANIFESTS if p.exists()],
        "ranking": [
            "higher loss_support_count first",
            "higher max_budget_with_loss first",
            "higher observability_priority first",
            "dataset/example_id lexical tie-break",
        ],
    }
    return ranked_records, policy


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

    return {
        "method": method_name,
        "run_seed": run_seed,
        "budget": budget,
        "prediction_text": result.prediction,
        "prediction_normalized": normalize_answer_text(str(result.prediction) if result.prediction is not None else None).get("normalized_answer"),
        "gold_normalized": normalize_answer_text(gold).get("normalized_answer"),
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


def _to_text_tree(nodes: list[dict[str, Any]], root_label: str) -> str:
    children: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        children[n.get("parent_branch_id")].append(n)
    for vals in children.values():
        vals.sort(key=lambda x: str(x.get("branch_id")))
    lines = [root_label]

    def rec(parent: str | None, indent: str) -> None:
        for n in children.get(parent, []):
            lines.append(f"{indent}- {n.get('branch_id')} [fam={n.get('branch_family_id')}, depth={n.get('depth')}, score={float(n.get('score',0.0)):.4f}, done={n.get('is_done')}, ans={n.get('predicted_answer_normalized')}]")
            rec(str(n.get("branch_id")), indent + "  ")

    rec(None, "")
    return "\n".join(lines)


def main() -> None:
    best_method, best_evidence = _resolve_best_method()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    for p in CASE_DIR.glob("*.json"):
        p.unlink()
    for p in TEXT_DIR.glob("*.txt"):
        p.unlink()

    excluded_ids = _collect_excluded_case_ids()
    rows = _build_eval_surface(CURRENT_FULL_METHOD, best_method)
    ranked, selection_policy = _select_candidates(rows, excluded_ids)

    selected_payloads: list[dict[str, Any]] = []
    manifest_cases: list[dict[str, Any]] = []

    for pick in ranked:
        row = pick["representative"]
        dataset = str(row["dataset"])
        case_id = str(pick["case_id"])
        gold_raw = str(row["ground_truth"])
        gold_can = canonicalize_answer(gold_raw, dataset=dataset)

        our_run = _run_with_observability(CURRENT_FULL_METHOD, row, "obs_full_method")
        best_run = _run_with_observability(best_method, row, "obs_best_method")

        our_repair = choose_repair_answer(
            final_nodes=list(our_run.get("final_nodes", [])),
            selected_group_hint=(our_run.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        best_repair = choose_repair_answer(
            final_nodes=list(best_run.get("final_nodes", [])),
            selected_group_hint=(best_run.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )

        our_surface_can = canonicalize_answer(our_repair.get("surfaced_final_answer_raw"), dataset=dataset)
        best_surface_can = canonicalize_answer(best_repair.get("surfaced_final_answer_raw"), dataset=dataset)

        our_wrong = (our_surface_can != gold_can)
        best_correct = (best_surface_can == gold_can)
        if not (our_wrong and best_correct):
            continue

        our_correct_nodes = _node_ids_with_answer(our_run["final_nodes"], gold_can)
        best_correct_nodes = _node_ids_with_answer(best_run["final_nodes"], gold_can)
        our_contains = bool(our_correct_nodes)
        best_contains = bool(best_correct_nodes)

        output_layer_mismatch = bool(
            our_contains and (our_repair.get("chosen_final_node_answer_canonical") == gold_can) and (our_surface_can != gold_can)
        )
        extraction_or_canon_mismatch = bool(
            (our_repair.get("chosen_final_node_answer_canonical") != our_repair.get("extracted_final_answer_canonical"))
            or (our_repair.get("extracted_final_answer_canonical") != our_repair.get("surfaced_final_answer_canonical"))
            or (our_repair.get("chosen_final_node_answer_raw") != our_repair.get("chosen_final_node_answer_canonical"))
        )

        if not our_contains:
            failure_type = "correct answer absent from our tree"
        elif output_layer_mismatch:
            failure_type = "correct answer present but mismatched at output layer"
        else:
            failure_type = "correct answer present in our tree but not selected"

        case_payload = {
            "case_id": case_id,
            "dataset": dataset,
            "example_id": str(row["example_id"]),
            "problem_statement": str(row["problem_text"]),
            "ground_truth_answer": gold_raw,
            "ground_truth_answer_canonical": gold_can,
            "current_full_method_name": CURRENT_FULL_METHOD,
            "best_comparison_method_name": best_method,
            "selection_rank_fields": {
                "loss_support_count": int(pick["loss_support_count"]),
                "max_budget_with_loss": int(pick["max_budget_with_loss"]),
                "observability_priority": int(pick["observability_priority"]),
                "support_rows": pick["all_support_rows"],
            },
            "recorded_surface_outcome": {
                "seed": int(row["seed"]),
                "budget": int(row["budget"]),
                "our_surface_prediction_raw": row["our_prediction"],
                "best_surface_prediction_raw": row["best_prediction"],
                "our_surface_correct_raw": bool(row["our_correct"]),
                "best_surface_correct_raw": bool(row["best_correct"]),
                "source": "fresh_eval_surface_20260420",
            },
            "rerun_observability": {
                "our": {**our_run, "deterministic_output_layer_repair": our_repair},
                "best": {
                    **best_run,
                    "deterministic_output_layer_repair": best_repair,
                    "structure_type": "sample_forest" if best_method == "self_consistency_3" else "tree_or_controller_native_structure",
                },
            },
            "comparison": {
                "our_full_method_answer": our_repair.get("surfaced_final_answer_raw"),
                "best_method_answer": best_repair.get("surfaced_final_answer_raw"),
                "our_contains_correct_answer": our_contains,
                "best_contains_correct_answer": best_contains,
                "our_chosen_node_id": our_repair.get("chosen_final_node_id"),
                "best_chosen_node_or_sample_id": best_repair.get("chosen_final_node_id"),
                "our_correct_answer_node_ids": our_correct_nodes,
                "best_correct_answer_node_or_sample_ids": best_correct_nodes,
                "failure_type": failure_type,
                "output_layer_mismatch": output_layer_mismatch,
                "answer_extraction_or_canonicalization_mismatch": extraction_or_canon_mismatch,
                "budget_action_summary": {
                    "budget": int(row["budget"]),
                    "our_actions": int(our_run["actions_used"]),
                    "best_actions": int(best_run["actions_used"]),
                    "our_expansions": int(our_run["expansions"]),
                    "best_expansions": int(best_run["expansions"]),
                    "our_verifications": int(our_run["verifications"]),
                    "best_verifications": int(best_run["verifications"]),
                },
            },
            "provenance_labels": {
                "our_structure_recovery": "exact_from_rerun_observability",
                "best_structure_recovery": "faithful_sample_forest" if best_method == "self_consistency_3" else "best_available_controller_structure",
                "our_correct_node_identity": "exact" if our_contains else "absent",
                "best_correct_node_identity": "exact" if best_contains else "absent",
            },
        }

        (CASE_DIR / f"{case_id}.json").write_text(json.dumps(case_payload, indent=2) + "\n", encoding="utf-8")
        (TEXT_DIR / f"{case_id}_our_structure.txt").write_text(_to_text_tree(our_run["final_nodes"], "root") + "\n", encoding="utf-8")
        (TEXT_DIR / f"{case_id}_best_structure.txt").write_text(_to_text_tree(best_run["final_nodes"], "root") + "\n", encoding="utf-8")

        selected_payloads.append(case_payload)
        manifest_cases.append(
            {
                "case_id": case_id,
                "dataset": dataset,
                "example_id": str(row["example_id"]),
                "seed": int(row["seed"]),
                "budget": int(row["budget"]),
                "selection_criterion": "current_full_method_wrong_and_best_method_correct_after_deterministic_output_layer_repair",
                "current_full_method": CURRENT_FULL_METHOD,
                "best_method": best_method,
            }
        )

        if len(selected_payloads) >= 20:
            break

    if len(selected_payloads) < 20:
        raise RuntimeError(f"Need 20 selected cases but found {len(selected_payloads)} after full rerun eligibility checks")

    absent = sum(1 for c in selected_payloads if not c["comparison"]["our_contains_correct_answer"])
    present_not_selected = sum(1 for c in selected_payloads if c["comparison"]["our_contains_correct_answer"] and not c["comparison"]["output_layer_mismatch"])
    output_layer_mismatch = sum(1 for c in selected_payloads if c["comparison"]["output_layer_mismatch"])
    best_contains = sum(1 for c in selected_payloads if c["comparison"]["best_contains_correct_answer"])
    repeat_same_family = sum(1 for c in selected_payloads if int((c["rerun_observability"]["our"].get("metadata") or {}).get("repeated_same_family_expansion_count", 0)) > 0)
    extraction_mismatch = sum(1 for c in selected_payloads if c["comparison"]["answer_extraction_or_canonicalization_mismatch"])
    failure_hist = Counter(str(c["comparison"]["failure_type"]) for c in selected_payloads)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_full_method": CURRENT_FULL_METHOD,
        "best_method": best_method,
        "best_method_resolution": best_evidence,
        "selected_case_count": len(selected_payloads),
        "counts": {
            "correct_answer_absent_from_our_tree": absent,
            "correct_answer_present_in_our_tree_but_not_selected": present_not_selected,
            "correct_answer_present_but_mismatched_at_output_layer": output_layer_mismatch,
            "correct_answer_present_in_best_method_structure": best_contains,
            "repeated_same_family_expansion_still_present": repeat_same_family,
            "answer_extraction_or_canonicalization_mismatch": extraction_mismatch,
        },
        "dominant_remaining_failure_type": max(failure_hist.items(), key=lambda kv: kv[1])[0] if failure_hist else "n/a",
        "failure_type_histogram": dict(failure_hist),
        "exact_structure_recovery": {
            "our_exact_structure_recovery_cases": sum(1 for c in selected_payloads if c["provenance_labels"]["our_structure_recovery"] == "exact_from_rerun_observability"),
            "best_faithful_structure_recovery_cases": sum(1 for c in selected_payloads if c["provenance_labels"]["best_structure_recovery"] in {"faithful_sample_forest", "best_available_controller_structure"}),
            "cases_with_exact_correct_node_or_sample_identified": sum(1 for c in selected_payloads if c["comparison"]["our_correct_answer_node_ids"] or c["comparison"]["best_correct_answer_node_or_sample_ids"]),
        },
    }

    manifest = {
        "artifact_family": "twenty_exact_current_full_method_failures_vs_best",
        "artifact_date": "2026-04-20",
        "current_full_method": CURRENT_FULL_METHOD,
        "best_method": best_method,
        "best_method_resolution": best_evidence,
        "selection_policy": selection_policy,
        "selected_case_count": len(selected_payloads),
        "cases": manifest_cases,
    }

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Twenty exact current full-method failures vs best method (2026-04-20)")
    lines.append("")
    lines.append("## Method identities")
    lines.append(f"- Current full method (registered): `{CURRENT_FULL_METHOD}`")
    lines.append(f"- Best comparison method (resolved): `{best_method}`")
    lines.append(f"- Best-method resolution note: {best_evidence['note']}")
    lines.append("")
    lines.append("## Deterministic selection policy")
    lines.append("- Eligibility: current full method wrong and best method correct after deterministic output-layer repair check.")
    lines.append("- Exclusions: prior canonical 20-case sets and targeted output-layer-repair subset case IDs.")
    lines.append("- Ranking rule (deterministic):")
    lines.append("  1. Higher loss support-count across seed/budget rows.")
    lines.append("  2. Higher max budget with loss support.")
    lines.append("  3. Higher observability priority score.")
    lines.append("  4. Dataset/example lexical tie-break.")
    lines.append("")
    lines.append("## Aggregate summary")
    lines.append(f"- Correct answer absent from our tree: {absent}")
    lines.append(f"- Correct answer present in our tree but not selected: {present_not_selected}")
    lines.append(f"- Correct answer present but mismatched at output layer: {output_layer_mismatch}")
    lines.append(f"- Correct answer present in best-method structure: {best_contains}")
    lines.append(f"- Repeated same-family expansion still present: {repeat_same_family}")
    lines.append(f"- Answer extraction/canonicalization mismatch: {extraction_mismatch}")
    lines.append(f"- Dominant remaining failure type: `{summary['dominant_remaining_failure_type']}`")
    lines.append("")

    for idx, c in enumerate(selected_payloads, start=1):
        cmp = c["comparison"]
        lines.append(f"## Case {idx}: `{c['dataset']} / {c['example_id']}`")
        lines.append("")
        lines.append(f"1. Dataset + example id: `{c['dataset']} / {c['example_id']}`")
        lines.append(f"2. Problem statement: {c['problem_statement']}")
        lines.append(f"3. Ground-truth answer: `{c['ground_truth_answer']}` (canonical `{c['ground_truth_answer_canonical']}`)")
        lines.append(f"4. Our current full-method answer: `{cmp['our_full_method_answer']}`")
        lines.append(f"5. Best-method answer: `{cmp['best_method_answer']}`")
        lines.append(f"6. Correct answer in our structure: `{cmp['our_contains_correct_answer']}`")
        lines.append(f"7. Correct answer in best-method structure: `{cmp['best_contains_correct_answer']}`")
        lines.append(f"8. Chosen node/sample IDs: our=`{cmp['our_chosen_node_id']}`, best=`{cmp['best_chosen_node_or_sample_id']}`")
        lines.append(f"9. Correct-answer node/sample IDs: our=`{cmp['our_correct_answer_node_ids']}`, best=`{cmp['best_correct_answer_node_or_sample_ids']}`")
        lines.append("10. Our discovered structure:")
        lines.append("```text")
        lines.append((TEXT_DIR / f"{c['case_id']}_our_structure.txt").read_text(encoding="utf-8").rstrip())
        lines.append("```")
        lines.append("11. Best-method structure:")
        lines.append("```text")
        lines.append((TEXT_DIR / f"{c['case_id']}_best_structure.txt").read_text(encoding="utf-8").rstrip())
        lines.append("```")
        lines.append(f"12. Concise failure type: `{cmp['failure_type']}`")
        bu = cmp["budget_action_summary"]
        lines.append(f"13. Budget/action summary: budget={bu['budget']}, our(actions={bu['our_actions']}, expand={bu['our_expansions']}, verify={bu['our_verifications']}), best(actions={bu['best_actions']}, expand={bu['best_expansions']}, verify={bu['best_verifications']})")
        lines.append("")

    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
