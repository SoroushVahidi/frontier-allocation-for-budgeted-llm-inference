#!/usr/bin/env python3
"""D6 generation runner with strict API guard and append-only run artifacts.

Default mode performs NO API calls and writes a dry-run call plan/status package.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request
import random

from experiments.data import extract_final_answer_conservative_v2, normalize_answer_text

REQUIRED_VARIANTS = [
    "frontier_math_extended_verify_v1",
    "frontier_math_answer_type_control_v1",
    "frontier_symbolic_check_v1",
]

VARIANT_INSTRUCTIONS = {
    "frontier_math_extended_verify_v1": (
        "Solve carefully and verify key arithmetic or algebra steps."
    ),
    "frontier_math_answer_type_control_v1": (
        "Return one canonical final value (simplified integer, fraction, decimal, or expression)."
    ),
    "frontier_symbolic_check_v1": (
        "Do a brief symbolic consistency check before finalizing one canonical answer."
    ),
}

VARIANT_OUTPUT_CONTRACTS = {
    "frontier_math_extended_verify_v1": {
        "goal": "Careful solve with concise verification, JSON output.",
        "output_format": "json",
        "output_contract": [
            'OUTPUT EXACTLY ONE LINE: ONLY a single JSON object and NOTHING else.',
            'The object MUST contain the key "answer" (exactly this name, no alternatives).',
            'Do NOT use "final_answer", "finalAnswer", "result", or any other key for the final answer.',
            'Do NOT return an empty object {}.',
            'Do NOT return {"answer": ""}.',
            'If uncertain, still provide the best final answer in "answer".',
            'Use {"answer": null} only if no answer can be formed at all.',
            'No markdown fences (no ```json).',
            'No text before or after the JSON object.',
            'If including brief reasoning, add it in the "reasoning" key. The "answer" key must always be present.',
            'Do not include multiple final answers.',
        ],
        "examples": {
            "positive": '{"answer":"42"}',
            "negative": '{"final_answer":"42"}',
        },
    },
    "frontier_math_answer_type_control_v1": {
        "goal": "Control final answer type and canonical formatting.",
        "output_contract": [
            "Reasoning is allowed before the final line.",
            "The final non-empty line must be exactly: FINAL_ANSWER: <answer>",
            "Do not output JSON.",
            "Do not wrap the answer in a dictionary.",
            "Do not include multiple final answers.",
            "Do not include any text after the FINAL_ANSWER line.",
            "If the answer is an expression, put only the simplified expression after FINAL_ANSWER.",
            "If uncertain, still provide the best final answer after FINAL_ANSWER.",
        ],
        "final_answer_marker": "FINAL_ANSWER:",
    },
    "frontier_symbolic_check_v1": {
        "goal": "Runtime symbolic self-check before finalizing.",
        "output_contract": [
            "Reasoning is allowed before the final line.",
            "Do a brief symbolic self-check.",
            "The final non-empty line must be exactly: FINAL_ANSWER: <answer>",
            "Do not output JSON.",
            "Do not wrap the answer in a dictionary.",
            "Do not include multiple final answers.",
            "Do not include any text after the FINAL_ANSWER line.",
            "If the answer is an expression, put only the simplified expression after FINAL_ANSWER.",
            "If uncertain, still provide the best final answer after FINAL_ANSWER.",
        ],
        "final_answer_marker": "FINAL_ANSWER:",
    },
}

STRICT_FINAL_ANSWER_LINE_RE = re.compile(r"^\s*FINAL_ANSWER\s*:\s*(.+?)\s*$")
ALIAS_FINAL_ANSWER_LINE_RE = re.compile(r"^\s*(?:Final\s+answer|Answer)\s*:\s*(.+?)\s*$", re.IGNORECASE)
JSON_ANSWER_FIELD_RE = re.compile(
    r'"(?:final_answer|answer|numeric_answer|result|solution_answer)"\s*:\s*"?([^"\n\r,}]+)"?',
    re.IGNORECASE,
)
NUMERIC_LINE_RE = re.compile(r"^\s*[-+]?\d[\d,]*(?:\.\d+)?(?:\s*/\s*\d+)?\s*$")
FENCED_JSON_RE = re.compile(r"```(?:json)?\s*\n(\{.*?\})\s*\n?```", re.IGNORECASE | re.DOTALL)
_JSON_OBJECT_SEARCH_RE = re.compile(r"\{[^{}]+\}")

FORBIDDEN_PROMPT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("gold_answer", re.compile(r"(?i)\bgold\s*[_\- ]?answer\b")),
    ("gold_label", re.compile(r"(?i)\bgold\s*[_\- ]?(label|labels|target|truth)\b")),
    ("correctness", re.compile(r"(?i)\bcorrectness\b")),
    ("oracle", re.compile(r"(?i)\boracle\b")),
    ("source_correct", re.compile(r"(?i)\bsource_correct\b")),
    ("action_correct", re.compile(r"(?i)\baction_correct\b")),
    ("frontier_correct", re.compile(r"(?i)\bfrontier_correct\b")),
    ("l1_correct", re.compile(r"(?i)\bl1_correct\b")),
    ("s1_correct", re.compile(r"(?i)\bs1_correct\b")),
    ("tale_correct", re.compile(r"(?i)\btale_correct\b")),
    ("answer_from_dataset_gold", re.compile(r"(?i)answer\s+from\s+dataset\s*/\s*gold")),
]

PROVIDER_ROUTE_DEFAULTS = {
    "cohere": {
        "provider_name": "cohere",
        "adapter_key": "cohere",
        "model_env": "COHERE_MODEL",
        "model_default": "command-r-plus-08-2024",
        "base_url_env": None,
        "required_env_any": ["COHERE_API_KEY", "CO_API_KEY"],
    },
    "cloudrift_ai": {
        "provider_name": "cloudrift_ai",
        "adapter_key": "openai_compatible",
        "model": "Qwen/Qwen3.6-35B-A3B-FP8",
        "base_url_env": "CLOUDRIFT_BASE_URL",
        "base_url_default": "https://inference.cloudrift.ai/v1",
        "required_env_any": ["CLOUDRIFT_API_KEY", "RIFT_API_KEY"],
    },
    "azure_openai": {
        "provider_name": "azure_openai",
        "adapter_key": "azure_openai",
        "model_env": "AZURE_OPENAI_DEPLOYMENT",
        "model_default": "gpt-4.1-mini",
        "base_url_env": "AZURE_OPENAI_ENDPOINT",
        "base_url_default": "https://api.openai.com/v1",
        "required_env_all": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    },
    "mistral": {
        "provider_name": "mistral",
        "adapter_key": "mistral",
        "model": "mistral-large-latest",
        "base_url_env": "MISTRAL_BASE_URL",
        "base_url_default": "https://api.mistral.ai/v1",
        "required_env_any": ["MISTRAL_API_KEY"],
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_now() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def resolve_variants(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return REQUIRED_VARIANTS[:]
    vals = [v.strip() for v in raw.split(",") if v.strip()]
    bad = [v for v in vals if v not in REQUIRED_VARIANTS]
    if bad:
        raise SystemExit(f"Unknown variants requested: {bad}. Allowed: {REQUIRED_VARIANTS}")
    return vals


def load_existing_completed(outputs_path: Path) -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    if not outputs_path.exists():
        return done
    for r in read_jsonl(outputs_path):
        if str(r.get("status", "")) == "completed":
            done.add((str(r.get("pool_id", "")), str(r.get("variant_name", ""))))
    return done


def ensure_generation_run_dir(base_run_dir: Path, resume: bool) -> Path:
    root = base_run_dir / "generation_runs"
    root.mkdir(parents=True, exist_ok=True)
    if resume:
        runs = sorted([p for p in root.glob("run_*") if p.is_dir()])
        if runs:
            return runs[-1]
    base = slug_now()
    out = root / base
    if not out.exists():
        out.mkdir(parents=True, exist_ok=False)
        return out
    idx = 1
    while True:
        candidate = root / f"{base}_{idx:02d}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        idx += 1


def write_status(path: Path, items: list[dict[str, Any]], mode: str, approve_api: bool, dry_run: bool, status: str = "ok") -> dict[str, Any]:
    counts = {k: 0 for k in ["planned", "skipped_existing", "running", "completed", "failed"]}
    for it in items:
        st = str(it.get("status", "planned"))
        if st in counts:
            counts[st] += 1
    payload = {
        "updated_at_utc": now_utc(),
        "mode": mode,
        "approve_api": bool(approve_api),
        "dry_run": bool(dry_run),
        "counts": counts,
        "total": int(len(items)),
        "status": status,
    }
    path.write_text(json.dumps(payload, indent=2))
    return payload


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_provider_tag(value: Any) -> str:
    txt = str(value or "").strip().lower()
    return txt.replace("-", "_")


def resolve_provider_route(case: dict[str, Any]) -> dict[str, Any]:
    provider_raw = normalize_provider_tag(case.get("provider"))
    scenario_raw = normalize_provider_tag(case.get("scenario"))

    # Primary D6 routes
    if provider_raw == "cohere" or scenario_raw.startswith("cohere_"):
        out = dict(PROVIDER_ROUTE_DEFAULTS["cohere"])
        out["source"] = "cohere_rule"
        return out
    if provider_raw in {"cloudrift", "cloudrift_ai"} or scenario_raw.startswith("cloudrift_"):
        out = dict(PROVIDER_ROUTE_DEFAULTS["cloudrift_ai"])
        out["source"] = "cloudrift_rule"
        return out

    # Future-proof routes
    if provider_raw in {"azure", "azure_openai"} or scenario_raw.startswith("azure_"):
        out = dict(PROVIDER_ROUTE_DEFAULTS["azure_openai"])
        out["source"] = "azure_rule"
        return out
    if provider_raw == "mistral" or scenario_raw.startswith("mistral_"):
        out = dict(PROVIDER_ROUTE_DEFAULTS["mistral"])
        out["source"] = "mistral_rule"
        return out

    return {
        "provider_name": provider_raw or "unknown",
        "adapter_key": "unsupported",
        "model": "",
        "source": "unsupported_rule",
        "unsupported_reason": f"Unsupported provider/scenario combination: provider={provider_raw!r}, scenario={scenario_raw!r}",
    }


def resolve_model_name(route: dict[str, Any]) -> str:
    model_env = route.get("model_env")
    if model_env:
        val = os.environ.get(str(model_env), "").strip()
        if val:
            return val
        return str(route.get("model_default", ""))
    return str(route.get("model", ""))


def resolve_base_url(route: dict[str, Any]) -> str | None:
    env_name = route.get("base_url_env")
    if env_name:
        val = os.environ.get(str(env_name), "").strip()
        if val:
            return val.rstrip("/")
    default = route.get("base_url_default")
    if default:
        return str(default).rstrip("/")
    return None


def check_adapter_readiness(route: dict[str, Any]) -> dict[str, Any]:
    if route.get("adapter_key") == "unsupported":
        return {
            "supported": False,
            "adapter_importable": False,
            "env_ready": False,
            "missing_env_vars": [],
            "error": route.get("unsupported_reason", "unsupported provider"),
        }

    adapter_importable = True
    adapter_error = ""
    try:
        mod = importlib.import_module("experiments.branching")
        if not hasattr(mod, "APIBranchGenerator"):
            adapter_importable = False
            adapter_error = "experiments.branching.APIBranchGenerator not found"
    except Exception as exc:  # pragma: no cover - import safety path
        adapter_importable = False
        adapter_error = f"adapter import failed: {exc}"

    missing: list[str] = []
    req_all = [str(x) for x in route.get("required_env_all", [])]
    req_any = [str(x) for x in route.get("required_env_any", [])]

    for env_name in req_all:
        if not os.environ.get(env_name, "").strip():
            missing.append(env_name)

    if req_any and not any(os.environ.get(x, "").strip() for x in req_any):
        missing.extend(req_any)

    return {
        "supported": True,
        "adapter_importable": bool(adapter_importable),
        "env_ready": len(missing) == 0,
        "missing_env_vars": sorted(set(missing)),
        "error": adapter_error,
    }


def _cohere_api_key() -> str:
    return os.environ.get("COHERE_API_KEY", "") or os.environ.get("CO_API_KEY", "")


def fetch_cohere_available_models(timeout_seconds: int = 25) -> dict[str, Any]:
    """Fetch available Cohere model IDs for approved-mode precheck.

    No key values are logged. This check runs only in approved mode.
    """
    key = _cohere_api_key().strip()
    if not key:
        return {"ok": False, "error": "missing_cohere_api_key", "model_ids": []}

    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    endpoints = [
        "https://api.cohere.com/v1/models",
        "https://api.cohere.com/v2/models",
    ]
    last_error = ""
    for url in endpoints:
        req = request.Request(url, headers=headers, method="GET")
        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            models = body.get("models") if isinstance(body, dict) else None
            if not isinstance(models, list):
                models = body.get("data") if isinstance(body, dict) else None
            if not isinstance(models, list):
                continue
            ids: list[str] = []
            for m in models:
                if not isinstance(m, dict):
                    continue
                mid = m.get("name") or m.get("id") or m.get("model")
                if isinstance(mid, str) and mid.strip():
                    ids.append(mid.strip())
            if ids:
                return {"ok": True, "error": "", "model_ids": sorted(set(ids)), "source": url}
            last_error = f"no_model_ids_from_{url}"
        except error.HTTPError as exc:  # pragma: no cover - network path
            last_error = f"http_{exc.code}_from_{url}"
        except Exception as exc:  # pragma: no cover - network path
            last_error = f"{type(exc).__name__}_from_{url}"
    return {"ok": False, "error": last_error or "cohere_model_list_unavailable", "model_ids": []}


def _build_json_prompt(problem_text: str, instruction: str, contract: dict[str, Any]) -> str:
    """Build prompt for JSON-output-format variants with positive/negative examples."""
    contract_lines = [str(x) for x in contract.get("output_contract", [])]
    examples = contract.get("examples", {})
    positive_ex = examples.get("positive", '{"answer":"42"}')
    negative_ex = examples.get("negative", '{"final_answer":"42"}')
    lines = [
        "You are solving a math problem.",
        instruction,
        "Do not include hidden metadata. Use only the problem statement.",
        "",
        "OUTPUT CONTRACT:",
    ]
    for c in contract_lines:
        lines.append(f"- {c}")
    lines += [
        "",
        "Correct output:",
        positive_ex,
        "",
        "Wrong output (invalid key name):",
        negative_ex,
        "",
        "Problem:",
        problem_text.strip(),
        "",
        'FINAL OUTPUT REMINDER: Return exactly one JSON object on a single line with key "answer". '
        'No markdown fences. No text before or after the JSON.',
    ]
    return "\n".join(lines).strip() + "\n"


def build_prompt(problem_text: str, variant_name: str) -> str:
    instruction = VARIANT_INSTRUCTIONS.get(variant_name, "Solve carefully and provide a final answer.")
    contract = VARIANT_OUTPUT_CONTRACTS.get(variant_name, {})
    if contract.get("output_format") == "json":
        return _build_json_prompt(problem_text, instruction, contract)
    contract_lines = [str(x) for x in contract.get("output_contract", [])]
    lines = [
        "You are solving a math problem.",
        instruction,
        "Do not include hidden metadata. Use only the problem statement.",
        "Output contract:",
    ]
    for c in contract_lines:
        lines.append(f"- {c}")
    lines += ["", "Problem:", problem_text.strip()]
    return "\n".join(lines).strip() + "\n"


def _normalize_scalar_answer_text(value: str) -> str | None:
    norm = normalize_answer_text(value)
    out = norm.get("normalized_answer")
    if out is None:
        txt = str(value).strip()
        return txt if txt else None
    return str(out)


def _inspect_strict_final_answer_contract(stripped_text: str) -> dict[str, Any]:
    raw_lines = stripped_text.splitlines()
    strict_hits: list[tuple[int, str]] = []
    for idx, raw in enumerate(raw_lines):
        ln = raw.strip()
        if not ln:
            continue
        m = STRICT_FINAL_ANSWER_LINE_RE.match(ln)
        if m:
            strict_hits.append((idx, m.group(1).strip()))
    if not strict_hits:
        return {
            "strict_line_exists": False,
            "strict_payload": "",
            "strict_contract_compliance": False,
            "trailing_non_empty_count": 0,
        }
    last_idx, payload = strict_hits[-1]
    trailing_non_empty_count = 0
    for idx, raw in enumerate(raw_lines):
        if idx <= last_idx:
            continue
        if raw.strip():
            trailing_non_empty_count += 1
    strict_compliant = bool(payload) and trailing_non_empty_count == 0
    return {
        "strict_line_exists": True,
        "strict_payload": payload,
        "strict_contract_compliance": strict_compliant,
        "trailing_non_empty_count": trailing_non_empty_count,
    }


def extract_answer_with_contract(response_text: str) -> dict[str, Any]:
    """Contract-aware extraction with explicit status/method diagnostics."""
    text = str(response_text or "")
    stripped = text.strip()
    if not stripped:
        return {
            "extracted_answer": None,
            "extraction_method": "none",
            "extraction_status": "failed",
            "strict_contract_compliance": False,
            "extraction_error": "empty_response",
        }

    strict_info = _inspect_strict_final_answer_contract(stripped)
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]

    # 1) strict FINAL_ANSWER line, preferring the last explicit marker line.
    for ln in reversed(lines):
        m = STRICT_FINAL_ANSWER_LINE_RE.match(ln)
        if not m:
            continue
        payload = m.group(1).strip()
        ans = _normalize_scalar_answer_text(payload)
        return {
            "extracted_answer": ans,
            "extraction_method": "strict_final_answer_marker",
            "extraction_status": "ok" if ans is not None else "failed",
            "strict_contract_compliance": bool(strict_info.get("strict_contract_compliance")) and ans is not None,
            "extraction_error": (
                "" if ans is not None and bool(strict_info.get("strict_contract_compliance"))
                else "final_answer_marker_empty" if ans is None
                else "final_answer_not_last_non_empty_line"
            ),
        }

    # 2) Alias marker support.
    for ln in reversed(lines):
        m = ALIAS_FINAL_ANSWER_LINE_RE.match(ln)
        if not m:
            continue
        payload = m.group(1).strip()
        ans = _normalize_scalar_answer_text(payload)
        return {
            "extracted_answer": ans,
            "extraction_method": "alias_final_answer_marker",
            "extraction_status": "ok" if ans is not None else "failed",
            "strict_contract_compliance": False,
            "extraction_error": "" if ans is not None else "alias_final_answer_empty",
        }

    # 3) Boxed answer fallback from conservative extractor.
    cons = extract_final_answer_conservative_v2(stripped)
    cons_ans = cons.get("answer")
    cons_rule = str(cons.get("extraction_rule_used") or "")
    if cons_ans is not None and "box" in cons_rule.lower():
        ans = _normalize_scalar_answer_text(str(cons_ans))
        return {
            "extracted_answer": ans,
            "extraction_method": f"boxed_answer_fallback::{cons_rule or 'conservative_v2'}",
            "extraction_status": "ok" if ans is not None else "failed",
            "strict_contract_compliance": False,
            "extraction_error": "" if ans is not None else "conservative_answer_not_normalized",
        }

    # 4) Lightweight JSON key extraction fallback.
    j = JSON_ANSWER_FIELD_RE.search(stripped)
    if j:
        payload = j.group(1).strip()
        ans = _normalize_scalar_answer_text(payload)
        return {
            "extracted_answer": ans,
            "extraction_method": "json_answer_field_fallback",
            "extraction_status": "ok" if ans is not None else "failed",
            "strict_contract_compliance": False,
            "extraction_error": "" if ans is not None else "json_answer_value_unusable",
        }

    # 5) Conservative repository-wide fallback (non-boxed) for compatibility.
    if cons_ans is not None:
        ans = _normalize_scalar_answer_text(str(cons_ans))
        rule = cons_rule or "conservative_v2"
        return {
            "extracted_answer": ans,
            "extraction_method": f"conservative_v2::{rule}",
            "extraction_status": "ok" if ans is not None else "failed",
            "strict_contract_compliance": False,
            "extraction_error": "" if ans is not None else "conservative_answer_not_normalized",
        }

    # 6) Last non-empty line fallback only for a safe numeric-looking line.
    if lines:
        last_line = lines[-1]
        if NUMERIC_LINE_RE.match(last_line):
            ans = _normalize_scalar_answer_text(last_line)
            return {
                "extracted_answer": ans,
                "extraction_method": "last_line_numeric_fallback",
                "extraction_status": "ok" if ans is not None else "failed",
                "strict_contract_compliance": False,
                "extraction_error": "" if ans is not None else "last_line_numeric_unusable",
            }

    return {
        "extracted_answer": None,
        "extraction_method": "none",
        "extraction_status": "failed",
        "strict_contract_compliance": False,
        "extraction_error": "no_supported_pattern",
    }


def extract_answer_json_contract(response_text: str) -> dict[str, Any]:
    """Extraction for JSON-output-format variants (e.g. frontier_math_extended_verify_v1).

    Tries in order: strict JSON, fenced JSON, ast.literal_eval dict, embedded JSON,
    conservative text fallback, safe numeric last-line fallback.
    """
    _BOXED_RE = re.compile(r"\\boxed\{([^{}]+)\}")
    _ALIAS_KEYS = ["answer", "final_answer", "finalAnswer", "result", "final"]

    def _get_answer_from_dict(d: dict) -> tuple[str | None, str | None, bool]:
        if not d:
            return None, None, True
        for key in _ALIAS_KEYS:
            if key in d:
                val = d[key]
                if val is None:
                    return None, key, True
                s = str(val).strip()
                if not s or s == "null":
                    return None, key, True
                boxed_m = _BOXED_RE.search(s)
                if boxed_m:
                    s = boxed_m.group(1).strip()
                ans = _normalize_scalar_answer_text(s)
                return ans, key, False
        return None, None, False

    text = str(response_text or "")
    stripped = text.strip()

    if not stripped:
        return {
            "extracted_answer": None, "extraction_method": "none", "extraction_status": "failed",
            "strict_json_contract_compliance": False, "response_format_type": "empty",
            "answer_key_used": None, "extraction_error": "empty_response",
            "empty_json_stub": True, "json_contract_violation_reason": "empty_response",
        }

    # 1. Strict JSON: entire response parses as a dict
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            ans, key, is_stub = _get_answer_from_dict(parsed)
            single_line = "\n" not in stripped.rstrip()
            strict = bool(ans and key == "answer" and single_line)
            violation = None
            if not strict:
                if not key or key != "answer":
                    violation = f"wrong_key:{key}"
                elif not single_line:
                    violation = "multi_line"
                elif not ans:
                    violation = "empty_or_null_answer"
            return {
                "extracted_answer": ans,
                "extraction_method": f"strict_json:key_{key}" if key else "strict_json:no_key",
                "extraction_status": "ok" if ans else "failed",
                "strict_json_contract_compliance": strict,
                "response_format_type": "strict_json",
                "answer_key_used": key,
                "extraction_error": "" if ans else "json_parsed_no_extractable_answer",
                "empty_json_stub": is_stub,
                "json_contract_violation_reason": violation,
            }
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Markdown-fenced JSON
    fenced_m = FENCED_JSON_RE.search(stripped)
    if fenced_m:
        try:
            parsed = json.loads(fenced_m.group(1).strip())
            if isinstance(parsed, dict):
                ans, key, is_stub = _get_answer_from_dict(parsed)
                return {
                    "extracted_answer": ans,
                    "extraction_method": f"fenced_json:key_{key}" if key else "fenced_json:no_key",
                    "extraction_status": "ok" if ans else "failed",
                    "strict_json_contract_compliance": False,
                    "response_format_type": "fenced_json",
                    "answer_key_used": key,
                    "extraction_error": "" if ans else "fenced_json_no_extractable_answer",
                    "empty_json_stub": is_stub,
                    "json_contract_violation_reason": "markdown_fence_present",
                }
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. ast.literal_eval for Python dict-like substrings
    dict_candidates = list(_JSON_OBJECT_SEARCH_RE.finditer(stripped))
    for match in dict_candidates:
        try:
            parsed = ast.literal_eval(match.group(0))
            if isinstance(parsed, dict):
                ans, key, is_stub = _get_answer_from_dict(parsed)
                return {
                    "extracted_answer": ans,
                    "extraction_method": f"ast_dict:key_{key}" if key else "ast_dict:no_key",
                    "extraction_status": "ok" if ans else "failed",
                    "strict_json_contract_compliance": False,
                    "response_format_type": "dict_like",
                    "answer_key_used": key,
                    "extraction_error": "" if ans else "ast_dict_no_extractable_answer",
                    "empty_json_stub": is_stub,
                    "json_contract_violation_reason": "dict_literal_not_strict_json",
                }
        except (ValueError, SyntaxError):
            pass

    # 4. JSON embedded inside prose (scan brace-delimited substrings)
    for match in dict_candidates:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                ans, key, is_stub = _get_answer_from_dict(parsed)
                return {
                    "extracted_answer": ans,
                    "extraction_method": f"embedded_json:key_{key}" if key else "embedded_json:no_key",
                    "extraction_status": "ok" if ans else "failed",
                    "strict_json_contract_compliance": False,
                    "response_format_type": "embedded_json",
                    "answer_key_used": key,
                    "extraction_error": "" if ans else "embedded_json_no_extractable_answer",
                    "empty_json_stub": is_stub,
                    "json_contract_violation_reason": "json_embedded_in_text",
                }
        except (json.JSONDecodeError, ValueError):
            pass

    # 5. Conservative text fallback (boxed LaTeX, answer phrases in text)
    cons = extract_final_answer_conservative_v2(stripped)
    cons_ans = cons.get("answer")
    cons_rule = str(cons.get("extraction_rule_used") or "")
    if cons_ans is not None:
        ans = _normalize_scalar_answer_text(str(cons_ans))
        return {
            "extracted_answer": ans,
            "extraction_method": f"text_fallback::{cons_rule}",
            "extraction_status": "ok" if ans else "failed",
            "strict_json_contract_compliance": False,
            "response_format_type": "text_fallback",
            "answer_key_used": None,
            "extraction_error": "" if ans else "fallback_answer_not_normalized",
            "empty_json_stub": False,
            "json_contract_violation_reason": "no_json_object_found",
        }

    # 6. Safe numeric last-line fallback
    lines_nz = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    if lines_nz and NUMERIC_LINE_RE.match(lines_nz[-1]):
        ans = _normalize_scalar_answer_text(lines_nz[-1])
        return {
            "extracted_answer": ans,
            "extraction_method": "numeric_line_fallback",
            "extraction_status": "ok" if ans else "failed",
            "strict_json_contract_compliance": False,
            "response_format_type": "text_fallback",
            "answer_key_used": None,
            "extraction_error": "" if ans else "last_line_numeric_unusable",
            "empty_json_stub": False,
            "json_contract_violation_reason": "no_json_object_found",
        }

    return {
        "extracted_answer": None, "extraction_method": "none", "extraction_status": "failed",
        "strict_json_contract_compliance": False, "response_format_type": "unknown",
        "answer_key_used": None, "extraction_error": "no_supported_pattern",
        "empty_json_stub": False, "json_contract_violation_reason": "no_extractable_content",
    }


def extract_answer_for_variant(response_text: str, variant_name: str) -> dict[str, Any]:
    """Dispatch extraction to the appropriate function based on the variant's output format."""
    contract = VARIANT_OUTPUT_CONTRACTS.get(variant_name, {})
    if contract.get("output_format") == "json":
        result = extract_answer_json_contract(response_text)
        result["strict_contract_compliance"] = result.get("strict_json_contract_compliance", False)
        return result
    result = extract_answer_with_contract(response_text)
    result.setdefault("strict_json_contract_compliance", False)
    result.setdefault("response_format_type", "final_answer_line")
    result.setdefault("answer_key_used", None)
    result.setdefault("empty_json_stub", False)
    result.setdefault("json_contract_violation_reason", None)
    return result


