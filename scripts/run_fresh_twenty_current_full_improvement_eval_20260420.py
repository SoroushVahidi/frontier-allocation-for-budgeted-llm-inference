#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import random
import re
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

SOURCE_DOC = REPO_ROOT / "docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md"
IMPROVED_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_width_depth_challenger_guard_v1"


@dataclass
class CaseSpec:
    dataset: str
    example_id: str
    budget: int
    gold_answer: str


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


def _stable_seed(*parts: Any) -> int:
    s = "||".join(str(x) for x in parts)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def _norm(x: str | None) -> str | None:
    return normalize_answer_text(x).get("normalized_answer") if x is not None else None


def _runtime_method(method_name: str) -> str:
    suffix = "__deterministic_output_layer_repair_v1"
    if method_name.endswith(suffix):
        return method_name[: -len(suffix)]
    return method_name


def _parse_source() -> tuple[str, str, list[CaseSpec]]:
    txt = SOURCE_DOC.read_text(encoding="utf-8")
    old = re.search(r"Current full method name: `([^`]+)`", txt).group(1)
    best = re.search(r"Best method name: `([^`]+)`", txt).group(1)
    blocks = re.split(r"\n## Case \d+: ", txt)[1:]
    out: list[CaseSpec] = []
    for blk in blocks:
        m_head = re.search(r"`([^`]+) / ([^`]+)`", blk)
        m_budget = re.search(r"our budget/actions/expansions/verifications: `\{'budget':\s*(\d+)", blk)
        m_gold = re.search(r"gold answer: `([^`]+)`", blk)
        if not (m_head and m_budget and m_gold):
            continue
        out.append(CaseSpec(dataset=m_head.group(1), example_id=m_head.group(2), budget=int(m_budget.group(1)), gold_answer=m_gold.group(1)))
    return old, best, out


def _find_question(dataset: str, example_id: str) -> str:
    for seed in [11, 23, 37, 59, 71, 83, 97, 109]:
        for ex in load_pilot_examples(dataset, 40, seed):
            if ex.example_id == example_id:
                return ex.question
    raise ValueError(f"question not found for {dataset}/{example_id}")


