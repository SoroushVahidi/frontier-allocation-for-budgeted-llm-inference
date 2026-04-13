#!/usr/bin/env python3
"""Write external baseline integration report (JSON + Markdown)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Structured audit rows: user priority order1–8, then legacy four summarized in JSON appendix.
ROWS: list[dict[str, str | bool]] = [
    {
        "baseline_name": "compute_optimal_tts",
        "paper_title": "Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Parameters for Reasoning (Snell et al., ICLR 2025)",
        "paper_link": "https://openreview.net/forum?id=4FWAwZtd2n",
        "official_code_link": "https://github.com/RyanLiu112/compute-optimal-tts",
        "license_status": "MIT on RyanLiu112 repo (GitHub API); Snell author code not verified here",
        "could_add_to_repository": "PARTIAL",
        "integration_status": "LINK_ONLY",
        "what_was_added": "external/compute_optimal_tts/README.md; registry entry; explicit non-overclaim note",
        "what_is_still_missing": "Confirmed author-official repo for Snell et al.; RyanLiu112 repo README titles a different paper—treat as related MIT implementation, not verified author release; wrapper/adapter in this repo.",
        "recommended_for_main_paper_now": True,
        "reason": "Central reference for compute-optimal test-time scaling; cite Snell et al.; clone related repo only with correct attribution.",
    },
    {
        "baseline_name": "when_solve_when_verify",
        "paper_title": "When To Solve, When To Verify: Compute-Optimal Problem Solving and Generative Verification for LLM Reasoning",
        "paper_link": "https://arxiv.org/abs/2504.01005",
        "official_code_link": "https://github.com/nishadsinghi/sc-genrm-scaling",
        "license_status": "Apache-2.0 (GitHub API metadata)",
        "could_add_to_repository": "YES",
        "integration_status": "LINK_ONLY",
        "what_was_added": "external/when_solve_when_verify/README.md; registry entry",
        "what_is_still_missing": "No adapter; heavy upstream deps (vLLM / LLM Monkeys stack per upstream).",
        "recommended_for_main_paper_now": True,
        "reason": "Direct solve-vs-verify budget trade-off; arXiv links code explicitly.",
    },
    {
        "baseline_name": "cascade_routing",
        "paper_title": "A Unified Approach to Routing and Cascading for LLMs",
        "paper_link": "https://proceedings.mlr.press/v267/dekoninck25a.html",
        "official_code_link": "https://github.com/eth-sri/cascade-routing",
        "license_status": "Apache-2.0 (GitHub API metadata)",
        "could_add_to_repository": "YES",
        "integration_status": "LINK_ONLY",
        "what_was_added": "external/cascade_routing/README.md; registry entry",
        "what_is_still_missing": "No unified runner with this repo’s pilots; compare in separate environment.",
        "recommended_for_main_paper_now": True,
        "reason": "Strong routing/cascading baseline for heterogeneous models under cost constraints.",
    },
    {
        "baseline_name": "mob_majority_of_bests",
        "paper_title": "Majority of the Bests: Improving Best-of-N via Bootstrapping",
        "paper_link": "https://openreview.net/forum?id=ZVtHNM3Dd2",
        "official_code_link": "https://github.com/arakhsha/mob",
        "license_status": "MIT (repo); paper on OpenReview CC BY-NC-SA 4.0",
        "could_add_to_repository": "PARTIAL",
        "integration_status": "LINK_ONLY",
        "what_was_added": "external/mob_majority_of_bests/README.md; registry entry; license duality noted",
        "what_is_still_missing": "Confirm camera-ready / venue page code URL if it differs from arakhsha/mob.",
        "recommended_for_main_paper_now": True,
        "reason": "Best-of-N family competitor for test-time selection under imperfect rewards.",
    },
    {
        "baseline_name": "mcts_llm_community",
        "paper_title": "(Community repo) MCTS + LLM — not a single canonical paper binding",
        "paper_link": "https://github.com/NumberChiffre/mcts-llm",
        "official_code_link": "https://github.com/NumberChiffre/mcts-llm",
        "license_status": "MIT (GitHub API metadata)",
        "could_add_to_repository": "PARTIAL",
        "integration_status": "LINK_ONLY",
        "what_was_added": "external/mcts_llm_community/README.md; optional registry entry",
        "what_is_still_missing": "Official paper linkage; use only with correct citations to primary MCTS+LLM literature.",
        "recommended_for_main_paper_now": False,
        "reason": "Use cautiously; engineering reference more than a named paper baseline.",
    },
    {
        "baseline_name": "llm_tree_search_waterhorse",
        "paper_title": "AlphaZero-like Tree-Search for LLMs (see upstream repo citation)",
        "paper_link": "https://github.com/waterhorse1/LLM_Tree_Search",
        "official_code_link": "https://github.com/waterhorse1/LLM_Tree_Search",
        "license_status": "Unclear / not declared in GitHub API at verification time",
        "could_add_to_repository": "NO",
        "integration_status": "DISCUSS_ONLY",
        "what_was_added": "external/llm_tree_search_waterhorse/README.md; registry marked discuss_only",
        "what_is_still_missing": "Explicit OSS license file for safe redistribution or submodule policy.",
        "recommended_for_main_paper_now": False,
        "reason": "License ambiguity blocks conservative integration.",
    },
    {
        "baseline_name": "best_route_microsoft",
        "paper_title": "BEST-Route (Microsoft; see upstream README for full title)",
        "paper_link": "https://github.com/microsoft/best-route-llm",
        "official_code_link": "https://github.com/microsoft/best-route-llm",
        "license_status": "MIT (GitHub API); re-verify LICENSE file on default branch",
        "could_add_to_repository": "YES",
        "integration_status": "LINK_ONLY",
        "what_was_added": "external/best_route_microsoft/README.md; registry entry",
        "what_is_still_missing": "Adapter; confirm default branch and LICENSE path in clone.",
        "recommended_for_main_paper_now": True,
        "reason": "Microsoft OSS routing baseline; relevant to frontier/model routing story.",
    },
    {
        "baseline_name": "openr",
        "paper_title": "OpenReasoner / OpenR (see upstream)",
        "paper_link": "https://github.com/openreasoner/openr",
        "official_code_link": "https://github.com/openreasoner/openr",
        "license_status": "MIT (GitHub API metadata)",
        "could_add_to_repository": "YES",
        "integration_status": "LINK_ONLY",
        "what_was_added": "external/openr/README.md; registry entry",
        "what_is_still_missing": "Narrow experiment integration; large stack.",
        "recommended_for_main_paper_now": False,
        "reason": "Useful ecosystem reference; optional depending on evaluation scope.",
    },
]

LEGACY: list[dict[str, str | bool]] = [
    {
        "baseline_name": "rest_mcts",
        "paper_title": "ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search",
        "paper_link": "https://arxiv.org/abs/2406.03816",
        "official_code_link": "https://github.com/THUDM/ReST-MCTS",
        "license_status": "Unclear in repo metadata (pre-existing audit)",
        "could_add_to_repository": "PARTIAL",
        "integration_status": "LINK_ONLY",
        "what_was_added": "(pre-existing) external/rest_mcts/README.md",
        "what_is_still_missing": "Clear license for submodule import",
        "recommended_for_main_paper_now": True,
        "reason": "Already tracked PRM-guided search neighbor.",
    },
    {
        "baseline_name": "tree_plv",
        "paper_title": "Advancing Process Verification for Large Language Models via Tree-Based Preference Learning",
        "paper_link": "https://arxiv.org/abs/2407.00390",
        "official_code_link": "Not verified (ACL attachment / unclear GitHub)",
        "license_status": "Unknown",
        "could_add_to_repository": "NO",
        "integration_status": "DISCUSS_ONLY",
        "what_was_added": "(pre-existing) external/tree_plv/README.md",
        "what_is_still_missing": "Official public git + license",
        "recommended_for_main_paper_now": True,
        "reason": "Cite as related process-verification work; code path unclear.",
    },
    {
        "baseline_name": "pgts",
        "paper_title": "Policy Guided Tree Search for Enhanced LLM Reasoning",
        "paper_link": "https://arxiv.org/abs/2502.06813",
        "official_code_link": "Not confirmed",
        "license_status": "Unknown",
        "could_add_to_repository": "NO",
        "integration_status": "DISCUSS_ONLY",
        "what_was_added": "(pre-existing) external/pgts/README.md",
        "what_is_still_missing": "Official code + license",
        "recommended_for_main_paper_now": True,
        "reason": "Policy-guided search neighbor for discussion/comparison.",
    },
    {
        "baseline_name": "scaling_automated_process_verifiers",
        "paper_title": "Scaling Automated Process Verifiers for LLM Reasoning",
        "paper_link": "https://arxiv.org/abs/2410.08146",
        "official_code_link": "Not confirmed",
        "license_status": "Unknown",
        "could_add_to_repository": "NO",
        "integration_status": "DISCUSS_ONLY",
        "what_was_added": "(pre-existing) external/scaling_automated_process_verifiers/README.md",
        "what_is_still_missing": "Official code + license",
        "recommended_for_main_paper_now": True,
        "reason": "Verifier scaling reference for framing.",
    },
]


def main() -> None:
    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).isoformat()
    report = {
        "created_utc": created,
        "policy": "Link-only external baselines unless license and official status are clear; no vendored code.",
        "priority_candidates": ROWS,
        "legacy_tracked_baselines": LEGACY,
    }
    json_path = out_dir / "external_baseline_integration_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# External baseline integration report",
        "",
        f"- Generated (UTC): `{created}`",
        "",
        "## Priority candidates (new paper track)",
        "",
        "| Baseline | Code | License | Status | Paper-ready |",
        "|---|---|---|---|---|",
    ]
    for r in ROWS:
        lines.append(
            f"| {r['baseline_name']} | [link]({r['official_code_link']}) | {r['license_status']} | "
            f"{r['integration_status']} | {r['recommended_for_main_paper_now']} |"
        )
    lines.extend(["", "### Detail", ""])
    for r in ROWS:
        lines.extend(
            [
                f"#### {r['baseline_name']}",
                f"- **Paper:** {r['paper_title']}",
                f"- **Link:** {r['paper_link']}",
                f"- **Code:** {r['official_code_link']}",
                f"- **could_add_to_repository:** {r['could_add_to_repository']}",
                f"- **integration_status:** {r['integration_status']}",
                f"- **Added:** {r['what_was_added']}",
                f"- **Missing:** {r['what_is_still_missing']}",
                f"- **Reason:** {r['reason']}",
                "",
            ]
        )
    lines.extend(["## Legacy tracked baselines (original four)", ""])
    for r in LEGACY:
        lines.append(f"- **{r['baseline_name']}**: {r['integration_status']} — {r['official_code_link']}")

    md_path = out_dir / "external_baseline_integration_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(str(json_path))
    print(str(md_path))


if __name__ == "__main__":
    main()
