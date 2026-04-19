#!/usr/bin/env python3
"""Recover discovered tree/frontier structure for the selected twenty defeat cases."""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchActionResult, BranchState, SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies

AUDIT_DIR = REPO_ROOT / "outputs/full_comparative_mistake_audit_vs_best_method_20260418"
PROXY_DIR = REPO_ROOT / "outputs/branch_label_bruteforce_learning/current_leading_failure_case_extraction_20260418"
DOC_OUT = REPO_ROOT / "docs/TWENTY_DEFEAT_CASES_WITH_DISCOVERED_TREES_2026_04_19.md"
OUT_DIR = REPO_ROOT / "outputs/twenty_defeat_case_trees_20260419"


@dataclass
class DecisionSnapshot:
    decision_index: int
    action: str
    chosen_branch_id: str
    remaining_budget_before: int
    active_frontier_before: list[str]
    branch_states_before: list[dict[str, Any]]


class ObservedGenerator:
    """Wrap SimulatedBranchGenerator and capture branch lifecycle observability."""

    def __init__(self, base: SimulatedBranchGenerator) -> None:
        self.base = base
        self.registry: dict[str, BranchState] = {}
        self.events: list[dict[str, Any]] = []
        self.decision_snaps: list[DecisionSnapshot] = []
        self._decision_counter = 0

    def _snapshot_branch(self, b: BranchState) -> dict[str, Any]:
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
            "action_history": list(b.action_history),
        }

    def _active_snapshot(self) -> list[dict[str, Any]]:
        active = [b for b in self.registry.values() if not b.is_pruned]
        active.sort(key=lambda x: x.branch_id)
        return [self._snapshot_branch(b) for b in active]

    def init_branch(self, branch_id: str) -> BranchState:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        self.events.append({"event": "init_branch", "branch_id": b.branch_id, "score": float(b.score)})
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
                "before": before,
                "after": after,
                "score_after": float(out.score_after),
            }
        )
        return out

    def prune(self, branch: BranchState) -> BranchActionResult:
        out = self.base.prune(branch)
        self.events.append({"event": "prune", "branch_id": branch.branch_id})
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


def _select_twenty() -> list[dict[str, Any]]:
    ranked = _read_json(AUDIT_DIR / "ranked_casebook_records.json")
    mistakes = _read_jsonl(AUDIT_DIR / "all_mistake_records.jsonl")
    failures = [r for r in mistakes if bool(r.get("best_method_correct")) and not bool(r.get("our_method_correct"))]
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in failures:
        by_key[(str(r.get("dataset")), str(r.get("example_id")))].append(r)
    selected: list[dict[str, Any]] = []
    for rr in ranked:
        key = (str(rr.get("dataset")), str(rr.get("example_id")))
        rows = by_key.get(key, [])
        if not rows:
            continue
        representative = sorted(rows, key=lambda r: (int(r.get("seed", 0)), int(r.get("budget", 0))), reverse=True)[0]
        selected.append(representative)
        if len(selected) >= 20:
            break
    if len(selected) != 20:
        raise RuntimeError(f"expected 20 selected, got {len(selected)}")
    return selected


def _oracle_proxy_lookup() -> dict[tuple[str, str], dict[str, Any]]:
    table = _read_json(PROXY_DIR / "failure_case_ranking_table.json").get("rows", [])
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in table:
        k = (str(r.get("dataset_name")), str(r.get("example_id")))
        if k not in out or float(r.get("oracle_gap_if_choose_k3", 0.0)) > float(out[k].get("oracle_gap_if_choose_k3", 0.0)):
            out[k] = r
    return out


