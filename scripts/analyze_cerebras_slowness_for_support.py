#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "outputs" / "cerebras_support_slowness_diagnostics_20260524"
DOC_PATH = REPO_ROOT / "docs" / "CEREBRAS_SUPPORT_SLOWNESS_DIAGNOSTICS_20260524.md"

TARGET_ROOT = REPO_ROOT / "outputs" / "cerebras_frozen_agreement_only_2of3_validation_20260523"
RUN_DIR = TARGET_ROOT / "cohere_real_model_cost_normalized_validation_20260523T144414Z"
RUN_LOG = TARGET_ROOT / "live_validation_20260523T144414Z.log"
DRY_PLAN = TARGET_ROOT / "cohere_real_model_cost_normalized_validation_20260523T104237Z" / "dry_run_call_plan.json"
PER_EXAMPLE = RUN_DIR / "per_example_records.jsonl"
HEARTBEAT = RUN_DIR / "progress_heartbeat.jsonl"
FAILURES = RUN_DIR / "raw" / "failures.jsonl"

EXPECTED_ROWS = 1200
EXPECTED_METHODS = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]

ERROR_PATTERNS = {
    "http_429": re.compile(r"\b429\b|too_many_requests|rate limit|rate_limit", re.I),
    "http_500": re.compile(r"\b500\b", re.I),
    "http_502": re.compile(r"\b502\b", re.I),
    "http_503": re.compile(r"\b503\b|unavailable", re.I),
    "http_504": re.compile(r"\b504\b", re.I),
    "timeout": re.compile(r"timeout|timed out", re.I),
    "temporary_unavailable": re.compile(r"temporary unavailable|try again soon|high traffic", re.I),
    "queue_exceeded": re.compile(r"queue_exceeded|queue exceeded|param\s*[:=]\s*\"?queue", re.I),
    "rate_limit": re.compile(r"rate limit|too_many_requests", re.I),
    "http_403": re.compile(r"\b403\b", re.I),
    "code_1010": re.compile(r"\b1010\b", re.I),
    "traceback": re.compile(r"traceback", re.I),
    "fatal": re.compile(r"fatal", re.I),
    "exception": re.compile(r"exception|runtimeerror|httperror", re.I),
    "retry": re.compile(r"retry", re.I),
}


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_or_none(x: Optional[dt.datetime]) -> Optional[str]:
    return x.isoformat() if x is not None else None


def parse_ts(v: Any) -> Optional[dt.datetime]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
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
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def table_text(df: pd.DataFrame) -> str:
    if df is None or len(df) == 0:
        return "no rows"
    return df.to_string(index=False)


def fmt_float(v: Any, n: int = 2) -> str:
    if v is None:
        return "n/a"
    try:
        return f"{float(v):.{n}f}"
    except Exception:
        return "n/a"


def list_artifacts() -> List[Path]:
    files: List[Path] = []
    for p in TARGET_ROOT.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        if (
            name.endswith(".log")
            or name == "per_example_records.jsonl"
            or name == "progress_heartbeat.jsonl"
            or name == "failures.jsonl"
            or name == "manifest.json"
            or "call_plan" in name
            or "status" in name
        ):
            files.append(p)
    return sorted(files)


def build_artifact_inventory(files: List[Path]) -> None:
    rows = []
    for p in files:
        st = p.stat()
        rows.append(
            {
                "path": str(p.relative_to(REPO_ROOT)),
                "size_bytes": int(st.st_size),
                "mtime_utc": dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc).isoformat(),
            }
        )
    write_json(OUT_DIR / "artifact_inventory.json", {"artifacts": rows, "count": len(rows)})
    pd.DataFrame(rows).to_csv(OUT_DIR / "artifact_inventory.csv", index=False)


def latest_snapshot_file() -> Optional[Path]:
    snaps = sorted(OUT_DIR.glob("raw_process_snapshot_*.txt"))
    return snaps[-1] if snaps else None


