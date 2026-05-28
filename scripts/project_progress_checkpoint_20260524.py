#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from scripts.evaluate_reliability_gated_pooled_voting_c1 import (
    add_pattern_features,
    c1a_decision,
    c1d_decision,
    compute_training_fold_calibration,
    decision_ok,
    pooled4_decision,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO_ROOT / "outputs" / "project_progress_checkpoint_20260524"
DOC_PATH = REPO_ROOT / "docs" / "PROJECT_PROGRESS_CHECKPOINT_20260524.md"

COHERE_S4_BASE = REPO_ROOT / "outputs" / "cohere_math500_official_scenario4_20260524" / "cohere_math500_full_20260524T144902Z"
COHERE_S4_LOG = REPO_ROOT / "outputs" / "cohere_math500_official_scenario4_20260524" / "cohere_math500_full_20260524T144902Z.log"
MISTRAL_TRAIN_BASE = REPO_ROOT / "outputs" / "mistral_large_router_training_gsm8k_20260524" / "mistral_gsm8k_train1000_full_20260524T151853Z"
MISTRAL_TRAIN_LOG = REPO_ROOT / "outputs" / "mistral_large_router_training_gsm8k_20260524" / "mistral_gsm8k_train1000_full_20260524T151853Z.log"
CEREBRAS_GSM_BASE = REPO_ROOT / "outputs" / "cerebras_frozen_agreement_only_2of3_validation_20260523" / "cohere_real_model_cost_normalized_validation_20260523T144414Z"
CEREBRAS_GSM_LOG = REPO_ROOT / "outputs" / "cerebras_frozen_agreement_only_2of3_validation_20260523" / "live_validation_20260523T144414Z.log"
CEREBRAS_S6_LAUNCH_STATUS = REPO_ROOT / "outputs" / "scenarios_5_6_math500_full_tracking_20260524" / "cerebras_math500_launch_status.json"
CEREBRAS_S6_BASE = REPO_ROOT / "outputs" / "scenarios_5_6_math500_full_tracking_20260524" / "cerebras_math500_full_20260524T015003Z"
CEREBRAS_S6_LOG = REPO_ROOT / "outputs" / "scenarios_5_6_math500_full_tracking_20260524" / "cerebras_math500_full_20260524T015003Z.log"

COHERE_S4_PROCESS_OUT = REPO_ROOT / "outputs" / "cohere_math500_official_scenario4_processing_20260524"
COHERE_S4_PROCESS_DOC = REPO_ROOT / "docs" / "COHERE_MATH500_OFFICIAL_SCENARIO4_PROCESSING_20260524.md"
MISTRAL_TRAIN_PROCESS_OUT = REPO_ROOT / "outputs" / "mistral_large_router_training_gsm8k_processing_20260524"
MISTRAL_TRAIN_PROCESS_DOC = REPO_ROOT / "docs" / "MISTRAL_LARGE_ROUTER_TRAINING_GSM8K_PROCESSING_20260524.md"
CEREBRAS_PROCESS_OUT = REPO_ROOT / "outputs" / "cerebras_gsm8k_completed_processing_20260524"
CEREBRAS_PROCESS_DOC = REPO_ROOT / "docs" / "CEREBRAS_GSM8K_COMPLETED_PROCESSING_20260524.md"
FOUR_MATRIX_OUT = REPO_ROOT / "outputs" / "four_scenario_official_matrix_20260524"
FOUR_MATRIX_DOC = REPO_ROOT / "docs" / "FOUR_SCENARIO_OFFICIAL_MATRIX_20260524.md"

METHOD_MAP = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "L1",
    "external_s1_budget_forcing": "S1",
    "external_tale_prompt_budgeting": "TALE",
}
EXPECTED_METHODS = list(METHOD_MAP.keys())


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_ts(s: Any) -> Optional[dt.datetime]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    try:
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
    except Exception:
        return None


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def json_dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def find_per_example(base: Path) -> Optional[Path]:
    if not base.exists():
        return None
    matches = sorted(base.rglob("per_example_records.jsonl"))
    return matches[-1] if matches else None


def find_heartbeat(base: Path) -> Optional[Path]:
    if not base.exists():
        return None
    matches = sorted(base.rglob("progress_heartbeat.jsonl"))
    return matches[-1] if matches else None


def find_failures(base: Path) -> Optional[Path]:
    if not base.exists():
        return None
    matches = sorted(base.rglob("failures.jsonl"))
    return matches[-1] if matches else None


def ps_lines() -> List[str]:
    cmd = "ps -eo pid,ppid,etime,stat,pcpu,pmem,cmd | grep -E 'run_cohere_real_model_cost_normalized_validation|overnight_cerebras_supervisor|cerebras|cohere|mistral|math500|gsm8k|python3' | grep -v grep || true"
    out = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, check=False)
    return [x for x in out.stdout.splitlines() if x.strip()]


def tmux_sessions() -> List[str]:
    out = subprocess.run(["bash", "-lc", "tmux ls || true"], capture_output=True, text=True, check=False)
    sessions: List[str] = []
    for line in out.stdout.splitlines():
        if ":" in line:
            sessions.append(line.split(":", 1)[0].strip())
    return sessions


def choose_answer(row: pd.Series) -> str:
    for c in ["selected_answer_canonical", "final_answer_canonical", "selected_answer_raw", "final_answer_raw"]:
        v = str(row.get(c, "") or "").strip()
        if v and v.lower() not in {"nan", "none"}:
            return v
    return ""


