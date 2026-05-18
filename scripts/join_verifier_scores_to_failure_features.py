"""Join offline verifier scores into failure-pattern feature rows.

This utility attaches RelationReady verifier score features from scored-candidate
JSONL artifacts to enriched failure-pattern feature rows.

Primary join key:
    artifact_label + example_id + method + budget + seed

Fallback join keys (in order):
    artifact_label + example_id + method + budget
    artifact_label + example_id + method
    example_id + method + budget + seed
    example_id + method
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


KEY_SPECS = [
    ("artifact_label+example_id+method+budget+seed", True, True, True),
    ("artifact_label+example_id+method+budget", True, True, False),
    ("artifact_label+example_id+method", True, False, False),
    ("example_id+method+budget+seed", False, True, True),
    ("example_id+method", False, False, False),
]

ADDED_COLUMNS = [
    "baseline_proba_ready_max",
    "baseline_proba_ready_mean",
    "baseline_proba_ready_min",
    "baseline_proba_ready_std",
    "baseline_proba_ready_top2_gap",
    "baseline_predicted_ready_count",
    "baseline_scored_candidate_count",
    "frontier_proba_ready_max",
    "frontier_proba_ready_mean",
    "frontier_proba_ready_min",
    "frontier_proba_ready_std",
    "frontier_proba_ready_top2_gap",
    "frontier_predicted_ready_count",
    "frontier_scored_candidate_count",
    "score_margin_frontier_minus_baseline_max",
    "score_margin_frontier_minus_baseline_mean",
    "verifier_join_status",
    "verifier_join_match_count_baseline",
    "verifier_join_match_count_frontier",
]

TARGET_FLAGS = [
    "oracle_recoverable",
    "regression_risk",
    "both_wrong",
    "both_correct",
    "disagreement",
]


def _norm_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _norm_lower(v: Any) -> str:
    return _norm_str(v).lower()


def _truthy(v: Any) -> bool:
    s = _norm_lower(v)
    return s in {"1", "true", "t", "yes", "y"}


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    s = _norm_str(v)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    s = _norm_str(v)
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _first_nonempty(*vals: Any) -> str:
    for v in vals:
        s = _norm_str(v)
        if s:
            return s
    return ""


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def _parse_candidate_answer(feature_text: str) -> str:
    if not feature_text:
        return ""
    m = re.search(r"(?:^|\|)\s*candidate_answer:\s*(.*?)\s*(?:\||$)", feature_text)
    if not m:
        return ""
    return m.group(1).strip()


def _method_contains_match(target: str, candidate: str) -> bool:
    t = _norm_lower(target)
    c = _norm_lower(candidate)
    if not t or not c:
        return False
    if t == c:
        return True
    if len(t) >= 8 and t in c:
        return True
    if len(c) >= 8 and c in t:
        return True
    return False


def load_feature_rows(path: pathlib.Path) -> tuple[list[dict[str, str]], list[str]]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def flatten_scored_row(raw: dict[str, Any], score_field: str) -> dict[str, Any]:
    metadata = raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {}
    out: dict[str, Any] = dict(raw)
    out.update(metadata)

    out["example_id"] = _first_nonempty(
        out.get("example_id"),
        out.get("problem_id"),
        metadata.get("example_id"),
        metadata.get("problem_id"),
    )
    out["problem_id"] = _first_nonempty(out.get("problem_id"), metadata.get("problem_id"))
    out["method"] = _first_nonempty(out.get("method"), metadata.get("method"))
    out["budget"] = _first_nonempty(out.get("budget"), metadata.get("budget"))
    out["seed"] = _first_nonempty(out.get("seed"), metadata.get("seed"))
    out["dataset"] = _first_nonempty(out.get("dataset"), metadata.get("dataset"))
    out["model"] = _first_nonempty(out.get("model"), metadata.get("model"))
    out["candidate_answer"] = _first_nonempty(
        out.get("candidate_answer"),
        out.get("final_answer"),
        out.get("normalized_answer"),
        _parse_candidate_answer(_norm_str(out.get("feature_text"))),
    )

    proba = _as_float(out.get(score_field))
    if proba is None:
        proba = _as_float(out.get("proba_ready"))
    if proba is None:
        proba = _as_float(out.get("score_ready"))
    out["proba_ready"] = proba
    out["score_ready"] = _as_float(out.get("score_ready"))

    predicted = _as_int(out.get("predicted_label"))
    if predicted is None and proba is not None:
        predicted = int(proba >= 0.5)
    out["predicted_label"] = predicted

    out["artifact_label"] = _first_nonempty(out.get("artifact_label"), out.get("artifact"))
    out["artifact_path"] = _first_nonempty(
        out.get("artifact_path"),
        out.get("source_artifact_path"),
        out.get("artifact_source_path"),
    )
    return out


def load_scored_candidates(
    path: pathlib.Path,
    score_field: str,
    artifact_label: str,
    artifact_path: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    rows: list[dict[str, Any]] = []
    with open(path) as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            flat = flatten_scored_row(raw, score_field=score_field)
            flat["_row_id"] = idx
            rows.append(flat)

    notes: list[str] = []
    provenance = {
        "artifact_label_mode": "provided" if artifact_label else "inferred",
        "artifact_path_mode": "provided" if artifact_path else "inferred",
    }

    if artifact_label:
        for r in rows:
            r["artifact_label"] = artifact_label
    else:
        labels = sorted({_norm_str(r.get("artifact_label")) for r in rows if _norm_str(r.get("artifact_label"))})
        if len(labels) == 1:
            inferred = labels[0]
            for r in rows:
                if not _norm_str(r.get("artifact_label")):
                    r["artifact_label"] = inferred
            provenance["artifact_label"] = inferred
        elif len(labels) > 1:
            provenance["artifact_label"] = ""
            notes.append("Multiple artifact labels found in scored candidates; artifact label is ambiguous.")
        else:
            inferred = path.parent.name
            for r in rows:
                r["artifact_label"] = inferred
            provenance["artifact_label"] = inferred
            notes.append("Artifact label not present in scored rows; inferred from scored JSONL parent directory.")

    if artifact_path:
        for r in rows:
            r["artifact_path"] = artifact_path
    else:
        paths = sorted({_norm_str(r.get("artifact_path")) for r in rows if _norm_str(r.get("artifact_path"))})
        if len(paths) == 1:
            inferred = paths[0]
            for r in rows:
                if not _norm_str(r.get("artifact_path")):
                    r["artifact_path"] = inferred
            provenance["artifact_path"] = inferred
        elif len(paths) > 1:
            provenance["artifact_path"] = ""
            notes.append("Multiple artifact paths found in scored candidates; artifact path is ambiguous.")
        else:
            provenance["artifact_path"] = ""
            notes.append("Artifact path not present in scored rows and not provided; artifact path joins may be limited.")

    return rows, provenance, notes


def resolve_method_matches(candidate_rows: list[dict[str, Any]], target_method: str) -> tuple[list[str], str]:
    target = _norm_str(target_method)
    available = sorted({_norm_str(r.get("method")) for r in candidate_rows if _norm_str(r.get("method"))})
    if not available:
        return [], "none"
    exact = [m for m in available if _norm_lower(m) == _norm_lower(target)]
    if exact:
        return exact, "exact"
    fuzzy = [m for m in available if _method_contains_match(target, m)]
    if fuzzy:
        return sorted(fuzzy), "fuzzy"
    return [], "none"


def _row_artifact_label(feature_row: dict[str, Any]) -> str:
    return _first_nonempty(feature_row.get("artifact_label"))


def _row_example_id(feature_row: dict[str, Any], group_id_field: str) -> str:
    return _first_nonempty(
        feature_row.get(group_id_field),
        feature_row.get("example_id"),
        feature_row.get("problem_id"),
    )


def _candidate_matches_key(
    feature_row: dict[str, Any],
    cand: dict[str, Any],
    *,
    group_id_field: str,
    budget_field: str,
    seed_field: str,
    include_artifact: bool,
    include_budget: bool,
    include_seed: bool,
) -> bool:
    if _row_example_id(feature_row, group_id_field) != _first_nonempty(cand.get(group_id_field), cand.get("example_id"), cand.get("problem_id")):
        return False
    if include_artifact and _row_artifact_label(feature_row) != _norm_str(cand.get("artifact_label")):
        return False
    if include_budget and _norm_str(feature_row.get(budget_field)) != _norm_str(cand.get(budget_field)):
        return False
    if include_seed and _norm_str(feature_row.get(seed_field)) != _norm_str(cand.get(seed_field)):
        return False
    return True


def aggregate_matches(matches: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [m.get("proba_ready") for m in matches if m.get("proba_ready") is not None]
    if not matches:
        return {
            "proba_ready_max": None,
            "proba_ready_mean": None,
            "proba_ready_min": None,
            "proba_ready_std": None,
            "proba_ready_top2_gap": None,
            "predicted_ready_count": 0,
            "scored_candidate_count": 0,
            "match_count": 0,
        }
    if scores:
        s_sorted = sorted(scores, reverse=True)
        top2_gap = s_sorted[0] - s_sorted[1] if len(s_sorted) >= 2 else 0.0
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        max_v = max(scores)
        mean_v = statistics.mean(scores)
        min_v = min(scores)
    else:
        top2_gap = None
        std = None
        max_v = None
        mean_v = None
        min_v = None
    pred_ready = 0
    for m in matches:
        pred = m.get("predicted_label")
        if pred is None:
            pred = int((m.get("proba_ready") or 0.0) >= 0.5)
        if int(pred) == 1:
            pred_ready += 1
    return {
        "proba_ready_max": max_v,
        "proba_ready_mean": mean_v,
        "proba_ready_min": min_v,
        "proba_ready_std": std,
        "proba_ready_top2_gap": top2_gap,
        "predicted_ready_count": pred_ready,
        "scored_candidate_count": len(matches),
        "match_count": len(matches),
    }


def match_one_side(
    feature_row: dict[str, Any],
    scored_rows: list[dict[str, Any]],
    *,
    target_method: str,
    group_id_field: str,
    budget_field: str,
    seed_field: str,
) -> dict[str, Any]:
    example_id = _row_example_id(feature_row, group_id_field)
    candidate_rows = [
        r for r in scored_rows
        if _first_nonempty(r.get(group_id_field), r.get("example_id"), r.get("problem_id")) == example_id
    ]
    methods, method_mode = resolve_method_matches(candidate_rows, target_method)
    method_filtered = [r for r in candidate_rows if _norm_str(r.get("method")) in methods]

    chosen_matches: list[dict[str, Any]] = []
    key_used = ""
    for key_name, include_artifact, include_budget, include_seed in KEY_SPECS:
        matches = [
            r for r in method_filtered
            if _candidate_matches_key(
                feature_row,
                r,
                group_id_field=group_id_field,
                budget_field=budget_field,
                seed_field=seed_field,
                include_artifact=include_artifact,
                include_budget=include_budget,
                include_seed=include_seed,
            )
        ]
        if matches:
            chosen_matches = matches
            key_used = key_name
            break

    return {
        "matches": chosen_matches,
        "join_key_used": key_used,
        "method_mode": method_mode,
        "matched_methods": sorted({_norm_str(m.get("method")) for m in chosen_matches if _norm_str(m.get("method"))}),
    }


def _choose_methods(feature_row: dict[str, Any], baseline_default: str, frontier_default: str) -> tuple[str, str]:
    baseline = _first_nonempty(feature_row.get("baseline_method"), baseline_default)
    frontier = _first_nonempty(feature_row.get("frontier_method"), frontier_default)
    return baseline, frontier


def write_csv_rows(path: pathlib.Path, rows: list[dict[str, Any]], preferred_fields: list[str] | None = None) -> None:
    if preferred_fields is None:
        preferred_fields = []
    fieldnames = list(preferred_fields)
    seen = set(fieldnames)
    for r in rows:
        for k in r.keys():
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: _fmt(r.get(k)) for k in fieldnames})


def build_target_summary(joined_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    groups = [("all_rows", None)] + [(t, t) for t in TARGET_FLAGS]
    for label, flag in groups:
        if flag is None:
            subset = joined_rows
        else:
            subset = [r for r in joined_rows if _truthy(r.get(flag))]
        n_rows = len(subset)
        any_join = [r for r in subset if _norm_lower(r.get("verifier_join_status")) != "unmatched"]
        both_join = [r for r in subset if _norm_lower(r.get("verifier_join_status")) == "matched_both"]
        frontier_max_vals = [_as_float(r.get("frontier_proba_ready_max")) for r in subset]
        frontier_max_vals = [v for v in frontier_max_vals if v is not None]
        baseline_max_vals = [_as_float(r.get("baseline_proba_ready_max")) for r in subset]
        baseline_max_vals = [v for v in baseline_max_vals if v is not None]
        margin_vals = [_as_float(r.get("score_margin_frontier_minus_baseline_max")) for r in subset]
        margin_vals = [v for v in margin_vals if v is not None]
        summary_rows.append(
            {
                "target": label,
                "n_rows": n_rows,
                "n_rows_with_any_verifier_scores": len(any_join),
                "n_rows_with_both_verifier_scores": len(both_join),
                "frontier_proba_ready_max_mean": statistics.mean(frontier_max_vals) if frontier_max_vals else None,
                "baseline_proba_ready_max_mean": statistics.mean(baseline_max_vals) if baseline_max_vals else None,
                "score_margin_frontier_minus_baseline_max_mean": statistics.mean(margin_vals) if margin_vals else None,
            }
        )
    return summary_rows


def write_markdown_report(
    out_path: pathlib.Path,
    *,
    args: argparse.Namespace,
    metrics: dict[str, Any],
    target_summary: list[dict[str, Any]],
    limitations: list[str],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Verifier Score Join Report",
        "",
        f"- Generated: {now}",
        f"- Feature table: `{args.feature_table_csv}`",
        f"- Scored candidates: `{args.scored_candidates_jsonl}`",
        f"- Output directory: `{args.output_dir}`",
        "",
        "## Counts",
        "",
        f"- Feature rows loaded: {metrics['feature_rows_loaded']}",
        f"- Scored candidates loaded: {metrics['scored_candidates_loaded']}",
        f"- Feature rows matched (any side): {metrics['feature_rows_matched_any']} ({metrics['join_rate_any']*100:.1f}%)",
        f"- Feature rows matched (both sides): {metrics['feature_rows_matched_both']} ({metrics['join_rate_both']*100:.1f}%)",
        "",
        "## Join Match Rates By Artifact",
        "",
        "| Artifact Label | Rows | Matched Any | Matched Both |",
        "|---|---:|---:|---:|",
    ]
    for artifact, data in sorted(metrics["by_artifact"].items()):
        lines.append(f"| {artifact} | {data['rows']} | {data['matched_any']} | {data['matched_both']} |")

    lines += [
        "",
        "## Target Coverage With Verifier Features",
        "",
        "| Target | Rows | Any Verifier Scores | Both Sides Joined | Frontier Max Mean | Baseline Max Mean | Margin Mean |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in target_summary:
        lines.append(
            "| {target} | {n_rows} | {n_any} | {n_both} | {fmax} | {bmax} | {mmean} |".format(
                target=row["target"],
                n_rows=row["n_rows"],
                n_any=row["n_rows_with_any_verifier_scores"],
                n_both=row["n_rows_with_both_verifier_scores"],
                fmax=_fmt(row["frontier_proba_ready_max_mean"]),
                bmax=_fmt(row["baseline_proba_ready_max_mean"]),
                mmean=_fmt(row["score_margin_frontier_minus_baseline_max_mean"]),
            )
        )

    oracle = next((r for r in target_summary if r["target"] == "oracle_recoverable"), None)
    risk = next((r for r in target_summary if r["target"] == "regression_risk"), None)
    signal_line = "Insufficient oracle/regrisk rows with joined features for a stable comparison."
    if oracle and risk:
        o_mean = oracle.get("frontier_proba_ready_max_mean")
        r_mean = risk.get("frontier_proba_ready_max_mean")
        if o_mean is not None and r_mean is not None:
            signal_line = (
                "Frontier max score mean: oracle_recoverable={:.4f}, regression_risk={:.4f}, delta={:+.4f}.".format(
                    o_mean,
                    r_mean,
                    o_mean - r_mean,
                )
            )

    lines += [
        "",
        "## Preliminary Utility Signal",
        "",
        f"- {signal_line}",
        "",
        "## Mining Readiness",
        "",
        "- Enough rows for rerun suggestion uses a simple rule: any-join coverage >= 50% and both-side coverage >= 30%.",
        (
            f"- Result: {'YES' if metrics['enough_for_rerun'] else 'NO'} "
            f"(any={metrics['join_rate_any']*100:.1f}%, both={metrics['join_rate_both']*100:.1f}%)."
        ),
        "",
        "## Limitations",
        "",
    ]
    if limitations:
        for lim in limitations:
            lines.append(f"- {lim}")
    else:
        lines.append("- None noted.")

    out_path.write_text("\n".join(lines) + "\n")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--feature-table-csv", required=True)
    p.add_argument("--scored-candidates-jsonl", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--artifact-label", default="")
    p.add_argument("--artifact-path", default="")
    p.add_argument("--group-id-field", default="example_id")
    p.add_argument("--method-field", default="method")
    p.add_argument("--budget-field", default="budget")
    p.add_argument("--seed-field", default="seed")
    p.add_argument("--score-field", default="proba_ready")
    p.add_argument("--baseline-method", default="external_l1_max")
    p.add_argument("--frontier-method", default="direct_reserve_semantic_frontier_v2")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    feature_path = pathlib.Path(args.feature_table_csv)
    scored_path = pathlib.Path(args.scored_candidates_jsonl)
    if not feature_path.exists():
        print(f"ERROR: feature table not found: {feature_path}", file=sys.stderr)
        return 1
    if not scored_path.exists():
        print(f"ERROR: scored candidates file not found: {scored_path}", file=sys.stderr)
        return 1

    feature_rows, feature_fields = load_feature_rows(feature_path)
    scored_rows, provenance, load_notes = load_scored_candidates(
        scored_path,
        score_field=args.score_field,
        artifact_label=args.artifact_label,
        artifact_path=args.artifact_path,
    )

    used_scored_ids: set[int] = set()
    joined_rows: list[dict[str, Any]] = []
    diagnostics_rows: list[dict[str, Any]] = []
    unmatched_feature_rows: list[dict[str, Any]] = []
    fuzzy_count = 0
    fuzzy_examples = 0

    for idx, frow in enumerate(feature_rows):
        baseline_method, frontier_method = _choose_methods(
            frow,
            baseline_default=args.baseline_method,
            frontier_default=args.frontier_method,
        )

        base_match = match_one_side(
            frow,
            scored_rows,
            target_method=baseline_method,
            group_id_field=args.group_id_field,
            budget_field=args.budget_field,
            seed_field=args.seed_field,
        )
        front_match = match_one_side(
            frow,
            scored_rows,
            target_method=frontier_method,
            group_id_field=args.group_id_field,
            budget_field=args.budget_field,
            seed_field=args.seed_field,
        )

        base_stats = aggregate_matches(base_match["matches"])
        front_stats = aggregate_matches(front_match["matches"])

        for m in base_match["matches"]:
            used_scored_ids.add(int(m["_row_id"]))
        for m in front_match["matches"]:
            used_scored_ids.add(int(m["_row_id"]))

        if base_match["method_mode"] == "fuzzy" or front_match["method_mode"] == "fuzzy":
            fuzzy_examples += 1
            fuzzy_count += int(base_match["method_mode"] == "fuzzy") + int(front_match["method_mode"] == "fuzzy")

        if base_stats["match_count"] > 0 and front_stats["match_count"] > 0:
            join_status = "matched_both"
        elif base_stats["match_count"] > 0:
            join_status = "matched_baseline_only"
        elif front_stats["match_count"] > 0:
            join_status = "matched_frontier_only"
        else:
            join_status = "unmatched"

        joined = dict(frow)
        joined.update(
            {
                "baseline_proba_ready_max": base_stats["proba_ready_max"],
                "baseline_proba_ready_mean": base_stats["proba_ready_mean"],
                "baseline_proba_ready_min": base_stats["proba_ready_min"],
                "baseline_proba_ready_std": base_stats["proba_ready_std"],
                "baseline_proba_ready_top2_gap": base_stats["proba_ready_top2_gap"],
                "baseline_predicted_ready_count": base_stats["predicted_ready_count"],
                "baseline_scored_candidate_count": base_stats["scored_candidate_count"],
                "frontier_proba_ready_max": front_stats["proba_ready_max"],
                "frontier_proba_ready_mean": front_stats["proba_ready_mean"],
                "frontier_proba_ready_min": front_stats["proba_ready_min"],
                "frontier_proba_ready_std": front_stats["proba_ready_std"],
                "frontier_proba_ready_top2_gap": front_stats["proba_ready_top2_gap"],
                "frontier_predicted_ready_count": front_stats["predicted_ready_count"],
                "frontier_scored_candidate_count": front_stats["scored_candidate_count"],
                "score_margin_frontier_minus_baseline_max": (
                    front_stats["proba_ready_max"] - base_stats["proba_ready_max"]
                    if front_stats["proba_ready_max"] is not None and base_stats["proba_ready_max"] is not None
                    else None
                ),
                "score_margin_frontier_minus_baseline_mean": (
                    front_stats["proba_ready_mean"] - base_stats["proba_ready_mean"]
                    if front_stats["proba_ready_mean"] is not None and base_stats["proba_ready_mean"] is not None
                    else None
                ),
                "verifier_join_status": join_status,
                "verifier_join_match_count_baseline": base_stats["match_count"],
                "verifier_join_match_count_frontier": front_stats["match_count"],
            }
        )
        joined_rows.append(joined)

        diagnostics_rows.append(
            {
                "feature_row_index": idx,
                "artifact_label": _row_artifact_label(frow),
                "example_id": _row_example_id(frow, args.group_id_field),
                "baseline_method": baseline_method,
                "frontier_method": frontier_method,
                "baseline_method_match_mode": base_match["method_mode"],
                "frontier_method_match_mode": front_match["method_mode"],
                "baseline_join_key_used": base_match["join_key_used"],
                "frontier_join_key_used": front_match["join_key_used"],
                "baseline_match_count": base_stats["match_count"],
                "frontier_match_count": front_stats["match_count"],
                "baseline_matched_methods": ";".join(base_match["matched_methods"]),
                "frontier_matched_methods": ";".join(front_match["matched_methods"]),
                "verifier_join_status": join_status,
            }
        )

        if join_status == "unmatched":
            unmatched_feature_rows.append(dict(joined))

    unmatched_scored_rows = [r for r in scored_rows if int(r["_row_id"]) not in used_scored_ids]

    by_artifact: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "matched_any": 0, "matched_both": 0})
    by_method_side: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "matched": 0})
    for row in joined_rows:
        artifact = _first_nonempty(row.get("artifact_label"), "<missing_artifact_label>")
        status = _norm_lower(row.get("verifier_join_status"))
        by_artifact[artifact]["rows"] += 1
        if status != "unmatched":
            by_artifact[artifact]["matched_any"] += 1
        if status == "matched_both":
            by_artifact[artifact]["matched_both"] += 1

        bmethod = _first_nonempty(row.get("baseline_method"), args.baseline_method)
        fmethod = _first_nonempty(row.get("frontier_method"), args.frontier_method)
        by_method_side[f"baseline::{bmethod}"]["rows"] += 1
        by_method_side[f"frontier::{fmethod}"]["rows"] += 1
        if _as_int(row.get("verifier_join_match_count_baseline")) and _as_int(row.get("verifier_join_match_count_baseline")) > 0:
            by_method_side[f"baseline::{bmethod}"]["matched"] += 1
        if _as_int(row.get("verifier_join_match_count_frontier")) and _as_int(row.get("verifier_join_match_count_frontier")) > 0:
            by_method_side[f"frontier::{fmethod}"]["matched"] += 1

    feature_rows_loaded = len(feature_rows)
    matched_any = sum(1 for r in joined_rows if _norm_lower(r.get("verifier_join_status")) != "unmatched")
    matched_both = sum(1 for r in joined_rows if _norm_lower(r.get("verifier_join_status")) == "matched_both")
    join_rate_any = (matched_any / feature_rows_loaded) if feature_rows_loaded else 0.0
    join_rate_both = (matched_both / feature_rows_loaded) if feature_rows_loaded else 0.0
    enough_for_rerun = (join_rate_any >= 0.50) and (join_rate_both >= 0.30)

    target_summary = build_target_summary(joined_rows)
    summary_map = {row["target"]: row for row in target_summary}

    key_usage = Counter()
    for d in diagnostics_rows:
        if d.get("baseline_join_key_used"):
            key_usage[f"baseline::{d['baseline_join_key_used']}"] += 1
        if d.get("frontier_join_key_used"):
            key_usage[f"frontier::{d['frontier_join_key_used']}"] += 1

    limitations = list(load_notes)
    if fuzzy_count:
        limitations.append(
            f"Fuzzy method matching was used {fuzzy_count} time(s) across {fuzzy_examples} feature row(s)."
        )
    if summary_map.get("all_rows", {}).get("n_rows_with_any_verifier_scores", 0) < feature_rows_loaded:
        limitations.append("Some feature rows did not receive verifier features (unmatched rows are exported).")
    if summary_map.get("all_rows", {}).get("n_rows_with_both_verifier_scores", 0) < feature_rows_loaded:
        limitations.append("Some rows have only one side (baseline/frontier) matched.")
    if not args.artifact_label:
        limitations.append("Artifact label was not explicitly provided; best-effort inference was used.")
    if not args.artifact_path:
        limitations.append("Artifact path was not explicitly provided; best-effort inference was used.")

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "feature_table_csv": args.feature_table_csv,
            "scored_candidates_jsonl": args.scored_candidates_jsonl,
            "artifact_label_arg": args.artifact_label,
            "artifact_path_arg": args.artifact_path,
        },
        "provenance": provenance,
        "feature_rows_loaded": feature_rows_loaded,
        "scored_candidates_loaded": len(scored_rows),
        "feature_rows_matched_any": matched_any,
        "feature_rows_matched_both": matched_both,
        "join_rate_any": join_rate_any,
        "join_rate_both": join_rate_both,
        "enough_for_rerun": enough_for_rerun,
        "unmatched_feature_rows": len(unmatched_feature_rows),
        "unmatched_scored_candidates": len(unmatched_scored_rows),
        "fuzzy_method_match_count": fuzzy_count,
        "fuzzy_method_match_rows": fuzzy_examples,
        "key_usage_counts": dict(key_usage),
        "by_artifact": dict(by_artifact),
        "by_method_side": dict(by_method_side),
        "target_coverage": {row["target"]: row for row in target_summary},
        "limitations": limitations,
    }

    joined_fieldnames = feature_fields + [c for c in ADDED_COLUMNS if c not in feature_fields]
    write_csv_rows(out_dir / "joined_failure_pattern_features.csv", joined_rows, preferred_fields=joined_fieldnames)
    write_csv_rows(out_dir / "join_match_diagnostics.csv", diagnostics_rows)
    write_csv_rows(out_dir / "unmatched_feature_rows.csv", unmatched_feature_rows, preferred_fields=joined_fieldnames)
    write_csv_rows(out_dir / "unmatched_scored_candidates.csv", unmatched_scored_rows)
    write_csv_rows(out_dir / "verifier_score_feature_summary.csv", target_summary)
    with open(out_dir / "verifier_join_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    write_markdown_report(
        out_dir / "verifier_join_report.md",
        args=args,
        metrics=metrics,
        target_summary=target_summary,
        limitations=limitations,
    )

    print(f"Loaded feature rows: {feature_rows_loaded}")
    print(f"Loaded scored candidates: {len(scored_rows)}")
    print(f"Matched any: {matched_any}/{feature_rows_loaded} ({join_rate_any*100:.1f}%)")
    print(f"Matched both: {matched_both}/{feature_rows_loaded} ({join_rate_both*100:.1f}%)")
    print(f"Outputs written to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