def extract_run_config(snapshot_path: Optional[Path]) -> Dict[str, Any]:
    plan = json.loads(DRY_PLAN.read_text(encoding="utf-8")) if DRY_PLAN.exists() else {}

    run_cmd_raw = ""
    if snapshot_path and snapshot_path.exists():
        for line in snapshot_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "--providers cerebras" in line and "run_cohere_real_model_cost_normalized_validation.py" in line:
                run_cmd_raw = line.strip()
                break
    run_cmd_redacted = re.sub(r"(?i)(api[_-]?key|token)[^\s]*", "[REDACTED]", run_cmd_raw)

    start_ts = None
    if RUN_LOG.exists():
        for line in RUN_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[:5]:
            m = re.search(r"\[start\]\s+([0-9TZ:\-]+)", line)
            if m:
                start_ts = m.group(1)
                break

    now = now_utc()
    per_rows = read_jsonl(PER_EXAMPLE)
    ts_rows = [parse_ts(r.get("timestamp")) for r in per_rows]
    ts_rows = [t for t in ts_rows if t is not None]
    latest_row_ts = max(ts_rows) if ts_rows else None

    cfg = {
        "provider": "cerebras",
        "model_name": "llama3.1-8b",
        "dataset": "openai/gsm8k",
        "seed": 71,
        "budget": 6,
        "num_examples_target": 300,
        "methods_requested": EXPECTED_METHODS,
        "expected_rows": EXPECTED_ROWS,
        "start_timestamp_utc": start_ts,
        "current_or_end_timestamp_utc": now.isoformat(),
        "latest_row_timestamp_utc": iso_or_none(latest_row_ts),
        "runner_command_redacted": run_cmd_redacted,
        "retry_backoff_settings": plan.get("retry_policy", {}),
        "max_recovery_passes": plan.get("max_recovery_passes"),
        "output_root": str(TARGET_ROOT.relative_to(REPO_ROOT)),
        "run_output_dir": str(RUN_DIR.relative_to(REPO_ROOT)),
        "run_log_path": str(RUN_LOG.relative_to(REPO_ROOT)),
        "source_snapshot_path": str(snapshot_path.relative_to(REPO_ROOT)) if snapshot_path else None,
    }
    write_json(OUT_DIR / "cerebras_run_configuration.json", cfg)
    return cfg


def series_quantiles(arr: List[float]) -> Dict[str, Optional[float]]:
    if not arr:
        return {"median": None, "p90": None, "p95": None, "p99": None, "max": None}
    a = np.array(arr, dtype=float)
    return {
        "median": float(np.quantile(a, 0.5)),
        "p90": float(np.quantile(a, 0.9)),
        "p95": float(np.quantile(a, 0.95)),
        "p99": float(np.quantile(a, 0.99)),
        "max": float(np.max(a)),
    }