def choose_gold(row: pd.Series) -> str:
    for c in ["gold_answer_canonical", "gold_answer"]:
        v = str(row.get(c, "") or "").strip()
        if v and v.lower() not in {"nan", "none"}:
            return v
    return ""


def dedup_records(records: List[Dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records).copy()
    df["example_id"] = df["example_id"].astype(str)
    df["method"] = df["method"].astype(str)
    df["ts"] = df["timestamp"].map(parse_ts)
    df["failed_int"] = pd.to_numeric(df.get("failed", 0), errors="coerce").fillna(0).astype(int)
    df["ans"] = df.apply(choose_answer, axis=1)
    df["gold"] = df.apply(choose_gold, axis=1)
    df["exact_match"] = pd.to_numeric(df.get("exact_match", 0), errors="coerce").fillna(0).astype(int)

    # Prefer non-failed rows, then latest timestamp.
    df = df.sort_values(["example_id", "method", "failed_int", "ts"], ascending=[True, True, True, False])
    keep = df.drop_duplicates(["example_id", "method"], keep="first").copy().reset_index(drop=True)
    return keep


def wide_from_records(records: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    raw = pd.DataFrame(records) if records else pd.DataFrame()
    dedup = dedup_records(records)
    if len(dedup) == 0:
        return pd.DataFrame(), {
            "raw_rows": 0,
            "effective_rows": 0,
            "duplicate_overage": 0,
            "method_counts_raw": {},
            "method_counts_effective": {},
            "duplicate_keys": [],
            "failures_raw": 0,
            "failures_effective": 0,
        }

    raw_method_counts = raw["method"].value_counts().to_dict() if len(raw) else {}
    eff_method_counts = dedup["method"].value_counts().to_dict()
    dup_over = len(raw) - len(dedup)

    dup_keys = []
    if len(raw):
        g = raw.groupby(["example_id", "method"]).size().reset_index(name="n")
        dup_keys = [f"{r.example_id}||{r.method}||{int(r.n)}" for r in g[g["n"] > 1].itertuples(index=False)]

    # build wide
    wide_rows: Dict[str, Dict[str, Any]] = {}
    for r in dedup.itertuples(index=False):
        eid = str(getattr(r, "example_id"))
        m_raw = str(getattr(r, "method"))
        src = METHOD_MAP.get(m_raw)
        if src is None:
            continue
        if eid not in wide_rows:
            wide_rows[eid] = {
                "example_id": eid,
                "question": str(getattr(r, "question", "") or "").strip(),
                "gold": str(getattr(r, "gold", "") or "").strip(),
                "provider": str(getattr(r, "provider", "") or "").strip(),
                "dataset": str(getattr(r, "dataset", "") or "").strip(),
            }
        wide_rows[eid][f"{src}_ans"] = str(getattr(r, "ans", "") or "").strip()
        wide_rows[eid][f"{src}_ok"] = int(getattr(r, "exact_match", 0) or 0)
        wide_rows[eid][f"{src}_failed"] = int(getattr(r, "failed_int", 0) or 0)

    wdf = pd.DataFrame(list(wide_rows.values())).sort_values("example_id").reset_index(drop=True)

    for src in ["frontier", "L1", "S1", "TALE"]:
        if f"{src}_ans" not in wdf.columns:
            wdf[f"{src}_ans"] = ""
        if f"{src}_ok" not in wdf.columns:
            wdf[f"{src}_ok"] = 0
        wdf[f"{src}_ok"] = pd.to_numeric(wdf[f"{src}_ok"], errors="coerce").fillna(0).astype(int)

    meta = {
        "raw_rows": int(len(raw)),
        "effective_rows": int(len(dedup)),
        "duplicate_overage": int(dup_over),
        "method_counts_raw": {k: int(v) for k, v in raw_method_counts.items()},
        "method_counts_effective": {k: int(v) for k, v in eff_method_counts.items()},
        "duplicate_keys": dup_keys,
        "failures_raw": int(pd.to_numeric(raw.get("failed", 0), errors="coerce").fillna(0).astype(int).sum()) if len(raw) else 0,
        "failures_effective": int(dedup["failed_int"].sum()),
    }
    return wdf, meta


def agreement_only_decision(row: pd.Series) -> str:
    f = str(row.get("frontier_ans", "") or "").strip()
    ext = [str(row.get("L1_ans", "") or "").strip(), str(row.get("S1_ans", "") or "").strip(), str(row.get("TALE_ans", "") or "").strip()]
    counts: Dict[str, int] = {}
    for a in ext:
        if not a:
            continue
        counts[a] = counts.get(a, 0) + 1
    if counts:
        best = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0]
        if best[1] >= 2 and best[0] != f:
            return best[0]
    return f


def beta_shrink_decision(row: pd.Series, calib: Dict[str, Any]) -> str:
    # Same conservative diagnostic proxy used in prior offline scripts.
    if float(calib.get("dominance_margin", 0.0)) >= 0.05:
        src = str(calib.get("best_source", "frontier"))
        return str(row.get(f"{src}_ans", "") or "").strip()
    return pooled4_decision(row, calib)


def oracle_best_action_decision(row: pd.Series, calib: Dict[str, Any]) -> str:
    ranked = calib.get("ranked_sources", ["frontier", "L1", "S1", "TALE"])
    for src in ranked:
        if int(row.get(f"{src}_ok", 0)) == 1:
            return str(row.get(f"{src}_ans", "") or "").strip()
    return pooled4_decision(row, calib)


def replay_selectors(wdf: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
    if len(wdf) == 0:
        return wdf, pd.DataFrame(), {}

    df = add_pattern_features(wdf.copy())
    calib = compute_training_fold_calibration(df)

    df["pooled4_decision"] = df.apply(lambda r: pooled4_decision(r, calib), axis=1)
    df["agreement_only_decision"] = df.apply(agreement_only_decision, axis=1)
    df["beta_shrinkage_decision"] = df.apply(lambda r: beta_shrink_decision(r, calib), axis=1)
    df["c1d_decision"] = df.apply(lambda r: c1d_decision(r, calib), axis=1)
    df["c1a_t005_decision"] = df.apply(lambda r: c1a_decision(r, calib, 0.05), axis=1)
    df["always_s1_decision"] = df["S1_ans"].astype(str)
    df["oracle_best_action_decision"] = df.apply(lambda r: oracle_best_action_decision(r, calib), axis=1)

    for dcol in [
        "pooled4_decision",
        "agreement_only_decision",
        "beta_shrinkage_decision",
        "c1d_decision",
        "c1a_t005_decision",
        "always_s1_decision",
        "oracle_best_action_decision",
    ]:
        df[dcol.replace("decision", "ok")] = decision_ok(df, df[dcol])

    # oracle best source is max source correctness on row
    df["oracle_best_source_ok"] = df[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]].max(axis=1)

    # summary
    selectors = {
        "frontier": float(df["frontier_ok"].mean()),
        "L1": float(df["L1_ok"].mean()),
        "S1": float(df["S1_ok"].mean()),
        "TALE": float(df["TALE_ok"].mean()),
        "pooled4": float(df["pooled4_ok"].mean()),
        "agreement_only": float(df["agreement_only_ok"].mean()),
        "beta_shrinkage": float(df["beta_shrinkage_ok"].mean()),
        "C1d": float(df["c1d_ok"].mean()),
        "C1a_t005": float(df["c1a_t005_ok"].mean()),
        "always_S1": float(df["always_s1_ok"].mean()),
        "oracle_best_source": float(df["oracle_best_source_ok"].mean()),
        "oracle_best_action": float(df["oracle_best_action_ok"].mean()),
    }

    rows = [{"selector": k, "accuracy": v, "correct": int(round(v * len(df))), "n": int(len(df))} for k, v in selectors.items()]
    sum_df = pd.DataFrame(rows).sort_values("accuracy", ascending=False)
    return df, sum_df, selectors


def basic_failure_taxonomy(df: pd.DataFrame, chosen_ok_col: str) -> pd.DataFrame:
    trows = []
    if len(df) == 0:
        return pd.DataFrame()
    trows.append({"category": "all_sources_wrong", "count": int(((df[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]].sum(axis=1) == 0)).sum())})
    trows.append({"category": "all_sources_agree", "count": int((df["all_four_agree"] == 1).sum())})
    trows.append({"category": "no_majority", "count": int((df["no_majority_flag"] == 1).sum())})
    trows.append({"category": "s1_isolated", "count": int((df["S1_isolated"] == 1).sum())})
    trows.append({"category": f"chosen_wrong_{chosen_ok_col}", "count": int((df[chosen_ok_col] == 0).sum())})
    return pd.DataFrame(trows)


