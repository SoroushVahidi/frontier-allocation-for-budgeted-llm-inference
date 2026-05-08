#!/usr/bin/env python3
"""Run reproducible integrated-vs-external checkpoint (dry-run or live)."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.data import extract_final_answer
from experiments.targeted_discovery_retry import validate_prompt_no_gold

DEFAULT_METHOD = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_"
    "structural_commit_v1_targeted_retry_v1"
)


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


def _resolve_prompt(base_dir: Path, prompt_path: str) -> Path:
    p = Path(prompt_path)
    if p.is_absolute():
        return p
    repo_path = REPO / p
    if repo_path.is_file():
        return repo_path
    base_path = base_dir / p
    if base_path.is_file():
        return base_path
    return repo_path


def _build_prompt_map(v1_dry: Path, v21_dry: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    v21_csv = v21_dry / "targeted_retry_v21_cases.csv"
    if v21_csv.is_file():
        for row in _read_csv(v21_csv):
            cid = str(row.get("case_id") or "").strip()
            rp = str(row.get("prompt_path") or "").strip()
            if not cid or not rp:
                continue
            out[cid] = {
                "prompt_path": rp,
                "prompt_abspath": str(_resolve_prompt(v21_dry, rp)),
                "prompt_version": str(row.get("prompt_version") or "quantity_ledger_v2_1").strip(),
                "scaffold": str(row.get("scaffold") or "").strip(),
            }
    v1_csv = v1_dry / "targeted_retry_cases.csv"
    if v1_csv.is_file():
        for row in _read_csv(v1_csv):
            cid = str(row.get("case_id") or "").strip()
            rp = str(row.get("prompt_path") or "").strip()
            if not cid or not rp or cid in out:
                continue
            out[cid] = {
                "prompt_path": rp,
                "prompt_abspath": str(_resolve_prompt(v1_dry, rp)),
                "prompt_version": "v1",
                "scaffold": str(row.get("selected_scaffold") or "").strip(),
            }
    return out


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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--readiness-dir", type=Path, required=True)
    ap.add_argument("--case-file", type=Path, default=None)
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--max-new-cohere-calls", type=int, default=50)
    ap.add_argument("--dry-run-only", action="store_true")
    ap.add_argument("--stage-name", default="custom")
    ap.add_argument("--reuse-external-l1", action="store_true")
    ap.add_argument("--method-name", default=DEFAULT_METHOD)
    ap.add_argument("--baseline", default="external_l1_max")
    ap.add_argument("--model", default="command-a-03-2025")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=700)
    ap.add_argument(
        "--v1-dry-run-dir",
        type=Path,
        default=REPO / "outputs/targeted_discovery_retry_v1_dry_run_20260508T010738Z",
    )
    ap.add_argument(
        "--v21-dry-run-dir",
        type=Path,
        default=REPO / "outputs/targeted_discovery_retry_v21_dry_run_20260508T014403Z",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    readiness_dir = args.readiness_dir.resolve()
    case_file = args.case_file.resolve() if args.case_file else readiness_dir / "recommended_checkpoint_cases.csv"
    if not case_file.is_file():
        stage2_default = readiness_dir / "stage2_recommended_cases.csv"
        if stage2_default.is_file():
            case_file = stage2_default
        else:
            raise SystemExit(f"case file not found: {case_file}")
    case_rows = _read_csv(case_file)
    if not case_rows:
        raise SystemExit("case file is empty")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.output_dir:
        out = args.output_dir.resolve()
    else:
        prefix = f"external_l1_{args.stage_name}_integrated_checkpoint"
        if args.dry_run_only:
            prefix += "_dry_run"
        out = REPO / "outputs" / f"{prefix}_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    responses_dir = out / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    prompt_map = _build_prompt_map(args.v1_dry_run_dir.resolve(), args.v21_dry_run_dir.resolve())
    external_paths = [
        REPO / "outputs/cohere_paired_pal_retry_vs_external_l1_100case_20260506T185133Z/external_l1_results.csv",
        REPO / "outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/external_l1_results.csv",
        REPO / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_results.jsonl",
    ]
    planned_calls = sum(1 for r in case_rows if str(r.get("planned_integrated_action") or "") == "targeted_retry")
    missing_external = [str(p) for p in external_paths if not p.exists()]
    missing_prompt_paths: list[str] = []
    gold_leak_case_ids: list[str] = []
    unsupported_case_ids: list[str] = []
    for r in case_rows:
        if str(r.get("planned_integrated_action") or "") != "targeted_retry":
            continue
        cid = str(r.get("case_id") or "")
        pm = prompt_map.get(cid)
        if not pm:
            missing_prompt_paths.append(f"{cid}:prompt_map_missing")
            continue
        pp = Path(pm["prompt_abspath"])
        if not pp.is_file():
            missing_prompt_paths.append(str(pp))
            continue
        prompt_body = pp.read_text(encoding="utf-8")
        gold = str(r.get("gold_answer") or "").strip()
        if gold and not validate_prompt_no_gold(prompt_body, gold):
            gold_leak_case_ids.append(cid)
        if pm.get("scaffold", "") not in {"quantity_ledger", "rate_table", "before_after_state", "target_difference"}:
            unsupported_case_ids.append(cid)

    preflight = {
        "readiness_dir": str(readiness_dir),
        "case_file": str(case_file),
        "case_count": len(case_rows),
        "cohere_api_key_set": bool(os.getenv("COHERE_API_KEY")),
        "external_l1_paths_exist": len(missing_external) == 0,
        "missing_external_l1_paths": missing_external,
        "planned_new_cohere_calls": planned_calls,
        "planned_calls_ok": planned_calls <= int(args.max_new_cohere_calls),
        "targeted_prompt_files_ok": len(missing_prompt_paths) == 0,
        "missing_prompt_paths": missing_prompt_paths,
        "no_ascii_gold_in_prompts": len(gold_leak_case_ids) == 0,
        "gold_leak_case_ids": gold_leak_case_ids,
        "no_unsupported_targeted_cases": len(unsupported_case_ids) == 0,
        "unsupported_targeted_case_ids": unsupported_case_ids,
        "dry_run_only": bool(args.dry_run_only),
    }
    if args.dry_run_only:
        preflight_ok = all(
            [
                preflight["external_l1_paths_exist"] or (not args.reuse_external_l1),
                preflight["planned_calls_ok"],
                preflight["targeted_prompt_files_ok"],
                preflight["no_ascii_gold_in_prompts"],
                preflight["no_unsupported_targeted_cases"],
            ]
        )
    else:
        preflight_ok = all(
            [
                preflight["cohere_api_key_set"],
                preflight["external_l1_paths_exist"] or (not args.reuse_external_l1),
                preflight["planned_calls_ok"],
                preflight["targeted_prompt_files_ok"],
                preflight["no_ascii_gold_in_prompts"],
                preflight["no_unsupported_targeted_cases"],
            ]
        )
    preflight["preflight_ok"] = preflight_ok
    (out / "preflight_status.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")

    manifest = {
        "stage_name": args.stage_name,
        "method_name": args.method_name,
        "baseline": args.baseline,
        "source_readiness_dir": str(readiness_dir),
        "source_case_file": str(case_file),
        "case_count": len(case_rows),
        "planned_new_cohere_calls": planned_calls,
        "max_new_cohere_calls": int(args.max_new_cohere_calls),
        "external_l1_reused": bool(args.reuse_external_l1),
        "external_l1_source_paths": [str(p) for p in external_paths],
        "targeted_retry_model_settings": {
            "model": args.model,
            "temperature": float(args.temperature),
            "max_tokens": int(args.max_tokens),
        },
        "scoring_is_offline": True,
        "no_gold_in_runtime": True,
        "no_api_calls": bool(args.dry_run_only),
        "abort_conditions": [
            "missing COHERE_API_KEY when dry_run_only=false",
            "missing external_l1 path when reuse-external-l1 is set",
            "planned calls exceed max-new-cohere-calls",
            "missing targeted retry prompt file",
            "gold leakage found in prompt",
            "unsupported targeted scaffold",
        ],
    }
    (out / "stage_checkpoint_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    selected_rows: list[dict[str, Any]] = []
    for row in case_rows:
        cid = str(row.get("case_id") or "")
        action = str(row.get("planned_integrated_action") or row.get("planned_action") or "unknown")
        pm = prompt_map.get(cid, {})
        selected_rows.append(
            {
                **row,
                "planned_action": action,
                "expected_new_cohere_call": str(row.get("expected_new_cohere_calls") or row.get("expected_new_cohere_call") or "0"),
                "prompt_path": str(pm.get("prompt_path") or ""),
                "prompt_version": str(pm.get("prompt_version") or ""),
                "scaffold": str(pm.get("scaffold") or ""),
                "notes": str(row.get("notes") or ""),
            }
        )
    selected_fields = list(selected_rows[0].keys())
    _write_csv(out / "selected_stage_cases.csv", selected_fields, selected_rows)

    results: list[dict[str, Any]] = []
    api_errors: list[str] = []
    parsing_ambiguities = 0
    calls_made = 0
    for row in case_rows:
        cid = str(row.get("case_id") or "")
        gold = str(row.get("gold_answer") or "")
        ext_pred = str(row.get("external_l1_prediction") or "")
        ext_correct = str(row.get("external_l1_correct") or "")
        pal_pred = str(row.get("current_pal_prediction") or row.get("baseline_pal_prediction") or "")
        pal_correct = str(row.get("current_pal_correct") or row.get("baseline_pal_correct") or "")
        action = str(row.get("planned_integrated_action") or row.get("planned_action") or "unknown")
        integrated_action = "base_method_no_retry"
        if action == "targeted_retry":
            integrated_action = "targeted_retry"
        elif action in {"structural_commit_only", "structural_commit"}:
            integrated_action = "structural_commit"
        integrated_pred = pal_pred
        cohere_call_made = "no"
        response_text_path = ""
        notes = ""

        if action == "targeted_retry" and preflight_ok and not args.dry_run_only:
            pm = prompt_map.get(cid)
            if pm is not None:
                pp = Path(pm["prompt_abspath"])
                prompt = pp.read_text(encoding="utf-8")
                out_path = responses_dir / f"{cid}.txt"
                try:
                    text = _cohere_chat(prompt, model=args.model, temperature=float(args.temperature), max_tokens=int(args.max_tokens))
                    out_path.write_text(text, encoding="utf-8")
                    response_text_path = str(out_path.relative_to(out)).replace("\\", "/")
                    parsed = _norm_num(text)
                    if parsed:
                        integrated_pred = parsed
                    else:
                        parsing_ambiguities += 1
                        notes = "parse_ambiguous_or_empty"
                    calls_made += 1
                    cohere_call_made = "yes"
                except Exception as exc:  # noqa: BLE001
                    api_errors.append(f"{cid}: {type(exc).__name__}: {exc}")
                    out_path.write_text("", encoding="utf-8")
                    response_text_path = str(out_path.relative_to(out)).replace("\\", "/")
                    notes = f"api_error:{type(exc).__name__}"
                    cohere_call_made = "yes"
            else:
                notes = "missing_prompt_map_entry"
        elif action == "targeted_retry" and args.dry_run_only:
            notes = "dry_run_no_api_call"
        elif action == "targeted_retry" and not preflight_ok:
            notes = "preflight_failed_no_api_call"

        goldn = _norm_num(gold)
        intn = _norm_num(integrated_pred)
        integrated_correct = "1" if (goldn and intn and goldn == intn) else "0"

        results.append(
            {
                "case_id": cid,
                "gold_answer": gold,
                "external_l1_prediction": ext_pred,
                "external_l1_correct": ext_correct,
                "baseline_pal_prediction": pal_pred,
                "baseline_pal_correct": pal_correct,
                "integrated_prediction": integrated_pred,
                "integrated_correct": integrated_correct,
                "integrated_action": integrated_action,
                "cohere_call_made": cohere_call_made,
                "response_text_path": response_text_path,
                "notes": notes,
            }
        )
    _write_csv(out / "stage_checkpoint_results.csv", list(results[0].keys()), results)

    ext_correct_count = sum(1 for r in results if str(r["external_l1_correct"]) in {"1", "true", "True", "yes"})
    pal_correct_count = sum(1 for r in results if str(r["baseline_pal_correct"]) in {"1", "true", "True", "yes"})
    int_correct_count = sum(1 for r in results if str(r["integrated_correct"]) in {"1", "true", "True", "yes"})
    external_only = 0
    integrated_only = 0
    both_correct = 0
    both_wrong = 0
    for r in results:
        e = str(r["external_l1_correct"]) in {"1", "true", "True", "yes"}
        i = str(r["integrated_correct"]) in {"1", "true", "True", "yes"}
        if e and i:
            both_correct += 1
        elif e and not i:
            external_only += 1
        elif i and not e:
            integrated_only += 1
        else:
            both_wrong += 1

    summary = {
        "stage_name": args.stage_name,
        "case_count": len(results),
        "actual_new_cohere_calls": calls_made,
        "external_l1_correct_count": ext_correct_count,
        "baseline_pal_correct_count": pal_correct_count,
        "integrated_correct_count": int_correct_count,
        "integrated_minus_external_l1": int_correct_count - ext_correct_count,
        "integrated_minus_baseline_pal": int_correct_count - pal_correct_count,
        "paired_external_l1_only": external_only,
        "paired_integrated_only": integrated_only,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "mcnemar_inputs": {
            "external_correct_integrated_wrong": external_only,
            "integrated_correct_external_wrong": integrated_only,
        },
        "api_errors": api_errors,
        "parsing_ambiguities": parsing_ambiguities,
        "no_api_calls": bool(args.dry_run_only),
    }
    (out / "stage_checkpoint_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report_lines = [
        f"# Integrated checkpoint: {args.stage_name}",
        "",
        f"- Case file: `{case_file}`",
        f"- Cases: {len(results)}",
        f"- Planned new calls: {planned_calls}",
        f"- Actual new calls: {calls_made}",
        f"- Dry-run only: {args.dry_run_only}",
        "",
        "## Scoreboard",
        f"- external_l1_correct: {ext_correct_count}/{len(results)}",
        f"- baseline_pal_correct: {pal_correct_count}/{len(results)}",
        f"- integrated_correct: {int_correct_count}/{len(results)}",
        f"- integrated_minus_external_l1: {int_correct_count - ext_correct_count}",
        f"- integrated_minus_baseline_pal: {int_correct_count - pal_correct_count}",
        f"- paired_integrated_only: {integrated_only}",
        f"- paired_external_l1_only: {external_only}",
        "",
        "## Preflight",
        f"- preflight_ok: {preflight_ok}",
        f"- planned_calls_ok: {preflight['planned_calls_ok']}",
        f"- targeted_prompt_files_ok: {preflight['targeted_prompt_files_ok']}",
        f"- no_ascii_gold_in_prompts: {preflight['no_ascii_gold_in_prompts']}",
    ]
    (out / "stage_checkpoint_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