def analyze_progress(per_rows: List[Dict[str, Any]], hb_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    now = now_utc()

    df = pd.DataFrame(per_rows)
    if len(df) == 0:
        empty = {
            "first_row_timestamp_utc": None,
            "latest_row_timestamp_utc": None,
            "first_heartbeat_timestamp_utc": None,
            "latest_heartbeat_timestamp_utc": None,
            "elapsed_wall_clock_seconds": None,
            "total_rows_written": 0,
            "effective_complete_rows": 0,
            "expected_rows": EXPECTED_ROWS,
            "percent_complete": 0.0,
        }
        write_json(OUT_DIR / "cerebras_progress_summary.json", empty)
        pd.DataFrame([]).to_csv(OUT_DIR / "cerebras_method_throughput.csv", index=False)
        pd.DataFrame([]).to_csv(OUT_DIR / "cerebras_hourly_throughput.csv", index=False)
        pd.DataFrame([]).to_csv(OUT_DIR / "cerebras_pause_windows.csv", index=False)
        return empty

    df["ts"] = df["timestamp"].map(parse_ts)
    df = df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)

    key_cols = ["example_id", "method"]
    key_counts = df.groupby(key_cols).size().rename("dup_count").reset_index()
    dup_keys = key_counts[key_counts["dup_count"] > 1]

    first_row_ts = df["ts"].iloc[0]
    latest_row_ts = df["ts"].iloc[-1]
    elapsed_sec = max((latest_row_ts - first_row_ts).total_seconds(), 0.0)

    total_rows = int(len(df))
    effective_rows = int(df[key_cols].drop_duplicates().shape[0])
    percent_complete = 100.0 * effective_rows / EXPECTED_ROWS

    df["gap_sec"] = df["ts"].diff().dt.total_seconds()
    gaps = [float(x) for x in df["gap_sec"].dropna().tolist() if x >= 0]
    q = series_quantiles(gaps)

    active_threshold = 600.0
    active_gaps = [g for g in gaps if g <= active_threshold]
    active_sec = float(np.sum(active_gaps)) if active_gaps else 0.0
    rows_per_hour_overall = (total_rows / (elapsed_sec / 3600.0)) if elapsed_sec > 0 else None
    rows_per_hour_active = ((len(gaps)) / (active_sec / 3600.0)) if active_sec > 0 else None
    sec_per_row_overall = (elapsed_sec / total_rows) if total_rows > 0 else None

    # method throughput
    mrows: List[Dict[str, Any]] = []
    for m, g in df.groupby("method"):
        g = g.sort_values("ts").reset_index(drop=True)
        ggaps = g["ts"].diff().dt.total_seconds().dropna().tolist()
        qq = series_quantiles([float(x) for x in ggaps if x >= 0])
        unique_cnt = int(g[key_cols].drop_duplicates().shape[0])
        completed = unique_cnt >= 300
        long_gaps = int(sum(1 for x in ggaps if x > 600))
        mrows.append(
            {
                "method": m,
                "rows_written": int(len(g)),
                "effective_unique_rows": unique_cnt,
                "first_timestamp_utc": g["ts"].iloc[0].isoformat(),
                "last_timestamp_utc": g["ts"].iloc[-1].isoformat(),
                "avg_seconds_per_row_from_gaps": (float(np.mean(ggaps)) if ggaps else None),
                "median_seconds_per_row": qq["median"],
                "p90_seconds_per_row": qq["p90"],
                "p95_seconds_per_row": qq["p95"],
                "long_gap_count_gt10m": long_gaps,
                "completed_300": bool(completed),
            }
        )
    mdf = pd.DataFrame(mrows).sort_values("method")
    mdf.to_csv(OUT_DIR / "cerebras_method_throughput.csv", index=False)

    # hourly throughput
    df["hour_bucket_utc"] = df["ts"].dt.floor("h")
    hourly = df.groupby("hour_bucket_utc").size().rename("rows_written").reset_index()
    hourly["rows_per_hour"] = hourly["rows_written"].astype(float)
    hourly["hour_bucket_utc"] = hourly["hour_bucket_utc"].dt.tz_convert(dt.timezone.utc).astype(str)
    hourly.to_csv(OUT_DIR / "cerebras_hourly_throughput.csv", index=False)

    # pause windows from row gaps
    pause_rows: List[Dict[str, Any]] = []
    for i in range(1, len(df)):
        g = float(df.loc[i, "gap_sec"])
        if g <= 600:
            continue
        start_t = df.loc[i - 1, "ts"]
        end_t = df.loc[i, "ts"]
        pause_rows.append(
            {
                "pause_start_utc": start_t.isoformat(),
                "pause_end_utc": end_t.isoformat(),
                "gap_seconds": g,
                "gap_minutes": g / 60.0,
                "gt_10m": int(g > 600),
                "gt_30m": int(g > 1800),
                "gt_60m": int(g > 3600),
                "rows_before_pause": int(i),
                "rows_after_pause": int(i + 1),
                "method_before": df.loc[i - 1, "method"],
                "method_after": df.loc[i, "method"],
                "example_before": df.loc[i - 1, "example_id"],
                "example_after": df.loc[i, "example_id"],
            }
        )
    pwin = pd.DataFrame(pause_rows).sort_values("gap_seconds", ascending=False)
    pwin.to_csv(OUT_DIR / "cerebras_pause_windows.csv", index=False)

    # heartbeat range
    hb_ts = sorted([parse_ts(r.get("timestamp")) for r in hb_rows if parse_ts(r.get("timestamp")) is not None])
    first_hb_ts = hb_ts[0] if hb_ts else None
    latest_hb_ts = hb_ts[-1] if hb_ts else None

    summary = {
        "first_row_timestamp_utc": first_row_ts.isoformat(),
        "latest_row_timestamp_utc": latest_row_ts.isoformat(),
        "first_heartbeat_timestamp_utc": iso_or_none(first_hb_ts),
        "latest_heartbeat_timestamp_utc": iso_or_none(latest_hb_ts),
        "elapsed_wall_clock_seconds": elapsed_sec,
        "elapsed_wall_clock_hours": elapsed_sec / 3600.0,
        "total_rows_written": total_rows,
        "effective_complete_rows": effective_rows,
        "expected_rows": EXPECTED_ROWS,
        "percent_complete": percent_complete,
        "rows_per_hour_overall": rows_per_hour_overall,
        "rows_per_hour_in_active_windows": rows_per_hour_active,
        "average_seconds_per_row_overall": sec_per_row_overall,
        "median_seconds_between_rows": q["median"],
        "p90_seconds_between_rows": q["p90"],
        "p95_seconds_between_rows": q["p95"],
        "p99_seconds_between_rows": q["p99"],
        "max_observed_gap_between_rows_seconds": q["max"],
        "max_observed_gap_between_rows_minutes": (q["max"] / 60.0 if q["max"] is not None else None),
        "duplicate_key_count": int(len(dup_keys)),
        "duplicate_row_overage": int(total_rows - effective_rows),
        "rows_missing_to_expected": int(EXPECTED_ROWS - effective_rows),
        "age_of_latest_row_seconds": (now - latest_row_ts).total_seconds(),
    }
    write_json(OUT_DIR / "cerebras_progress_summary.json", summary)
    return summary


