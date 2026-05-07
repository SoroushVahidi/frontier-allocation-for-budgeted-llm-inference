#!/usr/bin/env python3
"""Orchestrate GSM8K windows to collect PAL+retry failure cases vs three external baselines (Cohere only).

Does not modify experiment/runtime logic — only invokes scripts/run_cohere_real_model_cost_normalized_validation.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

PAL = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"
EXT_L1 = "external_l1_max"
EXT_TALE = "external_tale_prompt_budgeting"
EXT_S1 = "external_s1_budget_forcing"
METHOD_LIST = [PAL, EXT_L1, EXT_TALE, EXT_S1]
METHODS_CSV = ",".join(METHOD_LIST)

RUNNER = REPO_ROOT / "scripts" / "run_cohere_real_model_cost_normalized_validation.py"
DEFAULT_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

DATASET = "openai/gsm8k"
SEED = 20260501
BUDGET = 6
WINDOW_SIZE = 60
CALL_CAP = 3000
PREFERRED_TARGET = 45
START_SUFFIX = 1072
END_SUFFIX = 1318

RANGE_300 = {f"openai_gsm8k_{i}" for i in range(772, 1072)}  # 772..1071 inclusive
RANGE_30 = {f"openai_gsm8k_{i}" for i in range(50, 80)}  # 50..79


def load_corpus_ids(repo: Path) -> set[str]:
    p = repo / "outputs" / "failure_case_corpus_20260507" / "failure_cases.csv"
    if not p.exists():
        return set()
    out: set[str] = set()
    with p.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            out.add(str(row.get("example_id", "")))
    return out


def build_candidates(repo: Path) -> tuple[list[str], dict[str, Any]]:
    corpus = load_corpus_ids(repo)
    cands: list[str] = []
    overlap_corpus: list[str] = []
    for suf in range(START_SUFFIX, END_SUFFIX + 1):
        eid = f"openai_gsm8k_{suf}"
        if eid in corpus:
            overlap_corpus.append(eid)
            continue
        cands.append(eid)
    meta = {
        "corpus_overlap_skipped": overlap_corpus,
        "corpus_path": str(repo / "outputs" / "failure_case_corpus_20260507" / "failure_cases.csv"),
    }
    return cands, meta


def write_allowlist(path: Path, example_ids: list[str]) -> None:
    lines: list[str] = []
    for eid in example_ids:
        for m in METHOD_LIST:
            lines.append(
                json.dumps(
                    {"dataset": DATASET, "seed": SEED, "budget": BUDGET, "method": m, "example_id": eid},
                    ensure_ascii=False,
                )
            )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def sum_logical_calls(jsonl: Path) -> int:
    if not jsonl.exists():
        return 0
    tot = 0
    with jsonl.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            tot += int(json.loads(line).get("cohere_logical_api_calls") or 0)
    return tot


def run_runner(
    *,
    python_exe: Path,
    bundle_dir: Path,
    inner_ts: str,
    allow_path: Path,
    n_cases: int,
    remaining_cap: int,
    resume: bool,
    dry_run: bool,
) -> None:
    rel_out = bundle_dir.relative_to(REPO_ROOT)
    cmd: list[str | Path] = [
        python_exe,
        RUNNER,
        "--providers",
        "cohere",
        "--datasets",
        DATASET,
        "--seeds",
        str(SEED),
        "--budgets",
        str(BUDGET),
        "--methods",
        METHODS_CSV,
        "--target-scored-per-slice",
        str(n_cases),
        "--max-examples",
        str(n_cases),
        "--allowed-example-ids-file",
        str(allow_path),
        "--max-total-api-calls",
        str(remaining_cap),
        "--timestamp",
        inner_ts,
        "--output-root",
        str(rel_out),
    ]
    if resume:
        cmd.append("--resume")
    if dry_run:
        cmd.append("--dry-run-call-plan")
    env = {**os.environ}
    # Runner checks COHERE_API_KEY or CO_API_KEY
    print("[collect] Running:", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run(cmd, cwd=REPO_ROOT, check=True, env=env)


def validate_methods(python_exe: Path) -> None:
    cmd = [
        python_exe,
        RUNNER,
        "--validate-methods-only",
        "--providers",
        "cohere",
        "--datasets",
        DATASET,
        "--seeds",
        str(SEED),
        "--budgets",
        str(BUDGET),
        "--methods",
        METHODS_CSV,
        "--timestamp",
        "validate_methods_only",
        "--output-root",
        "outputs/_tmp_method_validate",
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def windows_from_candidates(cands: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    i = 0
    while i < len(cands):
        out.append(cands[i : i + WINDOW_SIZE])
        i += WINDOW_SIZE
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle-timestamp", default="", help="UTC suffix e.g. 20260507T161935Z (default: now)")
    ap.add_argument("--python", default=str(DEFAULT_PYTHON), help="Python executable")
    ap.add_argument("--dry-run-only", action="store_true", help="Only write call_plan + first-window dry-run")
    ap.add_argument("--skip-dry-run", action="store_true")
    ap.add_argument("--skip-live", action="store_true")
    args = ap.parse_args()

    python_exe = Path(args.python)
    repo = REPO_ROOT
    ts = args.bundle_timestamp.strip() or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_dir = repo / "outputs" / f"cohere_collect_pal_failure_cases_vs_3_external_{ts}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    inner_validation = bundle_dir / f"cohere_real_model_cost_normalized_validation_{ts}"
    per_path = inner_validation / "per_example_records.jsonl"

    cands, cmeta = build_candidates(repo)
    windows = windows_from_candidates(cands)
    if not windows:
        print("No candidate cases after exclusions.", file=sys.stderr)
        raise SystemExit(2)

    # Validate method IDs resolve (no API)
    validate_methods(python_exe)

    # Estimated calls: pilot ~1.87 calls / row; 4 methods * N cases rows per window
    est_per_row = 1.87
    plan_windows = []
    total_est = 0
    for wi, win in enumerate(windows, start=1):
        rows = len(win) * 4
        est = int(rows * est_per_row) + 1
        plan_windows.append({"window_index": wi, "case_count": len(win), "rows": rows, "estimated_logical_calls": est})
        total_est += est

    env_names = []
    for name in ("COHERE_API_KEY", "CO_API_KEY", "HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        if os.getenv(name):
            env_names.append(name)

    call_plan_pre = {
        "windows_planned": len(windows),
        "window_size_target": WINDOW_SIZE,
        "methods_per_case": METHOD_LIST,
        "rows_per_case": 4,
        "estimated_logical_calls_per_row_prior_run": est_per_row,
        "estimated_total_logical_calls_all_windows": total_est,
        "hard_cap_logical_calls": CALL_CAP,
        "abort_conditions": [
            "Unknown method ID in METHODS registry",
            "Provider not cohere",
            "max_total_api_calls exhausted",
            "45 preferred failures (PAL wrong ∧ ≥1 external correct) collected (stop scheduling new windows)",
        ],
        "windows": plan_windows,
        "case_selection": {
            "dataset": DATASET,
            "seed": SEED,
            "budget": BUDGET,
            "id_suffix_range_inclusive": [START_SUFFIX, END_SUFFIX],
            "exclude_prior_300_case_band_openai_gsm8k_772_1071": True,
            "exclude_prior_30_case_pilot_band_openai_gsm8k_50_79": True,
            "exclude_failure_case_corpus_20260507": True,
            "corpus_skipped_ids": cmeta.get("corpus_overlap_skipped", []),
        },
    }
    (bundle_dir / "call_plan.json").write_text(json.dumps(call_plan_pre, indent=2) + "\n", encoding="utf-8")

    commands_log: list[str] = []

    if not args.skip_dry_run:
        w1 = windows[0]
        allow1 = bundle_dir / "allowlist_window_001.jsonl"
        write_allowlist(allow1, w1)
        cmd_note = f"dry-run window 1 n={len(w1)}"
        run_runner(
            python_exe=python_exe,
            bundle_dir=bundle_dir,
            inner_ts=ts,
            allow_path=allow1,
            n_cases=len(w1),
            remaining_cap=CALL_CAP,
            resume=False,
            dry_run=True,
        )
        commands_log.append(cmd_note)

    if args.dry_run_only:
        print(f"Dry-run-only complete. Bundle: {bundle_dir}")
        raise SystemExit(0)

    if args.skip_live:
        raise SystemExit(0)

    cohere_ok = bool(os.getenv("COHERE_API_KEY") or os.getenv("CO_API_KEY"))
    if not cohere_ok:
        print("No COHERE_API_KEY or CO_API_KEY; skipping live collection.", file=sys.stderr)
        raise SystemExit(3)

    preferred_ordered: list[str] = []
    evaluated_case_order: list[str] = []
    calls_used = 0

    def index_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        by_case: dict[str, dict[str, dict[str, Any]]] = {}
        for r in rows:
            if int(r.get("scored", 0)) != 1:
                continue
            eid = str(r["example_id"])
            by_case.setdefault(eid, {})[str(r["method"])] = r
        return by_case

    def preferred_in_window_order(win: list[str], by_case: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
        out: list[str] = []
        for eid in win:
            blk = by_case.get(eid, {})
            if len(blk) < 4:
                continue
            pal_r = blk[PAL]
            ok_p = int(pal_r.get("exact_match") or 0)
            ok1 = int(blk[EXT_L1].get("exact_match") or 0)
            ok2 = int(blk[EXT_TALE].get("exact_match") or 0)
            ok3 = int(blk[EXT_S1].get("exact_match") or 0)
            ext_any = max(ok1, ok2, ok3)
            if not ok_p and ext_any:
                out.append(eid)
        return out

    for wi, win in enumerate(windows, start=1):
        allow_path = bundle_dir / f"allowlist_window_{wi:03d}.jsonl"
        write_allowlist(allow_path, win)
        remaining = CALL_CAP - calls_used
        if remaining <= 0:
            print("[collect] Call cap reached before window", wi, flush=True)
            break
        resume = per_path.exists() and per_path.stat().st_size > 0
        cmd_note = f"live window {wi} n={len(win)} resume={resume} remaining_cap={remaining}"
        run_runner(
            python_exe=python_exe,
            bundle_dir=bundle_dir,
            inner_ts=ts,
            allow_path=allow_path,
            n_cases=len(win),
            remaining_cap=remaining,
            resume=resume,
            dry_run=False,
        )
        commands_log.append(cmd_note)
        calls_used = sum_logical_calls(per_path)
        # Load records for classification
        rows = [json.loads(x) for x in per_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        by_case = index_rows(rows)
        new_prefs = preferred_in_window_order(win, by_case)
        for eid in win:
            if eid not in evaluated_case_order:
                evaluated_case_order.append(eid)
        for p in new_prefs:
            if p not in preferred_ordered:
                preferred_ordered.append(p)
        print(
            f"[collect] After window {wi}: logical_calls={calls_used} preferred_unique={len(preferred_ordered)}",
            flush=True,
        )
        if len(preferred_ordered) >= PREFERRED_TARGET:
            print("[collect] Preferred failure target reached; stopping.", flush=True)
            break

    state_path = bundle_dir / "collection_state.json"
    state_path.write_text(
        json.dumps(
            {
                "bundle_timestamp": ts,
                "evaluated_case_ids_in_order": evaluated_case_order,
                "preferred_failure_ids_in_order": preferred_ordered,
                "logical_calls_total": calls_used,
                "call_cap": CALL_CAP,
                "commands": commands_log,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Collection phase done. Bundle: {bundle_dir} calls={calls_used}")


if __name__ == "__main__":
    main()
