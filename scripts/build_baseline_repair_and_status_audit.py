#!/usr/bin/env python3
"""Emit normalized baseline status matrix (JSON + CSV) for paper-safe auditing."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _exists(rel: str) -> bool:
    return (REPO_ROOT / rel).is_file()


def _any_exists(rels: list[str]) -> bool:
    return any(_exists(r) for r in rels)


def _artifact_bundle_has_method(method: str) -> bool:
    """True if a committed comparison bundle mentions the method (conservative artifact signal)."""
    p = REPO_ROOT / "outputs/full_method_comparison_bundle/20260419T214335Z/aggregate_comparison_summary.json"
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    for r in data.get("aggregate_ranking", []) or []:
        if isinstance(r, dict) and str(r.get("method", "")) == method:
            return True
    return False


def _rows() -> list[dict[str, Any]]:
    """Conservative audited rows: intent is paper-safe; paths checked where applicable."""
    rows: list[dict[str, Any]] = []

    def row(
        baseline_id: str,
        display_name: str,
        *,
        status: str,
        control_equivalence: str,
        paper_safe_now: bool,
        repo_command_available: bool,
        artifact_backed_now: bool,
        official_resource_verified: bool,
        primary_commands: list[str],
        primary_paths: list[str],
        prior_overclaim_risk: str,
        safe_wording_now: str,
        notes: str,
    ) -> dict[str, Any]:
        cmd_ok = repo_command_available and (_any_exists(primary_commands) or not primary_commands)
        path_ok = _any_exists(primary_paths) if primary_paths else artifact_backed_now
        art_ok = artifact_backed_now and (path_ok or baseline_id.startswith("internal"))
        return {
            "baseline_id": baseline_id,
            "display_name": display_name,
            "status": status,
            "control_equivalence": control_equivalence,
            "paper_safe_now": paper_safe_now,
            "repo_command_available": bool(cmd_ok),
            "artifact_backed_now": bool(art_ok),
            "official_resource_verified": official_resource_verified,
            "primary_commands_checked": primary_commands,
            "primary_paths_checked": primary_paths,
            "prior_overclaim_risk": prior_overclaim_risk,
            "safe_wording_now": safe_wording_now,
            "notes": notes,
        }

    rows.append(
        row(
            "s1_mode_a",
            "s1 (MODE A: inference-only budget forcing)",
            status="adapter_based",
            control_equivalence="near_direct",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("configs/s1_budget_forcing_inference_only_v1.json"),
            official_resource_verified=False,
            primary_commands=["scripts/run_s1_budget_forcing_baseline.py"],
            primary_paths=[
                "configs/s1_budget_forcing_inference_only_v1.json",
                "docs/s1_baseline_integration.md",
            ],
            prior_overclaim_risk="Calling MODE A a full s1 reproduction or identical to official s1 training stack.",
            safe_wording_now="MODE A is an inference-only budget-forcing adapter on this repo's substrate; near-direct, not official s1 training.",
            notes="MODE B uses verify_s1_mode_b_import.py when importing official CSV packages.",
        )
    )
    rows.append(
        row(
            "s1_mode_b",
            "s1 (MODE B: official/full import)",
            status="import_validated",
            control_equivalence="adjacent",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("scripts/verify_s1_mode_b_import.py"),
            official_resource_verified=False,
            primary_commands=["scripts/verify_s1_mode_b_import.py", "scripts/run_s1_baseline_comparison_bundle.py"],
            primary_paths=["configs/s1_full_or_official_adapter_v1.json", "docs/s1_baseline_integration.md"],
            prior_overclaim_risk="Treating MODE B as apples-to-apples with unchanged-base frontier controllers.",
            safe_wording_now="MODE B is separately labeled import reporting; not control-equivalent to MODE A comparisons.",
            notes="Requires user-supplied official package; validator enforces contract.",
        )
    )
    rows.append(
        row(
            "tale_mode_a",
            "TALE (MODE A: prompt/token budgeting adapter)",
            status="adapter_based",
            control_equivalence="near_direct",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("configs/tale_prompt_budgeting_v1.json"),
            official_resource_verified=False,
            primary_commands=["scripts/run_tale_baseline.py"],
            primary_paths=["configs/tale_prompt_budgeting_v1.json", "docs/tale_baseline_integration.md"],
            prior_overclaim_risk="Equating per-instance token budgeting with frontier branch allocation control.",
            safe_wording_now="Adjacent near-direct budget neighbor; explicit non-equivalence to stop-vs-act frontier control.",
            notes="MODE B: verify_tale_mode_b_import.py + tale_official_adapter_v1.json.",
        )
    )
    rows.append(
        row(
            "tale_mode_b",
            "TALE (MODE B: official/full import)",
            status="import_validated",
            control_equivalence="adjacent",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("scripts/verify_tale_mode_b_import.py"),
            official_resource_verified=False,
            primary_commands=["scripts/verify_tale_mode_b_import.py"],
            primary_paths=["configs/tale_official_adapter_v1.json", "docs/tale_baseline_integration.md"],
            prior_overclaim_risk="Omitting TALE vs TALE-PT variant separation when citing MODE B.",
            safe_wording_now="Validator requires tale_variant fields; still not direct reproduction of full upstream training.",
            notes="Stabilized canonical output family: outputs/rest_mcts_adjacent_integration/<run_id>/.",
        )
    )
    rows.append(
        row(
            "l1_mode_a",
            "L1 (MODE A: LCPO-style inference adapter)",
            status="adapter_based",
            control_equivalence="near_direct",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("configs/l1_inference_adapter_v1.json"),
            official_resource_verified=False,
            primary_commands=["scripts/run_l1_baseline.py"],
            primary_paths=["configs/l1_inference_adapter_v1.json", "docs/l1_baseline_integration.md"],
            prior_overclaim_risk="Claiming MODE A reproduces L1 RL or official LCPO training dynamics.",
            safe_wording_now="Inference-only length conditioning on this substrate; matched-budget reporting only.",
            notes="MODE B: verify_l1_mode_b_import.py (parity with s1/TALE).",
        )
    )
    rows.append(
        row(
            "l1_mode_b",
            "L1 (MODE B: official/full import)",
            status="import_validated",
            control_equivalence="adjacent",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("scripts/verify_l1_mode_b_import.py"),
            official_resource_verified=False,
            primary_commands=["scripts/verify_l1_mode_b_import.py"],
            primary_paths=["configs/l1_official_full_adapter_v1.json", "docs/l1_baseline_integration.md"],
            prior_overclaim_risk="MODE B without imported official rows still described as complete L1.",
            safe_wording_now="Blocked or import-validated only when CSV+metadata pass strict checks.",
            notes="Added verify_l1_mode_b_import.py in baseline repair pass for parity.",
        )
    )
    rows.append(
        row(
            "best_route_microsoft",
            "BEST-Route (Microsoft)",
            status="import_validated",
            control_equivalence="adjacent",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("scripts/verify_best_route_import.py"),
            official_resource_verified=False,
            primary_commands=["scripts/verify_best_route_import.py"],
            primary_paths=["docs/best_route_integration.md", "external/best_route_microsoft/README.md"],
            prior_overclaim_risk="Routing baseline described as direct branch-allocation comparator.",
            safe_wording_now="Import-validated adjacent neighbor only; routing action space ≠ frontier expand/verify.",
            notes="",
        )
    )
    rows.append(
        row(
            "when_solve_when_verify",
            "When To Solve, When To Verify",
            status="import_validated",
            control_equivalence="adjacent",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("scripts/verify_when_solve_when_verify_import.py"),
            official_resource_verified=False,
            primary_commands=["scripts/verify_when_solve_when_verify_import.py"],
            primary_paths=["docs/when_solve_when_verify_integration.md", "external/when_solve_when_verify/README.md"],
            prior_overclaim_risk="SC-vs-GenRM slice presented as full paper reproduction.",
            safe_wording_now="Strict import validation for adjacent SC-vs-GenRM budget comparisons only.",
            notes="",
        )
    )
    rows.append(
        row(
            "rest_mcts",
            "ReST-MCTS*",
            status="import_validated",
            control_equivalence="adjacent",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_exists("scripts/verify_rest_mcts_import.py"),
            official_resource_verified=False,
            primary_commands=["scripts/verify_rest_mcts_import.py", "scripts/run_rest_mcts_adjacent_integration.py"],
            primary_paths=["docs/rest_mcts_integration.md", "external/rest_mcts/README.md"],
            prior_overclaim_risk="Upstream training + self-training loop implied as runnable in-repo.",
            safe_wording_now="Contract-bound adjacent lane with verified import + official layout checks; no full ReST-MCTS training reproduction claim.",
            notes="",
        )
    )
    rows.append(
        row(
            "qstar_deliberative_planning",
            "Q* (deliberative planning)",
            status="discuss_only",
            control_equivalence="direct",
            paper_safe_now=True,
            repo_command_available=False,
            artifact_backed_now=_exists("external/qstar_deliberative_planning/README.md"),
            official_resource_verified=False,
            primary_commands=[],
            primary_paths=[
                "external/qstar_deliberative_planning/README.md",
                "docs/QSTAR_PROVENANCE_AND_INTEGRATION_PASS_20260422T013736Z.md",
                "docs/main_baselines.md",
            ],
            prior_overclaim_risk="Implying integrated runnable Q* baseline in this repository.",
            safe_wording_now="Essential direct-family conceptual neighbor; discuss-only with explicit provenance blockers.",
            notes="No verified official repo/artifacts wired for exact paper; do not upgrade without reproducible integration contract.",
        )
    )
    rows.append(
        row(
            "lets_verify_step_by_step",
            "Let's Verify Step by Step",
            status="discuss_only",
            control_equivalence="ingredient_only",
            paper_safe_now=True,
            repo_command_available=False,
            artifact_backed_now=_exists("external/lets_verify_step_by_step/README.md"),
            official_resource_verified=False,
            primary_commands=[],
            primary_paths=["external/lets_verify_step_by_step/README.md"],
            prior_overclaim_risk="PRM family oversold as runnable empirical baseline stack here.",
            safe_wording_now="Adjacent ingredient / completion-aware evidence family; not integrated as runnable stack.",
            notes="",
        )
    )
    rows.append(
        row(
            "rational_metareasoning_llm",
            "Rational Metareasoning for LLMs",
            status="discuss_only",
            control_equivalence="adjacent",
            paper_safe_now=True,
            repo_command_available=False,
            artifact_backed_now=_exists("external/rational_metareasoning_llm/README.md"),
            official_resource_verified=False,
            primary_commands=[],
            primary_paths=["external/rational_metareasoning_llm/README.md"],
            prior_overclaim_risk="Framing reference described as implemented metareasoning controller.",
            safe_wording_now="Conceptual stop-vs-continue/value-of-computation neighbor; discuss-only.",
            notes="",
        )
    )
    rows.append(
        row(
            "verifier_guided_search",
            "verifier_guided_search (internal)",
            status="runnable_direct",
            control_equivalence="adjacent",
            paper_safe_now=True,
            repo_command_available=True,
            artifact_backed_now=_artifact_bundle_has_method("verifier_guided_search"),
            official_resource_verified=False,
            primary_commands=["scripts/run_full_method_comparison_bundle.py"],
            primary_paths=["experiments/frontier_matrix_core.py", "experiments/controllers.py"],
            prior_overclaim_risk="Equating internal heuristic VGS with external PRM papers one-to-one.",
            safe_wording_now="Internal fixed-budget simulator baseline; cite as implementation neighbor, not PRM reproduction.",
            notes="Distinct from 'Let's Verify Step by Step' paper baseline row.",
        )
    )
    return rows


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / f"outputs/baseline_repair_and_status_audit_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _rows()
    meta = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "taxonomy": {
            "status": [
                "runnable_direct",
                "runnable_adjacent",
                "adapter_based",
                "import_validated",
                "discuss_only",
                "blocked",
                "broken_needs_repair",
            ],
            "control_equivalence": ["direct", "near_direct", "adjacent", "ingredient_only"],
        },
        "legacy_mapping_note": (
            "Registry field `integration` / `completeness_class` may still use older tokens "
            "(`mode_a_complete_mode_b_partial`, `runnable_adjacent`). "
            "Map: mode_a runnable paths → adapter_based; strict-import neighbors → import_validated; "
            "MODE B partial → import_validated or blocked depending on assets."
        ),
    }
    (out_dir / "baseline_status_matrix.json").write_text(
        json.dumps({"meta": meta, "baselines": rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    flat_keys = list(rows[0].keys()) if rows else []
    with (out_dir / "baseline_status_matrix.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=flat_keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = dict(r)
            out["primary_commands_checked"] = "|".join(out.get("primary_commands_checked") or [])
            out["primary_paths_checked"] = "|".join(out.get("primary_paths_checked") or [])
            w.writerow(out)
    print(out_dir)


if __name__ == "__main__":
    main()