def scan_prompt_forbidden_fields(prompt_text: str) -> dict[str, Any]:
    hits = [name for name, pat in FORBIDDEN_PROMPT_PATTERNS if pat.search(prompt_text)]
    return {
        "has_forbidden": bool(hits),
        "hits": hits,
    }


def load_problem_text_lookup(manifest: dict[str, Any], run_dir: Path) -> dict[str, str]:
    candidates: list[Path] = []
    udir = manifest.get("input_artifacts", {}).get("unified_learning_tables")
    if isinstance(udir, str) and udir.strip():
        candidates.append(Path(udir) / "unified_candidate_action_table.csv")
    candidates.append(run_dir / "unified_candidate_action_table.csv")

    lookup: dict[str, str] = {}
    for path in candidates:
        if not path.exists():
            continue
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pool_id = str(row.get("pool_id") or "").strip()
                q = str(row.get("question_text") or "").strip()
                if not pool_id or not q:
                    continue
                if pool_id not in lookup:
                    lookup[pool_id] = q
        if lookup:
            return lookup
    return lookup


def _make_api_generator(route: dict[str, Any], *, timeout_seconds: int, max_tokens: int) -> Any:
    from experiments.branching import APIBranchGenerator

    provider_name = str(route.get("provider_name", ""))
    model = resolve_model_name(route)
    base_url = resolve_base_url(route)

    api_key = ""
    if provider_name == "cohere":
        api_key = os.environ.get("COHERE_API_KEY", "") or os.environ.get("CO_API_KEY", "")
    elif provider_name == "cloudrift_ai":
        api_key = os.environ.get("CLOUDRIFT_API_KEY", "") or os.environ.get("RIFT_API_KEY", "")
    elif provider_name == "azure_openai":
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    elif provider_name == "mistral":
        api_key = os.environ.get("MISTRAL_API_KEY", "")

    return APIBranchGenerator(
        provider=provider_name,
        api_key=api_key,
        model=model,
        temperature=0.1,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        base_url=base_url,
    )


