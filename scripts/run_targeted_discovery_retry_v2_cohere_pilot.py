#!/usr/bin/env python3
"""Capped Cohere pilot for targeted discovery retry v2 (max 15 calls).

Uses frozen prompts from a targeted discovery retry v2 dry-run directory.
No HF downloads. Gold is used only after generation for scoring.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.data import extract_final_answer
from experiments.targeted_discovery_retry import validate_prompt_no_gold

REPO = Path(__file__).resolve().parents[1]

MODEL_DEFAULT = "command-a-03-2025"
MAX_CALLS = 15


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _normalize_numeric(text: str) -> str:
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
    if val.is_integer():
        return str(int(val))
    return f"{val:.10g}"


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
        for part in getattr(msg, "content"):
            t = getattr(part, "text", "")
            if t:
                out += str(t)
    return out.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run-dir",
        type=Path,
        default=REPO / "outputs/targeted_discovery_retry_v2_dry_run_20260508T013214Z",
    )
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=700)
    args = ap.parse_args()

    dry = args.dry_run_dir.resolve()
    cases_csv = dry / "targeted_retry_v2_cases.csv"
    if not cases_csv.is_file():
        raise SystemExit(f"missing {cases_csv}")
    cases = _read_csv(cases_csv)
    if not cases:
        raise SystemExit("no v2 cases")
    if len(cases) > MAX_CALLS:
        raise SystemExit(f"selected {len(cases)} cases > cap {MAX_CALLS}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO / f"outputs/targeted_discovery_retry_v2_cohere_pilot_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = out_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    # Save selected_pilot_cases.csv
    cases_selected_rows: list[dict[str, Any]] = []
    for r in cases:
        cases_selected_rows.append(
            {
                "case_id": r["case_id"],
                "scaffold": r["scaffold"],
                "prompt_version": r["prompt_version"],
                "prompt_path": r["prompt_path"],
                "gold_answer": r.get("gold_answer") or "",
                "current_pal_prediction": r.get("current_pal_prediction") or "",
                "external_prediction_if_available": r.get("external_prediction_if_available") or "",
                "problem_text": r.get("problem_text") or "",
                "source_artifacts": r.get("source_artifacts") or "",
            }
        )
    _write_selected = out_dir / "selected_pilot_cases.csv"
    with _write_selected.open("w", encoding="utf-8", newline="") as f:
        fields = list(cases_selected_rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in cases_selected_rows:
            w.writerow(row)

    # Preflight
    prompt_paths: list[str] = []
    for r in cases:
        prompt_paths.append(r["prompt_path"])

    preflight: dict[str, Any] = {
        "cohere_api_key_set": bool(os.getenv("COHERE_API_KEY")),
        "all_prompt_files_exist": True,
        "no_ascii_gold_in_prompts": True,
        "planned_calls_ok": True,
        "planned_calls": len(cases),
        "max_cohere_calls": MAX_CALLS,
        "missing_prompt_paths": [],
        "gold_leak_case_ids": [],
    }

    for r in cases:
        cid = r["case_id"]
        prompt_rel = r["prompt_path"]
        pp = dry / prompt_rel
        if not pp.is_file():
            preflight["all_prompt_files_exist"] = False
            preflight["missing_prompt_paths"].append(str(pp))
            continue
        gold = str(r.get("gold_answer") or "").strip()
        prompt = pp.read_text(encoding="utf-8")
        if gold and not validate_prompt_no_gold(prompt, gold):
            preflight["no_ascii_gold_in_prompts"] = False
            preflight["gold_leak_case_ids"].append(cid)

    preflight["planned_calls_ok"] = len(cases) <= MAX_CALLS

    preflight_ok = (
        preflight["cohere_api_key_set"]
        and preflight["all_prompt_files_exist"]
        and preflight["no_ascii_gold_in_prompts"]
        and preflight["planned_calls_ok"]
    )

    # prompt_versions_by_scaffold: scaffold -> prompt_version string
    prompt_versions_by_scaffold: dict[str, str] = {}
    for r in cases:
        sc = str(r.get("scaffold") or "")
        pv = str(r.get("prompt_version") or "")
        if sc in prompt_versions_by_scaffold and prompt_versions_by_scaffold[sc] != pv:
            # In this pilot, we expect only one prompt version per scaffold, but keep the first.
            continue
        prompt_versions_by_scaffold[sc] = pv

    manifest: dict[str, Any] = {
        "timestamp": ts,
        "source_v2_dry_run_dir": str(dry.relative_to(REPO)),
        "selected_case_count": len(cases),
        "selected_case_ids": [r["case_id"] for r in cases],
        "scaffold_counts": dict(Counter(str(r.get("scaffold") or "") for r in cases)),
        "max_cohere_calls": MAX_CALLS,
        "planned_cohere_calls": len(cases),
        "model": args.model,
        "temperature": float(args.temperature),
        "max_tokens": int(args.max_tokens),
        "no_gold_in_prompts_verified": bool(preflight["no_ascii_gold_in_prompts"]),
        "abort_conditions": [
            "COHERE_API_KEY missing",
            "any prompt missing",
            "ASCII gold answer appears in prompt",
            "planned calls exceeds cap",
        ],
        "prompt_versions_by_scaffold": prompt_versions_by_scaffold,
        "scoring_is_offline": True,
    }

    (out_dir / "pilot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "preflight_status.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")

    if not preflight_ok:
        # Write empty pilot_results and report; do not call Cohere.
        (out_dir / "pilot_results.csv").write_text(
            "case_id,scaffold,prompt_version,response_text_path,parsed_final_answer,gold_answer,exact_match,"
            "current_pal_prediction,improved_over_current_pal,prior_v1_status,notes\n",
            encoding="utf-8",
        )
        (out_dir / "pilot_report.md").write_text(
            "# Targeted discovery retry v2 Cohere pilot\n\nPreflight failed; no Cohere calls made.\n",
            encoding="utf-8",
        )
        print(out_dir)
        return

    # Run Cohere
    results: list[dict[str, Any]] = []
    api_errors: list[str] = []
    calls_made = 0
    for idx, r in enumerate(cases, start=1):
        if calls_made >= MAX_CALLS:
            break
        cid = r["case_id"]
        scaffold = r.get("scaffold") or ""
        prompt_rel = r["prompt_path"]
        prompt = (dry / prompt_rel).read_text(encoding="utf-8")
        resp_path = responses_dir / f"{cid}.txt"
        prior_status = r.get("prior_v1_pilot_status") or ""
        notes = ""
        parsed = ""
        exact = False
        try:
            text = _cohere_chat(
                prompt,
                model=args.model,
                temperature=float(args.temperature),
                max_tokens=int(args.max_tokens),
            )
            calls_made += 1
            resp_path.write_text(text, encoding="utf-8")
            parsed = _normalize_numeric(text)
        except Exception as exc:  # noqa: BLE001
            if calls_made == 0:
                raise SystemExit(f"Cohere failed before any successful call: {type(exc).__name__}: {exc}") from exc
            api_errors.append(f"{cid}: {type(exc).__name__}: {exc}")
            resp_path.write_text("", encoding="utf-8")
            parsed = ""
            notes = f"api_error:{type(exc).__name__}"

        gold = str(r.get("gold_answer") or "").strip()
        gold_norm = _normalize_numeric(gold)
        if parsed and gold_norm:
            exact = parsed == gold_norm

        pal_pred = str(r.get("current_pal_prediction") or "").strip()
        pal_norm = _normalize_numeric(pal_pred)
        improved = "unknown"
        if parsed and gold_norm and pal_norm:
            if parsed == gold_norm and pal_norm != gold_norm:
                improved = "yes"
            elif parsed == gold_norm and pal_norm == gold_norm:
                improved = "no"
        results.append(
            {
                "case_id": cid,
                "scaffold": scaffold,
                "prompt_version": r.get("prompt_version") or "",
                "response_text_path": str(resp_path.relative_to(out_dir)).replace("\\", "/"),
                "parsed_final_answer": parsed,
                "gold_answer": gold,
                "exact_match": str(exact).lower(),
                "current_pal_prediction": pal_pred,
                "improved_over_current_pal": improved,
                "prior_v1_status": prior_status,
                "notes": notes,
            }
        )

        if calls_made >= MAX_CALLS:
            break

    manifest["actual_cohere_calls"] = calls_made
    manifest["no_gold_in_prompts_verified"] = bool(preflight["no_ascii_gold_in_prompts"])
    (out_dir / "pilot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Write pilot_results.csv
    with (out_dir / "pilot_results.csv").open("w", encoding="utf-8", newline="") as f:
        fields = list(results[0].keys()) if results else [
            "case_id",
            "scaffold",
            "prompt_version",
            "response_text_path",
            "parsed_final_answer",
            "gold_answer",
            "exact_match",
            "current_pal_prediction",
            "improved_over_current_pal",
            "prior_v1_status",
            "notes",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in results:
            w.writerow(row)

    # Report
    by_scaffold: dict[str, dict[str, int]] = {}
    for sc in [str(r.get("scaffold") or "") for r in cases]:
        by_scaffold.setdefault(sc, {"cases": 0, "exact": 0, "improved": 0})
    for row in results:
        sc = row["scaffold"]
        by_scaffold.setdefault(sc, {"cases": 0, "exact": 0, "improved": 0})
        by_scaffold[sc]["cases"] += 1
        if row["exact_match"] == "true":
            by_scaffold[sc]["exact"] += 1
        if row["improved_over_current_pal"] == "yes":
            by_scaffold[sc]["improved"] += 1

    failed_qty_cases = ["openai_gsm8k_750", "openai_gsm8k_841"]
    qty_v2_fixed = {cid: False for cid in failed_qty_cases}
    for row in results:
        if row["case_id"] in qty_v2_fixed and row["exact_match"] == "true":
            qty_v2_fixed[row["case_id"]] = True

    exact_hits = sum(1 for r in results if r["exact_match"] == "true")
    improved_hits = sum(1 for r in results if r["improved_over_current_pal"] == "yes")

    report_lines = [
        "# Targeted discovery retry v2 Cohere pilot",
        "",
        f"- Output dir: `{out_dir.relative_to(REPO)}`",
        f"- Selected cases: {len(cases)}",
        f"- Scaffold counts: `{manifest['scaffold_counts']}`",
        f"- Cohere calls made: {calls_made}",
        f"- Exact matches: {exact_hits}/{len(cases)}",
        f"- Improved over current PAL: {improved_hits}/{len(cases)}",
        "",
        "## Results by scaffold",
        "```json",
        json.dumps(by_scaffold, indent=2),
        "```",
        "",
        "## quantity_ledger v2: did it fix v1 failures?",
        "```json",
        json.dumps(qty_v2_fixed, indent=2),
        "```",
        "",
        "## API/parsing errors",
        "```json",
        json.dumps({"api_errors": api_errors}, indent=2),
        "```",
        "",
        "## Recommendation",
        "Continue if both v1 quantity_ledger failures are fixed; otherwise revise quantity_ledger v2 prompt again.",
        "",
    ]
    (out_dir / "pilot_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()

