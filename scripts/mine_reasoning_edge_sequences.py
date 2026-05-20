#!/usr/bin/env python3
"""
mine_reasoning_edge_sequences.py

No-API trace-mining experiment: reasoning_edge_sequence_mining_v1.

Loads existing trace packets (and optionally a replay casebook / candidate
feature rows), maps every reasoning step or candidate expansion to an
edge-color, builds n-gram motifs and prefix-transition rules, and writes
seven output files.

Gold answers are used ONLY for offline quality labeling after sequences are
constructed — they never appear as input features that would be available
at inference time.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Edge-color taxonomy
# ---------------------------------------------------------------------------
EDGE_COLORS: tuple[str, ...] = (
    "target_extraction",
    "equation_setup",
    "direct_arithmetic",
    "ratio_base",
    "unit_conversion",
    "original_before_process",
    "per_unit_share",
    "profit_revenue_cost",
    "difference_remainder",
    "PAL_code",
    "verifier_check",
    "repair",
    "selector",
    "fallback",
    "unknown",
)

# Branch-family → canonical edge color
_BF_COLOR: dict[str, str] = {
    "entity_unit_ledger_reasoning": "target_extraction",
    "target_first_reasoning": "target_extraction",
    "equation_first_reasoning": "equation_setup",
    "backward_from_target_check": "verifier_check",
    "pal_code_with_required_target_variable": "PAL_code",
    # final-transform branch families
    "ratio_base_branch": "ratio_base",
    "unit_conversion_branch": "unit_conversion",
    "original_before_process_branch": "original_before_process",
    "per_unit_share_branch": "per_unit_share",
    "profit_revenue_cost_branch": "profit_revenue_cost",
    "difference_or_remainder_branch": "difference_remainder",
    "target_first_final_transform_branch": "target_extraction",
}

# last_operation_family fallback → color
_OP_COLOR: dict[str, str] = {
    "subtract": "difference_remainder",
    "add": "direct_arithmetic",
    "divide": "ratio_base",
    "multiply": "direct_arithmetic",
    "conversion": "unit_conversion",
    "ratio": "ratio_base",
}


def map_edge_color(
    branch_family: str | None = None,
    source: str | None = None,
    last_op: str | None = None,
    selected_source: str | None = None,
    is_pal_exec: bool = False,
    is_repair: bool = False,
    is_selector: bool = False,
    is_fallback: bool = False,
) -> str:
    """Deterministic, gold-free edge-color mapper."""
    if is_selector:
        return "selector"
    if is_repair:
        return "repair"
    if is_fallback:
        return "fallback"
    if is_pal_exec or source == "pal_seed":
        return "PAL_code"
    if branch_family:
        if branch_family in _BF_COLOR:
            return _BF_COLOR[branch_family]
        # Partial match
        for k, v in _BF_COLOR.items():
            if k in branch_family or branch_family in k:
                return v
    if last_op and last_op in _OP_COLOR:
        return _OP_COLOR[last_op]
    return "unknown"


# ---------------------------------------------------------------------------
# Path construction
# ---------------------------------------------------------------------------

def build_case_path(case: dict[str, Any]) -> list[str]:
    """
    Build the ordered edge-color sequence for one case.

    Strategy:
    1. Iterate candidate_rows (sorted by branch_slot) → one edge per row.
    2. Append PAL_code edge if pal_exec_ok.
    3. Append repair edge if selected_source == repair_layer.
    4. Append selector edge.

    The path reflects what the controller actually explored, not gold.
    """
    path: list[str] = []
    seen_branches: set[str] = set()

    candidate_rows: list[dict[str, Any]] = (
        case.get("structural_fields", {}).get("candidate_rows", [])
    )
    # Sort by branch_slot (string "1".."5"), then by branch_family for stability
    def _slot(r: dict) -> int:
        try:
            return int(r.get("branch_slot", 99))
        except (TypeError, ValueError):
            return 99

    for row in sorted(candidate_rows, key=_slot):
        bf = row.get("branch_family") or row.get("prompt_template_id") or ""
        lop = row.get("last_operation_family", "")
        color = map_edge_color(branch_family=bf, last_op=lop)
        key = f"{bf}|{color}"
        if key not in seen_branches:
            path.append(color)
            seen_branches.add(key)

    # PAL edge
    pal_ok = str(case.get("pal_exec_summary", {}).get("pal_exec_ok", "0")) == "1"
    if pal_ok:
        path.append("PAL_code")

    # Repair or selector
    sel_src = case.get("selector_metadata", {}).get("selected_source", "")
    if sel_src == "repair_layer":
        path.append("repair")
    path.append("selector")

    return path


def build_trace_excerpt_path(case: dict[str, Any]) -> list[str]:
    """
    Alternative path built from trace_excerpt steps (truncated, 3 steps).
    Supplements the candidate_rows path with alignment info.
    """
    path: list[str] = []
    for step in case.get("action_trace_summary", {}).get("trace_excerpt", []):
        src = step.get("source", "")
        bid = step.get("branch_id", "")
        align_cat = step.get("target_alignment_category", "")
        # Determine color from step
        if src == "pal_seed":
            color = "PAL_code"
        elif bid.startswith("pal"):
            color = "PAL_code"
        elif align_cat == "likely_intermediate_or_mistargeted":
            color = "target_extraction"
        elif align_cat == "likely_target_aligned":
            color = "equation_setup"
        else:
            color = "unknown"
        path.append(color)
    return path


# ---------------------------------------------------------------------------
# Quality label assignment (gold used only here, offline)
# ---------------------------------------------------------------------------

def assign_quality_label(
    case: dict[str, Any],
    gold_map: dict[str, dict[str, str]],
) -> str:
    """
    Return one of: exact_correct | target_aligned_proxy | wrong | unknown.

    Gold is allowed here for offline labeling only.
    """
    case_id = case.get("case_id", "")
    if case_id in gold_map:
        gd = gold_map[case_id]
        proxy_impr = gd.get("proxy_alignment_improved", "")
        proxy_score = gd.get("proxy_score_improved", "")
        if proxy_score == "True":
            return "target_aligned_proxy"
        if proxy_impr == "True":
            return "target_aligned_proxy"
        return "wrong"

    # Fallback: use average target_alignment_score from candidate_rows
    rows = case.get("structural_fields", {}).get("candidate_rows", [])
    if rows:
        try:
            avg = sum(
                float(r.get("target_alignment_score", 0.0)) for r in rows
            ) / len(rows)
            if avg >= 0.8:
                return "target_aligned_proxy"
            return "wrong"
        except (TypeError, ValueError):
            pass
    return "unknown"


# ---------------------------------------------------------------------------
# N-gram motif mining
# ---------------------------------------------------------------------------

def ngrams(seq: list[str], n: int):
    """Yield all n-grams from a sequence."""
    for i in range(len(seq) - n + 1):
        yield tuple(seq[i : i + n])


def mine_motifs(
    paths: list[list[str]],
    labels: list[str],
    max_seq_len: int,
    min_support: int,
    baseline_correct_rate: float,
) -> list[dict[str, Any]]:
    """Mine sequence motifs (unigrams through max_seq_len-grams)."""
    motif_counts: dict[tuple[str, ...], Counter] = defaultdict(Counter)

    for path, label in zip(paths, labels):
        for n in range(1, max_seq_len + 1):
            for gram in ngrams(path, n):
                motif_counts[gram][label] += 1

    rows = []
    for motif, label_counts in motif_counts.items():
        support = sum(label_counts.values())
        if support < min_support:
            continue
        correct = label_counts.get("exact_correct", 0) + label_counts.get(
            "target_aligned_proxy", 0
        )
        wrong = label_counts.get("wrong", 0)
        precision = correct / support if support > 0 else 0.0
        lift = precision / baseline_correct_rate if baseline_correct_rate > 0 else 0.0
        # Avg target_alignment_score not stored here; put 0 placeholder
        rows.append(
            {
                "sequence": json.dumps(list(motif)),
                "length": len(motif),
                "support_count": support,
                "correct_count": correct,
                "wrong_count": wrong,
                "unknown_count": label_counts.get("unknown", 0),
                "precision": round(precision, 4),
                "lift": round(lift, 4),
                "baseline_correct_rate": round(baseline_correct_rate, 4),
            }
        )

    rows.sort(key=lambda r: (-r["support_count"], -r["precision"]))
    return rows


def mine_transitions(
    paths: list[list[str]],
    labels: list[str],
    max_prefix_len: int,
    min_support: int,
    baseline_correct_rate: float,
) -> list[dict[str, Any]]:
    """Mine prefix → next-color transition rules."""
    trans: dict[tuple[tuple[str, ...], str], Counter] = defaultdict(Counter)
    example_cases: dict[tuple[tuple[str, ...], str], list[str]] = defaultdict(list)

    for path, label, *_ in zip(paths, labels, range(len(paths))):
        for n in range(1, max_prefix_len + 1):
            for i in range(len(path) - n):
                prefix = tuple(path[i : i + n])
                nxt = path[i + n]
                trans[(prefix, nxt)][label] += 1

    for idx, (path, label) in enumerate(zip(paths, labels)):
        for n in range(1, max_prefix_len + 1):
            for i in range(len(path) - n):
                prefix = tuple(path[i : i + n])
                nxt = path[i + n]
                key = (prefix, nxt)
                if len(example_cases[key]) < 3:
                    example_cases[key].append(str(idx))

    rows = []
    for (prefix, nxt), label_counts in trans.items():
        support = sum(label_counts.values())
        if support < min_support:
            continue
        correct = label_counts.get("exact_correct", 0) + label_counts.get(
            "target_aligned_proxy", 0
        )
        success_rate = correct / support if support > 0 else 0.0
        lift = success_rate / baseline_correct_rate if baseline_correct_rate > 0 else 0.0
        rows.append(
            {
                "prefix_sequence": json.dumps(list(prefix)),
                "next_color": nxt,
                "prefix_len": len(prefix),
                "support": support,
                "correct_count": correct,
                "success_rate": round(success_rate, 4),
                "lift": round(lift, 4),
                "example_case_indices": json.dumps(
                    example_cases[(prefix, nxt)][:3]
                ),
            }
        )

    rows.sort(key=lambda r: (-r["support"], -r["success_rate"]))
    return rows


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("(empty)\n", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def load_trace_packets(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            # Support both top-level batch (single line with "cases" list)
            # and one-case-per-line formats.
            if "cases" in obj:
                cases.extend(obj["cases"])
            else:
                cases.append(obj)
    return cases


def load_replay_casebook(path: Path) -> dict[str, dict[str, str]]:
    """Return case_id → row dict from a replay casebook CSV."""
    gold_map: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                gold_map[cid] = row
    return gold_map


def load_candidate_feature_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    """Return case_id → list of candidate rows."""
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                out[cid].append(row)
    return dict(out)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    cases: list[dict[str, Any]],
    paths: list[list[str]],
    labels: list[str],
    edge_rows: list[dict[str, Any]],
    motifs: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
    out_dir: Path,
    args: argparse.Namespace,
) -> str:
    n = len(cases)
    label_counts = Counter(labels)
    baseline_correct = (
        label_counts.get("exact_correct", 0)
        + label_counts.get("target_aligned_proxy", 0)
    ) / n if n > 0 else 0.0

    # Color distribution
    color_dist = Counter(e["edge_color"] for e in edge_rows)

    # Top motifs
    top_motifs = motifs[:10]
    motif_lines = "\n".join(
        f"  {m['sequence']:40s}  sup={m['support_count']:3d}  prec={m['precision']:.2f}  lift={m['lift']:.2f}"
        for m in top_motifs
    )

    # Top transitions
    top_trans = transitions[:10]
    trans_lines = "\n".join(
        f"  {t['prefix_sequence']:30s} → {t['next_color']:25s}  sup={t['support']:3d}  sr={t['success_rate']:.2f}  lift={t['lift']:.2f}"
        for t in top_trans
    )

    # Per-branch-family summary
    bf_summary: dict[str, Counter] = defaultdict(Counter)
    for case, label in zip(cases, labels):
        for row in case.get("structural_fields", {}).get("candidate_rows", []):
            bf = row.get("branch_family", "unknown")
            bf_summary[bf][label] += 1
    bf_lines = []
    for bf, lc in sorted(bf_summary.items()):
        total = sum(lc.values())
        aligned = lc.get("exact_correct", 0) + lc.get("target_aligned_proxy", 0)
        bf_lines.append(
            f"  {bf:45s} total={total:3d}  aligned={aligned:3d}  rate={aligned/total:.2f}"
        )

    report = f"""# Reasoning Edge Sequence Mining v1

