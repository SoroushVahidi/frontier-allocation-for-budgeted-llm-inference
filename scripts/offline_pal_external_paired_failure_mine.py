#!/usr/bin/env python3
"""Offline failure archaeology for paired PAL vs external runs (no API).

Joins `paired_casebook.csv` with `pal_results.jsonl`, recomputes retry fields from
raw `result_metadata.pal_execution` (avoiding the known buggy casebook
`retry_enabled` column), and aggregates failure signals for regret buckets.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def _to_int(v: Any) -> int:
    try:
        return int(float(str(v)))
    except Exception:
        return 0


def _norm_str(v: Any) -> str:
    return str(v if v is not None else "").strip()


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _index_pal_results(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in _iter_jsonl(path):
        eid = _norm_str(row.get("example_id") or row.get("case_id"))
        if eid:
            out[eid] = row
    return out


def _pal_execution(row: dict[str, Any]) -> dict[str, Any]:
    md = row.get("result_metadata")
    if not isinstance(md, dict):
        md = {}
    px = md.get("pal_execution")
    return px if isinstance(px, dict) else {}


def extract_retry_from_pal_row(pal_row: dict[str, Any] | None) -> dict[str, Any]:
    """Recompute retry-related fields from raw PAL metadata."""
    if not pal_row:
        return {
            "truth_retry_enabled": 0,
            "truth_retry_ran": 0,
            "truth_retry_skipped_reason": "",
            "truth_retry_reason": "",
            "truth_retry_selected_source": "",
            "truth_retry_exec_ok": None,
            "truth_retry_parse_ok": None,
            "truth_retry_safety_ok": None,
            "truth_retry_candidate_strong": None,
            "truth_retry_code_present": None,
        }
    px = _pal_execution(pal_row)
    rex = px.get("pal_empty_code_retry_execution")
    rex_d = rex if isinstance(rex, dict) else {}

    enabled = 1 if px.get("pal_empty_code_retry_enabled") else 0
    ran = _to_int(px.get("pal_empty_code_retry_ran"))

    selected = _norm_str(px.get("pal_selected_candidate_source")).lower()
    if not selected:
        selected = "none"

    retry_exec_ok = None
    retry_parse_ok = None
    retry_safety_ok = None
    retry_strong = None
    retry_code_present = None
    if rex_d:
        retry_exec_ok = _to_int(rex_d.get("pal_exec_ok", 0))
        retry_parse_ok = _to_int(rex_d.get("pal_parse_ok", 0))
        retry_safety_ok = _to_int(rex_d.get("pal_safety_ok", 0))
        retry_strong = _to_int(rex_d.get("pal_candidate_is_strong", 0))
        retry_code_present = 1 if _norm_str(rex_d.get("pal_code")) else 0

    return {
        "truth_retry_enabled": enabled,
        "truth_retry_ran": ran,
        "truth_retry_skipped_reason": _norm_str(px.get("pal_empty_code_retry_skipped_reason")),
        "truth_retry_reason": _norm_str(px.get("pal_empty_code_retry_reason")),
        "truth_retry_selected_source": selected,
        "truth_retry_exec_ok": retry_exec_ok,
        "truth_retry_parse_ok": retry_parse_ok,
        "truth_retry_safety_ok": retry_safety_ok,
        "truth_retry_candidate_strong": retry_strong,
        "truth_retry_code_present": retry_code_present,
    }


def regret_bucket(ext_exact: int, pal_exact: int) -> str:
    if ext_exact and pal_exact:
        return "both_correct"
    if ext_exact and not pal_exact:
        return "external_only"
    if pal_exact and not ext_exact:
        return "pal_only"
    return "both_wrong"


def _failure_signature_tags(cb: dict[str, str], retry: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if _to_int(cb.get("pal_gold_absent")):
        tags.append("gold_absent_cb")
    if _to_int(cb.get("pal_discovery3")):
        tags.append("discovery3_cb")
    if _to_int(cb.get("pal_present_not_selected")):
        tags.append("present_not_selected_cb")
    if _to_int(cb.get("pal_code_present")) == 0:
        tags.append("code_absent_cb")
    if _to_int(cb.get("pal_parse_ok")) == 0:
        tags.append("parse_fail_cb")
    if _to_int(cb.get("pal_safety_ok")) == 0:
        tags.append("safety_fail_cb")
    if _to_int(cb.get("pal_exec_ok")) == 0:
        tags.append("exec_fail_cb")
    if _to_int(cb.get("pal_overlay_triggered")):
        tags.append("overlay_cb")
    if retry.get("truth_retry_ran"):
        tags.append("retry_ran_raw")
    sel = _norm_str(retry.get("truth_retry_selected_source")).lower()
    if sel == "pal_empty_code_retry":
        tags.append("retry_selected_raw")
    return sorted(tags)


def mine_failure_modes(
    *,
    casebook_rows: list[dict[str, str]],
    pal_by_id: dict[str, dict[str, Any]],
    top_signatures: int,
    anchors_per_signature: int,
) -> dict[str, Any]:
    bucket_counts: Counter[str] = Counter()
    marginal_by_subset: dict[str, Counter[tuple[str, str]]] = {
        "external_only": Counter(),
        "both_wrong": Counter(),
    }
    sig_counter: dict[str, Counter[str]] = {
        "external_only": Counter(),
        "both_wrong": Counter(),
    }
    anchors: dict[str, dict[str, list[dict[str, Any]]]] = {
        "external_only": defaultdict(list),
        "both_wrong": defaultdict(list),
    }

    retry_enabled_raw = 0
    retry_ran_raw = 0
    retry_selected_count = 0
    retry_helped = 0
    retry_hurt = 0
    casebook_retry_enabled_bug_hint = 0

    missing_pal = 0

    for cb in casebook_rows:
        eid = _norm_str(cb.get("example_id") or cb.get("case_id"))
        pal_row = pal_by_id.get(eid)
        if not pal_row:
            missing_pal += 1
        retry = extract_retry_from_pal_row(pal_row)

        retry_enabled_raw += _to_int(retry["truth_retry_enabled"])
        retry_ran_raw += _to_int(retry["truth_retry_ran"])

        if _to_int(cb.get("retry_enabled")) == 0 and retry["truth_retry_enabled"]:
            casebook_retry_enabled_bug_hint += 1

        ext_ok = _to_int(cb.get("external_exact"))
        pal_ok = _to_int(cb.get("pal_exact"))
        bucket = regret_bucket(ext_ok, pal_ok)
        bucket_counts[bucket] += 1

        sel_src = _norm_str(retry["truth_retry_selected_source"]).lower()
        if sel_src == "pal_empty_code_retry":
            retry_selected_count += 1
            if pal_ok:
                retry_helped += 1
            else:
                retry_hurt += 1

        if bucket not in ("external_only", "both_wrong"):
            continue

        sig = "|".join(_failure_signature_tags(cb, retry)) or "(none)"
        sig_counter[bucket][sig] += 1

        sub = marginal_by_subset[bucket]
        sub[("pal_gold_absent", str(_to_int(cb.get("pal_gold_absent"))))] += 1
        sub[("pal_discovery3", str(_to_int(cb.get("pal_discovery3"))))] += 1
        sub[("pal_present_not_selected", str(_to_int(cb.get("pal_present_not_selected"))))] += 1
        sub[("pal_parse_ok", str(_to_int(cb.get("pal_parse_ok"))))] += 1
        sub[("pal_safety_ok", str(_to_int(cb.get("pal_safety_ok"))))] += 1
        sub[("pal_exec_ok", str(_to_int(cb.get("pal_exec_ok"))))] += 1
        sub[("pal_code_present", str(_to_int(cb.get("pal_code_present"))))] += 1
        sub[("pal_overlay_triggered", str(_to_int(cb.get("pal_overlay_triggered"))))] += 1
        sub[("final_answer_source_cb", _norm_str(cb.get("final_answer_source")) or "(empty)")] += 1
        sub[("truth_retry_ran", str(_to_int(retry["truth_retry_ran"])))] += 1
        sub[("truth_retry_selected_source", sel_src or "(empty)")] += 1
        sub[("retry_skipped_reason_raw", retry["truth_retry_skipped_reason"] or "(empty)")] += 1

        if len(anchors[bucket][sig]) < anchors_per_signature:
            anchors[bucket][sig].append(
                {
                    "example_id": eid,
                    "signature": sig,
                    "external_exact": ext_ok,
                    "pal_exact": pal_ok,
                    "pal_gold_absent": _to_int(cb.get("pal_gold_absent")),
                    "pal_discovery3": _to_int(cb.get("pal_discovery3")),
                    "pal_present_not_selected": _to_int(cb.get("pal_present_not_selected")),
                    "pal_exec_ok": _to_int(cb.get("pal_exec_ok")),
                    "final_answer_source_cb": _norm_str(cb.get("final_answer_source")),
                    "truth_retry_ran": _to_int(retry["truth_retry_ran"]),
                    "truth_retry_selected_source": sel_src,
                    "pal_retry_skipped_reason_cb": _norm_str(cb.get("pal_retry_skipped_reason")),
                }
            )

    top_sigs = {
        subset: sig_counter[subset].most_common(top_signatures) for subset in sig_counter
    }

    return {
        "bucket_counts": dict(bucket_counts),
        "marginal_by_subset": {
            k: {f"{a}|{b}": c for (a, b), c in v.items()} for k, v in marginal_by_subset.items()
        },
        "top_signatures": {k: [(sig, n) for sig, n in v] for k, v in top_sigs.items()},
        "anchors": {subset: dict(v) for subset, v in anchors.items()},
        "retry_recompute": {
            "rows_total": len(casebook_rows),
            "truth_retry_enabled_count": retry_enabled_raw,
            "truth_retry_ran_count": retry_ran_raw,
            "truth_retry_selected_as_final_source_count": retry_selected_count,
            "inferable_retry_helped_exact_count": retry_helped,
            "inferable_retry_hurt_exact_count": retry_hurt,
            "casebook_retry_enabled_all_zero_but_raw_enabled_rows": casebook_retry_enabled_bug_hint,
            "missing_pal_results_rows": missing_pal,
        },
    }


def _write_failure_mode_table(path: Path, mined: dict[str, Any]) -> None:
    rows: list[dict[str, str]] = []
    for subset in ("external_only", "both_wrong"):
        marginal = mined["marginal_by_subset"].get(subset, {})
        for key, cnt in sorted(marginal.items(), key=lambda x: (-x[1], x[0])):
            if "|" in key:
                signal, _, value = key.partition("|")
            else:
                signal, value = key, ""
            rows.append(
                {
                    "subset": subset,
                    "row_kind": "marginal",
                    "signal": signal,
                    "value": value,
                    "count": str(cnt),
                }
            )
        for sig, cnt in mined["top_signatures"].get(subset, []):
            rows.append(
                {
                    "subset": subset,
                    "row_kind": "composite_signature",
                    "signal": "signature",
                    "value": sig,
                    "count": str(cnt),
                }
            )
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["subset", "row_kind", "signal", "value", "count"],
        )
        w.writeheader()
        w.writerows(rows)


def _write_anchor_cases(path: Path, mined: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    rank_counter: dict[str, Counter[str]] = {
        "external_only": Counter(),
        "both_wrong": Counter(),
    }
    for subset in ("external_only", "both_wrong"):
        for sig, lst in mined["anchors"].get(subset, {}).items():
            for item in lst:
                rank_counter[subset][sig] += 1
                rank = rank_counter[subset][sig]
                rows.append({"subset": subset, "signature_rank": rank, **item})
    rows.sort(key=lambda r: (r["subset"], r["signature"], r["signature_rank"]))
    if not rows:
        path.write_text("subset,signature_rank,example_id\n", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _write_report_md(path: Path, mined: dict[str, Any], meta: dict[str, Any]) -> None:
    rr = mined["retry_recompute"]
    lines = [
        "# Offline PAL vs external paired failure mine",
        "",
        "## Inputs",
        f"- casebook: `{meta.get('casebook_path')}`",
        f"- pal_results: `{meta.get('pal_results_path')}`",
        "",
        "## Bucket counts",
    ]
    for k, v in sorted(mined["bucket_counts"].items()):
        lines.append(f"- **{k}**: {v}")
    lines += [
        "",
        "## Retry recompute (raw `pal_execution`, not casebook `retry_enabled`)",
        f"- Rows: **{rr['rows_total']}**",
        f"- Truth retry enabled (sum): **{rr['truth_retry_enabled_count']}**",
        f"- Truth retry ran (sum): **{rr['truth_retry_ran_count']}**",
        f"- Selected source `pal_empty_code_retry` rows: **{rr['truth_retry_selected_as_final_source_count']}**",
        f"- Inferable retry helped (exact & retry selected): **{rr['inferable_retry_helped_exact_count']}**",
        f"- Inferable retry hurt (not exact & retry selected): **{rr['inferable_retry_hurt_exact_count']}**",
        f"- Casebook `retry_enabled`=0 but raw enabled: **{rr['casebook_retry_enabled_all_zero_but_raw_enabled_rows']}** rows",
        f"- Missing `pal_results` join rows: **{rr['missing_pal_results_rows']}**",
        "",
        "## Top composite signatures",
    ]
    for subset in ("external_only", "both_wrong"):
        lines.append(f"### {subset}")
        for sig, cnt in mined["top_signatures"].get(subset, [])[:12]:
            lines.append(f"- `{sig}` — **{cnt}**")
        lines.append("")
    lines += [
        "## Fix-target hints (interpretive)",
        "- **`gold_absent_cb` heavy in `external_only`:** widen/improve candidate discovery / frontier surfacing so gold enters the selector pool.",
        "- **`present_not_selected_cb`:** selector / tie-break / verification policies failing despite executable candidates.",
        "- **`exec_fail_cb` / `parse_fail_cb` / `safety_fail_cb`:** executor / sandbox / parsing brittleness.",
        "- **Retry rare (`truth_retry_ran` mostly 0):** empty-code retry policy will not address gold-absent / discovery gaps.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_from_paths(
    *,
    casebook_path: Path,
    pal_results_path: Path,
    paired_summary_path: Path | None,
    materialization_path: Path | None,
    output_dir: Path,
    top_signatures: int,
    anchors_per_signature: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    cb_rows = _read_csv_rows(casebook_path)
    pal_by_id = _index_pal_results(pal_results_path)

    mined = mine_failure_modes(
        casebook_rows=cb_rows,
        pal_by_id=pal_by_id,
        top_signatures=top_signatures,
        anchors_per_signature=anchors_per_signature,
    )

    summary: dict[str, Any] = {
        "meta": {
            "casebook_path": str(casebook_path.resolve()),
            "pal_results_path": str(pal_results_path.resolve()),
            "paired_summary_path": str(paired_summary_path.resolve())
            if paired_summary_path
            else None,
            "materialization_consistency_checks_path": str(materialization_path.resolve())
            if materialization_path
            else None,
            "output_dir": str(output_dir.resolve()),
            "rows_join_attempted": len(cb_rows),
        },
        "retry_recompute": mined["retry_recompute"],
        "bucket_counts": mined["bucket_counts"],
        "marginal_by_subset": mined["marginal_by_subset"],
        "top_signatures": mined["top_signatures"],
    }
    if paired_summary_path and paired_summary_path.exists():
        ps = _read_json(paired_summary_path)
        summary["paired_summary_excerpt"] = {
            "selected_fresh_examples_count": ps.get("selected_fresh_examples_count"),
        }
    if materialization_path and materialization_path.exists():
        summary["materialization_consistency_checks"] = _read_json(materialization_path)

    # Drop non-serializable anchors expansion from summary.json (keep compact)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _write_failure_mode_table(output_dir / "failure_mode_table.csv", mined)
    _write_anchor_cases(output_dir / "anchor_cases.csv", mined)
    _write_report_md(
        output_dir / "report.md",
        mined,
        {
            "casebook_path": str(casebook_path.resolve()),
            "pal_results_path": str(pal_results_path.resolve()),
        },
    )

    return summary


def main() -> None:
    repo = Path.cwd()
    default_dir = (
        repo / "outputs" / "cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z"
    )

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--casebook",
        type=Path,
        default=default_dir / "paired_casebook.csv",
        help="paired_casebook.csv path",
    )
    p.add_argument(
        "--pal-results",
        type=Path,
        dest="pal_results",
        default=default_dir / "pal_results.jsonl",
        help="pal_results.jsonl path",
    )
    p.add_argument(
        "--paired-summary",
        type=Path,
        default=default_dir / "paired_summary.json",
        help="optional paired_summary.json",
    )
    p.add_argument(
        "--materialization-checks",
        type=Path,
        default=default_dir / "materialization_consistency_checks.json",
        help="optional materialization_consistency_checks.json",
    )
    p.add_argument(
        "--timestamp",
        type=str,
        required=True,
        help="Output folder suffix: outputs/offline_pal_external_failure_mine_<timestamp>/",
    )
    p.add_argument(
        "--output-root",
        type=Path,
        default=repo / "outputs",
        help="Directory containing offline_pal_external_failure_mine_* outputs",
    )
    p.add_argument("--top-signatures", type=int, default=25)
    p.add_argument("--anchors-per-signature", type=int, default=12)
    args = p.parse_args()

    paired_summary = args.paired_summary if args.paired_summary.exists() else None
    materialization = (
        args.materialization_checks if args.materialization_checks.exists() else None
    )

    out_dir = args.output_root / f"offline_pal_external_failure_mine_{args.timestamp}"
    run_from_paths(
        casebook_path=args.casebook,
        pal_results_path=args.pal_results,
        paired_summary_path=paired_summary,
        materialization_path=materialization,
        output_dir=out_dir,
        top_signatures=args.top_signatures,
        anchors_per_signature=args.anchors_per_signature,
    )
    print(str(out_dir.resolve()))


if __name__ == "__main__":
    main()
