#!/usr/bin/env python3
"""Stage-3 integrated-vs-external checkpoint runner with live gating."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.data import extract_final_answer
from experiments.targeted_discovery_retry import build_prompt

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


def _norm_num(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    final = extract_final_answer(raw).strip().replace(",", "")
    if not final:
        return ""
    try:
        val = float(final)
    except ValueError:
        return ""
    return str(int(val)) if val.is_integer() else f"{val:.10g}"


def _is_true(value: str) -> bool:
    return str(value or "").strip() in {"1", "true", "True", "yes"}


def _has_value_leak(prompt_text: str, value: str) -> bool:
    v = str(value or "").strip()
    if not v:
        return False
    # Avoid false positives on single-digit tokens that commonly appear in instructions.
    if v.isdigit() and len(v) <= 1:
        return False
    if re.search(r"\\boxed\{\s*" + re.escape(v) + r"\s*\}", prompt_text):
        return True
    if re.search(r"(?i)\b(final\s+answer|answer)\b[^\\n]{0,40}" + re.escape(v), prompt_text):
        return True
    return False


def _cohere_chat(prompt: str, *, model: str, temperature: float, max_tokens: int) -> str:
    import cohere  # type: ignore

    api_key = os.getenv("COHERE_API_KEY", "")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is required")
    client = cohere.ClientV2(api_key=api_key)
    resp = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    out = ""
    msg = getattr(resp, "message", None)
    if msg is not None and getattr(msg, "content", None):
        for part in msg.content:
            text = getattr(part, "text", "")
            if text:
                out += str(text)
    return out.strip()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--readiness-dir", type=Path, required=True)
    p.add_argument("--case-file", type=Path, default=None)
    p.add_argument("--stage-name", default="stage3_pilot")
    p.add_argument("--max-new-cohere-calls", type=int, default=50)
    p.add_argument("--reuse-external-outputs", action="store_true")
    p.add_argument("--dry-run-only", action="store_true")
    p.add_argument("--execute-live", action="store_true")
    p.add_argument("--method-name", default=DEFAULT_METHOD)
    p.add_argument("--baselines", default=DEFAULT_BASELINES)
    p.add_argument("--model", default="command-a-03-2025")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, default=700)
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
        if args.dry_run_only:
            suffix = "dry_run"
        elif args.execute_live:
            suffix = "live"
        else:
            suffix = "live_preflight"
        out = REPO / "outputs" / f"{args.stage_name}_integrated_vs_external_{suffix}_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    prompts_dir = out / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = out / "responses"
    if args.execute_live and not args.dry_run_only:
        responses_dir.mkdir(parents=True, exist_ok=True)

    selected_rows: list[dict[str, Any]] = []
    call_plan_rows: list[dict[str, Any]] = []
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

        planned = str(r.get("planned_integrated_action") or "stage3_pilot_integrated_action").strip()
        expected_call = "1"

        best_external_prediction = str(r.get("best_external_prediction") or "").strip()
        if not best_external_prediction:
            winner = str(r.get("best_external_winner") or "").strip()
            if winner == "external_l1_max":
                best_external_prediction = str(r.get("external_l1_prediction") or "").strip()
            elif winner == "external_tale":
                best_external_prediction = str(r.get("tale_prediction") or "").strip()
            elif winner == "external_s1":
                best_external_prediction = str(r.get("s1_prediction") or "").strip()
        if not best_external_prediction:
            best_external_prediction = (
                str(r.get("external_l1_prediction") or "").strip()
                or str(r.get("tale_prediction") or "").strip()
                or str(r.get("s1_prediction") or "").strip()
            )

        # External availability check from row-level reused columns.
        if args.reuse_external_outputs:
            req_cols = [
                "external_l1_prediction",
                "external_l1_correct",
                "tale_prediction",
                "tale_correct",
                "s1_prediction",
                "s1_correct",
                "best_external_correct",
            ]
            missing = [c for c in req_cols if not str(r.get(c) or "").strip()]
            if not best_external_prediction:
                missing.append("best_external_prediction")
            if missing:
                external_missing.append(f"{cid}:{'|'.join(missing)}")

        prompt_text = build_prompt(str(r.get("problem_text") or ""), "l1_style_concise_decomposition")
        prompt_path = f"prompts/{cid}.txt"
        (out / prompt_path).write_text(prompt_text, encoding="utf-8")

        gold = str(r.get("gold_answer") or "").strip()
        ext = str(r.get("external_l1_prediction") or "").strip()
        no_gold_leakage = not _has_value_leak(prompt_text, gold)
        no_external_leakage = not _has_value_leak(prompt_text, ext)
        if not no_gold_leakage:
            prompt_leak_gold.append(cid)
        if not no_external_leakage:
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
                "best_external_prediction": best_external_prediction,
                "best_external_correct": r.get("best_external_correct", ""),
                "best_external_winner": r.get("best_external_winner", ""),
                "planned_integrated_action": planned,
                "expected_new_cohere_call": expected_call,
                "prompt_path": prompt_path,
                "no_gold_leakage": "1" if no_gold_leakage else "0",
                "no_external_prediction_leakage": "1" if no_external_leakage else "0",
                "source_artifacts": r.get("source_artifacts", ""),
                "notes": r.get("notes", ""),
            }
        )

        call_plan_rows.append(
            {
                "case_id": cid,
                "planned_integrated_action": planned,
                "expected_new_cohere_call": expected_call,
                "prompt_path": prompt_path,
                "no_gold_leakage": "1" if no_gold_leakage else "0",
                "no_external_prediction_leakage": "1" if no_external_leakage else "0",
                "notes": r.get("notes", ""),
            }
        )

    planned_calls = sum(1 for r in call_plan_rows if str(r["expected_new_cohere_call"]) == "1")

    live_execution_supported = True
    would_call_cohere = not args.dry_run_only
    execute_live_allowed = bool(args.execute_live and not args.dry_run_only)
    preflight_ok = (
        planned_calls <= int(args.max_new_cohere_calls)
        and len(external_missing) == 0
        and len(prompt_leak_gold) == 0
        and len(prompt_leak_external) == 0
        and len(duplicate_ids) == 0
        and len(selected_rows) > 0
    )
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
        "no_ascii_gold_in_prompts": len(prompt_leak_gold) == 0,
        "gold_leak_case_ids": prompt_leak_gold,
        "no_external_prediction_in_prompts": len(prompt_leak_external) == 0,
        "external_prediction_leak_case_ids": prompt_leak_external,
        "no_duplicate_case_ids": len(duplicate_ids) == 0,
        "duplicate_case_ids": duplicate_ids,
        "live_execution_supported": live_execution_supported,
        "execute_live": bool(args.execute_live),
        "execute_live_required_for_api_calls": True,
        "would_call_cohere": would_call_cohere,
        "preflight_ok": preflight_ok,
    }
    (out / "preflight_status.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")

    _write_csv(out / "selected_stage3_cases.csv", list(selected_rows[0].keys()), selected_rows)
    _write_csv(out / "stage3_call_plan.csv", list(call_plan_rows[0].keys()), call_plan_rows)

    manifest = {
        "stage_name": args.stage_name,
        "method_name": args.method_name,
        "case_count": len(selected_rows),
        "max_new_cohere_calls": int(args.max_new_cohere_calls),
        "planned_new_cohere_calls": planned_calls,
        "baselines": baseline_list,
        "reuse_external_outputs": bool(args.reuse_external_outputs),
        "external_outputs_reused": bool(args.reuse_external_outputs),
        "dry_run_only": bool(args.dry_run_only),
        "execute_live": bool(args.execute_live),
        "would_call_cohere": would_call_cohere,
        "no_api_calls": not execute_live_allowed,
        "live_execution_supported": live_execution_supported,
        "model": args.model,
        "temperature": float(args.temperature),
        "max_tokens": int(args.max_tokens),
    }
    (out / "stage3_checkpoint_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    live_schema = [
        "# Stage-3 Live Result Schema",
        "",
        "## stage3_live_results.csv columns",
        "- case_id",
        "- integrated_prediction",
        "- integrated_correct",
        "- external_l1_prediction",
        "- external_l1_correct",
        "- tale_prediction",
        "- tale_correct",
        "- s1_prediction",
        "- s1_correct",
        "- best_external_prediction",
        "- best_external_correct",
        "- cohere_call_made",
        "- response_text_path",
        "- parse_status",
        "- no_gold_leakage",
        "- no_external_prediction_leakage",
        "- notes",
        "",
        "## stage3_live_summary.json keys",
        "- integrated_correct_count",
        "- external_l1_correct_count",
        "- tale_correct_count",
        "- s1_correct_count",
        "- best_external_correct_count",
        "- integrated_minus_external_l1",
        "- integrated_minus_tale",
        "- integrated_minus_s1",
        "- integrated_minus_best_external",
        "- paired_external_l1_only",
        "- paired_tale_only",
        "- paired_s1_only",
        "- paired_best_external_only",
        "- paired_integrated_only_vs_external_l1",
        "- api_errors",
        "- parsing_ambiguities",
        "- no_gold_leakage",
        "- no_external_prediction_leakage",
    ]
    (out / "stage3_live_schema.md").write_text("\n".join(live_schema) + "\n", encoding="utf-8")

    dry_report = [
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
        f"- live_execution_supported={live_execution_supported}",
        "",
        "## Notes",
        "- Dry-run validates schema, prompt leakage checks, and call-plan only.",
        "- Cohere calls remain disabled unless --execute-live is explicitly supplied.",
    ]

    preflight_report = [
        "# Stage-3 Integrated vs External Live Preflight",
        "",
        f"- execute_live: {bool(args.execute_live)}",
        f"- preflight_ok: {preflight_ok}",
        f"- would_call_cohere: {would_call_cohere}",
        f"- no_api_calls: {not execute_live_allowed}",
        f"- planned_new_cohere_calls: {planned_calls}",
        f"- baselines_reused: {', '.join(baseline_list)}",
        "",
        "## Safety gate",
        "- API calls are blocked unless --execute-live is provided.",
    ]
    (out / "stage3_preflight_report.md").write_text("\n".join(preflight_report) + "\n", encoding="utf-8")

    if args.dry_run_only:
        (out / "stage3_dry_run_report.md").write_text("\n".join(dry_report) + "\n", encoding="utf-8")
        print(out)
        return

    if not args.execute_live:
        print(out)
        return

    if not preflight_ok:
        raise SystemExit("preflight failed; refusing live execution")

    # Live execution path (enabled only with --execute-live).
    results: list[dict[str, Any]] = []
    api_errors: list[str] = []
    parsing_ambiguities = 0
    no_gold_leakage_all = True
    no_external_leakage_all = True
    for r in selected_rows:
        cid = str(r["case_id"])
        prompt_path = out / str(r["prompt_path"])
        prompt = prompt_path.read_text(encoding="utf-8")
        response_path = responses_dir / f"{cid}.txt"
        cohere_call_made = "yes"
        notes = ""
        text = ""
        try:
            text = _cohere_chat(
                prompt,
                model=args.model,
                temperature=float(args.temperature),
                max_tokens=int(args.max_tokens),
            )
            response_path.write_text(text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            api_errors.append(f"{cid}:{type(exc).__name__}:{exc}")
            response_path.write_text("", encoding="utf-8")
            notes = f"api_error:{type(exc).__name__}"
        pred = _norm_num(text)
        parse_status = "ok" if pred else "ambiguous"
        if parse_status != "ok":
            parsing_ambiguities += 1
        gold = _norm_num(str(r.get("gold_answer") or ""))
        integrated_correct = "1" if (gold and pred and gold == pred) else "0"
        ng = _is_true(str(r.get("no_gold_leakage") or "0"))
        ne = _is_true(str(r.get("no_external_prediction_leakage") or "0"))
        no_gold_leakage_all = no_gold_leakage_all and ng
        no_external_leakage_all = no_external_leakage_all and ne
        results.append(
            {
                "case_id": cid,
                "integrated_prediction": pred,
                "integrated_correct": integrated_correct,
                "external_l1_prediction": r.get("external_l1_prediction", ""),
                "external_l1_correct": r.get("external_l1_correct", ""),
                "tale_prediction": r.get("tale_prediction", ""),
                "tale_correct": r.get("tale_correct", ""),
                "s1_prediction": r.get("s1_prediction", ""),
                "s1_correct": r.get("s1_correct", ""),
                "best_external_prediction": r.get("best_external_prediction", ""),
                "best_external_correct": r.get("best_external_correct", ""),
                "cohere_call_made": cohere_call_made,
                "response_text_path": str(response_path.relative_to(out)).replace("\\", "/"),
                "parse_status": parse_status,
                "no_gold_leakage": "1" if ng else "0",
                "no_external_prediction_leakage": "1" if ne else "0",
                "notes": notes,
            }
        )

    _write_csv(out / "stage3_live_results.csv", list(results[0].keys()), results)
    integrated_correct_count = sum(1 for x in results if _is_true(x["integrated_correct"]))
    external_l1_correct_count = sum(1 for x in results if _is_true(x["external_l1_correct"]))
    tale_correct_count = sum(1 for x in results if _is_true(x["tale_correct"]))
    s1_correct_count = sum(1 for x in results if _is_true(x["s1_correct"]))
    best_external_correct_count = sum(1 for x in results if _is_true(x["best_external_correct"]))
    summary = {
        "integrated_correct_count": integrated_correct_count,
        "external_l1_correct_count": external_l1_correct_count,
        "tale_correct_count": tale_correct_count,
        "s1_correct_count": s1_correct_count,
        "best_external_correct_count": best_external_correct_count,
        "integrated_minus_external_l1": integrated_correct_count - external_l1_correct_count,
        "integrated_minus_tale": integrated_correct_count - tale_correct_count,
        "integrated_minus_s1": integrated_correct_count - s1_correct_count,
        "integrated_minus_best_external": integrated_correct_count - best_external_correct_count,
        "paired_external_l1_only": sum(
            1 for x in results if _is_true(x["external_l1_correct"]) and not _is_true(x["integrated_correct"])
        ),
        "paired_tale_only": sum(1 for x in results if _is_true(x["tale_correct"]) and not _is_true(x["integrated_correct"])),
        "paired_s1_only": sum(1 for x in results if _is_true(x["s1_correct"]) and not _is_true(x["integrated_correct"])),
        "paired_best_external_only": sum(
            1 for x in results if _is_true(x["best_external_correct"]) and not _is_true(x["integrated_correct"])
        ),
        "paired_integrated_only_vs_external_l1": sum(
            1 for x in results if _is_true(x["integrated_correct"]) and not _is_true(x["external_l1_correct"])
        ),
        "api_errors": api_errors,
        "parsing_ambiguities": parsing_ambiguities,
        "no_gold_leakage": no_gold_leakage_all,
        "no_external_prediction_leakage": no_external_leakage_all,
    }
    (out / "stage3_live_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / "stage3_live_report.md").write_text(
        "# Stage-3 Integrated vs External Live Report\n\n"
        f"- cases: {len(results)}\n"
        f"- integrated_correct: {integrated_correct_count}\n"
        f"- external_l1_correct: {external_l1_correct_count}\n",
        encoding="utf-8",
    )

    print(out)


if __name__ == "__main__":
    main()
