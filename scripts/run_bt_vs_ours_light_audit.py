#!/usr/bin/env python3
"""Targeted light diagnostic: BT pairwise allocator vs canonical allocator.

If a runnable BT model artifact is available, this script can be extended to run a direct
comparison. In the current lightweight path, it first enforces honesty by checking for an
existing BT artifact path; if none is found, it writes explicit 'not runnable' outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return sum(float(r[key]) for r in rows) / len(rows)


def _discover_bt_artifact(explicit_path: str | None) -> tuple[Path | None, str]:
    if explicit_path:
        p = (REPO_ROOT / explicit_path) if not Path(explicit_path).is_absolute() else Path(explicit_path)
        if p.exists():
            return p, "explicit_arg"
        return None, f"explicit path not found: {p}"

    candidates = [
        REPO_ROOT / "outputs/new_paper/bt_pairwise_branch_scorer",
        REPO_ROOT / "outputs",
    ]
    for root in candidates:
        if not root.exists():
            continue
        for p in root.rglob("adaptive_learned_branch_score_v7_bt.json"):
            return p, "auto_discovery"
    return None, "no existing BT model artifact found in current branch/output"


def main() -> None:
    p = argparse.ArgumentParser(description="BT-vs-ours light targeted audit")
    p.add_argument("--bundle-dir", required=True)
    p.add_argument("--bt-model-path", default=None)
    args = p.parse_args()

    bundle_dir = REPO_ROOT / args.bundle_dir
    bundle_dir.mkdir(parents=True, exist_ok=True)

    bt_model_path, source = _discover_bt_artifact(args.bt_model_path)

    disagreement_rows = _load_rows(bundle_dir / "branch_ranking_disagreement.csv")
    ours_rows = disagreement_rows
    ours_near = [r for r in ours_rows if int(float(r.get("is_near_tie_by_score", 0))) == 1]
    ours_non = [r for r in ours_rows if int(float(r.get("is_near_tie_by_score", 0))) == 0]

    ours_oracle_mismatch = _rate(ours_rows, "is_mismatch_vs_oracle") if ours_rows else None
    ours_near_mismatch = _rate(ours_near, "is_mismatch_vs_oracle") if ours_near else None
    ours_non_mismatch = _rate(ours_non, "is_mismatch_vs_oracle") if ours_non else None

    runnable = bt_model_path is not None

    summary_rows = [
        {
            "status": "not_runnable" if not runnable else "runnable",
            "reason": source if not runnable else "existing BT artifact found",
            "bundle_dir": str(bundle_dir),
            "bt_model_path": str(bt_model_path) if bt_model_path else "",
            "ours_oracle_mismatch_rate": "" if ours_oracle_mismatch is None else f"{ours_oracle_mismatch:.6f}",
            "bt_oracle_mismatch_rate": "",
            "ours_final_quality_proxy": "" if not ours_rows else f"{_rate(ours_rows, 'final_is_correct'):.6f}",
            "bt_final_quality_proxy": "",
            "can_answer_bt_vs_ours": "no" if not runnable else "yes",
        }
    ]
    _write_csv(bundle_dir / "bt_vs_ours_summary.csv", summary_rows)

    near_tie_rows = [
        {
            "method": "ours_adaptive_min_expand_1",
            "slice": "near_tie_score_gap_le_0.03",
            "n": len(ours_near),
            "oracle_mismatch_rate": "" if ours_near_mismatch is None else f"{ours_near_mismatch:.6f}",
            "final_quality_proxy": "" if not ours_near else f"{_rate(ours_near, 'final_is_correct'):.6f}",
            "notes": "from existing branch_ranking_disagreement.csv",
        },
        {
            "method": "ours_adaptive_min_expand_1",
            "slice": "non_tie_score_gap_gt_0.03",
            "n": len(ours_non),
            "oracle_mismatch_rate": "" if ours_non_mismatch is None else f"{ours_non_mismatch:.6f}",
            "final_quality_proxy": "" if not ours_non else f"{_rate(ours_non, 'final_is_correct'):.6f}",
            "notes": "from existing branch_ranking_disagreement.csv",
        },
        {
            "method": "adaptive_bt_pairwise",
            "slice": "near_tie_score_gap_le_0.03",
            "n": 0,
            "oracle_mismatch_rate": "",
            "final_quality_proxy": "",
            "notes": "BT run unavailable in current branch/output (no artifact path).",
        },
    ]
    _write_csv(bundle_dir / "bt_vs_ours_near_tie_analysis.csv", near_tie_rows)

    audit_lines = [
        "# BT vs Ours targeted audit (light diagnostic)",
        "",
        "**Label:** light diagnostic comparison, not a final paper result.",
        "",
        "## Runnable status",
        f"- BT artifact discovery result: `{source}`.",
    ]

    if not runnable:
        audit_lines += [
            "- **Direct BT-vs-ours comparison was not runnable in the current branch/output.**",
            "- Per instruction, no BT results were fabricated and no heavy BT training path was launched.",
            "",
            "## What is missing",
            "- A runnable BT pairwise model artifact path (e.g., `adaptive_learned_branch_score_v7_bt.json`) tied to this light setup.",
            "- Without that artifact, we cannot answer whether BT reduces branch-choice mismatch or near-tie errors in this exact bundle.",
            "",
            "## What we can still report from current data",
            f"- Ours mismatch rate (oracle proxy): {('n/a' if ours_oracle_mismatch is None else f'{ours_oracle_mismatch:.3f}')}",
            f"- Ours near-tie mismatch rate: {('n/a' if ours_near_mismatch is None else f'{ours_near_mismatch:.3f}')}",
            f"- Ours non-tie mismatch rate: {('n/a' if ours_non_mismatch is None else f'{ours_non_mismatch:.3f}')}",
            "- BT side remains unresolved pending a real artifact path.",
        ]

    takeaways_lines = [
        "# BT vs Ours takeaways (light diagnostic)",
        "",
        "- **Does BT beat ours on branch-ranking in this bundle?** Cannot determine: BT was not runnable here due to missing artifact path.",
        "- **Is any gap concentrated in near-tie states?** Cannot determine for BT; only ours near-tie behavior is available.",
        "- **Should this change immediate priority before/after merge?** Yes: ensure a reproducible lightweight BT artifact path is part of the light audit pipeline, then rerun this exact targeted comparison before making branch-ranking priority shifts.",
    ]

    (bundle_dir / "bt_vs_ours_audit.md").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
    (bundle_dir / "bt_vs_ours_takeaways.md").write_text("\n".join(takeaways_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "runnable": runnable,
                "reason": source,
                "bundle_dir": str(bundle_dir),
                "bt_model_path": str(bt_model_path) if bt_model_path else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
