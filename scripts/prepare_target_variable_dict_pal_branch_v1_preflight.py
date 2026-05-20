#!/usr/bin/env python3
"""
prepare_target_variable_dict_pal_branch_v1_preflight.py

No-API dry-run preflight for target_variable_dict_pal_branch_v1.

Selects gold-absent (or all) cases from trace packets, ranks them with
gold-free cues, renders the target-variable dict prompt, audits for gold
leakage, and writes all preflight artifacts.  No model API is called.

Case selection note
-------------------
All 97 trace-packet cases carry the same batch-level ``selection_logic``
string ("gold_absent rows with external_contrast == 'Both wrong'...")
in their subset_memberships.  That string describes the query that built
the batch, NOT individual per-case gold membership.  Reading it naively
marks all 97 cases as gold-absent, which is wrong.

The authoritative per-case gold-absent / gold-present split (70 / 27) is
in the gold pool report (Section B: gold_absent_from_pool).  When
``--gold-pool-report`` is supplied the script parses that file to obtain
the correct 70 gold-absent case IDs and uses them for filtering.  Without
the report, all cases are included and the manifest is labelled
``all_wrong_consensus_cases`` to avoid a false gold-absent claim.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.mine_reasoning_edge_sequences import load_trace_packets

EXPERIMENT_ID = "target_variable_dict_pal_branch_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

PROMPT_TEMPLATE_PATH = REPO_ROOT / "prompts" / "target_variable_dict_pal_branch_v1.md"

# Patterns that must not appear in rendered prompts
_FORBIDDEN_PROMPT_RE = [
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
]

# Gold-free question cue patterns
_PROFIT_RE = re.compile(
    r"\b(profit|revenue|cost|earn|charge|price|fee|income|expense|spend|spent|pay|paid|sale|sell|sold)\b", re.I
)
_DIFF_RE = re.compile(
    r"\b(left|remaining|leftover|difference|fewer|less|subtract|how many more|how much more|remain|remainder)\b", re.I
)
_RATIO_RE = re.compile(
    r"(\d+\s*%|percent|percentage|ratio|fraction|proportion|rate|per cent)", re.I
)
_ORIG_BEFORE_RE = re.compile(
    r"\b(before|original|initially|was|had|used to|start with|began with|at first)\b", re.I
)
_PER_UNIT_RE = re.compile(r"\b(each|per|every|apiece|per unit|per item)\b", re.I)
_UNIT_CONV_RE = re.compile(
    r"\b(convert|feet|foot|meters?|metres?|miles?|km|kilometers?|hours?|minutes?|seconds?|"
    r"lb|lbs|pounds?|kg|kilograms?|gallons?|liters?|litres?|inches?|yards?|celsius|fahrenheit|ounces?|oz)\b",
    re.I,
)
_TRANSFORMED_TARGET_RE = re.compile(
    r"\b(profit|revenue|cost|difference|remaining|percent|percentage|ratio|fraction|"
    r"before|original|each|per|apiece|convert|left|remainder)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Cue extraction (gold-free)
# ---------------------------------------------------------------------------

def _extract_question_cues(question: str) -> list[str]:
    cues: list[str] = []
    q = question or ""
    if _PROFIT_RE.search(q):
        cues.append("profit_revenue_cost")
    if _DIFF_RE.search(q):
        cues.append("difference_or_remainder")
    if _RATIO_RE.search(q):
        cues.append("ratio_base")
    if _ORIG_BEFORE_RE.search(q):
        cues.append("original_before_process")
    if _PER_UNIT_RE.search(q):
        cues.append("per_unit_share")
    if _UNIT_CONV_RE.search(q):
        cues.append("unit_conversion")
    return cues


def _transformed_target_cue_count(question: str) -> int:
    return len(_TRANSFORMED_TARGET_RE.findall(question or ""))


# ---------------------------------------------------------------------------
# Case scoring (gold-free)
# ---------------------------------------------------------------------------

def _score_case(
    case_id: str,
    question: str,
    cues: list[str],
    transformed_cue_count: int,
    det_rec: str,
    heldout_label: str,
) -> int:
    score = 0
    if det_rec == "backward_from_target_check":
        score += 3
    if heldout_label == "backward_from_target_check":
        score += 2
    if transformed_cue_count > 0:
        score += 2
    score += len(cues)
    return score


# ---------------------------------------------------------------------------
# Gold-absent detection
# ---------------------------------------------------------------------------

# Matches a markdown table row starting with a case ID, e.g.:
#   | openai_gsm8k_1003 | ...
_CASE_ID_ROW_RE = re.compile(r"^\|\s*([A-Za-z0-9_]+)\s*\|")


def parse_gold_pool_report(path: Path) -> tuple[set[str], set[str]]:
    """
    Parse gold_pool_split report markdown and return
    (gold_absent_ids, gold_present_not_selected_ids).

    Section A (## A. gold_present_not_selected) → gold_present_not_selected_ids
    Section B (## B. gold_absent_from_pool)     → gold_absent_ids

    Both sets contain only rows where the first column looks like a case ID
    (not a header row like "case_id").
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Locate section boundaries
    section_a_start: int | None = None
    section_b_start: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+A\.", line):
            section_a_start = i
        elif re.match(r"^##\s+B\.", line):
            section_b_start = i

    def _extract_ids(start: int | None, end: int | None) -> set[str]:
        ids: set[str] = set()
        if start is None:
            return ids
        stop = end if end is not None else len(lines)
        for line in lines[start:stop]:
            m = _CASE_ID_ROW_RE.match(line)
            if m:
                cid = m.group(1)
                if cid.lower() != "case_id":
                    ids.add(cid)
        return ids

    gold_present_ids = _extract_ids(section_a_start, section_b_start)
    gold_absent_ids = _extract_ids(section_b_start, None)
    return gold_absent_ids, gold_present_ids


# ---------------------------------------------------------------------------
# Prompt rendering and audit
# ---------------------------------------------------------------------------

def _load_prompt_template() -> str:
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def render_prompt(template: str, question: str) -> str:
    rendered = template.replace("{{question}}", question)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("unresolved placeholder in prompt template")
    return rendered


def audit_prompt(prompt: str, case_id: str) -> dict[str, Any]:
    violations: list[str] = []
    for pattern in _FORBIDDEN_PROMPT_RE:
        m = pattern.search(prompt)
        if m:
            violations.append(f"forbidden pattern '{pattern.pattern}' matched at pos {m.start()}")
    return {
        "case_id": case_id,
        "gold_free": len(violations) == 0,
        "violations": violations,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt_char_count": len(prompt),
    }


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_csv_by_case_id(path: Path, key_col: str = "case_id") -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not path or not path.exists():
        return rows
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            k = row.get(key_col, "")
            if k:
                rows[k] = dict(row)
    return rows


def _load_heldout_policy_rows(path: Path) -> dict[str, str]:
    """Return case_id → true_label from the last split of combined_edge_node_policy."""
    if not path or not path.exists():
        return {}
    labels: dict[str, str] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("policy") == "combined_edge_node_policy":
                cid = row.get("case_id", "")
                if cid:
                    labels[cid] = row.get("true_label", "")
    return labels


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("(empty)\n", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                        for k, v in row.items()})


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _generate_report(
    args: argparse.Namespace,
    n_loaded: int,
    n_selected: int,
    cue_dist: Counter,
    gold_free_all: bool,
    det_rec_counts: Counter,
    heldout_label_counts: Counter,
    case_selection_source: str = "unknown",
) -> str:
    lines = [
        f"# Target-Variable Dict PAL Branch v1 — Dry-Run Preflight",
        f"**Timestamp:** {_TS}  ",
        f"**Experiment:** {EXPERIMENT_ID}  ",
        f"**Mode:** no_api_preflight_only  ",
        "",
        "## Case Selection",
        f"- Trace packets loaded: {n_loaded}",
        f"- Cases selected: {n_selected}",
        f"- Selection source: {case_selection_source}",
        f"- Subset requested: {args.subset}",
        f"- Limit applied: {args.limit or 'none'}",
        "",
        "## Gold-Free Cue Distribution",
        "",
    ]
    for cue, cnt in cue_dist.most_common():
        lines.append(f"- {cue}: {cnt}")
    lines += [
        "",
        "## Routing Signals",
        "",
    ]
    if det_rec_counts:
        for rec, cnt in det_rec_counts.most_common(5):
            lines.append(f"- det_rec={rec}: {cnt}")
    if heldout_label_counts:
        for lbl, cnt in heldout_label_counts.most_common(5):
            lines.append(f"- heldout_label={lbl}: {cnt}")
    lines += [
        "",
        f"## Gold Safety",
        f"- All prompts gold-free: {gold_free_all}",
        "",
        "## Safe Claims",
        "- This is a no-API preflight. No model API was called.",
        "- Case selection uses only gold-free features.",
        "- Prompt template passes gold-leak audit.",
        "",
        "## Unsafe Claims",
        "- Do not claim accuracy improvement without live pilot evidence.",
        "- Do not run live pilot until preflight passes and evidence threshold is confirmed.",
        "",
        "## Recommended Next Steps",
        "- Review selected_cases.jsonl and provider_requests_dry_run.jsonl.",
        "- If prompts pass audit, run ≤12-case Cohere-only fixed-budget live pilot.",
        "- Validate JSON schema compliance on live outputs.",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="No-API preflight for target_variable_dict_pal_branch_v1.")
    p.add_argument("--trace-packets", required=True, type=Path)
    p.add_argument("--gold-pool-report", type=Path, default=None)
    p.add_argument("--missing-edge-recommendations", type=Path, default=None)
    p.add_argument("--heldout-policy-rows", type=Path, default=None)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--subset", choices=["gold_absent", "all"], default="gold_absent")
    p.add_argument("--model-label", default=EXPERIMENT_ID)
    p.add_argument("--max-output-tokens", type=int, default=2048)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    print(f"Loading trace packets from {args.trace_packets}", flush=True)
    cases = load_trace_packets(args.trace_packets)
    print(f"  Loaded {len(cases)} cases", flush=True)

    det_recs = _load_csv_by_case_id(args.missing_edge_recommendations) if args.missing_edge_recommendations else {}
    heldout_labels = _load_heldout_policy_rows(args.heldout_policy_rows) if args.heldout_policy_rows else {}
    print(f"  Det recs: {len(det_recs)}  Heldout labels: {len(heldout_labels)}", flush=True)

    # ------------------------------------------------------------------
    # Determine gold-absent case IDs
    # ------------------------------------------------------------------
    # The subset_memberships.selection_logic field is a batch-level query
    # description shared by all cases in the packet — not per-case gold
    # membership.  The authoritative split comes from the gold pool report.
    gold_absent_ids: set[str] | None = None
    case_selection_source: str

    if args.gold_pool_report and args.gold_pool_report.exists():
        gold_absent_ids, gold_present_ids = parse_gold_pool_report(args.gold_pool_report)
        print(f"  Gold pool report: {len(gold_absent_ids)} gold-absent IDs, "
              f"{len(gold_present_ids)} gold-present-not-selected IDs", flush=True)
        case_selection_source = "gold_pool_report"
    else:
        print("  WARNING: --gold-pool-report not provided; cannot determine per-case "
              "gold-absent status.  Under --subset gold_absent all cases will be included "
              "and labelled 'all_wrong_consensus_cases'.", flush=True)
        case_selection_source = "all_wrong_consensus_cases"

    template = _load_prompt_template()

    # ------------------------------------------------------------------
    # Select and rank cases
    # ------------------------------------------------------------------
    selected: list[dict[str, Any]] = []
    for case in cases:
        case_id = case.get("case_id", "")
        if not case_id:
            continue

        if args.subset == "gold_absent":
            if gold_absent_ids is not None:
                # Use authoritative IDs from the report
                if case_id not in gold_absent_ids:
                    continue
            # If no report, include all (and label accordingly)

        question = case.get("question", "")
        cues = _extract_question_cues(question)
        tc_count = _transformed_target_cue_count(question)
        det_rec = det_recs.get(case_id, {}).get("primary_recommendation", "")
        heldout_label = heldout_labels.get(case_id, "")

        # Record whether this case is in the authoritative gold-absent set
        if gold_absent_ids is not None:
            is_gold_absent = case_id in gold_absent_ids
        else:
            is_gold_absent = None  # unknown without the report

        score = _score_case(case_id, question, cues, tc_count, det_rec, heldout_label)
        selected.append({
            "case_id": case_id,
            "question": question,
            "cues": cues,
            "transformed_cue_count": tc_count,
            "det_rec": det_rec,
            "heldout_label": heldout_label,
            "score": score,
            "gold_absent": is_gold_absent,
        })

    # Sort by descending score, then case_id for determinism
    selected.sort(key=lambda r: (-r["score"], r["case_id"]))
    if args.limit:
        selected = selected[: args.limit]

    print(f"  Selected {len(selected)} cases (subset={args.subset})", flush=True)

    # ------------------------------------------------------------------
    # Render prompts and audit
    # ------------------------------------------------------------------
    selected_cases_out: list[dict[str, Any]] = []
    provider_requests: list[dict[str, Any]] = []
    routing_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    cue_dist: Counter = Counter()
    det_rec_counts: Counter = Counter()
    heldout_label_counts: Counter = Counter()
    gold_free_all = True

    for idx, rec in enumerate(selected, start=1):
        case_id = rec["case_id"]
        question = rec["question"]
        cues = rec["cues"]

        prompt = render_prompt(template, question)
        audit = audit_prompt(prompt, case_id)
        if not audit["gold_free"]:
            gold_free_all = False

        for cue in cues:
            cue_dist[cue] += 1
        det_rec_counts[rec["det_rec"] or "none"] += 1
        heldout_label_counts[rec["heldout_label"] or "none"] += 1

        request_id = f"{EXPERIMENT_ID}:{case_id}:{idx:05d}"

        selected_cases_out.append({
            "case_id": case_id,
            "question": question,
            "cues": cues,
            "transformed_cue_count": rec["transformed_cue_count"],
            "det_rec": rec["det_rec"],
            "heldout_label": rec["heldout_label"],
            "score": rec["score"],
            "gold_absent": rec["gold_absent"],
            "prompt_sha256": audit["prompt_sha256"],
            "gold_free": audit["gold_free"],
        })

        provider_requests.append({
            "request_id": request_id,
            "experiment_id": EXPERIMENT_ID,
            "model_label": args.model_label,
            "case_id": case_id,
            "case_index": idx,
            "prompt_template_id": EXPERIMENT_ID,
            "prompt_template_path": str(PROMPT_TEMPLATE_PATH.relative_to(REPO_ROOT)),
            "prompt_text": prompt,
            "prompt_sha256": audit["prompt_sha256"],
            "max_output_tokens": args.max_output_tokens,
            "dry_run": True,
            "api_call_made": False,
            "gold_free": audit["gold_free"],
            "routing_cues": cues,
            "score": rec["score"],
        })

        routing_rows.append({
            "case_id": case_id,
            "case_index": idx,
            "score": rec["score"],
            "cues": "|".join(cues),
            "transformed_cue_count": rec["transformed_cue_count"],
            "det_rec": rec["det_rec"],
            "heldout_label": rec["heldout_label"],
            "gold_absent": rec["gold_absent"],
            "gold_free": audit["gold_free"],
            "prompt_sha256": audit["prompt_sha256"],
        })

        audit_rows.append(audit)

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    _write_jsonl(args.out_dir / "selected_cases.jsonl", selected_cases_out)
    _write_jsonl(args.out_dir / "provider_requests_dry_run.jsonl", provider_requests)
    _write_csv(args.out_dir / "routing_summary.csv", routing_rows)
    _write_json(args.out_dir / "prompt_audit.json", {
        "all_gold_free": gold_free_all,
        "n_prompts": len(audit_rows),
        "violations": [a for a in audit_rows if not a["gold_free"]],
        "audits": audit_rows,
    })

    report = _generate_report(
        args=args,
        n_loaded=len(cases),
        n_selected=len(selected),
        cue_dist=cue_dist,
        gold_free_all=gold_free_all,
        det_rec_counts=det_rec_counts,
        heldout_label_counts=heldout_label_counts,
        case_selection_source=case_selection_source,
    )
    (args.out_dir / "dry_run_report.md").write_text(report, encoding="utf-8")

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "mode": "dry_run_only",
        "api_calls_made": 0,
        "runtime_defaults_changed": False,
        "gold_leakage_allowed": False,
        "no_gold_features": True,
        "all_prompts_gold_free": gold_free_all,
        "trace_packets": str(args.trace_packets),
        "gold_pool_report": str(args.gold_pool_report),
        "missing_edge_recommendations": str(args.missing_edge_recommendations),
        "heldout_policy_rows": str(args.heldout_policy_rows),
        "out_dir": str(args.out_dir),
        "subset": args.subset,
        "case_selection_source": case_selection_source,
        "gold_absent_ids_from_report": len(gold_absent_ids) if gold_absent_ids is not None else None,
        "limit": args.limit,
        "model_label": args.model_label,
        "max_output_tokens": args.max_output_tokens,
        "cases_loaded": len(cases),
        "cases_selected": len(selected),
        "cue_distribution": dict(cue_dist.most_common()),
        "prompt_template": str(PROMPT_TEMPLATE_PATH.relative_to(REPO_ROOT)),
        "outputs": [
            "manifest.json",
            "selected_cases.jsonl",
            "provider_requests_dry_run.jsonl",
            "routing_summary.csv",
            "prompt_audit.json",
            "dry_run_report.md",
        ],
    }
    _write_json(args.out_dir / "manifest.json", manifest)

    print(f"\nDone. Output: {args.out_dir}", flush=True)
    print(f"  Cases selected: {len(selected)}", flush=True)
    print(f"  All prompts gold-free: {gold_free_all}", flush=True)
    print(f"  Cue distribution: {dict(cue_dist.most_common())}", flush=True)

    return manifest


if __name__ == "__main__":
    main()