def call_provider_via_existing_adapter(route: dict[str, Any], prompt_text: str, *, timeout_seconds: int, max_tokens: int) -> str:
    gen = _make_api_generator(route, timeout_seconds=timeout_seconds, max_tokens=max_tokens)
    provider_name = str(route.get("provider_name", ""))

    if provider_name == "cohere":
        return gen._call_cohere_chat_api(prompt_text)
    if provider_name == "cloudrift_ai":
        return gen._call_openai_compatible_chat_api(prompt_text)
    if provider_name == "azure_openai":
        return gen._call_azure_chat_api(prompt_text)
    if provider_name == "mistral":
        return gen._call_mistral_chat_api(prompt_text)
    raise RuntimeError(f"Unsupported provider adapter path: {provider_name}")


def output_row_schema(
    *,
    run_id: str,
    generation_item_id: str,
    scenario: str,
    provider: str,
    dataset: str,
    pool_id: str,
    original_example_id: str,
    variant_name: str,
    problem_text: str,
    prompt_hash: str,
    response_text: str,
    extracted_answer: str | None,
    normalized_answer: str | None,
    extraction_method: str,
    extraction_status: str,
    strict_contract_compliance: bool,
    extraction_error: str,
    status: str,
    error_type: str,
    error_message: str,
    # Extended JSON-contract telemetry (optional; populated for json-format variants)
    strict_json_contract_compliance: bool = False,
    response_format_type: str = "",
    answer_key_used: str | None = None,
    empty_json_stub: bool = False,
    json_contract_violation_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "generation_item_id": generation_item_id,
        "scenario": scenario,
        "provider": provider,
        "dataset": dataset,
        "pool_id": pool_id,
        "original_example_id": original_example_id,
        "variant_name": variant_name,
        "problem_text": problem_text,
        "prompt_hash": prompt_hash,
        "response_text": response_text,
        "extracted_answer": extracted_answer,
        "normalized_answer": normalized_answer,
        "extraction_method": extraction_method,
        "extraction_status": extraction_status,
        "strict_contract_compliance": bool(strict_contract_compliance),
        "strict_json_contract_compliance": bool(strict_json_contract_compliance),
        "response_format_type": response_format_type or "",
        "answer_key_used": answer_key_used,
        "empty_json_stub": bool(empty_json_stub),
        "json_contract_violation_reason": json_contract_violation_reason,
        "extraction_error": extraction_error,
        "status": status,
        "error_type": error_type,
        "error_message": error_message,
        "timestamp": now_utc(),
    }


