#!/usr/bin/env python3
"""
audit_cerebras_capabilities.py

Bounded capability audit for Cerebras /v1/chat/completions.

Tests every listed model for:
  A. plain-text response
  B. JSON-only output
  C. structured reasoning-style JSON

Then runs project-prompt compatibility for models that passed B.

Does NOT log the API key. Does NOT run a large study.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "cerebras_capability_audit"
CEREBRAS_API_BASE = "https://api.cerebras.ai/v1"

CANDIDATE_MODELS = [
    "llama3.1-8b",
    "zai-glm-4.7",
    "qwen-3-235b-a22b-instruct-2507",
    "gpt-oss-120b",
]

# Test A — plain text
PROMPT_A = "Reply with exactly: ok"

# Test B — strict JSON
PROMPT_B_TEMPLATE = (
    'Return exactly this JSON and nothing else. No markdown. No explanation.\n'
    '{{"status":"ok","model":"{model}","arithmetic":391}}'
)

# Test C — structured reasoning JSON for a toy wrong-target case
PROMPT_C = """\
You are diagnosing a failure in a math solver. Return strict JSON only. No markdown.

Toy case:
  question: A store buys items for $50 each and sells them for $80 each. \
After selling 10 items, what was the total profit?
  solver_selected_answer: 800
  candidate_pool: [500, 800, 300]

