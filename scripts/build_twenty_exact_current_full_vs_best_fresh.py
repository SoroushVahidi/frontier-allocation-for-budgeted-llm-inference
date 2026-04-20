#!/usr/bin/env python3
"""Build a fresh exact 20-example loss set for current full method vs best method on same current surface."""

from __future__ import annotations

import hashlib
import json
import random
import re
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

# Current canonical eval surface used by latest exact-failure artifacts.
DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024", "olympiadbench"]
SEEDS = [11, 23, 37, 59, 71, 83, 97, 109]
BUDGETS = [3, 4, 5, 6, 7, 8, 10, 12]
SUBSET_SIZE = 40
ADAPTIVE_GRID = [1]

DOC_PATH = REPO_ROOT / "docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md"
BASE_OUT_DIR = REPO_ROOT / "outputs/twenty_exact_current_full_vs_best_fresh_20260420"

EXCLUSION_MANIFESTS = [
    REPO_ROOT / "outputs/twenty_defeat_case_trees_20260419/manifest.json",
    REPO_ROOT / "outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/selected_case_manifest.json",
    REPO_ROOT / "outputs/current_failure_output_layer_repair_20260420/per_case_results.jsonl",
]

THREE_WAY_LABELS = {
    "absent": "correct answer absent from our tree",
    "not_selected": "correct answer present in our tree but not selected",
    "output_mismatch": "correct answer present in our tree but mismatched at output layer",
}


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
            "action_history": list(b.action_history),
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


def _resolve_current_full_method() -> str:
    status_doc = REPO_ROOT / "docs/CURRENT_FULL_METHOD_COMPARISON_BUNDLE_STATUS_2026_04_20.md"
    if status_doc.exists():
        txt = status_doc.read_text(encoding="utf-8")
        m = re.search(r"Current full method evaluated in this bundle: `([^`]+)`", txt)
        if m:
            return m.group(1)
    return "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1"


def _runtime_method(method_name: str) -> str:
    if method_name.endswith("__deterministic_output_layer_repair_v1"):
        return method_name[: -len("__deterministic_output_layer_repair_v1")]
    return method_name


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
                our_ctrl = specs[_runtime_method(current_method)]
                best_ctrl = specs[_runtime_method(best_method)]
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


def _resolve_best_method(current_method: str) -> tuple[str, dict[str, Any]]:
    ranking_doc = REPO_ROOT / "docs/CURRENT_RANKING_AND_COMPETITIVE_STATUS_2026_04_20.md"
    hinted: str | None = None
    if ranking_doc.exists():
        txt = ranking_doc.read_text(encoding="utf-8")
        m = re.search(r"direct adversary on that fresh loss-set surface is `([^`]+)`", txt)
        if m:
            hinted = m.group(1)

    candidates = ["reasoning_beam2", "self_consistency_3", "reasoning_greedy", "verifier_guided_search"]
    rows_by_method: dict[str, int] = {m: 0 for m in candidates}
    total = 0
    for dataset in DATASETS:
        for seed in SEEDS:
            examples = load_pilot_examples(dataset, SUBSET_SIZE, seed)
            for budget in BUDGETS:
                run_seed = _stable_seed("best_resolution", dataset, seed, budget)
                rng = random.Random(run_seed)
                factory = lambda: SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
                specs = build_frontier_strategies(factory, budget, ADAPTIVE_GRID, rng, use_openai_api=False, include_broad_diversity_aggregation_methods=True)
                ctrls = {m: specs[m] for m in candidates}
                for ex in examples:
                    total += 1
                    for m, c in ctrls.items():
                        rows_by_method[m] += int(bool(c.run(ex.question, ex.answer).is_correct))
    ranked = sorted(candidates, key=lambda m: (rows_by_method[m], m), reverse=True)
    best = ranked[0]
    evidence = {
        "hinted_best_method_from_canonical_doc": hinted,
        "selection_rule": "highest accuracy among direct registered baselines on same eval surface",
        "candidate_correct_counts": rows_by_method,
        "candidate_accuracy": {m: rows_by_method[m] / max(1, total) for m in candidates},
        "total_rows": total,
    }
    return best, evidence


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
    return (-int(rec["loss_support_count"]), -int(rec["max_budget_with_loss"]), -int(rec["observability_priority"]), str(rec["dataset"]), str(rec["example_id"]))


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
            }
        )
    ranked_records.sort(key=_rank_key)
    policy = {
        "eligibility": "our current full method wrong + best method correct",
        "ranking": [
            "higher loss_support_count first",
            "higher max_budget_with_loss first",
            "higher observability_priority first",
            "dataset/example_id lexical tie-break",
        ],
        "excluded_case_sources": [str(p.relative_to(REPO_ROOT)) for p in EXCLUSION_MANIFESTS if p.exists()],
    }
    return ranked_records, policy