def run_reextract_only(*, run_dir: Path, generation_run_dir: Path, output_csv: Path | None = None) -> None:
    outputs_path = generation_run_dir / "generation_outputs.jsonl"
    if not outputs_path.exists():
        raise SystemExit(f"Missing generation outputs file: {outputs_path}")

    rows = read_jsonl(outputs_path)
    if not rows:
        raise SystemExit(f"No rows found in {outputs_path}")

    out_csv = output_csv or (generation_run_dir / "reextracted_generation_outputs.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "run_id",
        "generation_item_id",
        "scenario",
        "provider",
        "dataset",
        "pool_id",
        "original_example_id",
        "variant_name",
        "prior_extracted_answer",
        "prior_extraction_method",
        "prior_extraction_status",
        "prior_strict_contract_compliance",
        "new_extracted_answer",
        "new_extraction_method",
        "new_extraction_status",
        "new_strict_contract_compliance",
        "new_strict_json_contract_compliance",
        "new_response_format_type",
        "new_answer_key_used",
        "new_empty_json_stub",
        "new_json_contract_violation_reason",
        "new_extraction_error",
        "response_text_length",
    ]

    status_counter: Counter[str] = Counter()
    strict_counter: Counter[str] = Counter()
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            vname = str(r.get("variant_name") or "")
            extraction = extract_answer_for_variant(str(r.get("response_text") or ""), vname)
            status_counter[str(extraction.get("extraction_status") or "unknown")] += 1
            strict_counter[str(bool(extraction.get("strict_contract_compliance")))] += 1
            w.writerow(
                {
                    "run_id": r.get("run_id"),
                    "generation_item_id": r.get("generation_item_id"),
                    "scenario": r.get("scenario"),
                    "provider": r.get("provider"),
                    "dataset": r.get("dataset"),
                    "pool_id": r.get("pool_id"),
                    "original_example_id": r.get("original_example_id"),
                    "variant_name": vname,
                    "prior_extracted_answer": r.get("extracted_answer"),
                    "prior_extraction_method": r.get("extraction_method", ""),
                    "prior_extraction_status": r.get("extraction_status", ""),
                    "prior_strict_contract_compliance": bool(r.get("strict_contract_compliance", False)),
                    "new_extracted_answer": extraction.get("extracted_answer"),
                    "new_extraction_method": extraction.get("extraction_method"),
                    "new_extraction_status": extraction.get("extraction_status"),
                    "new_strict_contract_compliance": bool(extraction.get("strict_contract_compliance", False)),
                    "new_strict_json_contract_compliance": bool(extraction.get("strict_json_contract_compliance", False)),
                    "new_response_format_type": extraction.get("response_format_type") or "",
                    "new_answer_key_used": extraction.get("answer_key_used"),
                    "new_empty_json_stub": bool(extraction.get("empty_json_stub", False)),
                    "new_json_contract_violation_reason": extraction.get("json_contract_violation_reason"),
                    "new_extraction_error": extraction.get("extraction_error"),
                    "response_text_length": len(str(r.get("response_text") or "")),
                }
            )

    summary = {
        "run_dir": str(run_dir),
        "generation_run_dir": str(generation_run_dir),
        "source_generation_outputs": str(outputs_path),
        "output_csv": str(out_csv),
        "total_rows": len(rows),
        "new_extraction_status_counts": dict(status_counter),
        "new_strict_contract_compliance_counts": dict(strict_counter),
        "generated_at_utc": now_utc(),
    }
    summary_path = out_csv.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print("D6 reextract-only completed.")
    print(f"output_csv={out_csv}")
    print(f"summary_json={summary_path}")


