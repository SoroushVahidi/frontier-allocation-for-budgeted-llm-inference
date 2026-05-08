#!/usr/bin/env python3
"""Stage-3 integrated-vs-external replay checkpoint runner (dry-run focused, no API)."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]

DEFAULT_METHOD = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
    "structural_commit_v1_targeted_retry_v1_validated_fixes"
)
DEFAULT_BASELINES = "external_l1_max,external_tale,external_s1,best_external"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--readiness-dir", type=Path, required=True)
    p.add_argument("--case-file", type=Path, default=None)
    p.add_argument("--stage-name", default="stage3_pilot")
    p.add_argument("--max-new-cohere-calls", type=int, default=50)
    p.add_argument("--reuse-external-outputs", action="store_true")
    p.add_argument("--dry-run-only", action="store_true")
    p.add_argument("--method-name", default=DEFAULT_METHOD)
    p.add_argument("--baselines", default=DEFAULT_BASELINES)
    p.add_argument("--output-dir", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    readiness_dir = args.readiness_dir.resolve()
    case_file = args.case_file.resolve() if args.case_file else readiness_dir / "stage3_pilot_cases.csv"
    if not case_file.exists():
        raise SystemExit(f"case file not found: {case_file}")
    rows = _read_csv(case_file)
    if not rows:
        raise SystemExit("case file is empty")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.output_dir:
        out = args.output_dir.resolve()
    else:
        suffix = "dry_run" if args.dry_run_only else "live"
        out = REPO / "outputs" / f"{args.stage_name}_integrated_vs_external_{suffix}_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    selected_rows: list[dict[str, Any]] = []
    call_plan_rows: list[dict[str, Any]] = []
    prompt_missing: list[str] = []
    external_missing: list[str] = []
    prompt_leak_gold: list[str] = []
    prompt_leak_external: list[str] = []
    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    baseline_list = [b.strip() for b in str(args.baselines).split(",") if b.strip()]

    for r in rows:
        cid = str(r.get("case_id") or "").strip()
        if not cid:
            continue
        if cid in seen_ids:
            duplicate_ids.append(cid)
        seen_ids.add(cid)

        planned = str(r.get("planned_integrated_action") or "stage3_validated_fixes_method_eval").strip()
        expected_call = str(r.get("expected_new_cohere_call") or "1").strip()
        prompt_path = str(r.get("prompt_or_method_path") or "").strip()
        if not prompt_path:
            prompt_path = f"method::{args.method_name}"

        # External availability check from row-level reused columns.
        if args.reuse_external_outputs:
            req_cols = [
                "external_l1_prediction",
                "external_l1_correct",
                "tale_prediction",
                "tale_correct",
                "s1_prediction",
                "s1_correct",
                "best_external_prediction",
                "best_external_correct",
            ]
            missing = [c for c in req_cols if not str(r.get(c) or "").strip()]
            if missing:
                external_missing.append(f"{cid}:{'|'.join(missing)}")

        # Optional prompt leak checks if a concrete prompt path is provided.
        if prompt_path.startswith("prompts/"):
            pp = readiness_dir / prompt_path
            if not pp.exists():
                prompt_missing.append(str(pp))
            else:
                txt = pp.read_text(encoding="utf-8")
                gold = str(r.get("gold_answer") or "").strip()
                ext = str(r.get("external_l1_prediction") or "").strip()
                if gold and gold in txt:
                    prompt_leak_gold.append(cid)
                if ext and ext in txt:
                    prompt_leak_external.append(cid)

        selected_rows.append(
            {
                "case_id": cid,
                "problem_text": r.get("problem_text", ""),
                "gold_answer": r.get("gold_answer", ""),
                "pal_prediction": r.get("pal_prediction", ""),
                "pal_correct": r.get("pal_correct", ""),
                "external_l1_prediction": r.get("external_l1_prediction", ""),
                "external_l1_correct": r.get("external_l1_correct", ""),
                "tale_prediction": r.get("tale_prediction", ""),
                "tale_correct": r.get("tale_correct", ""),
                "s1_prediction": r.get("s1_prediction", ""),
                "s1_correct": r.get("s1_correct", ""),
                "best_external_prediction": r.get("best_external_prediction", ""),
                "best_external_correct": r.get("best_external_correct", ""),
                "best_external_winner": r.get("best_external_winner", ""),
                "planned_integrated_action": planned,
                "expected_new_cohere_call": expected_call,
                "prompt_or_method_path": prompt_path,
                "source_artifacts": r.get("source_artifacts", ""),
                "notes": r.get("notes", ""),
            }
        )

        call_plan_rows.append(
            {
                "case_id": cid,
                "planned_integrated_action": planned,
                "expected_new_cohere_call": expected_call,
                "prompt_or_method_path": prompt_path,
                "notes": r.get("notes", ""),
            }
        )

    planned_calls = sum(1 for r in call_plan_rows if str(r["expected_new_cohere_call"]) == "1")

    preflight = {
        "readiness_dir": str(readiness_dir),
        "case_file": str(case_file),
        "case_count": len(selected_rows),
        "cohere_api_key_set": bool(os.getenv("COHERE_API_KEY")),
        "planned_new_cohere_calls": planned_calls,
        "planned_calls_ok": planned_calls <= int(args.max_new_cohere_calls),
        "reuse_external_outputs": bool(args.reuse_external_outputs),
        "baselines": baseline_list,
        "external_outputs_complete": len(external_missing) == 0,
        "external_missing_entries": external_missing,
        "all_prompt_paths_exist": len(prompt_missing) == 0,
        "missing_prompt_paths": prompt_missing,
        "no_ascii_gold_in_prompts": len(prompt_leak_gold) == 0,
        "gold_leak_case_ids": prompt_leak_gold,
        "no_external_prediction_in_prompts": len(prompt_leak_external) == 0,
        "external_prediction_leak_case_ids": prompt_leak_external,
        "no_duplicate_case_ids": len(duplicate_ids) == 0,
        "duplicate_case_ids": duplicate_ids,
    }
    (out / "preflight_status.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")

    _write_csv(out / "selected_stage3_cases.csv", list(selected_rows[0].keys()), selected_rows)
    _write_csv(out / "stage3_call_plan.csv", list(call_plan_rows[0].keys()), call_plan_rows)

    live_supported = False  # intentionally dry-run only in this runner revision
    manifest = {
        "stage_name": args.stage_name,
        "method_name": args.method_name,
        "case_count": len(selected_rows),
        "max_new_cohere_calls": int(args.max_new_cohere_calls),
        "planned_new_cohere_calls": planned_calls,
        "baselines": baseline_list,
        "reuse_external_outputs": bool(args.reuse_external_outputs),
        "dry_run_only": bool(args.dry_run_only),
        "no_api_calls": True,
        "live_execution_supported": live_supported,
        "missing_live_components": [
            "cohere invocation path intentionally disabled for replay checkpoint runner",
            "result-scoring live step not implemented in this script",
        ],
    }
    (out / "stage3_checkpoint_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    report = [
        "# Stage-3 Integrated vs External Replay Checkpoint (Dry Run)",
        "",
        f"- Method alias: `{args.method_name}`",
        f"- Cases selected: {len(selected_rows)}",
        f"- Planned integrated calls: {planned_calls}",
        f"- Cap: {args.max_new_cohere_calls}",
        f"- Planned calls within cap: {preflight['planned_calls_ok']}",
        f"- External outputs reused: {args.reuse_external_outputs}",
        f"- Baselines: {', '.join(baseline_list)}",
        "",
        "## Execution mode",
        "- no_api_calls=true (dry-run provenance only).",
        f"- live_execution_supported={live_supported}",
        "",
        "## Notes",
        "- This runner validates replay-ready schema and call-plan only.",
        "- It intentionally does not execute model calls in this revision.",
    ]
    (out / "stage3_dry_run_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(out)


if __name__ == "__main__":
    main()