def analyze_heartbeat(hb_rows: List[Dict[str, Any]], per_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    now = now_utc()
    h = pd.DataFrame(hb_rows)
    if len(h) == 0:
        write_json(OUT_DIR / "cerebras_heartbeat_gap_summary.json", {"heartbeat_count": 0})
        pd.DataFrame([]).to_csv(OUT_DIR / "cerebras_heartbeat_intervals.csv", index=False)
        return {"heartbeat_count": 0}

    h["ts"] = h["timestamp"].map(parse_ts)
    h = h.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    h["gap_sec"] = h["ts"].diff().dt.total_seconds()

    intervals = []
    for i in range(1, len(h)):
        g = float(h.loc[i, "gap_sec"])
        intervals.append(
            {
                "prev_timestamp_utc": h.loc[i - 1, "ts"].isoformat(),
                "next_timestamp_utc": h.loc[i, "ts"].isoformat(),
                "interval_seconds": g,
                "interval_minutes": g / 60.0,
                "gt_10m": int(g > 600),
                "gt_30m": int(g > 1800),
                "gt_60m": int(g > 3600),
            }
        )
    idf = pd.DataFrame(intervals).sort_values("interval_seconds", ascending=False)
    idf.to_csv(OUT_DIR / "cerebras_heartbeat_intervals.csv", index=False)

    max_gap = float(idf["interval_seconds"].max()) if len(idf) else 0.0

    # pause windows from heartbeat gaps
    hb_pause = idf[idf["interval_seconds"] > 600].copy()

    # did heartbeat continue during no-row pauses?
    per_ts = sorted([parse_ts(r.get("timestamp")) for r in per_rows if parse_ts(r.get("timestamp")) is not None])
    row_pause_windows: List[Tuple[dt.datetime, dt.datetime]] = []
    for i in range(1, len(per_ts)):
        gap = (per_ts[i] - per_ts[i - 1]).total_seconds()
        if gap > 600:
            row_pause_windows.append((per_ts[i - 1], per_ts[i]))

    continued_count = 0
    pause_checks = []
    for s, e in row_pause_windows:
        n_hb = int(((h["ts"] > s) & (h["ts"] < e)).sum())
        continued = n_hb > 0
        if continued:
            continued_count += 1
        pause_checks.append({
            "pause_start_utc": s.isoformat(),
            "pause_end_utc": e.isoformat(),
            "heartbeat_events_during_pause": n_hb,
            "heartbeat_continued": continued,
        })

    running = is_cerebras_process_running()

    summary = {
        "heartbeat_count": int(len(h)),
        "first_heartbeat_timestamp_utc": h.loc[0, "ts"].isoformat(),
        "latest_heartbeat_timestamp_utc": h.loc[len(h) - 1, "ts"].isoformat(),
        "latest_heartbeat_age_seconds": float((now - h.loc[len(h) - 1, "ts"]).total_seconds()),
        "max_heartbeat_interval_seconds": max_gap,
        "max_heartbeat_interval_minutes": max_gap / 60.0,
        "pause_windows_from_heartbeat_gt10m": int((idf["interval_seconds"] > 600).sum()) if len(idf) else 0,
        "pause_windows_from_heartbeat_gt30m": int((idf["interval_seconds"] > 1800).sum()) if len(idf) else 0,
        "pause_windows_from_heartbeat_gt60m": int((idf["interval_seconds"] > 3600).sum()) if len(idf) else 0,
        "heartbeat_continued_during_row_pauses_count": continued_count,
        "row_pause_windows_checked": len(row_pause_windows),
        "current_status": "running" if running else "not_running_or_complete",
        "heartbeat_continued_checks": pause_checks[:1000],
    }
    write_json(OUT_DIR / "cerebras_heartbeat_gap_summary.json", summary)
    return summary


def is_cerebras_process_running() -> bool:
    cmd = "ps -eo cmd | grep -E 'run_cohere_real_model_cost_normalized_validation.py' | grep -E 'providers cerebras|--providers cerebras' | grep -v grep || true"
    out = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, check=False)
    return bool(out.stdout.strip())