def call_provider_with_rate_limit_handling(
    route: dict[str, Any],
    prompt_text: str,
    *,
    timeout_seconds: int,
    max_tokens: int,
    sleep_seconds: int = 60,
    max_retries: int = 4,
) -> tuple[str, bool]:
    """Call provider with exponential backoff on HTTP 429 rate-limit errors.
    
    Returns: (response_text, is_rate_limited)
     - response_text: API response (empty string if rate-limited)
     - is_rate_limited: True if hit rate limit after all retries
    """
    # Exponential backoff schedule for retries 1-4.
    # The 5th attempt (after 4 retries) will fail if still rate-limited.
    backoff_schedule = [60, 120, 240, 300] 
    
    for attempt in range(1, max_retries + 2):  # max_retries + 1 attempts total (initial + retries)
        try:
            response_text = call_provider_via_existing_adapter(
                route,
                prompt_text,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
            return (response_text, False)  # Success
        except Exception as e:
            error_msg = str(e)
            is_rate_limited = "429" in error_msg or "rate_limited" in error_msg or "Rate limit exceeded" in error_msg
            
            if is_rate_limited and attempt <= max_retries: # Check if more retries are allowed
                # Apply exponential backoff with jitter
                backoff_time = backoff_schedule[attempt - 1] if attempt - 1 < len(backoff_schedule) else backoff_schedule[-1]
                jitter = random.uniform(0.5, 1.5) # Add +/- 50% jitter
                sleep_for = backoff_time * jitter
                
                provider_name = route.get("provider_name", "unknown_provider")
                print(f"[{now_utc()}] Rate limit hit for {provider_name}. Attempt {attempt}/{max_retries + 1}. Sleeping for {sleep_for:.2f} seconds...")
                time.sleep(sleep_for)
                continue
            elif is_rate_limited and attempt == max_retries + 1: # Rate-limited and out of retries
                provider_name = route.get("provider_name", "unknown_provider")
                print(f"[{now_utc()}] Rate limit hit for {provider_name}. Max retries ({max_retries}) exhausted. Marking as failed.")
                return ("", True)
            else:
                # Non-rate-limit error, re-raise
                raise
    
    # This part should ideally not be reached if the loop condition is correct.
    # It implies all attempts failed without being explicitly rate-limited or re-raised.
    return ("", False)


def main() -> None:
    ap = argparse.ArgumentParser(description="D6 frontier variant generation (guarded)")
    ap.add_argument("--run-dir", required=True, help="D6 pilot run directory")
    ap.add_argument("--approve-api", action="store_true", help="Explicitly allow API generation attempts")
    ap.add_argument("--limit", type=int, default=None, help="Optional max case count")
    ap.add_argument("--variants", default=None, help="Comma-separated variant subset")
    ap.add_argument("--dry-run", action="store_true", help="Force no-call dry-run planning mode")
    ap.add_argument("--resume", action="store_true", help="Resume latest generation run dir if present")
    ap.add_argument("--max-output-tokens", type=int, default=512, help="Max output tokens for approved provider calls")
    ap.add_argument("--timeout-seconds", type=int, default=60, help="Per-call timeout seconds for approved provider calls")
    ap.add_argument("--sleep-seconds", type=int, default=60, help="Base delay (seconds) between API requests to avoid rate-limiting")
    ap.add_argument("--max-retries", type=int, default=4, help="Max retries per item on HTTP 429 rate-limit errors")
    ap.add_argument("--reextract-only", action="store_true", help="Offline re-extraction from an existing generation run")
    ap.add_argument("--generation-run-dir", default=None, help="Generation run dir for --reextract-only")
    ap.add_argument("--reextract-output-csv", default=None, help="Optional output CSV path for --reextract-only")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)

    if args.reextract_only:
        if not args.generation_run_dir:
            raise SystemExit("--reextract-only requires --generation-run-dir")
        gen_dir = Path(args.generation_run_dir)
        if not gen_dir.exists():
            raise SystemExit(f"Missing generation run dir: {gen_dir}")
        out_csv = Path(args.reextract_output_csv) if args.reextract_output_csv else None
        run_reextract_only(run_dir=run_dir, generation_run_dir=gen_dir, output_csv=out_csv)
        return

    manifest_path = run_dir / "d6_generation_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest: {manifest_path}")

    manifest = read_json(manifest_path)
    cases_path = Path(str(manifest.get("pilot_case_selection_jsonl", run_dir / "pilot_case_selection.jsonl")))
    if not cases_path.exists():
        raise SystemExit(f"Missing pilot_case_selection.jsonl: {cases_path}")

    cases = read_jsonl(cases_path)
    variants = resolve_variants(args.variants)

    if args.limit is not None and args.limit >= 0:
        cases = cases[: args.limit]

    gen_run_dir = ensure_generation_run_dir(run_dir, resume=args.resume)
    run_id = gen_run_dir.name

    outputs_path = gen_run_dir / "generation_outputs.jsonl"
    errors_path = gen_run_dir / "generation_errors.jsonl"
    plan_path = gen_run_dir / "generation_call_plan.json"
    resolved_manifest_path = gen_run_dir / "generation_manifest_resolved.json"
    status_path = gen_run_dir / "generation_status.json"
    live_log = gen_run_dir / "generation_live.log"

    completed = load_existing_completed(outputs_path) if args.resume else set()
    problem_lookup = load_problem_text_lookup(manifest, run_dir)

    items: list[dict[str, Any]] = []
    for case in cases:
        pool_id = str(case.get("pool_id") or "")
        scenario = str(case.get("scenario") or "")
        provider = str(case.get("provider") or "")
        dataset = str(case.get("dataset") or "")
        original_example_id = str(case.get("original_example_id") or "")
        problem_text = str(case.get("problem_text") or problem_lookup.get(pool_id, "")).strip()
        route = resolve_provider_route(case)
        readiness = check_adapter_readiness(route)

        for v in variants:
            key = (pool_id, v)
            st = "skipped_existing" if key in completed else "planned"
            prompt_text = build_prompt(problem_text=problem_text, variant_name=v) if problem_text else ""
            prompt_hash = stable_hash(prompt_text) if prompt_text else ""
            prompt_scan = scan_prompt_forbidden_fields(prompt_text) if prompt_text else {"has_forbidden": False, "hits": []}
            generation_item_id = stable_hash(f"{pool_id}::{v}::{scenario}")

            items.append(
                {
                    "run_id": run_id,
                    "generation_item_id": generation_item_id,
                    "pool_id": pool_id,
                    "scenario": scenario,
                    "provider": provider,
                    "dataset": dataset,
                    "split": case.get("split"),
                    "selection_bucket": case.get("selection_bucket"),
                    "variant_name": v,
                    "status": st,
                    "api_call_status": "not_run" if st == "planned" else "already_done",
                    "question_hash": case.get("question_hash"),
                    "example_uid": case.get("example_uid"),
                    "original_example_id": original_example_id,
                    "problem_text": problem_text,
                    "prompt_text": prompt_text,
                    "prompt_hash": prompt_hash,
                    "prompt_forbidden_scan": prompt_scan,
                    "provider_route": {
                        "provider_name": route.get("provider_name"),
                        "adapter_key": route.get("adapter_key"),
                        "route_source": route.get("source"),
                        "model": resolve_model_name(route),
                        "base_url": resolve_base_url(route),
                    },
                    "adapter_readiness": readiness,
                }
            )

    resolved_manifest = {
        "prepared_from": str(manifest_path),
        "resolved_at_utc": now_utc(),
        "run_dir": str(run_dir),
        "generation_run_dir": str(gen_run_dir),
        "run_id": run_id,
        "case_count": len(cases),
        "variant_names": variants,
        "approve_api": bool(args.approve_api),
        "dry_run": bool(args.dry_run),
        "resume": bool(args.resume),
        "notes": [
            "No gold/correctness labels are used in provider prompts.",
            "frontier_symbolic_check_v1 is runtime symbolic consistency, not a gold check.",
            "Default mode is no-call planning unless --approve-api is explicitly set.",
        ],
    }
    resolved_manifest_path.write_text(json.dumps(resolved_manifest, indent=2))
    plan_path.write_text(json.dumps(items, indent=2))

    mode = "DRY_RUN_NO_CALLS"
    if not args.approve_api or args.dry_run:
        write_status(status_path, items, mode=mode, approve_api=args.approve_api, dry_run=args.dry_run)
        live_log.write_text(
            f"[{now_utc()}] Dry-run planning complete. API not executed. planned_items={sum(1 for i in items if i['status']=='planned')}\n"
        )
        print("D6 generation dry-run complete. No API calls executed.")
        print(f"generation_run_dir={gen_run_dir}")
        print(f"planned_items={sum(1 for i in items if i['status']=='planned')}")
        return

    precheck_failures: list[dict[str, Any]] = []
    cohere_models_requested: set[str] = set()
    for it in items:
        if it["status"] == "skipped_existing":
            continue
        route = it.get("provider_route", {})
        if str(route.get("provider_name") or "") == "cohere":
            cohere_models_requested.add(str(route.get("model") or "").strip())
        if not str(it.get("problem_text") or "").strip():
            precheck_failures.append(
                {
                    "generation_item_id": it.get("generation_item_id"),
                    "pool_id": it.get("pool_id"),
                    "variant_name": it.get("variant_name"),
                    "error_type": "missing_problem_text",
                    "error_message": "problem_text could not be resolved from pilot case or unified tables",
                }
            )
        scan = it.get("prompt_forbidden_scan", {})
        if bool(scan.get("has_forbidden")):
            precheck_failures.append(
                {
                    "generation_item_id": it.get("generation_item_id"),
                    "pool_id": it.get("pool_id"),
                    "variant_name": it.get("variant_name"),
                    "error_type": "prompt_leakage",
                    "error_message": f"forbidden prompt fields detected: {scan.get('hits', [])}",
                }
            )
        ready = it.get("adapter_readiness", {})
        if not bool(ready.get("supported", False)):
            precheck_failures.append(
                {
                    "generation_item_id": it.get("generation_item_id"),
                    "pool_id": it.get("pool_id"),
                    "variant_name": it.get("variant_name"),
                    "error_type": "unsupported_provider",
                    "error_message": str(ready.get("error") or "unsupported provider"),
                }
            )
        elif not bool(ready.get("adapter_importable", False)):
            precheck_failures.append(
                {
                    "generation_item_id": it.get("generation_item_id"),
                    "pool_id": it.get("pool_id"),
                    "variant_name": it.get("variant_name"),
                    "error_type": "adapter_import_failure",
                    "error_message": str(ready.get("error") or "adapter import failed"),
                }
            )
        elif not bool(ready.get("env_ready", False)):
            precheck_failures.append(
                {
                    "generation_item_id": it.get("generation_item_id"),
                    "pool_id": it.get("pool_id"),
                    "variant_name": it.get("variant_name"),
                    "error_type": "missing_provider_env",
                    "error_message": f"missing env vars: {ready.get('missing_env_vars', [])}",
                }
            )

    # Cohere-specific model availability precheck: fail before benchmark calls.
    if cohere_models_requested:
        blank_models = sorted(m for m in cohere_models_requested if not m)
        for m in blank_models:
            precheck_failures.append(
                {
                    "generation_item_id": "",
                    "pool_id": "",
                    "variant_name": "",
                    "error_type": "cohere_model_missing",
                    "error_message": (
                        "Cohere model is not configured. Set a valid model id via "
                        "`export COHERE_MODEL=<valid_model_id>` before running --approve-api."
                    ),
                }
            )

        non_blank_models = sorted(m for m in cohere_models_requested if m)
        if non_blank_models:
            probe = fetch_cohere_available_models(timeout_seconds=max(10, int(args.timeout_seconds)))
            if not bool(probe.get("ok")):
                precheck_failures.append(
                    {
                        "generation_item_id": "",
                        "pool_id": "",
                        "variant_name": "",
                        "error_type": "cohere_model_validation_failed",
                        "error_message": (
                            "Could not verify Cohere model availability before benchmark calls "
                            f"({probe.get('error')}). Configure COHERE_MODEL explicitly and retry."
                        ),
                    }
                )
            else:
                available = set(str(x) for x in probe.get("model_ids", []))
                for model_name in non_blank_models:
                    if model_name not in available:
                        precheck_failures.append(
                            {
                                "generation_item_id": "",
                                "pool_id": "",
                                "variant_name": "",
                                "error_type": "cohere_model_unavailable",
                                "error_message": (
                                    f"Configured Cohere model `{model_name}` is not present in Cohere model list. "
                                    "Set a valid model id via `export COHERE_MODEL=<valid_model_id>` and retry."
                                ),
                            }
                        )

    if precheck_failures:
        for fail in precheck_failures:
            append_jsonl(
                errors_path,
                {
                    "run_id": run_id,
                    "failed_at_utc": now_utc(),
                    **fail,
                },
            )
        stat = write_status(
            status_path,
            items,
            mode="API_APPROVED_BLOCKED_PRECHECK",
            approve_api=args.approve_api,
            dry_run=args.dry_run,
            status="blocked_precheck",
        )
        with live_log.open("a") as f:
            f.write(f"[{now_utc()}] API-approved run blocked by precheck failures: {len(precheck_failures)}\n")
        print("D6 generation blocked before API calls due to adapter/prompt precheck failures.")
        print(json.dumps(stat, indent=2))
        return

    with live_log.open("a") as f:
        f.write(f"[{now_utc()}] API-approved run requested. Executing guarded adapter path.\n")

    for it in items:
        if it["status"] == "skipped_existing":
            continue
        it["status"] = "running"
        it["api_call_status"] = "running"

        prompt_text = str(it.get("prompt_text") or "")
        route = it.get("provider_route", {})

        try:
            response_text, is_rate_limited = call_provider_with_rate_limit_handling(
                route,
                prompt_text,
                timeout_seconds=int(args.timeout_seconds),
                max_tokens=int(args.max_output_tokens),
                sleep_seconds=int(args.sleep_seconds),
                max_retries=int(args.max_retries),
            )
             
            # Handle rate-limit error
            if is_rate_limited:
                it["status"] = "failed"
                it["api_call_status"] = "failed"
                err_row = output_row_schema(
                    run_id=run_id,
                    generation_item_id=str(it.get("generation_item_id")),
                    scenario=str(it.get("scenario") or ""),
                    provider=str(route.get("provider_name") or it.get("provider") or ""),
                    dataset=str(it.get("dataset") or ""),
                    pool_id=str(it.get("pool_id") or ""),
                    original_example_id=str(it.get("original_example_id") or ""),
                    variant_name=str(it.get("variant_name") or ""),
                    problem_text=str(it.get("problem_text") or ""),
                    prompt_hash=str(it.get("prompt_hash") or ""),
                    response_text="",
                    extracted_answer=None,
                    normalized_answer=None,
                    extraction_method="none",
                    extraction_status="failed",
                    strict_contract_compliance=False,
                    extraction_error="provider_call_failed",
                    status="failed",
                    error_type="RateLimitError",
                    error_message="HTTP 429 Rate limit exceeded after max retries",
                )
                append_jsonl(errors_path, err_row)
                with live_log.open("a") as f:
                    f.write(json.dumps(err_row, ensure_ascii=True) + "\n")
                # Continue to next item (don't break on rate-limit)
                continue
             
            extraction = extract_answer_for_variant(response_text, str(it.get("variant_name") or ""))
            extracted_answer = extraction.get("extracted_answer")
            norm = normalize_answer_text(str(extracted_answer) if extracted_answer is not None else "")
            normalized_answer = norm.get("normalized_answer")

            out_row = output_row_schema(
                run_id=run_id,
                generation_item_id=str(it.get("generation_item_id")),
                scenario=str(it.get("scenario") or ""),
                provider=str(route.get("provider_name") or it.get("provider") or ""),
                dataset=str(it.get("dataset") or ""),
                pool_id=str(it.get("pool_id") or ""),
                original_example_id=str(it.get("original_example_id") or ""),
                variant_name=str(it.get("variant_name") or ""),
                problem_text=str(it.get("problem_text") or ""),
                prompt_hash=str(it.get("prompt_hash") or ""),
                response_text=response_text,
                extracted_answer=str(extracted_answer) if extracted_answer is not None else None,
                normalized_answer=str(normalized_answer) if normalized_answer is not None else None,
                extraction_method=str(extraction.get("extraction_method") or ""),
                extraction_status=str(extraction.get("extraction_status") or ""),
                strict_contract_compliance=bool(extraction.get("strict_contract_compliance", False)),
                extraction_error=str(extraction.get("extraction_error") or ""),
                status="completed",
                error_type="",
                error_message="",
                strict_json_contract_compliance=bool(extraction.get("strict_json_contract_compliance", False)),
                response_format_type=str(extraction.get("response_format_type") or ""),
                answer_key_used=extraction.get("answer_key_used"),
                empty_json_stub=bool(extraction.get("empty_json_stub", False)),
                json_contract_violation_reason=extraction.get("json_contract_violation_reason"),
            )
            append_jsonl(outputs_path, out_row)
            it["status"] = "completed"
            it["api_call_status"] = "completed"
             
            # Sleep after successful call to avoid rate-limit
            time.sleep(int(args.sleep_seconds))
             
        except Exception as e:  # pragma: no cover - network path
            it["status"] = "failed"
            it["api_call_status"] = "failed"
            err_row = output_row_schema(
                run_id=run_id,
                generation_item_id=str(it.get("generation_item_id")),
                scenario=str(it.get("scenario") or ""),
                provider=str(route.get("provider_name") or it.get("provider") or ""),
                dataset=str(it.get("dataset") or ""),
                pool_id=str(it.get("pool_id") or ""),
                original_example_id=str(it.get("original_example_id") or ""),
                variant_name=str(it.get("variant_name") or ""),
                problem_text=str(it.get("problem_text") or ""),
                prompt_hash=str(it.get("prompt_hash") or ""),
                response_text="",
                extracted_answer=None,
                normalized_answer=None,
                extraction_method="none",
                extraction_status="failed",
                strict_contract_compliance=False,
                extraction_error="provider_call_failed",
                status="failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            append_jsonl(errors_path, err_row)
            with live_log.open("a") as f:
                f.write(json.dumps(err_row, ensure_ascii=True) + "\n")
            # Continue on non-rate-limit errors too (instead of breaking)
            continue

    plan_path.write_text(json.dumps(items, indent=2))
    stat = write_status(status_path, items, mode="API_APPROVED_ATTEMPTED", approve_api=args.approve_api, dry_run=args.dry_run)
    print("D6 generation run ended.")
    print(json.dumps(stat, indent=2))


if __name__ == "__main__":
    main()
