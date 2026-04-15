#!/usr/bin/env python3
"""Generate conservative status artifacts for compute_optimal_tts integration."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate compute_optimal_tts blocker/status report")
    p.add_argument(
        "--provenance-json",
        default="outputs/external_baseline_completeness/compute_optimal_tts_provenance_check.json",
    )
    p.add_argument(
        "--status-json",
        default="outputs/external_baseline_completeness/compute_optimal_tts_status.json",
    )
    p.add_argument(
        "--status-md",
        default="outputs/external_baseline_completeness/compute_optimal_tts_status.md",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(timezone.utc).isoformat()

    provenance_path = REPO_ROOT / args.provenance_json
    provenance: dict[str, Any] = {}
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

    linked = provenance.get("linked_repo", {}) if isinstance(provenance, dict) else {}
    head_commit = linked.get("head_commit")

    status = {
        "generated_utc": now,
        "baseline_key": "compute_optimal_tts",
        "status": "blocked",
        "status_taxonomy": [
            "runnable_direct",
            "runnable_adjacent",
            "mode_a_only",
            "mode_b_partial",
            "link_only",
            "discuss_only",
            "blocked",
        ],
        "provenance": {
            "target_paper": {
                "title": "Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning",
                "venue": "ICLR 2025",
                "url": "https://openreview.net/forum?id=4FWAwZtd2n",
            },
            "linked_repo": {
                "url": "https://github.com/RyanLiu112/compute-optimal-tts",
                "observed_head_commit": head_commit,
                "paper_repo_match_strength": "weak",
                "official_for_target_paper": "unverified",
                "reason": "Linked repo self-identifies around arXiv:2502.06703; target paper in this repo is OpenReview 4FWAwZtd2n.",
            },
        },
        "fair_adapter_feasible_now": False,
        "main_blockers": [
            "Paper-repo identity for target ICLR 2025 paper is not verified as official.",
            "Upstream linked repo depends on heavy multi-GPU serving and PRM stack (vLLM + Ray + FastChat + model serving scripts).",
            "No fair apples-to-apples adapter protocol is yet defined for this repo's frontier/action substrate.",
        ],
        "manuscript_use_now": {
            "recommended": "discussion_only_not_empirical",
            "safe_claim": "Conceptual adjacent baseline for compute-optimal allocation framing; not runnable in this repo yet.",
        },
        "next_exact_step": "Pin an author-verified official code release (or explicit author confirmation), then implement a minimal import-only adapter protocol on shared prompts and matched cost accounting before any empirical claim.",
    }

    out_json = REPO_ROOT / args.status_json
    out_md = REPO_ROOT / args.status_md
    out_json.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(status, indent=2), encoding="utf-8")

    lines = [
        "# compute_optimal_tts status",
        "",
        f"- Generated (UTC): `{now}`",
        "- Baseline: `compute_optimal_tts`",
        f"- Status: `{status['status']}`",
        "",
        "## Why this status",
        "- Target paper is ICLR 2025 OpenReview `4FWAwZtd2n` (Snell et al.).",
        "- Linked repo in registry is `RyanLiu112/compute-optimal-tts`, which self-identifies with arXiv `2502.06703`.",
        "- This means official target paper-repo identity is not verified; comparability must remain conservative.",
        "",
        "## Provenance strength",
        "- `paper_repo_match_strength`: **weak**",
        f"- observed linked-repo commit (if locally cloned): `{head_commit}`",
        "",
        "## Fairness / runnability decision",
        "- A fair in-repo adapter is **not** treated as feasible now under manuscript-safe standards.",
        "- Main blockers:",
    ]
    for b in status["main_blockers"]:
        lines.append(f"  - {b}")

    lines.extend(
        [
            "",
            "## Manuscript guidance",
            "- Use now as discussion/positioning baseline only; do not claim runnable empirical integration.",
            "",
            "## Exact next strengthening step",
            f"- {status['next_exact_step']}",
        ]
    )

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
