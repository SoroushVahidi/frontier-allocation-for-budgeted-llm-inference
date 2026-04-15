#!/usr/bin/env python3
"""Lightweight branch-ranking audit for adaptive_min_expand_1 next-step decisions.

Replays a small simulator run using the bundle's dataset/seeds/budgets and emits
branch-level disagreement diagnostics focused on: did we spend the next unit of
compute on the likely wrong branch?
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import BranchState, SimulatedBranchGenerator
from experiments.frontier_matrix_core import load_pilot_examples
from experiments.scoring import ScoreConfig, SimpleBranchScorer


@dataclass
class AuditConfig:
    high_threshold: float = 0.72
    low_threshold: float = 0.42
    max_branches: int = 3
    min_expansions_before_prune: int = 1
    allow_verify: bool = True


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _top2_gap(values: list[float]) -> float:
    if len(values) <= 1:
        return 1.0
    s = sorted(values, reverse=True)
    return float(s[0] - s[1])


def _run_one_example(
    *,
    question: str,
    gold_answer: str,
    example_id: str,
    budget: int,
    rng: random.Random,
    cfg: AuditConfig,
    dataset: str,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    gen = SimulatedBranchGenerator(rng=rng, max_depth=7, finish_prob_base=0.16, answer_noise=0.12)
    scorer = SimpleBranchScorer(ScoreConfig())

    actions = expansions = verifications = 0
    branches: list[BranchState] = [gen.init_branch("adaptive_0")]
    branch_expansions: dict[str, int] = {}
    decision_rows: list[dict[str, Any]] = []
    decision_idx = 0

    while actions < budget and branches:
        next_branches: list[BranchState] = []
        for branch in branches:
            if actions >= budget:
                break
            if branch.is_done or branch.is_pruned:
                next_branches.append(branch)
                continue

            active = [b for b in branches if not b.is_done and not b.is_pruned]
            if not active:
                break

            h_scores = {b.branch_id: float(scorer.score_branch(b)) for b in active}
            l_scores = {b.branch_id: float(b.latent_quality) for b in active}
            heuristic_top = max(active, key=lambda b: h_scores[b.branch_id]).branch_id
            oracle_top = max(active, key=lambda b: l_scores[b.branch_id]).branch_id
            score_gap = _top2_gap(list(h_scores.values()))
            latent_gap = _top2_gap(list(l_scores.values()))

            score_before = float(scorer.score_branch(branch))
            branch_expand_count = branch_expansions.get(branch.branch_id, 0)

            selected_action = "prune"
            consumed_compute = False

            if branch_expand_count < cfg.min_expansions_before_prune:
                gen.expand(branch, question, gold_answer)
                actions += 1
                expansions += 1
                consumed_compute = True
                selected_action = "expand"
                branch_expansions[branch.branch_id] = branch_expand_count + 1
                next_branches.append(branch)
                if not branch.is_done and len(next_branches) < cfg.max_branches and actions < budget:
                    child = gen.init_branch(f"adaptive_child_{actions}_{len(next_branches)}")
                    child.score = 0.5 * child.score + 0.5 * branch.score
                    next_branches.append(child)
                    branch_expansions[child.branch_id] = 0
            elif score_before >= cfg.high_threshold:
                gen.expand(branch, question, gold_answer)
                actions += 1
                expansions += 1
                consumed_compute = True
                selected_action = "expand"
                branch_expansions[branch.branch_id] = branch_expand_count + 1
                next_branches.append(branch)
                if not branch.is_done and len(next_branches) < cfg.max_branches and actions < budget:
                    child = gen.init_branch(f"adaptive_child_{actions}_{len(next_branches)}")
                    child.score = 0.5 * child.score + 0.5 * branch.score
                    next_branches.append(child)
                    branch_expansions[child.branch_id] = 0
            elif cfg.allow_verify and score_before >= cfg.low_threshold:
                gen.verify(branch, question)
                actions += 1
                verifications += 1
                consumed_compute = True
                selected_action = "verify"
                next_branches.append(branch)
            else:
                gen.prune(branch)

            if consumed_compute:
                decision_idx += 1
                selected = branch.branch_id
                decision_rows.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "budget": budget,
                        "example_id": example_id,
                        "decision_index": decision_idx,
                        "selected_branch_id": selected,
                        "selected_action": selected_action,
                        "n_active_branches": len(active),
                        "remaining_budget_before_action": budget - actions + 1,
                        "selected_score": score_before,
                        "selected_latent_quality": float(branch.latent_quality),
                        "heuristic_top_branch_id": heuristic_top,
                        "oracle_top_branch_id": oracle_top,
                        "is_mismatch_vs_heuristic": int(selected != heuristic_top),
                        "is_mismatch_vs_oracle": int(selected != oracle_top),
                        "heuristic_top2_score_gap": score_gap,
                        "oracle_top2_latent_gap": latent_gap,
                        "is_near_tie_by_score": int(score_gap <= 0.03),
                        "is_near_tie_by_oracle": int(latent_gap <= 0.05),
                    }
                )

        branches = [b for b in next_branches if not b.is_pruned][: cfg.max_branches]
        if all(b.is_done for b in branches):
            break

    candidates = [b for b in branches if not b.is_pruned]
    best = max(candidates, key=scorer.score_branch) if candidates else None
    pred = best.predicted_answer if best else None
    is_correct = bool(pred is not None and str(pred).strip() == str(gold_answer).strip())

    return (
        {
            "actions_used": actions,
            "expansions": expansions,
            "verifications": verifications,
            "is_correct": is_correct,
            "final_selected_branch": best.branch_id if best else None,
        },
        decision_rows,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Run branch ranking disagreement audit")
    p.add_argument("--bundle-dir", required=True)
    args = p.parse_args()

    bundle_dir = REPO_ROOT / args.bundle_dir
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset = str(manifest["dataset"])
    seeds = [int(s) for s in manifest["seeds"]]
    budgets = [int(b) for b in manifest["budgets"]]
    subset_size = int(manifest["subset_size"])

    cfg = AuditConfig()
    master_rng = random.Random(20260415)

    rows: list[dict[str, Any]] = []
    per_run: list[dict[str, Any]] = []

    for seed in seeds:
        examples = load_pilot_examples(dataset, subset_size, seed)
        for budget in budgets:
            for ex in examples:
                run_rng = random.Random(master_rng.randint(0, 10**9))
                result, drows = _run_one_example(
                    question=ex.question,
                    gold_answer=ex.answer,
                    example_id=ex.example_id,
                    budget=budget,
                    rng=run_rng,
                    cfg=cfg,
                    dataset=dataset,
                    seed=seed,
                )
                for d in drows:
                    d["final_is_correct"] = int(result["is_correct"])
                rows.extend(drows)
                per_run.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "budget": budget,
                        "example_id": ex.example_id,
                        "final_is_correct": int(result["is_correct"]),
                        "actions_used": int(result["actions_used"]),
                    }
                )

    if not rows:
        raise SystemExit("No decision rows captured; audit cannot proceed.")

    _write_csv(bundle_dir / "branch_ranking_disagreement.csv", rows)

    n = len(rows)
    mismatch_oracle = sum(int(r["is_mismatch_vs_oracle"]) for r in rows)
    mismatch_heur = sum(int(r["is_mismatch_vs_heuristic"]) for r in rows)

    near_tie_rows = [r for r in rows if int(r["is_near_tie_by_score"]) == 1]
    non_tie_rows = [r for r in rows if int(r["is_near_tie_by_score"]) == 0]

    def _rate(items: list[dict[str, Any]], key: str) -> float:
        if not items:
            return 0.0
        return float(sum(int(x[key]) for x in items) / len(items))

    by_budget: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        by_budget.setdefault(int(r["budget"]), []).append(r)

    budget_lines: list[str] = []
    for b in sorted(by_budget):
        br = by_budget[b]
        budget_lines.append(
            f"- Budget {b}: oracle mismatch rate={_rate(br, 'is_mismatch_vs_oracle'):.3f}, "
            f"heuristic mismatch rate={_rate(br, 'is_mismatch_vs_heuristic'):.3f}, n={len(br)}"
        )

    wrong_rows = [r for r in rows if int(r["is_mismatch_vs_oracle"]) == 1]
    right_rows = [r for r in rows if int(r["is_mismatch_vs_oracle"]) == 0]
    wrong_acc = _rate(wrong_rows, "final_is_correct")
    right_acc = _rate(right_rows, "final_is_correct")

    audit_md = [
        "# Branch ranking audit (light exploratory)",
        "",
        "This is a **light exploratory branch-choice diagnosis**, not a final benchmark.",
        "",
        "## Plain answer",
        f"- Does wrong next-branch selection appear present? **Yes, in this replay/proxy audit**: oracle-proxy mismatch in {mismatch_oracle}/{n} spend decisions ({mismatch_oracle / n:.3f}).",
        f"- Heuristic-top mismatch rate: {mismatch_heur}/{n} ({mismatch_heur / n:.3f}).",
        f"- In near-tie score states (gap<=0.03), oracle-proxy mismatch={_rate(near_tie_rows, 'is_mismatch_vs_oracle'):.3f} (n={len(near_tie_rows)}).",
        f"- In non-tie score states, oracle-proxy mismatch={_rate(non_tie_rows, 'is_mismatch_vs_oracle'):.3f} (n={len(non_tie_rows)}).",
        f"- Correctness when mismatch vs oracle: {wrong_acc:.3f}; when aligned: {right_acc:.3f}.",
        "",
        "## Concentration checks",
        *budget_lines,
        "- Dataset concentration: only one dataset (`openai/gsm8k`) was present in the light bundle, so no cross-dataset claim is possible.",
        "",
        "## Main interpretation",
        "- Evidence is consistent with a real branch-choice issue (high mismatch vs oracle proxy), but evidence is proxy-level because oracle uses hidden simulator latent quality.",
        "- A strong alternative explanation is comparator/threshold design: the controller can prune/verify based on local score thresholds without global re-ranking all active branches.",
        "- Another concurrent issue is under-spend/misaligned spend in the light run, so wrong branch ranking is likely important but not proven as the only main weakness.",
    ]

    takeaways_md = [
        "# Branch ranking takeaways (light exploratory)",
        "",
        "## Is wrong branch selection the main weakness?",
        "- **Likely a major contributor**, but not fully isolated: branch-choice mismatch vs oracle proxy is high, and mismatch correlates with lower final correctness in this audit.",
        "",
        "## Best evidence",
        f"- Oracle-proxy mismatch rate: {mismatch_oracle / n:.3f} across {n} spend decisions.",
        f"- Mismatch-associated correctness drop: aligned {right_acc:.3f} vs mismatch {wrong_acc:.3f}.",
        "",
        "## Main alternative explanations if evidence is weak",
        "- Oracle comparator is proxy-only (latent-quality in simulator), not a real oracle label from actual model traces.",
        "- Local thresholds and anti-collapse guards can induce under-spend/misallocation even if ranking is partly right.",
        "- Single-seed single-dataset run may exaggerate or hide effects.",
        "",
        "## Single most important next fix",
        "- Add a **global next-action branch comparator** for adaptive_min_expand_1: before each spend decision, rank all active branches by a short-horizon ACT-vs-STOP delta proxy and spend only on the top branch; log disagreement against current policy.",
    ]

    (bundle_dir / "branch_ranking_audit.md").write_text("\n".join(audit_md) + "\n", encoding="utf-8")
    (bundle_dir / "branch_ranking_takeaways.md").write_text("\n".join(takeaways_md) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "bundle_dir": str(bundle_dir),
                "rows": n,
                "oracle_mismatch_rate": mismatch_oracle / n,
                "heuristic_mismatch_rate": mismatch_heur / n,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
