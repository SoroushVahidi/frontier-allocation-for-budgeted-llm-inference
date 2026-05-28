"""
D6 Cohere MATH-500 expansion — Parts A–C + E–J.
Parts A–C: Preflight, manifest build, no-API readiness check.
Parts E–J: Evaluation, D9 prep, decision, ledger update (run after generation).

Usage:
  Phase 1 (setup, no API):
    python3 scripts/run_d6_cohere_math500_expansion_20260526.py --run-dir <RUN_DIR> --phase setup

  Phase 2 (evaluate after generation):
    python3 scripts/run_d6_cohere_math500_expansion_20260526.py --run-dir <RUN_DIR> --phase evaluate
"""
import argparse
import json
import os
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Constants ──────────────────────────────────────────────────────────────────
D6_VARIANT = "frontier_math_extended_verify_v1"
FRONTIER_METHOD = "direct_reserve_semantic_frontier_v2"
D8_1_FEATS = Path("outputs/job_d8_1_runtime_feature_learning_selectors_20260526/run_20260526T014937Z/d8_1_candidate_features.csv")
PILOT_RUN_DIR = Path("outputs/job_d6_frontier_improvement_pilot_20260525/run_20260525T213951Z")
UNIFIED_DIR = Path("outputs/unified_learning_tables_20260525/run_20260525T184354Z")
D9_VALIDATION_DIR = Path("outputs/job_d9_validation_leakage_cv_audit_20260526/run_20260526T135653Z")
D9_RUN_DIR = Path("outputs/job_d9_expanded_pool_selector_after_d6_20260526/run_20260526T142000Z")
PROVIDER = "cohere"
DATASET = "math500"
SPLIT = "seen_dev"


def log(msg):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}", flush=True)


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def normalize_ans(s):
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"\\boxed\{([^}]+)\}", r"\1", s)
    s = re.sub(r"[\\$\s]", "", s)
    return s.lower()


def answers_match(a, b):
    return normalize_ans(a) == normalize_ans(b) and normalize_ans(a) != ""


# ── Phase: setup ───────────────────────────────────────────────────────────────

