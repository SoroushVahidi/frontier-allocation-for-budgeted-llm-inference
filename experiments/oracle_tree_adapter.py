"""Adapter: oracle-tree action-log schema -> frontier_target_construction inputs.

The oracle-tree pilot (outputs/oracle_tree_tiny_pilot_*) logs one row per
*node* (one generation action), linked into a tree via (node_id, parent_id).
`experiments/frontier_target_construction.py`'s real-trace ingestion path,
`_collect_frontier_states_from_trace_rows()`, instead expects one row per
*active branch at a decision point*, grouped by (episode_id, decision_id).

This module is the small, mechanical translation layer documented as missing
in outputs/oracle_tree_tiny_pilot_20260716T025239Z/stage4_learning_sanity_check.md:
it reconstructs, for each chronological action t, "which branches (root
lineages) were alive right before action t was taken" and emits one row per
active branch in the trace-row schema `_collect_frontier_states_from_trace_rows`
already knows how to consume (the per-row / no-`active_branches`-list
fallback path). It does not modify frontier_target_construction.py at all.

Gold-leakage discipline: gold fields (gold_answer, node_produces_gold,
subtree_reaches_gold, first_observed_gold_depth, first_observed_gold_cost,
gold_path_ancestry) are threaded through ONLY into a separate "offline
outcome" side-channel for label construction; they are never written into the
`branch_text_raw` / feature-shaped fields that flow into FrontierState.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any

from experiments.frontier_target_construction import (
    FrontierState,
    FrontierTargetConstructionConfig,
    _collect_frontier_states_from_trace_rows,
)

# Actions that start a brand-new root lineage (a fresh branch with no parent).
_NEW_BRANCH_MODES = {"stochastic_restart", "explicit_strategy"}
# Actions that extend / re-examine an existing lineage (parent_id must be set).
_CONTINUING_MODES = {"continuation", "verification"}

GOLD_FIELDS = (
    "gold_answer",
    "node_produces_gold",
    "subtree_reaches_gold",
    "first_observed_gold_depth",
    "first_observed_gold_cost",
    "gold_path_ancestry",
)


def _stable_int_id(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


@dataclass
class ChronologyIssue:
    problem_id: str
    node_id: str
    issue: str


@dataclass
class LineageState:
    """Mutable bookkeeping for one root lineage (= one branch) as we replay
    the tree in chronological order."""

    branch_id: str
    root_node_id: str
    latest_node_id: str
    depth: int = 0
    score: float = 0.5
    is_done: bool = False
    verify_count: int = 0
    branch_age: int = 0
    action_history: list = field(default_factory=list)
    score_history: list = field(default_factory=list)
    depth_history: list = field(default_factory=list)
    latest_reasoning_text: str | None = None
    latest_final_answer_text: str | None = None
    latest_generation_metadata: dict = field(default_factory=dict)


def validate_chronology(rows: list[dict[str, Any]]) -> list[ChronologyIssue]:
    """Programmatic validation of parent/child chronology within one problem's
    node list: no cycles, parents strictly precede children in chronological
    action index, no duplicate node_ids, no dangling non-empty parent_id."""
    issues: list[ChronologyIssue] = []
    rows_sorted = sorted(rows, key=lambda r: int(r["chronological_action_index"]))
    seen_index: dict[str, int] = {}
    for r in rows_sorted:
        nid = str(r["node_id"])
        idx = int(r["chronological_action_index"])
        pid = str(r.get("parent_id") or "")
        if nid in seen_index:
            issues.append(ChronologyIssue(r["problem_id"], nid, "duplicate_node_id"))
            continue
        if pid:
            if pid not in seen_index:
                issues.append(ChronologyIssue(r["problem_id"], nid, f"parent_not_seen_before_child:{pid}"))
            elif seen_index[pid] >= idx:
                issues.append(ChronologyIssue(r["problem_id"], nid, f"parent_index_not_before_child:{pid}"))
            if pid == nid:
                issues.append(ChronologyIssue(r["problem_id"], nid, "self_parent_cycle"))
        seen_index[nid] = idx
    # cycle check via ancestor walk (defensive; the index check above already
    # rules out cycles among chronologically-ordered nodes, but walk anyway).
    parent_of = {str(r["node_id"]): str(r.get("parent_id") or "") for r in rows_sorted}
    for nid in parent_of:
        visited = set()
        cur = nid
        depth_guard = 0
        while cur:
            if cur in visited:
                issues.append(ChronologyIssue(rows_sorted[0]["problem_id"], nid, f"cycle_detected_at:{cur}"))
                break
            visited.add(cur)
            cur = parent_of.get(cur, "")
            depth_guard += 1
            if depth_guard > len(parent_of) + 2:
                issues.append(ChronologyIssue(rows_sorted[0]["problem_id"], nid, "cycle_guard_tripped"))
                break
    return issues


def _describe_action(row: dict[str, Any]) -> str:
    mode = row.get("generation_mode")
    if mode == "stochastic_restart":
        return "new_stochastic_sample"
    if mode == "explicit_strategy":
        strat = row.get("requested_strategy") or "?"
        return f"new_explicit_strategy({strat})"
    if mode == "continuation":
        return f"continue({row.get('parent_id')})"
    if mode == "verification":
        return f"verify({row.get('parent_id')})"
    return f"unknown_mode({mode})"


def build_state_action_examples(
    rows_with_gold: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Replay one problem's chronological node list and emit one
    (state_t, action_t, resulting_state_t, offline_outcome_t) example per
    action, where state_t = the active-branch snapshot immediately BEFORE
    action t, and resulting_state_t = the snapshot immediately AFTER.

    `offline_outcome_t` carries gold fields (label-construction only) kept in
    a clearly separate sub-dict, never mixed into the state/action features.
    """
    if not rows_with_gold:
        return []
    problem_id = rows_with_gold[0]["problem_id"]
    rows_sorted = sorted(rows_with_gold, key=lambda r: int(r["chronological_action_index"]))

    lineages: dict[str, LineageState] = {}  # branch_id -> LineageState
    node_to_branch: dict[str, str] = {}  # node_id -> branch_id it belongs to
    examples: list[dict[str, Any]] = []

    def snapshot_active_branches() -> list[dict[str, Any]]:
        return [
            {
                "branch_id": bid,
                "score": ls.score,
                "depth": ls.depth,
                "is_done": ls.is_done,
                "verify_count": ls.verify_count,
                "branch_age": ls.branch_age,
                "action_history": list(ls.action_history),
                "score_history": list(ls.score_history),
                "depth_history": list(ls.depth_history),
                "branch_reasoning_text_raw": ls.latest_reasoning_text,
                "branch_final_answer_text_raw": ls.latest_final_answer_text,
                "generation_metadata": dict(ls.latest_generation_metadata),
            }
            for bid, ls in lineages.items()
        ]

    for row in rows_sorted:
        node_id = str(row["node_id"])
        parent_id = str(row.get("parent_id") or "")
        action_desc = _describe_action(row)

        state_before = snapshot_active_branches()

        offline_outcome = {k: row.get(k) for k in GOLD_FIELDS if k in row}

        if row.get("generation_mode") in _NEW_BRANCH_MODES or not parent_id:
            branch_id = node_id  # new lineage rooted at this node
            lineages[branch_id] = LineageState(
                branch_id=branch_id,
                root_node_id=node_id,
                latest_node_id=node_id,
                depth=int(row.get("depth", 1)),
                score=float(row.get("branch_score") or 0.5),
                is_done=bool(row.get("is_done", False)),
                verify_count=0,
                branch_age=1,
                action_history=[action_desc],
                score_history=[float(row.get("branch_score") or 0.5)],
                depth_history=[int(row.get("depth", 1))],
                latest_reasoning_text=row.get("full_reasoning_text"),
                latest_final_answer_text=row.get("candidate_answer"),
                latest_generation_metadata={
                    "node_id": node_id,
                    "requested_strategy": row.get("requested_strategy"),
                    "observed_reasoning_family": row.get("observed_reasoning_family"),
                    "generation_mode": row.get("generation_mode"),
                },
            )
            node_to_branch[node_id] = branch_id
        else:
            branch_id = node_to_branch.get(parent_id)
            if branch_id is None or branch_id not in lineages:
                # Defensive fallback: treat as a new lineage if parent
                # bookkeeping is somehow missing (should not happen once
                # validate_chronology() passes clean).
                branch_id = node_id
                lineages[branch_id] = LineageState(
                    branch_id=branch_id, root_node_id=node_id, latest_node_id=node_id,
                )
            ls = lineages[branch_id]
            ls.latest_node_id = node_id
            ls.depth = int(row.get("depth", ls.depth))
            ls.score = float(row.get("branch_score") if row.get("branch_score") is not None else ls.score)
            ls.is_done = bool(row.get("is_done", ls.is_done))
            if row.get("generation_mode") == "verification":
                ls.verify_count += 1
            ls.branch_age += 1
            ls.action_history.append(action_desc)
            ls.score_history.append(ls.score)
            ls.depth_history.append(ls.depth)
            ls.latest_reasoning_text = row.get("full_reasoning_text") or ls.latest_reasoning_text
            ls.latest_final_answer_text = row.get("candidate_answer") or ls.latest_final_answer_text
            node_to_branch[node_id] = branch_id

        state_after = snapshot_active_branches()

        examples.append({
            "problem_id": problem_id,
            "chronological_action_index": int(row["chronological_action_index"]),
            "node_id": node_id,
            "parent_id": parent_id,
            "action_taken": action_desc,
            "budget_before_action": row.get("budget_before_action"),
            "budget_after_action": row.get("budget_after_action"),
            "state_before_active_branches": state_before,
            "state_after_active_branches": state_after,
            "offline_outcome": offline_outcome,
        })

    return examples


