#!/usr/bin/env python3
"""
prepare_bftc_executable_repair_v1_preflight.py

No-API preflight for bftc_executable_repair_v1.

Renders provider requests using prompts/backward_from_target_check_executable_repair_v1.md.
Optionally includes prior BFTC response as context. Never includes gold in prompts.
Audits all prompts for gold-leakage patterns.

Inputs:
  --selected-cases    selected_cases.jsonl from BFTC v1 preflight  (required)
  --prior-bftc-output parsed_responses.jsonl from BFTC v1 live run (optional)
  --out-dir           output directory                              (required)
  --limit             max cases (default 20)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "bftc_executable_repair_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

PROMPT_TEMPLATE_PATH = (
    REPO_ROOT / "prompts" / "backward_from_target_check_executable_repair_v1.md"
)

_REQUIRED_OUTPUT_FIELDS = [
    "requested_target",
    "source_facts",
    "reverse_derivation",
    "failed_relation",
    "repair_operation",
    "formula_variables",
    "solution_formula",
    "final_answer",
    "confidence",
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

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _default_out_dir() -> Path:
    return Path(tempfile.gettempdir()) / f"{EXPERIMENT_ID}_preflight_{_TS}"


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _load_prompt_template() -> str:
    if not PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {PROMPT_TEMPLATE_PATH}\n"
            "Expected: prompts/backward_from_target_check_executable_repair_v1.md"
        )
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _build_candidate_pool_summary(values: list[str]) -> str:
    if not values:
        return "(no prior candidates recorded)"
    return (
        ", ".join(values)
        + " (model-generated from prior branches; none are confirmed correct)"
    )


def _build_prior_bftc_context(prior: dict[str, Any] | None) -> str:
    """Render prior BFTC response as context block (gold-free)."""
    if not prior:
        return ""
    lines = [
        "",
        "PRIOR BFTC RESPONSE (for context — do not assume final_answer is correct):",
        f"  requested_target: {prior.get('target_identified', '')[:200]}",
        f"  steps_count: {prior.get('steps_count', '')}",
        f"  review: {prior.get('candidate_pool_review', '')[:200]}",
        f"  prior_final_answer: {prior.get('fa_numeric', '')}",
        "",
    ]
    return "\n".join(lines)


def render_prompt(
    template: str,
    question: str,
    candidate_pool_summary: str,
    prior_bftc_context: str,
) -> str:
    rendered = template.replace("{{question}}", question)
    rendered = rendered.replace("{{candidate_pool_summary}}", candidate_pool_summary)
    rendered = rendered.replace("{{prior_bftc_context}}", prior_bftc_context)
    unresolved = re.findall(r"\{\{[^}]+\}\}", rendered)
    if unresolved:
        raise ValueError(f"Unresolved placeholders: {unresolved}")
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
# Data loaders
# ---------------------------------------------------------------------------

def _load_selected_cases(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_prior_bftc(path: Path) -> dict[str, dict[str, Any]]:
    """Load parsed_responses.jsonl from BFTC v1 run, keyed by case_id."""
    idx: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                cid = row.get("case_id", "")
                if cid:
                    idx[cid] = row
    return idx


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    if args.out_dir is None:
        args.out_dir = _default_out_dir()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Load prompt template
    try:
        template = _load_prompt_template()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Load selected cases
    if not args.selected_cases.exists():
        print(
            f"ERROR: selected cases file not found: {args.selected_cases}",
            file=sys.stderr,
        )
        sys.exit(1)
    cases = _load_selected_cases(args.selected_cases)
    if not cases:
        print(f"ERROR: no cases loaded from {args.selected_cases}", file=sys.stderr)
        sys.exit(1)

    # Sort deterministically then limit
    cases.sort(key=lambda c: c.get("case_id", ""))
    cases = cases[: args.limit]

    # Load prior BFTC responses (optional)
    prior_bftc: dict[str, dict[str, Any]] = {}
    has_prior_bftc = False
    if args.prior_bftc_output is not None:
        if not args.prior_bftc_output.exists():
            print(
                f"ERROR: prior BFTC output not found: {args.prior_bftc_output}",
                file=sys.stderr,
            )
            sys.exit(1)
        prior_bftc = _load_prior_bftc(args.prior_bftc_output)
        has_prior_bftc = bool(prior_bftc)

    # Render prompts
    provider_requests: list[dict[str, Any]] = []
    selected_cases_out: list[dict[str, Any]] = []
    audit_results: list[dict[str, Any]] = []
    all_gold_free = True

    for idx, case in enumerate(cases, start=1):
        case_id = case.get("case_id", f"case_{idx:04d}")
        question = case.get("question", "")
        candidate_pool = case.get("candidate_pool", [])
        baseline_answer = str(case.get("baseline_answer", "")).strip()
        gold_absent = case.get("gold_absent")

        pool_summary = _build_candidate_pool_summary(
            [str(v) for v in candidate_pool if str(v).strip()]
        )
        prior = prior_bftc.get(case_id)
        prior_ctx = _build_prior_bftc_context(prior)

        prompt_text = render_prompt(template, question, pool_summary, prior_ctx)
        audit = audit_prompt(prompt_text, case_id)
        audit_results.append(audit)
        if not audit["gold_free"]:
            all_gold_free = False

        selected_cases_out.append({
            "case_id": case_id,
            "question": question,
            "candidate_pool": candidate_pool,
            "candidate_pool_size": len(candidate_pool),
            "baseline_answer": baseline_answer,
            "gold_absent": gold_absent,
            "has_prior_bftc_context": prior is not None,
            "prompt_sha256": audit["prompt_sha256"],
        })

        provider_requests.append({
            "request_id": f"{EXPERIMENT_ID}:{case_id}:{idx:05d}",
            "case_id": case_id,
            "question": question,
            "prompt_text": prompt_text,
            "candidate_pool": candidate_pool,
            "candidate_pool_size": len(candidate_pool),
            "baseline_answer": baseline_answer,
            "gold_absent": gold_absent,
            "has_prior_bftc_context": prior is not None,
            "dry_run": True,
            "api_call_made": False,
            "prompt_sha256": audit["prompt_sha256"],
            "max_output_tokens": 2048,
            "required_output_fields": _REQUIRED_OUTPUT_FIELDS,
        })

    # Write outputs
    _write_jsonl(args.out_dir / "selected_cases.jsonl", selected_cases_out)
    _write_jsonl(args.out_dir / "provider_requests_dry_run.jsonl", provider_requests)

    prompt_audit: dict[str, Any] = {
        "all_gold_free": all_gold_free,
        "case_count": len(cases),
        "violations": [r for r in audit_results if not r["gold_free"]],
        "per_case": audit_results,
    }
    _write_json(args.out_dir / "prompt_audit.json", prompt_audit)

    report_lines = [
        "# BFTC Executable Repair v1 — Dry-Run Preflight Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        "",
        "## Summary",
        f"- Cases loaded: {len(cases)}",
        f"- Has prior BFTC context: {has_prior_bftc}",
        f"- All prompts gold-free: {all_gold_free}",
        "- API calls made: 0 (dry-run only)",
        "",
        "## New Fields vs BFTC v1",
        "Each request now requires: requested_target, source_facts, formula_variables,",
        "solution_formula (safe Python expression), repair_operation, failed_relation, confidence.",
        "",
        "## Executable Repair Contract",
        "- solution_formula is evaluated locally using ast-based safe evaluator.",
        "- formula_variables binds all names; unknown names cause eval_rejected.",
        "- executable_final_answer replaces model final_answer when eval_ok=True.",
        "- Gold is post-hoc only.",
        "",
        "## Stop/Go Criteria (for live run)",
        "- 0–4/20 recovered: do not scale; revisit formula prompt or add SymPy layer.",
        "- 5–8/20: borderline; inspect qualitatively.",
        "- 9–12/20: justified for 50–100-case follow-up.",
        "- 13+/20: strong signal; plan full 70-case pilot.",
    ]
    (args.out_dir / "dry_run_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )

    manifest: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "selected_cases_input": str(args.selected_cases),
        "prior_bftc_output_input": (
            str(args.prior_bftc_output) if args.prior_bftc_output is not None else None
        ),
        "cases_selected": len(cases),
        "has_prior_bftc_context": has_prior_bftc,
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
        f"BFTC executable repair preflight complete. "
        f"{len(cases)} cases. Output: {args.out_dir}",
        flush=True,
    )
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="No-API preflight for BFTC executable repair v1."
    )
    p.add_argument(
        "--selected-cases",
        required=True,
        type=Path,
        help="selected_cases.jsonl from BFTC v1 preflight.",
    )
    p.add_argument(
        "--prior-bftc-output",
        type=Path,
        default=None,
        help="parsed_responses.jsonl from BFTC v1 live run (optional context).",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory for preflight artifacts.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of cases (default 20).",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    main()
