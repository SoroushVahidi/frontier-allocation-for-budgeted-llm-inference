from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _to_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def _to_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _safe_metadata(row: dict[str, Any]) -> dict[str, Any]:
    # New evaluator records store controller metadata under result_metadata.
    md = row.get("result_metadata")
    if isinstance(md, dict) and md:
        return md
    # Fallback for older artifacts that used metadata directly.
    md2 = row.get("metadata")
    return md2 if isinstance(md2, dict) else {}


def materialize_pal_smoke(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    records_path = input_dir / "per_example_records.jsonl"
    selected_cases_path = input_dir / "selected_cases.csv"
    old_summary_path = input_dir / "pal_summary.json"
    old_casebook_path = input_dir / "pal_casebook.csv"

    records = _read_jsonl(records_path)
    selected_cases = _read_csv(selected_cases_path)
    old_summary = _read_json(old_summary_path) if old_summary_path.exists() else {}
    old_casebook = _read_csv(old_casebook_path) if old_casebook_path.exists() else []

    method = ""
    for r in records:
        if str(r.get("method") or "").endswith("_pal"):
            method = str(r.get("method") or "")
            break
    if not method:
        raise ValueError("No PAL method rows found in per_example_records.jsonl")

    rows = [r for r in records if str(r.get("method") or "") == method]
    order = {str(r.get("example_id") or ""): i for i, r in enumerate(selected_cases)}
    rows.sort(key=lambda r: order.get(str(r.get("example_id") or ""), 10**9))
    bucket_by_id = {str(r.get("example_id") or ""): str(r.get("bucket") or "") for r in selected_cases}

    per_case: list[dict[str, Any]] = []
    err_hist: Counter[str] = Counter()
    calls = 0
    exact = 0
    gold_in_tree = 0
    parse_fail = 0
    pal_seed_ran = 0
    pal_code_present = 0
    pal_parse_ok = 0
    pal_safety_ok = 0
    pal_exec_ok = 0
    pal_strong = 0
    pal_overlay = 0
    raw_non_null = 0

    for r in rows:
        md = _safe_metadata(r)
        pal_exec = md.get("pal_execution") if isinstance(md.get("pal_execution"), dict) else {}
        pal_overlay_md = md.get("pal_overlay") if isinstance(md.get("pal_overlay"), dict) else {}
        exid = str(r.get("example_id") or "")

        code_present = int(bool(str(pal_exec.get("pal_code") or "").strip()))
        json_answer_present = int(bool(str(pal_exec.get("pal_json_answer") or "").strip()))
        conf_present = int(pal_exec.get("pal_confidence") is not None and str(pal_exec.get("pal_confidence")).strip() != "")
        p_parse = int(bool(pal_exec.get("pal_parse_ok")))
        p_safety = int(bool(pal_exec.get("pal_safety_ok")))
        p_exec = int(bool(pal_exec.get("pal_exec_ok")))
        p_stdout = int(bool(str((pal_exec.get("pal_execution_result") or {}).get("pal_stdout") or "").strip()))
        p_raw = str((pal_exec.get("pal_execution_result") or {}).get("pal_answer_raw") or "")
        p_norm = str((pal_exec.get("pal_execution_result") or {}).get("pal_answer_normalized") or "")
        p_err = str((pal_exec.get("pal_execution_result") or {}).get("pal_error_type") or "")
        p_strong = int(bool(pal_exec.get("pal_candidate_is_strong")))
        p_overlay = int(bool(pal_overlay_md.get("pal_overlay_applied")))
        p_seed = _to_int(md.get("pal_seed_ran"))

        if p_err:
            err_hist[p_err] += 1
        calls += _to_int(r.get("cohere_logical_api_calls"))
        exact += _to_int(r.get("exact_match"))
        gold_in_tree += _to_int(r.get("gold_in_tree"))
        parse_fail += _to_int(r.get("parse_extraction_failure"))
        pal_seed_ran += p_seed
        pal_code_present += code_present
        pal_parse_ok += p_parse
        pal_safety_ok += p_safety
        pal_exec_ok += p_exec
        pal_strong += p_strong
        pal_overlay += p_overlay
        raw_non_null += int(bool(p_raw.strip()))

        per_case.append(
            {
                "example_id": exid,
                "bucket": bucket_by_id.get(exid, ""),
                "pal_seed_ran": p_seed,
                "pal_budget_cost_planned": _to_int(md.get("pal_budget_cost_planned")),
                "pal_budget_cost_observed": _to_int(md.get("pal_budget_cost_observed")),
                "frontier_budget_before_pal": _to_int(md.get("frontier_budget_before_pal")),
                "frontier_budget_after_pal": _to_int(md.get("frontier_budget_after_pal")),
                "pal_code_present": code_present,
                "pal_json_answer_present": json_answer_present,
                "pal_confidence_present": conf_present,
                "pal_parse_ok": p_parse,
                "pal_safety_ok": p_safety,
                "pal_exec_ok": p_exec,
                "pal_stdout_present": p_stdout,
                "pal_answer_raw": p_raw,
                "pal_answer_normalized": p_norm,
                "pal_error_type": p_err,
                "pal_candidate_strong": p_strong,
                "pal_overlay_triggered": p_overlay,
                "pal_enabled": bool(md.get("pal_enabled")),
                "exact_match": _to_int(r.get("exact_match")),
                "gold_in_tree": _to_int(r.get("gold_in_tree")),
                "parse_extraction_failure": _to_int(r.get("parse_extraction_failure")),
            }
        )

    n = len(per_case)
    rate = (lambda x: (float(x) / n) if n else 0.0)
    corrected_summary = {
        "method": method,
        "cases": n,
        "cohere_logical_calls_used": calls,
        "exact_accuracy": {"num": exact, "den": n, "rate": rate(exact)},
        "gold_in_tree": {"num": gold_in_tree, "den": n, "rate": rate(gold_in_tree)},
        "parse_extraction_failure_count": parse_fail,
        "final_answer_raw_non_null": {"num": raw_non_null, "den": n, "rate": rate(raw_non_null)},
        "pal_seed_ran": {"num": pal_seed_ran, "den": n, "rate": rate(pal_seed_ran)},
        "pal_parse_ok": {"num": pal_parse_ok, "den": n, "rate": rate(pal_parse_ok)},
        "pal_safety_ok": {"num": pal_safety_ok, "den": n, "rate": rate(pal_safety_ok)},
        "pal_exec_ok": {"num": pal_exec_ok, "den": n, "rate": rate(pal_exec_ok)},
        "pal_candidate_strong_count": pal_strong,
        "pal_overlay_triggered_count": pal_overlay,
        "pal_error_type_histogram": dict(err_hist),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "corrected_pal_casebook.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_case[0].keys()) if per_case else [])
        if per_case:
            w.writeheader()
            w.writerows(per_case)

    (output_dir / "corrected_pal_summary.json").write_text(
        json.dumps(corrected_summary, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "corrected_pal_report.md").write_text(
        "\n".join(
            [
                "# Corrected PAL Smoke Report",
                "",
                f"- Input: `{input_dir}`",
                f"- Cases: **{n}**",
                f"- Calls: **{calls}**",
                f"- Exact: **{exact}/{n}**",
                f"- PAL seed ran: **{pal_seed_ran}/{n}**",
                f"- PAL parse/safety/exec: **{pal_parse_ok}/{n}**, **{pal_safety_ok}/{n}**, **{pal_exec_ok}/{n}**",
                f"- PAL candidate strong: **{pal_strong}**",
                f"- PAL overlay triggered: **{pal_overlay}**",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    old = old_summary if isinstance(old_summary, dict) else {}
    old_seed = _to_int(((old.get("pal_seed_ran") or {}).get("num")))
    old_parse = _to_int(((old.get("pal_parse_ok") or {}).get("num")))
    old_safety = _to_int(((old.get("pal_safety_ok") or {}).get("num")))
    old_exec = _to_int(((old.get("pal_exec_ok") or {}).get("num")))
    old_strong = _to_int(old.get("pal_candidate_strong_count"))
    old_overlay = _to_int(old.get("pal_overlay_triggered_count"))
    old_exact = _to_int(((old.get("exact_accuracy") or {}).get("num")))
    old_gold = _to_int(((old.get("gold_in_tree") or {}).get("num")))

    correction_manifest = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "metadata_resolution_rule": "prefer result_metadata, fallback metadata",
        "old_vs_corrected": {
            "pal_seed_ran": {"old": old_seed, "corrected": pal_seed_ran},
            "pal_parse_ok": {"old": old_parse, "corrected": pal_parse_ok},
            "pal_safety_ok": {"old": old_safety, "corrected": pal_safety_ok},
            "pal_exec_ok": {"old": old_exec, "corrected": pal_exec_ok},
            "pal_candidate_strong_count": {"old": old_strong, "corrected": pal_strong},
            "pal_overlay_triggered_count": {"old": old_overlay, "corrected": pal_overlay},
            "exact_accuracy_num": {"old": old_exact, "corrected": exact},
            "gold_in_tree_num": {"old": old_gold, "corrected": gold_in_tree},
        },
        "old_casebook_rows": len(old_casebook),
        "corrected_casebook_rows": len(per_case),
    }
    (output_dir / "correction_manifest.json").write_text(
        json.dumps(correction_manifest, indent=2) + "\n", encoding="utf-8"
    )
    return corrected_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize corrected PAL smoke summary from per-example records.")
    parser.add_argument("--input-dir", required=True, help="Existing PAL smoke output directory")
    parser.add_argument("--output-dir", required=True, help="Corrected output directory")
    args = parser.parse_args()
    summary = materialize_pal_smoke(Path(args.input_dir), Path(args.output_dir))
    print(
        f"corrected_cases={summary['cases']} pal_seed_ran={summary['pal_seed_ran']['num']} "
        f"pal_exec_ok={summary['pal_exec_ok']['num']}"
    )


if __name__ == "__main__":
    main()
