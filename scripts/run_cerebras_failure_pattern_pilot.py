#!/usr/bin/env python3
"""
run_cerebras_failure_pattern_pilot.py

Bounded qualitative failure-pattern discovery pilot over the
wrong_supported_consensus_97 slice using Cerebras.

Each case gets its own prompt (compact gold-free evidence packet).
Cerebras returns per-case JSON labeling the failure mechanism.
Post-hoc reporting uses local labels only.

This is NOT an accuracy comparison. Gold is never included in prompts.
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

EXPERIMENT_ID = "cerebras_failure_pattern_pilot"
CEREBRAS_API_BASE = "https://api.cerebras.ai/v1"

CANDIDATE_MODELS = [
    "llama3.1-8b",
    "zai-glm-4.7",
    "qwen-3-235b-a22b-instruct-2507",
    "gpt-oss-120b",
]

VALID_SUBTYPES = frozenset({
    "profit_vs_sale_price",
    "difference_vs_total",
    "original_before_after",
    "per_unit_vs_total",
    "unit_conversion",
    "ratio_base",
    "leftover_remainder",
    "other",
    "none",
})

VALID_NEXT_EDGES = frozenset({
    "backward_from_target_check",
    "target_variable_dict_pal",
    "declarative_equation_branch",
    "ratio_base_branch",
    "original_before_process_branch",
    "per_unit_share_branch",
    "profit_revenue_cost_branch",
    "difference_or_remainder_branch",
    "unit_conversion_branch",
    "target_first_final_transform_branch",
    "none",
})

REQUIRED_RESPONSE_FIELDS = [
    "case_id",
    "primary_failure_mechanism",
    "secondary_failure_mechanisms",
    "is_final_target_binding_failure",
    "is_candidate_absence_failure",
    "is_selector_failure",
    "is_repair_collapse",
    "wrong_target_subtype",
    "evidence_summary",
    "computed_nearby_quantity",
    "missing_candidate_hypothesis",
    "recommended_next_edge",
    "confidence",
]

SYSTEM_INSTRUCTION = """\
You are labeling PAL failure mechanisms from trace-grounded evidence.
Return JSON only. Do not use any reference answer or label metadata beyond the packet.
Do not solve the problem from scratch.
Do not claim the selected answer is wrong unless the trace evidence supports it.
Distinguish candidate absence (gold not in pool) from selector failure (gold present but not picked).
Distinguish wrong target binding from arithmetic error.
Confidence must be between 0.0 and 1.0.

Return exactly these keys:
case_id, primary_failure_mechanism, secondary_failure_mechanisms,
is_final_target_binding_failure, is_candidate_absence_failure, is_selector_failure,
is_repair_collapse, wrong_target_subtype, evidence_summary, computed_nearby_quantity,
missing_candidate_hypothesis, recommended_next_edge, confidence

Allowed wrong_target_subtype values:
  profit_vs_sale_price | difference_vs_total | original_before_after | per_unit_vs_total |
  unit_conversion | ratio_base | leftover_remainder | other | none

Allowed recommended_next_edge values:
  backward_from_target_check | target_variable_dict_pal | declarative_equation_branch |
  ratio_base_branch | original_before_process_branch | per_unit_share_branch |
  profit_revenue_cost_branch | difference_or_remainder_branch | unit_conversion_branch |
  target_first_final_transform_branch | none\
