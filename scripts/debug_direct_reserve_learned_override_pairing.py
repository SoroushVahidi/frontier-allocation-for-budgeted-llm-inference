#!/usr/bin/env python3
"""Offline pairing diagnostics for direct-reserve learned override validation outputs."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_METHOD = "direct_reserve_strong_plus_diverse_v1"
LEARNED_METHOD = "direct_reserve_strong_plus_diverse_learned_override_v1"


def _path(text: str | Path) -> Path:
    p = Path(text)
    return p if p.is_absolute() else REPO_ROOT / p


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({key: row.get(key, "") for key in fields})


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (str(row.get("example_id", "")), _as_int(row.get("seed", 0)), _as_int(row.get("budget", 0)))


def _norm_answer(row: dict[str, str]) -> str:
    return str(row.get("normalized_selected_answer") or row.get("final_selected_answer") or "").strip()


def _candidate_signature(rows: list[dict[str, str]]) -> str:
    vals = sorted(str(r.get("answer_group") or r.get("normalized_candidate_answer") or "").strip() for r in rows)
    return json.dumps(vals, sort_keys=True)


def _candidate_set(rows: list[dict[str, str]]) -> set[str]:
    return {str(r.get("answer_group") or r.get("normalized_candidate_answer") or "").strip() for r in rows if str(r.get("answer_group") or r.get("normalized_candidate_answer") or "").strip()}


def _metadata_issue(row: dict[str, str]) -> str:
    required = (
        "base_selected_answer",
        "learned_selected_answer",
        "final_selected_answer_after_learned_override",
        "learned_override_triggered",
    )
    missing = [key for key in required if key not in row or str(row.get(key, "")).strip() == "" and key != "learned_selected_answer"]
    if missing:
        return "missing:" + ",".join(missing)
    triggered = _as_int(row.get("learned_override_triggered", 0))
    pre = str(row.get("base_selected_answer", "")).strip()
    learned = str(row.get("learned_selected_answer", "")).strip()
    final = str(row.get("final_selected_answer_after_learned_override", "")).strip()
    if triggered and learned and final != learned:
        return "triggered_final_not_learned"
    if not triggered and final != pre:
        return "no_trigger_final_not_base_selected_answer"
    return ""


def _mismatch_reason(
    *,
    base_row: dict[str, str],
    learned_row: dict[str, str],
    base_candidates: list[dict[str, str]],
    learned_candidates: list[dict[str, str]],
) -> str:
    issue = _metadata_issue(learned_row)
    if issue:
        return "metadata_missing" if issue.startswith("missing:") else "fallback_not_base_answer"
    if _candidate_signature(base_candidates) != _candidate_signature(learned_candidates):
        return "candidate_pool_differs"
    base_ans = _norm_answer(base_row)
    learned_pre = str(learned_row.get("base_selected_answer", "")).strip()
    learned_final = str(learned_row.get("final_selected_answer_after_learned_override", "")).strip() or _norm_answer(learned_row)
    if _as_int(learned_row.get("learned_override_triggered", 0)) == 0 and learned_final != learned_pre:
        return "fallback_not_base_answer"
    if base_ans != learned_pre:
        return "answer_normalization_diff"
    return ""


def build_debug(validation_output: Path, output_dir: Path, case_limit: int | None = None) -> dict[str, Any]:
    per_case = _read_csv(validation_output / "per_case_method_results.csv")
    candidates = _read_csv(validation_output / "candidate_branch_table.csv")
    groups = _read_csv(validation_output / "answer_group_summary.csv")

    base = {_key(r): r for r in per_case if r.get("method") == BASE_METHOD}
    learned = {_key(r): r for r in per_case if r.get("method") == LEARNED_METHOD}
    keys = sorted(set(base) | set(learned))
    if case_limit is not None:
        keys = keys[: max(0, int(case_limit))]

    cand_by: dict[tuple[str, int, int, str], list[dict[str, str]]] = {}
    for row in candidates:
        cand_by.setdefault((*_key(row), str(row.get("method", ""))), []).append(row)
    group_by: dict[tuple[str, int, int, str], list[dict[str, str]]] = {}
    for row in groups:
        group_by.setdefault((*_key(row), str(row.get("method", ""))), []).append(row)

    per_case_rows: list[dict[str, Any]] = []
    pool_diff_rows: list[dict[str, Any]] = []
    fallback_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []

    for key in keys:
        b = base.get(key, {})
        l = learned.get(key, {})
        bc = cand_by.get((*key, BASE_METHOD), [])
        lc = cand_by.get((*key, LEARNED_METHOD), [])
        bg = group_by.get((*key, BASE_METHOD), [])
        lg = group_by.get((*key, LEARNED_METHOD), [])
        base_sig = _candidate_signature(bc)
        learned_sig = _candidate_signature(lc)
        pool_equal = int(base_sig == learned_sig)
        metadata_issue = _metadata_issue(l)
        mismatch = _mismatch_reason(base_row=b, learned_row=l, base_candidates=bc, learned_candidates=lc)
        triggered = _as_int(l.get("learned_override_triggered", 0))
        learned_pre = str(l.get("base_selected_answer", "")).strip()
        learned_final = str(l.get("final_selected_answer_after_learned_override", "")).strip() or _norm_answer(l)
        row = {
            "example_id": key[0],
            "seed": key[1],
            "budget": key[2],
            "base_selected_answer": _norm_answer(b),
            "learned_method_final_selected_answer": _norm_answer(l),
            "learned_method_base_selected_answer_metadata": learned_pre,
            "learned_method_learned_selected_answer_metadata": l.get("learned_selected_answer", ""),
            "learned_method_final_selected_answer_metadata": learned_final,
            "learned_override_triggered": triggered,
            "fallback_should_match_base_selected_answer": int(triggered == 0),
            "fallback_matches_base_selected_answer": int(triggered == 0 and learned_final == learned_pre),
            "base_candidate_count": len(bc),
            "learned_candidate_count": len(lc),
            "base_answer_group_count": len(bg),
            "learned_answer_group_count": len(lg),
            "base_candidate_answer_set": json.dumps(sorted(_candidate_set(bc)), sort_keys=True),
            "learned_candidate_answer_set": json.dumps(sorted(_candidate_set(lc)), sort_keys=True),
            "candidate_pool_equal": pool_equal,
            "mismatch_reason": mismatch or "none",
            "metadata_issue": metadata_issue,
        }
        per_case_rows.append(row)
        if not pool_equal:
            pool_diff_rows.append(row)
        if triggered == 0 and learned_final != learned_pre:
            fallback_rows.append(row)
        if metadata_issue:
            metadata_rows.append(row)

    reason_counts = Counter(str(r["mismatch_reason"]) for r in per_case_rows)
    summary = [
        {
            "validation_output": str(validation_output),
            "n_cases": len(per_case_rows),
            "candidate_pool_diff_count": len(pool_diff_rows),
            "fallback_mismatch_count": len(fallback_rows),
            "metadata_consistency_issue_count": len(metadata_rows),
            "unpaired_or_stochastic_candidate_pool_count": len(pool_diff_rows),
            "mismatch_reasons": json.dumps(dict(sorted(reason_counts.items())), sort_keys=True),
        }
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "summary.csv", summary)
    _write_csv(output_dir / "per_case_pairing.csv", per_case_rows)
    _write_csv(output_dir / "candidate_pool_diff.csv", pool_diff_rows)
    _write_csv(output_dir / "fallback_mismatch_cases.csv", fallback_rows)
    _write_csv(output_dir / "metadata_consistency_issues.csv", metadata_rows)
    (output_dir / "README.md").write_text(
        "# Direct-reserve learned override pairing debug\n\n"
        "Offline diagnostic comparing base plus-diverse and learned-override rows from an existing validation output. "
        "No API calls are made. Candidate-pool differences indicate unpaired stochastic generations, so base-vs-learned "
        "accuracy deltas should not be interpreted as selector effects unless candidate pools match.\n",
        encoding="utf-8",
    )
    return summary[0]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--validation-output", required=True)
    p.add_argument("--output-dir", default="")
    p.add_argument("--case-limit", type=int, default=0)
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = _path(args.output_dir) if args.output_dir else REPO_ROOT / "outputs" / f"direct_reserve_learned_override_pairing_debug_{args.timestamp}"
    summary = build_debug(
        validation_output=_path(args.validation_output),
        output_dir=out_dir,
        case_limit=args.case_limit if args.case_limit > 0 else None,
    )
    print(
        f"Wrote {out_dir} "
        f"candidate_pool_diff={summary['candidate_pool_diff_count']} "
        f"fallback_mismatch={summary['fallback_mismatch_count']} "
        f"metadata_issues={summary['metadata_consistency_issue_count']}"
    )


if __name__ == "__main__":
    main()