- experiment: reasoning_edge_sequence_mining_v1
- source_packets: {args.trace_packets}
- replay_casebook: {getattr(args, 'replay_casebook', None)}
- out_dir: {out_dir}
- cases_loaded: {n}
- max_seq_len: {args.max_seq_len}
- min_support: {args.min_support}
- timestamp: {datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}

## Task 1 — Trace availability

Fields found in trace packets:
- action_trace_summary: action_trace_step_count, trace_excerpt (3 steps/case), failure_category,
  failure_family, final_answer_source, frontier_candidate_maturity, frontier_candidate_support,
  latest_method_failure_tag, selection_reason, selector_candidate_pool_size
- structural_fields.candidate_rows: branch_family, prompt_template_id, last_operation_family,
  target_alignment_score, final_answer_role, intermediate_answer_penalty,
  operation_cues_found, exec_ok, branch_slot
- pal_exec_summary: pal_exec_ok, pal_execution_status, pal_retry_reason
- selector_metadata: selected_answer, selected_source, frontier_answer, direct_reserve_answer,
  gold_present_in_candidate_pool, answer_group_support_counts
- failure_audit_labels: question_type, diversity_bucket, num_candidate_groups, candidate_pool_status

Fields absent (cannot use for edge-color):
- operation_sequence_key: NOT in traces
- reasoning_signature_key: NOT in traces
- reasoning_role: NOT in traces (branch_family substitutes)
- final_branch_states: NOT in traces
- gold answers: in replay casebook only (used for offline labeling, not features)