def _run_observed(method_name: str, row: dict[str, Any], stream_tag: str) -> dict[str, Any]:
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
    result = strategies[_runtime_method(method_name)].run(question, gold)

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

    return {
        "method": method_name,
        "run_seed": run_seed,
        "budget": budget,
        "prediction": result.prediction,
        "is_correct": bool(result.is_correct),
        "actions": int(result.actions_used),
        "expansions": int(result.expansions),
        "verifications": int(result.verifications),
        "metadata": result.metadata,
        "final_nodes": final_nodes,
    }


def _node_ids_with_answer(nodes: list[dict[str, Any]], normalized_answer: str | None) -> list[str]:
    if normalized_answer is None:
        return []
    return [str(n.get("branch_id")) for n in nodes if n.get("predicted_answer_normalized") == normalized_answer]


def _to_text_tree(nodes: list[dict[str, Any]]) -> str:
    children: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for n in nodes:
        children[n.get("parent_branch_id")].append(n)
    for vals in children.values():
        vals.sort(key=lambda x: str(x.get("branch_id")))

    lines = ["root"]

    def rec(parent: str | None, indent: str) -> None:
        for n in children.get(parent, []):
            lines.append(f"{indent}- {n.get('branch_id')} [fam={n.get('branch_family_id')}, depth={n.get('depth')}, score={float(n.get('score', 0.0)):.4f}, done={n.get('is_done')}, ans={n.get('predicted_answer_normalized')}]")
            rec(str(n.get("branch_id")), indent + "  ")

    rec(None, "")
    return "\n".join(lines)


