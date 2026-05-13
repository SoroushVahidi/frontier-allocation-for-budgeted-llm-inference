#!/usr/bin/env python3
"""
run_cerebras_target_variable_dict_pal_pilot.py

Cerebras-only live pilot for target_variable_dict_pal_branch_v1.

Sends the rendered target-variable-dict prompt to Cerebras llama3.1-8b,
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

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "cerebras_target_variable_dict_pal_branch_v1"
CEREBRAS_API_BASE = "https://api.cerebras.ai/v1"
DEFAULT_MODEL = "llama3.1-8b"

_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("(empty)\n", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                        for k, v in row.items()})


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


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
# JSON extraction
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
# Schema validation
# ---------------------------------------------------------------------------

def validate_variable_dict(obj: dict) -> dict[str, Any]:
    issues: list[str] = []

    missing = [f for f in _REQUIRED_FIELDS if f not in obj]
    if missing:
        issues.append(f"missing_fields:{','.join(missing)}")

    tvn = str(obj.get("target_variable_name", "")).strip().lower()
    avn = str(obj.get("answer_variable_name", "")).strip().lower()
    tvn_semantic = tvn not in _GENERIC_NAMES and len(tvn) > 1
    avn_semantic = avn not in _GENERIC_NAMES and len(avn) > 1
    if not tvn_semantic:
        issues.append(f"non_semantic_target_variable_name:{tvn!r}")
    if not avn_semantic:
        issues.append(f"non_semantic_answer_variable_name:{avn!r}")

    names_match = tvn == avn
    if not names_match:
        issues.append(f"answer_variable_mismatch:target={tvn!r},answer={avn!r}")

    variables = obj.get("variables", [])
    vars_ok = isinstance(variables, list) and len(variables) > 0
    if not vars_ok:
        issues.append("variables_empty_or_not_list")

    var_names = [str(v.get("name", "")).strip().lower() for v in variables if isinstance(v, dict)]
    avn_in_vars = avn in var_names
    if vars_ok and not avn_in_vars:
        issues.append(f"answer_variable_not_in_variables:{avn!r}")

    rejected = obj.get("rejected_non_final_variables", [])
    has_rejections = isinstance(rejected, list) and len(rejected) > 0
    if not has_rejections:
        issues.append("rejected_non_final_variables_empty")

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
            # Bundle format: {"cases": [...]}
            for case in obj.get("cases", [obj]):
                cid = case.get("case_id", "")
                if cid:
                    cases[cid] = case
    return cases


def _load_casebook(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                rows[cid] = dict(row)
    return rows


# ---------------------------------------------------------------------------
# Cerebras call
# ---------------------------------------------------------------------------

def make_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    return session


def _call_cerebras(
    session: requests.Session,
    model: str,
    prompt: str,
    max_tokens: int,
) -> tuple[str, dict[str, Any], bool, str | None]:
    """
    Make one Cerebras chat call.
    Returns (text, usage_dict, call_ok, error_str).
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    try:
        resp = session.post(
            f"{CEREBRAS_API_BASE}/chat/completions",
            json=payload,
            timeout=90,
        )
        if resp.ok:
            body = resp.json()
            text = body["choices"][0]["message"]["content"]
            usage: dict[str, Any] = body.get("usage", {})
            return text, usage, True, None
        else:
            try:
                err_body = resp.json()
            except Exception:
                err_body = {"raw": resp.text[:300]}
            inner = err_body.get("error", err_body)
            if isinstance(inner, dict):
                code = inner.get("type", inner.get("code", ""))
                msg = inner.get("message", "")
                err_str = f"{code}: {msg}" if code else str(inner)[:200]
            else:
                err_str = str(err_body)[:200]
            return "", {}, False, f"HTTP {resp.status_code} {err_str}"
    except Exception as exc:
        return "", {}, False, f"{type(exc).__name__}: {str(exc)[:200]}"