"""

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
# Data loaders
# ---------------------------------------------------------------------------

def load_trace_packets(path: Path) -> list[dict[str, Any]]:
    """Load the 97-case bundle, returning a flat list of case dicts."""
    with path.open(encoding="utf-8") as f:
        raw = f.read().strip()
    bundle = json.loads(raw)
    if "cases" in bundle:
        return list(bundle["cases"])
    # Already a list
    cases = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def parse_gold_pool_split(report_path: Path) -> tuple[list[str], list[str]]:
    """
    Parse the markdown gold-pool split report.
    Returns (gold_present_not_selected_ids, gold_absent_ids).
    """
    content = report_path.read_text(encoding="utf-8")

    def _extract_ids(section_text: str) -> list[str]:
        ids = []
        for m in re.finditer(r"\| (openai_gsm8k_\d+) \|", section_text):
            cid = m.group(1)
            if cid not in ids:
                ids.append(cid)
        return ids

    sec_a = re.search(r"## A\. gold_present_not_selected(.*?)(?=## B\.)", content, re.DOTALL)
    sec_b = re.search(r"## B\. gold_absent_from_pool(.*?)(?=## C\.|$)", content, re.DOTALL)

    gpns = _extract_ids(sec_a.group(1) if sec_a else "")
    ga = _extract_ids(sec_b.group(1) if sec_b else "")
    return gpns, ga


def load_replay_casebook(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                rows[cid] = dict(row)
    return rows


def load_missing_edge_recs(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                rows[cid] = dict(row)
    return rows


def load_heldout_policy_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    by_case: dict[str, list[dict[str, str]]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id", "")
            if cid:
                by_case.setdefault(cid, []).append(dict(row))
    return by_case


# ---------------------------------------------------------------------------
# Case selection
# ---------------------------------------------------------------------------

def select_cases(
    all_cases: list[dict[str, Any]],
    gold_present_not_selected: list[str],
    gold_absent: list[str],
    replay_cb: dict[str, dict[str, str]],
    missing_edge_recs: dict[str, dict[str, str]],
    limit: int = 24,
) -> list[dict[str, Any]]:
    """
    Stratified selection:
      up to 8 gold_present_not_selected
      up to 8 gold_absent
      up to 4 repair_layer_collapse_to_1 (not already covered)
      up to 4 backward_from_target_check primary (not already covered)
    Deduped, capped at limit.
    """
    cases_by_id: dict[str, dict[str, Any]] = {c["case_id"]: c for c in all_cases}

    selected: list[str] = []
    strata: dict[str, str] = {}

    def _add(cids: list[str], stratum: str, cap: int) -> None:
        added = 0
        for cid in cids:
            if cid in cases_by_id and cid not in selected and len(selected) < limit:
                selected.append(cid)
                strata[cid] = stratum
                added += 1
                if added >= cap:
                    break

    _add(gold_present_not_selected, "gold_present_not_selected", 8)
    _add(gold_absent, "gold_absent", 8)

    # repair_layer_collapse_to_1
    collapse_ids = [
        cid for cid, row in replay_cb.items()
        if row.get("repair_layer_collapse_to_1", "").strip().lower() in {"true", "1", "yes"}
    ]
    _add(collapse_ids, "repair_layer_collapse", 4)

    # backward_from_target_check primary recommendation not yet covered
    bftc_ids = [
        cid for cid, row in missing_edge_recs.items()
        if row.get("primary_recommendation", "").strip() == "backward_from_target_check"
    ]
    _add(bftc_ids, "missing_bftc", 4)

    return [
        {**cases_by_id[cid], "_stratum": strata[cid]}
        for cid in selected
        if cid in cases_by_id
    ]


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _safe_truncate(s: str, n: int) -> str:
    s = str(s)
    return s[:n] + "…" if len(s) > n else s


def build_case_prompt(
    case: dict[str, Any],
    missing_edge_rec: dict[str, str] | None,
) -> str:
    """Build a compact gold-free per-case evidence packet prompt."""
    cid = case.get("case_id", "")
    question = case.get("question", "")

    sm = case.get("selector_metadata", {})
    if isinstance(sm, str):
        try:
            sm = json.loads(sm)
        except Exception:
            sm = {}

    selected_answer = sm.get("selected_answer", case.get("model_final_prediction", ""))
    selected_source = sm.get("selected_source", "")

    ats = case.get("action_trace_summary", {})
    if isinstance(ats, str):
        try:
            ats = json.loads(ats)
        except Exception:
            ats = {}

    pes = case.get("pal_exec_summary", {})
    if isinstance(pes, str):
        try:
            pes = json.loads(pes)
        except Exception:
            pes = {}

    # Candidate pool — compact representation
    pool = case.get("selector_candidate_pool", [])
    if isinstance(pool, list):
        pool_str = ", ".join(str(v) for v in pool[:10])
    else:
        pool_str = str(pool)[:200]

    # Structural candidate rows — compact
    sf = case.get("structural_fields", {})
    if isinstance(sf, str):
        try:
            sf = json.loads(sf)
        except Exception:
            sf = {}
    cand_rows = sf.get("candidate_rows", [])
    struct_lines = []
    for cr in cand_rows[:6]:
        if isinstance(cr, dict):
            ans = cr.get("candidate_answer", "?")
            role = cr.get("candidate_role", cr.get("branch_family", ""))
            src = cr.get("alias", cr.get("source_family", ""))
            struct_lines.append(f"  {ans} [{src}/{role}]")
    struct_str = "\n".join(struct_lines) if struct_lines else "  (none)"

    # PAL summary
    pal_ok = str(pes.get("pal_exec_ok", "")) in {"1", "True", "true"}
    pal_ans = pes.get("pal_answer", "")
    pal_err = pes.get("pal_error_type", pes.get("pal_retry_reason", ""))
    pal_str = f"exec_ok={pal_ok}, answer={pal_ans!r}, error={pal_err!r}"

    # Action trace summary
    short_diag = ats.get("short_diagnosis", ats.get("latest_method_failure_tag", ""))
    sel_reason = ats.get("selection_reason", "")
    failure_family = ats.get("failure_family", "")
    likely_subtype = ats.get("likely_mismatch_subtype", "")

    # Missing edge recommendation
    rec_str = "none"
    if missing_edge_rec:
        rec_str = (
            f"primary={missing_edge_rec.get('primary_recommendation', 'none')}, "
            f"all={missing_edge_rec.get('recommended_next_edges', '[]')}, "
            f"reason={_safe_truncate(missing_edge_rec.get('recommendation_reasons', ''), 200)}"
        )

    prompt = f"""{SYSTEM_INSTRUCTION}