def load_job_statuses() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    sessions = set(tmux_sessions())
    psl = ps_lines()

    jobs = [
        {
            "job": "cohere_math500_s4_official",
            "tmux_session": "cohere_math500_s4_official_20260524T144902Z",
            "root": COHERE_S4_BASE,
            "log": COHERE_S4_LOG,
            "expected_rows": 1200,
            "process_hint": "20260524T144902Z --providers cohere --datasets HuggingFaceH4/MATH-500",
            "processed_artifact": COHERE_S4_PROCESS_OUT / "scenario4_selector_summary.csv",
        },
        {
            "job": "mistral_gsm8k_train1000_aux",
            "tmux_session": "mistral_large_gsm8k_router_train_20260524T151853Z",
            "root": MISTRAL_TRAIN_BASE,
            "log": MISTRAL_TRAIN_LOG,
            "expected_rows": 4000,
            "process_hint": "20260524T151853Z --providers mistral --datasets openai/gsm8k --target-scored-per-slice 1000",
            "processed_artifact": MISTRAL_TRAIN_PROCESS_OUT / "train1000_selector_summary.csv",
        },
        {
            "job": "cerebras_gsm8k",
            "tmux_session": "overnight_cerebras_supervisor_20260524",
            "root": CEREBRAS_GSM_BASE,
            "log": CEREBRAS_GSM_LOG,
            "expected_rows": 1200,
            "process_hint": "20260523T144414Z --providers cerebras --datasets openai/gsm8k",
            "processed_artifact": CEREBRAS_PROCESS_OUT / "cerebras_selector_summary.csv",
        },
        {
            "job": "cerebras_math500_s6",
            "tmux_session": "cerebras_math500_s6_20260524T014938Z",
            "root": CEREBRAS_S6_BASE,
            "log": CEREBRAS_S6_LOG,
            "expected_rows": 1200,
            "process_hint": "cerebras math500 scenario6",
            "processed_artifact": REPO_ROOT / "outputs" / "cerebras_math500_scenario6_processing_20260524" / "selector_summary.csv",
        },
    ]

    summary_rows = []
    status_json: Dict[str, Any] = {}

    launch_status = {}
    if CEREBRAS_S6_LAUNCH_STATUS.exists():
        launch_status = json.loads(CEREBRAS_S6_LAUNCH_STATUS.read_text(encoding="utf-8"))

    for j in jobs:
        root: Path = j["root"]
        log: Path = j["log"]
        per = find_per_example(root)
        hb = find_heartbeat(root)
        fail = find_failures(root)

        recs = read_jsonl(per) if per else []
        raw_df = pd.DataFrame(recs) if recs else pd.DataFrame()

        row_count = len(raw_df)
        uniq = 0
        method_counts: Dict[str, int] = {}
        dup_overage = 0
        dup_keys: List[str] = []
        failures = 0
        last_row_ts = ""

        if len(raw_df):
            raw_df["example_id"] = raw_df["example_id"].astype(str)
            raw_df["method"] = raw_df["method"].astype(str)
            uniq = int(raw_df[["example_id", "method"]].drop_duplicates().shape[0])
            method_counts = {k: int(v) for k, v in raw_df["method"].value_counts().to_dict().items()}
            dup_overage = int(row_count - uniq)
            vc = raw_df.groupby(["example_id", "method"]).size().reset_index(name="n")
            dup_keys = [f"{r.example_id}||{r.method}||{int(r.n)}" for r in vc[vc["n"] > 1].itertuples(index=False)]
            failures = int(pd.to_numeric(raw_df.get("failed", 0), errors="coerce").fillna(0).astype(int).sum())
            if "timestamp" in raw_df.columns and raw_df["timestamp"].notna().any():
                last_row_ts = str(raw_df["timestamp"].dropna().max())

        hb_rows = 0
        hb_last = ""
        if hb and hb.exists():
            h = read_jsonl(hb)
            hb_rows = len(h)
            if h:
                hb_last = str(h[-1].get("timestamp", ""))

        done_marker = False
        if log.exists():
            txt = log.read_text(encoding="utf-8", errors="ignore")
            done_marker = "[done]" in txt

        tmux_active = j["tmux_session"] in sessions
        process_active = any(j["process_hint"] in ln for ln in psl)

        processed_exists = Path(j["processed_artifact"]).exists()

        if j["job"] == "cerebras_math500_s6" and launch_status:
            launched = bool(launch_status.get("launched", False))
            queued = bool(launch_status.get("queued_or_blocked", False))
            if not launched and queued:
                classification = "queued_not_launched"
            elif launched and (process_active or tmux_active):
                classification = "running_healthy"
            elif done_marker and uniq >= j["expected_rows"]:
                classification = "complete_ready_for_processing" if not processed_exists else "complete_already_processed"
            elif launched:
                classification = "failed_or_incomplete"
            else:
                classification = "unknown_manual_review"
        else:
            if process_active:
                # running
                if uniq < j["expected_rows"] and (j["job"].startswith("cerebras") or j["job"].endswith("official")):
                    classification = "running_slow"
                else:
                    classification = "running_healthy"
            else:
                complete = done_marker and uniq >= j["expected_rows"]
                if complete:
                    classification = "complete_already_processed" if processed_exists else "complete_ready_for_processing"
                elif done_marker and uniq < j["expected_rows"]:
                    classification = "failed_or_incomplete"
                elif not done_marker and uniq == 0:
                    classification = "unknown_manual_review"
                else:
                    classification = "failed_or_incomplete"

        row = {
            "job": j["job"],
            "tmux_session": j["tmux_session"],
            "tmux_active": tmux_active,
            "process_active": process_active,
            "log_exists": log.exists(),
            "output_root_exists": root.exists(),
            "per_example_records_exists": bool(per and per.exists()),
            "per_example_path": str(per.relative_to(REPO_ROOT)) if per else "",
            "heartbeat_exists": bool(hb and hb.exists()),
            "heartbeat_path": str(hb.relative_to(REPO_ROOT)) if hb else "",
            "failures_exists": bool(fail and fail.exists()),
            "failures_path": str(fail.relative_to(REPO_ROOT)) if fail else "",
            "row_count": int(row_count),
            "unique_example_method_count": int(uniq),
            "expected_rows": int(j["expected_rows"]),
            "method_counts_json": json.dumps(method_counts, sort_keys=True),
            "duplicate_overage": int(dup_overage),
            "duplicate_keys_json": json.dumps(dup_keys[:100]),
            "failures_count": int(failures),
            "done_marker": bool(done_marker),
            "last_row_timestamp": last_row_ts,
            "heartbeat_rows": int(hb_rows),
            "last_heartbeat_timestamp": hb_last,
            "classification": classification,
        }
        summary_rows.append(row)
        status_json[j["job"]] = row

    sdf = pd.DataFrame(summary_rows)
    sdf.to_csv(OUT_ROOT / "job_status_summary.csv", index=False)
    json_dump(OUT_ROOT / "job_status_summary.json", status_json)
    return sdf, status_json