def _call_cerebras_with_retry(
    session: requests.Session,
    model: str,
    prompt: str,
    max_tokens: int,
) -> tuple[str, dict[str, Any], bool, str | None, int]:
    """One call + one retry on 429/5xx. Returns (..., total_calls)."""
    text, usage, ok, err = _call_cerebras(session, model, prompt, max_tokens)
    calls = 1
    if not ok and err is not None:
        status_str = err.split()[1] if err.startswith("HTTP ") else ""
        try:
            status = int(status_str)
        except ValueError:
            status = 0
        if status == 429 or status >= 500:
            time.sleep(3)
            text, usage, ok, err = _call_cerebras(session, model, prompt, max_tokens)
            calls += 1
    return text, usage, ok, err, calls


# ---------------------------------------------------------------------------
# Per-case processing
# ---------------------------------------------------------------------------

def _process_case(
    *,
    req: dict[str, Any],
    trace_case: dict[str, Any],
    cb_row: dict[str, str],
    session: requests.Session,
    model: str,
    max_tokens: int,
    call_index: int,
) -> tuple[dict[str, Any], int]:
    """Process one case. Returns (result_dict, api_calls_made)."""
    case_id = req.get("case_id", "")
    prompt = req.get("prompt_text", "")

    # Audit prompt for gold leakage
    gold_in_prompt = any(p.search(prompt) for p in _FORBIDDEN_PROMPT_RE)

    sm = trace_case.get("selector_metadata", {})
    if isinstance(sm, str):
        try:
            sm = json.loads(sm)
        except Exception:
            sm = {}

    result: dict[str, Any] = {
        "call_index": call_index,
        "case_id": case_id,
        "question": trace_case.get("question", ""),
        "baseline_answer": str(sm.get("selected_answer", "")),
        "candidate_answers": trace_case.get("candidate_answers", []),
        "proxy_structural_best": cb_row.get("structural_best_answer", ""),
        "api_call_made": True,
        "call_timestamp": _utc_stamp(),
        "model": model,
        "provider": "cerebras",
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "gold_in_prompt": gold_in_prompt,
    }

    # Live Cerebras call
    raw_text, usage, call_ok, call_error, ncalls = _call_cerebras_with_retry(
        session, model, prompt, max_tokens
    )
    result["usage"] = usage
    result["call_ok"] = call_ok
    result["call_error"] = call_error

    if not call_ok:
        result["raw_response"] = ""
        result.update({
            "parse_ok": False, "parse_method": "call_failed",
            "schema_ok": False, "issues": ["call_failed"],
            "final_answer_generated": None, "final_answer_normalized": "",
            "is_new_candidate": False,
            "matches_baseline": False,
            "matches_structural_best": False,
        })
        return result, ncalls

    result["raw_response"] = raw_text

    # JSON parse
    obj, parse_method = _extract_json(raw_text)
    result["parse_ok"] = obj is not None
    result["parse_method"] = parse_method

    if obj is None:
        result.update({
            "schema_ok": False, "issues": ["json_parse_failed"],
            "final_answer_generated": None, "final_answer_normalized": "",
            "is_new_candidate": False,
            "matches_baseline": False,
            "matches_structural_best": False,
        })
        return result, ncalls

    # Schema validation
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

    # Post-hoc comparison (gold-free)
    baseline_norm = _normalize_answer(result["baseline_answer"])
    pool_norms = {_normalize_answer(a) for a in result["candidate_answers"]}
    proxy_best_norm = _normalize_answer(result["proxy_structural_best"])

    result["matches_baseline"] = fa_str == baseline_norm
    result["is_new_candidate"] = fa_str not in pool_norms and fa_str not in ("", "NA")
    result["matches_structural_best"] = (
        fa_str == proxy_best_norm and proxy_best_norm not in ("", "NA")
    )

    # Check if any variable value matches structural best
    var_values = []
    for v in obj.get("variables", []):
        if isinstance(v, dict):
            vval = _normalize_answer(v.get("value", ""))
            var_values.append(vval)
    result["var_values"] = var_values
    result["structural_best_in_variables"] = (
        proxy_best_norm in var_values and proxy_best_norm not in ("", "NA")
    )

    return result, ncalls


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _generate_report(results: list[dict[str, Any]], model: str, ts: str) -> str:
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
    gold_in_any = any(r.get("gold_in_prompt") for r in results)

    issue_counts: Counter = Counter()
    for r in results:
        for issue in r.get("issues", []):
            issue_counts[issue.split(":")[0]] += 1

    pct = lambda a, b: f"{a/b*100:.0f}%" if b else "—"  # noqa: E731

    lines = [
        "# Cerebras Target-Variable Dict PAL Branch — Live Pilot Report",
        f"**Timestamp:** {ts}",
        f"**Model:** `{model}` (Cerebras)",
        f"**Cases attempted:** {n}",
        "",
        "## Call Results",
        "",
        f"| metric | value |",
        f"|--------|-------|",
        f"| Calls succeeded | {calls_ok}/{n} |",
        f"| JSON parse rate | {parse_ok}/{n} ({pct(parse_ok,n)}) |",
        f"| Schema compliance | {schema_ok}/{n} ({pct(schema_ok,n)}) |",
        f"| answer_variable_name == target_variable_name | {names_match}/{n} |",
        f"| final_answer is bare number | {fa_bare}/{n} |",
        f"| Gold in any prompt | {'YES — AUDIT FAILURE' if gold_in_any else 'No'} |",
        "",
        "## Answer Quality (post-hoc, gold-free proxy)",
        "",
        f"| metric | value |",
        f"|--------|-------|",
        f"| New candidates (not in existing pool) | {new_candidates}/{parse_ok} |",
        f"| Matches baseline (selected) answer | {matches_baseline}/{parse_ok} |",
        f"| Matches proxy structural best | {matches_proxy}/{parse_ok} |",
        f"| Proxy-best value in generated variables | {proxy_in_vars}/{parse_ok} |",
        "",
        "## Per-Case Summary",
        "",
        "| # | case_id | call_ok | parse_ok | schema_ok | fa | new | proxy_hit | issues |",
        "|---|---------|---------|----------|-----------|-----|-----|-----------|--------|",
    ]
    for r in results:
        fa_disp = r.get("final_answer_normalized", "?")
        issues = "; ".join(r.get("issues", []))[:60] or "—"
        lines.append(
            f"| {r['call_index']} | {r['case_id']} | {r.get('call_ok')} | "
            f"{r.get('parse_ok')} | {r.get('schema_ok')} | {fa_disp} | "
            f"{r.get('is_new_candidate')} | {r.get('matches_structural_best')} | {issues} |"
        )

    lines += [
        "",
        "## Issue Summary",
        "",
    ]
    for issue, cnt in issue_counts.most_common():
        lines.append(f"- `{issue}`: {cnt}")

    lines += [
        "",
        "## Useful Variable Values",
        "",
        "Cases where a variable value matched the proxy structural best "
        "(even when final_answer was wrong):",
        "",
    ]
    for r in results:
        if r.get("structural_best_in_variables") and not r.get("matches_structural_best"):
            lines.append(
                f"- **{r['case_id']}**: proxy_best={r.get('proxy_structural_best')}, "
                f"final={r.get('final_answer_normalized')}, "
                f"var_values={r.get('var_values', [])}"
            )

    # Follow-up recommendation
    lines += [
        "",
        "## Follow-Up Recommendation",
        "",
    ]
    if schema_ok >= n * 0.75 and new_candidates >= 2:
        lines += [
            "**A 20-case follow-up pilot is justified.** "
            f"Schema compliance {pct(schema_ok,n)}, "
            f"new candidates {new_candidates}/{parse_ok}. "
            "Cerebras `llama3.1-8b` produces structured variable dicts at useful quality.",
        ]
    elif parse_ok == n and schema_ok >= n * 0.5:
        lines += [
            "**A 20-case follow-up pilot is conditionally justified.** "
            f"All calls parsed ({parse_ok}/{n}) and schema compliance is {pct(schema_ok,n)}. "
            "Recommend fixing `avn_not_in_variables` failure before scaling.",
        ]
    else:
        lines += [
            "**Follow-up not recommended until schema failures are resolved.** "
            f"Schema compliance {pct(schema_ok,n)}. Investigate common failure modes first.",
        ]

    lines += [
        "",
        "## Safe Claims",
        "",
        "- Gold was not included in prompts.",
        "- All comparisons made post-hoc only against structural_best_answer (proxy, not gold).",
        f"- {calls_ok} API calls made to Cerebras `{model}`.",
        "- Schema compliance ≠ accuracy on the underlying math task.",
        "",
        "## Unsafe Claims",
        "",
        "- Do not claim exact-match accuracy improvement without held-out evaluation.",
        "- Do not claim Cerebras results generalize to the full 97-case slice from 8 cases.",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Cerebras live pilot for target_variable_dict_pal_branch_v1."
    )
    p.add_argument("--provider-requests", required=True, type=Path)
    p.add_argument("--selected-cases", required=True, type=Path)
    p.add_argument(
        "--trace-packets",
        type=Path,
        default=Path("/tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl"),
    )
    p.add_argument("--replay-casebook", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--max-output-tokens", type=int, default=2048)
    p.add_argument(
        "--allow-api",
        action="store_true",
        help="Required to enable live API calls.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ts = _utc_stamp()

    if not args.allow_api:
        print("ERROR: --allow-api flag required for live calls.", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("CEREBRAS_API_KEY", "")
    if not api_key:
        print("ERROR: CEREBRAS_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    # --- Load data ---
    print(f"Loading provider requests from {args.provider_requests}", flush=True)
    reqs = _load_provider_requests(args.provider_requests)
    print(f"  {len(reqs)} provider requests loaded", flush=True)

    selected_meta = _load_selected_cases(args.selected_cases)
    print(f"  {len(selected_meta)} selected-case metadata rows", flush=True)

    print(f"Loading trace cases from {args.trace_packets}", flush=True)
    trace_cases = _load_trace_cases(args.trace_packets)
    print(f"  {len(trace_cases)} trace cases loaded", flush=True)

    casebook = _load_casebook(args.replay_casebook)
    print(f"  Casebook: {len(casebook)} rows", flush=True)

    # --- Sort by score and cap ---
    def _req_score(r: dict) -> float:
        try:
            return float(r.get("score", 0))
        except (ValueError, TypeError):
            return 0.0

    sorted_reqs = sorted(reqs, key=lambda r: (-_req_score(r), r.get("case_id", "")))
    live_reqs = sorted_reqs[: args.limit]
    print(f"  {len(live_reqs)} cases selected for pilot (limit={args.limit})", flush=True)

    # --- Init Cerebras session ---
    session = make_session(api_key)
    print(f"  Cerebras session ready. Model: {args.model}", flush=True)

    # --- Live calls ---
    results: list[dict[str, Any]] = []
    total_api_calls = 0

    for call_idx, req in enumerate(live_reqs, start=1):
        case_id = req.get("case_id", "")
        print(f"  [{call_idx}/{len(live_reqs)}] {case_id} ...", end=" ", flush=True)

        trace_case = trace_cases.get(
            case_id,
            {"case_id": case_id, "question": "", "candidate_answers": [], "selector_metadata": {}},
        )
        cb_row = casebook.get(case_id, {})

        result, ncalls = _process_case(
            req=req,
            trace_case=trace_case,
            cb_row=cb_row,
            session=session,
            model=args.model,
            max_tokens=args.max_output_tokens,
            call_index=call_idx,
        )
        total_api_calls += ncalls
        results.append(result)

        if result.get("call_ok"):
            status = "SCHEMA_OK" if result.get("schema_ok") else (
                "PARSE_OK" if result.get("parse_ok") else "PARSE_FAIL"
            )
            print(
                f"{status} fa={result.get('final_answer_normalized','?')} "
                f"new={result.get('is_new_candidate')} "
                f"proxy={result.get('matches_structural_best')}",
                flush=True,
            )
            if result.get("issues"):
                print(f"    issues: {result['issues']}", flush=True)
        else:
            print(f"CALL_FAIL {result.get('call_error','')[:80]}", flush=True)

    # --- Write outputs ---
    # raw_generations: minimal (case_id, call_index, call_ok, raw_response, parse_method)
    raw_gen_rows = [
        {
            "case_id": r["case_id"],
            "call_index": r["call_index"],
            "call_ok": r["call_ok"],
            "raw_response": r.get("raw_response", ""),
            "parse_method": r.get("parse_method", ""),
        }
        for r in results
    ]
    _write_jsonl(args.out_dir / "raw_generations.jsonl", raw_gen_rows)

    # parsed_outputs: everything except raw_response (keeps file manageable)
    parsed_rows = [
        {k: v for k, v in r.items() if k != "raw_response"}
        for r in results
    ]
    _write_jsonl(args.out_dir / "parsed_outputs.jsonl", parsed_rows)

    # selected_live_cases: full result rows (matches Cohere pilot schema)
    _write_jsonl(args.out_dir / "selected_live_cases.jsonl", results)

    # pilot_casebook.csv
    casebook_rows = [
        {
            "call_index": r["call_index"],
            "case_id": r["case_id"],
            "baseline_answer": r.get("baseline_answer", ""),
            "proxy_structural_best": r.get("proxy_structural_best", ""),
            "final_answer_generated": r.get("final_answer_generated", ""),
            "final_answer_normalized": r.get("final_answer_normalized", ""),
            "call_ok": r.get("call_ok"),
            "parse_ok": r.get("parse_ok"),
            "schema_ok": r.get("schema_ok"),
            "names_match": r.get("names_match"),
            "fa_bare": r.get("fa_bare"),
            "avn_in_vars": r.get("avn_in_vars"),
            "is_new_candidate": r.get("is_new_candidate"),
            "matches_baseline": r.get("matches_baseline"),
            "matches_structural_best": r.get("matches_structural_best"),
            "structural_best_in_variables": r.get("structural_best_in_variables"),
            "issues": "; ".join(r.get("issues", [])),
            "gold_in_prompt": r.get("gold_in_prompt", False),
        }
        for r in results
    ]
    _write_csv(args.out_dir / "pilot_casebook.csv", casebook_rows)

    # pilot_summary.json
    n = len(results)
    calls_ok = sum(1 for r in results if r.get("call_ok"))
    parse_ok_n = sum(1 for r in results if r.get("parse_ok"))
    schema_ok_n = sum(1 for r in results if r.get("schema_ok"))
    summary: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": ts,
        "model": args.model,
        "provider": "cerebras",
        "limit": args.limit,
        "cases_attempted": n,
        "api_calls_made": total_api_calls,
        "calls_ok": calls_ok,
        "parse_ok": parse_ok_n,
        "schema_ok": schema_ok_n,
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
        "gold_in_prompts": any(r.get("gold_in_prompt") for r in results),
        "out_dir": str(args.out_dir),
    }
    _write_json(args.out_dir / "pilot_summary.json", summary)

    # manifest.json
    manifest: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": ts,
        "model": args.model,
        "provider": "cerebras",
        "cases_attempted": n,
        "api_calls_made": total_api_calls,
        "calls_ok": calls_ok,
        "parse_ok": parse_ok_n,
        "schema_ok": schema_ok_n,
        "gold_in_prompts": summary["gold_in_prompts"],
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json",
            "selected_live_cases.jsonl",
            "raw_generations.jsonl",
            "parsed_outputs.jsonl",
            "pilot_casebook.csv",
            "pilot_summary.json",
            "pilot_report.md",
        ],
    }
    _write_json(args.out_dir / "manifest.json", manifest)

    # pilot_report.md
    report = _generate_report(results, args.model, ts)
    (args.out_dir / "pilot_report.md").write_text(report, encoding="utf-8")

    print(f"\nDone. Output: {args.out_dir}", flush=True)
    print(f"  API calls: {total_api_calls}", flush=True)
    print(f"  parse_ok: {parse_ok_n}/{n}", flush=True)
    print(f"  schema_ok: {schema_ok_n}/{n}", flush=True)
    print(f"  new_candidates: {summary['new_candidates']}", flush=True)


if __name__ == "__main__":
    main()