def oracle_tree_rows_to_frontier_states(
    rows: list[dict[str, Any]],
    cfg: FrontierTargetConstructionConfig | None = None,
) -> tuple[list[FrontierState], list[dict[str, Any]], list[ChronologyIssue]]:
    """Main adapter entry point.

    Parameters
    ----------
    rows: oracle-tree action-log rows (one problem, or many problems mixed --
        grouping is done internally by problem_id). May be the runtime
        (no-gold) rows or the offline WITH_GOLD rows; gold fields, if
        present, are threaded only into `offline_outcome` /
        trace_provenance-adjacent bookkeeping, never into branch features.
    cfg: FrontierTargetConstructionConfig (defaults used if omitted).

    Returns
    -------
    (frontier_states, state_action_examples, chronology_issues)
      frontier_states: list[FrontierState], built by directly reusing
        experiments.frontier_target_construction._collect_frontier_states_from_trace_rows
        (no logic in that function is modified).
      state_action_examples: flat list of the (state_t, action_t,
        resulting_state, offline_outcome) tuples for every action across all
        problems (see build_state_action_examples()).
      chronology_issues: any parent/child ordering problems found (should be
        empty for clean data; non-empty entries mean a problem's node graph
        did not validate and its rows were still processed best-effort).
    """
    if cfg is None:
        cfg = FrontierTargetConstructionConfig()

    by_problem: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_problem.setdefault(str(r["problem_id"]), []).append(r)

    all_issues: list[ChronologyIssue] = []
    all_examples: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []

    for problem_id, prows in by_problem.items():
        prows_sorted = sorted(prows, key=lambda r: int(r["chronological_action_index"]))
        issues = validate_chronology(prows_sorted)
        all_issues.extend(issues)

        examples = build_state_action_examples(prows_sorted)
        all_examples.extend(examples)

        episode_id = _stable_int_id(problem_id)
        dataset_name = prows_sorted[0].get("dataset")
        # present only in WITH_GOLD rows; use "" (not None) so downstream
        # `str(x).strip() or None` in _collect_frontier_states_from_trace_rows
        # does not turn a genuinely-absent gold answer into the literal
        # string "None" (which would look like a populated ground truth).
        answer = prows_sorted[0].get("gold_answer") or ""

        # Replay again to emit one trace_row per (decision_id=t, active branch)
        # in the schema _collect_frontier_states_from_trace_rows expects.
        for ex in examples:
            decision_id = ex["chronological_action_index"]
            remaining_budget = ex["budget_before_action"]
            active = ex["state_before_active_branches"]
            if len(active) <= 1:
                continue  # matches upstream's own "<=1 active branch" skip
            # need the raw text/final-answer/meta per branch; recover from
            # per-node rows already folded into lineages via a small re-index
            for b in active:
                trace_rows.append({
                    "episode_id": episode_id,
                    "decision_id": decision_id,
                    "remaining_budget": remaining_budget,
                    "dataset_name": dataset_name,
                    "example_id": problem_id,
                    "answer": answer,
                    "split": "train",
                    "branch_id": b["branch_id"],
                    "score": b["score"],
                    "depth": b["depth"],
                    "verify_count": b["verify_count"],
                    "stalled_steps": 0,
                    "recent_delta": (
                        b["score_history"][-1] - b["score_history"][-2]
                        if len(b["score_history"]) >= 2 else 0.0
                    ),
                    "branch_age": b["branch_age"],
                    "is_done": b["is_done"],
                    "is_pruned": False,
                    "action_history": b["action_history"],
                    "score_history": b["score_history"],
                    "depth_history": b["depth_history"],
                    "parent_relative_score": (
                        b["score"] - (sum(x["score"] for x in active) / len(active))
                    ),
                    "branch_text_raw": b.get("branch_reasoning_text_raw"),
                    "branch_reasoning_text_raw": b.get("branch_reasoning_text_raw"),
                    "branch_final_answer_text_raw": b.get("branch_final_answer_text_raw"),
                    "generation_metadata": b.get("generation_metadata", {}),
                })

    frontier_states = _collect_frontier_states_from_trace_rows(trace_rows, cfg)
    return frontier_states, all_examples, all_issues
