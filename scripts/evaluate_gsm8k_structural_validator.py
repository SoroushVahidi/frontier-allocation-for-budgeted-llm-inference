#!/usr/bin/env python3
"""Offline batch evaluation for GSM8K structural validator (no API, no controllers).

Reads archived CSV/JSONL only. Gold/correctness labels are applied *after* validation.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

from experiments.gsm8k_structural_validate import validate_gsm8k_candidate
from experiments.output_layer_repair import canonicalize_answer
from experiments.selector_error_features import build_structural_target_feature_row

DATASET = "openai/gsm8k"
PAL_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"

DEFAULT_BUNDLE = (
    REPO_ROOT / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z"
)
DEFAULT_OUT = REPO_ROOT / "outputs/gsm8k_structural_validator_eval_20260507"
DEFAULT_PRIMARY_FAILURE_CSV = (
    REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
)
DEFAULT_FOCUS_GOLD_ABSENT_CSV = (
    REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
)
DEFAULT_SECONDARY_ANCHOR_CSV = (
    REPO_ROOT / "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_20260510.csv"
)
DEFAULT_GUARDRAIL_30_JSONL = (
    REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/failure_recovery_30case_exact_cases_20260510.jsonl"
)
DEFAULT_DIAGNOSTIC_15_JSONL = (
    REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl"
)
DEFAULT_TARGET_AUDIT_DIAGNOSTIC_JSONL = (
    REPO_ROOT / "docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl"
)

# casebook column -> (role label, answer column, correct column)
EXTERNAL_SPECS: tuple[tuple[str, str, str], ...] = (
    ("external_l1_max", "external_l1_max_answer", "external_l1_max_correct"),
    (
        "external_tale",
        "external_tale_prompt_budgeting_answer",
        "external_tale_prompt_budgeting_correct",
    ),
    (
        "external_s1",
        "external_s1_budget_forcing_answer",
        "external_s1_budget_forcing_correct",
    ),
)

# Roles sharing PAL tree execution context for fair PN comparison (exclude externals).
PAL_INTERNAL_ROLES = frozenset(
    {"current_final", "pal_stdout", "overlay_tiebreak", "direct_reserve"}
)
PAL_INTERNAL_OTHER_SOURCES = frozenset({"overlay_previous", "pal_json_answer"})


def evidence_class_for_spec(spec: dict[str, Any]) -> str:
    """Offline stratification only — how much trace/code was passed into the validator."""
    tr = str(spec.get("trace") or "").strip()
    cd = str(spec.get("code") or "").strip()
    if tr and cd:
        return "pal_trace_code"
    if tr and not cd:
        return "text_trace"
    if not tr and not cd:
        return "answer_only"
    # Code without trace (unusual for GSM8K PAL wiring)
    return "unknown"


def score_family_for_evidence(evidence_class: str) -> str:
    if evidence_class in {"pal_trace_code", "text_trace"}:
        return "structural_trace_score"
    if evidence_class == "answer_only":
        return "answer_only_diagnostic"
    return "unknown"


def matches_gold_offline_column(value: Any) -> bool:
    """Parse CSV/boolean `matches_gold_offline` field."""
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"true", "1"}


def row_matches_gold_row(r: dict[str, Any]) -> bool:
    return matches_gold_offline_column(r.get("matches_gold_offline"))


def _safe_json(raw: str | None) -> dict[str, Any]:
    if not raw or not str(raw).strip():
        return {}
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return out if isinstance(out, dict) else {}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _norm_match(ans: str | None, gold: str | None) -> bool:
    if ans is None or gold is None:
        return False
    ca = canonicalize_answer(str(ans).strip(), dataset=DATASET)
    cg = canonicalize_answer(str(gold).strip(), dataset=DATASET)
    return bool(ca is not None and cg is not None and ca == cg)


def _trace_from_nodes(final_nodes: Any) -> str:
    if not isinstance(final_nodes, list):
        return ""
    parts: list[str] = []
    for n in final_nodes:
        if not isinstance(n, dict):
            continue
        rt = str(n.get("reasoning_text") or "").strip()
        if rt:
            parts.append(rt)
    return "\n".join(parts)[:120_000]


def _exec_meta_from_pal_execution(px: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in ("pal_exec_ok", "pal_parse_ok", "pal_safety_ok"):
        if k in px:
            out[k] = px[k]
    er = px.get("pal_execution_result")
    if isinstance(er, dict):
        for k in ("pal_exec_ok", "pal_parse_ok", "pal_safety_ok"):
            if k in er:
                out[k] = er[k]
    return out


def _pal_answer_from_method_record(mr: dict[str, Any]) -> str:
    for k in (
        "selected_answer_raw",
        "controller_final_answer_raw",
        "final_answer_raw",
        "repair_answer_raw",
    ):
        v = mr.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _external_answer_from_method_record(mr: dict[str, Any]) -> str:
    return _pal_answer_from_method_record(mr)


def load_pal_all_results(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("method") != PAL_METHOD:
                continue
            cid = str(d.get("case_id") or d.get("example_id") or "").strip()
            if cid:
                out[cid] = d
    return out


def load_failure_cluster_map(path: Path) -> dict[str, str]:
    m: dict[str, str] = {}
    if not path.is_file():
        return m
    with path.open(encoding="utf-8", newline="") as fp:
        r = csv.DictReader(fp)
        for row in r:
            cid = str(row.get("case_id") or "").strip()
            ft = str(row.get("failure_type") or "").strip()
            if cid:
                m[cid] = ft
    return m


def load_selected_failures(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = str(d.get("case_id") or "").strip()
            if cid:
                out[cid] = d
    return out


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
    return rows


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict):
                rows.append(d)
    return rows


def load_case_id_set_from_csv(path: Path, *, case_id_col: str = "case_id", predicate: Any | None = None) -> set[str]:
    out: set[str] = set()
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if predicate is not None and not predicate(row):
                continue
            cid = str(row.get(case_id_col) or "").strip()
            if cid:
                out.add(cid)
    return out


def load_case_map_from_csv(path: Path, *, case_id_col: str = "case_id", predicate: Any | None = None) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if predicate is not None and not predicate(row):
                continue
            cid = str(row.get(case_id_col) or "").strip()
            if cid and cid not in out:
                out[cid] = {str(k): str(v) if v is not None else "" for k, v in row.items()}
    return out


def load_case_id_set_from_jsonl(
    path: Path,
    *,
    case_id_keys: tuple[str, ...] = ("case_id", "example_id"),
    predicate: Any | None = None,
) -> set[str]:
    out: set[str] = set()
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if predicate is not None and not predicate(row):
                continue
            cid = ""
            for key in case_id_keys:
                cid = str(row.get(key) or "").strip()
                if cid:
                    break
            if cid:
                out.add(cid)
    return out


def _normalize_group_key(answer: str | None) -> str:
    if answer is None:
        return ""
    stripped = str(answer).strip()
    if not stripped:
        return ""
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", stripped.replace(",", ""))
    if nums:
        value = nums[-1]
        if value.endswith(".0"):
            value = value[:-2]
        return value
    return stripped.lower()


def guardrail_case_ids(casebook_rows: list[dict[str, str]]) -> set[str]:
    s: set[str] = set()
    for row in casebook_rows:
        if row.get("pal_correct") == "1" and row.get("best_external_correct") == "1":
            cid = row.get("case_id", "")
            if cid:
                s.add(cid)
    return s


def row_is_pal_internal_pool(row: dict[str, Any]) -> bool:
    """True if row compares PAL/tree-internal candidates only (not externals)."""
    role = str(row.get("candidate_role") or "")
    sf = str(row.get("source_family") or "")
    if role in PAL_INTERNAL_ROLES:
        return True
    if role == "other" and sf in PAL_INTERNAL_OTHER_SOURCES:
        return True
    return False


def assign_cohort(
    cid: str,
    *,
    replay_ids: set[str],
    ft_map: dict[str, str],
    guardrail_ids: set[str],
) -> str:
    if cid in replay_ids:
        return "present_not_selected"
    if ft_map.get(cid) == "gold_absent_discovery":
        return "gold_absent_discovery"
    if cid in guardrail_ids:
        return "guardrail_correct"
    return "other"


def build_candidate_specs(
    *,
    cohort: str,
    case_id: str,
    question: str,
    gold: str,
    replay_row: dict[str, str] | None,
    pal_row: dict[str, Any] | None,
    casebook_row: dict[str, str] | None,
    selected_failure: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    missing: list[str] = []
    specs: list[dict[str, Any]] = []

    trace_pal = ""
    code = ""
    px: dict[str, Any] = {}
    overlay: dict[str, Any] = {}

    if pal_row:
        trace_pal = _trace_from_nodes(pal_row.get("final_nodes"))
        px = dict(pal_row.get("pal_execution") or {})
        code = str(px.get("pal_code") or "").strip()
        rm = pal_row.get("result_metadata_full")
        if isinstance(rm, dict) and not code:
            code = str(rm.get("pal_code") or "").strip()
    else:
        missing.append("pal_all_results_row_missing")

    if replay_row:
        px = _safe_json(replay_row.get("pal_execution_summary_json")) or px
        overlay = _safe_json(replay_row.get("pal_overlay_json"))
        code = str(px.get("pal_code") or code or "").strip()

    er = px.get("pal_execution_result") if isinstance(px.get("pal_execution_result"), dict) else {}
    stdout_ans = str(er.get("pal_answer_normalized") or er.get("pal_answer_raw") or "").strip()
    pal_json_ans = str(px.get("pal_json_answer") or "").strip()
    pal_cand = str(px.get("pal_candidate_answer") or "").strip()

    method_records: dict[str, Any] = {}
    if selected_failure and isinstance(selected_failure.get("method_records"), dict):
        method_records = selected_failure["method_records"]
    pal_mr = method_records.get(PAL_METHOD) if method_records else None
    if isinstance(pal_mr, dict):
        if not trace_pal:
            fn = pal_mr.get("final_nodes")
            trace_pal = _trace_from_nodes(fn)
        if not code:
            pe = pal_mr.get("pal_execution")
            if isinstance(pe, dict):
                code = str(pe.get("pal_code") or "").strip()

    def push(
        role: str,
        answer: str | None,
        *,
        trace: str | None,
        cand_code: str | None,
        exec_meta: dict[str, Any] | None,
        source_family: str,
    ) -> None:
        if answer is None or not str(answer).strip():
            return
        specs.append(
            {
                "case_id": case_id,
                "cohort": cohort,
                "candidate_role": role,
                "candidate_answer": str(answer).strip(),
                "problem_text": question,
                "trace": trace or "",
                "code": cand_code or "",
                "execution_metadata": exec_meta,
                "source_family": source_family,
            }
        )

    em_pal = _exec_meta_from_pal_execution(px)

    # --- Tree-internal answers share PAL trace+code ---
    pal_channels = (trace_pal, code, em_pal)

    if replay_row:
        push(
            "current_final",
            replay_row.get("pal_final_answer_raw"),
            trace=pal_channels[0],
            cand_code=pal_channels[1],
            exec_meta=pal_channels[2],
            source_family="replay_pal_final",
        )
        push(
            "direct_reserve",
            replay_row.get("direct_reserve_answer_raw"),
            trace=pal_channels[0],
            cand_code=pal_channels[1],
            exec_meta=pal_channels[2],
            source_family="replay_direct_reserve",
        )
        tb = str(replay_row.get("frontier_tiebreak_selected_group") or "").strip()
        if tb:
            push(
                "overlay_tiebreak",
                tb,
                trace=pal_channels[0],
                cand_code=pal_channels[1],
                exec_meta=pal_channels[2],
                source_family="replay_frontier_tiebreak",
            )
        ov_prev = str(overlay.get("pal_overlay_previous_answer") or "").strip()
        if ov_prev:
            push(
                "other",
                ov_prev,
                trace=pal_channels[0],
                cand_code=pal_channels[1],
                exec_meta=pal_channels[2],
                source_family="overlay_previous",
            )

    if isinstance(pal_mr, dict):
        push(
            "current_final",
            _pal_answer_from_method_record(pal_mr),
            trace=pal_channels[0],
            cand_code=pal_channels[1],
            exec_meta=pal_channels[2],
            source_family="selected_failure_pal",
        )

    if pal_row and not replay_row:
        pred = pal_row.get("predicted_answer")
        if pred is None:
            pred = pal_row.get("raw_final_output")
        push(
            "current_final",
            str(pred).strip() if pred is not None else None,
            trace=pal_channels[0],
            cand_code=pal_channels[1],
            exec_meta=pal_channels[2],
            source_family="all_results_pal",
        )

    # PAL stdout / execution path
    exec_ans = stdout_ans or pal_cand
    if exec_ans:
        push(
            "pal_stdout",
            exec_ans,
            trace=pal_channels[0],
            cand_code=pal_channels[1],
            exec_meta=pal_channels[2],
            source_family="pal_execution_stdout",
        )
    if pal_json_ans and pal_json_ans != exec_ans:
        push(
            "other",
            pal_json_ans,
            trace=pal_channels[0],
            cand_code=pal_channels[1],
            exec_meta=pal_channels[2],
            source_family="pal_json_answer",
        )

    # Externals from selected_failure JSON (no gold used to choose)
    ext_name_map = {
        "external_l1_max": "external_l1_max",
        "external_tale_prompt_budgeting": "external_tale_prompt_budgeting",
        "external_s1_budget_forcing": "external_s1_budget_forcing",
    }
    for _key, mr in method_records.items():
        if _key == PAL_METHOD or not isinstance(mr, dict):
            continue
        short = ext_name_map.get(_key, _key)
        ans = _external_answer_from_method_record(mr)
        if ans:
            push(
                "external_answer",
                ans,
                trace=None,
                cand_code=None,
                exec_meta=None,
                source_family=short,
            )

    if casebook_row:
        for label, ans_col, corr_col in EXTERNAL_SPECS:
            ans = casebook_row.get(ans_col) or ""
            if not str(ans).strip():
                continue
            if casebook_row.get(corr_col) != "1":
                continue
            push(
                "external_answer",
                str(ans).strip(),
                trace=None,
                cand_code=None,
                exec_meta=None,
                source_family=f"casebook_{label}",
            )

    # Dedupe identical (role, answer, source_family)
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for s in specs:
        key = (s["candidate_role"], s["candidate_answer"], s["source_family"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)

    # One row per candidate_role (prefer richer replay / execution labels)
    priority = (
        "replay_pal_final",
        "replay_direct_reserve",
        "replay_frontier_tiebreak",
        "pal_execution_stdout",
        "selected_failure_pal",
        "all_results_pal",
        "external_l1_max",
        "external_tale_prompt_budgeting",
        "external_s1_budget_forcing",
    )

    def source_rank(sf: str) -> int:
        try:
            return priority.index(sf)
        except ValueError:
            return len(priority) + 1

    by_role: dict[str, dict[str, Any]] = {}
    for s in deduped:
        role = s["candidate_role"]
        cur = by_role.get(role)
        if cur is None or source_rank(s["source_family"]) < source_rank(cur["source_family"]):
            by_role[role] = s
    # external_answer and other may repeat per source_family — keep all distinct answers
    collapsed: list[dict[str, Any]] = []
    for s in deduped:
        role = s["candidate_role"]
        if role in {"external_answer", "other"}:
            collapsed.append(s)
            continue
        if by_role.get(role) is s:
            collapsed.append(s)
    deduped = collapsed

    if not question.strip():
        missing.append("empty_question")
    if not trace_pal.strip():
        missing.append("empty_trace")
    if not code.strip():
        missing.append("empty_pal_code")

    return deduped, missing


def flatten_validation(
    spec: dict[str, Any],
    v: dict[str, Any],
    *,
    gold: str,
    missing_case: list[str],
    evidence_class: str,
    score_family: str,
) -> dict[str, Any]:
    flags = list(missing_case)
    ans = spec.get("candidate_answer")
    target_tuple = v.get("target_tuple") or {}
    ledger_proxy = v.get("entity_unit_ledger_proxy") or {}
    return {
        "case_id": spec["case_id"],
        "cohort": spec["cohort"],
        "source_family": spec.get("source_family"),
        "candidate_role": spec["candidate_role"],
        "evidence_class": evidence_class,
        "score_family": score_family,
        "candidate_answer": ans,
        "matches_gold_offline": _norm_match(str(ans) if ans is not None else None, gold),
        "structural_score": v.get("structural_score"),
        "target_tuple": json.dumps(target_tuple, sort_keys=True),
        "entity_unit_ledger_proxy": json.dumps(ledger_proxy, sort_keys=True),
        "final_answer_role": v.get("final_answer_role"),
        "last_operation_family": v.get("last_operation_family"),
        "target_alignment_score": v.get("target_alignment_score"),
        "intermediate_answer_penalty": v.get("intermediate_answer_penalty"),
        "duplicate_wrong_signature": v.get("duplicate_wrong_signature"),
        "structural_selector_score": v.get("structural_selector_score"),
        "errors_count": len(v.get("errors") or []),
        "warnings_count": len(v.get("warnings") or []),
        "quantity_coverage": v.get("quantity_coverage"),
        "operation_cues_required": json.dumps(v.get("operation_cues_required") or []),
        "operation_cues_found": json.dumps(v.get("operation_cues_found") or []),
        "target_question_type": v.get("target_question_type"),
        "target_type_match": v.get("target_type_match"),
        "code_syntax_ok": v.get("code_syntax_ok"),
        "exec_ok": v.get("exec_ok"),
        "abstain_reasons": json.dumps(v.get("abstain_reasons") or []),
        "unused_salient_quantities_count": len(v.get("unused_salient_quantities") or []),
        "missing_metadata_flags": json.dumps(flags),
    }


def _replay_case_group_key(answer: str | None) -> str:
    return _normalize_group_key(answer)


def _group_candidate_pool(
    *,
    question: str,
    candidate_pool: list[dict[str, Any]],
    pal_code: str | None,
    pal_execution: dict[str, Any] | None,
    answer_group_support_counts: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    support_counts = dict(answer_group_support_counts or {})
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for idx, cand in enumerate(candidate_pool):
        if not isinstance(cand, dict):
            continue
        group_key = _replay_case_group_key(cand.get("normalized_answer") or cand.get("predicted_answer"))
        if not group_key:
            continue
        grouped[group_key].append(dict(cand))

    per_group: list[dict[str, Any]] = []
    for group_key, rows in grouped.items():
        feats: list[dict[str, Any]] = []
        candidate_rows: list[dict[str, Any]] = []
        for row in rows:
            trace = str(row.get("trace") or row.get("reasoning_text") or "")
            candidate_answer = row.get("predicted_answer") or row.get("normalized_answer")
            candidate_code = pal_code
            exec_meta = {
                "candidate_role": row.get("candidate_role"),
                "reasoning_role": row.get("reasoning_role"),
                "source_family": row.get("source_family"),
                "source_metadata": row.get("source_metadata"),
                "answer_group": group_key,
                "target_entity": row.get("target_entity"),
                "target_unit": row.get("target_unit"),
                "unit_consistency_status": row.get("unit_consistency_status"),
            }
            feats.append(
                build_structural_target_feature_row(
                    question=question,
                    candidate_trace=trace,
                    candidate_code=candidate_code,
                    candidate_answer=candidate_answer,
                    execution_metadata=exec_meta,
                    support_count=int(support_counts.get(group_key, len(rows)) or len(rows)),
                )
            )
            candidate_row = dict(row)
            candidate_row["group_key"] = group_key
            candidate_row["support_count"] = int(support_counts.get(group_key, len(rows)) or len(rows))
            candidate_row["structural_features"] = feats[-1]
            candidate_rows.append(candidate_row)
        duplicate_counts: Counter[str] = Counter(
            feat["duplicate_wrong_signature"]
            for feat in feats
            if feat.get("duplicate_wrong_signature") and feat.get("final_answer_role") != "target"
        )
        best_feat = max(
            feats,
            key=lambda f: (
                float(f.get("structural_selector_score", 0.0)),
                float(f.get("target_alignment_score", 0.0)),
                -float(f.get("intermediate_answer_penalty", 0.0)),
            ),
        )
        group_row = {
            "group_key": group_key,
            "support_count": int(support_counts.get(group_key, len(rows)) or len(rows)),
            "candidate_count": len(rows),
            "frontier_support_count": 0,
            "direct_support_count": 0,
            "best_structural_selector_score": float(best_feat.get("structural_selector_score", 0.0)),
            "best_target_alignment_score": float(best_feat.get("target_alignment_score", 0.0)),
            "best_intermediate_answer_penalty": float(best_feat.get("intermediate_answer_penalty", 0.0)),
            "best_ledger_confidence": float(
                (best_feat.get("entity_unit_ledger_proxy") or {}).get("ledger_confidence", 0.0)
            ),
            "best_final_answer_role": str(best_feat.get("final_answer_role") or "unknown"),
            "best_last_operation_family": str(best_feat.get("last_operation_family") or "unknown"),
            "duplicate_wrong_penalty": float(max(0, max(duplicate_counts.values(), default=0) - 1)),
            "duplicate_wrong_signature_count": int(max(duplicate_counts.values(), default=0)),
            "features": feats,
            "candidate_rows": candidate_rows,
            "candidate_answers": [str(r.get("predicted_answer") or r.get("normalized_answer") or "").strip() for r in rows],
        }
        per_group.append(group_row)

    return per_group, {"group_count": len(per_group)}


def _baseline_selector_group(
    *,
    selected_group: str | None,
    answer_group_support_counts: dict[str, Any] | None,
    frontier_answer_group_counts: dict[str, Any] | None,
    direct_answer_group_counts: dict[str, Any] | None,
) -> str:
    baseline = _replay_case_group_key(selected_group)
    if baseline:
        return baseline
    support_counts = dict(answer_group_support_counts or {})
    frontier_counts = dict(frontier_answer_group_counts or {})
    direct_counts = dict(direct_answer_group_counts or {})
    if not support_counts:
        return ""
    try:
        max_support = max(int(v) for v in support_counts.values())
    except Exception:
        return ""
    tied = sorted(
        [
            str(g).strip()
            for g, c in support_counts.items()
            if str(g).strip() and str(g) != "__unknown__" and int(c) == int(max_support)
        ]
    )
    if not tied:
        return ""
    if len(tied) == 1:
        return tied[0]

    def _fc(g: str) -> int:
        try:
            return int(frontier_counts.get(g, 0) or 0)
        except Exception:
            return 0

    def _dc(g: str) -> int:
        try:
            return int(direct_counts.get(g, 0) or 0)
        except Exception:
            return 0

    ranked = sorted(tied, key=lambda g: (-_fc(g), _dc(g), g))
    return ranked[0] if ranked else tied[0]


def _variant_group_score(variant: str, group_row: dict[str, Any]) -> float:
    support = float(group_row.get("support_count", 0) or 0)
    target = float(group_row.get("best_target_alignment_score", 0.0) or 0.0)
    intermediate = float(group_row.get("best_intermediate_answer_penalty", 0.0) or 0.0)
    ledger = float(group_row.get("best_ledger_confidence", 0.0) or 0.0)
    duplicate_penalty = float(group_row.get("duplicate_wrong_penalty", 0.0) or 0.0)
    structural = float(group_row.get("best_structural_selector_score", 0.0) or 0.0)
    frontier = float(group_row.get("frontier_support_count", 0) or 0)
    direct = float(group_row.get("direct_support_count", 0) or 0)

    if variant == "baseline_current_selector_tiebreak":
        return support
    if variant == "+ target check":
        return support + 0.75 * target
    if variant == "+ anti-intermediate filter":
        return support + 0.75 * target - 0.85 * intermediate
    if variant == "+ unit/entity ledger proxy":
        return support + 0.75 * target - 0.85 * intermediate + 0.60 * ledger
    if variant == "+ wrong-consensus penalty":
        return support + 0.75 * target - 0.85 * intermediate + 0.60 * ledger - 0.50 * duplicate_penalty
    if variant == "combined_structural_selector":
        return 0.30 * support + 0.55 * structural + 0.15 * ledger - 0.35 * duplicate_penalty
    return support + frontier * 1e-3 - direct * 1e-6


def _variant_sort_key(variant_score: float, group_row: dict[str, Any]) -> tuple[float, float, float, float, str]:
    return (
        -float(variant_score),
        -float(group_row.get("support_count", 0) or 0),
        -float(group_row.get("frontier_support_count", 0) or 0),
        float(group_row.get("direct_support_count", 0) or 0),
        str(group_row.get("group_key") or ""),
    )


def _select_group_for_variant(
    *,
    variant: str,
    candidate_pool: list[dict[str, Any]],
    question: str,
    selected_group: str | None,
    answer_group_support_counts: dict[str, Any] | None,
    frontier_answer_group_counts: dict[str, Any] | None,
    direct_answer_group_counts: dict[str, Any] | None,
    pal_code: str | None,
    pal_execution: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    grouped, meta = _group_candidate_pool(
        question=question,
        candidate_pool=candidate_pool,
        pal_code=pal_code,
        pal_execution=pal_execution,
        answer_group_support_counts=answer_group_support_counts,
    )
    if not grouped:
        return "", {"missing_candidate_pool": True, **meta}
    frontier_counts = dict(frontier_answer_group_counts or {})
    direct_counts = dict(direct_answer_group_counts or {})
    for row in grouped:
        row["frontier_support_count"] = int(frontier_counts.get(row["group_key"], 0) or 0)
        row["direct_support_count"] = int(direct_counts.get(row["group_key"], 0) or 0)
    baseline_group = _baseline_selector_group(
        selected_group=selected_group,
        answer_group_support_counts=answer_group_support_counts,
        frontier_answer_group_counts=frontier_answer_group_counts,
        direct_answer_group_counts=direct_answer_group_counts,
    )
    if variant == "baseline_current_selector_tiebreak":
        return baseline_group, {"baseline_group": baseline_group, "group_count": len(grouped), **meta}
    ranked = sorted(
        grouped,
        key=lambda row: _variant_sort_key(_variant_group_score(variant, row), row),
    )
    chosen = ranked[0] if ranked else {}
    return str(chosen.get("group_key") or baseline_group or ""), {
        "baseline_group": baseline_group,
        "group_count": len(grouped),
        "ranked_group_keys": [str(r.get("group_key") or "") for r in ranked[:10]],
        **meta,
    }


def _selected_answer_for_group(
    group_key: str,
    *,
    candidate_pool: list[dict[str, Any]],
    fallback_answer: str | None = None,
) -> str:
    g = _replay_case_group_key(group_key)
    if not g:
        return fallback_answer or ""
    for row in candidate_pool:
        ans = str(row.get("predicted_answer") or row.get("normalized_answer") or "").strip()
        if not ans:
            continue
        if _replay_case_group_key(ans) == g:
            return ans
    return fallback_answer or g


def _load_slice_case_map(path: Path, *, kind: str) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    if path.suffix.lower() == ".jsonl":
        rows = load_jsonl_rows(path)
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            cid = str(row.get("case_id") or row.get("example_id") or "").strip()
            if cid:
                out[cid] = dict(row)
        return out
    rows = load_csv_rows(path)
    out = {}
    for row in rows:
        cid = str(row.get("case_id") or row.get("example_id") or "").strip()
        if cid:
            out[cid] = dict(row)
    return out


def _build_replay_case_records(
    *,
    bundle: Path,
    primary_slice_csv: Path,
    focus_slice_csv: Path,
    secondary_slice_csv: Path,
    guardrail_jsonl: Path,
    diagnostic_jsonl: Path,
    target_audit_jsonl: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pal_by_case = load_pal_all_results(bundle / "all_results.jsonl")
    replay_csv_rows = load_csv_rows(bundle / "present_not_selected_replay_table.csv")
    replay_by_case = {r["case_id"]: r for r in replay_csv_rows if r.get("case_id")}
    selected_by_case = load_selected_failures(bundle / "selected_failure_cases.jsonl")
    casebook_by_case = {r["case_id"]: r for r in load_csv_rows(bundle / "all_casebook.csv") if r.get("case_id")}

    primary_ids = load_case_id_set_from_csv(
        primary_slice_csv,
        predicate=lambda r: str(r.get("method_id") or "") == PAL_METHOD
        and str(r.get("evidence_completeness") or "").upper() == "FULL",
    )
    focus_ids = load_case_id_set_from_csv(
        focus_slice_csv,
        predicate=lambda r: str(r.get("external_contrast") or "") == "Both wrong",
    )
    secondary_ids = load_case_id_set_from_csv(
        secondary_slice_csv,
        predicate=lambda r: str(r.get("anchor_matches_l1_max") or "").lower() in {"1", "true", "yes"}
        or str(r.get("external_l1_exact") or "").lower() in {"1", "true", "yes"},
    )
    guardrail_ids = load_case_id_set_from_jsonl(guardrail_jsonl)
    diagnostic_ids = load_case_id_set_from_jsonl(diagnostic_jsonl)
    target_audit_rows = load_jsonl_rows(target_audit_jsonl)
    target_audit_stats = {
        "n_cases": len(target_audit_rows),
        "n_gold_present": sum(1 for row in target_audit_rows if str(row.get("gold_answer") or "").strip()),
        "n_selected_present": sum(1 for row in target_audit_rows if str(row.get("selected_answer") or "").strip()),
        "case_ids": sorted(
            {
                str(row.get("case_id") or "").strip()
                for row in target_audit_rows
                if str(row.get("case_id") or "").strip()
            }
        ),
    }

    slices = {
        "primary_pal_full_failure_slice": primary_ids,
        "focus_wrong_supported_consensus_slice": focus_ids,
        "secondary_direct_l1_anchor_slice": secondary_ids,
        "guardrail_30case_exact_replay": guardrail_ids,
        "diagnostic_15case_direct_l1_strong_seed": diagnostic_ids,
    }

    all_case_ids: list[str] = []
    seen: set[str] = set()
    for case_ids in slices.values():
        for cid in sorted(case_ids):
            if cid and cid not in seen:
                seen.add(cid)
                all_case_ids.append(cid)

    case_records: list[dict[str, Any]] = []
    slice_stats: dict[str, dict[str, Any]] = {}

    for slice_name, case_ids in slices.items():
        replay_ready = 0
        missing_candidate_pools = 0
        missing_gold = 0
        missing_question = 0
        missing_support_counts = 0
        for cid in sorted(case_ids):
            pal_row = pal_by_case.get(cid)
            replay_row = replay_by_case.get(cid)
            casebook_row = casebook_by_case.get(cid)
            selected_failure = selected_by_case.get(cid)
            question = ""
            gold = ""
            if replay_row:
                question = str(replay_row.get("question") or "")
                gold = str(replay_row.get("gold_answer_raw") or replay_row.get("gold_answer") or "")
            elif casebook_row:
                question = str(casebook_row.get("question") or "")
                gold = str(casebook_row.get("gold_answer") or "")
            elif selected_failure:
                question = str(selected_failure.get("question") or "")
                gold = str(selected_failure.get("gold_answer") or "")
            elif pal_row:
                question = str(pal_row.get("question") or "")
                gold = str(pal_row.get("gold_answer") or "")

            if not gold.strip():
                missing_gold += 1
            if not question.strip():
                missing_question += 1

            candidate_pool = list(pal_row.get("selector_candidate_pool") or []) if pal_row else []
            if not candidate_pool:
                missing_candidate_pools += 1
            if not pal_row or not isinstance(pal_row.get("answer_group_support_counts"), dict):
                missing_support_counts += 1
            if pal_row and candidate_pool and question.strip():
                replay_ready += 1
            case_records.append(
                {
                    "slice_name": slice_name,
                    "case_id": cid,
                    "in_replay_bundle": int(cid in pal_by_case),
                    "has_candidate_pool": int(bool(candidate_pool)),
                    "has_gold": int(bool(gold.strip())),
                    "has_question": int(bool(question.strip())),
                    "has_support_counts": int(bool(pal_row and isinstance(pal_row.get("answer_group_support_counts"), dict))),
                    "selected_failure_loaded": int(selected_failure is not None),
                    "bundle_case_id": int(cid in pal_by_case),
                    "bundle_selected_group": _safe_text((replay_row or {}).get("selected_group") or (pal_row or {}).get("selected_group")),
                    "bundle_predicted_answer": _safe_text((replay_row or {}).get("pal_final_answer_raw") or (pal_row or {}).get("predicted_answer") or (pal_row or {}).get("raw_final_output")),
                    "missing_reason": "|".join(
                        [
                            flag
                            for flag, enabled in (
                                ("missing_candidate_pool", not bool(candidate_pool)),
                                ("missing_gold", not bool(gold.strip())),
                                ("missing_question", not bool(question.strip())),
                                ("missing_support_counts", not bool(pal_row and isinstance(pal_row.get("answer_group_support_counts"), dict))),
                            )
                            if enabled
                        ]
                    ),
                }
            )
        slice_stats[slice_name] = {
            "n_cases": len(case_ids),
            "n_replay_ready": replay_ready,
            "n_missing_candidate_pool": missing_candidate_pools,
            "n_missing_gold": missing_gold,
            "n_missing_question": missing_question,
            "n_missing_support_counts": missing_support_counts,
        }

    return case_records, {
        "slices": slice_stats,
        "primary_ids": sorted(primary_ids),
        "focus_ids": sorted(focus_ids),
        "secondary_ids": sorted(secondary_ids),
        "guardrail_ids": sorted(guardrail_ids),
        "diagnostic_ids": sorted(diagnostic_ids),
        "target_audit_reference": target_audit_stats,
    }


def run_structural_target_replay(
    *,
    bundle: Path,
    out_dir: Path,
    primary_slice_csv: Path,
    focus_slice_csv: Path,
    secondary_slice_csv: Path,
    guardrail_jsonl: Path,
    diagnostic_jsonl: Path,
    target_audit_jsonl: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    case_records, slice_index = _build_replay_case_records(
        bundle=bundle,
        primary_slice_csv=primary_slice_csv,
        focus_slice_csv=focus_slice_csv,
        secondary_slice_csv=secondary_slice_csv,
        guardrail_jsonl=guardrail_jsonl,
        diagnostic_jsonl=diagnostic_jsonl,
        target_audit_jsonl=target_audit_jsonl,
    )

    pal_by_case = load_pal_all_results(bundle / "all_results.jsonl")
    replay_by_case = {r["case_id"]: r for r in load_csv_rows(bundle / "present_not_selected_replay_table.csv") if r.get("case_id")}

    rows: list[dict[str, Any]] = []
    candidate_feature_rows: list[dict[str, Any]] = []
    missing_reason_hist: Counter[str] = Counter()
    variant_case_counts: Counter[str] = Counter()
    slice_variant_summary: dict[str, dict[str, Any]] = defaultdict(dict)
    variants = [
        "baseline_current_selector_tiebreak",
        "+ target check",
        "+ anti-intermediate filter",
        "+ unit/entity ledger proxy",
        "+ wrong-consensus penalty",
        "combined_structural_selector",
    ]

    for rec in case_records:
        cid = rec["case_id"]
        slice_name = rec["slice_name"]
        pal_row = pal_by_case.get(cid)
        replay_row = replay_by_case.get(cid, {})
        candidate_pool = list(pal_row.get("selector_candidate_pool") or []) if pal_row else []
        missing_reason_hist.update([x for x in str(rec.get("missing_reason") or "").split("|") if x])
        if not pal_row or not candidate_pool:
            continue
        question = str((replay_row or {}).get("question") or pal_row.get("question") or "")
        gold = str((replay_row or {}).get("gold_answer_raw") or pal_row.get("gold_answer") or "")
        answer_support_counts = pal_row.get("answer_group_support_counts") if isinstance(pal_row.get("answer_group_support_counts"), dict) else {}
        frontier_counts = pal_row.get("frontier_answer_group_counts") if isinstance(pal_row.get("frontier_answer_group_counts"), dict) else {}
        direct_counts = pal_row.get("direct_answer_group_counts") if isinstance(pal_row.get("direct_answer_group_counts"), dict) else {}
        selected_group = _safe_text((replay_row or {}).get("selected_group") or pal_row.get("selected_group") or pal_row.get("predicted_answer"))
        pal_code = _safe_text((pal_row.get("pal_execution") or {}).get("pal_code"))
        pal_execution = dict(pal_row.get("pal_execution") or {})
        grouped_candidates, _ = _group_candidate_pool(
            question=question,
            candidate_pool=candidate_pool,
            pal_code=pal_code,
            pal_execution=pal_execution,
            answer_group_support_counts=answer_support_counts,
        )
        for group_row in grouped_candidates:
            for cand_row in group_row.get("candidate_rows") or []:
                cand_feat = dict(cand_row.get("structural_features") or {})
                cand_feat.update(
                    {
                        "slice_name": slice_name,
                        "case_id": cid,
                        "group_key": group_row.get("group_key") or "",
                        "candidate_answer": cand_row.get("predicted_answer") or cand_row.get("normalized_answer") or "",
                        "source_family": cand_row.get("source_family") or "",
                        "candidate_role": cand_row.get("candidate_role") or "",
                        "support_count": cand_row.get("support_count") or 0,
                        "candidate_pool_size": len(candidate_pool),
                    }
                )
                candidate_feature_rows.append(cand_feat)

        gold_group = _replay_case_group_key(gold)
        baseline_group = _baseline_selector_group(
            selected_group=selected_group,
            answer_group_support_counts=answer_support_counts,
            frontier_answer_group_counts=frontier_counts,
            direct_answer_group_counts=direct_counts,
        )

        for variant in variants:
            selected_variant_group, variant_meta = _select_group_for_variant(
                variant=variant,
                candidate_pool=candidate_pool,
                question=question,
                selected_group=selected_group,
                answer_group_support_counts=answer_support_counts,
                frontier_answer_group_counts=frontier_counts,
                direct_answer_group_counts=direct_counts,
                pal_code=pal_code,
                pal_execution=pal_execution,
            )
            chosen_answer = _selected_answer_for_group(
                selected_variant_group,
                candidate_pool=candidate_pool,
                fallback_answer=_safe_text(pal_row.get("predicted_answer") or pal_row.get("raw_final_output") or ""),
            )
            exact = _norm_match(chosen_answer, gold)
            rows.append(
                {
                    "slice_name": slice_name,
                    "case_id": cid,
                    "variant": variant,
                    "baseline_group": baseline_group,
                    "selected_group": selected_variant_group,
                    "selected_answer": chosen_answer,
                    "gold_answer": gold,
                    "gold_group": gold_group,
                    "matches_gold": int(exact),
                    "candidate_pool_size": len(candidate_pool),
                    "candidate_group_count": int(variant_meta.get("group_count", 0) or 0),
                    "missing_candidate_pool": int(not bool(candidate_pool)),
                    "missing_reason": rec.get("missing_reason") or "",
                    "ranked_group_keys": "|".join(variant_meta.get("ranked_group_keys") or []),
                }
            )
            variant_case_counts[variant] += 1

        slice_variant_summary[slice_name]["n_cases"] = slice_variant_summary[slice_name].get("n_cases", 0) + 1

    def _mean(xs: list[float]) -> float:
        return sum(xs) / max(len(xs), 1)

    summary_by_slice: dict[str, dict[str, Any]] = defaultdict(dict)
    for slice_name in sorted({r["slice_name"] for r in rows} | set(slice_index["slices"].keys())):
        slice_rows = [r for r in rows if r["slice_name"] == slice_name]
        summary_by_slice[slice_name]["n_replay_cases"] = len({r["case_id"] for r in slice_rows})
        summary_by_slice[slice_name]["n_result_rows"] = len(slice_rows)
        summary_by_slice[slice_name]["slice_label_stats"] = slice_index["slices"].get(slice_name, {})
        for variant in variants:
            vrows = [r for r in slice_rows if r["variant"] == variant]
            if not vrows:
                summary_by_slice[slice_name][variant] = {"accuracy": None, "n": 0}
                continue
            acc = sum(int(r["matches_gold"]) for r in vrows) / max(len(vrows), 1)
            summary_by_slice[slice_name][variant] = {
                "accuracy": acc,
                "n": len(vrows),
                "selected_group_examples": [r["selected_group"] for r in vrows[:5]],
            }

    primary_slice_name = "primary_pal_full_failure_slice"
    baseline_acc = summary_by_slice.get(primary_slice_name, {}).get("baseline_current_selector_tiebreak", {}).get("accuracy")
    combined_acc = summary_by_slice.get(primary_slice_name, {}).get("combined_structural_selector", {}).get("accuracy")
    variant_delta_summary: dict[str, dict[str, Any]] = defaultdict(dict)
    for slice_name in sorted({r["slice_name"] for r in rows} | set(slice_index["slices"].keys())):
        slice_rows = [r for r in rows if r["slice_name"] == slice_name]
        baseline_by_case = {
            r["case_id"]: r for r in slice_rows if r["variant"] == "baseline_current_selector_tiebreak"
        }
        n_cases = int(slice_index["slices"].get(slice_name, {}).get("n_cases", len({r["case_id"] for r in slice_rows})) or 0)
        for variant in variants[1:]:
            variant_by_case = {r["case_id"]: r for r in slice_rows if r["variant"] == variant}
            compared = sorted(set(baseline_by_case) & set(variant_by_case))
            fixes = 0
            regressions = 0
            for cid in compared:
                base = baseline_by_case[cid]
                cur = variant_by_case[cid]
                if int(cur["matches_gold"]) > int(base["matches_gold"]):
                    fixes += 1
                elif int(cur["matches_gold"]) < int(base["matches_gold"]):
                    regressions += 1
            variant_delta_summary[slice_name][variant] = {
                "fixes": fixes,
                "regressions": regressions,
                "unknowns": max(0, n_cases - len(compared)),
                "n_compared": len(compared),
            }
    improvements = 0
    regressions = 0
    unknowns = 0
    for cid in {r["case_id"] for r in rows if r["slice_name"] == primary_slice_name}:
        case_rows = [r for r in rows if r["slice_name"] == primary_slice_name and r["case_id"] == cid]
        if not case_rows:
            continue
        base = next((r for r in case_rows if r["variant"] == "baseline_current_selector_tiebreak"), None)
        combo = next((r for r in case_rows if r["variant"] == "combined_structural_selector"), None)
        if not base or not combo:
            unknowns += 1
            continue
        if int(combo["matches_gold"]) > int(base["matches_gold"]):
            improvements += 1
        elif int(combo["matches_gold"]) < int(base["matches_gold"]):
            regressions += 1

    json_summary = {
        "bundle": str(bundle),
        "output_dir": str(out_dir),
        "primary_slice_csv": str(primary_slice_csv),
        "focus_slice_csv": str(focus_slice_csv),
        "secondary_slice_csv": str(secondary_slice_csv),
        "guardrail_jsonl": str(guardrail_jsonl),
        "diagnostic_jsonl": str(diagnostic_jsonl),
        "slice_index": slice_index,
        "summary_by_slice": summary_by_slice,
        "variant_delta_summary": variant_delta_summary,
        "primary_improvements_vs_baseline": improvements,
        "primary_regressions_vs_baseline": regressions,
        "primary_unknowns_vs_baseline": unknowns,
        "missing_reason_hist": dict(missing_reason_hist),
        "variant_case_counts": dict(variant_case_counts),
        "replay_rows": rows,
        "candidate_feature_rows": candidate_feature_rows,
        "claim_boundary": {
            "safe": [
                "The replay compares deterministic structural selector variants on archived candidate pools only.",
                "No API calls were made.",
                "The current bundle does not cover every primary/focus slice case, so missing metadata is reported explicitly.",
            ],
            "unsafe": [
                "Do not claim the structural selector beats external_l1_max.",
                "Do not claim the focus wrong-supported-consensus slice is fully replayed unless the candidate pool is present.",
            ],
        },
    }

    (out_dir / "replay_summary.json").write_text(json.dumps(json_summary, indent=2), encoding="utf-8")

    report_lines = [
        "# PAL frontier structural-target replay v1",
        "",
        "Offline deterministic replay only. No API calls were made.",
        "",
        "## Coverage",
        "",
        f"- Primary slice cases: **{slice_index['slices']['primary_pal_full_failure_slice']['n_cases']}** (doc target: 157 PAL still-failing covered cases)",
        f"- Primary replay-ready cases in current bundle: **{slice_index['slices']['primary_pal_full_failure_slice']['n_replay_ready']}**",
        f"- Focus slice cases: **{slice_index['slices']['focus_wrong_supported_consensus_slice']['n_cases']}** (doc target: 97 wrong-supported-consensus cases)",
        f"- Focus replay-ready cases in current bundle: **{slice_index['slices']['focus_wrong_supported_consensus_slice']['n_replay_ready']}**",
        f"- Secondary slice cases: **{slice_index['slices']['secondary_direct_l1_anchor_slice']['n_cases']}** (doc target: 43 direct-L1-anchor-potential cases)",
        f"- Secondary replay-ready cases in current bundle: **{slice_index['slices']['secondary_direct_l1_anchor_slice']['n_replay_ready']}**",
        f"- Guardrail 30-case exact slice: **{slice_index['slices']['guardrail_30case_exact_replay']['n_cases']}**",
        f"- Direct L1 strong-seed 15-case diagnostic: **{slice_index['slices']['diagnostic_15case_direct_l1_strong_seed']['n_cases']}**",
        f"- Target-audit 18-case diagnostic reference: **{slice_index['target_audit_reference']['n_cases']}**",
        f"- Candidate feature rows emitted: **{len(candidate_feature_rows)}**",
        "",
        "## Current bundle gap",
        "",
        f"- Missing candidate pool rows on primary slice: **{slice_index['slices']['primary_pal_full_failure_slice']['n_missing_candidate_pool']}**",
        f"- Missing candidate pool rows on focus slice: **{slice_index['slices']['focus_wrong_supported_consensus_slice']['n_missing_candidate_pool']}**",
        f"- Missing candidate pool rows on secondary slice: **{slice_index['slices']['secondary_direct_l1_anchor_slice']['n_missing_candidate_pool']}**",
        "",
        "## Variant accuracies on replay-ready cases",
        "",
    ]
    for slice_name, stats in summary_by_slice.items():
        report_lines.append(f"### {slice_name}")
        report_lines.append("")
        report_lines.append(f"- Replay cases: **{stats.get('n_replay_cases', 0)}**")
        report_lines.append(f"- Result rows: **{stats.get('n_result_rows', 0)}**")
        report_lines.append(f"- Label coverage: `{json.dumps(stats.get('slice_label_stats', {}), sort_keys=True)}`")
        for variant in variants:
            v = stats.get(variant, {})
            report_lines.append(
                f"- {variant}: accuracy={v.get('accuracy') if v.get('accuracy') is not None else 'NA'} n={v.get('n', 0)}"
            )
            if variant != "baseline_current_selector_tiebreak":
                delta = variant_delta_summary.get(slice_name, {}).get(variant, {})
                report_lines.append(
                    f"  - delta vs baseline: fixes={delta.get('fixes', 0)} regressions={delta.get('regressions', 0)} unknowns={delta.get('unknowns', 0)}"
                )
        report_lines.append("")

    report_lines.extend(
        [
            "## Primary-slice deltas",
            "",
            f"- Baseline accuracy: **{baseline_acc if baseline_acc is not None else 'NA'}**",
            f"- Combined structural selector accuracy: **{combined_acc if combined_acc is not None else 'NA'}**",
            f"- Improvements vs baseline: **{improvements}**",
            f"- Regressions vs baseline: **{regressions}**",
            f"- Unknown / missing baseline-compare rows: **{unknowns}**",
            "",
            "## Variant delta summary",
            "",
            "```json",
            json.dumps({k: dict(v) for k, v in variant_delta_summary.items()}, indent=2),
            "```",
            "",
            "## Missing metadata",
            "",
            "```json",
            json.dumps(dict(missing_reason_hist), indent=2),
            "```",
            "",
            "## Safe claim wording",
            "",
            "- This is a deterministic offline replay on archived candidate pools.",
            "- Structural target and ledger heuristics were computed without gold labels.",
            "- Current bundle coverage is incomplete for the focus slice, so focus-slice claims should stay provisional.",
            "",
            "## Unsafe wording",
            "",
            "- Do not say the structural selector is proven superior to external_l1_max.",
            "- Do not say the 97-case wrong-supported-consensus bucket is fully solved.",
            "- Do not move runtime defaults on the basis of this replay alone.",
        ]
    )
    (out_dir / "replay_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    if rows:
        with (out_dir / "replay_rows.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    if candidate_feature_rows:
        with (out_dir / "candidate_feature_rows.jsonl").open("w", encoding="utf-8") as f:
            for row in candidate_feature_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with (out_dir / "candidate_feature_rows.csv").open("w", encoding="utf-8", newline="") as f:
            fieldnames = list(candidate_feature_rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in candidate_feature_rows:
                writer.writerow(row)

    return json_summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--replay-selector-ablation",
        action="store_true",
        help="Run the offline structural-target selector replay instead of the validator-only batch report.",
    )
    ap.add_argument("--primary-slice-csv", type=Path, default=DEFAULT_PRIMARY_FAILURE_CSV)
    ap.add_argument("--focus-slice-csv", type=Path, default=DEFAULT_FOCUS_GOLD_ABSENT_CSV)
    ap.add_argument("--secondary-slice-csv", type=Path, default=DEFAULT_SECONDARY_ANCHOR_CSV)
    ap.add_argument("--guardrail-30-jsonl", type=Path, default=DEFAULT_GUARDRAIL_30_JSONL)
    ap.add_argument("--diagnostic-15-jsonl", type=Path, default=DEFAULT_DIAGNOSTIC_15_JSONL)
    ap.add_argument("--target-audit-jsonl", type=Path, default=DEFAULT_TARGET_AUDIT_DIAGNOSTIC_JSONL)
    args = ap.parse_args()
    bundle: Path = args.bundle_dir.resolve()
    out_dir: Path = args.out_dir.resolve()
    if args.replay_selector_ablation and out_dir == DEFAULT_OUT:
        out_dir = out_dir / f"pal_frontier_structural_target_replay_v1_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.replay_selector_ablation:
        summary = run_structural_target_replay(
            bundle=bundle,
            out_dir=out_dir,
            primary_slice_csv=args.primary_slice_csv,
            focus_slice_csv=args.focus_slice_csv,
            secondary_slice_csv=args.secondary_slice_csv,
            guardrail_jsonl=args.guardrail_30_jsonl,
            diagnostic_jsonl=args.diagnostic_15_jsonl,
            target_audit_jsonl=args.target_audit_jsonl,
        )
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"output_dir": str(out_dir), "primary_replay_cases": summary["slice_index"]["slices"]["primary_pal_full_failure_slice"]["n_replay_ready"]}, indent=2))
        return

    missing_inputs: list[str] = []
    paths = {
        "replay_csv": bundle / "present_not_selected_replay_table.csv",
        "failure_cluster": bundle / "failure_cluster_summary.csv",
        "all_results": bundle / "all_results.jsonl",
        "casebook": bundle / "all_casebook.csv",
        "selected_failures": bundle / "selected_failure_cases.jsonl",
    }
    for _label, pth in paths.items():
        if not pth.is_file():
            missing_inputs.append(str(pth))

    pal_by_case = load_pal_all_results(paths["all_results"])
    ft_map = load_failure_cluster_map(paths["failure_cluster"])
    replay_rows = load_csv_rows(paths["replay_csv"])
    replay_by_id = {r["case_id"]: r for r in replay_rows if r.get("case_id")}
    replay_ids = set(replay_by_id.keys())

    casebook_rows = load_csv_rows(paths["casebook"])
    casebook_by_id = {r["case_id"]: r for r in casebook_rows if r.get("case_id")}
    guard_ids = guardrail_case_ids(casebook_rows)

    selected_by_case = load_selected_failures(paths["selected_failures"])

    case_ids: list[str] = []
    seen: set[str] = set()

    def add(cid: str) -> None:
        if cid and cid not in seen:
            seen.add(cid)
            case_ids.append(cid)

    for r in replay_rows:
        add(r.get("case_id", ""))
    for cid in ft_map:
        add(cid)
    for cid in guard_ids:
        add(cid)

    output_rows: list[dict[str, Any]] = []
    warn_hist: Counter[str] = Counter()
    warn_hist_by_evidence_class: dict[str, Counter[str]] = defaultdict(Counter)
    gold_absent_warns: Counter[str] = Counter()

    for cid in case_ids:
        cohort = assign_cohort(cid, replay_ids=replay_ids, ft_map=ft_map, guardrail_ids=guard_ids)
        replay_row = replay_by_id.get(cid)
        pal_row = pal_by_case.get(cid)
        cb_row = casebook_by_id.get(cid)
        sf_row = selected_by_case.get(cid)

        if replay_row:
            gold = replay_row.get("gold_answer_raw") or ""
            question = replay_row.get("question") or ""
        elif cb_row:
            gold = cb_row.get("gold_answer") or ""
            question = cb_row.get("question") or ""
        elif sf_row:
            gold = str(sf_row.get("gold_answer") or "")
            question = str(sf_row.get("question") or "")
        elif pal_row:
            gold = str(pal_row.get("gold_answer") or "")
            question = str(pal_row.get("question") or "")
        else:
            continue

        specs, miss = build_candidate_specs(
            cohort=cohort,
            case_id=cid,
            question=question,
            gold=gold,
            replay_row=replay_row,
            pal_row=pal_row,
            casebook_row=cb_row,
            selected_failure=sf_row,
        )

        for spec in specs:
            ec = evidence_class_for_spec(spec)
            sfamily = score_family_for_evidence(ec)
            try:
                v = validate_gsm8k_candidate(
                    problem_text=spec["problem_text"],
                    candidate_answer=spec["candidate_answer"],
                    candidate_trace=spec.get("trace") or None,
                    candidate_code=spec.get("code") or None,
                    source_family=spec.get("source_family"),
                    execution_metadata=spec.get("execution_metadata"),
                )
            except Exception as exc:  # noqa: BLE001
                v = {
                    "errors": [f"batch_wrapped:{type(exc).__name__}"],
                    "warnings": [],
                    "quantity_coverage": None,
                    "operation_cues_required": [],
                    "operation_cues_found": [],
                    "target_question_type": "unknown",
                    "target_type_match": None,
                    "code_syntax_ok": None,
                    "exec_ok": None,
                    "structural_score": 0.0,
                    "abstain_reasons": ["batch_exception"],
                    "unused_salient_quantities": [],
                }
            for w in v.get("warnings") or []:
                warn_hist[str(w)] += 1
                warn_hist_by_evidence_class[ec][str(w)] += 1
            if (
                spec["cohort"] == "gold_absent_discovery"
                and spec["candidate_role"] in {"current_final", "pal_stdout"}
            ):
                for w in v.get("warnings") or []:
                    gold_absent_warns[str(w)] += 1
            output_rows.append(
                flatten_validation(
                    spec,
                    v,
                    gold=gold,
                    missing_case=miss,
                    evidence_class=ec,
                    score_family=sfamily,
                )
            )

    def score_val(r: dict[str, Any]) -> float | None:
        s = r.get("structural_score")
        if isinstance(s, (int, float)):
            return float(s)
        return None

    gold_scores = [score_val(r) for r in output_rows if row_matches_gold_row(r)]
    gold_scores = [x for x in gold_scores if x is not None]
    nongold_scores = [score_val(r) for r in output_rows if not row_matches_gold_row(r)]
    nongold_scores = [x for x in nongold_scores if x is not None]

    # By cohort
    cohort_gold: dict[str, list[float]] = defaultdict(list)
    cohort_nongold: dict[str, list[float]] = defaultdict(list)
    for r in output_rows:
        c = str(r.get("cohort") or "other")
        sv = score_val(r)
        if sv is None:
            continue
        if row_matches_gold_row(r):
            cohort_gold[c].append(sv)
        else:
            cohort_nongold[c].append(sv)

    def avg(xs: list[float]) -> float:
        return sum(xs) / max(len(xs), 1)

    separation_by_cohort = {}
    for c in set(cohort_gold.keys()) | set(cohort_nongold.keys()):
        separation_by_cohort[c] = {
            "mean_gold_matching": avg(cohort_gold.get(c, [])),
            "n_gold_rows": len(cohort_gold.get(c, [])),
            "mean_non_gold": avg(cohort_nongold.get(c, [])),
            "n_non_gold_rows": len(cohort_nongold.get(c, [])),
        }

    # --- Stratified metrics (no mixed-evidence headline) ---
    ec_gold: dict[str, list[float]] = defaultdict(list)
    ec_nongold: dict[str, list[float]] = defaultdict(list)
    role_ec_counts: Counter[tuple[str, str]] = Counter()
    score_family_counts: Counter[str] = Counter()

    for r in output_rows:
        ec = str(r.get("evidence_class") or "unknown")
        sfam = str(r.get("score_family") or "unknown")
        score_family_counts[sfam] += 1
        role_ec_counts[(str(r.get("candidate_role")), ec)] += 1
        sv = score_val(r)
        if sv is None:
            continue
        if row_matches_gold_row(r):
            ec_gold[ec].append(sv)
        else:
            ec_nongold[ec].append(sv)

    stratified_means_by_evidence_class: dict[str, dict[str, Any]] = {}
    for ec in sorted(set(ec_gold.keys()) | set(ec_nongold.keys())):
        stratified_means_by_evidence_class[ec] = {
            "mean_structural_score_gold_matching_rows": avg(ec_gold.get(ec, [])),
            "n_gold_matching_rows": len(ec_gold.get(ec, [])),
            "mean_structural_score_non_gold_rows": avg(ec_nongold.get(ec, [])),
            "n_non_gold_rows": len(ec_nongold.get(ec, [])),
        }

    evidence_class_counts_by_candidate_role: dict[str, dict[str, int]] = defaultdict(dict)
    for (role, ec), n in role_ec_counts.items():
        evidence_class_counts_by_candidate_role[role][ec] = n

    pn_cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in output_rows:
        if r.get("cohort") == "present_not_selected":
            pn_cases[str(r.get("case_id"))].append(r)

    pn_improved = 0
    pn_total_compare = 0
    pn_tie = 0
    pn_missing = 0
    pn_mislead = 0

    helper_examples: list[dict[str, Any]] = []
    mislead_examples: list[dict[str, Any]] = []

    for cid, rows in pn_cases.items():
        finals = [x for x in rows if x.get("candidate_role") == "current_final"]
        if not finals:
            continue
        frow = finals[0]
        sf = score_val(frow)
        gold_alts = [x for x in rows if row_matches_gold_row(x)]
        if not gold_alts:
            pn_missing += 1
            continue
        best_gold = max((score_val(x) for x in gold_alts if score_val(x) is not None), default=None)
        if sf is None or best_gold is None:
            pn_missing += 1
            continue
        pn_total_compare += 1
        if best_gold > sf + 1e-9:
            pn_improved += 1
            helper_examples.append(
                {
                    "case_id": cid,
                    "wrong_final_score": sf,
                    "best_gold_score": best_gold,
                    "wrong_answer": frow.get("candidate_answer"),
                    "gold_alt_answers": list(
                        {str(x.get("candidate_answer")) for x in gold_alts}
                    ),
                }
            )
        elif abs(best_gold - sf) <= 1e-9:
            pn_tie += 1
        elif best_gold < sf - 1e-9:
            pn_mislead += 1
            mislead_examples.append(
                {
                    "case_id": cid,
                    "wrong_final_score": sf,
                    "best_gold_score": best_gold,
                    "wrong_answer": frow.get("candidate_answer"),
                }
            )

    pn_case_total = len(pn_cases)
    pn_with_gold_alt_in_pool = sum(
        1 for rows in pn_cases.values() if any(row_matches_gold_row(r) for r in rows)
    )

    # --- PAL-internal PN only (exclude external_answer etc.) ---
    pn_internal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in output_rows:
        if r.get("cohort") != "present_not_selected":
            continue
        if not row_is_pal_internal_pool(r):
            continue
        pn_internal[str(r.get("case_id"))].append(r)

    pin_improved = 0
    pin_compare = 0
    pin_tie = 0
    pin_missing = 0
    pin_mislead = 0
    pin_helper: list[dict[str, Any]] = []
    pin_mislead_ex: list[dict[str, Any]] = []
    pairwise_csv_rows: list[dict[str, Any]] = []

    for cid, rows in pn_internal.items():
        finals = [x for x in rows if x.get("candidate_role") == "current_final"]
        if not finals:
            continue
        frow = finals[0]
        wf = score_val(frow)
        gold_alts = [x for x in rows if row_matches_gold_row(x)]
        pool_n = len(rows)
        if not gold_alts:
            pin_missing += 1
            pairwise_csv_rows.append(
                {
                    "case_id": cid,
                    "wrong_current_final_answer": frow.get("candidate_answer"),
                    "wrong_current_final_score": wf,
                    "wrong_evidence_class": frow.get("evidence_class"),
                    "best_gold_internal_answer": "",
                    "best_gold_internal_role": "",
                    "best_gold_internal_source_family": "",
                    "best_gold_internal_score": "",
                    "best_gold_evidence_class": "",
                    "outcome": "missing_gold_internal_alt",
                    "n_internal_candidates": pool_n,
                }
            )
            continue
        best_alt = max(gold_alts, key=lambda x: score_val(x) if score_val(x) is not None else -1.0)
        bg = score_val(best_alt)
        if wf is None or bg is None:
            pin_missing += 1
            outcome = "missing_score"
        elif bg > wf + 1e-9:
            pin_improved += 1
            pin_compare += 1
            outcome = "gold_internal_higher_than_wrong_final"
            pin_helper.append(
                {
                    "case_id": cid,
                    "wrong_final_score": wf,
                    "best_gold_internal_score": bg,
                    "wrong_answer": frow.get("candidate_answer"),
                    "gold_internal_answer": best_alt.get("candidate_answer"),
                    "gold_internal_role": best_alt.get("candidate_role"),
                    "gold_internal_source_family": best_alt.get("source_family"),
                }
            )
        elif abs(bg - wf) <= 1e-9:
            pin_tie += 1
            pin_compare += 1
            outcome = "tie"
        else:
            pin_mislead += 1
            pin_compare += 1
            outcome = "misleading_wrong_final_higher"
            pin_mislead_ex.append(
                {
                    "case_id": cid,
                    "wrong_final_score": wf,
                    "best_gold_internal_score": bg,
                    "wrong_answer": frow.get("candidate_answer"),
                }
            )

        pairwise_csv_rows.append(
            {
                "case_id": cid,
                "wrong_current_final_answer": frow.get("candidate_answer"),
                "wrong_current_final_score": wf if wf is not None else "",
                "wrong_evidence_class": frow.get("evidence_class"),
                "best_gold_internal_answer": best_alt.get("candidate_answer"),
                "best_gold_internal_role": best_alt.get("candidate_role"),
                "best_gold_internal_source_family": best_alt.get("source_family"),
                "best_gold_internal_score": bg if bg is not None else "",
                "best_gold_evidence_class": best_alt.get("evidence_class"),
                "outcome": outcome,
                "n_internal_candidates": pool_n,
            }
        )

    guard_pal = [
        r
        for r in output_rows
        if r.get("cohort") == "guardrail_correct" and r.get("candidate_role") == "current_final"
    ]
    gr_warn_rate = (
        sum(1 for r in guard_pal if int(r.get("warnings_count") or 0) > 0) / max(len(guard_pal), 1)
    )

    guard_pal_trace_code = [
        r
        for r in output_rows
        if r.get("cohort") == "guardrail_correct"
        and r.get("candidate_role") == "current_final"
        and r.get("evidence_class") == "pal_trace_code"
    ]
    gr_tc_warn_rate = (
        sum(1 for r in guard_pal_trace_code if int(r.get("warnings_count") or 0) > 0)
        / max(len(guard_pal_trace_code), 1)
    )

    warn_top_by_evidence_class = {
        ec: warn_hist_by_evidence_class[ec].most_common(20)
        for ec in sorted(warn_hist_by_evidence_class.keys())
    }

    pn_with_int_gold = sum(
        1 for rs in pn_internal.values() if any(row_matches_gold_row(x) for x in rs)
    )

    stratified_summary = {
        "missing_input_paths": missing_inputs,
        "documentation": {
            "evidence_class": {
                "pal_trace_code": "non-empty trace and non-empty code passed to validator",
                "text_trace": "trace without code",
                "answer_only": "no trace and no code (typical external_answer)",
                "unknown": "code without trace or other edge wiring",
            },
            "score_family": {
                "structural_trace_score": "PAL/trace-channel structural_score rows",
                "answer_only_diagnostic": "answer-only rows — same validator call, interpret separately",
                "unknown": "edge evidence class",
            },
            "no_global_mixed_evidence_headline": True,
        },
        "candidate_rows_total": len(output_rows),
        "distinct_cases": len({r.get("case_id") for r in output_rows}),
        "score_family_row_counts": dict(score_family_counts),
        "evidence_class_counts_by_candidate_role": {
            role: dict(ecs) for role, ecs in evidence_class_counts_by_candidate_role.items()
        },
        "stratified_means_by_evidence_class": stratified_means_by_evidence_class,
        "present_not_selected_legacy_mixed_pool": {
            "cases_total": pn_case_total,
            "cases_with_any_gold_matching_candidate": pn_with_gold_alt_in_pool,
            "cases_compared_gold_alt_vs_wrong_final": pn_total_compare,
            "cases_gold_alt_higher_score_than_wrong_final": pn_improved,
            "cases_tie_score": pn_tie,
            "cases_missing_score_or_no_gold_alt_in_pool": pn_missing,
            "cases_wrong_final_scores_higher_than_best_gold_alt": pn_mislead,
            "note": "Includes external_answer — unfair vs PAL; use pal_internal block instead.",
        },
        "present_not_selected_pal_internal_only": {
            "cases_total": len(pn_internal),
            "cases_with_gold_matching_internal_alt": pn_with_int_gold,
            "cases_compared": pin_compare,
            "cases_gold_internal_higher_than_wrong_final": pin_improved,
            "cases_tie": pin_tie,
            "cases_missing_gold_internal_or_score": pin_missing,
            "cases_misleading_wrong_final_higher": pin_mislead,
            "example_helper": pin_helper[:10],
            "example_mislead": pin_mislead_ex[:10],
        },
        "guardrail_correct_current_final": {
            "rows_all_evidence_classes": len(guard_pal),
            "warning_rate_any_warning": gr_warn_rate,
            "rows_pal_trace_code_only": len(guard_pal_trace_code),
            "warning_rate_pal_trace_code_only": gr_tc_warn_rate,
        },
        "top_warnings_by_evidence_class": warn_top_by_evidence_class,
        "deprecated_legacy_global_means": {
            "avg_structural_score_gold_matching_all_rows": avg(gold_scores),
            "avg_structural_score_non_gold_all_rows": avg(nongold_scores),
            "warning": "Do not use for ranking — mixes pal_trace_code with answer_only.",
        },
    }

    summary = {
        "missing_input_paths": missing_inputs,
        "candidate_rows_total": len(output_rows),
        "distinct_cases": len({r.get("case_id") for r in output_rows}),
        "avg_structural_score_gold_matching": avg(gold_scores),
        "avg_structural_score_non_gold": avg(nongold_scores),
        "deprecated_note": "Global gold vs non-gold means mix evidence classes — see stratified_summary.json",
        "separation_by_cohort": separation_by_cohort,
        "present_not_selected": {
            "cases_total": pn_case_total,
            "cases_with_any_gold_matching_candidate": pn_with_gold_alt_in_pool,
            "cases_compared_gold_alt_vs_wrong_final": pn_total_compare,
            "cases_gold_alt_higher_score_than_wrong_final": pn_improved,
            "cases_tie_score": pn_tie,
            "cases_missing_score_or_no_gold_alt_in_pool": pn_missing,
            "cases_wrong_final_scores_higher_than_best_gold_alt": pn_mislead,
        },
        "guardrail_correct_pal_current_final_rows": len(guard_pal),
        "guardrail_warning_rate_any_warning": gr_warn_rate,
        "top_warning_patterns": warn_hist.most_common(25),
        "gold_absent_common_warnings_top": gold_absent_warns.most_common(15),
        "example_helper_cases": helper_examples[:8],
        "example_mislead_cases": mislead_examples[:8],
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "stratified_summary.json").write_text(
        json.dumps(stratified_summary, indent=2), encoding="utf-8"
    )

    if pairwise_csv_rows:
        pfield = list(pairwise_csv_rows[0].keys())
        with (out_dir / "pal_internal_pairwise.csv").open("w", encoding="utf-8", newline="") as pf:
            pw = csv.DictWriter(pf, fieldnames=pfield)
            pw.writeheader()
            for row in sorted(pairwise_csv_rows, key=lambda x: str(x.get("case_id"))):
                pw.writerow(row)

    pin_block = stratified_summary["present_not_selected_pal_internal_only"]
    grb = stratified_summary["guardrail_correct_current_final"]
    strat_report_lines = [
        "# Stratified GSM8K structural validator evaluation",
        "",
        "Offline batch only; **no** selection wiring; **no** API.",
        "",
        "## Evidence stratification",
        "",
        "- **`pal_trace_code`:** trace and code both non-empty in the batch spec passed to `validate_gsm8k_candidate`.",
        "- **`text_trace`:** trace without code.",
        "- **`answer_only`:** no trace and no code (typical `external_answer`).",
        "- **`score_family`:** `structural_trace_score` vs `answer_only_diagnostic` — same validator numeric field, **different interpretation**.",
        "",
        "**Do not** rank PAL rows against externals using one pooled scalar — see `deprecated_legacy_global_means` in `stratified_summary.json`.",
        "",
        "## Stratified gold vs non-gold means (within evidence class only)",
        "",
        "```json",
        json.dumps(stratified_summary["stratified_means_by_evidence_class"], indent=2),
        "```",
        "",
        "## PAL-internal present-not-selected (excludes `external_answer`)",
        "",
        f"- Cases with ≥1 internal gold alt: **{pin_block['cases_with_gold_matching_internal_alt']}**",
        f"- Comparable cases: **{pin_block['cases_compared']}**",
        f"- Gold internal scored higher than wrong `current_final`: **{pin_block['cases_gold_internal_higher_than_wrong_final']}**",
        f"- Ties: **{pin_block['cases_tie']}**",
        f"- Misleading (wrong final higher): **{pin_block['cases_misleading_wrong_final_higher']}**",
        f"- Missing internal gold or score: **{pin_block['cases_missing_gold_internal_or_score']}**",
        "",
        "## Guardrail `current_final` warning rates",
        "",
        f"- All evidence classes (**{grb['rows_all_evidence_classes']}** rows): **{grb['warning_rate_any_warning']:.3f}**",
        f"- **`pal_trace_code` only** (**{grb['rows_pal_trace_code_only']}** rows): **{grb['warning_rate_pal_trace_code_only']:.3f}**",
        "",
        "## Track signal (diagnostic)",
        "",
        "- **Track B:** Interpret **`pal_trace_code`** PN-internal deltas only; mixed evidence invalidated the first headline.",
        "- **Track A:** Warning tags on **`pal_trace_code`** guardrail rows remain a plausible retry signal; rate drops when restricting to trace+code.",
        "",
        "**API:** not used.",
    ]
    (out_dir / "stratified_report.md").write_text("\n".join(strat_report_lines), encoding="utf-8")

    jsonl_path = out_dir / "candidate_validation_rows.jsonl"
    csv_path = out_dir / "candidate_validation_rows.csv"
    with jsonl_path.open("w", encoding="utf-8") as jf:
        for row in output_rows:
            jf.write(json.dumps(row, ensure_ascii=False) + "\n")

    if output_rows:
        fieldnames = list(output_rows[0].keys())
        with csv_path.open("w", encoding="utf-8", newline="") as cf:
            w = csv.DictWriter(cf, fieldnames=fieldnames)
            w.writeheader()
            for row in output_rows:
                w.writerow(row)

    report_lines = [
        "# GSM8K structural validator — offline batch evaluation",
        "",
        "> **Prefer `stratified_report.md` + `stratified_summary.json`** for fair metrics. "
        "Global gold vs non-gold means below mix `pal_trace_code` with `answer_only` rows.",
        "",
        "Diagnostic run only; scores are **metadata** and do not prove downstream ranking quality.",
        "",
        f"- **Bundle:** `{bundle}`",
        f"- **Output:** `{out_dir}`",
        "",
        "## Missing inputs",
        "",
        "```json",
        json.dumps(missing_inputs, indent=2),
        "```",
        "",
        "## Scale",
        "",
        f"- Candidate rows: **{summary['candidate_rows_total']}**",
        f"- Distinct cases: **{summary['distinct_cases']}**",
        "",
        "## Global separation (gold-matching vs non-gold candidate rows)",
        "",
        f"- Mean structural_score (gold-matching): **{summary['avg_structural_score_gold_matching']:.4f}**",
        f"- Mean structural_score (non-gold): **{summary['avg_structural_score_non_gold']:.4f}**",
        "",
        "## Separation by cohort",
        "",
        "```json",
        json.dumps(separation_by_cohort, indent=2),
        "```",
        "",
        "## Present-not-selected",
        "",
        f"- Cases total (present_not_selected cohort): **{pn_case_total}**",
        f"- Cases with ≥1 gold-matching candidate in emitted pool: **{pn_with_gold_alt_in_pool}**",
        f"- Comparable (scores present for wrong `current_final` and some gold alt): **{pn_total_compare}**",
        f"- Cases where some gold-matching candidate scored higher than wrong final: **{pn_improved}**",
        f"- Tie scores: **{pn_tie}**",
        f"- Missing score / no gold alt in pool: **{pn_missing}**",
        f"- Wrong final scored strictly higher than best gold alt (misleading signal): **{pn_mislead}**",
        "",
        "### Example helper cases (validator ranks gold alternative above wrong final)",
        "",
        "```json",
        json.dumps(helper_examples[:6], indent=2),
        "```",
        "",
        "### Example misleading cases",
        "",
        "```json",
        json.dumps(mislead_examples[:6], indent=2),
        "```",
        "",
        "## Guardrail (PAL + best external correct)",
        "",
        f"- `current_final` rows counted: **{len(guard_pal)}**",
        f"- Fraction with ≥1 warning: **{gr_warn_rate:.3f}**",
        "",
        "## Top warning strings",
        "",
        "```json",
        json.dumps(summary["top_warning_patterns"], indent=2),
        "```",
        "",
        "## Gold-absent discovery — common warnings on current_final / pal_stdout",
        "",
        "```json",
        json.dumps(summary["gold_absent_common_warnings_top"], indent=2),
        "```",
        "",
        "## Track alignment (non-final judgment)",
        "",
        "- **Track B (commitment / overlay):** usable only if calibrated; separation above is necessary but not sufficient.",
        "- **Track A (discovery / retry):** warning clusters may seed triggers; watch guardrail false-positive rate.",
        "",
        "**API:** not used.",
    ]
    (out_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Wrote {len(output_rows)} rows to {out_dir} (see stratified_summary.json)")


if __name__ == "__main__":
    main()