def extract_error_retry_signals(per_rows: List[Dict[str, Any]], hb_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    lines: List[Tuple[str, str, str, str, str, str, str]] = []
    # source, timestamp, method, example_id, text, recovered

    # failures file rows
    failure_rows = read_jsonl(FAILURES)
    if failure_rows:
        with (OUT_DIR / "cerebras_failure_rows.jsonl").open("w", encoding="utf-8") as f:
            for r in failure_rows:
                f.write(json.dumps(r) + "\n")

    # map for recovery detection
    scored_keys = set()
    for r in per_rows:
        if int(r.get("failed", 0)) == 0:
            scored_keys.add((str(r.get("example_id")), str(r.get("method"))))

    for r in failure_rows:
        key = (str(r.get("example_id")), str(r.get("method")))
        recovered = "yes" if key in scored_keys else "no"
        lines.append(
            (
                "failures.jsonl",
                str(r.get("timestamp") or ""),
                str(r.get("method") or ""),
                str(r.get("example_id") or ""),
                str(r.get("error") or ""),
                recovered,
                "",
            )
        )

    for r in per_rows:
        err = str(r.get("error") or "").strip()
        if not err:
            continue
        key = (str(r.get("example_id")), str(r.get("method")))
        recovered = "yes" if key in scored_keys and int(r.get("failed", 0)) == 1 else "unknown"
        lines.append(
            (
                "per_example_records",
                str(r.get("timestamp") or ""),
                str(r.get("method") or ""),
                str(r.get("example_id") or ""),
                err,
                recovered,
                "",
            )
        )

    if RUN_LOG.exists():
        for line in RUN_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
            lower = line.lower()
            if any(p.search(lower) for p in ERROR_PATTERNS.values()):
                ts_match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)?)", line)
                ts = ts_match.group(1) if ts_match else ""
                lines.append(("live_log", ts, "", "", line.strip(), "unknown", ""))

    event_rows: List[Dict[str, Any]] = []
    counts = Counter()

    for src, ts, method, example_id, text, recovered, _ in lines:
        matched = [name for name, pat in ERROR_PATTERNS.items() if pat.search(text)]
        for m in matched:
            counts[m] += 1
        if matched:
            for m in matched:
                event_rows.append(
                    {
                        "source": src,
                        "timestamp_utc": ts,
                        "method": method,
                        "example_id": example_id,
                        "error_type": m,
                        "log_snippet": text[:1200],
                        "recovered": recovered,
                    }
                )

    evdf = pd.DataFrame(event_rows)
    if len(evdf):
        evdf = evdf.sort_values(["timestamp_utc", "source", "error_type"])
    evdf.to_csv(OUT_DIR / "cerebras_error_retry_events.csv", index=False)

    retry_vals = [int(r.get("retry_attempts", 0) or 0) for r in per_rows]
    recovery_idx_vals = [int(r.get("recovery_pass_index", 0) or 0) for r in per_rows]

    summary = {
        "error_counts": {k: int(counts.get(k, 0)) for k in ERROR_PATTERNS.keys()},
        "failures_jsonl_rows": int(len(failure_rows)),
        "rows_with_nonempty_error_field": int(sum(1 for r in per_rows if str(r.get("error") or "").strip())),
        "retry_attempts_total": int(sum(retry_vals)),
        "retry_attempts_max": int(max(retry_vals) if retry_vals else 0),
        "rows_with_retry_attempts_gt0": int(sum(1 for x in retry_vals if x > 0)),
        "max_recovery_pass_index_seen": int(max(recovery_idx_vals) if recovery_idx_vals else 0),
        "recovery_pass_rows_gt0": int(sum(1 for x in recovery_idx_vals if x > 0)),
        "total_error_events_extracted": int(len(event_rows)),
    }
    write_json(OUT_DIR / "cerebras_error_retry_summary.json", summary)
    return summary


