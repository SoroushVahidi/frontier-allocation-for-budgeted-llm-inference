#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


CONFIG_PATH = REPO_ROOT / "configs/low_marginal_gain_family_cooldown_bounded_eval_20260420_v1.json"


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
    joined = "||".join(str(x) for x in parts)
    return int(hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8], 16)


def _norm(x: str | None) -> str | None:
    return normalize_answer_text(x).get("normalized_answer") if x is not None else None


def _parse_cases(surface_doc: Path) -> list[CaseSpec]:
    txt = surface_doc.read_text(encoding="utf-8")
    blocks = re.split(r"\n## Case \d+: ", txt)[1:]
    out: list[CaseSpec] = []
    for blk in blocks:
        m_head = re.search(r"`([^`]+) / ([^`]+)`", blk)
        m_budget = re.search(r"our budget/actions/expansions/verifications: `\{'budget':\s*(\d+)", blk)
        m_gold = re.search(r"gold answer: `([^`]+)`", blk)
        if not (m_head and m_budget and m_gold):
            continue
        out.append(
            CaseSpec(
                dataset=m_head.group(1),
                example_id=m_head.group(2),
                budget=int(m_budget.group(1)),
                gold_answer=m_gold.group(1),
            )
        )
    return out


def _find_question(dataset: str, example_id: str, seed_order: list[int]) -> str:
    for seed in seed_order:
        for ex in load_pilot_examples(dataset, 40, seed):
            if ex.example_id == example_id:
                return ex.question
    raise ValueError(f"question not found for {dataset}/{example_id}")