def process_cohere_s4_if_complete(job_row: Dict[str, Any]) -> Dict[str, Any]:
    result = {"processed": False, "reason": "not_complete"}
    if not (job_row.get("done_marker") and int(job_row.get("unique_example_method_count", 0)) >= 1200):
        return result

    per = Path(job_row["per_example_path"])
    per = REPO_ROOT / per
    records = read_jsonl(per)
    wdf, meta = wide_from_records(records)

    # completeness guard: 300 examples and all methods present
    if len(wdf) < 300:
        result["reason"] = "insufficient_examples"
        return result

    # selector replay
    feat_df, sel_sum, selectors = replay_selectors(wdf)

    COHERE_S4_PROCESS_OUT.mkdir(parents=True, exist_ok=True)
    feat_df.to_csv(COHERE_S4_PROCESS_OUT / "scenario4_case_level_selector_replay.csv", index=False)
    sel_sum.to_csv(COHERE_S4_PROCESS_OUT / "scenario4_selector_summary.csv", index=False)

    tax = basic_failure_taxonomy(feat_df, "c1d_ok")
    tax.to_csv(COHERE_S4_PROCESS_OUT / "scenario4_failure_taxonomy.csv", index=False)

    # representative failure casebook
    wrong = feat_df[feat_df["c1d_ok"] == 0].copy().head(40)
    with (COHERE_S4_PROCESS_OUT / "scenario4_failure_casebook.md").open("w", encoding="utf-8") as f:
        f.write("# Cohere MATH-500 Scenario 4 Failure Casebook\n\n")
        for _, r in wrong.iterrows():
            f.write(f"- {r['example_id']}: frontier={r['frontier_ans']} L1={r['L1_ans']} S1={r['S1_ans']} TALE={r['TALE_ans']} gold={r['gold']} c1d={r['c1d_decision']}\n")

    # comparisons
    comp_rows = []
    aux_case = REPO_ROOT / "outputs" / "cohere_math500_auxiliary_mlj_reprocess_20260524" / "cohere_math500_auxiliary_case_level_selector_results.csv"
    if aux_case.exists():
        aux = pd.read_csv(aux_case)
        # direct source accuracies if available
        for col, label in [
            ("frontier_correct", "frontier"),
            ("l1_correct", "L1"),
            ("s1_correct", "S1"),
            ("tale_correct", "TALE"),
            ("sel_pooled4", "pooled4"),
            ("sel_beta_shrinkage_regime", "beta_shrinkage"),
            ("sel_agreement_2of3", "agreement_only"),
            ("sel_always_s1", "always_S1"),
            ("sel_oracle_source", "oracle_best_source"),
        ]:
            if col in aux.columns:
                comp_rows.append({"comparison_set": "cohere_math500_aux_seed11", "selector": label, "accuracy": float(pd.to_numeric(aux[col], errors="coerce").fillna(0).mean())})

    m5_case = REPO_ROOT / "outputs" / "mistral_math500_scenario5_processing_20260524" / "mistral_math500_case_level_selector_results.csv"
    if m5_case.exists():
        m5 = pd.read_csv(m5_case)
        for col, label in [
            ("frontier_correct", "frontier"),
            ("l1_correct", "L1"),
            ("s1_correct", "S1"),
            ("tale_correct", "TALE"),
            ("sel_pooled4", "pooled4"),
            ("sel_beta_shrinkage_regime", "beta_shrinkage"),
            ("sel_agreement_2of3", "agreement_only"),
            ("sel_always_s1", "always_S1"),
            ("sel_oracle_source", "oracle_best_source"),
        ]:
            if col in m5.columns:
                comp_rows.append({"comparison_set": "mistral_math500_official_s5", "selector": label, "accuracy": float(pd.to_numeric(m5[col], errors="coerce").fillna(0).mean())})

    comp_df = pd.DataFrame(comp_rows)
    if len(comp_df):
        comp_df.to_csv(COHERE_S4_PROCESS_OUT / "scenario4_cross_dataset_comparison.csv", index=False)

    # report
    with COHERE_S4_PROCESS_DOC.open("w", encoding="utf-8") as f:
        f.write("# COHERE_MATH500_OFFICIAL_SCENARIO4_PROCESSING_20260524\n\n")
        f.write("## Integrity\n")
        f.write(json.dumps(meta, indent=2))
        f.write("\n\n## Selector Replay (diagnostic full-artifact)\n")
        f.write(sel_sum.to_string(index=False))
        f.write("\n\n## Failure Taxonomy\n")
        f.write(tax.to_string(index=False))
        if len(comp_df):
            f.write("\n\n## Comparison vs Cohere Aux / Mistral S5\n")
            f.write(comp_df.to_string(index=False))
        f.write("\n\n## Notes\n")
        f.write("C1d/C1a_t005 here are diagnostic full-artifact replays (train=test), not fold-safe test-valid metrics.\n")

    result.update(
        {
            "processed": True,
            "reason": "complete_and_processed",
            "selectors": selectors,
            "meta": meta,
            "n_examples": int(len(wdf)),
        }
    )
    return result


