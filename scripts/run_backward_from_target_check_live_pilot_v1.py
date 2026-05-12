#!/usr/bin/env python3
"""
run_backward_from_target_check_live_pilot_v1.py

Live runner for backward_from_target_check_live_pilot_v1.

Consumes provider requests from prepare_backward_from_target_check_live_pilot_v1_preflight.py,
makes Cohere API calls (with --allow-api), parses BFTC responses, and records
post-hoc scoring against gold labels (if a casebook is supplied).

Gold is used ONLY for post-hoc scoring. It is never placed in prompts or
provider request fields. The provider request prompt_text is used as-is.

Usage (dry-run, no API):
    python scripts/run_backward_from_target_check_live_pilot_v1.py \\
        --provider-requests /tmp/bftc_preflight/provider_requests_dry_run.jsonl \\
        --selected-cases   /tmp/bftc_preflight/selected_cases.jsonl \\
        --trace-packets    /tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl \\
        --out-dir          /tmp/bftc_dry_run

Usage (live, requires --allow-api):
    ... same plus --allow-api
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "backward_from_target_check_live_pilot_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# Fields expected in a valid BFTC response.
# Each entry lists the canonical name followed by acceptable synonyms.
_FIELD_SYNONYMS: dict[str, list[str]] = {
    "target_identified": [
        "target_identified", "requested_target", "target_quantity", "target",
    ],
    "backward_check_steps": [
        "backward_check_steps", "reverse_derivation", "check_steps",
        "reasoning_steps", "steps",
    ],
    "candidate_pool_review": [
        "candidate_pool_review", "candidates_review", "pool_review", "review",
    ],
    "final_answer": [
        "final_answer", "repaired_candidate", "answer",
    ],
}

_REQUIRED_CANONICAL = list(_FIELD_SYNONYMS.keys())

_FORBIDDEN_ANSWER_CHARS = re.compile(r"[$%,]|[a-zA-Z]")

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


def _parse_numeric(v: Any) -> float | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _normalize_answer(v: Any) -> str:
    n = _parse_numeric(v)
    if n is None:
        return str(v).strip()
    if n == int(n) and abs(n) < 1e12:
        return str(int(n))
    return str(round(n, 6))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("(empty)\n", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# JSON extraction from raw model output
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> tuple[dict | None, str]:
    if not text:
        return None, "empty_response"
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj, "direct"
    except json.JSONDecodeError:
        pass
    fence = re.sub(r"```(?:json)?\s*", "", stripped)
    fence = re.sub(r"```\s*$", "", fence).strip()
    try:
        obj = json.loads(fence)
        if isinstance(obj, dict):
            return obj, "fence_stripped"
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj, "extracted"
        except json.JSONDecodeError:
            pass
    return None, "parse_failed"


# ---------------------------------------------------------------------------
# BFTC response parser
# ---------------------------------------------------------------------------

def _resolve_field(obj: dict, canonical: str) -> tuple[Any, str | None]:
    """Try canonical name then synonyms. Returns (value, resolved_key) or (None, None)."""
    for key in _FIELD_SYNONYMS.get(canonical, [canonical]):
        if key in obj:
            return obj[key], key
    return None, None


def parse_bftc_response(obj: dict) -> dict[str, Any]:
    """Parse and validate a BFTC JSON response object.

    Returns a result dict with schema_ok, issues, extracted fields, and
    derived metrics. Minor field-name synonyms are accepted but recorded.
    """
    issues: list[str] = []
    resolved: dict[str, Any] = {}

    for canonical in _REQUIRED_CANONICAL:
        val, key = _resolve_field(obj, canonical)
        if val is None:
            issues.append(f"missing_field:{canonical}")
        else:
            resolved[canonical] = val
            if key != canonical:
                issues.append(f"synonym_used:{canonical}={key!r}")

    # final_answer: must be numeric
    fa = resolved.get("final_answer")
    fa_numeric = _parse_numeric(fa)
    if fa is not None and fa_numeric is None:
        issues.append(f"non_numeric_final_answer:{fa!r}")
    elif fa is None and "missing_field:final_answer" not in issues:
        pass  # already flagged

    # backward_check_steps: must be a list
    steps = resolved.get("backward_check_steps")
    steps_count = 0
    all_consistent = True
    if steps is not None:
        if isinstance(steps, list):
            steps_count = len(steps)
            for step in steps:
                if isinstance(step, dict) and step.get("consistent_with_target") is False:
                    all_consistent = False
        else:
            issues.append("backward_check_steps_not_list")

    # candidate_pool_review: check whether model said "none" (no prior candidate matches)
    review = str(resolved.get("candidate_pool_review", "")).lower()
    review_says_none = "none" in review

    # target_unit (optional)
    target_unit = str(obj.get("target_unit", "")).strip()

    schema_hard_failures = [
        i for i in issues
        if i.startswith("missing_field:") or i.startswith("non_numeric_final_answer")
    ]

    return {
        "schema_ok": len(schema_hard_failures) == 0,
        "issues": issues,
        "target_identified": str(resolved.get("target_identified", ""))[:300],
        "target_unit": target_unit[:100],
        "steps_count": steps_count,
        "all_steps_consistent": all_consistent,
        "review_says_none": review_says_none,
        "candidate_pool_review": str(resolved.get("candidate_pool_review", ""))[:300],
        "fa_numeric": fa_numeric,
        "fa_bare": fa_numeric is not None,
    }


def _audit_prompt_for_gold(text: str) -> bool:
    """Return True if the text contains a forbidden gold-leakage pattern."""
    return any(p.search(text) for p in _FORBIDDEN_PROMPT_RE)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_provider_requests(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_selected_cases(path: Path) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                cid = row.get("case_id", "")
                if cid:
                    cases[cid] = row
    return cases


def _load_trace_cases(path: Path) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            for case in obj.get("cases", [obj]):
                cid = case.get("case_id", "")
                if cid:
                    cases[cid] = case
    return cases


def _load_gold_labels(path: Path) -> dict[str, str]:
    """Load gold answers from a CSV casebook (post-hoc use only).

    Accepts columns named gold_answer, gold, correct_answer, or structural_best_answer.
    Returns case_id → normalized gold string.
    """
    gold: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if not cid:
                continue
            val = (
                row.get("gold_answer")
                or row.get("gold")
                or row.get("correct_answer")
                or row.get("structural_best_answer")
                or ""
            )
            gold[cid] = _normalize_answer(val)
    return gold


# ---------------------------------------------------------------------------
# Cohere API call
# ---------------------------------------------------------------------------

def _call_cohere(
    client: Any,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    text = ""
    if hasattr(response, "message") and response.message:
        content = response.message.content
        if content and hasattr(content[0], "text"):
            text = content[0].text or ""
    usage: dict[str, Any] = {}
    if hasattr(response, "usage") and response.usage:
        try:
            usage = json.loads(json.dumps(response.usage, default=str))
        except Exception:
            usage = {"raw": str(response.usage)}
    return text, usage


# ---------------------------------------------------------------------------
# Per-case processing
# ---------------------------------------------------------------------------

def _process_case(
    *,
    req: dict[str, Any],
    sc_row: dict[str, Any],
    gold_labels: dict[str, str],
    client: Any | None,
    model: str,
    max_tokens: int,
    temperature: float,
    call_index: int,
    dry_run: bool,
) -> tuple[dict[str, Any], int]:
    """Process one case. Returns (result, api_calls_made)."""
    case_id = req.get("case_id", "")
    prompt = req.get("prompt_text", "")
    candidate_pool = req.get("candidate_pool", [])
    baseline_answer = str(req.get("baseline_answer", "")).strip()
    gold_absent = req.get("gold_absent")

    result: dict[str, Any] = {
        "call_index": call_index,
        "case_id": case_id,
        "baseline_answer": baseline_answer,
        "candidate_pool": candidate_pool,
        "gold_absent": gold_absent,
        "prompt_sha256": _sha256(prompt),
        "gold_in_prompt": _audit_prompt_for_gold(prompt),
    }

    if dry_run:
        result.update({
            "call_ok": None,
            "api_call_made": False,
            "raw_response": None,
            "parse_ok": None,
            "schema_ok": None,
            "issues": ["dry_run"],
            "fa_numeric": None,
            "fa_bare": None,
            "is_new_candidate": None,
            "matches_baseline": None,
            "gold_recovered": None,
        })
        return result, 0

    # --- Live call ---
    result["api_call_made"] = True
    try:
        raw_text, usage = _call_cohere(client, model, prompt, max_tokens, temperature)
        result["raw_response"] = raw_text
        result["usage"] = usage
        result["call_ok"] = True
        result["call_error"] = None
    except Exception as exc:
        result.update({
            "raw_response": "",
            "usage": {},
            "call_ok": False,
            "call_error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "parse_ok": False,
            "schema_ok": False,
            "issues": ["call_failed"],
            "fa_numeric": None,
            "fa_bare": False,
            "is_new_candidate": False,
            "matches_baseline": False,
            "gold_recovered": None,
        })
        return result, 1

    # --- Parse ---
    obj, parse_method = _extract_json(raw_text)
    result["parse_ok"] = obj is not None
    result["parse_method"] = parse_method

    if obj is None:
        result.update({
            "schema_ok": False,
            "issues": [f"json_parse_failed:{parse_method}"],
            "fa_numeric": None,
            "fa_bare": False,
            "is_new_candidate": False,
            "matches_baseline": False,
            "gold_recovered": None,
        })
        return result, 1

    # --- Validate ---
    val = parse_bftc_response(obj)
    result.update({
        "schema_ok": val["schema_ok"],
        "issues": val["issues"],
        "target_identified": val["target_identified"],
        "target_unit": val["target_unit"],
        "steps_count": val["steps_count"],
        "all_steps_consistent": val["all_steps_consistent"],
        "review_says_none": val["review_says_none"],
        "candidate_pool_review": val["candidate_pool_review"],
        "fa_numeric": val["fa_numeric"],
        "fa_bare": val["fa_bare"],
    })

    fa_str = _normalize_answer(val["fa_numeric"]) if val["fa_numeric"] is not None else ""
    baseline_norm = _normalize_answer(baseline_answer)
    pool_norms = {_normalize_answer(a) for a in candidate_pool}

    result["is_new_candidate"] = (
        fa_str not in pool_norms and fa_str not in ("", "NA")
    )
    result["matches_baseline"] = fa_str == baseline_norm

    # Post-hoc gold scoring (gold never touched prompt)
    gold_norm = gold_labels.get(case_id, "")
    if gold_norm:
        result["gold_recovered"] = fa_str == gold_norm and fa_str not in ("", "NA")
    else:
        result["gold_recovered"] = None

    return result, 1


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _generate_report(
    results: list[dict[str, Any]],
    n_loaded: int,
    args: argparse.Namespace,
    dry_run: bool,
) -> str:
    n = len(results)
    mode = "DRY RUN" if dry_run else "LIVE"

    calls_ok = sum(1 for r in results if r.get("call_ok") is True)
    parse_ok = sum(1 for r in results if r.get("parse_ok") is True)
    schema_ok = sum(1 for r in results if r.get("schema_ok") is True)
    fa_extracted = sum(1 for r in results if r.get("fa_numeric") is not None)
    new_candidates = sum(1 for r in results if r.get("is_new_candidate") is True)
    gold_recovered = sum(1 for r in results if r.get("gold_recovered") is True)
    gold_scored = sum(1 for r in results if r.get("gold_recovered") is not None)

    issue_counts: Counter = Counter()
    for r in results:
        for issue in r.get("issues", []):
            key = issue.split(":")[0]
            issue_counts[key] += 1

    lines = [
        f"# BFTC Live Pilot v1 — {mode} Report",
        f"**Timestamp:** {_TS}",
        f"**Experiment:** {EXPERIMENT_ID}",
        f"**Mode:** {mode}",
        f"**Model:** {args.model}" if hasattr(args, "model") else "",
        "",
        "## Call Results",
        f"- Cases in provider requests: {n_loaded}",
        f"- Cases attempted: {n}",
        f"- Calls succeeded: {calls_ok}/{n}" if not dry_run else "- API calls made: 0 (dry run)",
        f"- JSON parse ok: {parse_ok}/{n}",
        f"- Schema ok: {schema_ok}/{n}",
        f"- final_answer extracted: {fa_extracted}/{n}",
        "",
        "## Answer Quality (post-hoc, gold-free comparison)",
        f"- New candidates (not in prior pool): {new_candidates}/{n}",
        "",
        "## Gold Recovery (post-hoc only)",
        f"- Cases with gold labels available: {gold_scored}/{n}",
        f"- Gold recovered into pool: {gold_recovered}/{gold_scored}" if gold_scored else "- Gold recovery: N/A (no casebook provided)",
        "",
        "## Issue Summary",
        "",
    ]
    for issue, cnt in issue_counts.most_common():
        if not issue.startswith("synonym_used"):
            lines.append(f"- {issue}: {cnt}")

    synonyms = {k: v for k, v in issue_counts.items() if k.startswith("synonym_used")}
    if synonyms:
        lines += ["", "## Synonym Usage (informational, not errors)"]
        for k, cnt in synonyms.items():
            lines.append(f"- {k}: {cnt}")

    lines += [
        "",
        "## Safe Claims",
        "- Gold was not included in any prompt or provider request field.",
        "- Gold comparison (if any) was post-hoc only.",
        "- Schema compliance does not equal accuracy on the underlying math task.",
        "",
        "## Unsafe Claims",
        "- Do not claim BFTC improves exact-match accuracy without a held-out evaluation.",
        "- Do not generalize pilot results without a larger follow-up.",
    ]
    return "\n".join(l for l in lines if l is not None) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dry_run = not args.allow_api

    # ------------------------------------------------------------------
    # Load provider requests
    # ------------------------------------------------------------------
    if not args.provider_requests.exists():
        print(f"ERROR: provider requests not found: {args.provider_requests}", file=sys.stderr)
        sys.exit(1)
    all_reqs = _load_provider_requests(args.provider_requests)
    n_loaded = len(all_reqs)

    # Sort by a stable key, then apply limit
    all_reqs.sort(key=lambda r: r.get("case_id", ""))
    reqs = all_reqs[: args.limit]

    # ------------------------------------------------------------------
    # Load selected-cases metadata
    # ------------------------------------------------------------------
    selected_cases: dict[str, dict[str, Any]] = {}
    if args.selected_cases and args.selected_cases.exists():
        selected_cases = _load_selected_cases(args.selected_cases)

    # ------------------------------------------------------------------
    # Load gold labels (post-hoc only — never placed in prompts)
    # ------------------------------------------------------------------
    gold_labels: dict[str, str] = {}
    if args.casebook and args.casebook.exists():
        gold_labels = _load_gold_labels(args.casebook)

    # ------------------------------------------------------------------
    # Validate no gold in prompts
    # ------------------------------------------------------------------
    gold_in_any_prompt = any(_audit_prompt_for_gold(r.get("prompt_text", "")) for r in reqs)

    # ------------------------------------------------------------------
    # Dry-run path (no API)
    # ------------------------------------------------------------------
    if dry_run:
        results = [
            _process_case(
                req=req,
                sc_row=selected_cases.get(req.get("case_id", ""), {}),
                gold_labels={},  # no gold in dry run processing
                client=None,
                model=args.model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                call_index=idx,
                dry_run=True,
            )[0]
            for idx, req in enumerate(reqs, start=1)
        ]
        total_api_calls = 0

        _write_jsonl(args.out_dir / "raw_responses.jsonl", [])
        _write_jsonl(args.out_dir / "parsed_responses.jsonl", [])
        _write_jsonl(args.out_dir / "candidate_rows.jsonl", [])

        report = _generate_report(results, n_loaded, args, dry_run=True)
        (args.out_dir / "dry_run_report.md").write_text(report, encoding="utf-8")

    else:
        # ------------------------------------------------------------------
        # Live path
        # ------------------------------------------------------------------
        api_key = os.environ.get("COHERE_API_KEY", "")
        if not api_key:
            print("ERROR: COHERE_API_KEY not set.", file=sys.stderr)
            sys.exit(1)
        try:
            import cohere  # type: ignore[import]
        except ImportError:
            print("ERROR: cohere SDK not installed.", file=sys.stderr)
            sys.exit(1)
        client = cohere.ClientV2(api_key=api_key)

        results: list[dict[str, Any]] = []
        total_api_calls = 0
        consecutive_auth_errors = 0

        for idx, req in enumerate(reqs, start=1):
            case_id = req.get("case_id", "")
            sc_row = selected_cases.get(case_id, {})
            print(f"  [{idx}/{len(reqs)}] {case_id} ...", end=" ", flush=True)

            result, n_calls = _process_case(
                req=req,
                sc_row=sc_row,
                gold_labels=gold_labels,
                client=client,
                model=args.model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                call_index=idx,
                dry_run=False,
            )
            results.append(result)
            total_api_calls += n_calls

            if result.get("call_ok"):
                consecutive_auth_errors = 0
                fa = result.get("fa_numeric")
                new = result.get("is_new_candidate")
                print(f"ok | fa={fa} new={new}", flush=True)
            else:
                err = result.get("call_error", "")
                print(f"FAIL: {err[:80]}", flush=True)
                if "401" in err or "AuthenticationError" in err or "Unauthorized" in err:
                    consecutive_auth_errors += 1
                    if consecutive_auth_errors >= 2:
                        print("ERROR: consecutive auth failures — stopping.", file=sys.stderr)
                        break

            if idx < len(reqs):
                time.sleep(0.5)

        # Write outputs
        raw_rows = [
            {
                "case_id": r["case_id"],
                "call_index": r["call_index"],
                "call_ok": r.get("call_ok"),
                "raw_response": r.get("raw_response", ""),
                "prompt_sha256": r.get("prompt_sha256", ""),
            }
            for r in results
        ]
        parsed_rows = [
            {
                "case_id": r["case_id"],
                "call_index": r["call_index"],
                "parse_ok": r.get("parse_ok"),
                "schema_ok": r.get("schema_ok"),
                "issues": r.get("issues", []),
                "target_identified": r.get("target_identified", ""),
                "target_unit": r.get("target_unit", ""),
                "steps_count": r.get("steps_count"),
                "all_steps_consistent": r.get("all_steps_consistent"),
                "review_says_none": r.get("review_says_none"),
                "fa_numeric": r.get("fa_numeric"),
                "fa_bare": r.get("fa_bare"),
            }
            for r in results if r.get("parse_ok")
        ]
        candidate_rows = [
            {
                "case_id": r["case_id"],
                "fa_numeric": r.get("fa_numeric"),
                "is_new_candidate": r.get("is_new_candidate"),
                "matches_baseline": r.get("matches_baseline"),
                "gold_recovered": r.get("gold_recovered"),
                "candidate_pool": r.get("candidate_pool", []),
                "baseline_answer": r.get("baseline_answer", ""),
            }
            for r in results
        ]
        _write_jsonl(args.out_dir / "raw_responses.jsonl", raw_rows)
        _write_jsonl(args.out_dir / "parsed_responses.jsonl", parsed_rows)
        _write_jsonl(args.out_dir / "candidate_rows.jsonl", candidate_rows)

        report = _generate_report(results, n_loaded, args, dry_run=False)
        (args.out_dir / "live_report.md").write_text(report, encoding="utf-8")

    # ------------------------------------------------------------------
    # pilot_summary.json
    # ------------------------------------------------------------------
    n = len(results)
    issue_counts_all: Counter = Counter()
    for r in results:
        for issue in r.get("issues", []):
            issue_counts_all[issue.split(":")[0]] += 1

    summary: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "mode": "dry_run" if dry_run else "live",
        "model": args.model,
        "provider": "cohere",
        "cases_in_requests": n_loaded,
        "cases_attempted": n,
        "api_calls_made": total_api_calls,
        "calls_ok": sum(1 for r in results if r.get("call_ok") is True),
        "parse_ok_count": sum(1 for r in results if r.get("parse_ok") is True),
        "schema_ok_count": sum(1 for r in results if r.get("schema_ok") is True),
        "final_answer_extracted_count": sum(1 for r in results if r.get("fa_numeric") is not None),
        "new_candidate_count": sum(1 for r in results if r.get("is_new_candidate") is True),
        "gold_recovered_into_pool_count": sum(1 for r in results if r.get("gold_recovered") is True),
        "gold_labels_available": len(gold_labels),
        "gold_in_any_prompt": gold_in_any_prompt,
        "missing_final_answer": issue_counts_all.get("missing_field", 0),
        "invalid_json": issue_counts_all.get("json_parse_failed", 0),
        "schema_missing_fields": issue_counts_all.get("missing_field", 0),
        "non_numeric_final_answer": issue_counts_all.get("non_numeric_final_answer", 0),
        "call_failed": issue_counts_all.get("call_failed", 0),
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json",
            "raw_responses.jsonl",
            "parsed_responses.jsonl",
            "candidate_rows.jsonl",
            "pilot_summary.json",
            "dry_run_report.md" if dry_run else "live_report.md",
        ],
    }
    _write_json(args.out_dir / "pilot_summary.json", summary)
    _write_json(args.out_dir / "manifest.json", summary)

    print(
        f"\nBFTC pilot {'dry-run' if dry_run else 'live'} complete."
        f" {n} cases. Output: {args.out_dir}",
        flush=True,
    )
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BFTC live pilot v1 runner (--allow-api required for live calls)."
    )
    p.add_argument("--provider-requests", required=True, type=Path,
                   help="provider_requests_dry_run.jsonl from preflight.")
    p.add_argument("--selected-cases", type=Path, default=None,
                   help="selected_cases.jsonl from preflight (optional metadata).")
    p.add_argument("--trace-packets", type=Path, default=None,
                   help="Trace packets JSONL (used for question lookup if needed).")
    p.add_argument("--casebook", type=Path, default=None,
                   help="CSV with case_id + gold_answer columns (post-hoc scoring only).")
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--allow-api", action="store_true",
                   help="Required to enable live API calls.")
    return p.parse_args(argv)


if __name__ == "__main__":
    main()
