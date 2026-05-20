#!/usr/bin/env python3
"""
prepare_backward_from_target_check_live_pilot_v1_preflight.py

No-API dry-run preflight for backward_from_target_check_live_pilot_v1.

Selects gold-absent wrong-supported-consensus cases from trace packets,
renders the BFTC live pilot prompt, audits for gold leakage, and writes
all preflight artifacts. No model API is called.

Case selection note
-------------------
All 97 trace-packet cases carry the same batch-level selection_logic string
in subset_memberships. That string describes the query that built the batch,
NOT individual per-case gold membership. The authoritative per-case split
(70 gold-absent / 21 gold-present-not-selected / 6 other) is in the gold
pool report (Section B: gold_absent_from_pool). When --gold-pool-report is
supplied the script uses that file to filter to the correct gold-absent IDs.
Without the report, all wrong-consensus cases are included and the manifest
is labelled 'all_wrong_consensus_cases' to avoid a false gold-absent claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.mine_reasoning_edge_sequences import load_trace_packets

EXPERIMENT_ID = "backward_from_target_check_live_pilot_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

PROMPT_TEMPLATE_PATH = (
    REPO_ROOT / "prompts" / "backward_from_target_check_live_pilot_v1.md"
)

_REQUIRED_OUTPUT_FIELDS = [
    "target_identified",
    "target_unit",
    "backward_check_steps",
    "candidate_pool_review",
    "final_answer",
]

_FORBIDDEN_PROMPT_RE = [
    re.compile(r"\bgold_answer\b\s*[:=]", re.I),
    re.compile(r"\banswer_key\b\s*[:=]", re.I),
    re.compile(r"\bhidden[_ -]?labels?\b\s*[:=]", re.I),
    re.compile(r"\bgold\b\s*[:=]", re.I),
]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Prompt loading and rendering
# ---------------------------------------------------------------------------

def _load_prompt_template() -> str:
    if not PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"BFTC pilot prompt template not found: {PROMPT_TEMPLATE_PATH}\n"
            "Expected: prompts/backward_from_target_check_live_pilot_v1.md"
        )
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def render_prompt(template: str, question: str, candidate_pool_summary: str) -> str:
    rendered = template.replace("{{question}}", question)
    rendered = rendered.replace("{{candidate_pool_summary}}", candidate_pool_summary)
    unresolved = re.findall(r"\{\{[^}]+\}\}", rendered)
    if unresolved:
        raise ValueError(f"Unresolved placeholders after render: {unresolved}")
    return rendered


def audit_prompt(text: str, case_id: str) -> dict[str, Any]:
    violations: list[str] = []
    for pattern in _FORBIDDEN_PROMPT_RE:
        if pattern.search(text):
            violations.append(pattern.pattern)
    return {
        "case_id": case_id,
        "gold_free": len(violations) == 0,
        "violations": violations,
        "prompt_sha256": _sha256(text),
        "prompt_length": len(text),
    }


# ---------------------------------------------------------------------------
# Case data extraction
# ---------------------------------------------------------------------------

def _extract_candidate_pool(case: dict[str, Any]) -> list[str]:
    """Return prior model-generated candidate values (gold-free: numeric strings only)."""
    raw = case.get("candidate_answers", [])
    if not isinstance(raw, list):
        return []
    return [str(v).strip() for v in raw if str(v).strip()]


def _build_candidate_pool_summary(values: list[str]) -> str:
    if not values:
        return "(no prior candidates recorded)"
    joined = ", ".join(values)
    return (
        f"{joined} "
        "(these are model-generated values from prior frontier branches; "
        "none are confirmed as correct)"
    )


# ---------------------------------------------------------------------------
# Gold pool report parsing
# ---------------------------------------------------------------------------

def parse_gold_pool_report(path: Path) -> tuple[set[str], set[str]]:
    """Return (gold_absent_ids, gold_present_ids) from a markdown gold pool report.

    Sections:
      ## A. gold_present_not_selected  → gold_present_ids
      ## B. gold_absent_from_pool      → gold_absent_ids
    Table rows of the form: | case_id | ... | are parsed; header rows are skipped.
    """
    text = path.read_text(encoding="utf-8")
    gold_absent: set[str] = set()
    gold_present: set[str] = set()
    in_present = False
    in_absent = False

    for line in text.splitlines():
        if re.search(r"##\s*A\.\s*gold_present_not_selected", line, re.I):
            in_present, in_absent = True, False
            continue
        if re.search(r"##\s*B\.\s*gold_absent_from_pool", line, re.I):
            in_absent, in_present = True, False
            continue
        if line.startswith("## "):  # level-2 only; "###" sub-headers do not reset state
            in_present = in_absent = False

        m = re.match(r"\|\s*([a-zA-Z0-9_]+)\s*\|", line)
        if m:
            cid = m.group(1)
            if cid == "case_id":
                continue
            if in_present:
                gold_present.add(cid)
            elif in_absent:
                gold_absent.add(cid)

    return gold_absent, gold_present


# ---------------------------------------------------------------------------
# Case selection
# ---------------------------------------------------------------------------

def _select_cases(
    cases: list[dict[str, Any]],
    gold_absent_ids: set[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Deterministically select up to `limit` cases sorted by case_id.

    If gold_absent_ids is provided, restrict to those IDs before sorting.
    """
    if gold_absent_ids is not None:
        eligible = [c for c in cases if c.get("case_id", "") in gold_absent_ids]
    else:
        eligible = list(cases)
    eligible.sort(key=lambda c: c.get("case_id", ""))
    return eligible[:limit]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Load prompt template
    # ------------------------------------------------------------------
    try:
        template = _load_prompt_template()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load trace packets
    # ------------------------------------------------------------------
    if not args.trace_packets.exists():
        print(
            f"ERROR: trace packets file not found: {args.trace_packets}\n"
            "Supply --trace-packets pointing to the wrong-consensus-97 trace packet JSONL.\n"
            "Typical path: /tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl",
            file=sys.stderr,
        )
        sys.exit(1)

    cases = load_trace_packets(args.trace_packets)
    if not cases:
        print(
            f"ERROR: No cases loaded from {args.trace_packets}.\n"
            "Check that the file is non-empty and in the expected JSONL format.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load gold pool report (optional)
    # ------------------------------------------------------------------
    gold_absent_ids: set[str] | None = None
    n_gold_absent_in_report = 0
    case_selection_source = "all_wrong_consensus_cases"

    if args.gold_pool_report is not None:
        if not args.gold_pool_report.exists():
            print(
                f"ERROR: gold pool report not found: {args.gold_pool_report}",
                file=sys.stderr,
            )
            sys.exit(1)
        gold_absent_ids, _ = parse_gold_pool_report(args.gold_pool_report)
        n_gold_absent_in_report = len(gold_absent_ids)
        case_selection_source = "gold_pool_report"

    # ------------------------------------------------------------------
    # Select cases (deterministic)
    # ------------------------------------------------------------------
    selected = _select_cases(cases, gold_absent_ids, args.limit)
    n_selected = len(selected)

    # ------------------------------------------------------------------
    # Render prompts and audit
    # ------------------------------------------------------------------
    provider_requests: list[dict[str, Any]] = []
    selected_cases_out: list[dict[str, Any]] = []
    audit_results: list[dict[str, Any]] = []
    all_gold_free = True

    for idx, case in enumerate(selected, start=1):
        case_id = case.get("case_id", f"case_{idx:04d}")
        question = case.get("question", "")
        pool_values = _extract_candidate_pool(case)
        pool_summary = _build_candidate_pool_summary(pool_values)
        baseline_answer = str(
            case.get("selector_metadata", {}).get("selected_answer", "")
            or case.get("frontier_candidate_answer", "")
        ).strip()

        prompt_text = render_prompt(template, question, pool_summary)
        audit = audit_prompt(prompt_text, case_id)
        audit_results.append(audit)
        if not audit["gold_free"]:
            all_gold_free = False

        is_gold_absent: bool | None = (
            (gold_absent_ids is not None and case_id in gold_absent_ids)
            if gold_absent_ids is not None
            else None
        )

        selected_cases_out.append({
            "case_id": case_id,
            "question": question,
            "candidate_pool": pool_values,
            "candidate_pool_size": len(pool_values),
            "baseline_answer": baseline_answer,
            "gold_absent": is_gold_absent,
            "prompt_sha256": audit["prompt_sha256"],
        })

        provider_requests.append({
            "request_id": f"{EXPERIMENT_ID}:{case_id}:{idx:05d}",
            "case_id": case_id,
            "question": question,
            "prompt_text": prompt_text,
            "candidate_pool": pool_values,
            "candidate_pool_size": len(pool_values),
            "baseline_answer": baseline_answer,
            "gold_absent": is_gold_absent,
            "dry_run": True,
            "api_call_made": False,
            "prompt_sha256": audit["prompt_sha256"],
            "max_output_tokens": 2048,
            "required_output_fields": _REQUIRED_OUTPUT_FIELDS,
        })

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    _write_jsonl(args.out_dir / "selected_cases.jsonl", selected_cases_out)
    _write_jsonl(args.out_dir / "provider_requests_dry_run.jsonl", provider_requests)

    prompt_audit_out: dict[str, Any] = {
        "all_gold_free": all_gold_free,
        "case_count": n_selected,
        "violations": [r for r in audit_results if not r["gold_free"]],
        "per_case": audit_results,
    }
    _write_json(args.out_dir / "prompt_audit.json", prompt_audit_out)

    report_lines = [
        "# BFTC Live Pilot v1 — Dry-Run Preflight Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        "",
        "## Summary",
        f"- Cases loaded from trace packets: {len(cases)}",
        f"- Case selection source: {case_selection_source}",
        f"- Gold-absent IDs in report: {n_gold_absent_in_report}",
        f"- Cases selected for pilot: {n_selected}",
        f"- All prompts gold-free: {all_gold_free}",
        "- API calls made: 0 (dry-run only)",
        "",
        "## Provider Request Schema",
        "Each request includes: case_id, question, candidate_pool (gold-free numeric values),",
        "baseline_answer, gold_absent, prompt_text, prompt_sha256, max_output_tokens=2048.",
        "",
        "## Post-Hoc Evaluation Fields",
        "After live run, evaluate: parse_ok, final_answer, is_new_candidate,",
        "gold_recovered (post-hoc lookup only, never in prompt), matches_baseline,",
        "candidate_pool_review (BFTC verdict on existing candidates), error_category.",
        "",
        "## Gold Safety",
        "- Gold answers are NOT in any prompt or request field.",
        "- gold_absent flag is from the gold pool report pre-computed label, not model output.",
        "- Gold comparison is post-hoc only, keyed by case_id after live run.",
        "",
        "## Stop/Go Criteria",
        "- 0–2/20 recovered: do not scale; revisit prompt or case selection.",
        "- 3/20: borderline; inspect failures qualitatively.",
        "- 4–6+/20: justified for 50–100-case follow-up.",
        "- 8+/20: strong signal; plan full 70-case pilot.",
    ]
    (args.out_dir / "dry_run_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )

    manifest: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "cases_loaded": len(cases),
        "case_selection_source": case_selection_source,
        "gold_absent_ids_from_report": n_gold_absent_in_report,
        "cases_selected": n_selected,
        "all_prompts_gold_free": all_gold_free,
        "gold_leakage_allowed": False,
        "api_calls_made": 0,
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json",
            "selected_cases.jsonl",
            "provider_requests_dry_run.jsonl",
            "prompt_audit.json",
            "dry_run_report.md",
        ],
    }
    _write_json(args.out_dir / "manifest.json", manifest)

    print(
        f"BFTC preflight complete. {n_selected} cases selected. Output: {args.out_dir}",
        flush=True,
    )
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="No-API dry-run preflight for backward_from_target_check_live_pilot_v1."
    )
    p.add_argument(
        "--trace-packets",
        required=True,
        type=Path,
        help="Path to wrong-consensus-97 trace packet JSONL.",
    )
    p.add_argument(
        "--gold-pool-report",
        type=Path,
        default=None,
        help="Optional markdown gold pool report for gold-absent case IDs.",
    )
    p.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Directory for preflight outputs.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum cases to select (default 20).",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    main()
