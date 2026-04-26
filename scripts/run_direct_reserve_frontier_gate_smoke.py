#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import random
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import SimulatedBranchGenerator
from experiments.frontier_matrix_core import build_frontier_strategies


@dataclass
class _Example:
    example_id: str
    question: str
    gold: str


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _examples() -> list[_Example]:
    return [
        _Example("smoke_1", "What is 12 + 13?", "25"),
        _Example("smoke_2", "A bag has 4 red and 6 blue balls. How many total?", "10"),
        _Example("smoke_3", "If 3x = 21, what is x?", "7"),
        _Example("smoke_4", "What is 15% of 200?", "30"),
        _Example("smoke_5", "A train moves 60 miles in 2 hours. Speed?", "30"),
        _Example("smoke_6", "Compute 9*8 - 10.", "62"),
        _Example("smoke_7", "If you buy 3 items at $4 each, total cost?", "12"),
        _Example("smoke_8", "Half of 144 is?", "72"),
    ]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            w.writeheader()
            w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline smoke test for direct_reserve_frontier_gate_v1.")
    ap.add_argument("--timestamp", default=_now_ts())
    args = ap.parse_args()

    out_dir = REPO_ROOT / "outputs" / f"direct_reserve_frontier_gate_smoke_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = build_frontier_strategies(
        generator_factory=lambda: SimulatedBranchGenerator(
            rng=random.Random(211), max_depth=7, finish_prob_base=0.16, answer_noise=0.12
        ),
        budget=6,
        adaptive_min_expand_grid=[1],
        rng=random.Random(223),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )

    strict_name = "strict_f3_anti_collapse_default_v1"
    methods = ["external_l1_max", strict_name, "direct_reserve_frontier_gate_v1"]
    for m in methods:
        if m not in specs:
            raise RuntimeError(f"Required method not available in strategy set: {m}")

    rows: list[dict[str, object]] = []
    gate_overrides = reserve_used = agreements = helpful = harmful = 0
    n = 0
    acc: dict[str, int] = {m: 0 for m in methods}

    for ex in _examples():
        n += 1
        per_method: dict[str, object] = {}
        for m in methods:
            res = specs[m].run(ex.question, ex.gold)
            per_method[m] = res
            if bool(res.is_correct):
                acc[m] += 1
        gate_res = per_method["direct_reserve_frontier_gate_v1"]
        strict_res = per_method[strict_name]
        ext_res = per_method["external_l1_max"]

        gate_meta = dict(gate_res.metadata or {})
        override = bool(gate_meta.get("frontier_override_triggered", False))
        used = bool(gate_meta.get("reserve_used", True))
        agree = bool(gate_meta.get("direct_frontier_agree", False))
        gate_overrides += int(override)
        reserve_used += int(used)
        agreements += int(agree)

        if override:
            reserve_ans = str(gate_meta.get("direct_reserve_answer") or "")
            final_ans = str(gate_meta.get("final_answer") or "")
            reserve_ok = reserve_ans.strip() == ex.gold.strip()
            final_ok = final_ans.strip() == ex.gold.strip()
            if (not reserve_ok) and final_ok:
                helpful += 1
            if reserve_ok and (not final_ok):
                harmful += 1

        rows.append(
            {
                "example_id": ex.example_id,
                "gold_answer": ex.gold,
                "external_l1_max_prediction": getattr(ext_res, "prediction", None),
                "external_l1_max_correct": bool(getattr(ext_res, "is_correct", False)),
                "strict_f3_prediction": getattr(strict_res, "prediction", None),
                "strict_f3_correct": bool(getattr(strict_res, "is_correct", False)),
                "direct_reserve_frontier_gate_prediction": getattr(gate_res, "prediction", None),
                "direct_reserve_frontier_gate_correct": bool(getattr(gate_res, "is_correct", False)),
                "reserve_used": used,
                "frontier_override_triggered": override,
                "direct_frontier_agree": agree,
                "override_reason": gate_meta.get("override_reason", ""),
                "override_margin": gate_meta.get("override_margin", 0.0),
            }
        )

    _write_csv(out_dir / "per_example_results.csv", rows)
    summary = [
        {
            "n_examples": n,
            "reserve_used_count": reserve_used,
            "frontier_override_count": gate_overrides,
            "direct_frontier_agreement_count": agreements,
            "external_l1_max_accuracy": acc["external_l1_max"] / max(1, n),
            "strict_f3_accuracy": acc[strict_name] / max(1, n),
            "direct_reserve_frontier_gate_v1_accuracy": acc["direct_reserve_frontier_gate_v1"] / max(1, n),
            "helpful_override_count": helpful,
            "harmful_override_count": harmful,
            "status": "diagnostic_only",
        }
    ]
    _write_csv(out_dir / "summary.csv", summary)

    status = (
        "# Direct Reserve Frontier Gate Smoke Status\n\n"
        f"- Output directory: `{out_dir.relative_to(REPO_ROOT)}`\n"
        f"- Number of examples: {n}\n"
        f"- Reserve used count: {reserve_used}\n"
        f"- Frontier override count: {gate_overrides}\n"
        f"- Direct-frontier agreement count: {agreements}\n"
        f"- `external_l1_max` accuracy: {acc['external_l1_max'] / max(1, n):.3f}\n"
        f"- `strict_f3` accuracy: {acc[strict_name] / max(1, n):.3f}\n"
        f"- `direct_reserve_frontier_gate_v1` accuracy: {acc['direct_reserve_frontier_gate_v1'] / max(1, n):.3f}\n"
        f"- Helpful override count: {helpful}\n"
        f"- Harmful override count: {harmful}\n"
        "- Recommendation: diagnostic-only until broader paired evidence supports promotion.\n"
    )
    (REPO_ROOT / "docs" / "DIRECT_RESERVE_FRONTIER_GATE_SMOKE_STATUS.md").write_text(status, encoding="utf-8")
    print(status)


if __name__ == "__main__":
    main()
