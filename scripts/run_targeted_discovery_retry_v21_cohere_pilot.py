#!/usr/bin/env python3
"""Capped Cohere pilot for targeted discovery retry v2.1 (<=10 calls)."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure repo root is importable when executed with system `python3`.
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.data import extract_final_answer
from experiments.targeted_discovery_retry import validate_prompt_no_gold


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


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
        default=None,
        help="v2.1 dry-run directory with targeted_retry_v21_cases.csv and prompts/...",
    )
    ap.add_argument("--model", default="command-a-03-2025")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=700)
    args = ap.parse_args()

    if args.dry_run_dir is None:
        raise SystemExit("--dry-run-dir is required")

    dry = args.dry_run_dir.resolve()
    cases_csv = dry / "targeted_retry_v21_cases.csv"
    if not cases_csv.is_file():
        raise SystemExit(f"missing {cases_csv}")
    cases = _read_csv_dicts(cases_csv)
    if not cases:
        raise SystemExit("no selected cases")
    if len(cases) > 10:
        raise SystemExit(f"selected {len(cases)} > 10 cap")

    # Preflight checks
    preflight: dict[str, Any] = {
        "cohere_api_key_set": bool(os.getenv("COHERE_API_KEY")),
        "all_prompt_files_exist": True,
        "no_ascii_gold_in_prompts": True,
        "planned_calls_ok": True,
        "missing_prompt_paths": [],
        "gold_leak_case_ids": [],
    }
    preflight["planned_calls_ok"] = len(cases) <= 10

    for r in cases:
        cid = str(r.get("case_id") or "")
        pp = dry / str(r.get("prompt_path") or "")
        if not pp.is_file():
            preflight["all_prompt_files_exist"] = False
            preflight["missing_prompt_paths"].append(str(pp))
            continue
        prompt = pp.read_text(encoding="utf-8")
        gold = str(r.get("gold_answer") or "").strip()
        if gold and not validate_prompt_no_gold(prompt, gold):
            preflight["no_ascii_gold_in_prompts"] = False
            preflight["gold_leak_case_ids"].append(cid)

    preflight_ok = (
        preflight["cohere_api_key_set"]
        and preflight["all_prompt_files_exist"]
        and preflight["no_ascii_gold_in_prompts"]
        and preflight["planned_calls_ok"]
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO / "outputs" / f"targeted_discovery_retry_v21_cohere_pilot_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = out_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "source_v2_dry_run_dir": str(dry.relative_to(REPO)),
        "selected_case_count": len(cases),
        "max_cohere_calls": 10,
        "planned_cohere_calls": len(cases),
        "model": args.model,
        "temperature": float(args.temperature),
        "max_tokens": int(args.max_tokens),
        "prompt_versions_by_scaffold": dict(Counter(str(r.get("prompt_version") or "") for r in cases)),
        "no_gold_in_prompts_verified": bool(preflight["no_ascii_gold_in_prompts"]),
        "abort_conditions": [
            "COHERE_API_KEY missing",
            "prompt missing",
            "ASCII gold appears in prompt",
            "planned calls exceeds cap",
        ],
        "scoring_is_offline": True,
    }
    (out_dir / "pilot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "preflight_status.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")

    # Save selected_pilot_cases.csv
    cases_out_rows: list[dict[str, Any]] = []
    for r in cases:
        cases_out_rows.append(
            {
                "case_id": r.get("case_id") or "",
                "scaffold": r.get("scaffold") or "",
                "prompt_version": r.get("prompt_version") or "",
                "prompt_path": r.get("prompt_path") or "",
                "gold_answer": r.get("gold_answer") or "",
                "current_pal_prediction": r.get("current_pal_prediction") or "",
                "external_prediction_if_available": r.get("external_prediction_if_available") or "",
                "problem_text": r.get("problem_text") or "",
                "source_artifacts": r.get("source_artifacts") or "",
            }
        )

    _write_csv(
        out_dir / "selected_pilot_cases.csv",
        [
            "case_id",
            "scaffold",
            "prompt_version",
            "prompt_path",
            "gold_answer",
            "current_pal_prediction",
            "external_prediction_if_available",
            "problem_text",
            "source_artifacts",
        ],
        cases_out_rows,
    )

    if not preflight_ok:
        _write_csv(
            out_dir / "pilot_results.csv",
            [
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
            ],
            [],
        )
        (out_dir / "pilot_report.md").write_text(
            "# Targeted discovery retry v2.1 Cohere pilot\n\nPreflight failed; no Cohere calls made.\n",
            encoding="utf-8",
        )
        print(out_dir)
        return

    # Load v2 pilot exact for regression checks (quantity_ledger only)
    v2_pilot = REPO / "outputs/targeted_discovery_retry_v2_cohere_pilot_20260508T013332Z/pilot_results.csv"
    v2_exact_qty: dict[str, bool] = {}
    if v2_pilot.is_file():
        for r in _read_csv_dicts(v2_pilot):
            if r.get("scaffold") == "quantity_ledger":
                v2_exact_qty[str(r.get("case_id") or "")] = str(r.get("exact_match") or "").lower() == "true"

    results: list[dict[str, Any]] = []
    api_errors: list[str] = []
    calls_made = 0

    for idx, r in enumerate(cases, start=1):
        if calls_made >= 10:
            break
        cid = str(r.get("case_id") or "").strip()
        scaffold = str(r.get("scaffold") or "").strip()
        pv = str(r.get("prompt_version") or "").strip()
        prompt_path = dry / str(r.get("prompt_path") or "")
        prompt = prompt_path.read_text(encoding="utf-8")
        resp_path = responses_dir / f"{cid}.txt"
        parsed = ""
        exact = False
        notes = ""

        try:
            response_text = _cohere_chat(
                prompt,
                model=args.model,
                temperature=float(args.temperature),
                max_tokens=int(args.max_tokens),
            )
            calls_made += 1
            resp_path.write_text(response_text, encoding="utf-8")
            parsed = _normalize_numeric(response_text)
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

        if not parsed and not notes:
            notes = "parse_ambiguous_or_empty"

        results.append(
            {
                "case_id": cid,
                "scaffold": scaffold,
                "prompt_version": pv,
                "response_text_path": str(resp_path.relative_to(out_dir)).replace("\\", "/"),
                "parsed_final_answer": parsed,
                "gold_answer": gold,
                "exact_match": str(exact).lower(),
                "current_pal_prediction": pal_pred,
                "improved_over_current_pal": improved,
                "prior_v1_status": r.get("prior_v1_pilot_status") or "",
                "notes": notes,
            }
        )

    # Write results
    _write_csv(
        out_dir / "pilot_results.csv",
        [
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
        ],
        results,
    )

    exact_hits = sum(1 for r in results if str(r.get("exact_match")) == "true")
    qty_v21_exact = sum(1 for r in results if r.get("scaffold") == "quantity_ledger" and str(r.get("exact_match")) == "true")
    qty_v21_total = sum(1 for r in results if r.get("scaffold") == "quantity_ledger")

    fixed_841 = any(r.get("case_id") == "openai_gsm8k_841" and str(r.get("exact_match")) == "true" for r in results)

    # Regressions on previous quantity_ledger successes (from v2 exact true)
    qty_regressions = [
        r["case_id"]
        for r in results
        if r.get("scaffold") == "quantity_ledger"
        and v2_exact_qty.get(str(r.get("case_id") or ""), False)
        and str(r.get("exact_match")) != "true"
    ]

    by_scaffold: dict[str, dict[str, int]] = {}
    for r in results:
        sc = str(r.get("scaffold") or "")
        by_scaffold.setdefault(sc, {"cases": 0, "exact": 0, "improved": 0})
        by_scaffold[sc]["cases"] += 1
        if str(r.get("exact_match")) == "true":
            by_scaffold[sc]["exact"] += 1
        if str(r.get("improved_over_current_pal")) == "yes":
            by_scaffold[sc]["improved"] += 1

    report = "\n".join(
        [
            "# Targeted discovery retry v2.1 Cohere pilot",
            "",
            f"- Output dir: `{out_dir.relative_to(REPO)}`",
            f"- Selected cases: {len(cases)}",
            f"- Cohere calls made: {calls_made}",
            f"- Exact matches: {exact_hits}/{len(results)}",
            f"- quantity_ledger v2.1 exact matches: {qty_v21_exact}/{qty_v21_total}",
            "",
            "## openai_gsm8k_841 fixed?",
            "yes" if fixed_841 else "no",
            "",
            "## quantity_ledger regressions (vs v2 exact successes)",
            ", ".join(qty_regressions) if qty_regressions else "(none)",
            "",
            "## Results by scaffold",
            "```json",
            json.dumps(by_scaffold, indent=2),
            "```",
            "",
            "## API/parsing errors",
            "```json",
            json.dumps({"api_errors": api_errors}, indent=2),
            "```",
            "",
            "## Recommendation",
            "If `openai_gsm8k_841` is fixed and no regressions, proceed to a larger capped pilot; otherwise revise quantity_ledger v2.1 recurrence rules.",
            "",
        ]
    )
    (out_dir / "pilot_report.md").write_text(report, encoding="utf-8")

    # Update manifest with actual calls
    manifest["actual_cohere_calls"] = calls_made
    (out_dir / "pilot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(out_dir)


if __name__ == "__main__":
    main()