def analyze_duplicates(per_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    df = pd.DataFrame(per_rows)
    if len(df) == 0:
        write_json(OUT_DIR / "cerebras_duplicate_summary.json", {"duplicate_key_count": 0, "duplicate_row_overage": 0})
        pd.DataFrame([]).to_csv(OUT_DIR / "cerebras_duplicate_rows.csv", index=False)
        return {"duplicate_key_count": 0, "duplicate_row_overage": 0}

    df["key"] = df["example_id"].astype(str) + "||" + df["method"].astype(str)
    dup = df[df.duplicated("key", keep=False)].copy().sort_values(["key", "timestamp"])

    if len(dup):
        out_cols = [
            "key",
            "example_id",
            "method",
            "timestamp",
            "failed",
            "exact_match",
            "error",
            "latency_seconds",
            "retry_attempts",
            "recovery_pass_index",
        ]
        for c in out_cols:
            if c not in dup.columns:
                dup[c] = None
        dup[out_cols].to_csv(OUT_DIR / "cerebras_duplicate_rows.csv", index=False)
    else:
        pd.DataFrame([]).to_csv(OUT_DIR / "cerebras_duplicate_rows.csv", index=False)

    key_counts = df.groupby("key").size()
    summary = {
        "duplicate_key_count": int((key_counts > 1).sum()),
        "duplicate_row_overage": int(key_counts.sum() - key_counts.index.size),
        "duplicate_keys": [k for k, v in key_counts.items() if v > 1][:1000],
        "duplicates_include_failed_rows": bool(int(dup.get("failed", pd.Series(dtype=int)).fillna(0).sum()) > 0) if len(dup) else False,
    }
    write_json(OUT_DIR / "cerebras_duplicate_summary.json", summary)
    return summary


def provider_rows_per_hour(path: Path, label: str) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    rows = read_jsonl(path)
    if not rows:
        return None
    ts = sorted([parse_ts(r.get("timestamp")) for r in rows if parse_ts(r.get("timestamp")) is not None])
    if len(ts) < 2:
        return None
    elapsed = (ts[-1] - ts[0]).total_seconds()
    if elapsed <= 0:
        return None
    rph = len(rows) / (elapsed / 3600.0)
    spr = elapsed / len(rows)
    provider = str(rows[0].get("provider") or "")
    dataset = str(rows[0].get("dataset") or "")
    return {
        "label": label,
        "provider": provider,
        "dataset": dataset,
        "rows": int(len(rows)),
        "first_timestamp_utc": ts[0].isoformat(),
        "last_timestamp_utc": ts[-1].isoformat(),
        "elapsed_hours": elapsed / 3600.0,
        "rows_per_hour": rph,
        "seconds_per_row": spr,
    }


def compare_providers(cerebras_summary: Dict[str, Any]) -> None:
    refs = {
        "cerebras_gsm8k_active": PER_EXAMPLE,
        "cohere_gsm8k_official": REPO_ROOT / "outputs" / "canonical_final300_cohere_contract_matched_live_20260523T181948Z" / "cohere_real_model_cost_normalized_validation_20260523T181948Z" / "per_example_records.jsonl",
        "mistral_gsm8k_official": REPO_ROOT / "outputs" / "merged_repaired_cohere_mistral_selector_replay_20260524" / "mistral_full300_merged_per_example_records.jsonl",
        "mistral_math500_official": REPO_ROOT / "outputs" / "scenarios_5_6_math500_full_tracking_20260524" / "mistral_math500_full_20260524T014937Z" / "cohere_real_model_cost_normalized_validation_20260524T014937Z" / "per_example_records.jsonl",
        "cohere_math500_official": REPO_ROOT / "outputs" / "cohere_math500_official_scenario4_20260524" / "cohere_math500_full_20260524T144902Z" / "per_example_records.jsonl",
    }

    rows = []
    for label, path in refs.items():
        v = provider_rows_per_hour(path, label)
        if v is None:
            rows.append({
                "label": label,
                "provider": None,
                "dataset": None,
                "rows": None,
                "first_timestamp_utc": None,
                "last_timestamp_utc": None,
                "elapsed_hours": None,
                "rows_per_hour": None,
                "seconds_per_row": None,
                "status": "missing_or_incomplete",
            })
        else:
            v["status"] = "available"
            rows.append(v)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "provider_throughput_comparison.csv", index=False)

    cerebras_rph = cerebras_summary.get("rows_per_hour_overall")
    baseline = df[(df["status"] == "available") & (df["label"] != "cerebras_gsm8k_active") & df["rows_per_hour"].notna()]
    slower_note = "undetermined"
    if cerebras_rph and len(baseline):
        med = float(baseline["rows_per_hour"].median())
        slower_note = "yes" if cerebras_rph < med else "no"

    lines = [
        "# Provider Throughput Comparison",
        "",
        f"Cerebras unusually slower vs available completed baselines: **{slower_note}**.",
        "",
        table_text(df),
    ]
    (OUT_DIR / "provider_throughput_comparison.md").write_text("\n".join(lines), encoding="utf-8")