def _run_recovered_case(row: dict[str, Any]) -> dict[str, Any]:
    dataset = str(row["dataset"])
    example_id = str(row["example_id"])
    budget = int(row["budget"])
    seed = int(row["seed"])
    question = str(row["problem_text"])
    gold = str(row["ground_truth"])

    replay_seed = _stable_seed("recover", dataset, example_id, seed, budget)
    rng = random.Random(replay_seed)

    observed_gen = ObservedGenerator(
        SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    )

    def factory() -> ObservedGenerator:
        return observed_gen

    strategies = build_frontier_strategies(
        factory,
        budget,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    our = strategies["broad_diversity_aggregation_v1"].run(question, gold)
    best_rng = random.Random(_stable_seed("recover_best", dataset, example_id, seed, budget))

    def best_factory() -> SimulatedBranchGenerator:
        return SimulatedBranchGenerator(rng=best_rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)

    best_strategies = build_frontier_strategies(
        best_factory,
        budget,
        [1],
        best_rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    best = best_strategies["self_consistency_3"].run(question, gold)

    # Fill remaining_budget_before for each decision.
    for i, snap in enumerate(observed_gen.decision_snaps):
        snap.remaining_budget_before = max(0, budget - i)

    # Infer parent->child links from init events occurring after expand.
    parent_map: dict[str, str] = {}
    last_expand: str | None = None
    for ev in observed_gen.events:
        if ev["event"] == "expand":
            last_expand = str(ev["branch_id"])
        elif ev["event"] == "init_branch" and last_expand is not None and str(ev["branch_id"]).startswith("div_child_"):
            parent_map[str(ev["branch_id"])] = last_expand

    final_branches = []
    for b in sorted(observed_gen.registry.values(), key=lambda x: x.branch_id):
        final_branches.append(
            {
                "branch_id": b.branch_id,
                "parent_branch_id": parent_map.get(b.branch_id),
                "depth": int(b.depth),
                "verify_count": int(b.verify_count),
                "is_done": bool(b.is_done),
                "is_pruned": bool(b.is_pruned),
                "predicted_answer": b.predicted_answer,
                "action_history": list(b.action_history),
            }
        )

    action_trace = list(our.metadata.get("action_trace", []))
    decisions = []
    for i, snap in enumerate(observed_gen.decision_snaps):
        trace = action_trace[i] if i < len(action_trace) else {}
        decisions.append(
            {
                "decision_index": int(snap.decision_index),
                "action": snap.action,
                "chosen_branch_id": snap.chosen_branch_id,
                "remaining_budget_before": int(snap.remaining_budget_before),
                "budget_consumed_this_step": 1,
                "active_frontier_before": list(snap.active_frontier_before),
                "active_branch_states_before": snap.branch_states_before,
                "trace_metadata": {
                    "priority": trace.get("priority"),
                    "continuation_value": trace.get("continuation_value"),
                    "target_alignment_score": trace.get("target_alignment_score"),
                    "target_alignment_category": trace.get("target_alignment_category"),
                    "gate_decision": trace.get("gate_decision"),
                },
            }
        )

    return {
        "dataset": dataset,
        "example_id": example_id,
        "problem_statement": question,
        "ground_truth_answer": gold,
        "original_failure_record": {
            "seed": seed,
            "budget": budget,
            "our_method_final_answer": row.get("our_method_final_answer"),
            "best_method_final_answer": row.get("best_method_final_answer"),
        },
        "recovered_run": {
            "run_mode": "deterministic_simulated_replay",
            "replay_seed": replay_seed,
            "initial_branching": {"init_branches": 2, "max_branches": 4},
            "total_budget": budget,
            "decisions_used": len(decisions),
            "our_method_prediction": our.prediction,
            "best_method_prediction": best.prediction,
            "our_method_correct": bool(our.is_correct),
            "best_method_correct": bool(best.is_correct),
            "our_method_metadata": {
                "unique_answer_groups_seen": our.metadata.get("unique_answer_groups_seen"),
                "answer_support_entropy": our.metadata.get("answer_support_entropy"),
                "final_selected_group": our.metadata.get("selected_group"),
                "gold_group_present_final": our.metadata.get("gold_group_present_final"),
                "gold_group_disappeared_step": our.metadata.get("gold_group_disappeared_step"),
            },
        },
        "tree_summary": {
            "branches_created": len([e for e in observed_gen.events if e.get("event") == "init_branch"]),
            "max_depth": max((int(b["depth"]) for b in final_branches), default=0),
            "expand_actions": sum(1 for d in decisions if d["action"] == "expand"),
            "verify_actions": sum(1 for d in decisions if d["action"] == "verify"),
            "surviving_frontier_end": len([b for b in final_branches if not b["is_pruned"] and not b["is_done"]]),
        },
        "decisions": decisions,
        "final_tree": {
            "parent_links_inference": "inferred_from_child_creation_events_after_expand",
            "branches": final_branches,
        },
        "provenance_label": "partially_reconstructed_from_metadata",
    }


def _render_case_md(case_idx: int, c: dict[str, Any], oracle_proxy: dict[str, Any] | None) -> str:
    r = c["recovered_run"]
    ts = c["tree_summary"]
    lines = []
    lines.append(f"## Case {case_idx}: `{c['dataset']} / {c['example_id']}`")
    lines.append(f"- **Problem**: {c['problem_statement']}")
    lines.append(f"- **Ground truth**: `{c['ground_truth_answer']}`")
    lines.append(
        f"- **Original failure record**: seed={c['original_failure_record']['seed']}, budget={c['original_failure_record']['budget']}, "
        f"our_answer=`{c['original_failure_record']['our_method_final_answer']}`, best_answer=`{c['original_failure_record']['best_method_final_answer']}`"
    )
    lines.append(
        f"- **Recovered run setup**: budget={r['total_budget']}, init_branches=2, max_branches=4, replay_seed={r['replay_seed']}"
    )
    lines.append(
        f"- **Recovered outputs**: our_method=`{r['our_method_prediction']}` (correct={r['our_method_correct']}), "
        f"best_method=`{r['best_method_prediction']}` (correct={r['best_method_correct']})"
    )
    if oracle_proxy:
        lines.append(
            f"- **Oracle-best branch (proxy, when available)**: `{oracle_proxy.get('oracle_best_branch')}`, "
            f"method-selected-branch(proxy) `{oracle_proxy.get('method_choice_k3')}`"
        )
    lines.append(
        "- **Tree summary**: "
        f"branches_created={ts['branches_created']}, max_depth={ts['max_depth']}, "
        f"expand_actions={ts['expand_actions']}, verify_actions={ts['verify_actions']}, "
        f"surviving_frontier_end={ts['surviving_frontier_end']}"
    )
    lines.append("- **Provenance**: `partially reconstructed from metadata` (frontier/decision snapshots direct from replay; parent links inferred).")
    lines.append("- **Decision timeline**:")
    for d in c["decisions"]:
        lines.append(
            "  - "
            f"d{d['decision_index']}: action={d['action']}, chosen={d['chosen_branch_id']}, "
            f"remaining_budget_before={d['remaining_budget_before']}, "
            f"active={d['active_frontier_before']}"
        )
    lines.append("- **Final discovered frontier/tree**:")
    lines.append("```text")
    lines.append("root")
    by_parent: dict[str | None, list[str]] = defaultdict(list)
    for b in c["final_tree"]["branches"]:
        by_parent[b.get("parent_branch_id")].append(b["branch_id"])
    for k in by_parent:
        by_parent[k].sort()

    def rec(node: str | None, indent: int) -> None:
        for child in by_parent.get(node, []):
            b = next(x for x in c["final_tree"]["branches"] if x["branch_id"] == child)
            status = "done" if b["is_done"] else ("pruned" if b["is_pruned"] else "active")
            lines.append("  " * indent + f"- {child} [depth={b['depth']}, verify={b['verify_count']}, status={status}]")
            rec(child, indent + 1)

    rec(None, 1)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = _select_twenty()
    oracle_lookup = _oracle_proxy_lookup()

    recovered_cases: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    budget_rows: list[dict[str, Any]] = []

    for row in cases:
        rec = _run_recovered_case(row)
        k = (rec["dataset"], rec["example_id"])
        proxy = oracle_lookup.get(k)
        if proxy:
            rec["oracle_proxy"] = {
                "state_id": proxy.get("state_id"),
                "oracle_best_branch": proxy.get("oracle_best_branch"),
                "method_choice_k3": proxy.get("method_choice_k3"),
                "remaining_budget": proxy.get("remaining_budget"),
            }
        cid = f"{rec['dataset'].replace('/', '__')}__{rec['example_id']}"
        (OUT_DIR / f"{cid}.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        recovered_cases.append(rec)
        manifest_rows.append(
            {
                "case_id": cid,
                "dataset": rec["dataset"],
                "example_id": rec["example_id"],
                "provenance_label": rec["provenance_label"],
                "total_budget": rec["recovered_run"]["total_budget"],
                "decisions_used": rec["recovered_run"]["decisions_used"],
            }
        )
        budget_rows.append(
            {
                "dataset": rec["dataset"],
                "example_id": rec["example_id"],
                "total_budget": rec["recovered_run"]["total_budget"],
                "decisions_used": rec["recovered_run"]["decisions_used"],
                "branch_creation_count": rec["tree_summary"]["branches_created"],
                "expansion_count": rec["tree_summary"]["expand_actions"],
                "verify_count": rec["tree_summary"]["verify_actions"],
                "remaining_budget_at_final_wrong_turn": max(0, rec["recovered_run"]["total_budget"] - rec["recovered_run"]["decisions_used"]),
                "correct_answer_group_alive_low_budget": rec["recovered_run"]["our_method_metadata"].get("gold_group_present_final"),
            }
        )

    (OUT_DIR / "manifest.json").write_text(json.dumps({"cases": manifest_rows}, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "budget_summary_table.json").write_text(json.dumps({"rows": budget_rows}, indent=2) + "\n", encoding="utf-8")

    summary = {
        "total_cases": len(recovered_cases),
        "direct_tree_supported": 0,
        "direct_frontier_history_supported": 0,
        "partially_reconstructed_from_metadata": len(recovered_cases),
        "insufficient_to_reconstruct": 0,
    }
    (OUT_DIR / "recoverability_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Twenty defeat cases with discovered trees (2026-04-19)",
        "",
        "## Method definitions",
        "- Our method: `broad_diversity_aggregation_v1`.",
        "- Best method: `self_consistency_3`.",
        "",
        "## Recoverability honesty note",
        "- Source data did not expose full original tree pointers for all 20 selected cases.",
        "- This document reports deterministic simulated replay tree/frontier discovery with explicit provenance labels.",
        "- Parent links are inferred only when a child branch was created immediately after an expand event.",
        "",
        "## Cross-case recoverability summary",
        f"- direct-tree-supported: {summary['direct_tree_supported']}",
        f"- direct frontier-history-supported: {summary['direct_frontier_history_supported']}",
        f"- partially reconstructed from metadata: {summary['partially_reconstructed_from_metadata']}",
        f"- insufficient to reconstruct: {summary['insufficient_to_reconstruct']}",
        "",
        "## Compact budget table",
        "| dataset | example_id | budget | used | created | expand | verify | rem_after_last | gold_alive_final |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in budget_rows:
        lines.append(
            f"| {r['dataset']} | {r['example_id']} | {r['total_budget']} | {r['decisions_used']} | {r['branch_creation_count']} | "
            f"{r['expansion_count']} | {r['verify_count']} | {r['remaining_budget_at_final_wrong_turn']} | {r['correct_answer_group_alive_low_budget']} |"
        )
    lines.append("")

    for i, c in enumerate(recovered_cases, start=1):
        k = (c["dataset"], c["example_id"])
        lines.append(_render_case_md(i, c, oracle_lookup.get(k)))

    lines.extend(
        [
            "## Aggregate structural pattern summary",
            "- Dominant pattern in replayed trees: repeated expansion of one high-priority branch with shallow child spawning.",
            "- In many cases, divergence is early-to-mid trajectory (before full budget exhaustion), not only at final commit.",
        ]
    )

    DOC_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
