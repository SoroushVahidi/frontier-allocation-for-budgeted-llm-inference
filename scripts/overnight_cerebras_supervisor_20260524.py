"""
Overnight Cerebras supervisor — 2026-05-24

State machine:
  monitoring_gsm8k   → waiting for Cerebras × GSM8K to complete
  processing_gsm8k   → offline processing after GSM8K completion
  launching_s6       → launching Cerebras × MATH-500 Scenario 6
  done               → Scenario 6 launched; supervisor exits
  failed             → something went wrong; no Scenario 6 launched; safe exit

Safety guarantees:
  - Never kills, restarts, or modifies the running Cerebras GSM8K job.
  - Never launches two concurrent Cerebras API jobs.
  - Never launches Cohere or Mistral paid jobs.
  - Writes all actions to supervisor.log and supervisor_status.jsonl.
  - If anything is ambiguous, writes blocked report and exits safely.
"""

import collections
import csv
import datetime
import json
import os
import random
import signal
import subprocess
import sys
import time

# ── Config ─────────────────────────────────────────────────────────────────

REPO_ROOT = "/home/soroush/frontier-allocation-for-budgeted-llm-inference"
SUPERVISOR_OUT = os.path.join(REPO_ROOT, "outputs/overnight_cerebras_supervisor_20260524")
STATUS_JSONL = os.path.join(SUPERVISOR_OUT, "supervisor_status.jsonl")
MANIFEST_PATH = os.path.join(SUPERVISOR_OUT, "manifest.json")

# Cerebras GSM8K job
GSM8K_LOG = os.path.join(
    REPO_ROOT,
    "outputs/cerebras_frozen_agreement_only_2of3_validation_20260523",
    "live_validation_20260523T144414Z.log",
)
GSM8K_PER_EXAMPLE = os.path.join(
    REPO_ROOT,
    "outputs/cerebras_frozen_agreement_only_2of3_validation_20260523",
    "cohere_real_model_cost_normalized_validation_20260523T144414Z",
    "per_example_records.jsonl",
)
GSM8K_HEARTBEAT = os.path.join(
    REPO_ROOT,
    "outputs/cerebras_frozen_agreement_only_2of3_validation_20260523",
    "cohere_real_model_cost_normalized_validation_20260523T144414Z",
    "progress_heartbeat.jsonl",
)
GSM8K_FAILURES = os.path.join(
    REPO_ROOT,
    "outputs/cerebras_frozen_agreement_only_2of3_validation_20260523",
    "cohere_real_model_cost_normalized_validation_20260523T144414Z",
    "raw",
    "failures.jsonl",
)
# Known GSM8K PIDs (for initial verification only — we don't signal or kill these)
KNOWN_GSM8K_PIDS = {2195504, 2195513}

# Scenario 6 (Cerebras × MATH-500)
S6_SHARED_EXACT_CASES = os.path.join(
    REPO_ROOT,
    "outputs/scenarios_5_6_math500_full_tracking_20260524",
    "math500_shared_exact_cases.jsonl",
)
S6_ALLOWED_IDS = os.path.join(
    REPO_ROOT,
    "outputs/scenarios_5_6_math500_full_tracking_20260524",
    "math500_shared_allowed_ids.jsonl",
)
S6_TRACKING_ROOT = os.path.join(
    REPO_ROOT,
    "outputs/scenarios_5_6_math500_full_tracking_20260524",
)
RUNNER_SCRIPT = os.path.join(REPO_ROOT, "scripts/run_cohere_real_model_cost_normalized_validation.py")

# Processing output root for GSM8K
GSM8K_PROCESSING_ROOT = os.path.join(REPO_ROOT, "outputs/cerebras_gsm8k_completed_processing_20260524")

# Polling interval
POLL_INTERVAL_SECONDS = 600  # 10 minutes
# Stall threshold — if heartbeat age > this, mark possibly_stalled
STALL_THRESHOLD_SECONDS = 3600  # 60 minutes (cerebras can be slow; use generous threshold)

ALL_METHODS = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]
METHOD_SHORT = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "L1",
    "external_s1_budget_forcing": "S1",
    "external_tale_prompt_budgeting": "TALE",
}


# ── Logging helpers ───────────────────────────────────────────────────────────

def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str):
    ts = utcnow()
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def write_status(event: str, **kwargs):
    record = {"timestamp": utcnow(), "event": event, **kwargs}
    with open(STATUS_JSONL, "a") as f:
        f.write(json.dumps(record) + "\n")
    log(f"STATUS: {event} {json.dumps(kwargs)[:200]}")


def write_manifest(state: str, **kwargs):
    manifest = {
        "created_utc": utcnow(),
        "supervisor_script": "scripts/overnight_cerebras_supervisor_20260524.py",
        "state": state,
        "api_calls_launched_cohere": False,
        "api_calls_launched_mistral": False,
        "active_jobs_touched": False,
        **kwargs,
    }
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


# ── GSM8K monitoring helpers ──────────────────────────────────────────────────

def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def any_cerebras_gsm8k_pid_alive() -> bool:
    """Check if any of the known Cerebras GSM8K PIDs are still alive."""
    return any(is_pid_alive(p) for p in KNOWN_GSM8K_PIDS)