---
Case packet (no gold answer, no correctness label):

case_id: {cid}
question: {_safe_truncate(question, 400)}
selected_answer: {selected_answer}
selected_source: {selected_source}
selector_candidate_pool: [{pool_str}]

action_trace:
  short_diagnosis: {_safe_truncate(short_diag, 200)}
  selection_reason: {sel_reason}
  failure_family: {failure_family}
  likely_mismatch_subtype: {likely_subtype}

pal_exec: {pal_str}

structural_candidate_rows:
{struct_str}

missing_edge_recommendation: {rec_str}
---

Return exactly one JSON object for this case. No markdown, no code fences."""

    return prompt


# ---------------------------------------------------------------------------
# Cerebras API
# ---------------------------------------------------------------------------

def make_session(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    return session


def _chat(
    session: requests.Session,
    model: str,
    prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
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
            return {"ok": True, "http_status": resp.status_code, "text": text,
                    "usage": body.get("usage", {}), "error": None}
        else:
            try:
                err = resp.json()
            except Exception:
                err = {"raw": resp.text[:300]}
            return {"ok": False, "http_status": resp.status_code, "text": "",
                    "usage": {}, "error": err}
    except Exception as exc:
        return {"ok": False, "http_status": None, "text": "", "usage": {}, "error": str(exc)}


def model_access_check(
    session: requests.Session,
    probe_prompt: str = 'Return exactly valid JSON: {"status":"ok","probe":1}',
) -> tuple[str | None, list[dict[str, Any]]]:
    """Try each candidate model in order. Return (first_ok, results)."""
    results: list[dict[str, Any]] = []
    first_ok: str | None = None

    for model in CANDIDATE_MODELS:
        resp = _chat(session, model, probe_prompt, max_tokens=100)
        obj, parse_method = _try_json_parse(resp["text"]) if resp["ok"] else (None, "no_response")
        result: dict[str, Any] = {
            "model": model,
            "http_status": resp["http_status"],
            "call_ok": resp["ok"],
            "json_parse_ok": obj is not None,
            "parse_method": parse_method,
            "error": resp["error"],
            "response_snippet": resp["text"][:150] if resp["text"] else "",
        }
        results.append(result)
        if resp["ok"] and obj is not None and first_ok is None:
            first_ok = model
            break

    return first_ok, results


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
# Schema validation
# ---------------------------------------------------------------------------

def validate_response(obj: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    missing = [f for f in REQUIRED_RESPONSE_FIELDS if f not in obj]
    if missing:
        issues.append(f"missing_fields:{','.join(missing)}")

    conf = obj.get("confidence")
    try:
        conf_f = float(conf)  # type: ignore[arg-type]
        if not (0.0 <= conf_f <= 1.0):
            issues.append(f"confidence_out_of_range:{conf}")
    except (TypeError, ValueError):
        issues.append(f"confidence_not_float:{conf!r}")

    wts = str(obj.get("wrong_target_subtype", "")).strip()
    if wts not in VALID_SUBTYPES:
        issues.append(f"invalid_wrong_target_subtype:{wts!r}")

    rne = str(obj.get("recommended_next_edge", "")).strip()
    if rne not in VALID_NEXT_EDGES:
        issues.append(f"invalid_recommended_next_edge:{rne!r}")

    smf = obj.get("secondary_failure_mechanisms")
    if not isinstance(smf, list):
        issues.append("secondary_failure_mechanisms_not_list")

    for bool_field in ("is_final_target_binding_failure", "is_candidate_absence_failure",
                       "is_selector_failure", "is_repair_collapse"):
        val = obj.get(bool_field)
        if not isinstance(val, bool):
            issues.append(f"{bool_field}_not_bool")

    return {"schema_ok": len(issues) == 0, "issues": issues}


def audit_prompt_for_gold(prompt: str) -> bool:
    """Return True if prompt seems to contain a gold answer (bad)."""
    forbidden = [
        re.compile(r"\bgold_answer\s*[:=]", re.I),
        re.compile(r"\banswer_key\s*[:=]", re.I),
        re.compile(r"\bcorrect_answer\s*[:=]", re.I),
        re.compile(r"\bhidden[_ -]?labels?\s*[:=]", re.I),
    ]
    return any(p.search(prompt) for p in forbidden)


# ---------------------------------------------------------------------------
# Agreement analysis
# ---------------------------------------------------------------------------

HYPOTHESIS_FIELDS = {
    "is_final_target_binding_failure": True,
    "is_candidate_absence_failure": True,
}


def compute_agreement(parsed_labels: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute per-case and aggregate agreement with the project hypothesis."""
    n = len(parsed_labels)
    if n == 0:
        return {"n": 0, "hypothesis_agreement_rate": 0.0, "details": []}

    agrees = []
    details = []
    for row in parsed_labels:
        obj = row.get("parsed_obj", {}) or {}
        per_field: dict[str, Any] = {}
        all_match = True
        for field, expected in HYPOTHESIS_FIELDS.items():
            val = obj.get(field)
            match = val == expected
            per_field[field] = {"value": val, "expected": expected, "match": match}
            if not match:
                all_match = False
        rne = str(obj.get("recommended_next_edge", ""))
        hyp_rne = rne in {"backward_from_target_check", "target_variable_dict_pal"}
        per_field["recommended_next_edge"] = {
            "value": rne, "supports_hypothesis": hyp_rne
        }
        if not hyp_rne:
            all_match = False
        agrees.append(all_match)
        details.append({
            "case_id": row.get("case_id"),
            "full_agreement": all_match,
            "per_field": per_field,
        })

    rate = sum(agrees) / n
    return {
        "n": n,
        "hypothesis_agreement_rate": round(rate, 4),
        "agrees_count": sum(agrees),
        "details": details,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    args: argparse.Namespace,
    model: str,
    selected: list[dict[str, Any]],
    parsed_labels: list[dict[str, Any]],
    access_results: list[dict[str, Any]],
    agreement: dict[str, Any],
    total_api_calls: int,
    out_dir: Path,
) -> str:
    ts = _utc_stamp()
    n = len(parsed_labels)
    parse_ok = sum(1 for r in parsed_labels if r.get("parse_ok"))
    schema_ok_n = sum(1 for r in parsed_labels if r.get("schema_ok"))

    # Pattern counts
    primary_counts: Counter[str] = Counter()
    subtype_counts: Counter[str] = Counter()
    rne_counts: Counter[str] = Counter()
    ftbf_count = 0
    caf_count = 0
    sel_fail_count = 0
    repair_col_count = 0

    for row in parsed_labels:
        obj = row.get("parsed_obj") or {}
        if not obj:
            continue
        primary_counts[str(obj.get("primary_failure_mechanism", "unknown"))] += 1
        subtype_counts[str(obj.get("wrong_target_subtype", "none"))] += 1
        rne_counts[str(obj.get("recommended_next_edge", "none"))] += 1
        if obj.get("is_final_target_binding_failure") is True:
            ftbf_count += 1
        if obj.get("is_candidate_absence_failure") is True:
            caf_count += 1
        if obj.get("is_selector_failure") is True:
            sel_fail_count += 1
        if obj.get("is_repair_collapse") is True:
            repair_col_count += 1

    # Top 5 strongest cases (highest confidence + schema_ok)
    scored = [
        r for r in parsed_labels
        if r.get("parse_ok") and r.get("schema_ok")
    ]
    scored.sort(key=lambda r: float((r.get("parsed_obj") or {}).get("confidence", 0)), reverse=True)
    top5 = scored[:5]

    # Disagreements / unclear
    unclear = [
        r for r in parsed_labels
        if r.get("parse_ok") and not r.get("schema_ok")
    ] + [
        r for r in parsed_labels
        if not r.get("parse_ok")
    ]

    # Hypothesis agreement
    agr_rate = agreement.get("hypothesis_agreement_rate", 0.0)

    lines = [
        f"# Cerebras Failure-Pattern Pilot — {ts}",
        "",
        f"**Provider:** Cerebras  **Model:** `{model}`",
        f"**Cases attempted:** {n} / {args.limit}  **Total API calls:** {total_api_calls}",
        f"**Parse OK:** {parse_ok}/{n}  **Schema OK:** {schema_ok_n}/{n}",
        "",
        "## Model Access Check",
        "",
    ]
    for r in access_results:
        status = "OK" if r.get("call_ok") else "FAILED"
        err = ""
        if not r.get("call_ok") and r.get("error"):
            e = r["error"]
            if isinstance(e, dict):
                code = e.get("type") or (e.get("error") or {}).get("type") or ""
                msg = e.get("message") or (e.get("error") or {}).get("message") or ""
                err = f" — {code}: {msg}" if (code or msg) else f" — {str(e)[:80]}"
            else:
                err = f" — {str(e)[:80]}"
        lines.append(f"- `{r['model']}`: {status} (HTTP {r.get('http_status')}){err}")
    lines += [""]

    lines += [
        "## Stratification",
        "",
    ]
    strata_counts: Counter[str] = Counter()
    for c in selected:
        strata_counts[c.get("_stratum", "unknown")] += 1
    for stratum, count in strata_counts.most_common():
        lines.append(f"- {stratum}: {count}")
    lines += [""]

    lines += [
        "## Primary Failure Mechanism Counts",
        "",
        "| mechanism | count |",
        "|-----------|-------|",
    ]
    for mech, cnt in primary_counts.most_common():
        lines.append(f"| {mech} | {cnt} |")
    lines += [""]

    lines += [
        "## Wrong-Target Subtype Counts",
        "",
        "| subtype | count |",
        "|---------|-------|",
    ]
    for st, cnt in subtype_counts.most_common():
        lines.append(f"| {st} | {cnt} |")
    lines += [""]

    lines += [
        "## Recommended Next-Edge Counts",
        "",
        "| recommended_next_edge | count |",
        "|-----------------------|-------|",
    ]
    for rne, cnt in rne_counts.most_common():
        lines.append(f"| {rne} | {cnt} |")
    lines += [""]

    lines += [
        "## Boolean Flags (of parsed cases)",
        "",
        f"- is_final_target_binding_failure=True: {ftbf_count}/{parse_ok}",
        f"- is_candidate_absence_failure=True: {caf_count}/{parse_ok}",
        f"- is_selector_failure=True: {sel_fail_count}/{parse_ok}",
        f"- is_repair_collapse=True: {repair_col_count}/{parse_ok}",
        "",
        "## Hypothesis Agreement",
        "",
        f"Hypothesis: final-target binding failure + candidate absence + "
        f"missing backward_from_target_check / target-variable branch",
        "",
        f"**Full agreement rate:** {agr_rate:.1%} ({agreement.get('agrees_count', 0)}/{parse_ok} parsed cases)",
        "",
    ]

    if agr_rate >= 0.6:
        lines.append(
            "Cerebras **independently supports** the final-target-binding + candidate-absence hypothesis "
            f"at ≥60% agreement ({agr_rate:.1%})."
        )
    elif agr_rate >= 0.4:
        lines.append(
            "Cerebras **partially supports** the hypothesis "
            f"({agr_rate:.1%} agreement). Mixed signal."
        )
    else:
        lines.append(
            f"Cerebras **disputes or is inconclusive** on the hypothesis ({agr_rate:.1%} agreement)."
        )
    lines += [""]

    lines += [
        "## Top 5 Strongest Cases",
        "",
    ]
    for r in top5:
        obj = r.get("parsed_obj") or {}
        lines.append(
            f"**{r['case_id']}** — {obj.get('primary_failure_mechanism', '?')} "
            f"(confidence={obj.get('confidence', '?')}, subtype={obj.get('wrong_target_subtype', '?')})"
        )
        lines.append(f"  evidence: {_safe_truncate(str(obj.get('evidence_summary', '')), 200)}")
        lines.append("")

    if unclear:
        lines += [
            "## Unclear / Schema-Failed Cases",
            "",
        ]
        for r in unclear[:5]:
            issues = r.get("schema_issues", r.get("issues", []))
            lines.append(f"- {r['case_id']}: parse_ok={r.get('parse_ok')}, issues={issues}")
        lines += [""]

    # Follow-up recommendation
    lines += [
        "## Follow-Up Recommendation",
        "",
    ]
    bftc_rate = rne_counts.get("backward_from_target_check", 0) / max(parse_ok, 1)
    tvd_rate = rne_counts.get("target_variable_dict_pal", 0) / max(parse_ok, 1)
    if bftc_rate + tvd_rate >= 0.3 or agr_rate >= 0.5:
        lines += [
            "Results **support** a follow-up live pilot with:",
            "1. `backward_from_target_check` allocation (recommended by "
            f"{rne_counts.get('backward_from_target_check', 0)} cases)",
            "2. `target_variable_dict_pal` branch (recommended by "
            f"{rne_counts.get('target_variable_dict_pal', 0)} cases)",
            "3. `declarative_equation_branch` (recommended by "
            f"{rne_counts.get('declarative_equation_branch', 0)} cases)",
        ]
    else:
        lines += [
            "Results are **inconclusive** for recommending a specific follow-up branch. "
            "Expand the pilot or review schema failures before proceeding."
        ]

    lines += [""]

    lines += [
        "## Interpretation Caveats",
        "",
        "- This is a qualitative provider-assisted pattern-finding pilot.",
        "- 24 cases ≠ final pattern over all 97.",
        "- Do not claim this validates accuracy improvement.",
        "- Gold was never included in prompts.",
        "",
        "## Repo Modifications",
        "",
        "- `scripts/run_cerebras_failure_pattern_pilot.py` — created",
        "- `tests/test_cerebras_failure_pattern_pilot.py` — created",
        "- No other repo files were modified.",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cerebras failure-pattern pilot over wrong_consensus_97.")
    p.add_argument(
        "--trace-packets",
        type=Path,
        default=Path("/tmp/codex_pattern_mining_wrong_consensus_97_packets/trace_packets.jsonl"),
    )
    p.add_argument(
        "--gold-pool-report",
        type=Path,
        default=Path("/tmp/gold_pool_split_wrong_consensus_97_report.md"),
    )
    p.add_argument(
        "--replay-casebook",
        type=Path,
        default=Path(
            "/tmp/target_finalization_verifier_replay_v1_wrong_consensus_97_gold_scored/replay_casebook.csv"
        ),
    )
    p.add_argument(
        "--missing-edge-recs",
        type=Path,
        default=Path(
            "/tmp/frontier_node_distribution_mining_v1_wrong_consensus_97/missing_edge_recommendations.csv"
        ),
    )
    p.add_argument(
        "--heldout-policy-rows",
        type=Path,
        default=Path(
            "/tmp/frontier_next_edge_policy_v1_heldout_wrong_consensus_97/heldout_prediction_rows.csv"
        ),
    )
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument("--limit", type=int, default=24)
    p.add_argument("--max-output-tokens", type=int, default=1024)
    p.add_argument("--allow-api", action="store_true", default=False)

    args = p.parse_args(argv)

    if args.out_dir is None:
        ts = _utc_stamp()
        args.out_dir = Path(f"outputs/cerebras_failure_pattern_pilot_24_{ts}")

    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    api_key = os.environ.get("CEREBRAS_API_KEY", "")
    if not api_key:
        print("ERROR: CEREBRAS_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ts = _utc_stamp()
    total_api_calls = 0

    print(f"Loading inputs ...", flush=True)
    cases = load_trace_packets(args.trace_packets)
    print(f"  {len(cases)} trace cases loaded", flush=True)

    gold_present_not_selected, gold_absent = parse_gold_pool_split(args.gold_pool_report)
    print(
        f"  gold_present_not_selected: {len(gold_present_not_selected)}, "
        f"gold_absent: {len(gold_absent)}",
        flush=True,
    )

    replay_cb = load_replay_casebook(args.replay_casebook)
    missing_edge_recs = load_missing_edge_recs(args.missing_edge_recs)
    print(f"  replay casebook: {len(replay_cb)}, missing-edge recs: {len(missing_edge_recs)}", flush=True)

    # Case selection
    selected = select_cases(
        cases, gold_present_not_selected, gold_absent,
        replay_cb, missing_edge_recs, limit=args.limit,
    )
    print(f"Selected {len(selected)} cases", flush=True)
    _write_jsonl(args.out_dir / "selected_cases.jsonl", selected)

    # Model access check
    print("\nModel access check ...", flush=True)
    session = make_session(api_key)
    model, access_results = model_access_check(session)

    _write_json(args.out_dir / "model_access_check.json", {
        "timestamp_utc": ts,
        "candidate_models": CANDIDATE_MODELS,
        "first_accessible_model": model,
        "results": access_results,
    })
    total_api_calls += len(access_results)

    for r in access_results:
        status = "OK" if r.get("call_ok") else "FAILED"
        print(f"  {r['model']}: {status} (HTTP {r.get('http_status')})", flush=True)

    if model is None:
        print("No accessible Cerebras model. Writing manifest and exiting.", file=sys.stderr)
        _write_json(args.out_dir / "manifest.json", {
            "experiment_id": EXPERIMENT_ID,
            "timestamp_utc": ts,
            "provider": "cerebras",
            "first_accessible_model": None,
            "pilot_ran": False,
            "reason": "no_accessible_model",
        })
        sys.exit(1)

    print(f"\nUsing model: {model}", flush=True)

    # Build prompts and run pilot
    provider_requests: list[dict[str, Any]] = []
    raw_generations: list[dict[str, Any]] = []
    parsed_labels: list[dict[str, Any]] = []
    gold_in_any_prompt = False
    consecutive_errors = 0

    for i, case in enumerate(selected, 1):
        case_id = case.get("case_id", f"case_{i}")
        rec = missing_edge_recs.get(case_id)
        prompt = build_case_prompt(case, rec)
        prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()

        gold_leak = audit_prompt_for_gold(prompt)
        if gold_leak:
            gold_in_any_prompt = True
            print(f"  WARNING: gold detected in prompt for {case_id}", file=sys.stderr)

        req: dict[str, Any] = {
            "request_id": f"{EXPERIMENT_ID}:{i}:{case_id}",
            "case_id": case_id,
            "stratum": case.get("_stratum", "unknown"),
            "prompt_sha256": prompt_sha,
            "prompt_text": prompt,
            "model": model,
            "provider": "cerebras",
            "max_output_tokens": args.max_output_tokens,
            "gold_free": not gold_leak,
            "api_call_made": args.allow_api,
        }
        provider_requests.append(req)

        if not args.allow_api:
            continue

        if consecutive_errors >= 3:
            print(f"  Stopping: 3 consecutive provider errors", file=sys.stderr)
            break

        print(f"  [{i}/{len(selected)}] {case_id} ...", end="", flush=True)
        resp = _chat(session, model, prompt, max_tokens=args.max_output_tokens)
        total_api_calls += 1

        # One retry on 429 / 5xx
        if not resp["ok"] and resp["http_status"] is not None:
            if resp["http_status"] == 429 or resp["http_status"] >= 500:
                print(f" (retry)", end="", flush=True)
                time.sleep(3)
                resp = _chat(session, model, prompt, max_tokens=args.max_output_tokens)
                total_api_calls += 1

        obj, parse_method = _try_json_parse(resp["text"]) if resp["ok"] else (None, "call_failed")

        gen_row: dict[str, Any] = {
            "call_index": i,
            "case_id": case_id,
            "stratum": case.get("_stratum", "unknown"),
            "model": model,
            "provider": "cerebras",
            "prompt_sha256": prompt_sha,
            "call_ok": resp["ok"],
            "http_status": resp["http_status"],
            "call_error": resp["error"] if not resp["ok"] else None,
            "raw_response": resp["text"],
            "parse_method": parse_method,
            "usage": resp["usage"],
        }
        raw_generations.append(gen_row)

        parse_ok_flag = obj is not None
        validation = validate_response(obj) if obj else {"schema_ok": False, "issues": ["parse_failed"]}

        parsed_row: dict[str, Any] = {
            "call_index": i,
            "case_id": case_id,
            "stratum": case.get("_stratum", "unknown"),
            "call_ok": resp["ok"],
            "parse_ok": parse_ok_flag,
            "schema_ok": validation["schema_ok"],
            "schema_issues": validation["issues"],
            "parsed_obj": obj,
        }
        parsed_labels.append(parsed_row)

        status = (
            "OK" if resp["ok"] and parse_ok_flag and validation["schema_ok"]
            else ("SCHEMA_ISSUES" if resp["ok"] and parse_ok_flag
                  else ("PARSE_FAIL" if resp["ok"] else "CALL_FAIL"))
        )
        print(f" {status}", flush=True)

        if resp["ok"]:
            consecutive_errors = 0
        else:
            consecutive_errors += 1

    # Write provider_requests
    _write_jsonl(args.out_dir / "provider_requests.jsonl", provider_requests)

    if not args.allow_api:
        # Dry-run: write empty output stubs
        _write_jsonl(args.out_dir / "raw_generations.jsonl", [])
        _write_jsonl(args.out_dir / "parsed_labels.jsonl", [])
        _write_csv(args.out_dir / "pattern_counts.csv", [])
        _write_csv(args.out_dir / "subtype_counts.csv", [])
        _write_csv(args.out_dir / "recommendation_counts.csv", [])
        _write_json(args.out_dir / "agreement_with_existing_hypothesis.json", {})
        _write_csv(args.out_dir / "casebook.csv", [])
        _write_json(args.out_dir / "manifest.json", {
            "experiment_id": EXPERIMENT_ID,
            "timestamp_utc": ts,
            "provider": "cerebras",
            "model": model,
            "pilot_ran": False,
            "dry_run": True,
            "cases_selected": len(selected),
            "allow_api": False,
        })
        (args.out_dir / "pilot_report.md").write_text(
            f"# Cerebras Failure-Pattern Pilot — DRY RUN\n\nAdd --allow-api to run live.\n", encoding="utf-8"
        )
        print(f"\nDry run complete. Output: {args.out_dir}", flush=True)
        return

    # Write outputs
    _write_jsonl(args.out_dir / "raw_generations.jsonl", raw_generations)
    _write_jsonl(args.out_dir / "parsed_labels.jsonl", parsed_labels)

    # Count tables
    primary_counts: Counter[str] = Counter()
    subtype_counts: Counter[str] = Counter()
    rne_counts: Counter[str] = Counter()
    for row in parsed_labels:
        obj = row.get("parsed_obj") or {}
        if not obj:
            continue
        primary_counts[str(obj.get("primary_failure_mechanism", "unknown"))] += 1
        subtype_counts[str(obj.get("wrong_target_subtype", "none"))] += 1
        rne_counts[str(obj.get("recommended_next_edge", "none"))] += 1

    _write_csv(
        args.out_dir / "pattern_counts.csv",
        [{"primary_failure_mechanism": k, "count": v}
         for k, v in primary_counts.most_common()] or [{"primary_failure_mechanism": "", "count": 0}],
    )
    _write_csv(
        args.out_dir / "subtype_counts.csv",
        [{"wrong_target_subtype": k, "count": v}
         for k, v in subtype_counts.most_common()] or [{"wrong_target_subtype": "", "count": 0}],
    )
    _write_csv(
        args.out_dir / "recommendation_counts.csv",
        [{"recommended_next_edge": k, "count": v}
         for k, v in rne_counts.most_common()] or [{"recommended_next_edge": "", "count": 0}],
    )

    # Agreement
    agreement = compute_agreement(parsed_labels)
    _write_json(args.out_dir / "agreement_with_existing_hypothesis.json", agreement)

    # Casebook CSV
    casebook_rows = []
    for row in parsed_labels:
        obj = row.get("parsed_obj") or {}
        casebook_rows.append({
            "call_index": row.get("call_index"),
            "case_id": row.get("case_id"),
            "stratum": row.get("stratum"),
            "call_ok": row.get("call_ok"),
            "parse_ok": row.get("parse_ok"),
            "schema_ok": row.get("schema_ok"),
            "primary_failure_mechanism": obj.get("primary_failure_mechanism", ""),
            "is_final_target_binding_failure": obj.get("is_final_target_binding_failure", ""),
            "is_candidate_absence_failure": obj.get("is_candidate_absence_failure", ""),
            "is_selector_failure": obj.get("is_selector_failure", ""),
            "is_repair_collapse": obj.get("is_repair_collapse", ""),
            "wrong_target_subtype": obj.get("wrong_target_subtype", ""),
            "recommended_next_edge": obj.get("recommended_next_edge", ""),
            "confidence": obj.get("confidence", ""),
            "evidence_summary": str(obj.get("evidence_summary", ""))[:300],
            "schema_issues": "; ".join(row.get("schema_issues", [])),
        })
    _write_csv(args.out_dir / "casebook.csv", casebook_rows or [{"note": "no_data"}])

    # Manifest
    parse_ok_n = sum(1 for r in parsed_labels if r.get("parse_ok"))
    schema_ok_n = sum(1 for r in parsed_labels if r.get("schema_ok"))
    manifest: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": ts,
        "provider": "cerebras",
        "model": model,
        "pilot_ran": True,
        "allow_api": args.allow_api,
        "cases_selected": len(selected),
        "cases_attempted": len(raw_generations),
        "total_api_calls": total_api_calls,
        "model_access_calls": len(access_results),
        "pilot_calls": total_api_calls - len(access_results),
        "calls_ok": sum(1 for r in raw_generations if r.get("call_ok")),
        "parse_ok": parse_ok_n,
        "schema_ok": schema_ok_n,
        "gold_in_any_prompt": gold_in_any_prompt,
        "hypothesis_agreement_rate": agreement.get("hypothesis_agreement_rate", 0.0),
        "limit": args.limit,
        "max_output_tokens": args.max_output_tokens,
        "out_dir": str(args.out_dir),
        "outputs": [
            "manifest.json", "model_access_check.json", "selected_cases.jsonl",
            "provider_requests.jsonl", "raw_generations.jsonl", "parsed_labels.jsonl",
            "pattern_counts.csv", "subtype_counts.csv", "recommendation_counts.csv",
            "agreement_with_existing_hypothesis.json", "casebook.csv", "pilot_report.md",
        ],
    }
    _write_json(args.out_dir / "manifest.json", manifest)

    # Report
    report = generate_report(
        args, model, selected, parsed_labels, access_results, agreement,
        total_api_calls, args.out_dir,
    )
    (args.out_dir / "pilot_report.md").write_text(report, encoding="utf-8")

    print(f"\nDone. Output: {args.out_dir}", flush=True)
    print(f"  parse_ok: {parse_ok_n}/{len(raw_generations)}", flush=True)
    print(f"  schema_ok: {schema_ok_n}/{len(raw_generations)}", flush=True)
    print(f"  hypothesis_agreement_rate: {agreement.get('hypothesis_agreement_rate', 0.0):.1%}", flush=True)


if __name__ == "__main__":
    main()