Return exactly:
{"case_id":"toy_audit_c","primary_issue":"...","selected_target":"...","correct_target":"...","evidence":"..."}"""

# Required project-prompt schema fields
_PROJECT_REQUIRED_FIELDS = [
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

# Patterns that signal 403/Cloudflare/1010
_CLOUDFLARE_RE = re.compile(r"cloudflare|1010|ray id|error 403", re.I)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


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


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _try_json_parse(text: str) -> tuple[dict | None, str]:
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
# Error classification
# ---------------------------------------------------------------------------

def _classify_error(http_status: int | None, err_body: Any, response_text: str) -> dict[str, Any]:
    """Return boolean flags for known error categories."""
    is_cloudflare = False
    is_model_not_found = False
    is_rate_limit = False
    is_auth_error = False
    error_type = ""
    error_message = ""

    if isinstance(err_body, dict):
        # Unpack nested {"error": {...}} or flat
        inner = err_body.get("error", err_body)
        if isinstance(inner, dict):
            error_type = str(inner.get("type", inner.get("code", "")))
            error_message = str(inner.get("message", ""))
        else:
            error_type = str(err_body.get("type", ""))
            error_message = str(err_body.get("message", ""))
    elif isinstance(err_body, str):
        error_message = err_body[:300]

    # Check response text for Cloudflare
    if _CLOUDFLARE_RE.search(response_text or ""):
        is_cloudflare = True
    if http_status == 403:
        is_auth_error = True
        if _CLOUDFLARE_RE.search(response_text or "") or "1010" in (response_text or ""):
            is_cloudflare = True

    lc_msg = error_message.lower()
    lc_type = error_type.lower()
    if "model_not_found" in lc_type or "model not found" in lc_msg or "model_not_found" in lc_msg:
        is_model_not_found = True
    if http_status == 429 or "rate" in lc_msg or "rate_limit" in lc_type:
        is_rate_limit = True
    if http_status == 401 or "auth" in lc_type or "unauthorized" in lc_msg:
        is_auth_error = True

    return {
        "is_cloudflare_403_1010": is_cloudflare,
        "is_model_not_found": is_model_not_found,
        "is_rate_limit": is_rate_limit,
        "is_auth_error": is_auth_error,
        "error_type": error_type,
        "error_message": error_message[:200] if error_message else "",
    }


# ---------------------------------------------------------------------------
# Cerebras calls
# ---------------------------------------------------------------------------

def make_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    return session


def _call_models_endpoint(session: requests.Session) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        resp = session.get(f"{CEREBRAS_API_BASE}/models", timeout=30)
        latency_ms = int((time.monotonic() - t0) * 1000)
        if resp.ok:
            body = resp.json()
            model_ids = [m.get("id", m.get("model", "")) for m in body.get("data", [])]
            return {
                "ok": True,
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "model_ids": model_ids,
                "raw_response": body,
                "error": None,
            }
        else:
            try:
                err = resp.json()
            except Exception:
                err = {"raw": resp.text[:300]}
            return {
                "ok": False,
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "model_ids": [],
                "raw_response": {},
                "error": err,
            }
    except Exception as exc:
        return {
            "ok": False,
            "http_status": None,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "model_ids": [],
            "raw_response": {},
            "error": str(exc),
        }


def _chat(
    session: requests.Session,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float = 0.0,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    t0 = time.monotonic()
    try:
        resp = session.post(
            f"{CEREBRAS_API_BASE}/chat/completions",
            json=payload,
            timeout=90,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        if resp.ok:
            body = resp.json()
            text = body["choices"][0]["message"]["content"]
            return {
                "ok": True,
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "text": text,
                "response_length": len(text),
                "content_present": bool(text.strip()),
                "usage": body.get("usage", {}),
                "error": None,
                "raw_error_text": "",
            }
        else:
            raw_text = resp.text
            try:
                err = resp.json()
            except Exception:
                err = {"raw": raw_text[:300]}
            return {
                "ok": False,
                "http_status": resp.status_code,
                "latency_ms": latency_ms,
                "text": "",
                "response_length": 0,
                "content_present": False,
                "usage": {},
                "error": err,
                "raw_error_text": raw_text[:500],
            }
    except Exception as exc:
        return {
            "ok": False,
            "http_status": None,
            "latency_ms": int((time.monotonic() - t0) * 1000),
            "text": "",
            "response_length": 0,
            "content_present": False,
            "usage": {},
            "error": str(exc),
            "raw_error_text": "",
        }


def _chat_with_retry(
    session: requests.Session,
    model: str,
    prompt: str,
    max_tokens: int,
) -> tuple[dict[str, Any], int]:
    """One call + at most one retry for 429/5xx. Returns (result, total_calls)."""
    result = _chat(session, model, prompt, max_tokens)
    calls = 1
    if not result["ok"] and result["http_status"] is not None:
        if result["http_status"] == 429 or result["http_status"] >= 500:
            time.sleep(3)
            result = _chat(session, model, prompt, max_tokens)
            calls += 1
    return result, calls


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

def _run_test_suite(
    session: requests.Session,
    model: str,
    hard_fail_after: int = 2,
) -> list[dict[str, Any]]:
    """
    Run test A, B, C for a model.
    Stops early after `hard_fail_after` consecutive non-recoverable failures
    (not 429, not 5xx — those get one retry).
    Returns list of call_result dicts.
    """
    results: list[dict[str, Any]] = []
    hard_fails = 0

    tests = [
        ("A_plain_text",      PROMPT_A,                               256),
        ("B_json_only",       PROMPT_B_TEMPLATE.format(model=model),  256),
        ("C_json_reasoning",  PROMPT_C,                               512),
    ]

    for test_type, prompt, max_tokens in tests:
        if hard_fails >= hard_fail_after:
            break

        resp, ncalls = _chat_with_retry(session, model, prompt, max_tokens)
        err_class = _classify_error(resp["http_status"], resp.get("error"), resp.get("raw_error_text", ""))

        obj: dict | None = None
        parse_method = "n/a"
        schema_compliance: dict[str, Any] = {}

        if resp["ok"]:
            if test_type in ("B_json_only", "C_json_reasoning"):
                obj, parse_method = _try_json_parse(resp["text"])
                if test_type == "B_json_only" and obj is not None:
                    # Check expected fields
                    missing = [f for f in ("status", "model", "arithmetic") if f not in obj]
                    schema_compliance = {
                        "schema_ok": len(missing) == 0,
                        "missing_fields": missing,
                        "arithmetic_correct": obj.get("arithmetic") == 391,
                    }
                elif test_type == "C_json_reasoning" and obj is not None:
                    missing = [f for f in ("case_id", "primary_issue", "selected_target",
                                           "correct_target", "evidence") if f not in obj]
                    schema_compliance = {
                        "schema_ok": len(missing) == 0,
                        "missing_fields": missing,
                    }

        row: dict[str, Any] = {
            "model": model,
            "test_type": test_type,
            "http_status": resp["http_status"],
            "call_ok": resp["ok"],
            "api_calls_made": ncalls,
            "latency_ms": resp["latency_ms"],
            "response_length": resp["response_length"],
            "content_present": resp["content_present"],
            "json_parse_ok": obj is not None if test_type != "A_plain_text" else None,
            "json_parse_method": parse_method if test_type != "A_plain_text" else "n/a",
            "schema_ok": schema_compliance.get("schema_ok") if schema_compliance else None,
            "schema_missing_fields": schema_compliance.get("missing_fields", []),
            "text_snippet": resp["text"][:200] if resp["text"] else "",
            **err_class,
            "error_raw": resp.get("error"),
        }
        results.append(row)

        # Hard-fail tracking: stop if model returned definitive non-transient error
        if not resp["ok"]:
            if err_class["is_model_not_found"] or err_class["is_auth_error"]:
                hard_fails += 1
            elif resp["http_status"] not in (429, 500, 502, 503, 504, None):
                hard_fails += 1

    return results


# ---------------------------------------------------------------------------
# Project prompt test
# ---------------------------------------------------------------------------

def _parse_numeric(v: Any) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def _validate_project_response(obj: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    missing = [f for f in _PROJECT_REQUIRED_FIELDS if f not in obj]
    if missing:
        issues.append(f"missing_fields:{','.join(missing)}")

    avn = str(obj.get("answer_variable_name", "")).strip().lower()
    tvn = str(obj.get("target_variable_name", "")).strip().lower()
    names_match = tvn == avn
    if not names_match:
        issues.append(f"tvn_avn_mismatch")

    variables = obj.get("variables", [])
    var_names = [str(v.get("name", "")).strip().lower()
                 for v in variables if isinstance(v, dict)]
    avn_in_vars = avn in var_names
    if isinstance(variables, list) and variables and not avn_in_vars:
        issues.append("avn_not_in_variables")

    fa = obj.get("final_answer")
    fa_numeric = _parse_numeric(fa)
    fa_bare = False
    if fa_numeric is not None:
        fa_str = str(fa).strip() if not isinstance(fa, (int, float)) else str(fa)
        fa_bare = not _FORBIDDEN_ANSWER_CHARS.search(fa_str)
    if not fa_bare:
        issues.append(f"final_answer_not_bare_number")

    return {
        "schema_ok": len(issues) == 0,
        "issues": issues,
        "names_match": names_match,
        "avn_in_vars": avn_in_vars,
        "fa_bare": fa_bare,
        "fa_numeric": fa_numeric,
    }


def _audit_prompt_for_gold(prompt: str) -> bool:
    forbidden = [
        re.compile(r"\bgold_answer\s*[:=]", re.I),
        re.compile(r"\banswer_key\s*[:=]", re.I),
        re.compile(r"\bcorrect_answer\s*[:=]", re.I),
    ]
    return any(p.search(prompt) for p in forbidden)


def run_project_prompt_test(
    session: requests.Session,
    model: str,
    prompts_path: Path,
    max_prompts: int = 2,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    reqs: list[dict[str, Any]] = []
    with prompts_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                reqs.append(json.loads(line))
    reqs = reqs[:max_prompts]

    for i, req in enumerate(reqs, 1):
        case_id = req.get("case_id", f"case_{i}")
        prompt_text = req.get("prompt_text", "")
        gold_leak = _audit_prompt_for_gold(prompt_text)

        resp, ncalls = _chat_with_retry(session, model, prompt_text, max_tokens=1024)
        err_class = _classify_error(resp["http_status"], resp.get("error"), resp.get("raw_error_text", ""))

        obj, parse_method = _try_json_parse(resp["text"]) if resp["ok"] else (None, "call_failed")
        validation = _validate_project_response(obj) if obj else {
            "schema_ok": False, "issues": ["parse_failed"],
            "names_match": False, "avn_in_vars": False,
            "fa_bare": False, "fa_numeric": None,
        }

        # Check for truncation: if response ends mid-JSON
        truncated = False
        if resp["ok"] and resp["text"]:
            t = resp["text"].strip()
            truncated = bool(t) and not (t.endswith("}") or t.endswith("```"))

        row: dict[str, Any] = {
            "model": model,
            "case_id": case_id,
            "prompt_index": i,
            "gold_leak_in_prompt": gold_leak,
            "http_status": resp["http_status"],
            "call_ok": resp["ok"],
            "api_calls_made": ncalls,
            "latency_ms": resp["latency_ms"],
            "response_length": resp["response_length"],
            "truncated": truncated,
            "parse_ok": obj is not None,
            "parse_method": parse_method,
            **validation,
            **err_class,
        }
        results.append(row)

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _fmt_ok(v: Any) -> str:
    if v is True or v == "ok":
        return "ok"
    if v is False or v is None:
        return "fail"
    return str(v)


def generate_report(
    ts: str,
    models_result: dict[str, Any],
    all_call_results: list[dict[str, Any]],
    project_results: list[dict[str, Any]],
    accessible_models: list[str],
    json_reliable_models: list[str],
    project_compatible_models: list[str],
    total_api_calls: int,
) -> str:
    any_cloudflare = any(r.get("is_cloudflare_403_1010") for r in all_call_results + project_results)
    any_model_not_found = any(r.get("is_model_not_found") for r in all_call_results + project_results)
    any_rate_limit = any(r.get("is_rate_limit") for r in all_call_results + project_results)

    # Per-model summary
    by_model: dict[str, dict[str, Any]] = {}
    for r in all_call_results:
        m = r["model"]
        if m not in by_model:
            by_model[m] = {}
        by_model[m][r["test_type"]] = r

    lines = [
        f"# Cerebras Capability Audit — {ts}",
        "",
        f"**Total API calls:** {total_api_calls}",
        f"**Models listed by /v1/models:** {', '.join(models_result.get('model_ids', []))}",
        f"**Models accessible for chat:** {', '.join(accessible_models) or 'none'}",
        "",
        "## Environment",
        "",
        f"- CEREBRAS_API_KEY: set (not logged)",
        f"- /v1/models HTTP: {models_result.get('http_status')} "
        f"({'OK' if models_result.get('ok') else 'FAIL'}), "
        f"latency={models_result.get('latency_ms')}ms",
        "",
        "## Model Accessibility",
        "",
        "| model | listed | A_plain | B_json | C_reasoning | accessible |",
        "|-------|--------|---------|--------|-------------|------------|",
    ]
    for model in CANDIDATE_MODELS:
        listed = "yes" if model in models_result.get("model_ids", []) else "no"
        tests = by_model.get(model, {})
        a = _fmt_ok(tests.get("A_plain_text", {}).get("call_ok"))
        b = _fmt_ok(tests.get("B_json_only", {}).get("call_ok"))
        c = _fmt_ok(tests.get("C_json_reasoning", {}).get("call_ok"))
        acc = "YES" if model in accessible_models else "NO"
        lines.append(f"| `{model}` | {listed} | {a} | {b} | {c} | {acc} |")
    lines += [""]

    lines += [
        "## JSON Reliability",
        "",
        "| model | B_json_parse | B_schema_ok | C_json_parse | C_schema_ok |",
        "|-------|-------------|-------------|--------------|-------------|",
    ]
    for model in CANDIDATE_MODELS:
        tests = by_model.get(model, {})
        b = tests.get("B_json_only", {})
        c = tests.get("C_json_reasoning", {})
        bp = _fmt_ok(b.get("json_parse_ok"))
        bs = _fmt_ok(b.get("schema_ok"))
        cp = _fmt_ok(c.get("json_parse_ok"))
        cs = _fmt_ok(c.get("schema_ok"))
        lines.append(f"| `{model}` | {bp} | {bs} | {cp} | {cs} |")
    lines += [""]

    lines += [
        "## Latency (ms) — accessible models only",
        "",
        "| model | A_plain | B_json | C_reasoning |",
        "|-------|---------|--------|-------------|",
    ]
    for model in accessible_models:
        tests = by_model.get(model, {})
        a = tests.get("A_plain_text", {}).get("latency_ms", "—")
        b = tests.get("B_json_only", {}).get("latency_ms", "—")
        c = tests.get("C_json_reasoning", {}).get("latency_ms", "—")
        lines.append(f"| `{model}` | {a} | {b} | {c} |")
    lines += [""]

    # Project prompt table
    lines += [
        "## Project Prompt Compatibility",
        "",
    ]
    if project_results:
        lines += [
            "| model | case_id | call_ok | parse_ok | schema_ok | fa_bare | avn_in_vars | truncated | issues |",
            "|-------|---------|---------|----------|-----------|---------|-------------|-----------|--------|",
        ]
        for r in project_results:
            issues = "; ".join(r.get("issues", [])) or "—"
            lines.append(
                f"| `{r['model']}` | {r['case_id']} | {r['call_ok']} | {r['parse_ok']} | "
                f"{r.get('schema_ok')} | {r.get('fa_bare')} | {r.get('avn_in_vars')} | "
                f"{r.get('truncated')} | {issues} |"
            )
    else:
        lines.append("No project-prompt test ran (no model passed B_json_only).")
    lines += [""]

    # Error events
    lines += [
        "## Error Events",
        "",
        f"- 403 / Cloudflare 1010 occurred: **{'YES' if any_cloudflare else 'No'}**",
        f"- model_not_found occurred: **{'YES' if any_model_not_found else 'No'}**",
        f"- rate limit (429) occurred: **{'YES' if any_rate_limit else 'No'}**",
        "",
    ]

    # Inaccessible model details
    inaccessible = [m for m in CANDIDATE_MODELS if m not in accessible_models]
    if inaccessible:
        lines += ["### Inaccessible model details", ""]
        for model in inaccessible:
            tests = by_model.get(model, {})
            for tt in ("A_plain_text", "B_json_only", "C_json_reasoning"):
                r = tests.get(tt, {})
                if r:
                    lines.append(
                        f"- `{model}` / {tt}: HTTP={r.get('http_status')}, "
                        f"model_not_found={r.get('is_model_not_found')}, "
                        f"error={r.get('error_type')!r}: {r.get('error_message')!r}"
                    )
                    break
        lines += [""]

    # Recommendation
    lines += [
        "## Recommendation",
        "",
    ]
    if accessible_models:
        default_model = json_reliable_models[0] if json_reliable_models else accessible_models[0]
        lines += [
            f"**Recommended default Cerebras model:** `{default_model}`",
            "",
            f"- Accessible: {', '.join(f'`{m}`' for m in accessible_models)}",
            f"- JSON-reliable: {', '.join(f'`{m}`' for m in json_reliable_models) or 'none'}",
            f"- Project-prompt compatible: "
            f"{', '.join(f'`{m}`' for m in project_compatible_models) or 'none tested'}",
            "",
            "**Is Cerebras usable for tiny pilots in this repo?** "
            + ("Yes — at least one model is accessible and JSON-reliable."
               if json_reliable_models else "Partial — accessible but JSON reliability unclear."),
        ]
    else:
        lines += ["**No accessible model found. Cerebras is not usable under current credentials.**"]
    lines += [""]

    lines += [
        "## Caveats",
        "",
        "- No 403/1010 occurred during this audit."
        if not any_cloudflare else
        "- 403/Cloudflare 1010 DID occur during this audit.",
        "- The earlier urllib-based 403 was a client-side issue (fixed by using `requests.Session`); "
        "the error did not reproduce under `requests` in this or prior audits.",
        "- Future Cloudflare / rate-limit / model-access errors remain possible.",
        "- Model availability on /v1/models does not guarantee chat-completion access.",
        "- Audit covered temperature=0 only; higher-temperature behavior is untested.",
        "- Latency measurements are single-shot; real-world latency may vary.",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cerebras capability audit.")
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument(
        "--project-prompts",
        type=Path,
        default=Path("/tmp/target_variable_dict_pal_branch_v1_preflight/provider_requests_dry_run.jsonl"),
    )
    p.add_argument("--max-project-prompts-per-model", type=int, default=2)
    p.add_argument("--allow-api", action="store_true", default=False)
    args = p.parse_args(argv)
    if args.out_dir is None:
        args.out_dir = Path(f"outputs/cerebras_capability_audit_{_utc_stamp()}")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    api_key = os.environ.get("CEREBRAS_API_KEY", "")
    if not api_key:
        print("ERROR: CEREBRAS_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    if not args.allow_api:
        print("Dry-run mode (no --allow-api). No API calls will be made.", flush=True)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ts = _utc_stamp()
    total_api_calls = 0

    session = make_session(api_key)

    # -----------------------------------------------------------------------
    # 1. /v1/models
    # -----------------------------------------------------------------------
    print("\n[1] /v1/models ...", flush=True)
    if args.allow_api:
        models_result = _call_models_endpoint(session)
        total_api_calls += 1
    else:
        models_result = {
            "ok": False, "http_status": None, "latency_ms": 0,
            "model_ids": CANDIDATE_MODELS, "raw_response": {}, "error": "dry_run",
        }

    _write_json(args.out_dir / "models_endpoint_response.json", {
        "timestamp_utc": ts,
        "http_status": models_result["http_status"],
        "ok": models_result["ok"],
        "latency_ms": models_result["latency_ms"],
        "model_ids": models_result["model_ids"],
        "raw_response": models_result["raw_response"],
    })
    print(
        f"  HTTP {models_result['http_status']}, "
        f"models listed: {models_result['model_ids']}",
        flush=True,
    )

    # -----------------------------------------------------------------------
    # 2. Test suite: A / B / C per model
    # -----------------------------------------------------------------------
    print("\n[2] Chat completion test suite ...", flush=True)
    all_call_results: list[dict[str, Any]] = []

    for model in CANDIDATE_MODELS:
        print(f"  {model}:", flush=True)
        if args.allow_api:
            results = _run_test_suite(session, model)
            total_api_calls += sum(r.get("api_calls_made", 1) for r in results)
        else:
            results = []
        for r in results:
            status = "ok" if r["call_ok"] else f"FAIL({r['http_status']})"
            jp = f" json={r['json_parse_ok']}" if r["test_type"] != "A_plain_text" else ""
            print(f"    {r['test_type']}: {status}{jp} {r['latency_ms']}ms", flush=True)
        all_call_results.extend(results)

    _write_jsonl(args.out_dir / "call_results.jsonl", all_call_results)

    # -----------------------------------------------------------------------
    # 3. Classify models
    # -----------------------------------------------------------------------
    accessible_models: list[str] = []
    json_reliable_models: list[str] = []

    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in all_call_results:
        by_model.setdefault(r["model"], []).append(r)

    for model in CANDIDATE_MODELS:
        tests = {r["test_type"]: r for r in by_model.get(model, [])}
        # Accessible = any test returned HTTP 200
        if any(r.get("call_ok") for r in tests.values()):
            accessible_models.append(model)
        # JSON-reliable = B_json_only parsed and schema_ok
        b = tests.get("B_json_only", {})
        if b.get("call_ok") and b.get("json_parse_ok") and b.get("schema_ok"):
            json_reliable_models.append(model)

    # -----------------------------------------------------------------------
    # 4. Project prompt test
    # -----------------------------------------------------------------------
    print("\n[3] Project prompt compatibility ...", flush=True)
    project_results: list[dict[str, Any]] = []
    project_compatible_models: list[str] = []

    if args.allow_api and args.project_prompts.exists() and json_reliable_models:
        for model in json_reliable_models:
            print(f"  {model}:", flush=True)
            results = run_project_prompt_test(
                session, model, args.project_prompts,
                max_prompts=args.max_project_prompts_per_model,
            )
            total_api_calls += sum(r.get("api_calls_made", 1) for r in results)
            project_results.extend(results)
            if all(r.get("call_ok") and r.get("parse_ok") for r in results):
                project_compatible_models.append(model)
            for r in results:
                print(
                    f"    {r['case_id']}: call_ok={r['call_ok']} parse_ok={r['parse_ok']} "
                    f"schema_ok={r.get('schema_ok')} fa_bare={r.get('fa_bare')}",
                    flush=True,
                )
    elif not args.allow_api:
        print("  (skipped — dry run)", flush=True)
    elif not json_reliable_models:
        print("  (skipped — no JSON-reliable model)", flush=True)
    else:
        print(f"  (skipped — prompts file not found: {args.project_prompts})", flush=True)

    _write_jsonl(args.out_dir / "project_prompt_results.jsonl", project_results)

    # -----------------------------------------------------------------------
    # 5. Model access matrix CSV
    # -----------------------------------------------------------------------
    matrix_rows: list[dict[str, Any]] = []
    for model in CANDIDATE_MODELS:
        tests = {r["test_type"]: r for r in by_model.get(model, [])}
        a = tests.get("A_plain_text", {})
        b = tests.get("B_json_only", {})
        c = tests.get("C_json_reasoning", {})

        model_proj = [r for r in project_results if r["model"] == model]
        proj_ok = sum(1 for r in model_proj if r.get("call_ok"))
        proj_total = len(model_proj)

        matrix_rows.append({
            "model": model,
            "models_endpoint_listed": model in models_result.get("model_ids", []),
            "A_plain_text_ok": a.get("call_ok", "not_tested"),
            "A_latency_ms": a.get("latency_ms", ""),
            "B_json_ok": b.get("call_ok", "not_tested"),
            "B_json_parse_ok": b.get("json_parse_ok", "not_tested"),
            "B_schema_ok": b.get("schema_ok", "not_tested"),
            "C_json_ok": c.get("call_ok", "not_tested"),
            "C_json_parse_ok": c.get("json_parse_ok", "not_tested"),
            "C_schema_ok": c.get("schema_ok", "not_tested"),
            "project_prompts_passed": f"{proj_ok}/{proj_total}" if proj_total else "not_tested",
            "accessible": model in accessible_models,
            "json_reliable": model in json_reliable_models,
            "project_compatible": model in project_compatible_models,
            "error_type": (a or b or c).get("error_type", ""),
            "is_model_not_found": any(
                r.get("is_model_not_found") for r in [a, b, c] if r
            ),
            "is_cloudflare_403_1010": any(
                r.get("is_cloudflare_403_1010") for r in [a, b, c] if r
            ),
        })
    _write_csv(args.out_dir / "model_access_matrix.csv", matrix_rows)

    # -----------------------------------------------------------------------
    # 6. Failure summary CSV
    # -----------------------------------------------------------------------
    failure_rows = [
        {
            "model": r["model"],
            "test_type": r.get("test_type", r.get("case_id", "")),
            "http_status": r.get("http_status"),
            "error_type": r.get("error_type", ""),
            "error_message": r.get("error_message", "")[:150],
            "is_cloudflare_403_1010": r.get("is_cloudflare_403_1010", False),
            "is_model_not_found": r.get("is_model_not_found", False),
            "is_rate_limit": r.get("is_rate_limit", False),
        }
        for r in (all_call_results + project_results)
        if not r.get("call_ok")
    ]
    _write_csv(
        args.out_dir / "failure_summary.csv",
        failure_rows or [{"note": "no_failures"}],
    )

    # -----------------------------------------------------------------------
    # 7. Capability summary JSON
    # -----------------------------------------------------------------------
    any_cloudflare = any(r.get("is_cloudflare_403_1010") for r in all_call_results + project_results)
    any_model_not_found = any(r.get("is_model_not_found") for r in all_call_results + project_results)
    any_rate_limit = any(r.get("is_rate_limit") for r in all_call_results + project_results)

    capability_summary: dict[str, Any] = {
        "timestamp_utc": ts,
        "provider": "cerebras",
        "models_listed": models_result.get("model_ids", []),
        "models_accessible": accessible_models,
        "models_json_reliable": json_reliable_models,
        "models_project_compatible": project_compatible_models,
        "models_inaccessible": [m for m in CANDIDATE_MODELS if m not in accessible_models],
        "total_api_calls": total_api_calls,
        "any_cloudflare_403_1010": any_cloudflare,
        "any_model_not_found": any_model_not_found,
        "any_rate_limit": any_rate_limit,
        "recommended_default_model": (
            json_reliable_models[0] if json_reliable_models
            else accessible_models[0] if accessible_models
            else None
        ),
        "usable_for_tiny_pilots": len(json_reliable_models) > 0,
    }
    _write_json(args.out_dir / "capability_summary.json", capability_summary)

    # -----------------------------------------------------------------------
    # 8. Manifest + report
    # -----------------------------------------------------------------------
    manifest: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": ts,
        "provider": "cerebras",
        "allow_api": args.allow_api,
        "total_api_calls": total_api_calls,
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json",
            "models_endpoint_response.json",
            "model_access_matrix.csv",
            "call_results.jsonl",
            "project_prompt_results.jsonl",
            "failure_summary.csv",
            "capability_summary.json",
            "audit_report.md",
        ],
    }
    _write_json(args.out_dir / "manifest.json", manifest)

    report = generate_report(
        ts, models_result, all_call_results, project_results,
        accessible_models, json_reliable_models, project_compatible_models,
        total_api_calls,
    )
    (args.out_dir / "audit_report.md").write_text(report, encoding="utf-8")

    print(f"\nDone. Output: {args.out_dir}", flush=True)
    print(f"  accessible: {accessible_models}", flush=True)
    print(f"  json_reliable: {json_reliable_models}", flush=True)
    print(f"  project_compatible: {project_compatible_models}", flush=True)
    print(f"  total_api_calls: {total_api_calls}", flush=True)


if __name__ == "__main__":
    main()
