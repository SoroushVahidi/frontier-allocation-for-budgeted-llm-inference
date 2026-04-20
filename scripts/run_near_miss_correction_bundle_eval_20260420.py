#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import random
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

OLD_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1"
NEW_METHOD = "broad_diversity_aggregation_strong_v1_anti_collapse_near_miss_correction_gate_v1"


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


def _find_latest(glob_pat: str) -> Path:
    xs = sorted(REPO_ROOT.glob(glob_pat))
    if not xs:
        raise FileNotFoundError(glob_pat)
    return xs[-1]


def _find_question(dataset: str, example_id: str) -> str:
    for seed in [11, 23, 37, 59, 71, 83, 97, 109]:
        for ex in load_pilot_examples(dataset, 40, seed):
            if ex.example_id == example_id:
                return ex.question
    raise ValueError(f"question not found for {dataset}/{example_id}")


def _run_case(method: str, c: CaseSpec, question: str) -> dict[str, Any]:
    run_seed = _stable_seed("near_miss_eval", method, c.dataset, c.example_id, c.budget)
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
    pred = _norm(str(res.prediction) if res.prediction is not None else None)
    gold = _norm(c.gold_answer)
    final_nodes = []
    for b in gen.registry.values():
        if b.is_pruned:
            continue
        final_nodes.append(
            {
                "branch_id": b.branch_id,
                "pred": _norm(str(b.predicted_answer) if b.predicted_answer is not None else None),
                "is_done": bool(b.is_done),
            }
        )
    gold_node_ids = [n["branch_id"] for n in final_nodes if n.get("pred") == gold and n.get("is_done")]
    return {
        "prediction_norm": pred,
        "is_correct": bool(res.is_correct),
        "gold_present_in_tree": bool(gold_node_ids),
        "gold_node_ids": gold_node_ids,
        "metadata": res.metadata or {},
    }


def _label(run: dict[str, Any]) -> str:
    if run["is_correct"]:
        return "correct"
    if not run["gold_present_in_tree"]:
        return "correct answer absent from tree"
    return "correct answer present but not selected"


def _read_cases() -> tuple[list[CaseSpec], list[CaseSpec], dict[str, str]]:
    targeted_dir = _find_latest("outputs/targeted_failure_bundle_*/")
    targeted_rows = json.loads((targeted_dir / "per_case.json").read_text(encoding="utf-8"))
    targeted = [
        CaseSpec(dataset=str(r["dataset"]), example_id=str(r["example_id"]), budget=int(r["budget"]), gold_answer=str(r["gold_answer"]))
        for r in targeted_rows
    ]

    imp_dir = _find_latest("outputs/twenty_exact_current_full_improvement_eval_*/")
    broad_rows = json.loads((imp_dir / "per_case_before_after.json").read_text(encoding="utf-8"))
    broad = [
        CaseSpec(dataset=str(r["dataset"]), example_id=str(r["example_id"]), budget=int(r["budget"]), gold_answer=str(r["gold_answer"]))
        for r in broad_rows
    ]

    refs = {
        "targeted_bundle_dir": str(targeted_dir.relative_to(REPO_ROOT)),
        "improvement_eval_dir": str(imp_dir.relative_to(REPO_ROOT)),
        "fresh_loss_surface_doc": str(_find_latest("docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_*.md").relative_to(REPO_ROOT)),
        "twenty_case_improvement_report": str(_find_latest("docs/TWENTY_CASE_CURRENT_FULL_IMPROVEMENT_REPORT_*.md").relative_to(REPO_ROOT)),
        "targeted_bundle_report": str(_find_latest("docs/TARGETED_FAILURE_BUNDLE_REPORT_*.md").relative_to(REPO_ROOT)),
    }
    return targeted, broad, refs