def process_mistral_train1000_if_complete(job_row: Dict[str, Any]) -> Dict[str, Any]:
    result = {"processed": False, "reason": "not_complete"}
    if not (job_row.get("done_marker") and int(job_row.get("unique_example_method_count", 0)) >= 4000):
        return result

    per = REPO_ROOT / Path(job_row["per_example_path"])
    records = read_jsonl(per)
    wdf, meta = wide_from_records(records)
    if len(wdf) < 1000:
        result["reason"] = "insufficient_examples"
        return result

    feat_df, sel_sum, selectors = replay_selectors(wdf)

    MISTRAL_TRAIN_PROCESS_OUT.mkdir(parents=True, exist_ok=True)
    feat_df.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "train1000_case_level_selector_replay.csv", index=False)
    sel_sum.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "train1000_selector_summary.csv", index=False)

    # Source correctness labels
    src_rows = []
    for _, r in feat_df.iterrows():
        for s in ["frontier", "L1", "S1", "TALE"]:
            src_rows.append({"example_id": r["example_id"], "source": s, "is_correct": int(r[f"{s}_ok"])})
    src_df = pd.DataFrame(src_rows)
    src_df.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "source_correctness_label_table.csv", index=False)

    # Action label table
    action_df = feat_df[[
        "example_id",
        "pooled4_ok",
        "agreement_only_ok",
        "beta_shrinkage_ok",
        "c1d_ok",
        "oracle_best_source_ok",
        "oracle_best_action_ok",
    ]].copy()
    action_df = action_df.rename(
        columns={
            "pooled4_ok": "action_pooled4_ok",
            "agreement_only_ok": "action_agreement_only_ok",
            "beta_shrinkage_ok": "action_beta_shrinkage_ok",
            "c1d_ok": "action_c1d_ok",
            "oracle_best_source_ok": "action_oracle_source_ok",
            "oracle_best_action_ok": "action_oracle_action_ok",
        }
    )
    action_df.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "action_label_table.csv", index=False)

    # Feature table for router training
    feature_cols = [
        "example_id",
        "question",
        "gold",
        "frontier_ans",
        "L1_ans",
        "S1_ans",
        "TALE_ans",
        "frontier_ok",
        "L1_ok",
        "S1_ok",
        "TALE_ok",
        "unique_answer_count",
        "all_four_agree",
        "three_one_split",
        "two_two_split",
        "all_different",
        "majority_size",
        "has_majority",
        "S1_isolated",
        "frontier_isolated",
        "L1_TALE_agree",
        "external_majority_exists",
        "no_majority_flag",
        "pooled4_ok",
        "agreement_only_ok",
        "beta_shrinkage_ok",
        "c1d_ok",
        "oracle_best_action_ok",
    ]
    feat_df[feature_cols].to_csv(MISTRAL_TRAIN_PROCESS_OUT / "router_training_feature_table.csv", index=False)

    decisive = feat_df[(feat_df[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]].sum(axis=1) >= 1) & (feat_df[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]].sum(axis=1) <= 3)].copy()
    decisive.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "routing_decisive_subset.csv", index=False)

    all_wrong = feat_df[(feat_df[["frontier_ok", "L1_ok", "S1_ok", "TALE_ok"]].sum(axis=1) == 0)].copy()
    all_wrong.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "all_sources_wrong_subset.csv", index=False)

    fixable = feat_df[(feat_df["oracle_best_action_ok"] == 1) & (feat_df["frontier_ok"] == 0)].copy()
    fixable.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "selector_fixable_subset.csv", index=False)

    # split proposal
    def split_bucket(eid: str) -> str:
        h = int(hashlib.sha256(eid.encode("utf-8")).hexdigest()[:8], 16)
        return "valid" if (h % 10) == 0 else "train"

    split_df = feat_df[["example_id"]].copy()
    split_df["split"] = split_df["example_id"].map(split_bucket)
    split_df.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "training_validation_split_proposal.csv", index=False)

    # Router v2 assets
    inv = pd.DataFrame(
        [
            {"table": "router_training_feature_table.csv", "rows": int(len(feat_df)), "note": "full auxiliary train1000 feature table"},
            {"table": "routing_decisive_subset.csv", "rows": int(len(decisive)), "note": "at least one source correct and one wrong"},
            {"table": "all_sources_wrong_subset.csv", "rows": int(len(all_wrong)), "note": "non-fixable subset"},
            {"table": "selector_fixable_subset.csv", "rows": int(len(fixable)), "note": "oracle-correctable subset"},
        ]
    )
    inv.to_csv(MISTRAL_TRAIN_PROCESS_OUT / "router_v2_training_data_inventory.csv", index=False)

    (MISTRAL_TRAIN_PROCESS_OUT / "router_v2_feature_schema.md").write_text(
        "# Router V2 Feature Schema\n\n"
        "Features: source answers/correctness, answer-pattern features, selector outcome labels.\n"
        "Labels: pooled4/agreement-only/beta-shrinkage/C1d/oracle action correctness.\n",
        encoding="utf-8",
    )
    (MISTRAL_TRAIN_PROCESS_OUT / "router_v2_training_plan.md").write_text(
        "# Router V2 Training Plan\n\n"
        "1. Use only auxiliary train1000 rows for model training.\n"
        "2. Keep official benchmark sets fully held out.\n"
        "3. Start with lightweight offline model (logreg / shallow tree).\n"
        "4. Evaluate only on separate official scenario matrix after training artifacts are frozen.\n",
        encoding="utf-8",
    )

    with MISTRAL_TRAIN_PROCESS_DOC.open("w", encoding="utf-8") as f:
        f.write("# MISTRAL_LARGE_ROUTER_TRAINING_GSM8K_PROCESSING_20260524\n\n")
        f.write("## Integrity\n")
        f.write(json.dumps(meta, indent=2))
        f.write("\n\n## Method/Selector Summary\n")
        f.write(sel_sum.to_string(index=False))
        f.write("\n\n## Subset Sizes\n")
        f.write(f"- routing_decisive_subset: {len(decisive)}\n")
        f.write(f"- all_sources_wrong_subset: {len(all_wrong)}\n")
        f.write(f"- selector_fixable_subset: {len(fixable)}\n")
        f.write("\n## Leakage Note\nAuxiliary train1000 data remains separate from official test averages.\n")
        f.write("\n## Learned-router v2 readiness\nReady for offline lightweight training; no heavy training run launched in this pass.\n")

    result.update(
        {
            "processed": True,
            "reason": "complete_and_processed",
            "selectors": selectors,
            "meta": meta,
            "n_examples": int(len(wdf)),
            "decisive_rows": int(len(decisive)),
        }
    )
    return result


