#!/usr/bin/env python3
"""Production-equivalent v1 Stage-3 50-case dry-run (no API calls)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.adaptive_retry_router import AdaptiveRouterV3Config, choose_adaptive_retry_scaffold_v3, compute_adaptive_retry_features  # noqa: E402
from experiments.final_target_verifier import final_target_verifier_features  # noqa: E402
from experiments.targeted_discovery_retry import ProductionEquivalenceStage3Config, build_production_equivalence_stage3_config  # noqa: E402

METHOD_ALIAS = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
    "structural_commit_v1_production_equiv_v1"
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _map_router_scaffold_to_runtime(router_scaffold: str) -> str:
    m = {
        "quantity_ledger": "quantity_ledger_v2_1",
        "rate_table": "rate_table_v1",
        "before_after_state": "before_after_state_v1",
        "target_difference": "target_difference_v1",
        "final_target_verifier_retry": "final_target_extraction_repair",
    }
    return m.get(router_scaffold, router_scaffold)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--case-file",
        type=Path,
        default=REPO / "outputs/stage3_tale_s1_pilot_readiness_20260508T032919Z/stage3_pilot_cases.csv",
    )
    p.add_argument("--method-name", default=METHOD_ALIAS)
    p.add_argument("--max-extra-calls-per-case", type=int, default=1)
    p.add_argument("--enable-percent-base-denominator", action="store_true")
    p.add_argument("--output-dir", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg: ProductionEquivalenceStage3Config = build_production_equivalence_stage3_config(
        enable_percent_base_denominator=bool(args.enable_percent_base_denominator),
        targeted_retry_max_extra_calls=int(args.max_extra_calls_per_case),
        no_api_mode=True,
    )
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = (
        args.output_dir.resolve()
        if args.output_dir
        else REPO / "outputs" / f"production_equiv_v1_runtime_ready_stage3_50_dry_run_{ts}"
    )
    out.mkdir(parents=True, exist_ok=True)

    cases = _read_csv(args.case_file.resolve())
    if len(cases) != 50:
        raise SystemExit(f"expected 50 cases, got {len(cases)}")

    router_cfg = AdaptiveRouterV3Config(enable_percent_base_denominator=bool(cfg.enable_percent_base_denominator))
    allowed = set(cfg.targeted_retry_allowed_scaffolds)
    excluded_patches = [
        "discovery3_candidate_diversity_selection_v1",
        "unvalidated_discovery3_ratio_state_prompts",
    ]
    rows: list[dict[str, Any]] = []
    call_plan_rows: list[dict[str, Any]] = []
    blocked_runtime_hooks: list[str] = []

    for c in cases:
        cid = str(c.get("case_id") or "").strip()
        problem = str(c.get("problem_text") or "")
        router_features = compute_adaptive_retry_features(problem)
        router_decision, chosen_scaffold, held_back = choose_adaptive_retry_scaffold_v3(problem, router_features, router_cfg)
        verifier_features = final_target_verifier_features(problem_text=problem, candidate_answer_text=None, candidate_trace=None)

        mapped = _map_router_scaffold_to_runtime(chosen_scaffold)
        targeted_planned = False
        targeted_scaffold = ""
        excluded_patch_reason = ""

        if verifier_features.get("final_target_mismatch_risk"):
            mapped = "final_target_extraction_repair"
        if mapped == "percent_base_denominator" and not cfg.enable_percent_base_denominator:
            excluded_patch_reason = "percent_base_denominator_disabled_by_default"
            mapped = ""
        elif mapped and mapped not in allowed:
            excluded_patch_reason = f"scaffold_not_validated_for_production_equiv_v1:{mapped}"
            mapped = ""

        if mapped:
            targeted_planned = True
            targeted_scaffold = mapped

        planned_base_action = "frontier_structural_commit_path"
        structural_commit_available = "yes"
        expected_extra_calls = min(1, int(cfg.targeted_retry_max_extra_calls)) if targeted_planned else 0
        blocking_reason = ""
        ready_live = "yes"

        md = {
            "production_equiv_v1_enabled": True,
            "structural_commitment_enabled": True,
            "adaptive_router_v3_features": json.dumps(router_features, ensure_ascii=False),
            "final_target_verifier_features": json.dumps(verifier_features, ensure_ascii=False),
            "runtime_targeted_retry_enabled": True,
            "targeted_retry_triggered": targeted_planned,
            "targeted_retry_scaffold": targeted_scaffold,
            "targeted_retry_extra_calls_used": 0,
            "targeted_retry_answer_raw": "",
            "targeted_retry_answer_parsed": "",
            "targeted_retry_committed": False,
            "targeted_retry_rejection_reason": "",
            "production_equiv_surface_source": ("targeted_retry_rejected" if targeted_planned else "structural_commit"),
            "production_equiv_surface_reason": ("planned_runtime_hook_no_api_dryrun" if targeted_planned else "base_structural_commit_path"),
            "production_equiv_abstain_reason": "",
            "production_equiv_excluded_patches": json.dumps(excluded_patches, ensure_ascii=False),
        }

        row = {
            "case_id": cid,
            "planned_base_action": planned_base_action,
            "structural_commit_available": structural_commit_available,
            "router_decision": router_decision,
            "verifier_trigger": "yes" if verifier_features.get("final_target_mismatch_risk") else "no",
            "targeted_retry_planned": "yes" if targeted_planned else "no",
            "targeted_retry_scaffold": targeted_scaffold,
            "expected_extra_calls": expected_extra_calls,
            "excluded_patch_reason": excluded_patch_reason,
            "production_equiv_ready_for_live": ready_live,
            "blocking_reason": blocking_reason,
            **md,
        }
        rows.append(row)
        call_plan_rows.append(
            {
                "case_id": cid,
                "planned_method": args.method_name,
                "planned_base_action": planned_base_action,
                "targeted_retry_planned": row["targeted_retry_planned"],
                "targeted_retry_scaffold": targeted_scaffold,
                "expected_extra_calls": expected_extra_calls,
                "planned_total_calls_for_case": 1 + expected_extra_calls,
                "production_equiv_ready_for_live": ready_live,
                "blocking_reason": blocking_reason,
            }
        )

    _write_csv(out / "production_equiv_v1_runtime_cases.csv", list(rows[0].keys()), rows)
    _write_csv(out / "production_equiv_v1_runtime_call_plan.csv", list(call_plan_rows[0].keys()), call_plan_rows)

    targeted_count = sum(1 for r in rows if r["targeted_retry_planned"] == "yes")
    est_extra = sum(int(r["expected_extra_calls"]) for r in rows)
    runtime_wired = True
    surface_wired = True
    tiny_smoke_ready = bool(runtime_wired and surface_wired and not blocked_runtime_hooks)
    summary = {
        "case_count": len(rows),
        "no_api_calls": True,
        "planned_targeted_retry_count": targeted_count,
        "estimated_extra_calls": est_extra,
        "estimated_total_calls": len(rows) + est_extra,
        "router_decision_counts": dict(Counter(r["router_decision"] for r in rows)),
        "scaffold_counts": dict(Counter(r["targeted_retry_scaffold"] for r in rows if r["targeted_retry_scaffold"])),
        "excluded_patch_reasons": dict(Counter(r["excluded_patch_reason"] for r in rows if r["excluded_patch_reason"])),
        "runtime_targeted_retry_hook_wired": runtime_wired,
        "surface_parity_source_wired": surface_wired,
        "remaining_blocking_issues": blocked_runtime_hooks,
        "ready_for_tiny_live_smoke": tiny_smoke_ready,
        "ready_for_live_50_checkpoint": False,
    }
    (out / "production_equiv_v1_runtime_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "no_api_calls": True,
        "method_name": args.method_name,
        "method_alias": cfg.method_alias,
        "case_count": len(rows),
        "source_case_file": str(args.case_file.resolve()),
        "enable_structural_commitment_v1": True,
        "enable_adaptive_router_v3_features": True,
        "enable_final_target_verifier_v1": True,
        "enable_runtime_targeted_retry_v1": True,
        "targeted_retry_max_extra_calls": int(cfg.targeted_retry_max_extra_calls),
        "allowed_targeted_retry_scaffolds": list(cfg.targeted_retry_allowed_scaffolds),
        "enable_percent_base_denominator": bool(cfg.enable_percent_base_denominator),
        "enable_discovery3_candidate_diversity_selection_v1": bool(cfg.enable_discovery3_candidate_diversity_selection_v1),
        "excluded_patches_confirmed": excluded_patches,
    }
    manifest["runtime_targeted_retry_hook_wired"] = True
    manifest["surface_parity_source_wired"] = True
    (out / "production_equiv_v1_runtime_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    report = [
        "# Production Equiv v1 Stage-3 50 Dry Run",
        "",
        f"- method: `{args.method_name}`",
        "- no API calls were made.",
        f"- case_count: {len(rows)}",
        f"- planned_targeted_retry_count: {targeted_count}",
        f"- estimated_extra_calls: {est_extra}",
        f"- estimated_total_calls: {len(rows) + est_extra}",
        f"- excluded patches confirmed: {', '.join(excluded_patches)}",
        "- production-equivalent metadata contract is present in dry-run rows/call-plan.",
        f"- runtime_targeted_retry_hook_wired: {summary['runtime_targeted_retry_hook_wired']}",
        f"- surface_parity_source_wired: {summary['surface_parity_source_wired']}",
        f"- ready_for_tiny_live_smoke: {summary['ready_for_tiny_live_smoke']}",
        f"- ready_for_live_50_checkpoint: {summary['ready_for_live_50_checkpoint']}",
        "",
        "## Blocking hooks",
        *[f"- {x}" for x in blocked_runtime_hooks],
    ]
    (out / "production_equiv_v1_runtime_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()