def find_active_cerebras_pids() -> list[int]:
    """Scan process list for Cerebras GSM8K validation PIDs."""
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,cmd"],
            capture_output=True, text=True, timeout=10,
        )
        pids = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) < 2:
                continue
            pid_s, cmd = parts
            if (
                "run_cohere_real_model_cost_normalized_validation" in cmd
                and "cerebras" in cmd
                and "gsm8k" in cmd
            ):
                try:
                    pids.append(int(pid_s))
                except ValueError:
                    pass
        return pids
    except Exception:
        return []


def log_done_in_gsm8k() -> bool:
    if not os.path.exists(GSM8K_LOG):
        return False
    try:
        with open(GSM8K_LOG, "rb") as f:
            # Only read last 4KB for efficiency
            f.seek(max(0, os.path.getsize(GSM8K_LOG) - 4096))
            tail = f.read().decode("utf-8", errors="replace")
        return "[done]" in tail
    except Exception:
        return False


def gsm8k_log_age_seconds() -> float:
    """Seconds since the GSM8K log was last modified."""
    try:
        return time.time() - os.path.getmtime(GSM8K_LOG)
    except Exception:
        return float("inf")


def heartbeat_age_seconds() -> float:
    """Age of the most recent heartbeat entry."""
    try:
        lines = [l for l in open(GSM8K_HEARTBEAT) if l.strip()]
        if not lines:
            return float("inf")
        last = json.loads(lines[-1])
        ts_str = last.get("timestamp", "")
        if not ts_str:
            return float("inf")
        ts = datetime.datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        return (now - ts).total_seconds()
    except Exception:
        return float("inf")


def read_gsm8k_rows():
    """Load per-example records; return (all_rows, scored_rows, method_counts)."""
    try:
        rows = [json.loads(l) for l in open(GSM8K_PER_EXAMPLE) if l.strip()]
    except Exception:
        return [], [], {}
    scored = [r for r in rows if r.get("status") == "scored"]
    method_counts = dict(collections.Counter(r.get("method", "") for r in scored))
    return rows, scored, method_counts


def gsm8k_appears_complete() -> bool:
    """True if [done] is in log AND all four method counts are ≥ 300."""
    if not log_done_in_gsm8k():
        return False
    _, _, mc = read_gsm8k_rows()
    return all(mc.get(m, 0) >= 300 for m in ALL_METHODS)


# ── GSM8K post-processing (runs offline, no API calls) ───────────────────────

def bootstrap_ci(vals, n_boot=2000, seed=42):
    rng = random.Random(seed)
    n = len(vals)
    if n == 0:
        return float("nan"), float("nan")
    boot = [sum(rng.choices(vals, k=n)) / n for _ in range(n_boot)]
    boot.sort()
    return boot[int(0.025 * n_boot)], boot[int(0.975 * n_boot)]


def majority_vote(answers):
    c = collections.Counter(a for a in answers if a is not None)
    return c.most_common(1)[0][0] if c else None