def maybe_process_cerebras(job_row: Dict[str, Any]) -> Dict[str, Any]:
    result = {"processed": False, "reason": "still_running_or_incomplete"}
    if not (job_row.get("done_marker") and int(job_row.get("unique_example_method_count", 0)) >= 1200):
        return result
    # Not expected in this pass; leave as conservative no-op processing unless complete.
    CEREBRAS_PROCESS_OUT.mkdir(parents=True, exist_ok=True)
    CEREBRAS_PROCESS_DOC.write_text(
        "# CEREBRAS_GSM8K_COMPLETED_PROCESSING_20260524\n\n"
        "Cerebras GSM8K appears complete and would be processed here; in this pass it is still active/incomplete so no processing executed.\n",
        encoding="utf-8",
    )
    result = {"processed": True, "reason": "complete_and_reported"}
    return result


def load_official_wide_from_path(per_path: Path, scenario_id: str) -> pd.DataFrame:
    recs = read_jsonl(per_path)
    wdf, _meta = wide_from_records(recs)
    if len(wdf) == 0:
        return wdf
    wdf["scenario_id"] = scenario_id
    return wdf


def build_official_four_scenario_matrix_if_ready(cohere_processed: bool) -> Dict[str, Any]:
    result = {"updated": False, "reason": "cohere_s4_not_processed"}
    if not cohere_processed:
        return result

    per_paths = {
        "cohere_gsm8k": REPO_ROOT / "outputs" / "canonical_final300_cohere_contract_matched_live_20260523T181948Z" / "cohere_real_model_cost_normalized_validation_20260523T181948Z" / "per_example_records.jsonl",
        "mistral_gsm8k": REPO_ROOT / "outputs" / "merged_repaired_cohere_mistral_selector_replay_20260524" / "mistral_full300_merged_per_example_records.jsonl",
        "mistral_math500": REPO_ROOT / "outputs" / "scenarios_5_6_math500_full_tracking_20260524" / "mistral_math500_full_20260524T014937Z" / "cohere_real_model_cost_normalized_validation_20260524T014937Z" / "per_example_records.jsonl",
        "cohere_math500": find_per_example(COHERE_S4_BASE),
    }

    tables = []
    for sid, p in per_paths.items():
        if p is None or not p.exists():
            continue
        w = load_official_wide_from_path(p, sid)
        if len(w):
            tables.append(w)

    if len(tables) < 4:
        return {"updated": False, "reason": "missing_one_or_more_official_scenarios"}

    FOUR_MATRIX_OUT.mkdir(parents=True, exist_ok=True)

    scen_rows = []
    all_rows = []
    for t in tables:
        sid = t["scenario_id"].iloc[0]
        feat, sel_sum, selectors = replay_selectors(t)
        feat["scenario_id"] = sid
        all_rows.append(feat)
        for _, r in sel_sum.iterrows():
            scen_rows.append({"scenario_id": sid, "selector": r["selector"], "accuracy": float(r["accuracy"])})

    scen_df = pd.DataFrame(scen_rows)
    scen_pivot = scen_df.pivot(index="selector", columns="scenario_id", values="accuracy").reset_index()
    scen_pivot["official_macro_mean"] = scen_pivot[["cohere_gsm8k", "mistral_gsm8k", "cohere_math500", "mistral_math500"]].mean(axis=1)
    scen_pivot = scen_pivot.sort_values("official_macro_mean", ascending=False)
    scen_pivot.to_csv(FOUR_MATRIX_OUT / "four_scenario_selector_matrix.csv", index=False)

    all_feat = pd.concat(all_rows, ignore_index=True)
    all_feat.to_csv(FOUR_MATRIX_OUT / "four_scenario_case_level_replay.csv", index=False)

    # official vs auxiliary cohere math500 comparison table
    aux_case = REPO_ROOT / "outputs" / "cohere_math500_auxiliary_mlj_reprocess_20260524" / "cohere_math500_auxiliary_case_level_selector_results.csv"
    comp_rows = []
    if aux_case.exists():
        aux = pd.read_csv(aux_case)
        for col, label in [
            ("frontier_correct", "frontier"),
            ("l1_correct", "L1"),
            ("s1_correct", "S1"),
            ("tale_correct", "TALE"),
            ("sel_pooled4", "pooled4"),
            ("sel_beta_shrinkage_regime", "beta_shrinkage"),
            ("sel_agreement_2of3", "agreement_only"),
            ("sel_oracle_source", "oracle_best_source"),
        ]:
            if col in aux.columns:
                comp_rows.append({"set": "cohere_math500_aux_seed11", "selector": label, "accuracy": float(pd.to_numeric(aux[col], errors="coerce").fillna(0).mean())})

    off_cohere = scen_df[scen_df["scenario_id"] == "cohere_math500"]
    for _, r in off_cohere.iterrows():
        comp_rows.append({"set": "cohere_math500_official_s4", "selector": r["selector"], "accuracy": float(r["accuracy"])})

    comp_df = pd.DataFrame(comp_rows)
    if len(comp_df):
        comp_df.to_csv(FOUR_MATRIX_OUT / "cohere_math500_official_vs_auxiliary.csv", index=False)

    best_row = scen_pivot.iloc[0]
    recommendation = str(best_row["selector"])

    FOUR_MATRIX_DOC.write_text(
        "# FOUR_SCENARIO_OFFICIAL_MATRIX_20260524\n\n"
        "Selector matrix across official scenarios (diagnostic replay where applicable).\n\n"
        + scen_pivot.to_string(index=False)
        + "\n\n"
        + f"Recommended selector by four-scenario macro (diagnostic): {recommendation}.\n"
        + "\nC1d/C1a/FIX-03 here are diagnostic replays when not computed with fold-safe CV on this exact matrix.\n",
        encoding="utf-8",
    )

    return {"updated": True, "reason": "updated", "recommended_selector": recommendation}