def write_support_message_facts(
    cfg: Dict[str, Any],
    progress: Dict[str, Any],
    hb: Dict[str, Any],
    err: Dict[str, Any],
    dup: Dict[str, Any],
) -> None:
    pwin = pd.read_csv(OUT_DIR / "cerebras_pause_windows.csv") if (OUT_DIR / "cerebras_pause_windows.csv").exists() else pd.DataFrame()
    top_pauses = pwin.sort_values("gap_seconds", ascending=False).head(5) if len(pwin) else pd.DataFrame()

    lines = [
        "# Cerebras Support Message Facts",
        "",
        "- account/org ID: not extracted.",
        f"- model used: {cfg.get('model_name')}",
        "- endpoint type: API (inference, provider=cerebras).",
        f"- job start time (UTC): {cfg.get('start_timestamp_utc')}",
        f"- latest data timestamp (UTC): {progress.get('latest_row_timestamp_utc')}",
        f"- current status: {hb.get('current_status')}",
        f"- current progress: {progress.get('effective_complete_rows')}/{progress.get('expected_rows')} ({progress.get('percent_complete'):.2f}%)",
        f"- average throughput overall: {progress.get('rows_per_hour_overall'):.2f} rows/hour",
        f"- average seconds per row overall: {progress.get('average_seconds_per_row_overall'):.2f} sec/row",
        f"- longest row-gap pause: {progress.get('max_observed_gap_between_rows_minutes'):.2f} minutes",
        f"- latest heartbeat timestamp (UTC): {hb.get('latest_heartbeat_timestamp_utc')}",
        f"- latest heartbeat age: {hb.get('latest_heartbeat_age_seconds'):.1f} sec",
        "- error counts:",
    ]
    for k, v in err.get("error_counts", {}).items():
        lines.append(f"  - {k}: {v}")
    lines += [
        f"- failures.jsonl rows: {err.get('failures_jsonl_rows')}",
        f"- duplicate key count: {dup.get('duplicate_key_count')}",
        f"- duplicate row overage: {dup.get('duplicate_row_overage')}",
        f"- log path: `{RUN_LOG.relative_to(REPO_ROOT)}`",
        f"- per-example path: `{PER_EXAMPLE.relative_to(REPO_ROOT)}`",
        f"- heartbeat path: `{HEARTBEAT.relative_to(REPO_ROOT)}`",
        "",
        "## Longest Pause Windows (UTC)",
        "",
    ]
    if len(top_pauses):
        for _, r in top_pauses.iterrows():
            lines.append(
                f"- {r['pause_start_utc']} -> {r['pause_end_utc']} (gap={r['gap_minutes']:.2f} min, rows_before={int(r['rows_before_pause'])}, rows_after={int(r['rows_after_pause'])})"
            )
    else:
        lines.append("- none detected above 10 minutes.")

    lines += [
        "",
        "## Support Request",
        "",
        "Please confirm whether this account is currently on spare-capacity/queue-limited throughput, whether queue/rate throttling is expected for this workload, and whether a small paid/research quota tier would provide stable sustained throughput.",
        "",
        "Please advise if you need org/account ID, request IDs, or sanitized logs for targeted investigation.",
    ]
    (OUT_DIR / "cerebras_support_message_facts.md").write_text("\n".join(lines), encoding="utf-8")


def write_suggested_email() -> None:
    facts = (OUT_DIR / "cerebras_support_message_facts.md").read_text(encoding="utf-8")
    content = [
        "Subject: Request for help diagnosing very slow sustained Cerebras API throughput",
        "",
        "Hello Cerebras Support,",
        "",
        "I am running benchmark inference for academic research. The API is reachable and requests do complete, but sustained throughput is very slow with long pauses.",
        "",
        "I collected a read-only diagnostics package with exact UTC timestamps and throughput stats.",
        "",
        "Key facts:",
        "",
        facts,
        "",
        "Could you confirm whether this behavior is expected under spare-capacity/free-tier queueing?",
        "If so, is there a recommended path to obtain a stable small research inference quota or paid tier with consistent throughput?",
        "",
        "If useful, I can provide org/account ID and any request IDs/log slices you need.",
        "",
        "Thanks.",
    ]
    (OUT_DIR / "suggested_cerebras_support_email.md").write_text("\n".join(content), encoding="utf-8")