Note: trace_excerpt is truncated to 3 steps per case (full traces have 5-6 steps).
All trace_excerpt steps have action=expand only; branch_id distinguishes div_* vs pal_seed_*.

## Task 2 — Edge-color taxonomy

Colors used (deterministic, gold-free):
{json.dumps(list(EDGE_COLORS), indent=2)}

Color distribution across all candidate edges:
{chr(10).join(f'  {k:30s}: {v}' for k, v in color_dist.most_common())}

## Quality label distribution (offline, gold-from-casebook)

{json.dumps(dict(label_counts), indent=2)}

Baseline correct rate (target_aligned_proxy + exact_correct): {baseline_correct:.3f}

## Top-10 motifs by support

{motif_lines if motif_lines else '(none above min_support)'}

## Top-10 prefix → next-color transitions

{trans_lines if trans_lines else '(none above min_support)'}

## Per-branch-family alignment summary

{chr(10).join(bf_lines)}

## Interpretation notes

- The path sequence per case is: [bf_colors from candidate_rows sorted by slot]
  + [PAL_code if pal_exec_ok] + [repair if selected_source=repair_layer] + [selector]
- "target_aligned_proxy" means proxy_score_improved=True in replay casebook
  (not a gold exact-match; used only for offline quality ranking)
- Lift = precision / baseline_correct_rate (lift > 1.0 means above-average quality)
- All sequences are inferred from candidate structure, not full runtime trees
"""
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mine reasoning edge sequences from trace packets.")
    p.add_argument("--trace-packets", required=True, type=Path)
    p.add_argument("--candidate-feature-rows", type=Path, default=None)
    p.add_argument("--replay-casebook", type=Path, default=None)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--max-seq-len", type=int, default=4)
    p.add_argument("--min-support", type=int, default=3)
    p.add_argument("--include-gold-for-scoring", type=str, default="true")
    p.add_argument("--no-gold-features", type=str, default="true")
    p.add_argument("--limit", type=int, default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Load cases
    print(f"Loading trace packets from {args.trace_packets}", flush=True)
    cases = load_trace_packets(args.trace_packets)
    if args.limit:
        cases = cases[: args.limit]
    print(f"  Loaded {len(cases)} cases", flush=True)

    # Load gold map (offline scoring only)
    gold_map: dict[str, dict[str, str]] = {}
    use_gold = str(args.include_gold_for_scoring).lower() in ("true", "1", "yes")
    if use_gold and args.replay_casebook and args.replay_casebook.exists():
        print(f"Loading replay casebook from {args.replay_casebook}", flush=True)
        gold_map = load_replay_casebook(args.replay_casebook)
        print(f"  Loaded {len(gold_map)} case scoring rows", flush=True)

    # Load supplemental candidate feature rows
    extra_cand_rows: dict[str, list[dict[str, str]]] = {}
    if args.candidate_feature_rows and args.candidate_feature_rows.exists():
        print(f"Loading candidate feature rows from {args.candidate_feature_rows}", flush=True)
        extra_cand_rows = load_candidate_feature_rows(args.candidate_feature_rows)
        print(f"  Loaded feature rows for {len(extra_cand_rows)} cases", flush=True)

    # Build paths and quality labels
    paths: list[list[str]] = []
    labels: list[str] = []
    case_ids: list[str] = []

    for case in cases:
        path = build_case_path(case)
        label = assign_quality_label(case, gold_map)
        paths.append(path)
        labels.append(label)
        case_ids.append(case.get("case_id", "?"))

    n = len(cases)
    label_counts = Counter(labels)
    baseline_correct = (
        label_counts.get("exact_correct", 0) + label_counts.get("target_aligned_proxy", 0)
    ) / n if n > 0 else 0.0
    print(f"  Quality labels: {dict(label_counts)}", flush=True)
    print(f"  Baseline correct rate: {baseline_correct:.3f}", flush=True)

    # Build edge_color_rows (one row per candidate-row edge)
    edge_rows: list[dict[str, Any]] = []
    for case, path, label in zip(cases, paths, labels):
        case_id = case.get("case_id", "?")
        question_type = case.get("failure_audit_labels", {}).get("question_type", "")
        pal_ok = str(case.get("pal_exec_summary", {}).get("pal_exec_ok", "0")) == "1"
        sel_src = case.get("selector_metadata", {}).get("selected_source", "")
        cand_rows = case.get("structural_fields", {}).get("candidate_rows", [])

        for i, row in enumerate(sorted(cand_rows, key=lambda r: int(r.get("branch_slot", 99) if str(r.get("branch_slot", 99)).isdigit() else 99))):
            bf = row.get("branch_family") or row.get("prompt_template_id") or ""
            lop = row.get("last_operation_family", "")
            color = map_edge_color(branch_family=bf, last_op=lop)
            edge_rows.append(
                {
                    "case_id": case_id,
                    "edge_index": i,
                    "edge_color": color,
                    "branch_family": bf,
                    "last_op_family": lop,
                    "final_answer_role": row.get("final_answer_role", ""),
                    "target_alignment_score": row.get("target_alignment_score", ""),
                    "intermediate_answer_penalty": row.get("intermediate_answer_penalty", ""),
                    "exec_ok": row.get("exec_ok", ""),
                    "question_type": question_type,
                    "pal_ok": pal_ok,
                    "selected_source": sel_src,
                    "quality_label": label,
                    "source_field": "structural_fields.candidate_rows",
                }
            )
        # PAL edge
        if pal_ok:
            edge_rows.append(
                {
                    "case_id": case_id,
                    "edge_index": len(cand_rows),
                    "edge_color": "PAL_code",
                    "branch_family": "pal",
                    "last_op_family": "",
                    "final_answer_role": "",
                    "target_alignment_score": "",
                    "intermediate_answer_penalty": "",
                    "exec_ok": "True",
                    "question_type": question_type,
                    "pal_ok": pal_ok,
                    "selected_source": sel_src,
                    "quality_label": label,
                    "source_field": "pal_exec_summary",
                }
            )
        # Selector edge
        edge_rows.append(
            {
                "case_id": case_id,
                "edge_index": len(cand_rows) + (1 if pal_ok else 0),
                "edge_color": "repair" if sel_src == "repair_layer" else "selector",
                "branch_family": sel_src,
                "last_op_family": "",
                "final_answer_role": "",
                "target_alignment_score": "",
                "intermediate_answer_penalty": "",
                "exec_ok": "",
                "question_type": question_type,
                "pal_ok": pal_ok,
                "selected_source": sel_src,
                "quality_label": label,
                "source_field": "selector_metadata",
            }
        )

    # Build path_sequence_rows
    path_seq_rows: list[dict[str, Any]] = []
    for case_id, path, label, case in zip(case_ids, paths, labels, cases):
        trace_path = build_trace_excerpt_path(case)
        path_seq_rows.append(
            {
                "case_id": case_id,
                "path_json": json.dumps(path),
                "path_length": len(path),
                "trace_excerpt_path_json": json.dumps(trace_path),
                "unique_colors": len(set(path)),
                "quality_label": label,
                "question_type": case.get("failure_audit_labels", {}).get("question_type", ""),
                "pal_exec_ok": case.get("pal_exec_summary", {}).get("pal_exec_ok", ""),
                "selected_source": case.get("selector_metadata", {}).get("selected_source", ""),
                "selection_reason": case.get("action_trace_summary", {}).get("selection_reason", ""),
                "diversity_bucket": case.get("failure_audit_labels", {}).get("diversity_bucket", ""),
            }
        )

    # Mine motifs
    print("Mining motifs...", flush=True)
    motifs = mine_motifs(paths, labels, args.max_seq_len, args.min_support, baseline_correct)
    print(f"  Found {len(motifs)} motifs above min_support={args.min_support}", flush=True)

    # Mine transitions
    print("Mining transitions...", flush=True)
    transitions = mine_transitions(
        paths, labels, max(1, args.max_seq_len - 1), args.min_support, baseline_correct
    )
    # Enrich transitions with example case IDs
    # Re-run to attach case IDs (stored by index above, now replace with actual IDs)
    for t in transitions:
        indices_str = t.get("example_case_indices", "[]")
        try:
            indices = json.loads(indices_str)
            t["example_case_ids"] = json.dumps(
                [case_ids[int(i)] for i in indices if int(i) < len(case_ids)]
            )
        except Exception:
            t["example_case_ids"] = "[]"
    print(f"  Found {len(transitions)} transitions above min_support={args.min_support}", flush=True)

    # Build case_sequence_casebook
    casebook_rows: list[dict[str, Any]] = []
    for case_id, path, label, case in zip(case_ids, paths, labels, cases):
        ats = case.get("action_trace_summary", {})
        sm = case.get("selector_metadata", {})
        fal = case.get("failure_audit_labels", {})
        casebook_rows.append(
            {
                "case_id": case_id,
                "path_json": json.dumps(path),
                "path_length": len(path),
                "quality_label": label,
                "question_type": fal.get("question_type", ""),
                "diversity_bucket": fal.get("diversity_bucket", ""),
                "num_candidate_groups": fal.get("num_candidate_groups", ""),
                "pal_exec_ok": case.get("pal_exec_summary", {}).get("pal_exec_ok", ""),
                "selection_reason": ats.get("selection_reason", ""),
                "final_answer_source": ats.get("final_answer_source", ""),
                "selected_source": sm.get("selected_source", ""),
                "selected_answer": sm.get("selected_answer", ""),
                "action_trace_step_count": ats.get("action_trace_step_count", ""),
                "latest_failure_tag": ats.get("latest_method_failure_tag", ""),
            }
        )

    # Write outputs
    print("Writing outputs...", flush=True)

    write_csv(args.out_dir / "edge_color_rows.csv", edge_rows)
    write_csv(args.out_dir / "path_sequence_rows.csv", path_seq_rows)
    write_csv(args.out_dir / "motif_summary.csv", motifs)
    write_csv(args.out_dir / "transition_rules.csv", transitions)
    write_csv(args.out_dir / "case_sequence_casebook.csv", casebook_rows)

    report_text = generate_report(
        cases, paths, labels, edge_rows, motifs, transitions, args.out_dir, args
    )
    (args.out_dir / "report.md").write_text(report_text, encoding="utf-8")

    manifest = {
        "experiment": "reasoning_edge_sequence_mining_v1",
        "timestamp_utc": ts,
        "trace_packets": str(args.trace_packets),
        "replay_casebook": str(args.replay_casebook) if args.replay_casebook else None,
        "candidate_feature_rows": str(args.candidate_feature_rows) if args.candidate_feature_rows else None,
        "out_dir": str(args.out_dir),
        "cases_loaded": n,
        "max_seq_len": args.max_seq_len,
        "min_support": args.min_support,
        "include_gold_for_scoring": use_gold,
        "no_gold_features": str(args.no_gold_features).lower() in ("true", "1"),
        "edge_rows": len(edge_rows),
        "path_seq_rows": len(path_seq_rows),
        "motifs_found": len(motifs),
        "transitions_found": len(transitions),
        "quality_label_counts": dict(label_counts),
        "baseline_correct_rate": round(baseline_correct, 4),
        "edge_colors_used": list(EDGE_COLORS),
        "outputs": [
            "manifest.json",
            "edge_color_rows.csv",
            "path_sequence_rows.csv",
            "motif_summary.csv",
            "transition_rules.csv",
            "case_sequence_casebook.csv",
            "report.md",
        ],
        "api_calls_made": 0,
    }
    with open(args.out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Done. Report: {args.out_dir}/report.md", flush=True)
    return manifest


if __name__ == "__main__":
    main()