def _run_case(
    *,
    method: str,
    case: CaseSpec,
    question: str,
    simulator_cfg: dict[str, Any],
    seed_ns: str,
) -> dict[str, Any]:
    run_seed = _stable_seed(seed_ns, method, case.dataset, case.example_id, case.budget)
    rng = random.Random(run_seed)
    gen = ObservedGenerator(
        SimulatedBranchGenerator(
            rng=rng,
            max_depth=int(simulator_cfg.get("max_depth", 7)),
            finish_prob_base=float(simulator_cfg.get("finish_prob_base", 0.16)),
            answer_noise=float(simulator_cfg.get("answer_noise", 0.12)),
        )
    )
    specs = build_frontier_strategies(
        generator_factory=lambda: gen,
        budget=case.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    res = specs[method].run(question, case.gold_answer)
    metadata = res.metadata or {}
    pred = _norm(str(res.prediction) if res.prediction is not None else None)
    gold = _norm(case.gold_answer)
    final_nodes: list[dict[str, Any]] = []
    for b in gen.registry.values():
        if b.is_pruned:
            continue
        final_nodes.append(
            {
                "branch_id": b.branch_id,
                "prediction_norm": _norm(str(b.predicted_answer) if b.predicted_answer is not None else None),
            }
        )
    gold_node_ids = [n["branch_id"] for n in final_nodes if n["prediction_norm"] == gold]
    return {
        "method": method,
        "prediction": res.prediction,
        "prediction_norm": pred,
        "is_correct": bool(res.is_correct),
        "gold_present_in_tree": bool(gold_node_ids),
        "gold_node_ids": gold_node_ids,
        "metadata": metadata,
    }


def _failure_label(run: dict[str, Any]) -> str:
    if run["is_correct"]:
        return "correct"
    if not run["gold_present_in_tree"]:
        return "absent_from_tree"
    return "present_but_not_selected"


def _method_metrics(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    picked = [r for r in rows if r["method"] == method]
    n = len(picked)
    correct = sum(int(r["is_correct"]) for r in picked)
    absent = sum(1 for r in picked if _failure_label(r) == "absent_from_tree")
    present_not = sum(1 for r in picked if _failure_label(r) == "present_but_not_selected")
    return {
        "method": method,
        "n_examples": n,
        "accuracy": float(correct / max(1, n)),
        "correct_count": int(correct),
        "absent_from_tree_count": int(absent),
        "present_but_not_selected_count": int(present_not),
        "mean_repeated_same_family_expansion_rate": float(
            sum(float((r.get("metadata") or {}).get("repeated_same_family_expansion_rate", 0.0)) for r in picked) / max(1, n)
        ),
        "mean_actions": float(sum(len((r.get("metadata") or {}).get("action_trace") or []) for r in picked) / max(1, n)),
        "mean_expansions": float(sum(int((r.get("metadata") or {}).get("expand_action_count", 0)) for r in picked) / max(1, n)),
        "mean_verifications": float(
            sum(
                int(sum(1 for a in ((r.get("metadata") or {}).get("action_trace") or []) if str(a.get("action")) == "verify"))
                for r in picked
            )
            / max(1, n)
        ),
        "mean_low_marginal_gain_trigger_count": float(
            sum(float((r.get("metadata") or {}).get("low_marginal_gain_family_trigger_count", 0.0)) for r in picked) / max(1, n)
        ),
        "mean_low_marginal_gain_override_count": float(
            sum(float((r.get("metadata") or {}).get("low_marginal_gain_family_override_count", 0.0)) for r in picked) / max(1, n)
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded eval for low-marginal-gain same-family cooldown refinement")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    methods = cfg["methods"]
    surface_doc = REPO_ROOT / str(cfg["source_surface_doc"])
    seed_order = [int(x) for x in cfg["determinism"]["pilot_seed_search_order"]]
    seed_ns = str(cfg["determinism"]["seed_hash_namespace"])
    cases = _parse_cases(surface_doc)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) if args.output_dir else (REPO_ROOT / "outputs" / f"low_marginal_gain_family_cooldown_bounded_eval_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case: list[dict[str, Any]] = []
    for case in cases:
        q = _find_question(case.dataset, case.example_id, seed_order)
        baseline = _run_case(method=methods["baseline"], case=case, question=q, simulator_cfg=cfg["simulator"], seed_ns=seed_ns)
        soft = _run_case(method=methods["soft_low_marginal_gain_cooldown"], case=case, question=q, simulator_cfg=cfg["simulator"], seed_ns=seed_ns)
        hard = _run_case(method=methods["hard_block_ablation"], case=case, question=q, simulator_cfg=cfg["simulator"], seed_ns=seed_ns)
        per_case.append(
            {
                "dataset": case.dataset,
                "example_id": case.example_id,
                "budget": case.budget,
                "gold_answer": case.gold_answer,
                "runs": [baseline, soft, hard],
            }
        )

    flat_rows: list[dict[str, Any]] = []
    for row in per_case:
        for run in row["runs"]:
            flat_rows.append({"dataset": row["dataset"], "example_id": row["example_id"], **run})

    by_method = {
        "baseline": _method_metrics(flat_rows, methods["baseline"]),
        "soft": _method_metrics(flat_rows, methods["soft_low_marginal_gain_cooldown"]),
        "hard": _method_metrics(flat_rows, methods["hard_block_ablation"]),
    }
    ranking = sorted(
        [by_method["baseline"], by_method["soft"], by_method["hard"]],
        key=lambda x: (float(x["accuracy"]), -float(x["mean_actions"])),
        reverse=True,
    )

    improved_soft: list[dict[str, Any]] = []
    harmed_soft: list[dict[str, Any]] = []
    for row in per_case:
        by_name = {r["method"]: r for r in row["runs"]}
        base = by_name[methods["baseline"]]
        soft = by_name[methods["soft_low_marginal_gain_cooldown"]]
        if (not base["is_correct"]) and soft["is_correct"]:
            improved_soft.append(
                {
                    "dataset": row["dataset"],
                    "example_id": row["example_id"],
                    "baseline_failure": _failure_label(base),
                    "soft_control_trigger_count": int((soft.get("metadata") or {}).get("low_marginal_gain_family_trigger_count", 0)),
                }
            )
        if base["is_correct"] and (not soft["is_correct"]):
            harmed_soft.append(
                {
                    "dataset": row["dataset"],
                    "example_id": row["example_id"],
                    "soft_failure": _failure_label(soft),
                    "soft_block_count": int((soft.get("metadata") or {}).get("low_marginal_gain_family_block_count", 0)),
                    "soft_override_count": int((soft.get("metadata") or {}).get("low_marginal_gain_family_override_count", 0)),
                }
            )

    summary = {
        "config": cfg.get("name"),
        "source_surface_doc": str(cfg["source_surface_doc"]),
        "n_cases": len(per_case),
        "metrics_by_method": by_method,
        "ranking": [{"rank": i + 1, "method": r["method"], "accuracy": r["accuracy"]} for i, r in enumerate(ranking)],
        "improved_cases_soft_vs_baseline": improved_soft,
        "harmed_cases_soft_vs_baseline": harmed_soft,
        "soft_vs_baseline_delta": {
            "accuracy": float(by_method["soft"]["accuracy"] - by_method["baseline"]["accuracy"]),
            "absent_from_tree": int(by_method["soft"]["absent_from_tree_count"] - by_method["baseline"]["absent_from_tree_count"]),
            "present_but_not_selected": int(
                by_method["soft"]["present_but_not_selected_count"] - by_method["baseline"]["present_but_not_selected_count"]
            ),
            "mean_repeated_same_family_expansion_rate": float(
                by_method["soft"]["mean_repeated_same_family_expansion_rate"]
                - by_method["baseline"]["mean_repeated_same_family_expansion_rate"]
            ),
        },
    }

    (out_dir / "per_case_diagnostics.json").write_text(json.dumps(per_case, indent=2), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "script": "scripts/run_low_marginal_gain_family_cooldown_bounded_eval_20260420.py",
                "config": str(Path(args.config).relative_to(REPO_ROOT)),
                "output_dir": str(out_dir.relative_to(REPO_ROOT)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    report = REPO_ROOT / f"docs/LOW_MARGINAL_GAIN_FAMILY_COOLDOWN_BOUNDED_EVAL_{ts}.md"
    md = [
        f"# Low-marginal-gain family cooldown bounded eval ({ts})",
        "",
        "## Insertion point",
        "- Inserted inside `GlobalDiversityAggregationController._anti_collapse_priority_adjustments` as a conditional same-family control on the promoted repeat-expansion line.",
        "",
        "## Control definition",
        "- Name: `low_marginal_gain_family_cooldown` (soft default) plus optional `hard_block_ablation`.",
        "- Trigger: repeated same-family selection + recent family rolling marginal gain below threshold.",
        "- Rolling marginal gain: mean of recent expansion score deltas (`score_after - score_before`, clipped at 0) over a short window.",
        "- Answer-group-aware: threshold increases when many active siblings share the same answer group.",
        "- Override: if top-support is high and adjusted family priority still beats alternatives by override margin.",
        "",
        "## Parameters (soft)",
        "- window_size=3, min_threshold=0.015, consecutive_family_trigger=4",
        "- cooldown_steps=2, penalty_strength=0.14",
        "- override_top_support_min=0.74, override_margin=0.12",
        "",
        "## Comparison table",
        "| Method | Accuracy | Absent-from-tree | Present-not-selected | Mean repeat-same-family rate | Mean actions | Mean expansions | Mean verifications |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ["baseline", "soft", "hard"]:
        m = by_method[key]
        md.append(
            f"| `{m['method']}` | {m['accuracy']:.3f} | {m['absent_from_tree_count']} | {m['present_but_not_selected_count']} | "
            f"{m['mean_repeated_same_family_expansion_rate']:.3f} | {m['mean_actions']:.2f} | {m['mean_expansions']:.2f} | {m['mean_verifications']:.2f} |"
        )
    md.extend(
        [
            "",
            f"## Improved cases (soft vs baseline): {len(improved_soft)}",
            *[
                f"- `{r['dataset']} / {r['example_id']}` (baseline failure=`{r['baseline_failure']}`, soft_trigger_count={r['soft_control_trigger_count']})"
                for r in improved_soft[:10]
            ],
            "",
            f"## Harmed cases (soft vs baseline): {len(harmed_soft)}",
            *[
                f"- `{r['dataset']} / {r['example_id']}` (soft failure=`{r['soft_failure']}`, soft_block_count={r['soft_block_count']}, soft_override_count={r['soft_override_count']})"
                for r in harmed_soft[:10]
            ],
            "",
            "## Conclusion",
            (
                "- Keep if soft control reduces collapse proxies and absent-from-tree failures without a meaningful accuracy drop; "
                "otherwise tune threshold/cooldown and avoid hard-block default."
            ),
        ]
    )
    report.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output_dir": str(out_dir.relative_to(REPO_ROOT)),
                "summary_path": str((out_dir / "summary.json").relative_to(REPO_ROOT)),
                "report_path": str(report.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
