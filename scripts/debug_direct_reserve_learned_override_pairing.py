#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.direct_reserve_learned_override_utils import normalize_answer_set

BASE_METHOD = "direct_reserve_strong_plus_diverse_v1"
LEARNED_METHOD = "direct_reserve_strong_plus_diverse_learned_override_v1"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for r in rows:
            for k in r.keys():
                if k not in keys:
                    keys.append(str(k))
        fieldnames = keys or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def _case_key(r: dict[str, str]) -> tuple[str, str, str]:
    return (str(r.get("example_id", "")), str(r.get("seed", "")), str(r.get("budget", "")))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline pairing debug for direct-reserve learned override.")
    p.add_argument("--validation-output", required=True)
    p.add_argument("--output-dir", default="")
    p.add_argument("--case-limit", type=int, default=0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    validation = Path(args.validation_output)
    if not validation.is_absolute():
        validation = (REPO_ROOT / validation).resolve()
    if not validation.exists():
        raise SystemExit(f"validation output does not exist: {validation}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(args.output_dir)
        if args.output_dir
        else (REPO_ROOT / "outputs" / f"direct_reserve_learned_override_pairing_debug_{ts}")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    per_case = _read_csv(validation / "per_case_method_results.csv")
    branch_rows = _read_csv(validation / "candidate_branch_table.csv")
    group_rows = _read_csv(validation / "answer_group_summary.csv")
    _ = group_rows

    rows_by_method_case: dict[tuple[str, str, str, str], dict[str, str]] = {}
    all_cases: list[tuple[str, str, str]] = []
    for row in per_case:
        ck = _case_key(row)
        if ck not in all_cases:
            all_cases.append(ck)
        rows_by_method_case[(ck[0], ck[1], ck[2], str(row.get("method", "")))] = row
    if args.case_limit > 0:
        all_cases = all_cases[: args.case_limit]

    candidate_sets: dict[tuple[str, str, str, str], tuple[str, ...]] = defaultdict(tuple)
    branch_counts: Counter[tuple[str, str, str, str]] = Counter()
    for row in branch_rows:
        ck = _case_key(row)
        method = str(row.get("method", ""))
        key = (ck[0], ck[1], ck[2], method)
        ans = str(row.get("normalized_candidate_answer") or row.get("answer_group") or "").strip().lower()
        if ans:
            candidate_sets[key] = normalize_answer_set(list(candidate_sets[key]) + [ans])
        branch_counts[key] += 1

    per_case_pairing: list[dict[str, Any]] = []
    candidate_pool_diff: list[dict[str, Any]] = []
    fallback_mismatch: list[dict[str, Any]] = []
    metadata_issues: list[dict[str, Any]] = []
    mismatch_reasons: Counter[str] = Counter()

    for ck in all_cases:
        base = rows_by_method_case.get((ck[0], ck[1], ck[2], BASE_METHOD))
        learned = rows_by_method_case.get((ck[0], ck[1], ck[2], LEARNED_METHOD))
        if base is None or learned is None:
            metadata_issues.append(
                {
                    "example_id": ck[0],
                    "seed": ck[1],
                    "budget": ck[2],
                    "issue": "metadata_missing",
                    "detail": f"missing rows base={base is not None} learned={learned is not None}",
                }
            )
            mismatch_reasons["metadata_missing"] += 1
            continue

        base_final = str(base.get("final_selected_answer", ""))
        learned_final = str(learned.get("final_selected_answer", ""))
        learned_base_meta = str(learned.get("base_selected_answer", "")).strip()
        learned_sel_meta = str(learned.get("learned_selected_answer", "")).strip()
        triggered = str(learned.get("learned_override_triggered", "")).strip().lower() in {"1", "true", "yes"}

        base_set = candidate_sets.get((ck[0], ck[1], ck[2], BASE_METHOD), tuple())
        learned_set = candidate_sets.get((ck[0], ck[1], ck[2], LEARNED_METHOD), tuple())
        candidate_pool_equal = bool(base_set == learned_set and base_set)
        if not candidate_pool_equal:
            candidate_pool_diff.append(
                {
                    "example_id": ck[0],
                    "seed": ck[1],
                    "budget": ck[2],
                    "base_candidate_set": "|".join(base_set),
                    "learned_candidate_set": "|".join(learned_set),
                    "base_candidate_count": branch_counts.get((ck[0], ck[1], ck[2], BASE_METHOD), 0),
                    "learned_candidate_count": branch_counts.get((ck[0], ck[1], ck[2], LEARNED_METHOD), 0),
                }
            )

        fallback_should_match_base = not triggered
        fallback_mismatch_flag = bool(fallback_should_match_base and learned_final != base_final)
        if fallback_mismatch_flag:
            fallback_mismatch.append(
                {
                    "example_id": ck[0],
                    "seed": ck[1],
                    "budget": ck[2],
                    "base_final_answer": base_final,
                    "learned_final_answer": learned_final,
                    "learned_base_selected_answer_meta": learned_base_meta,
                    "learned_override_triggered": int(triggered),
                }
            )

        issues: list[str] = []
        if not learned_base_meta:
            issues.append("base_selected_answer_missing")
        if not learned_sel_meta:
            issues.append("learned_selected_answer_missing")
        if not str(learned.get("final_selected_answer", "")).strip():
            issues.append("final_selected_answer_missing")
        if issues:
            metadata_issues.append(
                {
                    "example_id": ck[0],
                    "seed": ck[1],
                    "budget": ck[2],
                    "issue": "metadata_missing",
                    "detail": ",".join(issues),
                }
            )

        reason = "unknown"
        if not candidate_pool_equal:
            reason = "candidate_pool_differs"
        elif fallback_mismatch_flag:
            reason = "fallback_not_base_answer"
        elif issues:
            reason = "metadata_missing"
        elif base_final.strip().lower() != learned_base_meta.strip().lower() and learned_base_meta:
            reason = "answer_normalization_diff"
        elif not base_set:
            reason = "seed_or_prompt_config_diff"
        mismatch_reasons[reason] += 1

        per_case_pairing.append(
            {
                "example_id": ck[0],
                "seed": ck[1],
                "budget": ck[2],
                "base_selected_answer": base_final,
                "learned_final_selected_answer": learned_final,
                "learned_base_selected_answer_meta": learned_base_meta or "NA",
                "learned_selected_answer_meta": learned_sel_meta or "NA",
                "learned_override_triggered": int(triggered),
                "candidate_count_base": branch_counts.get((ck[0], ck[1], ck[2], BASE_METHOD), 0),
                "candidate_count_learned": branch_counts.get((ck[0], ck[1], ck[2], LEARNED_METHOD), 0),
                "candidate_pool_equal": int(candidate_pool_equal),
                "fallback_should_match_base": int(fallback_should_match_base),
                "fallback_mismatch": int(fallback_mismatch_flag),
                "mismatch_reason": reason,
            }
        )

    summary = [
        {
            "n_cases_compared": len(per_case_pairing),
            "n_candidate_pool_differs": sum(1 for r in per_case_pairing if int(r["candidate_pool_equal"]) == 0),
            "n_fallback_mismatch": len(fallback_mismatch),
            "n_metadata_issues": len(metadata_issues),
            "reason_candidate_pool_differs": mismatch_reasons.get("candidate_pool_differs", 0),
            "reason_fallback_not_base_answer": mismatch_reasons.get("fallback_not_base_answer", 0),
            "reason_metadata_missing": mismatch_reasons.get("metadata_missing", 0),
            "reason_answer_normalization_diff": mismatch_reasons.get("answer_normalization_diff", 0),
            "reason_seed_or_prompt_config_diff": mismatch_reasons.get("seed_or_prompt_config_diff", 0),
            "reason_unknown": mismatch_reasons.get("unknown", 0),
        }
    ]

    _write_csv(out_dir / "summary.csv", summary)
    _write_csv(out_dir / "per_case_pairing.csv", per_case_pairing)
    _write_csv(out_dir / "candidate_pool_diff.csv", candidate_pool_diff)
    _write_csv(out_dir / "fallback_mismatch_cases.csv", fallback_mismatch)
    _write_csv(out_dir / "metadata_consistency_issues.csv", metadata_issues)
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                "# direct_reserve learned-override pairing debug",
                "",
                f"- validation input: `{validation}`",
                f"- compared methods: `{BASE_METHOD}` vs `{LEARNED_METHOD}`",
                "- This is an offline artifact-only diagnosis; no API calls were made.",
                "- `fallback_mismatch_cases.csv` flags cases where learned override did not trigger but final answer still differed from base.",
                "- `candidate_pool_diff.csv` flags cases where candidate sets differ across methods (unpaired/stochastic generation risk).",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote pairing debug package: {out_dir}")


if __name__ == "__main__":
    main()