def _evaluate_slice(cases: list[CaseSpec]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in cases:
        q = _find_question(c.dataset, c.example_id)
        old_run = _run_case(OLD_METHOD, c, q)
        new_run = _run_case(NEW_METHOD, c, q)
        old_md = old_run.get("metadata") or {}
        new_md = new_run.get("metadata") or {}
        out.append(
            {
                "dataset": c.dataset,
                "example_id": c.example_id,
                "budget": c.budget,
                "gold_answer": c.gold_answer,
                "old_correct": bool(old_run["is_correct"]),
                "new_correct": bool(new_run["is_correct"]),
                "old_label": _label(old_run),
                "new_label": _label(new_run),
                "old_gold_present_in_tree": bool(old_run["gold_present_in_tree"]),
                "new_gold_present_in_tree": bool(new_run["gold_present_in_tree"]),
                "old_actions": int(len(old_md.get("action_trace") or [])),
                "new_actions": int(len(new_md.get("action_trace") or [])),
                "old_expansions": int(old_md.get("expand_action_count", 0)),
                "new_expansions": int(new_md.get("expand_action_count", 0)),
                "old_verifications": int(sum(1 for a in (old_md.get("action_trace") or []) if str(a.get("action")) == "verify")),
                "new_verifications": int(sum(1 for a in (new_md.get("action_trace") or []) if str(a.get("action")) == "verify")),
                "delta_actions": int(len(new_md.get("action_trace") or [])) - int(len(old_md.get("action_trace") or [])),
                "delta_expansions": int(new_md.get("expand_action_count", 0)) - int(old_md.get("expand_action_count", 0)),
                "delta_verifications": int(sum(1 for a in (new_md.get("action_trace") or []) if str(a.get("action")) == "verify"))
                - int(sum(1 for a in (old_md.get("action_trace") or []) if str(a.get("action")) == "verify")),
                "new_near_miss_correction_activation_count": int(new_md.get("near_miss_correction_activation_count", 0)),
                "new_near_miss_correction_forced_expand_count": int(new_md.get("near_miss_correction_forced_expand_count", 0)),
                "improved_case": (not bool(old_run["is_correct"])) and bool(new_run["is_correct"]),
                "worsened_case": bool(old_run["is_correct"]) and (not bool(new_run["is_correct"])),
            }
        )
    return sorted(out, key=lambda r: (r["dataset"], r["example_id"]))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    targeted_cases, broad_cases, refs = _read_cases()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / f"near_miss_correction_eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    targeted_rows = _evaluate_slice(targeted_cases)
    broad_rows = _evaluate_slice(broad_cases)

    (out_dir / "targeted_7_before_after.json").write_text(json.dumps(targeted_rows, indent=2), encoding="utf-8")
    (out_dir / "broad_20_before_after.json").write_text(json.dumps(broad_rows, indent=2), encoding="utf-8")
    _write_csv(out_dir / "targeted_7_before_after.csv", targeted_rows)
    _write_csv(out_dir / "broad_20_before_after.csv", broad_rows)

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "n_cases": len(rows),
            "old_correct": int(sum(1 for r in rows if r["old_correct"])),
            "new_correct": int(sum(1 for r in rows if r["new_correct"])),
            "improved_cases": int(sum(1 for r in rows if r["improved_case"])),
            "worsened_cases": int(sum(1 for r in rows if r["worsened_case"])),
            "old_absent_from_tree": int(sum(1 for r in rows if r["old_label"] == "correct answer absent from tree")),
            "new_absent_from_tree": int(sum(1 for r in rows if r["new_label"] == "correct answer absent from tree")),
            "old_present_not_selected": int(sum(1 for r in rows if r["old_label"] == "correct answer present but not selected")),
            "new_present_not_selected": int(sum(1 for r in rows if r["new_label"] == "correct answer present but not selected")),
            "gold_entered_tree_newly": int(sum(1 for r in rows if (not r["old_gold_present_in_tree"]) and r["new_gold_present_in_tree"])),
            "mean_new_near_miss_activation_count": float(
                sum(float(r["new_near_miss_correction_activation_count"]) for r in rows) / max(1, len(rows))
            ),
            "total_new_near_miss_activation_count": int(sum(int(r["new_near_miss_correction_activation_count"]) for r in rows)),
            "total_new_near_miss_forced_expand_count": int(sum(int(r["new_near_miss_correction_forced_expand_count"]) for r in rows)),
        }

    targeted_summary = summarize(targeted_rows)
    broad_summary = summarize(broad_rows)
    improved_targeted_ids = [f"{r['dataset']}::{r['example_id']}" for r in targeted_rows if r["improved_case"]]
    worsened_targeted_ids = [f"{r['dataset']}::{r['example_id']}" for r in targeted_rows if r["worsened_case"]]
    improved_broad_ids = [f"{r['dataset']}::{r['example_id']}" for r in broad_rows if r["improved_case"]]
    worsened_broad_ids = [f"{r['dataset']}::{r['example_id']}" for r in broad_rows if r["worsened_case"]]

    summary = {
        "created_at_utc": ts,
        "old_method": OLD_METHOD,
        "new_method": NEW_METHOD,
        "source_references": refs,
        "targeted_7_summary": targeted_summary,
        "broad_20_summary": broad_summary,
        "improved_targeted_case_ids": improved_targeted_ids,
        "worsened_targeted_case_ids": worsened_targeted_ids,
        "improved_broad_case_ids": improved_broad_ids,
        "worsened_broad_case_ids": worsened_broad_ids,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "selection_manifest.json").write_text(
        json.dumps(
            {
                "created_at_utc": ts,
                "inputs": refs,
                "old_method": OLD_METHOD,
                "new_method": NEW_METHOD,
                "outputs": [
                    str((out_dir / "targeted_7_before_after.json").relative_to(REPO_ROOT)),
                    str((out_dir / "targeted_7_before_after.csv").relative_to(REPO_ROOT)),
                    str((out_dir / "broad_20_before_after.json").relative_to(REPO_ROOT)),
                    str((out_dir / "broad_20_before_after.csv").relative_to(REPO_ROOT)),
                    str((out_dir / "summary.json").relative_to(REPO_ROOT)),
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    docs_path = REPO_ROOT / "docs" / f"NEAR_MISS_CORRECTION_EVAL_REPORT_{ts}.md"
    lines = [
        f"# Near-miss correction bounded controller report ({ts})",
        "",
        "## Mechanism implemented",
        f"- Old method: `{OLD_METHOD}`",
        f"- New method: `{NEW_METHOD}`",
        "- Added a bounded near-miss correction gate that activates only when the selected branch is done, top-support is not concentrated, repeated same-family expansion is already high, and nearby numeric done answers exist in the same family.",
        "- On activation, the controller spawns a same-family corrective refinement child and forces one bounded local correction expansion.",
        "- Added traceable metadata counters for activations and forced correction expands.",
        "",
        "## Canonical materials read",
        f"- Fresh exact current-full-vs-best bundle doc: `{refs['fresh_loss_surface_doc']}`",
        f"- Twenty-case improvement report: `{refs['twenty_case_improvement_report']}`",
        f"- Targeted failure-bundle report: `{refs['targeted_bundle_report']}`",
        f"- Targeted machine-readable bundle: `{refs['targeted_bundle_dir']}`",
        "",
        "## Primary results: targeted 7-case near-miss absent-from-tree bundle",
        f"- Old correct: {targeted_summary['old_correct']}/{targeted_summary['n_cases']}",
        f"- New correct: {targeted_summary['new_correct']}/{targeted_summary['n_cases']}",
        f"- Improved cases: {targeted_summary['improved_cases']}",
        f"- Worsened cases: {targeted_summary['worsened_cases']}",
        f"- Gold answer newly entered tree: {targeted_summary['gold_entered_tree_newly']}",
        f"- Correction activations (total): {targeted_summary['total_new_near_miss_activation_count']}",
        "",
        "## Secondary transfer results: broader fresh 20-case surface",
        f"- Old correct: {broad_summary['old_correct']}/{broad_summary['n_cases']}",
        f"- New correct: {broad_summary['new_correct']}/{broad_summary['n_cases']}",
        f"- Improved cases: {broad_summary['improved_cases']}",
        f"- Worsened cases: {broad_summary['worsened_cases']}",
        f"- Gold answer newly entered tree: {broad_summary['gold_entered_tree_newly']}",
        f"- Correction activations (total): {broad_summary['total_new_near_miss_activation_count']}",
        "",
        "## Case movement",
        f"- Targeted improved: {improved_targeted_ids if improved_targeted_ids else 'none'}",
        f"- Targeted worsened: {worsened_targeted_ids if worsened_targeted_ids else 'none'}",
        f"- Broad improved: {improved_broad_ids if improved_broad_ids else 'none'}",
        f"- Broad worsened: {worsened_broad_ids if worsened_broad_ids else 'none'}",
        "",
        "## Conclusion",
        "- This direction is only better than width/depth challenger guard if it improves the targeted 7-case slice without unacceptable broad regression; otherwise it should be treated as a partial/failed attempt and revised.",
        f"- Artifacts: `{out_dir.relative_to(REPO_ROOT)}`",
    ]
    docs_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "old_current_full_method_name": OLD_METHOD,
                "new_improved_method_name": NEW_METHOD,
                "improved_cases_on_targeted_7": targeted_summary["improved_cases"],
                "improved_cases_on_broader_20": broad_summary["improved_cases"],
                "docs_report_path": str(docs_path.relative_to(REPO_ROOT)),
                "output_bundle_path": str(out_dir.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