def _run_case(method: str, c: CaseSpec, question: str) -> dict[str, Any]:
    run_seed = _stable_seed("improvement_eval", method, c.dataset, c.example_id, c.budget)
    rng = random.Random(run_seed)
    gen = ObservedGenerator(SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12))
    specs = build_frontier_strategies(
        generator_factory=lambda: gen,
        budget=c.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    res = specs[method].run(question, c.gold_answer)
    final_nodes = []
    for b in gen.registry.values():
        if b.is_pruned:
            continue
        final_nodes.append({"branch_id": b.branch_id, "pred": _norm(str(b.predicted_answer) if b.predicted_answer is not None else None)})
    pred = _norm(str(res.prediction) if res.prediction is not None else None)
    gold = _norm(c.gold_answer)
    gold_nodes = [n["branch_id"] for n in final_nodes if n.get("pred") == gold]
    return {
        "prediction": res.prediction,
        "prediction_norm": pred,
        "is_correct": bool(res.is_correct),
        "gold_present_in_tree": bool(gold_nodes),
        "gold_node_ids": gold_nodes,
        "metadata": res.metadata,
    }


def _decision_label(run: dict[str, Any]) -> str:
    if run["is_correct"]:
        return "correct"
    if not run["gold_present_in_tree"]:
        return "correct answer absent from tree"
    return "correct answer present but not selected"


def main() -> None:
    old_full, best_method, cases = _parse_source()
    old_runtime = _runtime_method(old_full)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / f"twenty_exact_current_full_improvement_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case: list[dict[str, Any]] = []
    for c in cases:
        q = _find_question(c.dataset, c.example_id)
        old_run = _run_case(old_runtime, c, q)
        new_run = _run_case(IMPROVED_METHOD, c, q)
        best_run = _run_case(best_method, c, q)
        per_case.append(
            {
                "dataset": c.dataset,
                "example_id": c.example_id,
                "budget": c.budget,
                "gold_answer": c.gold_answer,
                "old": old_run,
                "improved": new_run,
                "best": best_run,
                "old_label": _decision_label(old_run),
                "improved_label": _decision_label(new_run),
                "changed_to_correct": (not old_run["is_correct"]) and new_run["is_correct"],
                "repeated_same_family_before": int((old_run["metadata"] or {}).get("repeated_same_family_expansion_count", 0)),
                "repeated_same_family_after": int((new_run["metadata"] or {}).get("repeated_same_family_expansion_count", 0)),
            }
        )

    improved_n = sum(1 for r in per_case if r["changed_to_correct"])
    old_correct = sum(1 for r in per_case if r["old"]["is_correct"])
    new_correct = sum(1 for r in per_case if r["improved"]["is_correct"])
    summary = {
        "old_method": old_full,
        "old_runtime_method": old_runtime,
        "improved_method": IMPROVED_METHOD,
        "best_reference_method": best_method,
        "n_cases": len(per_case),
        "old_correct": old_correct,
        "improved_correct": new_correct,
        "improved_cases": improved_n,
        "old_absent_from_tree": sum(1 for r in per_case if r["old_label"] == "correct answer absent from tree"),
        "improved_absent_from_tree": sum(1 for r in per_case if r["improved_label"] == "correct answer absent from tree"),
        "old_present_not_selected": sum(1 for r in per_case if r["old_label"] == "correct answer present but not selected"),
        "improved_present_not_selected": sum(1 for r in per_case if r["improved_label"] == "correct answer present but not selected"),
        "old_repeated_same_family_total": sum(int(r["repeated_same_family_before"]) for r in per_case),
        "improved_repeated_same_family_total": sum(int(r["repeated_same_family_after"]) for r in per_case),
        "mean_actions_old": sum(float((r["old"]["metadata"] or {}).get("action_trace") and len((r["old"]["metadata"] or {}).get("action_trace")) or 0) for r in per_case) / max(1, len(per_case)),
        "mean_actions_new": sum(float((r["improved"]["metadata"] or {}).get("action_trace") and len((r["improved"]["metadata"] or {}).get("action_trace")) or 0) for r in per_case) / max(1, len(per_case)),
    }

    (out_dir / "per_case_before_after.json").write_text(json.dumps(per_case, indent=2), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "dataset,example_id,budget,old_correct,improved_correct,old_label,improved_label,old_repeated_same_family,improved_repeated_same_family,old_actions,improved_actions,old_expansions,improved_expansions,old_verifications,improved_verifications"
    ]
    for r in per_case:
        om = r["old"]["metadata"] or {}
        nm = r["improved"]["metadata"] or {}
        lines.append(
            ",".join(
                [
                    r["dataset"],
                    r["example_id"],
                    str(r["budget"]),
                    str(int(r["old"]["is_correct"])),
                    str(int(r["improved"]["is_correct"])),
                    r["old_label"],
                    r["improved_label"],
                    str(r["repeated_same_family_before"]),
                    str(r["repeated_same_family_after"]),
                    str(len(om.get("action_trace") or [])),
                    str(len(nm.get("action_trace") or [])),
                    str(int(om.get("expand_action_count", 0))),
                    str(int(nm.get("expand_action_count", 0))),
                    str(int(sum(1 for a in (om.get("action_trace") or []) if str(a.get("action")) == "verify"))),
                    str(int(sum(1 for a in (nm.get("action_trace") or []) if str(a.get("action")) == "verify"))),
                ]
            )
        )
    (out_dir / "per_case_before_after.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = REPO_ROOT / f"docs/TWENTY_CASE_CURRENT_FULL_IMPROVEMENT_REPORT_{ts}.md"
    md = [
        f"# Twenty-case targeted improvement report ({ts})",
        "",
        "## Method change",
        f"- Old current full runtime method: `{old_runtime}`",
        f"- Improved method: `{IMPROVED_METHOD}`",
        "- Added explicit width-vs-depth guard that interrupts repeated same-family monopolization and forces challenger maturation.",
        "- Added uncertainty-triggered verify allocation on near-tie states (bounded steps).",
        "",
        "## Before/after summary on the same 20 cases",
        f"- Old correct: {old_correct}/20",
        f"- Improved correct: {new_correct}/20",
        f"- Repaired cases (wrong -> correct): {improved_n}",
        f"- Absent-from-tree: {summary['old_absent_from_tree']} -> {summary['improved_absent_from_tree']}",
        f"- Present-but-not-selected: {summary['old_present_not_selected']} -> {summary['improved_present_not_selected']}",
        f"- Repeated same-family expansions (total): {summary['old_repeated_same_family_total']} -> {summary['improved_repeated_same_family_total']}",
        "",
        "## Artifacts",
        f"- Output bundle: `{out_dir.relative_to(REPO_ROOT)}`",
        f"- Per-case table: `{(out_dir / 'per_case_before_after.csv').relative_to(REPO_ROOT)}`",
        "",
        "## Conclusion",
        "- This is a bounded controller change focused on search-allocation under fixed budget; conclusions are limited to this fresh 20-case slice.",
    ]
    report.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({
        "old_current_full_method_name": old_full,
        "improved_method_name": IMPROVED_METHOD,
        "improved_cases_out_of_20": improved_n,
        "output_bundle_path": str(out_dir.relative_to(REPO_ROOT)),
        "docs_report_path": str(report.relative_to(REPO_ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
