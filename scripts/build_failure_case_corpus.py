#!/usr/bin/env python3
"""Build offline failure-case corpus from paired PAL/external artifacts (no API)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from experiments.output_layer_repair import canonicalize_answer
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _idx(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        eid = str(row.get("example_id") or row.get("case_id") or "").strip()
        if eid:
            out[eid] = row
    return out


def _to_int(v: Any) -> int:
    try:
        return int(float(str(v)))
    except Exception:
        return 0


def _norm(v: Any) -> str:
    return str(v if v is not None else "").strip()


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _has_nonempty(v: Any) -> bool:
    return str(v if v is not None else "").strip() != ""


def _sha256_or_empty(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _final_answer_from_external_row(ext_row: dict[str, Any]) -> str:
    direct = _norm(ext_row.get("final_answer_raw") or ext_row.get("final_answer") or ext_row.get("answer"))
    if direct:
        return direct
    md = ext_row.get("result_metadata") if isinstance(ext_row.get("result_metadata"), dict) else {}
    return _norm(
        md.get("final_answer")
        or md.get("final_answer_raw")
        or md.get("selected_answer")
        or md.get("prediction")
    )


def _operation_hints(question: str) -> list[str]:
    q = question.lower()
    hints: list[str] = []
    if re.search(r"\b(per|each|rate|ratio)\b", q):
        hints.append("rate_ratio")
    if re.search(r"\b(percent|percentage|%|discount|interest)\b", q):
        hints.append("percent")
    if re.search(r"\b(total|sum|altogether|in all)\b", q):
        hints.append("total_sum")
    if re.search(r"\b(left|remain|difference|more than|less than|fewer)\b", q):
        hints.append("difference")
    if re.search(r"\b(times|product|multiplied|double|triple)\b", q):
        hints.append("product")
    if re.search(r"\b(divide|split|share|average|quotient|equal parts)\b", q):
        hints.append("division_share")
    if re.search(r"\b(after|before|then|next|now|later|increased|decreased|change)\b", q):
        hints.append("temporal_change")
    return hints or ["none"]


def _quantity_count(question: str) -> int:
    return len(re.findall(r"[-+]?\d+(?:\.\d+)?", question.replace(",", "")))


def _length_bucket(question: str) -> str:
    w = len([x for x in question.split() if x.strip()])
    if w <= 12:
        return "len_short"
    if w <= 24:
        return "len_medium"
    return "len_long"


def _extract_answers_from_obj(obj: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(obj, dict):
        return out
    for k in (
        "predicted_answer",
        "answer",
        "extracted_answer",
        "final_answer",
        "trace_extracted_answer",
        "pal_answer_raw",
        "pal_answer_normalized",
    ):
        s = _norm(obj.get(k))
        if s:
            out.append(s)
    return out


def _candidate_pool_from_metadata(md: dict[str, Any]) -> list[dict[str, Any]]:
    pool = md.get("selector_candidate_pool")
    if isinstance(pool, list):
        return [x for x in pool if isinstance(x, dict)]
    fbs = md.get("final_branch_states")
    if isinstance(fbs, list):
        return [x for x in fbs if isinstance(x, dict)]
    return []


def _gold_in_pool(pool: list[dict[str, Any]], gcan: str) -> int:
    if not gcan:
        return 0
    for row in pool:
        for ans in _extract_answers_from_obj(row):
            if canonicalize_answer(ans, dataset="openai/gsm8k") == gcan:
                return 1
    return 0


def _source_family_counts(pool: list[dict[str, Any]]) -> dict[str, int]:
    c: Counter[str] = Counter()
    for row in pool:
        fam = _norm(row.get("source_family") or row.get("strategy_family") or row.get("source_id") or "unknown")
        c[fam] += 1
    return dict(c)


def _diversity(pool: list[dict[str, Any]]) -> int:
    gs: set[str] = set()
    for r in pool:
        if not isinstance(r, dict):
            continue
        for ans in _extract_answers_from_obj(r):
            gs.add(normalize_answer_group_key(_norm(ans)) or "__unknown__")
    return len(gs)


def _stage_from_path_counterfactual(
    eid: str, path_cov_idx: dict[str, dict[str, str]]
) -> str:
    row = path_cov_idx.get(eid)
    if not row:
        return "unknown"
    # Deterministic priority: discovery failure first if flags conflict.
    if _to_int(row.get("gold_absent_everywhere_detectable")) == 1:
        return "gold_absent_everywhere_detectable"
    for k in (
        "gold_in_selector_pool",
        "gold_in_trace_candidates",
        "gold_in_execution_output",
    ):
        if _to_int(row.get(k)) == 1:
            return k
    return "unknown"


def _bucket_from_casebook(cb: dict[str, str]) -> str:
    ext = _to_int(cb.get("external_exact") or cb.get("external_l1_max_exact"))
    pal = _to_int(cb.get("pal_exact"))
    if ext and pal:
        return "both_correct"
    if ext and not pal:
        return "external_only"
    if pal and not ext:
        return "pal_only"
    return "both_wrong"


def _external_exact_with_fallback(
    cb: dict[str, str],
    ext_row: dict[str, Any],
    *,
    gold_canonical: str,
) -> int:
    if _has_nonempty(cb.get("external_exact")):
        return _to_int(cb.get("external_exact"))
    if _has_nonempty(cb.get("external_l1_max_exact")):
        return _to_int(cb.get("external_l1_max_exact"))
    for k in ("external_exact", "external_l1_max_exact", "exact", "is_correct", "result_exact"):
        if _has_nonempty(ext_row.get(k)):
            return _to_int(ext_row.get(k))
    if gold_canonical:
        ext_ans = _final_answer_from_external_row(ext_row)
        if ext_ans:
            return int(canonicalize_answer(ext_ans, dataset="openai/gsm8k") == gold_canonical)
    return 0


def build_corpus(
    paired_casebook_csv: Path,
    pal_results_jsonl: Path,
    external_results_jsonl: Path | None,
    path_coverage_csv: Path | None,
    atlas_anchor_csv: Path | None,
    selector_sensitivity_csv: Path | None,
    output_dir: Path,
    broad_anchor_csv: Path | None = None,
    conservative_anchor_csv: Path | None = None,
    isolated_anchor_csv: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    cb_rows = _read_csv_rows(paired_casebook_csv)
    pal_idx = _idx(_iter_jsonl(pal_results_jsonl))
    ext_idx = _idx(_iter_jsonl(external_results_jsonl)) if external_results_jsonl and external_results_jsonl.is_file() else {}
    path_cov_idx = _idx(_read_csv_rows(path_coverage_csv)) if path_coverage_csv and path_coverage_csv.is_file() else {}
    atlas_idx = _idx(_read_csv_rows(atlas_anchor_csv)) if atlas_anchor_csv and atlas_anchor_csv.is_file() else {}
    sens_idx = _idx(_read_csv_rows(selector_sensitivity_csv)) if selector_sensitivity_csv and selector_sensitivity_csv.is_file() else {}
    broad_anchor_idx = _idx(_read_csv_rows(broad_anchor_csv)) if broad_anchor_csv and broad_anchor_csv.is_file() else {}
    conservative_anchor_idx = (
        _idx(_read_csv_rows(conservative_anchor_csv))
        if conservative_anchor_csv and conservative_anchor_csv.is_file()
        else {}
    )
    isolated_anchor_idx = (
        _idx(_read_csv_rows(isolated_anchor_csv)) if isolated_anchor_csv and isolated_anchor_csv.is_file() else {}
    )

    failure_cases: list[dict[str, Any]] = []
    compact_rows: list[dict[str, Any]] = []
    outcome_counts: Counter[str] = Counter()
    op_counts: Counter[str] = Counter()
    qty_bucket_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for cb in cb_rows:
        eid = _norm(cb.get("example_id") or cb.get("case_id"))
        if not eid:
            continue
        question = _norm(cb.get("question"))
        gold = _norm(cb.get("gold_answer"))
        gcan = canonicalize_answer(gold, dataset="openai/gsm8k") if gold else ""

        pal_exact = _to_int(cb.get("pal_exact"))
        pal_row = pal_idx.get(eid, {})
        ext_row = ext_idx.get(eid, {})
        ext_exact = _external_exact_with_fallback(cb, ext_row, gold_canonical=gcan or "")
        bucket = (
            "both_correct"
            if ext_exact == 1 and pal_exact == 1
            else ("external_only" if ext_exact == 1 and pal_exact == 0 else ("pal_only" if ext_exact == 0 and pal_exact == 1 else "both_wrong"))
        )
        pal_md = pal_row.get("result_metadata") if isinstance(pal_row.get("result_metadata"), dict) else {}
        ext_md = ext_row.get("result_metadata") if isinstance(ext_row.get("result_metadata"), dict) else {}

        pal_pool = _candidate_pool_from_metadata(pal_md)
        ext_pool = _candidate_pool_from_metadata(ext_md)
        pal_gold_in_pool = _gold_in_pool(pal_pool, gcan)
        ext_gold_in_pool = _gold_in_pool(ext_pool, gcan) if ext_pool else 0
        stage = _stage_from_path_counterfactual(eid, path_cov_idx)
        in_failed_gate_anchor = eid in broad_anchor_idx or eid in conservative_anchor_idx or eid in isolated_anchor_idx
        original_sources: list[str] = []
        if pal_exact == 0:
            original_sources.append("pal_wrong")
        if ext_exact == 1 and pal_exact == 0:
            original_sources.append("external_only_loss")
        if stage == "gold_absent_everywhere_detectable":
            original_sources.append("gold_absent_everywhere_detectable")
        if bucket == "both_wrong":
            original_sources.append("both_wrong")
        if eid in atlas_idx:
            original_sources.append("atlas_anchor")
        if eid in sens_idx:
            original_sources.append("selector_sensitivity")
        if in_failed_gate_anchor:
            original_sources.append("failed_gate_anchor")

        include = bool(
            pal_exact == 0
            or (ext_exact == 1 and pal_exact == 0)
            or stage == "gold_absent_everywhere_detectable"
            or (bucket == "both_wrong" and pal_gold_in_pool == 0)
            or in_failed_gate_anchor
        )
        if not include:
            continue

        op_hints = _operation_hints(question)
        qn = _quantity_count(question)
        qbucket = "qnum_0_1" if qn <= 1 else ("qnum_2_3" if qn <= 3 else ("qnum_4_5" if qn <= 5 else "qnum_6p"))
        lbucket = _length_bucket(question)
        pal_div = _diversity(pal_pool)
        ext_div = _diversity(ext_pool)

        outcome_counts[bucket] += 1
        for h in op_hints:
            op_counts[h] += 1
        qty_bucket_counts[qbucket] += 1
        stage_counts[stage] += 1
        for s in original_sources:
            source_counts[s] += 1

        external_tree_available = int(
            bool(ext_md.get("action_trace") or ext_md.get("final_branch_states") or ext_md.get("branch_states"))
        )

        row = {
            "example_id": eid,
            "case_id": eid,
            "question": question,
            "gold_answer": gold,
            "our_answer": _norm(cb.get("pal_final_answer") or pal_row.get("final_answer_raw")),
            "our_exact": pal_exact,
            "external_answer": _norm(cb.get("external_final_answer") or ext_row.get("final_answer_raw")),
            "external_exact": ext_exact,
            "outcome_bucket": bucket,
            "anchor_regression": int(in_failed_gate_anchor),
            "original_failure_sources": sorted(set(original_sources)),
            "our_gold_in_pool": pal_gold_in_pool,
            "external_gold_in_pool": ext_gold_in_pool if ext_pool else None,
            "our_candidate_pool": pal_pool,
            "external_candidate_pool": ext_pool if ext_pool else [],
            "our_discovery_trace": _as_list(pal_md.get("action_trace")),
            "our_final_branch_states": _as_list(pal_md.get("final_branch_states")),
            "external_discovery_trace": _as_list(ext_md.get("action_trace")) if ext_md else [],
            "external_final_branch_states": _as_list(ext_md.get("final_branch_states")) if ext_md else [],
            "external_tree_available": external_tree_available,
            "pal_execution": pal_md.get("pal_execution", {}),
            "pal_retry": {
                "pal_empty_code_retry_ran": _to_int((pal_md.get("pal_execution") or {}).get("pal_empty_code_retry_ran")),
                "pal_empty_code_retry_reason": _norm((pal_md.get("pal_execution") or {}).get("pal_empty_code_retry_reason")),
                "pal_empty_code_retry_skipped_reason": _norm((pal_md.get("pal_execution") or {}).get("pal_empty_code_retry_skipped_reason")),
            },
            "overlay_metadata": pal_md.get("pal_overlay", {}),
            "tiebreak_metadata": {
                k: pal_md.get(k)
                for k in (
                    "frontier_tiebreak_enabled",
                    "frontier_tiebreak_triggered",
                    "frontier_tiebreak_selected_group",
                    "frontier_tiebreak_reason",
                )
                if k in pal_md
            },
            "feature_tags": {
                "operation_hints": op_hints,
                "numeric_quantity_count": qn,
                "question_length_bucket": lbucket,
                "quantity_bucket": qbucket,
                "our_candidate_diversity": pal_div,
                "external_candidate_diversity": ext_div,
                "our_gold_presence_flags": {
                    "gold_in_selector_pool": pal_gold_in_pool,
                    "gold_in_tree_stage": stage,
                },
                "source_family_counts": _source_family_counts(pal_pool),
                "failure_stage_classification": stage,
                "in_atlas_anchor": int(eid in atlas_idx),
                "in_selector_sensitivity": int(eid in sens_idx),
                "in_broad_anchor_validation": int(eid in broad_anchor_idx),
                "in_conservative_anchor_validation": int(eid in conservative_anchor_idx),
                "in_isolated_anchor_validation": int(eid in isolated_anchor_idx),
            },
        }
        failure_cases.append(row)
        compact_rows.append(
            {
                "example_id": eid,
                "outcome_bucket": bucket,
                "our_exact": pal_exact,
                "external_exact": ext_exact,
                "our_answer": row["our_answer"],
                "external_answer": row["external_answer"],
                "our_gold_in_pool": pal_gold_in_pool,
                "external_gold_in_pool": "" if row["external_gold_in_pool"] is None else row["external_gold_in_pool"],
                "failure_stage": stage,
                "operation_hints": "|".join(op_hints),
                "quantity_bucket": qbucket,
                "question_length_bucket": lbucket,
                "our_candidate_diversity": pal_div,
                "external_tree_available": external_tree_available,
                "anchor_regression": int(in_failed_gate_anchor),
                "original_failure_sources": "|".join(sorted(set(original_sources))) if original_sources else "",
            }
        )

    with (output_dir / "failure_cases.jsonl").open("w", encoding="utf-8") as f:
        for row in failure_cases:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    with (output_dir / "failure_cases.csv").open("w", encoding="utf-8", newline="") as f:
        fns = list(compact_rows[0].keys()) if compact_rows else ["example_id"]
        w = csv.DictWriter(f, fieldnames=fns)
        w.writeheader()
        if compact_rows:
            w.writerows(compact_rows)

    feature_summary = {
        "meta": {
            "paired_casebook_csv": str(paired_casebook_csv.resolve()),
            "pal_results_jsonl": str(pal_results_jsonl.resolve()),
            "external_results_jsonl": str(external_results_jsonl.resolve()) if external_results_jsonl else "",
            "output_dir": str(output_dir.resolve()),
            "api_calls": "none",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "manifest": {
            "input_paths": {
                "paired_casebook_csv": str(paired_casebook_csv.resolve()),
                "pal_results_jsonl": str(pal_results_jsonl.resolve()),
                "external_results_jsonl": str(external_results_jsonl.resolve()) if external_results_jsonl else "",
                "path_coverage_csv": str(path_coverage_csv.resolve()) if path_coverage_csv else "",
                "atlas_anchor_csv": str(atlas_anchor_csv.resolve()) if atlas_anchor_csv else "",
                "selector_sensitivity_csv": str(selector_sensitivity_csv.resolve()) if selector_sensitivity_csv else "",
            },
            "input_sha256": {
                "paired_casebook_csv": _sha256_or_empty(paired_casebook_csv),
                "pal_results_jsonl": _sha256_or_empty(pal_results_jsonl),
                "external_results_jsonl": _sha256_or_empty(external_results_jsonl),
                "path_coverage_csv": _sha256_or_empty(path_coverage_csv),
                "atlas_anchor_csv": _sha256_or_empty(atlas_anchor_csv),
                "selector_sensitivity_csv": _sha256_or_empty(selector_sensitivity_csv),
            },
            "row_counts_loaded": {
                "paired_casebook_rows": len(cb_rows),
                "pal_results_rows": len(pal_idx),
                "external_results_rows": len(ext_idx),
                "path_coverage_rows": len(path_cov_idx),
                "atlas_anchor_rows": len(atlas_idx),
                "selector_sensitivity_rows": len(sens_idx),
                "broad_anchor_rows": len(broad_anchor_idx),
                "conservative_anchor_rows": len(conservative_anchor_idx),
                "isolated_anchor_rows": len(isolated_anchor_idx),
            },
            "missing_or_unmatched": {
                "pal_missing_for_casebook_ids": int(sum(1 for cb in cb_rows if _norm(cb.get("example_id") or cb.get("case_id")) and _norm(cb.get("example_id") or cb.get("case_id")) not in pal_idx)),
                "external_missing_for_casebook_ids": int(sum(1 for cb in cb_rows if _norm(cb.get("example_id") or cb.get("case_id")) and _norm(cb.get("example_id") or cb.get("case_id")) not in ext_idx)) if ext_idx else len(cb_rows),
                "path_coverage_missing_for_casebook_ids": int(sum(1 for cb in cb_rows if _norm(cb.get("example_id") or cb.get("case_id")) and _norm(cb.get("example_id") or cb.get("case_id")) not in path_cov_idx)) if path_cov_idx else len(cb_rows),
            },
            "corpus_row_count": len(failure_cases),
        },
        "failure_cases_collected": len(failure_cases),
        "outcome_buckets": dict(outcome_counts),
        "operation_hints": dict(op_counts),
        "quantity_buckets": dict(qty_bucket_counts),
        "failure_stages": dict(stage_counts),
        "counts_by_original_failure_source": dict(source_counts),
        "external_tree_available_cases": int(sum(1 for r in failure_cases if int(r.get("external_tree_available", 0)) == 1)),
        "external_tree_missing_cases": int(sum(1 for r in failure_cases if int(r.get("external_tree_available", 0)) == 0)),
        "pal_tree_available_cases": int(sum(1 for r in failure_cases if len(_as_list(r.get("our_discovery_trace"))) > 0 or len(_as_list(r.get("our_final_branch_states"))) > 0)),
        "pal_tree_missing_cases": int(sum(1 for r in failure_cases if len(_as_list(r.get("our_discovery_trace"))) == 0 and len(_as_list(r.get("our_final_branch_states"))) == 0)),
    }
    (output_dir / "feature_summary.json").write_text(json.dumps(feature_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    top_manual = compact_rows[: min(15, len(compact_rows))]
    md_lines = [
        "# Failure Case Corpus Pattern Seed Report",
        "",
        f"- Failure/loss cases collected: {len(failure_cases)}",
        f"- Top outcome buckets: {dict(outcome_counts.most_common(5))}",
        f"- Counts by original failure source: {dict(source_counts.most_common(8))}",
        f"- Top operation/quantity patterns: operation={dict(op_counts.most_common(5))}, quantity={dict(qty_bucket_counts.most_common(5))}",
        f"- Top gold-absence stages: {dict(stage_counts.most_common(5))}",
        f"- PAL trace/tree availability (cases): yes={feature_summary['pal_tree_available_cases']} no={feature_summary['pal_tree_missing_cases']}",
        f"- External trace availability (cases): yes={feature_summary['external_tree_available_cases']} no={feature_summary['external_tree_missing_cases']}",
        "- Missing external traces limit pairwise tree-diagnostics where availability=no.",
        "",
        "## Top cases for manual inspection",
    ]
    for row in top_manual:
        md_lines.append(
            f"- {row['example_id']} | bucket={row['outcome_bucket']} | our_exact={row['our_exact']} | external_exact={row['external_exact']} | stage={row['failure_stage']}"
        )
    (output_dir / "pattern_seed_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    idx_lines = [
        "# Failure Case Corpus Index",
        "",
        "- `failure_cases.jsonl`: full per-case JSON records",
        "- `failure_cases.csv`: compact tabular view",
        "- `feature_summary.json`: aggregate counts",
        "- `pattern_seed_report.md`: top patterns and manual-inspection seeds",
        "",
        f"- Total indexed cases: {len(failure_cases)}",
    ]
    (output_dir / "case_index.md").write_text("\n".join(idx_lines) + "\n", encoding="utf-8")

    return feature_summary


def main() -> None:
    p = argparse.ArgumentParser(description="Build offline failure-case corpus from paired artifacts.")
    p.add_argument("--paired-casebook", type=Path, required=True)
    p.add_argument("--pal-results", type=Path, required=True)
    p.add_argument("--external-results", type=Path, default=None)
    p.add_argument("--path-coverage-csv", type=Path, default=None)
    p.add_argument("--atlas-anchor-csv", type=Path, default=None)
    p.add_argument("--selector-sensitivity-csv", type=Path, default=None)
    p.add_argument("--broad-anchor-csv", type=Path, default=None)
    p.add_argument("--conservative-anchor-csv", type=Path, default=None)
    p.add_argument("--isolated-anchor-csv", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    summary = build_corpus(
        paired_casebook_csv=args.paired_casebook,
        pal_results_jsonl=args.pal_results,
        external_results_jsonl=args.external_results,
        path_coverage_csv=args.path_coverage_csv,
        atlas_anchor_csv=args.atlas_anchor_csv,
        selector_sensitivity_csv=args.selector_sensitivity_csv,
        broad_anchor_csv=args.broad_anchor_csv,
        conservative_anchor_csv=args.conservative_anchor_csv,
        isolated_anchor_csv=args.isolated_anchor_csv,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
