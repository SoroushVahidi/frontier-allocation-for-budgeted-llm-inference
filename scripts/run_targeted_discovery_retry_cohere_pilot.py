#!/usr/bin/env python3
"""Run a capped Cohere pilot for targeted discovery retry v1 (max 10 calls)."""

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

REPO = Path(__file__).resolve().parents[1]
ANCHOR_PREF = [
    "openai_gsm8k_720",
    "openai_gsm8k_750",
    "openai_gsm8k_841",
    "openai_gsm8k_906",
    "openai_gsm8k_1003",
    "openai_gsm8k_1099",
    "openai_gsm8k_864",
    "openai_gsm8k_818",
    "openai_gsm8k_1166",
    "openai_gsm8k_970",
]
SCAFFOLD_TARGETS = {
    "quantity_ledger": 3,
    "rate_table": 3,
    "before_after_state": 2,
    "target_difference": 2,
}
MAX_CALLS = 10


def _load_cases(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _select_balanced(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_id = {r["case_id"]: r for r in rows}
    selected: list[dict[str, str]] = []
    used: set[str] = set()
    counts = Counter()

    # First pass: anchor preference where scaffold still needs quota.
    for cid in ANCHOR_PREF:
        r = by_id.get(cid)
        if r is None:
            continue
        sc = str(r.get("selected_scaffold") or "")
        if sc not in SCAFFOLD_TARGETS:
            continue
        if counts[sc] >= SCAFFOLD_TARGETS[sc]:
            continue
        if cid in used:
            continue
        selected.append(r)
        used.add(cid)
        counts[sc] += 1

    # Fill remaining from earliest rows in CSV order.
    for r in rows:
        cid = r["case_id"]
        sc = str(r.get("selected_scaffold") or "")
        if cid in used or sc not in SCAFFOLD_TARGETS:
            continue
        if counts[sc] >= SCAFFOLD_TARGETS[sc]:
            continue
        selected.append(r)
        used.add(cid)
        counts[sc] += 1
        if len(selected) == MAX_CALLS:
            break

    if len(selected) != MAX_CALLS:
        raise RuntimeError(f"Selection failed: expected 10 rows, got {len(selected)}")
    if any(counts[k] != v for k, v in SCAFFOLD_TARGETS.items()):
        raise RuntimeError(f"Selection not balanced as requested: {dict(counts)}")
    return selected


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
            text = getattr(part, "text", "")
            if text:
                out += str(text)
    return out.strip()


def _normalize_answer(text: str) -> str:
    """Conservative numeric parser from final answer text."""
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run-dir",
        type=Path,
        default=REPO / "outputs/targeted_discovery_retry_v1_dry_run_20260508T010738Z",
    )
    ap.add_argument("--model", default="command-a-03-2025")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=700)
    args = ap.parse_args()

    dry = args.dry_run_dir.resolve()
    cases_csv = dry / "targeted_retry_cases.csv"
    if not cases_csv.is_file():
        raise SystemExit(f"missing {cases_csv}")
    all_rows = _load_cases(cases_csv)
    selected = _select_balanced(all_rows)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO / "outputs" / f"targeted_discovery_retry_v1_cohere_pilot_{ts}"
    responses_dir = out_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    scaffold_counts = Counter(str(r.get("selected_scaffold") or "") for r in selected)
    prompt_paths = [str(r["prompt_path"]) for r in selected]
    selected_ids = [r["case_id"] for r in selected]

    manifest: dict[str, Any] = {
        "timestamp": ts,
        "source_dry_run_dir": str(dry.relative_to(REPO)),
        "selected_case_count": len(selected),
        "selected_case_ids": selected_ids,
        "scaffold_counts": dict(scaffold_counts),
        "max_cohere_calls": MAX_CALLS,
        "planned_cohere_calls": len(selected),
        "model_name": args.model,
        "temperature": float(args.temperature),
        "max_tokens": int(args.max_tokens),
        "no_gold_in_prompts_verified": False,
        "abort_conditions": [
            "COHERE_API_KEY missing",
            "any prompt missing",
            "ASCII gold answer appears in prompt",
            "planned calls exceeds max_cohere_calls",
            "cohere client init/call fails before first successful call",
        ],
        "prompt_paths": prompt_paths,
        "scoring_is_offline": True,
    }

    preflight = {
        "cohere_api_key_set": bool(os.getenv("COHERE_API_KEY")),
        "selected_case_count_ok": len(selected) == 10,
        "planned_calls_ok": len(selected) <= MAX_CALLS,
        "prompt_files_ok": True,
        "no_ascii_gold_in_prompts": True,
        "missing_prompt_paths": [],
        "gold_leak_case_ids": [],
        "will_call_api": False,
    }
    for r in selected:
        pp = dry / r["prompt_path"]
        if not pp.is_file():
            preflight["prompt_files_ok"] = False
            preflight["missing_prompt_paths"].append(str(pp))
            continue
        prompt = pp.read_text(encoding="utf-8")
        gold = str(r.get("gold_answer") or "").strip()
        if gold and gold in prompt:
            preflight["no_ascii_gold_in_prompts"] = False
            preflight["gold_leak_case_ids"].append(r["case_id"])
    manifest["no_gold_in_prompts_verified"] = bool(preflight["no_ascii_gold_in_prompts"])
    (out_dir / "pilot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "preflight_status.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")

    # Always save selected_pilot_cases.csv before potential abort.
    with (out_dir / "selected_pilot_cases.csv").open("w", encoding="utf-8", newline="") as f:
        fields = [
            "case_id",
            "scaffold",
            "prompt_path",
            "gold_answer",
            "current_pal_prediction",
            "external_prediction_if_available",
            "problem_text",
            "source_artifacts",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in selected:
            w.writerow(
                {
                    "case_id": r["case_id"],
                    "scaffold": r["selected_scaffold"],
                    "prompt_path": r["prompt_path"],
                    "gold_answer": r.get("gold_answer", ""),
                    "current_pal_prediction": r.get("current_pal_prediction", ""),
                    "external_prediction_if_available": r.get("external_prediction_if_available", ""),
                    "problem_text": r.get("problem_text", ""),
                    "source_artifacts": r.get("source_artifacts", ""),
                }
            )

    if not (
        preflight["cohere_api_key_set"]
        and preflight["selected_case_count_ok"]
        and preflight["planned_calls_ok"]
        and preflight["prompt_files_ok"]
        and preflight["no_ascii_gold_in_prompts"]
    ):
        (out_dir / "pilot_results.csv").write_text(
            "case_id,scaffold,prompt_path,cohere_call_index,response_text_path,parsed_final_answer,gold_answer,exact_match,current_pal_prediction,external_prediction_if_available,improved_over_current_pal,notes\n",
            encoding="utf-8",
        )
        (out_dir / "pilot_report.md").write_text(
            "# Targeted discovery retry v1 Cohere pilot\n\nPreflight failed; no Cohere calls were made.\n",
            encoding="utf-8",
        )
        print(out_dir)
        return

    preflight["will_call_api"] = True
    (out_dir / "preflight_status.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")

    results: list[dict[str, Any]] = []
    api_errors: list[str] = []
    calls_made = 0
    for idx, r in enumerate(selected, start=1):
        if calls_made >= MAX_CALLS:
            break
        case_id = r["case_id"]
        scaffold = r["selected_scaffold"]
        prompt_path = dry / r["prompt_path"]
        prompt = prompt_path.read_text(encoding="utf-8")
        response_path = responses_dir / f"{case_id}.txt"
        notes = ""
        try:
            text = _cohere_chat(
                prompt,
                model=args.model,
                temperature=float(args.temperature),
                max_tokens=int(args.max_tokens),
            )
            calls_made += 1
            response_path.write_text(text, encoding="utf-8")
            parsed = _normalize_answer(text)
        except Exception as exc:  # noqa: BLE001
            if calls_made == 0:
                raise SystemExit(f"Cohere failed before any successful call: {type(exc).__name__}: {exc}") from exc
            api_errors.append(f"{case_id}: {type(exc).__name__}: {exc}")
            response_path.write_text("", encoding="utf-8")
            parsed = ""
            notes = f"api_error:{type(exc).__name__}"

        gold = str(r.get("gold_answer") or "").strip()
        gold_norm = _normalize_answer(gold) if gold else ""
        exact = bool(parsed and gold_norm and parsed == gold_norm)
        pal_pred = str(r.get("current_pal_prediction") or "").strip()
        pal_norm = _normalize_answer(pal_pred) if pal_pred else ""
        improved = "unknown"
        if parsed and gold_norm and pal_norm:
            improved = "yes" if (parsed == gold_norm and pal_norm != gold_norm) else "no"
        elif parsed and gold_norm and not pal_norm:
            improved = "yes" if parsed == gold_norm else "unknown"

        if not parsed and not notes:
            notes = "parse_ambiguous_or_empty"

        results.append(
            {
                "case_id": case_id,
                "scaffold": scaffold,
                "prompt_path": r["prompt_path"],
                "cohere_call_index": idx if response_path.exists() else "",
                "response_text_path": str(Path("responses") / f"{case_id}.txt"),
                "parsed_final_answer": parsed,
                "gold_answer": gold,
                "exact_match": str(exact).lower(),
                "current_pal_prediction": pal_pred,
                "external_prediction_if_available": str(r.get("external_prediction_if_available") or ""),
                "improved_over_current_pal": improved,
                "notes": notes,
            }
        )

    with (out_dir / "pilot_results.csv").open("w", encoding="utf-8", newline="") as f:
        fields = [
            "case_id",
            "scaffold",
            "prompt_path",
            "cohere_call_index",
            "response_text_path",
            "parsed_final_answer",
            "gold_answer",
            "exact_match",
            "current_pal_prediction",
            "external_prediction_if_available",
            "improved_over_current_pal",
            "notes",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in results:
            w.writerow(row)

    exact_hits = sum(1 for r in results if str(r.get("exact_match")) == "true")
    improved_hits = sum(1 for r in results if str(r.get("improved_over_current_pal")) == "yes")
    by_scaffold: dict[str, dict[str, int]] = {}
    for sc in SCAFFOLD_TARGETS:
        rr = [r for r in results if r.get("scaffold") == sc]
        by_scaffold[sc] = {
            "cases": len(rr),
            "exact_match": sum(1 for x in rr if x.get("exact_match") == "true"),
            "improved_over_pal": sum(1 for x in rr if x.get("improved_over_current_pal") == "yes"),
            "parse_or_api_issues": sum(1 for x in rr if "api_error" in str(x.get("notes")) or "parse_" in str(x.get("notes"))),
        }

    manifest["actual_cohere_calls"] = calls_made
    (out_dir / "pilot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_lines = [
        "# Targeted discovery retry v1 Cohere pilot",
        "",
        f"- Output dir: `{out_dir.relative_to(REPO)}`",
        f"- Selected cases: {len(selected)}",
        f"- Scaffold counts: {dict(scaffold_counts)}",
        f"- Cohere calls made: {calls_made}",
        f"- Exact matches: {exact_hits}/{len(selected)}",
        f"- Improved over current PAL: {improved_hits}/{len(selected)}",
        "",
        "## Selected cases",
        ", ".join(selected_ids),
        "",
        "## Results by scaffold",
        "```json",
        json.dumps(by_scaffold, indent=2),
        "```",
        "",
        "## Parsing ambiguities / API errors",
        "```json",
        json.dumps({"api_errors": api_errors, "ambiguous_parse_cases": [r["case_id"] for r in results if r["notes"] == "parse_ambiguous_or_empty"]}, indent=2),
        "```",
        "",
    ]
    if api_errors:
        recommendation = "revise prompts / error handling before expanding pilot"
    elif exact_hits >= 6:
        recommendation = "continue with a slightly larger capped pilot"
    elif exact_hits >= 3:
        recommendation = "revise prompts per weakest scaffold, then re-run 10-case cap"
    else:
        recommendation = "stop and perform more offline inspection"
    report_lines += ["## Recommendation", recommendation, ""]
    (out_dir / "pilot_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
