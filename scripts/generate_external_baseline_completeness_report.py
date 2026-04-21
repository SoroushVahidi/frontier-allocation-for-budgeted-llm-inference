#!/usr/bin/env python3
"""Generate external baseline completeness artifacts (markdown + JSON + CSV)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

CLASSIFICATION_ROWS: list[dict[str, str]] = [
    {
        "baseline_key": "s1_simple_test_time_scaling",
        "display_name": "s1",
        "category": "mode_b_partial",
        "status_v1_mode_a": "adapter_based",
        "status_v1_mode_b": "import_validated",
        "control_v1_mode_a": "near_direct",
        "control_v1_mode_b": "adjacent",
        "directness": "direct",
        "usable_now": "yes_mode_a",
        "mode_a": "runnable",
        "mode_b": "blocked_without_official_results_import",
        "blocker": "MODE B requires externally-produced official/full outputs; this repo does not reproduce s1 post-training stack.",
        "next_requirement": "Provide exported official/full s1 metrics file and wire official.results_path.",
    },
    {
        "baseline_key": "tale_token_budget_aware_reasoning",
        "display_name": "TALE",
        "category": "mode_b_partial",
        "status_v1_mode_a": "adapter_based",
        "status_v1_mode_b": "import_validated",
        "control_v1_mode_a": "near_direct",
        "control_v1_mode_b": "adjacent",
        "directness": "adjacent",
        "usable_now": "yes_mode_a",
        "mode_a": "runnable",
        "mode_b": "blocked_without_official_results_import",
        "blocker": "MODE B requires externally-produced TALE official/full outputs (e.g., TALE-PT stack).",
        "next_requirement": "Provide official/full TALE exported metrics and set official.results_path.",
    },
    {
        "baseline_key": "l1_length_control_rl",
        "display_name": "L1",
        "category": "mode_b_partial",
        "status_v1_mode_a": "adapter_based",
        "status_v1_mode_b": "import_validated",
        "control_v1_mode_a": "near_direct",
        "control_v1_mode_b": "adjacent",
        "directness": "direct",
        "usable_now": "yes_mode_a",
        "mode_a": "runnable",
        "mode_b": "blocked_without_official_results_import",
        "blocker": "MODE B requires externally-produced full L1 outputs; RL training path is not reproduced in this repo.",
        "next_requirement": "Provide exported official/full L1 metrics and set official.results_path.",
    },
    {
        "baseline_key": "best_route_microsoft",
        "display_name": "BEST-Route",
        "category": "import_validated",
        "status_v1_mode_a": "import_validated",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "yes_verified_import",
        "mode_a": "adjacent_import_validator",
        "mode_b": "not_applicable",
        "blocker": "Not blocked for adjacent use; direct apples-to-apples comparability remains out-of-scope and must not be claimed.",
        "next_requirement": "If pursuing direct comparability, define and justify control-space alignment beyond adjacent import.",
    },
    {
        "baseline_key": "compute_optimal_tts",
        "display_name": "Compute-optimal TTS",
        "category": "blocked",
        "status_v1_mode_a": "blocked",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "no",
        "mode_a": "not_applicable",
        "mode_b": "not_applicable",
        "blocker": "Paper↔repo official mapping for target OpenReview 4FWAwZtd2n is unverified and no fair matched adapter protocol exists yet.",
        "next_requirement": "Confirm author-official code mapping for target paper, then add import-only matched-cost adapter protocol.",
    },
    {
        "baseline_key": "when_solve_when_verify",
        "display_name": "When To Solve, When To Verify",
        "category": "runnable_adjacent",
        "status_v1_mode_a": "import_validated",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "yes_verified_import",
        "mode_a": "adjacent_import_validator",
        "mode_b": "not_applicable",
        "blocker": "Not blocked for adjacent use; direct in-repo full-stack reproduction and control-equivalence claims remain out-of-scope.",
        "next_requirement": "If pursuing direct comparability, justify and implement control-space alignment beyond adjacent import.",
    },
    {
        "baseline_key": "cascade_routing",
        "display_name": "Cascade routing",
        "category": "runnable_adjacent",
        "status_v1_mode_a": "import_validated",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "yes_verified_import",
        "mode_a": "adjacent_import_validator",
        "mode_b": "not_applicable",
        "blocker": "Not blocked for adjacent use; direct full-stack reproduction and control-equivalence claims remain out-of-scope.",
        "next_requirement": "If pursuing direct comparability, justify and implement control-space alignment beyond adjacent import.",
    },
    {
        "baseline_key": "mob_majority_of_bests",
        "display_name": "MoB",
        "category": "runnable_adjacent",
        "status_v1_mode_a": "import_validated",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "yes_verified_import",
        "mode_a": "adjacent_import_validator",
        "mode_b": "not_applicable",
        "blocker": "Not blocked for adjacent use; direct full-stack reproduction and control-equivalence claims remain out-of-scope.",
        "next_requirement": "If pursuing direct comparability, justify and implement control-space alignment beyond adjacent import.",
    },
    {
        "baseline_key": "rest_mcts",
        "display_name": "ReST-MCTS*",
        "category": "runnable_adjacent",
        "status_v1_mode_a": "import_validated",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "yes_verified_import",
        "mode_a": "adjacent_import_validator",
        "mode_b": "not_applicable",
        "blocker": "Not blocked for adjacent use; direct full-stack reproduction and control-equivalence claims remain out-of-scope.",
        "next_requirement": "If pursuing direct comparability, justify and implement control-space alignment beyond adjacent import.",
    },
    {
        "baseline_key": "mcts_llm_community",
        "display_name": "MCTS-LLM (community)",
        "category": "discuss_only",
        "status_v1_mode_a": "discuss_only",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "no",
        "mode_a": "not_applicable",
        "mode_b": "not_applicable",
        "blocker": "Optional/community reference; no canonical in-repo adapter.",
        "next_requirement": "Only integrate if clear canonical paper mapping is fixed.",
    },
    {
        "baseline_key": "openr",
        "display_name": "OpenR",
        "category": "runnable_adjacent",
        "status_v1_mode_a": "import_validated",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "yes_verified_import",
        "mode_a": "adjacent_import_validator",
        "mode_b": "not_applicable",
        "blocker": "Not blocked for adjacent use; direct full-stack reproduction and control-equivalence claims remain out-of-scope.",
        "next_requirement": "If pursuing direct comparability, justify and implement control-space alignment beyond adjacent import.",
    },
    {
        "baseline_key": "tree_plv",
        "display_name": "Tree-PLV",
        "category": "discuss_only",
        "status_v1_mode_a": "discuss_only",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "no",
        "mode_a": "not_applicable",
        "mode_b": "not_applicable",
        "blocker": "Official code/repro path not confirmed for this repo's integration policy.",
        "next_requirement": "Confirm official code + licensing before adapter work.",
    },
    {
        "baseline_key": "pgts",
        "display_name": "PGTS",
        "category": "discuss_only",
        "status_v1_mode_a": "discuss_only",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "no",
        "mode_a": "not_applicable",
        "mode_b": "not_applicable",
        "blocker": "No verified official code path for reproducible integration.",
        "next_requirement": "Confirm authoritative code artifact and license.",
    },
    {
        "baseline_key": "scaling_automated_process_verifiers",
        "display_name": "Scaling Automated Process Verifiers",
        "category": "discuss_only",
        "status_v1_mode_a": "discuss_only",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "no",
        "mode_a": "not_applicable",
        "mode_b": "not_applicable",
        "blocker": "No verified official repo integration path under current policy.",
        "next_requirement": "Verify official implementation and licensing.",
    },
    {
        "baseline_key": "llm_tree_search_waterhorse",
        "display_name": "LLM Tree Search (Waterhorse)",
        "category": "discuss_only",
        "status_v1_mode_a": "discuss_only",
        "status_v1_mode_b": "not_applicable",
        "control_v1_mode_a": "adjacent",
        "control_v1_mode_b": "not_applicable",
        "directness": "adjacent",
        "usable_now": "no",
        "mode_a": "not_applicable",
        "mode_b": "not_applicable",
        "blocker": "License uncertainty and no approved in-repo adapter.",
        "next_requirement": "Resolve license then revisit integration.",
    },
]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    docs_dir = REPO_ROOT / "docs"
    out_dir = REPO_ROOT / "outputs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated_utc = datetime.now(timezone.utc).isoformat()

    summary = {
        "generated_utc": generated_utc,
        "taxonomy_v1_status": [
            "runnable_direct",
            "runnable_adjacent",
            "adapter_based",
            "import_validated",
            "discuss_only",
            "blocked",
            "broken_needs_repair",
        ],
        "taxonomy_v1_control_equivalence": [
            "direct",
            "near_direct",
            "adjacent",
            "ingredient_only",
        ],
        "taxonomy_legacy_note": (
            "Historical per-baseline JSON under outputs/external_baseline_completeness/*_status.json "
            "may still list status `runnable_adjacent` for verified-import-only neighbors; canonical v1 "
            "status for those paths is `import_validated` (see docs/BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md)."
        ),
        "baseline_status_matrix_v1": (
            "outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json"
        ),
        "taxonomy": [
            "runnable_direct",
            "runnable_adjacent",
            "adapter_based",
            "import_validated",
            "discuss_only",
            "blocked",
            "broken_needs_repair",
        ],
        "rows": CLASSIFICATION_ROWS,
        "usable_now_in_comparisons": [
            "s1_simple_test_time_scaling (MODE A)",
            "tale_token_budget_aware_reasoning (MODE A)",
            "l1_length_control_rl (MODE A)",
            "best_route_microsoft (adjacent import validator)",
            "when_solve_when_verify (adjacent import validator)",
            "cascade_routing (adjacent import validator)",
            "mob_majority_of_bests (adjacent import validator)",
            "rest_mcts (adjacent import validator)",
            "openr (adjacent import validator)",
        ],
        "single_next_priority": "mcts_llm_community",
        "single_next_priority_rationale": (
            "mcts_llm_community is now v1 `discuss_only` (optional community link; no adapter). "
            "Next integration effort should pick a discuss_only row with a clear canonical paper mapping "
            "(for example Tree-PLV or PGTS) only after official code + license confirmation."
        ),
    }

    json_path = out_dir / "external_baseline_completeness_summary.json"
    csv_path = out_dir / "external_baseline_completeness_summary.csv"
    md_path = docs_dir / "external_baseline_completeness_report.md"

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_csv(csv_path, CLASSIFICATION_ROWS)

    lines = [
        "# External baseline completeness report",
        "",
        f"- Generated (UTC): `{generated_utc}`",
        "- Scope: external baseline completeness for reviewer-defensible reporting.",
        "",
        "## Canonical taxonomy (v1, paper-safe)",
        "",
        "Machine-readable matrix (normalized fields): `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json`.",
        "",
        "### `status` (v1)",
        "- `runnable_direct`",
        "- `runnable_adjacent`",
        "- `adapter_based`",
        "- `import_validated`",
        "- `discuss_only`",
        "- `blocked`",
        "- `broken_needs_repair`",
        "",
        "### `control_equivalence` (v1)",
        "- `direct`",
        "- `near_direct`",
        "- `adjacent`",
        "- `ingredient_only`",
        "",
        "### Legacy tokens (still appear in some CSV/JSON rows)",
        "- `category` column values like `mode_b_partial` and `runnable_adjacent` are **legacy row labels**; prefer `status_v1_mode_a` / `status_v1_mode_b` for paper-facing claims.",
        "- Per-baseline `outputs/external_baseline_completeness/*_status.json` may still say `runnable_adjacent` where v1 says `import_validated` (verified import protocol only).",
        "",
        "## Baseline status table",
        "",
        "| Baseline | legacy category | status_v1 (MODE A / primary) | status_v1 (MODE B) | control_v1 (A) | control_v1 (B) | Direct vs adjacent | Usable now | MODE A | MODE B |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in CLASSIFICATION_ROWS:
        lines.append(
            "| "
            + f"{row['display_name']} (`{row['baseline_key']}`) | {row['category']} | "
            + f"{row['status_v1_mode_a']} | {row['status_v1_mode_b']} | "
            + f"{row['control_v1_mode_a']} | {row['control_v1_mode_b']} | "
            + f"{row['directness']} | {row['usable_now']} | {row['mode_a']} | {row['mode_b']} |"
        )

    lines.extend(
        [
            "",
            "## Currently usable in comparisons",
            "- s1 MODE A (`inference_only`) through `scripts/run_s1_budget_forcing_baseline.py`.",
            "- TALE MODE A (`prompt_budgeting_inference_only`) through `scripts/run_tale_baseline.py`.",
            "- L1 MODE A (`inference_only_adapter`) through `scripts/run_l1_baseline.py`.",
            "- BEST-Route adjacent import path through `scripts/verify_best_route_import.py` (strict validator; adjacent-only claims).",
            "- when_solve_when_verify adjacent import path through `scripts/verify_when_solve_when_verify_import.py` (strict validator; adjacent-only claims).",
            "- Cascade Routing adjacent import path through `scripts/verify_cascade_routing_import.py` (strict validator; adjacent-only claims).",
            "- MoB adjacent import path through `scripts/verify_mob_import.py` (strict validator; adjacent-only claims).",
            "- ReST-MCTS adjacent import path through `scripts/verify_rest_mcts_import.py` (strict validator; adjacent-only claims).",
            "- OpenR adjacent import path through `scripts/verify_openr_import.py` (strict validator; adjacent-only claims).",
            "",
            "## Partially usable",
            "- s1 / TALE / L1 MODE B paths are **import-validated** official/full reporting only: blocked at run time unless externally produced outputs are supplied via `official.results_path`, then checked by `verify_*_mode_b_import.py` (including `scripts/verify_l1_mode_b_import.py` for L1).",
            "",
            "## BEST-Route integration decision in this pass",
            "- Canonical v1 status: `import_validated` (verified import protocol; legacy JSON may still say `runnable_adjacent`).",
            "- Interpretation: usable for adjacent comparisons only; not a direct control-space-equivalent reproduction.",
            "- Guardrail: imported outputs must pass `scripts/verify_best_route_import.py` and be labeled `adjacent_only`.",
            "",
            "## when_solve_when_verify integration decision in this pass",
            "- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).",
            "- Interpretation: usable for adjacent comparisons only; not a direct control-space-equivalent reproduction.",
            "- Guardrail: imported outputs must pass `scripts/verify_when_solve_when_verify_import.py` and be labeled `adjacent_only`.",
            "",
            "## Cascade Routing integration decision in this pass",
            "- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).",
            "- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.",
            "- Guardrail: imported outputs must pass `scripts/verify_cascade_routing_import.py` and be labeled `adjacent_only`.",
            "",
            "## MoB integration decision in this pass",
            "- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).",
            "- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.",
            "- Guardrail: imported outputs must pass `scripts/verify_mob_import.py` and be labeled `adjacent_only`.",
            "",
            "## ReST-MCTS integration decision in this pass",
            "- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).",
            "- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.",
            "- Guardrail: imported outputs must pass `scripts/verify_rest_mcts_import.py` and be labeled `adjacent_only`.",
            "",
            "## OpenR integration decision in this pass",
            "- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).",
            "- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.",
            "- Guardrail: imported outputs must pass `scripts/verify_openr_import.py` and be labeled `adjacent_only`.",
            "",
            "## Single next highest-priority baseline after this pass",
            "- `mcts_llm_community` (v1 `discuss_only`; optional community reference — confirm paper mapping before any adapter work).",
            "",
            "## Machine-readable companion artifacts",
            "- `outputs/external_baseline_completeness_summary.json`",
            "- `outputs/external_baseline_completeness_summary.csv`",
        ]
    )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(md_path))
    print(str(json_path))
    print(str(csv_path))


if __name__ == "__main__":
    main()
