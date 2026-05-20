#!/usr/bin/env python3
"""
run_target_variable_dict_pal_branch_v1_live_pilot.py

Tiny Cohere-only live pilot for target_variable_dict_pal_branch_v1.

Sends the rendered target-variable-dict prompt to command-r-plus-08-2024,
parses the strict-JSON response, validates schema compliance, and scores
the generated answer against the existing candidate pool and proxy gold.

Gold is used ONLY for post-hoc scoring and reporting, never in prompts.
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

EXPERIMENT_ID = "target_variable_dict_pal_branch_v1"
_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# Generic variable names that indicate a semantic-name failure
_GENERIC_NAMES = frozenset({
    "x", "y", "z", "a", "b", "c", "n", "m", "k",
    "answer", "result", "val", "value", "num", "var", "res",
    "ans", "output", "out",
})

_REQUIRED_FIELDS = [
    "problem_summary",
    "target_question",
    "target_variable_name",
    "target_unit",
    "variables",
    "rejected_non_final_variables",
    "answer_variable_name",
    "final_answer",
]

_FORBIDDEN_ANSWER_CHARS = re.compile(r"[$%,]|[a-zA-Z]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def _parse_numeric(v: Any) -> float | None:
    if isinstance(v, (int, float)):
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


# ---------------------------------------------------------------------------
# JSON extraction from model output
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> tuple[dict | None, str]:
    """Try to extract a JSON object from model output text."""
    if not text:
        return None, "empty_response"
    # Direct parse
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj, "direct"
    except json.JSONDecodeError:
        pass
    # Strip markdown fence
    fence = re.sub(r"```(?:json)?\s*", "", stripped)
    fence = re.sub(r"```\s*$", "", fence).strip()
    try:
        obj = json.loads(fence)
        if isinstance(obj, dict):
            return obj, "fence_stripped"
    except json.JSONDecodeError:
        pass
    # Find outermost { ... }
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
# Schema validation
# ---------------------------------------------------------------------------

def validate_variable_dict(obj: dict) -> dict[str, Any]:
    """Validate a parsed variable-dict response. Returns a validation result dict."""
    issues: list[str] = []

    # Required fields
    missing = [f for f in _REQUIRED_FIELDS if f not in obj]
    if missing:
        issues.append(f"missing_fields:{','.join(missing)}")

    # Semantic variable name check
    tvn = str(obj.get("target_variable_name", "")).strip().lower()
    avn = str(obj.get("answer_variable_name", "")).strip().lower()
    tvn_semantic = tvn not in _GENERIC_NAMES and len(tvn) > 1
    avn_semantic = avn not in _GENERIC_NAMES and len(avn) > 1
    if not tvn_semantic:
        issues.append(f"non_semantic_target_variable_name:{tvn!r}")
    if not avn_semantic:
        issues.append(f"non_semantic_answer_variable_name:{avn!r}")

    # answer_variable_name == target_variable_name
    names_match = tvn == avn
    if not names_match:
        issues.append(f"answer_variable_mismatch:target={tvn!r},answer={avn!r}")

    # Variables is a list
    variables = obj.get("variables", [])
    vars_ok = isinstance(variables, list) and len(variables) > 0
    if not vars_ok:
        issues.append("variables_empty_or_not_list")

    # answer_variable_name appears in variables list
    var_names = [str(v.get("name", "")).strip().lower() for v in variables if isinstance(v, dict)]
    avn_in_vars = avn in var_names
    if vars_ok and not avn_in_vars:
        issues.append(f"answer_variable_not_in_variables:{avn!r}")

    # rejected_non_final_variables nonempty
    rejected = obj.get("rejected_non_final_variables", [])
    has_rejections = isinstance(rejected, list) and len(rejected) > 0
    if not has_rejections:
        issues.append("rejected_non_final_variables_empty")

    # final_answer is bare number
    fa = obj.get("final_answer")
    fa_numeric = _parse_numeric(fa)
    fa_bare = False
    if fa_numeric is not None:
        fa_str = str(fa).strip() if not isinstance(fa, (int, float)) else str(fa)
        fa_bare = not _FORBIDDEN_ANSWER_CHARS.search(fa_str) and fa_numeric is not None
    if not fa_bare:
        issues.append(f"final_answer_not_bare_number:{fa!r}")

    return {
        "schema_ok": len(issues) == 0,
        "issues": issues,
        "tvn": tvn,
        "avn": avn,
        "names_match": names_match,
        "tvn_semantic": tvn_semantic,
        "avn_in_vars": avn_in_vars,
        "has_rejections": has_rejections,
        "fa_bare": fa_bare,
        "fa_numeric": fa_numeric,
        "var_count": len(variables),
        "var_names": var_names,
    }


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_provider_requests(path: Path) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_selected_cases(path: Path) -> dict[str, dict[str, Any]]:
    cases = {}
    with open(path, encoding="utf-8") as f:
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
    with open(path, encoding="utf-8") as f:
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


def _load_casebook(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                rows[cid] = dict(row)
    return rows


# ---------------------------------------------------------------------------
# Cohere call
# ---------------------------------------------------------------------------

def _call_cohere(
    client: Any,
    model: str,
    prompt: str,
    max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    """Make one Cohere chat call. Returns (text, usage_dict)."""
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
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
    trace_case: dict[str, Any],
    cb_row: dict[str, str],
    client: Any,
    model: str,
    max_tokens: int,
    call_index: int,
) -> dict[str, Any]:
    case_id = req.get("case_id", "")
    prompt = req.get("prompt_text", "")

    result: dict[str, Any] = {
        "call_index": call_index,
        "case_id": case_id,
        "question": trace_case.get("question", ""),
        "baseline_answer": str(trace_case.get("selector_metadata", {}).get("selected_answer", "")),
        "candidate_answers": trace_case.get("candidate_answers", []),
        "proxy_structural_best": cb_row.get("structural_best_answer", ""),
        "api_call_made": True,
        "call_timestamp": _utc_stamp(),
        "model": model,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    }

    # --- Live Cohere call ---
    try:
        raw_text, usage = _call_cohere(client, model, prompt, max_tokens)
        result["raw_response"] = raw_text
        result["usage"] = usage
        result["call_ok"] = True
        result["call_error"] = None
    except Exception as exc:
        result["raw_response"] = ""
        result["usage"] = {}
        result["call_ok"] = False
        result["call_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        result.update({
            "parse_ok": False, "parse_method": "call_failed",
            "schema_ok": False, "issues": ["call_failed"],
            "final_answer_generated": None,
            "is_new_candidate": False,
            "matches_baseline": False,
            "matches_structural_best": False,
        })
        return result

    # --- JSON parse ---
    obj, parse_method = _extract_json(raw_text)
    result["parse_ok"] = obj is not None
    result["parse_method"] = parse_method

    if obj is None:
        result.update({
            "schema_ok": False, "issues": ["json_parse_failed"],
            "final_answer_generated": None,
            "is_new_candidate": False,
            "matches_baseline": False,
            "matches_structural_best": False,
        })
        return result

    # --- Validation ---
    val = validate_variable_dict(obj)
    result["schema_ok"] = val["schema_ok"]
    result["issues"] = val["issues"]
    result["target_variable_name"] = val["tvn"]
    result["answer_variable_name"] = val["avn"]
    result["names_match"] = val["names_match"]
    result["tvn_semantic"] = val["tvn_semantic"]
    result["avn_in_vars"] = val["avn_in_vars"]
    result["has_rejections"] = val["has_rejections"]
    result["fa_bare"] = val["fa_bare"]
    result["var_count"] = val["var_count"]
    result["rejected_vars"] = obj.get("rejected_non_final_variables", [])
    result["problem_summary"] = str(obj.get("problem_summary", ""))[:200]

    fa_numeric = val["fa_numeric"]
    fa_str = _normalize_answer(fa_numeric) if fa_numeric is not None else ""
    result["final_answer_generated"] = fa_numeric
    result["final_answer_normalized"] = fa_str

    # --- Comparison (post-hoc, gold-free) ---
    baseline_norm = _normalize_answer(result["baseline_answer"])
    pool_norms = {_normalize_answer(a) for a in result["candidate_answers"]}
    proxy_best_norm = _normalize_answer(result["proxy_structural_best"])

    result["matches_baseline"] = fa_str == baseline_norm
    result["is_new_candidate"] = fa_str not in pool_norms and fa_str != "" and fa_str != "NA"
    result["matches_structural_best"] = fa_str == proxy_best_norm and proxy_best_norm not in ("", "NA")

    # Check if any variable value matches structural best (gold-in-variables probe)
    var_values = []
    for v in obj.get("variables", []):
        if isinstance(v, dict):
            vval = _normalize_answer(v.get("value", ""))
            var_values.append(vval)
    result["var_values"] = var_values
    result["structural_best_in_variables"] = (
        proxy_best_norm in var_values and proxy_best_norm not in ("", "NA")
    )

    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _generate_report(results: list[dict[str, Any]], args: argparse.Namespace) -> str:
    n = len(results)
    calls_ok = sum(1 for r in results if r.get("call_ok"))
    parse_ok = sum(1 for r in results if r.get("parse_ok"))
    schema_ok = sum(1 for r in results if r.get("schema_ok"))
    names_match = sum(1 for r in results if r.get("names_match"))
    fa_bare = sum(1 for r in results if r.get("fa_bare"))
    new_candidates = sum(1 for r in results if r.get("is_new_candidate"))
    matches_baseline = sum(1 for r in results if r.get("matches_baseline"))
    matches_proxy = sum(1 for r in results if r.get("matches_structural_best"))
    proxy_in_vars = sum(1 for r in results if r.get("structural_best_in_variables"))

    issue_counts: Counter = Counter()
    for r in results:
        for issue in r.get("issues", []):
            issue_counts[issue.split(":")[0]] += 1

    lines = [
        f"# Target-Variable Dict PAL Branch v1 — Live Pilot Report",
        f"**Timestamp:** {_TS}  ",
        f"**Model:** {args.model}  ",
        f"**Provider:** cohere  ",
        f"**Cases attempted:** {n}  ",
        "",
        "## Call Results",
        f"- Calls succeeded: {calls_ok}/{n}",
        f"- JSON parse rate: {parse_ok}/{n} ({parse_ok/n*100:.0f}%)" if n else "- JSON parse rate: 0/0",
        f"- Schema compliance: {schema_ok}/{n} ({schema_ok/n*100:.0f}%)" if n else "- Schema compliance: 0/0",
        f"- answer_variable_name == target_variable_name: {names_match}/{n}",
        f"- final_answer bare number: {fa_bare}/{n}",
        "",
        "## Answer Quality",
        f"- New candidates (not in existing pool): {new_candidates}/{n}",
        f"- Matches baseline answer: {matches_baseline}/{n}",
        f"- Matches proxy structural best: {matches_proxy}/{n}",
        f"- Proxy-best value found in variables (even if not final): {proxy_in_vars}/{n}",
        "",
        "## Issue Summary",
        "",
    ]
    for issue, cnt in issue_counts.most_common():
        lines.append(f"- {issue}: {cnt}")
    lines += [
        "",
        "## Safe Claims",
        "- Gold was not included in prompts.",
        "- All comparisons against gold-proxy (structural_best_answer) made post-hoc only.",
        f"- {calls_ok} API calls made to Cohere command-r-plus-08-2024.",
        "",
        "## Unsafe Claims",
        "- Do not claim exact-match accuracy improvement without held-out evaluation.",
        "- Schema compliance rate does not equal accuracy on the underlying math task.",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tiny Cohere live pilot for target_variable_dict_pal_branch_v1.")
    p.add_argument("--provider-requests", required=True, type=Path)
    p.add_argument("--selected-cases", required=True, type=Path)
    p.add_argument("--trace-packets", type=Path,
                   default=Path("/tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl"))
    p.add_argument("--replay-casebook", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--max-output-tokens", type=int, default=2048)
    p.add_argument("--allow-api", action="store_true",
                   help="Required flag to enable live API calls.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if not args.allow_api:
        print("ERROR: --allow-api flag required for live calls. Exiting.", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("COHERE_API_KEY", "")
    if not api_key:
        print("ERROR: COHERE_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    print(f"Loading provider requests from {args.provider_requests}", flush=True)
    reqs = _load_provider_requests(args.provider_requests)
    print(f"  Loaded {len(reqs)} provider requests", flush=True)

    selected = _load_selected_cases(args.selected_cases)
    print(f"  Loaded {len(selected)} selected cases", flush=True)

    print(f"Loading trace cases from {args.trace_packets}", flush=True)
    trace_cases = _load_trace_cases(args.trace_packets)
    print(f"  Loaded {len(trace_cases)} trace cases", flush=True)

    casebook = _load_casebook(args.replay_casebook)
    print(f"  Loaded casebook: {len(casebook)} rows", flush=True)

    # ------------------------------------------------------------------
    # Select top-scoring requests
    # ------------------------------------------------------------------
    def _req_score(r: dict) -> int:
        try:
            return int(float(r.get("score", 0)))
        except (ValueError, TypeError):
            return 0

    # Sort by score desc, then case_id for determinism
    sorted_reqs = sorted(reqs, key=lambda r: (-_req_score(r), r.get("case_id", "")))
    live_reqs = sorted_reqs[: args.limit]
    print(f"  Selected {len(live_reqs)} cases for live pilot (limit={args.limit})", flush=True)

    # ------------------------------------------------------------------
    # Init Cohere client
    # ------------------------------------------------------------------
    try:
        import cohere
    except ImportError:
        print("ERROR: cohere SDK not installed.", file=sys.stderr)
        sys.exit(1)

    client = cohere.ClientV2(api_key=api_key)
    print(f"  Cohere ClientV2 ready. Model: {args.model}", flush=True)

    # ------------------------------------------------------------------
    # Live calls
    # ------------------------------------------------------------------
    results: list[dict[str, Any]] = []
    consecutive_auth_errors = 0

    for call_idx, req in enumerate(live_reqs, start=1):
        case_id = req.get("case_id", "")
        print(f"  [{call_idx}/{len(live_reqs)}] {case_id} ...", end=" ", flush=True)

        trace_case = trace_cases.get(case_id, {"case_id": case_id, "question": req.get("case_id", ""), "candidate_answers": [], "selector_metadata": {}})
        cb_row = casebook.get(case_id, {})

        result = _process_case(
            req=req,
            trace_case=trace_case,
            cb_row=cb_row,
            client=client,
            model=args.model,
            max_tokens=args.max_output_tokens,
            call_index=call_idx,
        )
        results.append(result)

        if result.get("call_ok"):
            consecutive_auth_errors = 0
            status = "ok" if result.get("schema_ok") else f"parse={'ok' if result.get('parse_ok') else 'FAIL'}"
            print(f"{status} | new={result.get('is_new_candidate')} proxy_hit={result.get('matches_structural_best')}", flush=True)
        else:
            err = result.get("call_error", "")
            print(f"FAILED: {err[:80]}", flush=True)
            if "AuthenticationError" in err or "Unauthorized" in err or "401" in err:
                consecutive_auth_errors += 1
                if consecutive_auth_errors >= 2:
                    print("ERROR: Consecutive auth errors — stopping.", file=sys.stderr)
                    break

        # Brief pause between calls
        if call_idx < len(live_reqs):
            time.sleep(0.5)

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    calls_made = sum(1 for r in results if r.get("api_call_made"))

    # raw_generations: prompt + raw response
    raw_generations = []
    for r in results:
        raw_generations.append({
            "case_id": r["case_id"],
            "call_index": r["call_index"],
            "call_ok": r.get("call_ok"),
            "raw_response": r.get("raw_response", ""),
            "parse_method": r.get("parse_method", ""),
        })

    # parsed_variable_dicts: parsed JSON + validation
    parsed_dicts = []
    for r in results:
        if r.get("parse_ok"):
            parsed_dicts.append({
                "case_id": r["case_id"],
                "call_index": r["call_index"],
                "target_variable_name": r.get("target_variable_name", ""),
                "answer_variable_name": r.get("answer_variable_name", ""),
                "final_answer_generated": r.get("final_answer_generated"),
                "final_answer_normalized": r.get("final_answer_normalized", ""),
                "var_count": r.get("var_count", 0),
                "var_names": r.get("var_names", []),
                "rejected_vars": r.get("rejected_vars", []),
                "problem_summary": r.get("problem_summary", ""),
                "schema_ok": r.get("schema_ok"),
                "issues": r.get("issues", []),
            })

    # pilot_casebook: one row per case
    casebook_rows = []
    for r in results:
        casebook_rows.append({
            "case_id": r["case_id"],
            "call_index": r["call_index"],
            "call_ok": r.get("call_ok"),
            "parse_ok": r.get("parse_ok"),
            "parse_method": r.get("parse_method", ""),
            "schema_ok": r.get("schema_ok"),
            "issues": "|".join(r.get("issues", [])),
            "target_variable_name": r.get("target_variable_name", ""),
            "answer_variable_name": r.get("answer_variable_name", ""),
            "names_match": r.get("names_match"),
            "tvn_semantic": r.get("tvn_semantic"),
            "fa_bare": r.get("fa_bare"),
            "has_rejections": r.get("has_rejections"),
            "var_count": r.get("var_count"),
            "final_answer_generated": r.get("final_answer_generated"),
            "final_answer_normalized": r.get("final_answer_normalized", ""),
            "baseline_answer": r.get("baseline_answer", ""),
            "proxy_structural_best": r.get("proxy_structural_best", ""),
            "matches_baseline": r.get("matches_baseline"),
            "is_new_candidate": r.get("is_new_candidate"),
            "matches_structural_best": r.get("matches_structural_best"),
            "structural_best_in_variables": r.get("structural_best_in_variables"),
            "call_error": r.get("call_error", ""),
        })

    _write_jsonl(args.out_dir / "selected_live_cases.jsonl",
                 [{k: v for k, v in r.items() if k != "raw_response"} for r in results])
    _write_jsonl(args.out_dir / "raw_generations.jsonl", raw_generations)
    _write_jsonl(args.out_dir / "parsed_variable_dicts.jsonl", parsed_dicts)
    _write_csv(args.out_dir / "pilot_casebook.csv", casebook_rows)

    n = len(results)
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": _TS,
        "model": args.model,
        "provider": "cohere",
        "limit": args.limit,
        "cases_attempted": n,
        "api_calls_made": calls_made,
        "calls_ok": sum(1 for r in results if r.get("call_ok")),
        "parse_ok": sum(1 for r in results if r.get("parse_ok")),
        "schema_ok": sum(1 for r in results if r.get("schema_ok")),
        "names_match": sum(1 for r in results if r.get("names_match")),
        "fa_bare": sum(1 for r in results if r.get("fa_bare")),
        "new_candidates": sum(1 for r in results if r.get("is_new_candidate")),
        "matches_baseline": sum(1 for r in results if r.get("matches_baseline")),
        "matches_structural_best": sum(1 for r in results if r.get("matches_structural_best")),
        "structural_best_in_variables": sum(1 for r in results if r.get("structural_best_in_variables")),
        "avn_not_in_variables": sum(
            1 for r in results
            if any("answer_variable_not_in_variables" in issue for issue in r.get("issues", []))
        ),
        "gold_in_prompts": False,
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json",
            "selected_live_cases.jsonl",
            "raw_generations.jsonl",
            "parsed_variable_dicts.jsonl",
            "pilot_casebook.csv",
            "pilot_summary.json",
            "pilot_report.md",
        ],
    }
    _write_json(args.out_dir / "pilot_summary.json", summary)
    _write_json(args.out_dir / "manifest.json", summary)

    report = _generate_report(results, args)
    (args.out_dir / "pilot_report.md").write_text(report, encoding="utf-8")

    print(f"\n{'='*60}", flush=True)
    print(f"Done. Output: {args.out_dir}", flush=True)
    print(f"  Calls made: {calls_made}  Parse ok: {summary['parse_ok']}  Schema ok: {summary['schema_ok']}", flush=True)
    print(f"  New candidates: {summary['new_candidates']}  Proxy hits: {summary['matches_structural_best']}", flush=True)
    print(f"  Proxy-best in variables: {summary['structural_best_in_variables']}", flush=True)

    return summary


if __name__ == "__main__":
    main()
