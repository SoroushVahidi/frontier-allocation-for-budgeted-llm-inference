#!/usr/bin/env python3
"""Offline batch evaluation for GSM8K structural validator (no API, no controllers).

Reads archived CSV/JSONL only. Gold/correctness labels are applied *after* validation.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

from experiments.gsm8k_structural_validate import validate_gsm8k_candidate
from experiments.output_layer_repair import canonicalize_answer

DATASET = "openai/gsm8k"
PAL_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"

DEFAULT_BUNDLE = (
    REPO_ROOT / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z"
)
DEFAULT_OUT = REPO_ROOT / "outputs/gsm8k_structural_validator_eval_20260507"

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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    bundle: Path = args.bundle_dir.resolve()
    out_dir: Path = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

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