def process_gsm8k_offline():
    """
    Full offline processing of the completed Cerebras × GSM8K run.
    Returns True on success, False on critical failure.
    """
    log("=== Starting Cerebras GSM8K offline processing ===")
    os.makedirs(GSM8K_PROCESSING_ROOT, exist_ok=True)
    os.makedirs(os.path.join(GSM8K_PROCESSING_ROOT, "cerebras_gsm8k_failure_case_logs"), exist_ok=True)

    def wp(name):
        return os.path.join(GSM8K_PROCESSING_ROOT, name)

    # ── Load and deduplicate ────────────────────────────────────────────────
    log("Loading GSM8K per-example records...")
    try:
        all_rows = [json.loads(l) for l in open(GSM8K_PER_EXAMPLE) if l.strip()]
    except Exception as e:
        log(f"ERROR loading per-example records: {e}")
        return False

    # Dedup: prefer scored over failed; if both scored, prefer later row (index wins)
    def row_key(r):
        return (r.get("example_id", ""), r.get("method", ""))

    dedup_best = {}
    dup_log = []
    for r in all_rows:
        k = row_key(r)
        if k not in dedup_best:
            dedup_best[k] = r
        else:
            old = dedup_best[k]
            old_scored = int(old.get("status") == "scored")
            new_scored = int(r.get("status") == "scored")
            if new_scored > old_scored or (new_scored == old_scored == 1):
                # Prefer new (recovery/later) scored over old failed, or prefer later scored
                dup_log.append({
                    "example_id": r.get("example_id"),
                    "method": r.get("method"),
                    "kept": "new/later",
                    "old_status": old.get("status"),
                    "new_status": r.get("status"),
                })
                dedup_best[k] = r
            else:
                dup_log.append({
                    "example_id": r.get("example_id"),
                    "method": r.get("method"),
                    "kept": "old",
                    "old_status": old.get("status"),
                    "new_status": r.get("status"),
                })

    merged = list(dedup_best.values())
    scored_rows = [r for r in merged if r.get("status") == "scored"]

    with open(wp("cerebras_gsm8k_duplicate_resolution.csv"), "w", newline="") as f:
        if dup_log:
            w = csv.DictWriter(f, fieldnames=["example_id", "method", "kept", "old_status", "new_status"])
            w.writeheader()
            w.writerows(dup_log)
        else:
            f.write("example_id,method,kept,old_status,new_status\n")

    # ── Integrity check ─────────────────────────────────────────────────────
    log("Running integrity check...")
    per_ex = collections.defaultdict(dict)
    for r in scored_rows:
        per_ex[r.get("example_id", "")][r.get("method", "")] = r

    complete_eids = sorted(
        eid for eid, mmap in per_ex.items()
        if all(m in mmap for m in ALL_METHODS)
    )
    n_complete = len(complete_eids)
    method_counts = {m: sum(1 for r in scored_rows if r.get("method") == m) for m in ALL_METHODS}
    dup_pairs = [(k, v) for k, v in collections.Counter(
        (r.get("example_id"), r.get("method")) for r in scored_rows
    ).items() if v > 1]
    fail_rows = [r for r in merged if r.get("status") != "scored"]

    integrity = {
        "total_raw_rows": len(all_rows),
        "after_dedup_rows": len(merged),
        "scored_rows": len(scored_rows),
        "complete_examples": n_complete,
        "method_counts": method_counts,
        "duplicate_pairs_after_dedup": len(dup_pairs),
        "failed_rows": len(fail_rows),
        "log_done": log_done_in_gsm8k(),
        "integrity_pass": (n_complete >= 295 and len(dup_pairs) == 0 and log_done_in_gsm8k()),
    }
    with open(wp("cerebras_gsm8k_integrity_summary.json"), "w") as f:
        json.dump(integrity, f, indent=2)
    log(f"Integrity: {'PASS' if integrity['integrity_pass'] else 'FAIL'} | {n_complete} complete examples")

    if not integrity["integrity_pass"]:
        log("WARNING: integrity check failed — check cerebras_gsm8k_integrity_summary.json")
        if n_complete < 200:
            log("ERROR: fewer than 200 complete examples — stopping before Scenario 6 launch")
            return False

    # Method counts CSV
    with open(wp("cerebras_gsm8k_method_counts.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["method", "scored_count"])
        w.writeheader()
        w.writerows({"method": m, "scored_count": method_counts.get(m, 0)} for m in ALL_METHODS)

    # Failed rows
    with open(wp("cerebras_gsm8k_failure_rows.csv"), "w", newline="") as f:
        if fail_rows:
            keys = ["example_id", "method", "status", "failure_tag", "error"]
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(fail_rows)
        else:
            f.write("example_id,method,status,failure_tag,error\n")

    # ── Method accuracy ─────────────────────────────────────────────────────
    log("Computing method accuracy...")
    example_map = {eid: per_ex[eid] for eid in complete_eids}
    method_accs = {}
    acc_rows = []
    for m in ALL_METHODS:
        vals = [r.get("exact_match", 0) for eid in complete_eids for r in [example_map[eid].get(m, {})] if r]
        acc = sum(vals) / len(vals) if vals else 0.0
        ci_lo, ci_hi = bootstrap_ci(vals)
        method_accs[m] = acc
        acc_rows.append({
            "method": m,
            "short": METHOD_SHORT[m],
            "n": len(vals),
            "correct": sum(vals),
            "accuracy": round(acc, 6),
            "accuracy_pct": round(acc * 100, 2),
            "ci95_lo": round(ci_lo * 100, 2),
            "ci95_hi": round(ci_hi * 100, 2),
        })
    acc_rows.sort(key=lambda r: -r["accuracy"])
    with open(wp("cerebras_gsm8k_method_accuracy_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["method", "short", "n", "correct", "accuracy", "accuracy_pct", "ci95_lo", "ci95_hi"])
        w.writeheader()
        w.writerows(acc_rows)

    sorted_methods = sorted(method_accs, key=method_accs.get, reverse=True)
    best = sorted_methods[0]
    second = sorted_methods[1]
    spread_1_2 = method_accs[best] - method_accs[second]
    spread_best_worst = method_accs[best] - method_accs[sorted_methods[-1]]
    if spread_1_2 > 0.15:
        regime = "dominant_source"
    elif spread_1_2 < 0.05:
        regime = "near_peer"
    else:
        regime = "mixed"
    regime_summary = {
        "regime": regime,
        "best_source": best,
        "best_acc": round(method_accs[best], 6),
        "second_source": second,
        "second_acc": round(method_accs[second], 6),
        "spread_1_2_pp": round(spread_1_2 * 100, 3),
        "spread_best_worst_pp": round(spread_best_worst * 100, 3),
        "s1_dominant": method_accs["external_s1_budget_forcing"] == max(method_accs.values()),
        "n_examples": n_complete,
    }
    with open(wp("cerebras_gsm8k_regime_summary.json"), "w") as f:
        json.dump(regime_summary, f, indent=2)
    log(f"Regime: {regime} | best={METHOD_SHORT[best]} ({method_accs[best]*100:.2f}%)")

    # ── Selector replay ─────────────────────────────────────────────────────
    log("Running selector replay...")

    alpha_prior = beta_prior = 2.0
    def shrink(acc, n_total):
        return (acc * n_total + alpha_prior) / (n_total + alpha_prior + beta_prior)

    shrunk = {m: shrink(method_accs[m], n_complete) for m in ALL_METHODS}
    shrunk_best = max(shrunk, key=shrunk.get)
    shrunk_spread = shrunk[shrunk_best] - sorted(shrunk.values(), reverse=True)[1]

    sel_agg = collections.defaultdict(list)
    case_rows = []

    for eid in complete_eids:
        mmap = example_map[eid]
        answers = {m: mmap[m].get("final_answer_canonical") for m in ALL_METHODS}
        correct = {m: int(mmap[m].get("exact_match", 0)) for m in ALL_METHODS}

        # Pooled4
        pool_ans = majority_vote(list(answers.values()))
        pooled4_correct = int(any(correct[m] for m in ALL_METHODS if answers[m] == pool_ans))

        # Agreement 2of3 vs frontier
        frontier_ans = answers["direct_reserve_semantic_frontier_v2"]
        non_f = [answers[m] for m in ALL_METHODS if m != "direct_reserve_semantic_frontier_v2"]
        agree_cnt = sum(1 for a in non_f if a == frontier_ans)
        agreement_correct = correct["direct_reserve_semantic_frontier_v2"] if agree_cnt >= 2 else pooled4_correct

        # Always S1
        always_s1_correct = correct["external_s1_budget_forcing"]

        # Raw spread regime
        raw_spread = spread_1_2
        raw_regime_correct = correct[best] if raw_spread > 0.07 else pooled4_correct

        # Beta shrinkage regime
        beta_correct = correct[shrunk_best] if shrunk_spread > 0.07 else pooled4_correct

        # Dominant source veto
        dominant_veto_correct = correct[best] if spread_1_2 > 0.15 else pooled4_correct

        # Oracle
        oracle_src = int(any(correct.values()))
        oracle_act = int(any(correct.values()))

        selectors = {
            "direct_reserve_semantic_frontier_v2": correct["direct_reserve_semantic_frontier_v2"],
            "external_l1_max": correct["external_l1_max"],
            "external_s1_budget_forcing": correct["external_s1_budget_forcing"],
            "external_tale_prompt_budgeting": correct["external_tale_prompt_budgeting"],
            "pooled4_with_fallback": pooled4_correct,
            "agreement_only_2of3_against_frontier": agreement_correct,
            "always_s1": always_s1_correct,
            "raw_spread_regime_selector": raw_regime_correct,
            "beta_shrinkage_regime_selector": beta_correct,
            "dominant_source_veto": dominant_veto_correct,
            "oracle_best_source": oracle_src,
            "oracle_best_action": oracle_act,
        }

        for sname, val in selectors.items():
            sel_agg[sname].append(val)

        case_rows.append({
            "example_id": eid,
            **{f"{m}_correct": correct[m] for m in ALL_METHODS},
            **{sname: val for sname, val in selectors.items()},
            "all_correct": int(all(correct.values())),
            "all_wrong": int(not any(correct.values())),
        })

    with open(wp("cerebras_gsm8k_case_level_selector_results.csv"), "w", newline="") as f:
        fieldnames = ["example_id"] + [f"{m}_correct" for m in ALL_METHODS] + list(case_rows[0].keys() - {"example_id"} - {f"{m}_correct" for m in ALL_METHODS})
        w = csv.DictWriter(f, fieldnames=list(case_rows[0].keys()), extrasaction="ignore")
        w.writeheader()
        w.writerows(case_rows)

    frontier_acc = sum(sel_agg["direct_reserve_semantic_frontier_v2"]) / n_complete
    sel_summary_rows = []
    for sname, vals in sorted(sel_agg.items(), key=lambda x: -sum(x[1])):
        acc = sum(vals) / len(vals)
        sel_summary_rows.append({
            "selector": sname,
            "n": len(vals),
            "correct": sum(vals),
            "accuracy_pct": round(acc * 100, 2),
            "delta_vs_frontier_pp": round((acc - frontier_acc) * 100, 3),
        })
    with open(wp("cerebras_gsm8k_selector_replay_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["selector", "n", "correct", "accuracy_pct", "delta_vs_frontier_pp"])
        w.writeheader()
        w.writerows(sel_summary_rows)

    log("Selector replay complete:")
    for row in sel_summary_rows[:6]:
        log(f"  {row['selector'][:45]:45s} {row['accuracy_pct']:5.2f}%  Δfrontier={row['delta_vs_frontier_pp']:+.2f}pp")

    # ── Failure cases ────────────────────────────────────────────────────────
    log("Extracting failure cases...")
    our_algo = "beta_shrinkage_regime_selector"
    all_wrong_eids = [r["example_id"] for r in case_rows if r.get("all_wrong")]
    our_wrong_oracle_correct = [r["example_id"] for r in case_rows if not r.get(our_algo) and r.get("oracle_best_action")]
    pooled4_wrong_oracle = [r["example_id"] for r in case_rows if not r.get("pooled4_with_fallback") and r.get("oracle_best_action")]
    s1_correct_our_wrong = [r["example_id"] for r in case_rows if r.get("external_s1_budget_forcing") and not r.get(our_algo)]

    fail_summary_rows = [
        {"failure_set": "all_sources_wrong", "count": len(all_wrong_eids), "pct": round(len(all_wrong_eids)/n_complete*100, 2)},
        {"failure_set": "our_algorithm_wrong_oracle_correct", "count": len(our_wrong_oracle_correct), "pct": round(len(our_wrong_oracle_correct)/n_complete*100, 2)},
        {"failure_set": "pooled4_wrong_oracle_correct", "count": len(pooled4_wrong_oracle), "pct": round(len(pooled4_wrong_oracle)/n_complete*100, 2)},
        {"failure_set": "S1_correct_our_algorithm_wrong", "count": len(s1_correct_our_wrong), "pct": round(len(s1_correct_our_wrong)/n_complete*100, 2)},
    ]
    with open(wp("cerebras_gsm8k_failure_taxonomy_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["failure_set", "count", "pct"])
        w.writeheader()
        w.writerows(fail_summary_rows)

    # ── Source ranking markdown ──────────────────────────────────────────────
    ranking_md = f"""# Cerebras × GSM8K — Source Ranking and Regime

**Dataset:** `openai/gsm8k` (Scenario 3, seed=71, {n_complete} complete examples)
**Provider/model:** Cerebras / llama3.1-8b

## Method Accuracy Ranking

| Rank | Method | Short | Accuracy |
|---|---|---|---|
"""
    for i, row in enumerate(acc_rows, 1):
        ranking_md += f"| {i} | {row['method']} | {row['short']} | {row['accuracy_pct']}% |\n"
    ranking_md += f"\n## Regime: `{regime}`\n"
    ranking_md += f"- Best–second spread: {spread_1_2*100:.2f}pp\n"
    ranking_md += f"- Best–worst spread: {spread_best_worst*100:.2f}pp\n"
    ranking_md += f"- S1 dominant: {regime_summary['s1_dominant']}\n"

    with open(wp("cerebras_gsm8k_source_ranking_and_regime.md"), "w") as f:
        f.write(ranking_md)

    # ── Human report ────────────────────────────────────────────────────────
    oracle_acc = sum(sel_agg["oracle_best_action"]) / n_complete * 100
    best_sel_acc = max(row["accuracy_pct"] for row in sel_summary_rows if "oracle" not in row["selector"])
    best_sel_name = next(row["selector"] for row in sel_summary_rows if row["accuracy_pct"] == best_sel_acc and "oracle" not in row["selector"])

    report_md = f"""# Cerebras × GSM8K — Completed Processing Report

**Processing timestamp:** {utcnow()}
**Source artifact:** `outputs/cerebras_frozen_agreement_only_2of3_validation_20260523`
**Processing output:** `outputs/cerebras_gsm8k_completed_processing_20260524/`

## Integrity

| Field | Value |
|---|---|
| Total raw rows | {integrity['total_raw_rows']} |
| After deduplication | {integrity['after_dedup_rows']} |
| Scored rows | {integrity['scored_rows']} |
| Complete examples (all 4 methods) | **{n_complete}** |
| Duplicate pairs resolved | {len(dup_log)} |
| Failed rows | {len(fail_rows)} |
| `[done]` in log | {integrity['log_done']} |
| **Integrity pass** | **{'PASS' if integrity['integrity_pass'] else 'FAIL'}** |

## Method Accuracies

| Method | Accuracy |
|---|---|
"""
    for row in acc_rows:
        report_md += f"| {row['short']} | {row['accuracy_pct']}% |\n"

    report_md += f"\n## Regime: `{regime}`\n\n"
    report_md += f"- Best source: {METHOD_SHORT[best]} ({method_accs[best]*100:.2f}%)\n"
    report_md += f"- Best–second spread: {spread_1_2*100:.2f}pp\n"
    report_md += f"- S1 dominant: {regime_summary['s1_dominant']}\n\n"

    report_md += f"## Selector Results (top)\n\n| Selector | Accuracy |\n|---|---|\n"
    for row in sel_summary_rows[:8]:
        report_md += f"| {row['selector']} | {row['accuracy_pct']}% |\n"

    report_md += f"\n## Failure Taxonomy\n\n| Set | Count | % |\n|---|---|---|\n"
    for row in fail_summary_rows:
        report_md += f"| {row['failure_set']} | {row['count']} | {row['pct']}% |\n"

    report_md += f"\n## Safety\n\nNo API calls. No job interruptions. Offline processing only.\n"

    with open(os.path.join(REPO_ROOT, "docs/CEREBRAS_GSM8K_COMPLETED_PROCESSING_20260524.md"), "w") as f:
        f.write(report_md)

    log(f"GSM8K processing complete. n_complete={n_complete}, regime={regime}, best={METHOD_SHORT[best]} {method_accs[best]*100:.2f}%")
    write_status("gsm8k_processing_complete",
                 n_complete=n_complete,
                 regime=regime,
                 best_method=METHOD_SHORT[best],
                 best_acc=round(method_accs[best]*100, 2))
    return True


# ── Scenario 6 launch ─────────────────────────────────────────────────────────

def verify_scenario6_preconditions() -> tuple[bool, str]:
    """Returns (ok, reason)."""
    # Check shared case files
    if not os.path.exists(S6_SHARED_EXACT_CASES):
        return False, f"Missing shared exact cases: {S6_SHARED_EXACT_CASES}"
    if not os.path.exists(S6_ALLOWED_IDS):
        return False, f"Missing allowed IDs: {S6_ALLOWED_IDS}"
    # Verify case count
    n_cases = sum(1 for l in open(S6_SHARED_EXACT_CASES) if l.strip())
    if n_cases < 290 or n_cases > 310:
        return False, f"Unexpected case count in shared exact cases: {n_cases} (expected ~300)"
    # Verify no active Cerebras process
    active_pids = find_active_cerebras_pids()
    if active_pids:
        return False, f"Active Cerebras PIDs still running: {active_pids}"
    # Verify runner script exists
    if not os.path.exists(RUNNER_SCRIPT):
        return False, f"Runner script missing: {RUNNER_SCRIPT}"
    return True, "ok"


def launch_scenario6() -> tuple[bool, str, str, str]:
    """
    Launch Cerebras × MATH-500 Scenario 6 in a detached tmux session.
    Returns (success, tmux_session, output_root, log_path).
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_name = f"cerebras_math500_s6_{ts}"
    output_root = os.path.join(S6_TRACKING_ROOT, f"cerebras_math500_full_{ts}")
    log_path = os.path.join(S6_TRACKING_ROOT, f"cerebras_math500_full_{ts}.log")

    os.makedirs(output_root, exist_ok=True)

    cmd = (
        f"cd {REPO_ROOT} && "
        f"exec >{log_path!r} 2>&1; "
        f"echo \"[start] $(date -u +%Y-%m-%dT%H:%M:%SZ)\"; "
        f"python3 {RUNNER_SCRIPT} "
        f"--timestamp {ts} "
        f"--providers cerebras "
        f"--cerebras-model llama3.1-8b "
        f"--datasets HuggingFaceH4/MATH-500 "
        f"--seeds 71 "
        f"--budgets 6 "
        f"--methods direct_reserve_semantic_frontier_v2,external_l1_max,external_s1_budget_forcing,external_tale_prompt_budgeting "
        f"--target-scored-per-slice 300 "
        f"--max-examples 300 "
        f"--allowed-example-ids-file {S6_ALLOWED_IDS!r} "
        f"--exact-cases-jsonl {S6_SHARED_EXACT_CASES!r} "
        f"--api-retry-max-attempts 5 "
        f"--api-retry-base-delay-seconds 1.0 "
        f"--api-retry-backoff-multiplier 2.0 "
        f"--api-retry-max-delay-seconds 20.0 "
        f"--api-retry-jitter-seconds 0.5 "
        f"--max-recovery-passes 2 "
        f"--output-root {output_root!r}; "
        f"echo \"[done] $(date -u +%Y-%m-%dT%H:%M:%SZ)\""
    )

    tmux_cmd = [
        "tmux", "new-session", "-d",
        "-s", session_name,
        "bash", "-lc", cmd,
    ]

    log(f"Launching Scenario 6: tmux session={session_name}")
    log(f"  output_root={output_root}")
    log(f"  log_path={log_path}")

    try:
        result = subprocess.run(tmux_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            log(f"ERROR: tmux launch failed: {result.stderr}")
            return False, session_name, output_root, log_path
    except Exception as e:
        log(f"ERROR: tmux launch exception: {e}")
        return False, session_name, output_root, log_path

    # Wait briefly and verify
    time.sleep(15)

    # Check tmux session exists
    try:
        ls_result = subprocess.run(["tmux", "ls"], capture_output=True, text=True, timeout=10)
        if session_name not in ls_result.stdout:
            log(f"WARNING: tmux session {session_name} not found after launch")
    except Exception:
        pass

    # Check log was created
    if not os.path.exists(log_path):
        log(f"WARNING: log file not created yet: {log_path}")

    # Write launch status
    launch_status = {
        "launched": True,
        "tmux_session": session_name,
        "output_root": output_root,
        "log_path": log_path,
        "launch_utc": utcnow(),
        "provider": "cerebras",
        "model": "llama3.1-8b",
        "dataset": "HuggingFaceH4/MATH-500",
        "seed": 71,
        "n_examples": 300,
        "methods": ALL_METHODS,
    }
    launch_status_path = os.path.join(SUPERVISOR_OUT, "cerebras_math500_scenario6_launch_status.json")
    with open(launch_status_path, "w") as f:
        json.dump(launch_status, f, indent=2)

    log(f"Scenario 6 launched. session={session_name}")
    return True, session_name, output_root, log_path


def write_scenario6_call_plan():
    """Write the call plan JSON for Scenario 6."""
    plan = {
        "provider": "cerebras",
        "model": "llama3.1-8b",
        "dataset": "HuggingFaceH4/MATH-500",
        "seed": 71,
        "budget": 6,
        "methods": ALL_METHODS,
        "target_scored_per_slice": 300,
        "max_examples": 300,
        "exact_cases_jsonl": S6_SHARED_EXACT_CASES,
        "allowed_example_ids_file": S6_ALLOWED_IDS,
        "retry_settings": {
            "api_retry_max_attempts": 5,
            "api_retry_base_delay_seconds": 1.0,
            "api_retry_backoff_multiplier": 2.0,
            "api_retry_max_delay_seconds": 20.0,
            "api_retry_jitter_seconds": 0.5,
            "max_recovery_passes": 2,
        },
        "expected_records": 1200,
        "safety": "launch_only_after_gsm8k_complete_and_no_active_cerebras_pids",
    }
    path = os.path.join(SUPERVISOR_OUT, "cerebras_math500_scenario6_call_plan.json")
    with open(path, "w") as f:
        json.dump(plan, f, indent=2)
    log(f"Wrote call plan: {path}")


# ── Human report ──────────────────────────────────────────────────────────────

def write_supervisor_report(state: str, notes: str = "", s6_info: dict | None = None):
    report = f"""# Overnight Cerebras Supervisor — 2026-05-24

**Report generated:** {utcnow()}
**Branch:** main
**Final state:** `{state}`

---

## What the Supervisor Did

1. Monitored Cerebras × GSM8K job (PIDs 2195504/2195513) by polling every 10 minutes.
2. Checked: process alive, `[done]` in log, heartbeat age, method row counts.
3. Did NOT interrupt, kill, or modify the running GSM8K job at any time.
4. On GSM8K completion: ran full offline processing (integrity, accuracy, selector replay, failures).
5. On processing success: verified Scenario 6 preconditions (shared case files, no active Cerebras PIDs).
6. If conditions met: launched Cerebras × MATH-500 Scenario 6 in new tmux session.

---

## Cerebras × GSM8K Status

{notes}

---

## Scenario 6 Launch Status

"""
    if s6_info:
        report += f"| Field | Value |\n|---|---|\n"
        for k, v in s6_info.items():
            report += f"| {k} | {v} |\n"
    else:
        report += "_Not launched (see state above)._\n"

    report += f"""
---

## Safety Confirmation

- No Cohere API calls launched.
- No Mistral API calls launched.
- Cerebras × GSM8K job was observed only — never killed, restarted, or modified.
- No commits or pushes made.
- No original artifacts overwritten.
- If blocked, wrote blocked report and exited safely.

---

## Files Created

| Path | Description |
|---|---|
| `outputs/overnight_cerebras_supervisor_20260524/supervisor.log` | Full supervisor log |
| `outputs/overnight_cerebras_supervisor_20260524/supervisor_status.jsonl` | Machine-readable status events |
| `outputs/overnight_cerebras_supervisor_20260524/manifest.json` | Final manifest |
| `outputs/overnight_cerebras_supervisor_20260524/cerebras_math500_scenario6_call_plan.json` | Scenario 6 call plan |
| `outputs/cerebras_gsm8k_completed_processing_20260524/` | GSM8K offline processing bundle |
| `docs/CEREBRAS_GSM8K_COMPLETED_PROCESSING_20260524.md` | GSM8K human report |

---

## Morning Commands

```bash
# 1. Check Cerebras MATH-500 Scenario 6 progress
cat outputs/overnight_cerebras_supervisor_20260524/supervisor_status.jsonl | tail -5
tmux ls

# 2. If Scenario 6 launched, check its log
tail -30 outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_*/logs/*.log 2>/dev/null || \\
  tail -30 outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_*.log 2>/dev/null

# 3. Check GSM8K processing results
cat outputs/cerebras_gsm8k_completed_processing_20260524/cerebras_gsm8k_integrity_summary.json
cat outputs/cerebras_gsm8k_completed_processing_20260524/cerebras_gsm8k_method_accuracy_summary.csv

# 4. Check supervisor state
cat outputs/overnight_cerebras_supervisor_20260524/manifest.json
```
"""
    report_path = os.path.join(REPO_ROOT, "docs/OVERNIGHT_CEREBRAS_SUPERVISOR_20260524.md")
    with open(report_path, "w") as f:
        f.write(report)
    log(f"Wrote supervisor report: {report_path}")


# ── Main supervisor loop ──────────────────────────────────────────────────────

def main():
    os.makedirs(SUPERVISOR_OUT, exist_ok=True)
    os.chdir(REPO_ROOT)

    log("=" * 70)
    log("Overnight Cerebras supervisor starting")
    log(f"Output root: {SUPERVISOR_OUT}")
    log("=" * 70)

    write_status("supervisor_start",
                 gsm8k_log=GSM8K_LOG,
                 gsm8k_per_example=GSM8K_PER_EXAMPLE,
                 poll_interval_seconds=POLL_INTERVAL_SECONDS)

    # Write call plan early
    write_scenario6_call_plan()

    state = "monitoring_gsm8k"
    consecutive_stall_polls = 0
    gsm8k_completed = False
    gsm8k_processing_ok = False
    s6_launch_info = None

    try:
        while True:
            now = utcnow()

            # ── Check GSM8K state ───────────────────────────────────────────
            done_in_log = log_done_in_gsm8k()
            all_rows, scored, method_counts = read_gsm8k_rows()
            n_scored = len(scored)
            log_age = gsm8k_log_age_seconds()
            hb_age = heartbeat_age_seconds()
            active_pids = find_active_cerebras_pids()
            known_alive = any_cerebras_gsm8k_pid_alive()

            log(f"[{now}] state={state} done_in_log={done_in_log} scored={n_scored} method_counts={method_counts} log_age={log_age:.0f}s hb_age={hb_age:.0f}s active_pids={active_pids}")

            if state == "monitoring_gsm8k":
                if done_in_log and all(method_counts.get(m, 0) >= 295 for m in ALL_METHODS):
                    # GSM8K complete!
                    gsm8k_completed = True
                    log("*** Cerebras × GSM8K appears COMPLETE ***")
                    write_status("gsm8k_complete",
                                 scored_rows=n_scored,
                                 method_counts=method_counts,
                                 done_in_log=True)
                    state = "processing_gsm8k"

                elif not known_alive and not done_in_log and n_scored < 1190:
                    # Process died without [done] and not enough rows
                    log(f"ERROR: GSM8K process is dead, no [done], only {n_scored} scored rows")
                    write_status("gsm8k_failed_or_exited_incomplete",
                                 scored_rows=n_scored,
                                 method_counts=method_counts,
                                 done_in_log=False,
                                 action="stopping_supervisor_no_scenario6_launch")
                    write_supervisor_report(
                        "failed",
                        f"GSM8K process exited without [done], only {n_scored} rows. Scenario 6 NOT launched.",
                    )
                    write_manifest("failed",
                                   scenario6_launched=False,
                                   gsm8k_status="failed_incomplete",
                                   api_calls_launched_cerebras=False)
                    log("Supervisor stopping due to GSM8K failure.")
                    return

                elif not known_alive and not done_in_log and n_scored >= 1190:
                    # Likely done but [done] not written (edge case) — still process
                    log(f"GSM8K process ended, no [done], but {n_scored} rows — treating as likely complete")
                    write_status("gsm8k_likely_complete_no_done_marker",
                                 scored_rows=n_scored,
                                 method_counts=method_counts)
                    state = "processing_gsm8k"
                    gsm8k_completed = True

                elif hb_age > STALL_THRESHOLD_SECONDS:
                    # Possibly stalled
                    consecutive_stall_polls += 1
                    log(f"WARNING: heartbeat age {hb_age:.0f}s > {STALL_THRESHOLD_SECONDS}s — possibly_stalled (poll #{consecutive_stall_polls})")
                    write_status("possibly_stalled",
                                 heartbeat_age_seconds=hb_age,
                                 consecutive_stall_polls=consecutive_stall_polls,
                                 scored_rows=n_scored,
                                 action="monitoring_only_not_killing")
                    if consecutive_stall_polls >= 12:  # ~2 hours of stall
                        log(f"ERROR: stalled for {consecutive_stall_polls * POLL_INTERVAL_SECONDS / 3600:.1f}h — writing blocked report")
                        write_supervisor_report(
                            "stalled",
                            f"GSM8K appears stalled for {consecutive_stall_polls * POLL_INTERVAL_SECONDS / 3600:.1f}h. Heartbeat age: {hb_age:.0f}s. Scored rows: {n_scored}. Scenario 6 NOT launched.",
                        )
                        write_manifest("stalled",
                                       scenario6_launched=False,
                                       gsm8k_status="possibly_stalled")
                        return
                else:
                    consecutive_stall_polls = 0
                    write_status("monitoring_ok",
                                 scored_rows=n_scored,
                                 method_counts=method_counts,
                                 heartbeat_age_seconds=round(hb_age),
                                 log_age_seconds=round(log_age))

            if state == "processing_gsm8k":
                log("Starting GSM8K offline processing...")
                try:
                    gsm8k_processing_ok = process_gsm8k_offline()
                except Exception as e:
                    log(f"ERROR during GSM8K processing: {e}")
                    import traceback
                    traceback.print_exc()
                    gsm8k_processing_ok = False

                if not gsm8k_processing_ok:
                    write_supervisor_report(
                        "processing_failed",
                        "GSM8K processing script failed. Scenario 6 NOT launched. Check cerebras_gsm8k_completed_processing_20260524/.",
                    )
                    write_manifest("processing_failed",
                                   scenario6_launched=False,
                                   gsm8k_status="processing_failed")
                    return

                state = "launching_s6"

            if state == "launching_s6":
                log("Verifying Scenario 6 preconditions...")
                ok, reason = verify_scenario6_preconditions()
                if not ok:
                    log(f"Scenario 6 preconditions NOT met: {reason}")
                    write_status("scenario6_blocked", reason=reason)
                    write_supervisor_report(
                        "scenario6_blocked",
                        f"GSM8K complete and processed. Scenario 6 BLOCKED: {reason}",
                    )
                    write_manifest("scenario6_blocked",
                                   scenario6_launched=False,
                                   block_reason=reason)
                    return

                # Write call plan with final info
                write_scenario6_call_plan()

                log("Launching Cerebras × MATH-500 Scenario 6...")
                success, session, out_root, log_file = launch_scenario6()
                if not success:
                    log("ERROR: Scenario 6 launch failed")
                    write_supervisor_report(
                        "scenario6_launch_failed",
                        f"GSM8K complete. Scenario 6 launch FAILED (tmux error). Check supervisor.log.",
                    )
                    write_manifest("scenario6_launch_failed",
                                   scenario6_launched=False)
                    return

                s6_launch_info = {
                    "launched": True,
                    "tmux_session": session,
                    "output_root": out_root,
                    "log_path": log_file,
                    "launch_utc": utcnow(),
                }
                write_status("scenario6_launched", **s6_launch_info)

                write_supervisor_report(
                    "done",
                    "GSM8K completed and processed. Scenario 6 launched successfully.",
                    s6_info=s6_launch_info,
                )
                write_manifest(
                    "done",
                    scenario6_launched=True,
                    scenario6_session=session,
                    scenario6_output_root=out_root,
                    scenario6_log=log_file,
                    gsm8k_processing="success",
                    api_calls_launched_cerebras=True,
                )
                log("Supervisor complete. Scenario 6 is running.")
                return  # Done

            # Sleep before next poll
            log(f"Sleeping {POLL_INTERVAL_SECONDS}s until next poll...")
            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        log("Supervisor interrupted by KeyboardInterrupt")
        write_status("interrupted")
        write_supervisor_report("interrupted", "Supervisor was interrupted.")
        write_manifest("interrupted", scenario6_launched=False)
        raise


if __name__ == "__main__":
    main()