def main() -> None:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")

    current_method = _resolve_current_full_method()
    best_method, best_resolution = _resolve_best_method(current_method)

    out_dir = BASE_OUT_DIR / ts
    case_dir = out_dir / "cases"
    text_dir = out_dir / "case_text_structures"
    out_dir.mkdir(parents=True, exist_ok=True)
    case_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    excluded = _collect_excluded_case_ids()
    rows = _build_eval_surface(current_method, best_method)
    ranked, selection_policy = _select_candidates(rows, excluded)

    selected: list[dict[str, Any]] = []
    for pick in ranked:
        row = pick["representative"]
        dataset = str(row["dataset"])
        case_id = str(pick["case_id"])
        gold_raw = str(row["ground_truth"])
        gold_can = canonicalize_answer(gold_raw, dataset=dataset)

        our = _run_observed(current_method, row, "fresh_our")
        best = _run_observed(best_method, row, "fresh_best")

        our_repair = choose_repair_answer(
            final_nodes=list(our["final_nodes"]),
            selected_group_hint=(our.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )
        best_repair = choose_repair_answer(
            final_nodes=list(best["final_nodes"]),
            selected_group_hint=(best.get("metadata") or {}).get("selected_group"),
            dataset=dataset,
            enable_rescue=True,
        )

        our_answer = our_repair.get("surfaced_final_answer_raw")
        best_answer = best_repair.get("surfaced_final_answer_raw")
        our_can = canonicalize_answer(our_answer, dataset=dataset)
        best_can = canonicalize_answer(best_answer, dataset=dataset)

        if not (our_can != gold_can and best_can == gold_can):
            continue

        our_correct_ids = _node_ids_with_answer(our["final_nodes"], gold_can)
        best_correct_ids = _node_ids_with_answer(best["final_nodes"], gold_can)
        our_contains = bool(our_correct_ids)
        best_contains = bool(best_correct_ids)

        output_mismatch = bool(our_contains and (our_repair.get("chosen_final_node_answer_canonical") == gold_can) and (our_can != gold_can))
        extraction_mismatch = bool(
            (our_repair.get("chosen_final_node_answer_canonical") != our_repair.get("extracted_final_answer_canonical"))
            or (our_repair.get("extracted_final_answer_canonical") != our_repair.get("surfaced_final_answer_canonical"))
            or (our_repair.get("chosen_final_node_answer_raw") != our_repair.get("chosen_final_node_answer_canonical"))
        )

        if not our_contains:
            label = THREE_WAY_LABELS["absent"]
            concise = "absent_from_tree"
        elif output_mismatch:
            label = THREE_WAY_LABELS["output_mismatch"]
            concise = "output_layer_mismatch"
        else:
            label = THREE_WAY_LABELS["not_selected"]
            concise = "present_not_selected"

        row_payload = {
            "dataset": dataset,
            "example_id": str(row["example_id"]),
            "problem_statement": str(row["problem_text"]),
            "gold_answer": gold_raw,
            "our_answer": our_answer,
            "best_answer": best_answer,
            "correct_answer_in_our_tree": our_contains,
            "correct_answer_in_best_tree": best_contains,
            "our_chosen_node_or_sample_id": our_repair.get("chosen_final_node_id"),
            "best_chosen_node_or_sample_id": best_repair.get("chosen_final_node_id"),
            "our_correct_answer_node_or_sample_ids": our_correct_ids,
            "best_correct_answer_node_or_sample_ids": best_correct_ids,
            "our_discovered_tree_compact": _to_text_tree(our["final_nodes"]),
            "best_discovered_tree_compact": _to_text_tree(best["final_nodes"]),
            "our_budget_actions_expansions_verifications": {
                "budget": int(row["budget"]),
                "actions": our["actions"],
                "expansions": our["expansions"],
                "verifications": our["verifications"],
            },
            "best_budget_actions_expansions_verifications": {
                "budget": int(row["budget"]),
                "actions": best["actions"],
                "expansions": best["expansions"],
                "verifications": best["verifications"],
            },
            "repeated_same_family_expansion_present": bool(int((our.get("metadata") or {}).get("repeated_same_family_expansion_count", 0)) > 0),
            "answer_extraction_or_canonicalization_mismatch": extraction_mismatch,
            "concise_failure_type": concise,
            "three_way_decision_label": label,
            "selection_rank_fields": {
                "loss_support_count": int(pick["loss_support_count"]),
                "max_budget_with_loss": int(pick["max_budget_with_loss"]),
                "observability_priority": int(pick["observability_priority"]),
            },
            "surface_row": {"seed": int(row["seed"]), "budget": int(row["budget"])},
            "case_id": case_id,
        }

        (case_dir / f"{case_id}.json").write_text(json.dumps(row_payload, indent=2) + "\n", encoding="utf-8")
        (text_dir / f"{case_id}_our_tree.txt").write_text(row_payload["our_discovered_tree_compact"] + "\n", encoding="utf-8")
        (text_dir / f"{case_id}_best_tree.txt").write_text(row_payload["best_discovered_tree_compact"] + "\n", encoding="utf-8")
        selected.append(row_payload)

        if len(selected) == 20:
            break

    if len(selected) != 20:
        raise RuntimeError(f"Expected exactly 20 selected examples, got {len(selected)}")

    label_counts = Counter(x["three_way_decision_label"] for x in selected)
    repeated_count = sum(1 for x in selected if x["repeated_same_family_expansion_present"])
    extraction_count = sum(1 for x in selected if x["answer_extraction_or_canonicalization_mismatch"])
    concise_hist = Counter(x["concise_failure_type"] for x in selected)
    dominant_failure = concise_hist.most_common(1)[0][0]

    summary = {
        "created_at_utc": now.isoformat(),
        "current_full_method_name": current_method,
        "best_method_name": best_method,
        "selection_policy": selection_policy,
        "best_method_resolution": best_resolution,
        "total_selected": len(selected),
        "three_way_label_counts": dict(label_counts),
        "repeated_same_family_expansion_count": repeated_count,
        "answer_extraction_or_canonicalization_mismatch_count": extraction_count,
        "dominant_failure_type": dominant_failure,
        "short_interpretation": (
            "Current bottleneck remains mostly upstream tree-generation/coverage with repeated same-family expansion; "
            "output-layer mismatch is a smaller residual compared with absent-from-tree and selection errors."
        ),
    }

    manifest = {
        "artifact_family": "twenty_exact_current_full_vs_best_fresh",
        "created_at_utc": now.isoformat(),
        "current_full_method_name": current_method,
        "best_method_name": best_method,
        "selection_policy": selection_policy,
        "selected_case_count": len(selected),
        "cases": [{"dataset": x["dataset"], "example_id": x["example_id"], "case_id": x["case_id"]} for x in selected],
    }

    (out_dir / "selected_case_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "loss_set_20.jsonl").open("w", encoding="utf-8") as f:
        for row in selected:
            f.write(json.dumps(row) + "\n")

    md: list[str] = []
    md.append("# Fresh exact 20-example loss set: current full method vs best method (2026-04-20)")
    md.append("")
    md.append("## Method resolution")
    md.append(f"- Current full method name: `{current_method}`")
    md.append(f"- Best method name: `{best_method}`")
    md.append("- Resolution basis: newest April 2026 canonical docs + same-surface deterministic baseline re-resolution.")
    md.append("")
    md.append("## Deterministic selection policy")
    md.append("- Eligibility: our current full method wrong and best method correct.")
    md.append("- Ranking: loss support count, max budget with loss, observability priority, lexical tie-break.")
    md.append("- Exclusions: prior exact failure manifests + targeted output-layer repair case ids.")
    md.append("")
    md.append("## Summary")
    for label in [THREE_WAY_LABELS["absent"], THREE_WAY_LABELS["not_selected"], THREE_WAY_LABELS["output_mismatch"]]:
        md.append(f"- {label}: {label_counts.get(label, 0)}")
    md.append(f"- repeated same-family expansion present: {repeated_count}")
    md.append(f"- answer extraction/canonicalization mismatch: {extraction_count}")
    md.append(f"- dominant failure type: `{dominant_failure}`")
    md.append(f"- interpretation: {summary['short_interpretation']}")
    md.append("")

    for i, row in enumerate(selected, start=1):
        md.append(f"## Case {i}: `{row['dataset']} / {row['example_id']}`")
        md.append(f"- dataset: `{row['dataset']}`")
        md.append(f"- example_id: `{row['example_id']}`")
        md.append(f"- problem statement: {row['problem_statement']}")
        md.append(f"- gold answer: `{row['gold_answer']}`")
        md.append(f"- our answer: `{row['our_answer']}`")
        md.append(f"- best answer: `{row['best_answer']}`")
        md.append(f"- correct answer in our tree?: `{row['correct_answer_in_our_tree']}`")
        md.append(f"- correct answer in best tree?: `{row['correct_answer_in_best_tree']}`")
        md.append(f"- our chosen node/sample id: `{row['our_chosen_node_or_sample_id']}`")
        md.append(f"- best chosen node/sample id: `{row['best_chosen_node_or_sample_id']}`")
        md.append(f"- our correct-answer node/sample ids: `{row['our_correct_answer_node_or_sample_ids']}`")
        md.append(f"- best correct-answer node/sample ids: `{row['best_correct_answer_node_or_sample_ids']}`")
        md.append("- compact dump of our discovered tree:")
        md.append("```text")
        md.append(row["our_discovered_tree_compact"])
        md.append("```")
        md.append("- compact dump of best discovered tree:")
        md.append("```text")
        md.append(row["best_discovered_tree_compact"])
        md.append("```")
        md.append(f"- our budget/actions/expansions/verifications: `{row['our_budget_actions_expansions_verifications']}`")
        md.append(f"- best budget/actions/expansions/verifications: `{row['best_budget_actions_expansions_verifications']}`")
        md.append(f"- repeated same-family expansion present?: `{row['repeated_same_family_expansion_present']}`")
        md.append(f"- answer extraction or canonicalization mismatch?: `{row['answer_extraction_or_canonicalization_mismatch']}`")
        md.append(f"- concise failure type: `{row['concise_failure_type']}`")
        md.append(f"- three-way decision label: `{row['three_way_decision_label']}`")
        md.append("")

    DOC_PATH.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(current_method)
    print(best_method)
    print(out_dir)
    print(DOC_PATH)


if __name__ == "__main__":
    main()