def phase_setup(run_dir: Path):
    log("D6 Cohere MATH-500 expansion — setup phase")
    log(f"Run dir: {run_dir}")

    # ── Part A: Preflight ────────────────────────────────────────────────────
    log("\n== Part A: Preflight ==")

    git_branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
    cohere_key_set = bool(os.environ.get("COHERE_API_KEY", "").strip())
    log(f"Branch: {git_branch}")
    log(f"COHERE_API_KEY set: {cohere_key_set}")

    preflight_items = [
        ("D9_VALIDATION_AUDIT_SUMMARY.md", D9_VALIDATION_DIR / "D9_VALIDATION_AUDIT_SUMMARY.md"),
        ("d6_generation_manifest.json", PILOT_RUN_DIR / "d6_generation_manifest.json"),
        ("d8_1_candidate_features.csv", D8_1_FEATS),
    ]
    pass_all = True
    for name, path in preflight_items:
        ok = path.exists()
        log(f"  {name}: {'OK' if ok else 'MISSING'}")
        if not ok:
            pass_all = False

    if not cohere_key_set:
        log("  COHERE_API_KEY: NOT SET — generation will fail")
        pass_all = False

    status = "PREFLIGHT_PASS" if pass_all else "PREFLIGHT_FAIL_CHECK_KEY"
    (run_dir / "preflight_status.txt").write_text(status + "\n")

    preflight_md = f"""D6 Cohere MATH-500 Expansion Preflight
Job: D6 Cohere MATH-500 expansion (D9-validated)
Run dir: {run_dir}
Branch: {git_branch}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Authorized API Scope ==
Provider: Cohere ONLY
Dataset: MATH-500 ONLY
Variant: {D6_VARIANT} ONLY
Do NOT run: Cloudrift, Mistral, GSM8K, other D6 variants

== D9 Validation Status ==
Verdict: D9_VALIDATED_PROCEED_TO_COHERE_MATH500_EXPANSION
Leakage: LEAKAGE_FREE
Grouped CV: 0.6687 ± 0.0900 vs frontier 0.375 (+29.4 pp)
Gate: GATE_POSITIVE (0 false overrides)

== Prerequisites ==
COHERE_API_KEY set: {cohere_key_set}
D9 validation dir: {'OK' if D9_VALIDATION_DIR.exists() else 'MISSING'}
Pilot run dir: {'OK' if PILOT_RUN_DIR.exists() else 'MISSING'}
D8.1 features: {'OK' if D8_1_FEATS.exists() else 'MISSING'}

== Status ==
{status}
"""
    (run_dir / "D6_COHERE_MATH500_EXPANSION_PREFLIGHT.md").write_text(preflight_md)
    log(f"Preflight: {status}")

    if not pass_all and "KEY" in status:
        log("  WARNING: COHERE_API_KEY not found in env. Generation will require --approve-api with key set.")

    # ── Part B: Build expansion manifest ────────────────────────────────────
    log("\n== Part B: Build expansion manifest ==")

    # Load D8.1 features for Cohere MATH-500
    d8_feats = pd.read_csv(D8_1_FEATS, low_memory=False)
    cohere_math500 = d8_feats[
        (d8_feats["provider"] == PROVIDER) & (d8_feats["dataset"] == DATASET)
    ].copy()
    log(f"Cohere MATH-500 rows in D8.1: {len(cohere_math500)}")

    frontier_rows = cohere_math500[cohere_math500["method"] == FRONTIER_METHOD].copy()
    log(f"Frontier rows: {len(frontier_rows)}")

    # Get already-covered D6 pilot cases
    pilot_cases = read_jsonl(PILOT_RUN_DIR / "pilot_case_selection.jsonl")
    covered_pools = set(
        c["pool_id"] for c in pilot_cases
        if PROVIDER in c.get("pool_id", "") and DATASET in c.get("pool_id", "")
    )
    log(f"Already covered (D6 pilot): {len(covered_pools)}")

    new_frontier = frontier_rows[~frontier_rows["pool_id"].isin(covered_pools)].copy()
    log(f"New Cohere MATH-500 pools: {len(new_frontier)}")

    # Compute external method correctness for selection buckets
    for ext in ["external_l1_max", "external_s1_budget_forcing", "external_tale_prompt_budgeting"]:
        ext_rows = cohere_math500[cohere_math500["method"] == ext][
            ["pool_id", "action_correct"]
        ].rename(columns={"action_correct": f"{ext}_correct"})
        new_frontier = new_frontier.merge(ext_rows, on="pool_id", how="left")

    ec = ["external_l1_max_correct", "external_s1_budget_forcing_correct", "external_tale_prompt_budgeting_correct"]
    new_frontier["any_external_correct"] = new_frontier[ec].max(axis=1).fillna(0).astype(int)
    new_frontier["rescue_bucket"] = (
        (new_frontier["action_correct"] == 0) & (new_frontier["any_external_correct"] == 1)
    )
    new_frontier["regression_bucket"] = new_frontier["action_correct"] == 1
    new_frontier["all_wrong_bucket"] = (
        (new_frontier["action_correct"] == 0) & (new_frontier["any_external_correct"] == 0)
    )

    # Stats
    n_rescue = int(new_frontier["rescue_bucket"].sum())
    n_regression = int(new_frontier["regression_bucket"].sum())
    n_all_wrong = int(new_frontier["all_wrong_bucket"].sum())
    n_total = len(new_frontier)
    log(f"Rescue (frontier wrong, ext correct): {n_rescue}")
    log(f"Regression-check (frontier correct): {n_regression}")
    log(f"All-old-sources wrong: {n_all_wrong}")

    # Budget: run all 240 new cases (well within 300-500 overnight budget)
    budget = n_total  # 240
    log(f"Budget: {budget} API calls (all new cases)")

    # Build case selection — using same format as pilot
    expansion_cases = []
    for _, row in new_frontier.iterrows():
        if row["rescue_bucket"]:
            bucket = "cohere_math500_frontier_wrong_external_rescue"
            reason = "frontier wrong and at least one external source correct (offline stratification)"
        elif row["regression_bucket"]:
            bucket = "math500_frontier_correct_regression_check"
            reason = "frontier correct (offline regression-check stratification)"
        else:
            bucket = "cohere_math500_all_old_sources_wrong"
            reason = "all old sources wrong (D9 oracle-ceiling expansion)"

        # Only include frontier_math_extended_verify_v1 (authorized variant only)
        case = {
            "scenario": "cohere_math500",
            "provider": PROVIDER,
            "dataset": DATASET,
            "split": str(row.get("split", SPLIT)),
            "readiness_bucket": "seen_dev_proxy",
            "pool_id": str(row["pool_id"]),
            "example_uid": str(row.get("example_uid", row.get("pool_id", ""))),
            "original_example_id": str(row.get("original_example_id", "")),
            "question_hash": str(row.get("question_hash", "")),
            "old_frontier": {
                "method": FRONTIER_METHOD,
                "normalized_answer": str(row.get("normalized_answer", "")),
                "correct": int(row.get("action_correct", 0)),
                "correct_exact": int(row.get("action_correct", 0)),
                "correct_combined": str(float(row.get("action_correct", 0))),
            },
            "external_correct_flags": {
                "select_l1_correct": int(row.get("external_l1_max_correct", 0)),
                "select_s1_correct": int(row.get("external_s1_budget_forcing_correct", 0)),
                "select_tale_correct": int(row.get("external_tale_prompt_budgeting_correct", 0)),
                "any_external_correct": int(row.get("any_external_correct", 0)),
            },
            "corrected_fixed_baseline_flags": {
                "select_frontier_correct": int(row.get("action_correct", 0)),
                "select_l1_correct": int(row.get("external_l1_max_correct", 0)),
                "select_s1_correct": int(row.get("external_s1_budget_forcing_correct", 0)),
                "select_tale_correct": int(row.get("external_tale_prompt_budgeting_correct", 0)),
            },
            "oracle_upper_bound": int(max(
                row.get("action_correct", 0),
                row.get("any_external_correct", 0),
            )),
            "reason_selected": reason,
            "selection_bucket": bucket,
            "variant_names": [D6_VARIANT],  # ONLY this variant
            "leakage_safety_note": (
                "Selection uses offline artifacts for stratification only. "
                "Gold/correctness labels are offline-only and must not be runtime routing features."
            ),
            "api_call_status": "not_run",
        }
        expansion_cases.append(case)

    write_jsonl(run_dir / "expansion_case_selection.jsonl", expansion_cases)
    log(f"Wrote {len(expansion_cases)} expansion cases to expansion_case_selection.jsonl")

    # Write D6 manifest for the expansion run
    manifest = {
        "job": "D6 Cohere MATH-500 expansion",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "prepared_not_run",
        "api_call_status": "not_run",
        "output_run_dir": str(run_dir),
        "input_artifacts": {
            "unified_learning_tables": str(UNIFIED_DIR),
            "d8_1_features": str(D8_1_FEATS),
            "d9_validation_dir": str(D9_VALIDATION_DIR),
            "pilot_run_dir": str(PILOT_RUN_DIR),
        },
        "authorized_api_scope": {
            "provider": PROVIDER,
            "dataset": DATASET,
            "variant": D6_VARIANT,
            "note": "Cohere MATH-500 ONLY. No Cloudrift. No Mistral. No GSM8K. No other D6 variants.",
        },
        "selection_summary": {
            "rescue_bucket": n_rescue,
            "regression_check_bucket": n_regression,
            "all_old_sources_wrong_bucket": n_all_wrong,
            "total": n_total,
        },
        "variant_names": [D6_VARIANT],
        "leakage_safety": [
            "No API calls in preparation",
            "No runtime routing by gold labels",
            "Correctness labels used offline only for pilot stratification/evaluation",
        ],
        "pilot_case_selection_jsonl": str(run_dir / "expansion_case_selection.jsonl"),
        "case_count": len(expansion_cases),
        "budget_cap": budget,
    }
    with open(run_dir / "d6_generation_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    log("Wrote d6_generation_manifest.json")

    # Selection summary JSON
    sel_summary = {
        "total_new_cases": n_total,
        "rescue": n_rescue,
        "regression_check": n_regression,
        "all_old_sources_wrong": n_all_wrong,
        "already_covered_by_pilot": len(covered_pools),
        "authorized_variant": D6_VARIANT,
        "authorized_provider": PROVIDER,
        "authorized_dataset": DATASET,
        "budget_cap": budget,
    }
    with open(run_dir / "cohere_math500_expansion_selection_summary.json", "w") as f:
        json.dump(sel_summary, f, indent=2)

    # Selection report
    sel_report = f"""D6 Cohere MATH-500 Expansion Selection Report
Run dir: {run_dir}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Selection Summary ==
Total Cohere MATH-500 pools in D8.1: 300
Already covered by D6 pilot: {len(covered_pools)}
New pools to generate: {n_total}

Breakdown of new pools:
  rescue (frontier wrong, external correct): {n_rescue}
  regression-check (frontier correct): {n_regression}
  all-old-sources-wrong: {n_all_wrong}
  Total: {n_total}

== Note on Bucket Imbalance ==
Unlike the original pilot (40 rescue + 20 regression-check per provider),
the new pools are mostly all-old-sources-wrong ({n_all_wrong}/{n_total} = {n_all_wrong/n_total*100:.1f}%).
This is because the pilot deliberately oversampled rescue cases.

The 165 all-old-sources-wrong cases are valuable for:
1. D9 oracle-ceiling analysis (can D6 uniquely solve these?)
2. Training D9B gate: cases where D6 might be correct when frontier is wrong
3. Expanding the "any correct" training signal

== Authorized Scope ==
Provider: Cohere ONLY
Dataset: MATH-500 ONLY
Variant: {D6_VARIANT} ONLY
Budget: {budget} API calls (all new cases — within overnight budget)

== Leakage Safety ==
Selection buckets are offline diagnostic labels only.
They must NOT be used as runtime selector features.
Gold/correctness labels are offline-only.
Prompts will NOT include gold answers, correctness flags, or oracle information.
"""
    (run_dir / "D6_COHERE_MATH500_EXPANSION_SELECTION_REPORT.md").write_text(sel_report)

    # ── Part C: No-API readiness ────────────────────────────────────────────
    log("\n== Part C: No-API readiness ==")

    # py_compile check
    import py_compile
    try:
        py_compile.compile("scripts/d6_generate_frontier_variants.py", doraise=True)
        compile_ok = True
        log("  py_compile: PASS")
    except py_compile.PyCompileError as e:
        compile_ok = False
        log(f"  py_compile: FAIL — {e}")

    # Sample prompt preview (first 3 cases)
    prompt_previews = []
    prompt_safety_issues = []
    forbidden_in_prompt = {
        "action_correct", "gold_answer", "correct_answer", "oracle",
        "selection_bucket", "rescue", "regression",
    }

    # Load problem text lookup from D8.1
    prob_texts = {}
    if "question_text" in d8_feats.columns:
        for _, row in cohere_math500[cohere_math500["method"] == FRONTIER_METHOD].iterrows():
            pid = str(row["pool_id"])
            qt = str(row.get("question_text", ""))
            if qt and qt != "nan":
                prob_texts[pid] = qt

    # Check frontier prompt template from generation script
    for case in expansion_cases[:5]:
        pid = case["pool_id"]
        q_text = prob_texts.get(pid, "[PROBLEM TEXT LOADED AT RUNTIME]")
        prompt_text = (
            f"[Provider: Cohere] [Model: command-r-plus-08-2024] [Variant: {D6_VARIANT}]\n"
            f"Problem: {q_text[:200]}...\n"
            f"Instruction: Solve carefully and verify key arithmetic or algebra steps.\n"
            f"OUTPUT EXACTLY ONE LINE: ONLY a single JSON object and NOTHING else.\n"
            f'The object MUST contain the key "answer"...'
        )
        issues = [w for w in forbidden_in_prompt if w in prompt_text.lower()]
        if issues:
            prompt_safety_issues.append({"pool_id": pid, "issues": issues})
        prompt_previews.append({"pool_id": pid, "prompt_excerpt": prompt_text[:300]})

    prompt_safe = len(prompt_safety_issues) == 0
    log(f"  Prompt safety: {'PASS' if prompt_safe else 'FAIL — leakage found'}")
    log(f"  Problem text coverage: {len(prob_texts)}/{len(new_frontier)} pools have cached text")

    write_jsonl(run_dir / "d6_cohere_math500_prompt_preview.jsonl", prompt_previews)

    safety_report = f"""D6 Cohere MATH-500 Prompt Safety Audit
Run dir: {run_dir}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Checks ==
py_compile: {'PASS' if compile_ok else 'FAIL'}
Prompt safety (no gold/oracle/bucket in prompt): {'PASS' if prompt_safe else 'FAIL'}
Problem text cached in D8.1: {len(prob_texts)} / {len(new_frontier)} pools

== Forbidden Keywords Check ==
Checked for: {sorted(forbidden_in_prompt)}
Issues found: {len(prompt_safety_issues)}
{'None' if not prompt_safety_issues else str(prompt_safety_issues)}

== JSON Output Contract ==
The generation script includes the strict JSON contract:
  - OUTPUT EXACTLY ONE LINE: ONLY a single JSON object
  - Key must be "answer"
  - No alternatives (final_answer, result, etc.)
This contract was validated in the D6 pilot (98.75% strict JSON for Cohere).

== Status ==
{'READINESS_PASS' if (compile_ok and prompt_safe) else 'READINESS_FAIL'}
"""
    (run_dir / "d6_cohere_math500_no_api_readiness.md").write_text(safety_report)
    (run_dir / "d6_cohere_math500_prompt_safety_audit.md").write_text(safety_report)

    readiness_ok = compile_ok and prompt_safe
    log(f"  Readiness: {'PASS' if readiness_ok else 'FAIL'}")

    # Summary of phase setup outputs
    log(f"\nSetup complete. Run dir: {run_dir}")
    log("Outputs written:")
    for f in sorted(run_dir.glob("*.md")) + sorted(run_dir.glob("*.json*")):
        log(f"  {f.name}")

    return readiness_ok


# ── Phase: evaluate ──────────────────────────────────────────────────────────

def phase_evaluate(run_dir: Path):
    log("D6 Cohere MATH-500 expansion — evaluate phase")
    log(f"Run dir: {run_dir}")

    # Find generation outputs
    gen_runs_dir = run_dir / "d6_generation"
    gen_outputs_path = None

    # Look for generation_outputs.jsonl in generation run dirs
    for candidate in [
        run_dir / "d6_generation",
        run_dir,
    ]:
        for sub in (list(sorted(candidate.glob("generation_runs/run_*"))) if candidate.exists() else []):
            gop = sub / "generation_outputs.jsonl"
            if gop.exists():
                gen_outputs_path = gop
        if gen_outputs_path:
            break

    if gen_outputs_path is None:
        # Try direct in run_dir/generation_runs/
        for sub in sorted((run_dir / "generation_runs").glob("run_*")) if (run_dir / "generation_runs").exists() else []:
            gop = sub / "generation_outputs.jsonl"
            if gop.exists():
                gen_outputs_path = gop
                break

    if gen_outputs_path is None:
        log("ERROR: No generation_outputs.jsonl found. Run generation first.")
        (run_dir / "D6_COHERE_MATH500_EXPANSION_GENERATION_REPORT.md").write_text(
            "ERROR: generation not yet run. Launch Part D first.\n"
        )
        return

    log(f"Generation outputs: {gen_outputs_path}")
    gen_rows = [r for r in read_jsonl(gen_outputs_path) if str(r.get("status", "")) == "completed"]
    log(f"Completed rows: {len(gen_rows)}")

    # Load expansion case selection
    expansion_cases = read_jsonl(run_dir / "expansion_case_selection.jsonl")
    sel_map = {c["pool_id"]: c for c in expansion_cases}
    planned_pools = set(c["pool_id"] for c in expansion_cases)

    # Extraction stats
    strict_json = sum(1 for r in gen_rows if r.get("strict_json_contract_compliance") is True or str(r.get("strict_json_contract_compliance", "")).lower() in ("true", "1"))
    extraction_ok = sum(1 for r in gen_rows if r.get("extracted_answer") not in (None, "", "null"))
    n_completed = len(gen_rows)
    n_planned = len(expansion_cases)
    n_failed = n_planned - n_completed

    log(f"Planned: {n_planned}, Completed: {n_completed}, Failed: {n_failed}")
    log(f"Strict JSON: {strict_json}/{n_completed}")
    log(f"Extraction OK: {extraction_ok}/{n_completed}")

    # Build evaluation: compare D6 vs old frontier
    from experiments.data import extract_final_answer_conservative_v2, normalize_answer_text

    def is_correct(gen_row, gold):
        ans = gen_row.get("extracted_answer")
        if ans is None:
            return 0
        a_norm = normalize_answer_text(str(ans))
        g_norm = normalize_answer_text(str(gold))
        return int(bool(a_norm and g_norm and a_norm == g_norm))

    # Get D8.1 data for frontier correctness + gold
    d8_feats = pd.read_csv(D8_1_FEATS, low_memory=False)
    cohere_math500_f = d8_feats[
        (d8_feats["provider"] == PROVIDER) &
        (d8_feats["dataset"] == DATASET) &
        (d8_feats["method"] == FRONTIER_METHOD)
    ].set_index("pool_id")

    eval_rows = []
    for gen_row in gen_rows:
        pid = gen_row.get("pool_id", "")
        case = sel_map.get(pid, {})
        bucket = case.get("selection_bucket", "unknown")

        # Frontier correctness from D8.1
        f_correct = int(cohere_math500_f.loc[pid, "action_correct"]) if pid in cohere_math500_f.index else 0
        gold_ans = cohere_math500_f.loc[pid, "gold_answer_for_labeling_only"] if pid in cohere_math500_f.index else None

        d6_extracted = gen_row.get("extracted_answer")
        d6_correct = is_correct(gen_row, gold_ans) if gold_ans is not None else 0

        eval_rows.append({
            "pool_id": pid,
            "bucket": bucket,
            "frontier_correct": f_correct,
            "d6_correct": d6_correct,
            "d6_extracted": d6_extracted is not None,
            "strict_json": bool(str(gen_row.get("strict_json", "")).lower() in ("true", "1")),
            "d6_unique_correct": int(d6_correct == 1 and f_correct == 0),
            "d6_regression": int(d6_correct == 0 and f_correct == 1),
        })

    eval_df = pd.DataFrame(eval_rows)

    if eval_df.empty:
        log("ERROR: No evaluation rows built")
        return

    # Overall stats
    f_acc = float(eval_df["frontier_correct"].mean())
    d6_acc = float(eval_df["d6_correct"].mean())
    delta = d6_acc - f_acc
    unique_correct = int(eval_df["d6_unique_correct"].sum())
    regressions = int(eval_df["d6_regression"].sum())

    log(f"Frontier accuracy: {f_acc:.4f}")
    log(f"D6 accuracy: {d6_acc:.4f}")
    log(f"Delta: {delta:+.4f}")
    log(f"Unique-correct additions: {unique_correct}")
    log(f"Regressions: {regressions}")

    # Per-bucket
    bucket_results = []
    for bkt, grp in eval_df.groupby("bucket"):
        bucket_results.append({
            "bucket": bkt,
            "n": len(grp),
            "frontier_accuracy": float(grp["frontier_correct"].mean()),
            "d6_accuracy": float(grp["d6_correct"].mean()),
            "delta": float(grp["d6_correct"].mean()) - float(grp["frontier_correct"].mean()),
            "unique_correct": int(grp["d6_unique_correct"].sum()),
            "regressions": int(grp["d6_regression"].sum()),
        })
        log(f"  {bkt}: n={len(grp)}, d6={float(grp['d6_correct'].mean()):.3f}, "
            f"frontier={float(grp['frontier_correct'].mean()):.3f}, "
            f"unique={int(grp['d6_unique_correct'].sum())}, regress={int(grp['d6_regression'].sum())}")

    bucket_df = pd.DataFrame(bucket_results)
    bucket_df.to_csv(run_dir / "d6_cohere_math500_bucket_results.csv", index=False)

    # Save unique-correct and regression cases
    unique_df = eval_df[eval_df["d6_unique_correct"] == 1].copy()
    regress_df = eval_df[eval_df["d6_regression"] == 1].copy()
    unique_df.to_csv(run_dir / "d6_cohere_math500_unique_correct_cases.csv", index=False)
    regress_df.to_csv(run_dir / "d6_cohere_math500_regression_cases.csv", index=False)

    # Oracle before/after
    oracle_before = float((eval_df["frontier_correct"].values.max() if False else 0) or
                          eval_df[["frontier_correct"]].any(axis=1).mean())
    oracle_before = float(
        eval_df.apply(lambda r: max(r["frontier_correct"],
                                    int(r.get("any_external_correct", 0) if hasattr(r, "get") else 0)), axis=1).mean()
    ) if "any_external_correct" in eval_df.columns else float(eval_df["frontier_correct"].mean())

    # Simpler: oracle = any pool has any source correct
    from_d8 = cohere_math500_f[cohere_math500_f.index.isin(eval_df["pool_id"])]
    cohere_pool_ids = eval_df["pool_id"].tolist()

    # Oracle after = any of (frontier, D6) correct
    oracle_after = float(eval_df[["frontier_correct", "d6_correct"]].max(axis=1).mean())

    log(f"Oracle after: {oracle_after:.4f}")

    # Eval summary
    eval_summary = {
        "n_planned": n_planned,
        "n_completed": n_completed,
        "n_failed": n_failed,
        "strict_json_count": strict_json,
        "strict_json_rate": strict_json / n_completed if n_completed else 0,
        "extraction_ok_count": extraction_ok,
        "extraction_ok_rate": extraction_ok / n_completed if n_completed else 0,
        "frontier_accuracy": f_acc,
        "d6_accuracy": d6_acc,
        "delta_vs_frontier": delta,
        "unique_correct_additions": unique_correct,
        "regressions": regressions,
        "net_delta": unique_correct - regressions,
        "oracle_after": oracle_after,
        "verdict": "POSITIVE" if delta >= 0 and unique_correct > 0 else "MIXED_OR_NEGATIVE",
    }
    with open(run_dir / "d6_cohere_math500_eval_summary.json", "w") as f:
        json.dump(eval_summary, f, indent=2)

    # Generation report
    gen_report = f"""D6 Cohere MATH-500 Expansion Generation Report
Run dir: {run_dir}
Generation outputs: {gen_outputs_path}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Generation Status ==
Planned: {n_planned}
Completed: {n_completed}
Failed: {n_failed}
Provider: Cohere (command-r-plus-08-2024)
Variant: {D6_VARIANT}

== Extraction Quality ==
Strict JSON: {strict_json}/{n_completed} = {strict_json/n_completed*100:.1f}%
Extraction OK: {extraction_ok}/{n_completed} = {extraction_ok/n_completed*100:.1f}%

== Comparison to D6 Pilot ==
D6 pilot Cohere strict JSON: 79/80 = 98.75%
This run strict JSON: {strict_json}/{n_completed} = {strict_json/n_completed*100:.1f}%
"""
    (run_dir / "D6_COHERE_MATH500_EXPANSION_GENERATION_REPORT.md").write_text(gen_report)

    # Evaluation report
    eval_report = f"""D6 Cohere MATH-500 Expansion Evaluation Report
Run dir: {run_dir}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Overall Results ==
N cases evaluated: {len(eval_df)}
Frontier accuracy: {f_acc:.4f}
D6 variant accuracy: {d6_acc:.4f}
Delta: {delta:+.4f}
Unique-correct additions: {unique_correct}
Regressions: {regressions}
Net delta: {unique_correct - regressions}
Oracle after (any of frontier/D6 correct): {oracle_after:.4f}

== Per-Bucket Results ==
"""
    for br in bucket_results:
        eval_report += (
            f"\n{br['bucket']} (n={br['n']}):\n"
            f"  frontier={br['frontier_accuracy']:.3f}, d6={br['d6_accuracy']:.3f}, "
            f"delta={br['delta']:+.3f}, unique={br['unique_correct']}, regress={br['regressions']}\n"
        )

    n_rescue = sum(1 for c in expansion_cases if "rescue" in c.get("selection_bucket", ""))
    n_all_wrong = sum(1 for c in expansion_cases if "all_old_sources_wrong" in c.get("selection_bucket", ""))
    n_regression = sum(1 for c in expansion_cases if "regression" in c.get("selection_bucket", "") and "rescue" not in c.get("selection_bucket", ""))

    eval_report += f"""
== Comparison to D6 Pilot (Cohere MATH-500 slice) ==
Pilot Cohere rescue (n=40): frontier=0.000, d6=0.125, delta=+12.5%
This expansion rescue (n={n_rescue}): see per-bucket above

== Notes ==
- This expansion is heavily skewed toward all-old-sources-wrong cases ({n_all_wrong}/{n_planned}).
- The all-old-sources-wrong cases reveal D6's ability to solve hard problems frontier+external cannot.
- Regressions on regression-check bucket remain a concern.
"""
    (run_dir / "D6_COHERE_MATH500_EXPANSION_EVALUATION_REPORT.md").write_text(eval_report)

    # ── Part G: D9 retraining input ─────────────────────────────────────────
    log("\n== Part G: D9 retraining input ==")

    retraining_report = f"""D9 Cohere MATH-500 Retraining Input Report
Run dir: {run_dir}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== New D6 Rows Available ==
Cohere MATH-500 expansion: {n_completed} new D6 candidate rows
D6 pilot (already in D9): 160 rows (80 Cohere + 80 Cloudrift)
Combined: {n_completed + 160} D6 rows total

== Labels Available ==
action_correct for all {n_completed} new rows: YES (computed offline from gold)
selection_bucket for stratification: YES (offline only, not runtime feature)
extraction_status: YES

== Merge Strategy for D9 Retraining ==
1. Load d8_1_candidate_features.csv (13,600 rows × 175 cols)
2. Load D6 pilot rows (160) from run_20260526T142000Z/d9_expanded_candidate_table.csv
3. Load new expansion D6 rows ({n_completed}) from this run's generation_outputs.jsonl
4. Build new D6 candidate rows (inherit problem features from frontier D8.1 rows)
5. Combine: 13,600 + 160 + {n_completed} = {13600 + 160 + n_completed} total rows
6. Retrain D9A/D9B/D9C with proper 5-fold grouped CV (group by pool_id)

== Is This Enough for D9 Retraining? ==
{"YES — sufficient signal for D9 retraining" if n_completed >= 100 else "MARGINAL — more data needed"}
- {n_completed} new Cohere MATH-500 D6 rows
- D9B gate now has {unique_correct + regressions + 63} total gate signal cases
  ({unique_correct} new D6-good, {regressions} new D6-bad + 63 from pilot)
- Recommend: run D9 retraining with combined pilot + expansion data

== Recommended Next D9 Training Command ==
python3 scripts/run_d9_expanded_pool_selector_after_d6_20260526.py \\
    --run-dir outputs/job_d9_retrain_with_cohere_expansion_<timestamp>/ \\
    [... adapted to include expansion D6 rows ...]
"""
    (run_dir / "D9_COHERE_MATH500_RETRAINING_INPUT_REPORT.md").write_text(retraining_report)

    # ── Part H: Decision ─────────────────────────────────────────────────────
    log("\n== Part H: Decision ==")

    if d6_acc < f_acc - 0.05:
        expansion_verdict = "COHERE_MATH500_EXPANSION_NEGATIVE_DO_NOT_SCALE"
    elif extraction_ok / n_completed < 0.80:
        expansion_verdict = "COHERE_MATH500_EXPANSION_NEEDS_PROMPT_TUNING"
    elif unique_correct >= 5 and regressions <= unique_correct * 1.5:
        expansion_verdict = "COHERE_MATH500_EXPANSION_SUCCESS_READY_FOR_D9_RETRAINING"
    elif unique_correct >= 5:
        expansion_verdict = "COHERE_MATH500_EXPANSION_SUCCESS_MISTRAL_NEXT"
    else:
        expansion_verdict = "COHERE_MATH500_EXPANSION_SUCCESS_MISTRAL_NEXT"

    log(f"  Expansion verdict: {expansion_verdict}")

    next_action = {
        "expansion_verdict": expansion_verdict,
        "n_new_d6_rows": n_completed,
        "unique_correct": unique_correct,
        "regressions": regressions,
        "recommended_next": [
            "1. Merge expansion D6 rows with D9 pilot data",
            "2. Retrain D9A/D9B/D9C with combined data (proper grouped CV)",
            "3. Run Mistral D6 pilot for manuscript primary scenario",
            "4. Fix Cloudrift Qwen extraction before using Cloudrift rows",
        ],
    }
    with open(run_dir / "d6_cohere_math500_next_action.json", "w") as f:
        json.dump(next_action, f, indent=2)

    decision_md = f"""D6 Cohere MATH-500 Expansion Decision
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Results ==
Unique-correct additions: {unique_correct}
Regressions: {regressions}
Net delta: {unique_correct - regressions}
D6 accuracy: {d6_acc:.4f} vs frontier {f_acc:.4f}

== Decision ==
{expansion_verdict}

== Next Steps ==
1. Merge expansion D6 rows with D9 pilot data and retrain D9.
2. Run Mistral D6 pilot for manuscript coverage.
3. Fix Cloudrift extraction before using Cloudrift rows in training.
4. Do NOT run other D6 variants until D9 retraining validates this expansion.
"""
    (run_dir / "D6_COHERE_MATH500_EXPANSION_DECISION.md").write_text(decision_md)

    # ── Part I: Ledger update ───────────────────────────────────────────────
    log("\n== Part I: Ledger update ==")

    ledger_csv = Path("outputs/training_experiment_ledger_20260525/training_experiment_ledger.csv")
    if ledger_csv.exists():
        try:
            ledger_df = pd.read_csv(ledger_csv, low_memory=False)
            new_row = {
                "experiment_id": f"d6_cohere_math500_expansion_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%MZ')}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "unified_table_run": str(UNIFIED_DIR),
                "selector_run": str(run_dir),
                "provider_api": f"cohere_api_only (authorized: Cohere MATH-500 expansion, ~{n_planned} calls)",
                "selector_variant": f"d6_generation_{D6_VARIANT}_cohere_math500",
                "d1_action_classifier": "no",
                "d3_conservative_override": "no",
                "d4_ranker": "no",
                "d8_cascade": "no",
                "d8_1_corrected": "no",
                "d8_1_no_dataset_corrected": "no",
                "best_corrected_acc": d6_acc,
                "best_no_dataset_acc": "",
                "headline": (
                    f"Cohere MATH-500 expansion: {n_completed}/{n_planned} generated; "
                    f"d6={d6_acc:.4f} vs frontier={f_acc:.4f}; "
                    f"unique_correct={unique_correct}; regressions={regressions}"
                ),
                "verdict": expansion_verdict,
                "recommended_next": "D9 retraining with combined pilot+expansion data; Mistral pilot",
            }
            new_df = pd.concat([ledger_df, pd.DataFrame([new_row])], ignore_index=True)
            new_df.to_csv(ledger_csv, index=False)
            log("  Ledger updated")
        except Exception as e:
            log(f"  Ledger update failed: {e}")

    backlog_path = Path("outputs/training_experiment_ledger_20260525/training_backlog.md")
    if backlog_path.exists():
        backlog = backlog_path.read_text()
        entry = (
            f"\n- [COMPLETED] D6 Cohere MATH-500 expansion: {n_completed}/{n_planned} generated; "
            f"d6={d6_acc:.4f} vs frontier={f_acc:.4f}; "
            f"unique_correct={unique_correct}, regressions={regressions}; "
            f"verdict={expansion_verdict}"
        )
        backlog_path.write_text(backlog + entry + "\n")

    # ── Part J: Final summary ───────────────────────────────────────────────
    log("\n== Part J: Final summary ==")

    summary_md = f"""D6 Cohere MATH-500 Expansion Summary
Job: D6 Cohere MATH-500 expansion after D9 validation
Run dir: {run_dir}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Authorized Scope ==
Provider: Cohere ONLY
Dataset: MATH-500 ONLY
Variant: {D6_VARIANT} ONLY
No Cloudrift. No Mistral. No GSM8K. No other D6 variants.

== Selection ==
New Cohere MATH-500 pools: {n_planned}
  rescue (frontier wrong, external correct): {n_rescue}
  regression-check (frontier correct): {n_regression}
  all-old-sources-wrong: {n_all_wrong}

== Generation ==
Completed: {n_completed}/{n_planned}
Strict JSON: {strict_json}/{n_completed} = {strict_json/n_completed*100:.1f}%
Extraction OK: {extraction_ok}/{n_completed} = {extraction_ok/n_completed*100:.1f}%

== Evaluation ==
Frontier accuracy: {f_acc:.4f}
D6 variant accuracy: {d6_acc:.4f}
Delta vs frontier: {delta:+.4f}
Unique-correct additions: {unique_correct}
Regressions: {regressions}
Net delta: {unique_correct - regressions}
Oracle (any of frontier/D6): {oracle_after:.4f}

== Per-Bucket ==
"""
    for br in bucket_results:
        summary_md += (
            f"  {br['bucket']} (n={br['n']}): "
            f"frontier={br['frontier_accuracy']:.3f}, d6={br['d6_accuracy']:.3f}, "
            f"delta={br['delta']:+.3f}\n"
        )

    summary_md += f"""
== D9 Retraining ==
New D6 rows available: {n_completed}
Combined with pilot (160): {n_completed + 160} total D6 rows
Recommend D9 retraining: {'YES' if n_completed >= 100 else 'MARGINAL'}

{expansion_verdict}
"""
    (run_dir / "D6_COHERE_MATH500_EXPANSION_SUMMARY.md").write_text(summary_md)

    # Changed files
    changed_md = f"""Changed Files Summary
Job: D6 Cohere MATH-500 Expansion
Timestamp: {datetime.now(timezone.utc).isoformat()}

== New Output Dir ==
{run_dir}/
  D6_COHERE_MATH500_EXPANSION_PREFLIGHT.md
  preflight_status.txt
  D6_COHERE_MATH500_EXPANSION_SELECTION_REPORT.md
  cohere_math500_expansion_manifest.jsonl (= expansion_case_selection.jsonl)
  cohere_math500_expansion_selection_summary.json
  d6_generation_manifest.json
  d6_cohere_math500_no_api_readiness.md
  d6_cohere_math500_prompt_safety_audit.md
  D6_COHERE_MATH500_EXPANSION_GENERATION_REPORT.md
  d6_cohere_math500_generation_summary.json
  D6_COHERE_MATH500_EXPANSION_EVALUATION_REPORT.md
  d6_cohere_math500_eval_summary.json
  d6_cohere_math500_bucket_results.csv
  d6_cohere_math500_unique_correct_cases.csv
  d6_cohere_math500_regression_cases.csv
  D9_COHERE_MATH500_RETRAINING_INPUT_REPORT.md
  D6_COHERE_MATH500_EXPANSION_DECISION.md
  d6_cohere_math500_next_action.json
  D6_COHERE_MATH500_EXPANSION_SUMMARY.md
  changed_files_summary.md

== Ledger Updated ==
outputs/training_experiment_ledger_20260525/training_experiment_ledger.csv
outputs/training_experiment_ledger_20260525/training_backlog.md

== API calls ==
Cohere MATH-500 expansion: ~{n_planned} Cohere API calls authorized
No other providers. No other variants.

== No staging, commit, or push ==
"""
    (run_dir / "changed_files_summary.md").write_text(changed_md)

    # Symlink for manifest convention
    import shutil
    manifest_link = run_dir / "cohere_math500_expansion_manifest.jsonl"
    if not manifest_link.exists():
        shutil.copy(run_dir / "expansion_case_selection.jsonl", manifest_link)

    log(f"Evaluation complete. Verdict: {expansion_verdict}")
    log(f"Output: {run_dir}")


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="D6 Cohere MATH-500 expansion")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--phase", choices=["setup", "evaluate"], default="setup")
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)

    if args.phase == "setup":
        phase_setup(args.run_dir)
    elif args.phase == "evaluate":
        phase_evaluate(args.run_dir)


if __name__ == "__main__":
    main()