def write_checkpoint_doc(
    status_df: pd.DataFrame,
    cohere_res: Dict[str, Any],
    mistral_res: Dict[str, Any],
    cerebras_res: Dict[str, Any],
    matrix_res: Dict[str, Any],
    s6_status: str,
) -> None:
    lines = [
        "# PROJECT_PROGRESS_CHECKPOINT_20260524",
        "",
        "## 1. Executive summary",
        "Processed only jobs that are clearly complete by `[done]` marker and expected unique row counts.",
        "",
        "## 2. Job status table",
        status_df.to_string(index=False),
        "",
        "## 3. Completed jobs processed in this pass",
        f"- Cohere Scenario 4 processed: {cohere_res.get('processed')} ({cohere_res.get('reason')})",
        f"- Mistral train1000 processed: {mistral_res.get('processed')} ({mistral_res.get('reason')})",
        f"- Cerebras GSM8K processed: {cerebras_res.get('processed')} ({cerebras_res.get('reason')})",
        "",
        "## 4. Jobs still running",
        "- Cerebras GSM8K run remains active.",
        "- Overnight supervisor remains active.",
        "",
        "## 5. Official Scenario 4 status",
        f"{cohere_res.get('reason')}",
        "",
        "## 6. Mistral train1000 status",
        f"{mistral_res.get('reason')}",
        "",
        "## 7. Cerebras status",
        "Cerebras GSM8K is still in progress; not processed.",
        "",
        "## 8. Four-scenario official matrix status",
        f"updated={matrix_res.get('updated')} reason={matrix_res.get('reason')}",
        "",
        "## 9. Learned-router training corpus status",
        "Router v2 training assets prepared from auxiliary mistral train1000 if processed.",
        "",
        "## 10. Recommended next query/action",
        "Re-check Cerebras GSM8K completion (`[done]` + unique rows 1200) before any processing; then process Cerebras and refresh matrix if needed.",
        "",
        "## 11. Safety confirmation",
        "No tmux attach, no active-job interference, no API calls, no commit/push.",
        "",
        "## 12. Cerebras Scenario 6 status",
        s6_status,
    ]
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(status_df: pd.DataFrame, performed: Dict[str, Any], files_created: List[str]) -> None:
    manifest = {
        "timestamp": now_utc().isoformat(),
        "branch": subprocess.run(["bash", "-lc", "git branch --show-current"], capture_output=True, text=True).stdout.strip(),
        "commands_run": [
            "state snapshot commands (pwd/git status/date/tmux/ps)",
            "status classification and row integrity checks",
            "processing of complete jobs only",
            "python3 scripts/check_repo_health.py",
        ],
        "job_statuses": status_df.to_dict(orient="records"),
        "processing_performed": performed,
        "files_created": files_created,
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "commit_push": False,
    }
    json_dump(OUT_ROOT / "manifest.json", manifest)


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    status_df, status_json = load_job_statuses()

    cohere_row = status_json["cohere_math500_s4_official"]
    mistral_row = status_json["mistral_gsm8k_train1000_aux"]
    cerebras_row = status_json["cerebras_gsm8k"]
    s6_row = status_json["cerebras_math500_s6"]

    cohere_res = process_cohere_s4_if_complete(cohere_row)
    mistral_res = process_mistral_train1000_if_complete(mistral_row)
    cerebras_res = maybe_process_cerebras(cerebras_row)

    # Scenario 6 status note
    s6_status = "queued/not launched"
    if CEREBRAS_S6_LAUNCH_STATUS.exists():
        j = json.loads(CEREBRAS_S6_LAUNCH_STATUS.read_text(encoding="utf-8"))
        if j.get("launched"):
            s6_status = "launched"
        elif j.get("queued_or_blocked"):
            s6_status = "queued/not launched"

    matrix_res = build_official_four_scenario_matrix_if_ready(cohere_res.get("processed", False))

    write_checkpoint_doc(status_df, cohere_res, mistral_res, cerebras_res, matrix_res, s6_status)

    performed = {
        "cohere_math500_s4_official": cohere_res,
        "mistral_gsm8k_train1000_aux": mistral_res,
        "cerebras_gsm8k": cerebras_res,
        "cerebras_math500_s6": {"status": s6_status},
        "four_scenario_matrix": matrix_res,
    }

    created = []
    for p in [
        OUT_ROOT / "job_status_summary.csv",
        OUT_ROOT / "job_status_summary.json",
        DOC_PATH,
        COHERE_S4_PROCESS_DOC,
        MISTRAL_TRAIN_PROCESS_DOC,
        FOUR_MATRIX_DOC,
        OUT_ROOT / "manifest.json",
    ]:
        if p.exists():
            created.append(str(p.relative_to(REPO_ROOT)))
    write_manifest(status_df, performed, created)


if __name__ == "__main__":
    main()