def build_human_report(
    cfg: Dict[str, Any],
    progress: Dict[str, Any],
    hb: Dict[str, Any],
    err: Dict[str, Any],
    dup: Dict[str, Any],
) -> None:
    method_csv = OUT_DIR / "cerebras_method_throughput.csv"
    pause_csv = OUT_DIR / "cerebras_pause_windows.csv"
    provider_csv = OUT_DIR / "provider_throughput_comparison.csv"

    mdf = pd.read_csv(method_csv) if method_csv.exists() else pd.DataFrame()
    pdf = pd.read_csv(pause_csv) if pause_csv.exists() else pd.DataFrame()
    cdf = pd.read_csv(provider_csv) if provider_csv.exists() else pd.DataFrame()

    top_pause_md = "none"
    if len(pdf):
        top = pdf.sort_values("gap_seconds", ascending=False).head(10)
        top_pause_md = table_text(top)

    lines = [
        "# CEREBRAS_SUPPORT_SLOWNESS_DIAGNOSTICS_20260524",
        "",
        "## 1. Executive summary",
        f"Cerebras GSM8K run is {'still running' if hb.get('current_status') == 'running' else 'not running/completed'} with {progress.get('effective_complete_rows')}/{progress.get('expected_rows')} effective rows ({progress.get('percent_complete'):.2f}%).",
        f"Observed throughput: {fmt_float(progress.get('rows_per_hour_overall'))} rows/hour overall, {fmt_float(progress.get('average_seconds_per_row_overall'))} sec/row overall.",
        "",
        "## 2. Current job status",
        f"Latest row timestamp: {progress.get('latest_row_timestamp_utc')}",
        f"Latest heartbeat: {hb.get('latest_heartbeat_timestamp_utc')} (age {hb.get('latest_heartbeat_age_seconds'):.1f}s)",
        f"Heartbeat status: {hb.get('current_status')}",
        "",
        "## 3. Run configuration",
        f"Provider={cfg.get('provider')} model={cfg.get('model_name')} dataset={cfg.get('dataset')} seed={cfg.get('seed')} budget={cfg.get('budget')}",
        f"Methods={', '.join(cfg.get('methods_requested', []))}",
        f"Retry settings={json.dumps(cfg.get('retry_backoff_settings', {}))}",
        f"Run command (redacted)={cfg.get('runner_command_redacted')}",
        "",
        "## 4. Progress/throughput summary",
        f"Total rows written={progress.get('total_rows_written')} effective unique rows={progress.get('effective_complete_rows')} expected={progress.get('expected_rows')} percent={fmt_float(progress.get('percent_complete'))}%",
        f"Rows/hour overall={fmt_float(progress.get('rows_per_hour_overall'))}; rows/hour active-windows={fmt_float(progress.get('rows_per_hour_in_active_windows'))}",
        f"Median/P90/P95/P99 inter-row seconds={progress.get('median_seconds_between_rows')}, {progress.get('p90_seconds_between_rows')}, {progress.get('p95_seconds_between_rows')}, {progress.get('p99_seconds_between_rows')}",
        "",
        "## 5. Method-by-method progress",
        table_text(mdf) if len(mdf) else "no method rows",
        "",
        "## 6. Pause windows and heartbeat gaps",
        top_pause_md,
        "",
        "## 7. API/retry/error evidence",
        json.dumps(err, indent=2),
        "",
        "## 8. Duplicate/integrity notes",
        json.dumps(dup, indent=2),
        "",
        "## 9. Comparison with Cohere/Mistral throughput",
        table_text(cdf) if len(cdf) else "no comparison rows",
        "",
        "## 10. Support-ready facts",
        f"See `{(OUT_DIR / 'cerebras_support_message_facts.md').relative_to(REPO_ROOT)}`.",
        "",
        "## 11. Suggested support message",
        f"See `{(OUT_DIR / 'suggested_cerebras_support_email.md').relative_to(REPO_ROOT)}`.",
        "",
        "## 12. Safety confirmation",
        "Read-only diagnostics only; no API calls; no tmux attach; no active-job modification; no commit/push.",
    ]
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(input_artifacts: List[str], output_files: List[str]) -> None:
    cmd_hist = [
        "state snapshot (pwd/git/tmux/ps)",
        "artifact inventory (find outputs/cerebras_frozen_agreement_only_2of3_validation_20260523 ...)",
        "python scripts/analyze_cerebras_slowness_for_support.py",
    ]
    manifest = {
        "timestamp": now_utc().isoformat(),
        "input_artifacts": input_artifacts,
        "output_files": output_files,
        "commands_run": cmd_hist,
        "api_calls_launched": False,
        "active_jobs_touched": False,
        "secrets_printed": False,
        "limitations": [
            "Analysis is based on currently written artifacts and may evolve while the live Cerebras job continues.",
            "Live log does not embed timestamps on each progress line; exact timing comes from per_example_records/heartbeat timestamps.",
            "Cohere MATH-500 official scenario4 comparison skipped if artifact is absent/incomplete.",
        ],
    }
    write_json(OUT_DIR / "manifest.json", manifest)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    files = list_artifacts()
    build_artifact_inventory(files)

    snapshot = latest_snapshot_file()
    cfg = extract_run_config(snapshot)

    per_rows = read_jsonl(PER_EXAMPLE)
    hb_rows = read_jsonl(HEARTBEAT)

    progress = analyze_progress(per_rows, hb_rows)
    hb = analyze_heartbeat(hb_rows, per_rows)
    err = extract_error_retry_signals(per_rows, hb_rows)
    dup = analyze_duplicates(per_rows)

    compare_providers(progress)
    write_support_message_facts(cfg, progress, hb, err, dup)
    write_suggested_email()
    build_human_report(cfg, progress, hb, err, dup)

    output_files = sorted([str(p.relative_to(REPO_ROOT)) for p in OUT_DIR.glob("*")])
    write_manifest(
        input_artifacts=[str(p.relative_to(REPO_ROOT)) for p in files] + [str(PER_EXAMPLE.relative_to(REPO_ROOT)), str(HEARTBEAT.relative_to(REPO_ROOT)), str(FAILURES.relative_to(REPO_ROOT))],
        output_files=output_files,
    )


if __name__ == "__main__":
    main()
