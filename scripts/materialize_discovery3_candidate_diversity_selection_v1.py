#!/usr/bin/env python3
"""No-API design + dry-run materializer for discovery3 patch v1."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.adaptive_retry_router import compute_adaptive_retry_features, should_trigger_discovery3_diversity_retry
from experiments.final_target_verifier import final_target_verifier_features
from experiments.targeted_discovery_retry import (
    build_discovery3_candidate_diversity_prompt,
    build_discovery3_patch_metadata,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        fn = list(rows[0].keys()) if rows else []
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _guess_target_quantity_type(problem_text: str) -> str:
    t = (problem_text or "").lower()
    if "in total" in t or "altogether" in t or "combined" in t:
        return "total"
    if "how many more" in t or "difference" in t:
        return "difference"
    if "remaining" in t or "left" in t:
        return "remaining"
    if "ratio" in t or "twice" in t or "half" in t:
        return "ratio_part"
    if "per " in t or "mph" in t or "rate" in t:
        return "rate"
    if "average" in t:
        return "average"
    return "entity_value"


def _choose_scaffold(family: str) -> str:
    fam = (family or "").strip()
    if fam == "final_target_mismatch":
        return "final_target_extraction_repair"
    if fam == "state_update":
        return "state_transition_consistency"
    if fam == "ratio_setup":
        return "ratio_unit_equation"
    if fam == "format_parse":
        return "robust_extraction_observability"
    return "leave_unmodified"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--nonoverlap-discovery3",
        type=Path,
        default=REPO / "outputs/nonoverlap_our_method_discovery3_live_20260508T185859Z/discovery3_records.jsonl",
    )
    p.add_argument(
        "--expanded-discovery3",
        type=Path,
        default=REPO / "outputs/expanded_failure_bank_collection_20260508T185435Z/discovery3_records.jsonl",
    )
    p.add_argument(
        "--loss-best-core4-only",
        type=Path,
        default=REPO / "outputs/fair_core4_loss_pattern_bank_20260508T182155Z/our_loss_to_best_core4_cases.csv",
    )
    p.add_argument(
        "--loss-both-wrong",
        type=Path,
        default=REPO / "outputs/fair_core4_loss_pattern_bank_20260508T182155Z/both_wrong_cases.csv",
    )
    p.add_argument("--design-output-dir", type=Path, default=None)
    p.add_argument("--dry-run-output-dir", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    design_out = (
        args.design_output_dir.resolve()
        if args.design_output_dir
        else REPO / "outputs" / f"discovery3_candidate_diversity_selection_v1_design_{ts}"
    )
    dry_out = (
        args.dry_run_output_dir.resolve()
        if args.dry_run_output_dir
        else REPO / "outputs" / f"discovery3_candidate_diversity_selection_v1_dry_run_{ts}"
    )
    design_out.mkdir(parents=True, exist_ok=True)
    (dry_out / "prompts").mkdir(parents=True, exist_ok=True)

    nonoverlap = _read_jsonl(args.nonoverlap_discovery3.resolve())
    expanded = _read_jsonl(args.expanded_discovery3.resolve())
    loss1 = _read_csv(args.loss_best_core4_only.resolve())
    loss2 = _read_csv(args.loss_both_wrong.resolve())

    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for r in nonoverlap:
        key = ("nonoverlap_discovery3", str(r.get("case_id", "")))
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "case_id": r.get("case_id", ""),
                "source_bundle": "nonoverlap_discovery3_live",
                "problem_text": r.get("problem_text", ""),
                "gold_answer": r.get("gold_answer", ""),
                "our_answer": r.get("our_final_answer", ""),
                "our_correct": r.get("our_correct", ""),
                "selection_failure_type": r.get("selection_failure_type", ""),
                "reasoning_family_guess": r.get("reasoning_family_guess", "unknown"),
                "target_quantity_type": r.get("target_quantity_type", "unknown"),
                "state_update_risk": r.get("state_update_risk", "no"),
                "ratio_or_percent_risk": r.get("ratio_or_percent_risk", "no"),
                "unit_consistency_risk": r.get("unit_consistency_risk", "no"),
                "gold_in_candidate_set": r.get("gold_in_candidate_set", "unknown"),
                "selected_answer_source": r.get("selected_answer_source", ""),
                "proposed_fix_candidate": "",
                "priority": "high" if str(r.get("selection_failure_type")) != "not_failure" else "low",
            }
        )

    for r in expanded:
        key = ("expanded_discovery3", str(r.get("case_id", "")))
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "case_id": r.get("case_id", ""),
                "source_bundle": "expanded_failure_bank_collection",
                "problem_text": r.get("problem_text", ""),
                "gold_answer": r.get("gold_answer", ""),
                "our_answer": r.get("our_final_answer", ""),
                "our_correct": r.get("our_correct", ""),
                "selection_failure_type": r.get("selection_failure_type", ""),
                "reasoning_family_guess": r.get("reasoning_family_guess", "unknown"),
                "target_quantity_type": r.get("target_quantity_type", "unknown"),
                "state_update_risk": r.get("state_update_risk", "no"),
                "ratio_or_percent_risk": r.get("ratio_or_percent_risk", "no"),
                "unit_consistency_risk": r.get("unit_consistency_risk", "no"),
                "gold_in_candidate_set": r.get("gold_in_candidate_set", "unknown"),
                "selected_answer_source": r.get("selected_answer_source", ""),
                "proposed_fix_candidate": "",
                "priority": "high" if str(r.get("selection_failure_type")) != "not_failure" else "low",
            }
        )

    for r in loss1 + loss2:
        merged.append(
            {
                "case_id": r.get("case_id", ""),
                "source_bundle": "fair_core4_loss_pattern_bank",
                "problem_text": r.get("problem_text", ""),
                "gold_answer": r.get("gold_answer", ""),
                "our_answer": r.get("our_prediction", ""),
                "our_correct": r.get("our_correct", ""),
                "selection_failure_type": "present_not_selected" if r.get("best_core4_correct") == "1" else "both_wrong_unknown",
                "reasoning_family_guess": r.get("inferred_failure_family", "unknown"),
                "target_quantity_type": _guess_target_quantity_type(r.get("problem_text", "")),
                "state_update_risk": "yes" if r.get("inferred_failure_family") == "state_update" else "no",
                "ratio_or_percent_risk": "yes" if r.get("inferred_failure_family") in {"ratio_setup", "percent_base"} else "no",
                "unit_consistency_risk": "unknown",
                "gold_in_candidate_set": "unknown",
                "selected_answer_source": "our_candidate",
                "proposed_fix_candidate": r.get("possible_fix_candidate", ""),
                "priority": "high",
            }
        )

    _write_csv(design_out / "merged_failure_evidence.csv", merged)

    unique_cases = {}
    for r in merged:
        cid = str(r["case_id"])
        if cid not in unique_cases:
            unique_cases[cid] = r

    selected_confirmation = []
    # all 7 nonoverlap failures
    nonoverlap_fail = [r for r in merged if r["source_bundle"] == "nonoverlap_discovery3_live" and r["selection_failure_type"] != "not_failure"]
    for r in nonoverlap_fail:
        selected_confirmation.append(r)
    # plus 8 representative expanded failures
    expanded_fail = [r for r in merged if r["source_bundle"] == "expanded_failure_bank_collection" and r["selection_failure_type"] != "not_failure"]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for r in expanded_fail:
        by_type.setdefault(str(r["selection_failure_type"]), []).append(r)
    for k in ["gold_absent_discovery", "present_not_selected", "both_wrong_unknown", "parse_failure"]:
        for r in by_type.get(k, []):
            if len(selected_confirmation) >= 15:
                break
            if r["case_id"] not in {x["case_id"] for x in selected_confirmation}:
                selected_confirmation.append(r)
        if len(selected_confirmation) >= 15:
            break
    for r in expanded_fail:
        if len(selected_confirmation) >= 15:
            break
        if r["case_id"] not in {x["case_id"] for x in selected_confirmation}:
            selected_confirmation.append(r)
    selected_confirmation = selected_confirmation[:15]

    # dry-run materialization
    confirmation_rows: list[dict[str, Any]] = []
    trigger_counts = Counter()
    scaffold_counts = Counter()
    no_gold = True
    no_pred = True
    for r in selected_confirmation:
        cid = str(r["case_id"])
        problem = str(r["problem_text"])
        ttype = str(r.get("target_quantity_type") or _guess_target_quantity_type(problem))
        family = str(r.get("reasoning_family_guess") or "unknown")
        scaffold = _choose_scaffold(family)

        rf = compute_adaptive_retry_features(problem)
        vf = final_target_verifier_features(problem)
        trigger = should_trigger_discovery3_diversity_retry(
            problem,
            rf,
            vf,
            {
                "target_quantity_type": ttype,
                "reasoning_family_guess": family,
                "high_disagreement": True,
                "no_confident_candidate": True,
            },
        )
        trigger_counts["triggered" if trigger else "not_triggered"] += 1
        if scaffold == "leave_unmodified" and trigger:
            scaffold = "state_transition_consistency" if vf.get("state_update_risk") else "ratio_unit_equation"
        scaffold_counts[scaffold] += 1

        prompt = build_discovery3_candidate_diversity_prompt(problem, target_quantity_type=ttype, family_hint=family)
        ppath = dry_out / "prompts" / f"{cid}.txt"
        ppath.write_text(prompt, encoding="utf-8")
        gold = str(r.get("gold_answer") or "").strip()
        if gold and len(gold) >= 2 and gold in prompt:
            no_gold = False
        if any(x in prompt.lower() for x in ("our_prediction", "external_l1", "best_core4", "baseline prediction")):
            no_pred = False

        md = build_discovery3_patch_metadata(
            patch_enabled=True,
            retry_triggered=bool(trigger),
            selected_scaffold=scaffold,
            selection_policy_applied=True,
            selection_reason="dry_run_materialization",
            extra_calls_planned=1,
            extra_calls_used=0,
        )
        confirmation_rows.append(
            {
                "case_id": cid,
                "problem_text": problem,
                "gold_answer": gold,
                "selection_failure_type": r.get("selection_failure_type", ""),
                "reasoning_family_guess": family,
                "target_quantity_type": ttype,
                "selected_scaffold": scaffold,
                "triggered": "yes" if trigger else "no",
                "prompt_path": _display_path(ppath),
                "metadata_json": json.dumps(md, ensure_ascii=False),
            }
        )

    _write_csv(dry_out / "confirmation_cases.csv", confirmation_rows)
    call_plan = [{"case_id": r["case_id"], "planned_method": "discovery3_candidate_diversity_selection_v1", "planned_extra_calls": 1} for r in confirmation_rows]
    _write_csv(dry_out / "dry_run_call_plan.csv", call_plan)

    design_summary = {
        "total_unique_failure_cases": len(unique_cases),
        "gold_absent_discovery_count": sum(1 for r in merged if r["selection_failure_type"] == "gold_absent_discovery"),
        "present_not_selected_count": sum(1 for r in merged if r["selection_failure_type"] == "present_not_selected"),
        "family_counts": dict(Counter(str(r["reasoning_family_guess"]) for r in merged)),
        "target_quantity_type_counts": dict(Counter(str(r["target_quantity_type"]) for r in merged)),
        "risk_feature_counts": {
            "state_update_risk_yes": sum(1 for r in merged if str(r["state_update_risk"]) == "yes"),
            "ratio_or_percent_risk_yes": sum(1 for r in merged if str(r["ratio_or_percent_risk"]) == "yes"),
        },
        "recommended_patch_scope": "opt-in discovery3 candidate diversity + final-target selection verifier",
        "selected_confirmation_cases": [r["case_id"] for r in confirmation_rows],
    }
    (design_out / "design_summary.json").write_text(json.dumps(design_summary, indent=2) + "\n", encoding="utf-8")

    dry_manifest = {
        "no_api_calls": True,
        "case_count": len(confirmation_rows),
        "planned_extra_calls": len(confirmation_rows),
        "selected_case_ids": [r["case_id"] for r in confirmation_rows],
        "scaffold_counts": dict(scaffold_counts),
        "trigger_counts": dict(trigger_counts),
        "no_gold_in_prompts_verified": bool(no_gold),
        "no_prediction_leakage_verified": bool(no_pred),
        "ready_for_live_confirmation": bool(no_gold and no_pred and len(confirmation_rows) == 15),
        "abort_conditions": [
            "planned_extra_calls > 15",
            "gold or prediction leakage detected in prompts",
            "missing confirmation cases",
        ],
    }
    (dry_out / "dry_run_manifest.json").write_text(json.dumps(dry_manifest, indent=2) + "\n", encoding="utf-8")
    report = [
        "# discovery3 candidate diversity selection v1 dry run",
        "",
        f"- case_count: {len(confirmation_rows)}",
        f"- scaffold_counts: {dict(scaffold_counts)}",
        f"- trigger_counts: {dict(trigger_counts)}",
        f"- no_gold_in_prompts_verified: {no_gold}",
        f"- no_prediction_leakage_verified: {no_pred}",
        "- Ready for live confirmation if all checks pass and call budget <= 15.",
    ]
    (dry_out / "dry_run_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(design_out)
    print(dry_out)


if __name__ == "__main__":
    main()

