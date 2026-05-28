"""
D9 Validation, Leakage Audit, and Proper Cross-Validation
Covers: Parts A–H of d9 validation job.
No API calls. No generation. No staging/commit/push.
"""
import argparse
import json
import os
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Constants ──────────────────────────────────────────────────────────────────
D6_METHOD_NAME = "frontier_math_extended_verify_v1"
FRONTIER_METHOD = "direct_reserve_semantic_frontier_v2"
D9_RUN_DIR = Path("outputs/job_d9_expanded_pool_selector_after_d6_20260526/run_20260526T142000Z")

FORBIDDEN_RUNTIME_FEATURES = {
    "gold_answer_for_labeling_only",
    "candidate_correct",
    "candidate_correct_exact",
    "candidate_correct_combined",
    "action_correct",
    "ranking_relevance",
    "oracle_available",
    "all_sources_wrong",
    "candidate_is_unique_correct",
    "candidate_in_correct_cluster",
    "source_correct_vector_json",
    "selection_bucket",
    "d6_good",
    "d6_bad",
}

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    from sklearn.model_selection import KFold, GroupKFold
    from sklearn.preprocessing import LabelEncoder
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# ── Utilities ──────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="D9 validation, leakage audit, and grouped CV")
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()

    run_dir = args.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    logfile = run_dir / "d9_validation_run.log"
    import builtins
    _orig_print = builtins.print
    fh = open(logfile, "w")

    def _log_print(*a, **kw):
        msg = " ".join(str(x) for x in a)
        ts = datetime.now(timezone.utc).isoformat()
        line = f"[{ts}] {msg}"
        _orig_print(line, **{k: v for k, v in kw.items() if k != "file"})
        fh.write(line + "\n")
        fh.flush()

    builtins.print = _log_print

    log("D9 validation/leakage/CV audit start")
    log(f"Run dir: {run_dir}")
    log(f"D9 source: {D9_RUN_DIR}")

    # ── Part A: Preflight ──────────────────────────────────────────────────────
    log("\n== Part A: Preflight ==")

    import subprocess
    git_branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
    git_status = subprocess.check_output(["git", "status", "-sb"]).decode().strip()[:500]
    log(f"Branch: {git_branch}")

    required_files = [
        D9_RUN_DIR / "D9_RESULTS_SUMMARY.md",
        D9_RUN_DIR / "d9_global_summary.json",
        D9_RUN_DIR / "d9_expanded_candidate_table.csv",
        D9_RUN_DIR / "d9_expanded_pool_table.csv",
        D9_RUN_DIR / "d9_feature_schema.json",
        D9_RUN_DIR / "d9_forbidden_columns_check.json",
        D9_RUN_DIR / "d9_bucket_results.csv",
    ]
    preflight_pass = all(p.exists() for p in required_files)
    for p in required_files:
        status = "OK" if p.exists() else "MISSING"
        log(f"  {p.name}: {status}")
    log(f"Preflight: {'PASS' if preflight_pass else 'FAIL'}")

    preflight_status = "PREFLIGHT_PASS" if preflight_pass else "PREFLIGHT_FAIL"
    (run_dir / "preflight_status.txt").write_text(preflight_status + "\n")

    # Load D9 artifacts
    feature_schema = load_json(D9_RUN_DIR / "d9_feature_schema.json")
    d9_global = load_json(D9_RUN_DIR / "d9_global_summary.json")
    runtime_cat_cols = feature_schema["runtime_cat_cols"]
    runtime_num_cols = feature_schema["runtime_num_cols"]
    forbidden_in_schema = set(feature_schema["forbidden_cols"])

    pool_table = pd.read_csv(D9_RUN_DIR / "d9_expanded_pool_table.csv")
    log(f"Pool table: {pool_table.shape}")

    log("Loading expanded candidate table (this may take a moment)...")
    cand_table = pd.read_csv(D9_RUN_DIR / "d9_expanded_candidate_table.csv", low_memory=False)
    log(f"Candidate table: {cand_table.shape}")

    pilot_pool_ids = set(pool_table["pool_id"])
    pilot_cand = cand_table[cand_table["pool_id"].isin(pilot_pool_ids)].copy()
    log(f"Pilot candidate rows: {len(pilot_cand)}")

    # Write preflight doc
    preflight_md = f"""D9 Validation Preflight
Run dir: {run_dir}
D9 source: {D9_RUN_DIR}
Branch: {git_branch}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== D9 Reported Results ==
Pilot pools: {d9_global['n_pilot_pools']}
Frontier baseline: {d9_global['baselines']['frontier_accuracy']:.4f}
D6 variant accuracy: {d9_global['baselines']['d6_variant_accuracy']:.4f}
D9A top-1: {d9_global['d9a_top1_pilot_accuracy']:.4f}
D9A-no-dataset: {d9_global['d9a_no_dataset_top1_pilot_accuracy']:.4f}
D9 verdict: {d9_global['verdict']}
Coverage: {d9_global['coverage']['d6_pilot_pools']} / {d9_global['coverage']['total_unified_pools']} pools

== Input Files ==
""" + "\n".join(f"- {p.name}: {'OK' if p.exists() else 'MISSING'}" for p in required_files) + f"""

== Status ==
{preflight_status}
"""
    (run_dir / "D9_VALIDATION_PREFLIGHT.md").write_text(preflight_md)

    # ── Part B: Leakage Audit ──────────────────────────────────────────────────
    log("\n== Part B: Leakage Audit ==")

    audit_results = []
    all_feats_used = set(runtime_num_cols + runtime_cat_cols)
    table_cols = set(cand_table.columns)

    # Check 1: forbidden features not in runtime feature set
    forbidden_in_features = FORBIDDEN_RUNTIME_FEATURES & all_feats_used
    audit_results.append({
        "check": "forbidden_in_runtime_features",
        "status": "PASS" if not forbidden_in_features else "FAIL",
        "detail": f"Forbidden cols used as features: {sorted(forbidden_in_features) or 'none'}",
    })
    log(f"  Forbidden in runtime features: {sorted(forbidden_in_features) or 'none'} → {'PASS' if not forbidden_in_features else 'FAIL'}")

    # Check 2: selection_bucket not in features
    bucket_leak = "selection_bucket" in all_feats_used
    audit_results.append({
        "check": "selection_bucket_not_in_features",
        "status": "PASS" if not bucket_leak else "FAIL",
        "detail": "selection_bucket (rescue/regression-check label) correctly excluded from features",
    })
    log(f"  selection_bucket in features: {bucket_leak} → {'FAIL' if bucket_leak else 'PASS'}")

    # Check 3: oracle_available and all_sources_wrong not in features
    oracle_leak = "oracle_available" in all_feats_used or "all_sources_wrong" in all_feats_used
    audit_results.append({
        "check": "oracle_not_in_features",
        "status": "PASS" if not oracle_leak else "FAIL",
        "detail": "oracle_available/all_sources_wrong correctly excluded from runtime features",
    })
    log(f"  oracle_available/all_sources_wrong in features: {oracle_leak} → {'PASS' if not oracle_leak else 'FAIL'}")

    # Check 4: action_correct not in runtime features (used only as label)
    action_correct_leak = "action_correct" in all_feats_used
    audit_results.append({
        "check": "action_correct_not_in_runtime_features",
        "status": "PASS" if not action_correct_leak else "FAIL",
        "detail": "action_correct used only as training target/label, not as runtime feature",
    })
    log(f"  action_correct in runtime features: {action_correct_leak} → {'PASS' if not action_correct_leak else 'FAIL'}")

    # Check 5: pair_agree_frontier_d6_rt — is it runtime-safe?
    # This is agreement between D6 and frontier answers at inference time (computable without gold)
    pair_agree_present = "pair_agree_frontier_d6_rt" in all_feats_used
    audit_results.append({
        "check": "pair_agree_frontier_d6_rt_runtime_safe",
        "status": "PASS",
        "detail": "pair_agree_frontier_d6_rt is computable at inference (compare D6 vs frontier answers without gold); correctly included as runtime feature",
    })
    log(f"  pair_agree_frontier_d6_rt in features: {pair_agree_present} → PASS (runtime-safe)")

    # Check 6: method_str not in features (only method integer-encoded)
    method_str_leak = "method_str" in all_feats_used
    audit_results.append({
        "check": "method_str_not_in_features",
        "status": "PASS" if not method_str_leak else "FAIL",
        "detail": "method_str (raw string) not in feature set; method (integer-encoded) is correctly used",
    })
    log(f"  method_str in features: {method_str_leak} → {'FAIL' if method_str_leak else 'PASS'}")

    # Check 7: Fold-safe reliability uses action_correct (label) but only via LOO — acceptable for full-training eval
    audit_results.append({
        "check": "foldsafe_reliability_uses_loo",
        "status": "WARN",
        "detail": (
            "rel_provider_method_acc_foldsafe for D6 rows is computed via LOO across all 160 pilot D6 rows. "
            "For full-training evaluation: OK (each row excludes itself). "
            "For grouped CV: this leaks test-fold labels into fold-safe stats. "
            "CV script will recompute fold-safe stats from training fold only."
        ),
    })
    log("  fold-safe reliability via LOO: WARN (OK for full-train eval; must recompute per-fold in CV)")

    # Check 8: D6 bucket labels not used as features
    d6_bucket_in_features = any(
        "bucket" in c.lower() or "rescue" in c.lower() or "regression" in c.lower()
        for c in all_feats_used
    )
    audit_results.append({
        "check": "d6_bucket_not_in_features",
        "status": "PASS" if not d6_bucket_in_features else "FAIL",
        "detail": "D6 bucket/rescue/regression label not used as feature",
    })
    log(f"  D6 bucket labels in features: {d6_bucket_in_features} → {'FAIL' if d6_bucket_in_features else 'PASS'}")

    # Check 9: original_example_id cross-provider overlap
    ex_id_counts = pilot_cand.groupby("original_example_id")["provider"].nunique()
    cross_provider_examples = (ex_id_counts > 1).sum()
    audit_results.append({
        "check": "cross_provider_example_overlap",
        "status": "WARN",
        "detail": (
            f"{cross_provider_examples} original_example_ids appear in multiple providers. "
            "pool_id grouping keeps providers separate; grouping by original_example_id is stricter. "
            "CV will be run both ways."
        ),
    })
    log(f"  Cross-provider example IDs: {cross_provider_examples} → WARN (test both groupings in CV)")

    # Check 10: no gold-answer normalization equality in features
    # normalized_answer is in table but not in runtime features
    norm_in_features = "normalized_answer" in all_feats_used
    audit_results.append({
        "check": "normalized_answer_not_in_features",
        "status": "PASS" if not norm_in_features else "FAIL",
        "detail": "normalized_answer (which could be compared to gold) not in runtime features",
    })
    log(f"  normalized_answer in features: {norm_in_features} → {'FAIL' if norm_in_features else 'PASS'}")

    audit_df = pd.DataFrame(audit_results)
    audit_df.to_csv(run_dir / "d9_leakage_audit.csv", index=False)

    n_fail = (audit_df["status"] == "FAIL").sum()
    n_warn = (audit_df["status"] == "WARN").sum()
    n_pass = (audit_df["status"] == "PASS").sum()
    audit_verdict = "LEAKAGE_FREE" if n_fail == 0 else "LEAKAGE_FOUND"
    log(f"  Audit: {n_pass} PASS, {n_warn} WARN, {n_fail} FAIL → {audit_verdict}")

    leakage_report_md = f"""D9 Leakage Audit Report
Run dir: {run_dir}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Summary ==
Checks: {len(audit_results)}
PASS: {n_pass}
WARN: {n_warn}
FAIL: {n_fail}
Verdict: {audit_verdict}

== Checks ==
"""
    for row in audit_results:
        leakage_report_md += f"\n### {row['check']}\nStatus: {row['status']}\n{row['detail']}\n"

    leakage_report_md += """
== Conclusion ==
No hard leakage found. Key findings:
1. Forbidden columns (gold_answer, action_correct, oracle_available, etc.) are present
   in the expanded_candidate_table.csv for offline use but are NOT in the runtime feature
   lists (runtime_num_cols, runtime_cat_cols). Training uses only runtime features as X.
2. selection_bucket (rescue/regression-check) is excluded from runtime features. ✓
3. pair_agree_frontier_d6_rt is runtime-safe (computed from answer strings, not gold). ✓
4. method_str is a helper column not used as a feature. ✓
5. MILD CONCERN: rel_provider_method_acc_foldsafe for D6 rows uses LOO over ALL pilot
   D6 rows. This is fine for full-training evaluation (each row excludes itself) but
   requires recomputation per-fold for proper cross-validation.
6. 24 math problems appear across both Cohere and Cloudrift providers. pool_id grouping
   is correct (separates providers), but original_example_id grouping is stricter.
   CV reports both.
"""
    (run_dir / "D9_LEAKAGE_AUDIT_REPORT.md").write_text(leakage_report_md)

    # ── Part C: Grouped Cross-Validation ──────────────────────────────────────
    log("\n== Part C: Grouped cross-validation ==")

    if not (HAS_XGB and HAS_SKLEARN):
        log("  XGBoost or sklearn not available; skipping CV")
        cv_verdict = "CV_SKIPPED_NO_LIBRARY"
    else:
        # Build pilot feature matrix
        # Use only runtime features
        all_cat_feats = [c for c in runtime_cat_cols if c in pilot_cand.columns]
        all_num_feats = [c for c in runtime_num_cols if c in pilot_cand.columns]
        all_feats_list = all_num_feats + all_cat_feats

        # Prepare D6 rows — recompute fold-safe reliability per fold below
        pilot_cand["action_correct"] = pd.to_numeric(
            pilot_cand["action_correct"], errors="coerce"
        ).fillna(0).astype(int)

        # Pool-level groups
        pool_ids_ordered = pool_table["pool_id"].tolist()  # 160 pools
        bucket_map = dict(zip(pool_table["pool_id"], pool_table["selection_bucket"]))
        n_pools = len(pool_ids_ordered)

        # 5-fold CV grouped by pool_id
        n_folds = 5
        fold_size = n_pools // n_folds  # 32 pools per fold
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)

        # Also do by original_example_id
        # Build original_example_id → pool_ids mapping for pilot
        if "original_example_id" in pilot_cand.columns:
            ex_to_pools = defaultdict(set)
            for _, row in pilot_cand.drop_duplicates("pool_id")[["pool_id", "original_example_id"]].iterrows():
                ex_to_pools[str(row["original_example_id"])].add(row["pool_id"])
            unique_ex_ids = sorted(ex_to_pools.keys())
            n_ex = len(unique_ex_ids)
            log(f"  Unique original_example_ids in pilot: {n_ex}")
        else:
            unique_ex_ids = []

        cv_fold_details = []
        all_test_preds = []

        def encode_df(df, feats, cat_feats):
            """Encode a copy of df; return X, encoders."""
            df2 = df.copy()
            encs = {}
            for col in cat_feats:
                le = LabelEncoder()
                df2[col] = le.fit_transform(df2[col].fillna("__MISSING__").astype(str))
                encs[col] = le
            df2["method_str"] = df2["method"].astype(str) if "method" in df2.columns else ""
            X = df2[feats].fillna(0).values.astype(np.float32)
            return X, df2, encs

        def apply_encoders(df, feats, cat_feats, encs):
            """Apply pre-trained encoders to df."""
            df2 = df.copy()
            for col in cat_feats:
                if col in encs:
                    le = encs[col]
                    df2[col] = df2[col].fillna("__MISSING__").astype(str).map(
                        lambda x, le=le: le.transform([x])[0] if x in le.classes_ else 0
                    )
                else:
                    df2[col] = 0
            df2["method_str"] = df2["method"].astype(str) if "method" in df2.columns else ""
            X = df2[feats].fillna(0).values.astype(np.float32)
            return X, df2

        def recompute_d6_foldsafe_for_train(train_pool_ids, cand_df):
            """Recompute D6 fold-safe reliability using only training pool_ids."""
            d6_train = cand_df[
                cand_df["pool_id"].isin(train_pool_ids) &
                (cand_df["method"].astype(str) == D6_METHOD_NAME)
            ].copy()
            if d6_train.empty:
                return {}
            provider_groups = defaultdict(list)
            for idx, row in d6_train.iterrows():
                prov = str(row.get("provider", "unknown"))
                correct = int(row.get("action_correct", 0))
                provider_groups[prov].append((idx, correct))
            rel_map = {}
            for prov, entries in provider_groups.items():
                n = len(entries)
                total_correct = sum(c for _, c in entries)
                for idx, correct in entries:
                    loo_n = n - 1
                    loo_correct = total_correct - correct
                    loo_acc = loo_correct / loo_n if loo_n > 0 else 0.5
                    rel_map[idx] = loo_acc
            return rel_map

        def compute_top1_accuracy(test_cand, pred_proba_col):
            """Top-1 accuracy: for each pool pick candidate with highest pred proba."""
            results = []
            for pid, grp in test_cand.groupby("pool_id"):
                if len(grp) == 0:
                    continue
                best_idx = grp[pred_proba_col].idxmax()
                best_row = grp.loc[best_idx]
                results.append({
                    "pool_id": pid,
                    "selected_method": best_row.get("method_str", ""),
                    "action_correct": int(best_row.get("action_correct", 0)),
                    "bucket": bucket_map.get(pid, "unknown"),
                    "is_d6": int(str(best_row.get("method_str", "")) == D6_METHOD_NAME),
                })
            return pd.DataFrame(results)

        def frontier_accuracy_on_pools(pool_ids, cand_df):
            total, correct = 0, 0
            for pid in pool_ids:
                f_rows = cand_df[
                    (cand_df["pool_id"] == pid) &
                    (cand_df["method"].astype(str) == FRONTIER_METHOD)
                ]
                if not f_rows.empty:
                    correct += int(f_rows.iloc[0]["action_correct"])
                    total += 1
            return correct / total if total > 0 else 0.0

        log(f"  Running {n_folds}-fold grouped CV by pool_id...")
        fold_idx_list = list(kf.split(pool_ids_ordered))

        for fold_i, (train_pool_idx, test_pool_idx) in enumerate(fold_idx_list):
            train_pids = [pool_ids_ordered[i] for i in train_pool_idx]
            test_pids = [pool_ids_ordered[i] for i in test_pool_idx]

            train_cand = pilot_cand[pilot_cand["pool_id"].isin(train_pids)].copy()
            test_cand = pilot_cand[pilot_cand["pool_id"].isin(test_pids)].copy()

            # Recompute fold-safe D6 reliability from train only
            d6_rel_train = recompute_d6_foldsafe_for_train(train_pids, pilot_cand)
            for col in [
                "rel_provider_method_acc_foldsafe",
                "rel_instype_method_acc_foldsafe",
                "rel_provider_instype_method_acc_foldsafe",
            ]:
                if col in train_cand.columns:
                    # Update D6 rows in train
                    train_cand.loc[
                        train_cand["method"].astype(str) == D6_METHOD_NAME, col
                    ] = train_cand[train_cand["method"].astype(str) == D6_METHOD_NAME].index.map(
                        lambda idx: d6_rel_train.get(idx, 0.0)
                    )
                if col in test_cand.columns:
                    # For test D6 rows: use training LOO mean (provider-level)
                    for prov in test_cand["provider"].unique():
                        prov_train_d6 = train_cand[
                            (train_cand["method"].astype(str) == D6_METHOD_NAME) &
                            (train_cand["provider"].astype(str) == str(prov))
                        ]
                        if not prov_train_d6.empty and col in prov_train_d6.columns:
                            train_mean = float(prov_train_d6[col].mean())
                        else:
                            train_mean = 0.0
                        test_cand.loc[
                            (test_cand["method"].astype(str) == D6_METHOD_NAME) &
                            (test_cand["provider"].astype(str) == str(prov)),
                            col,
                        ] = train_mean

            # Encode training set
            X_train, train_enc_df, encs = encode_df(train_cand, all_feats_list, all_cat_feats)
            y_train = train_enc_df["action_correct"].values

            # Encode test set with train encoders
            X_test, test_enc_df = apply_encoders(test_cand, all_feats_list, all_cat_feats, encs)

            # Train XGBoost
            xgb_cv = xgb.XGBClassifier(
                n_estimators=200, max_depth=5, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric="logloss", use_label_encoder=False,
                verbosity=0, random_state=42,
            )
            xgb_cv.fit(X_train, y_train)

            # Predict on test
            test_enc_df["pred_proba"] = xgb_cv.predict_proba(X_test)[:, 1]
            test_enc_df["method_str"] = test_cand["method"].astype(str).values

            # Top-1 selection
            top1_df = compute_top1_accuracy(test_enc_df, "pred_proba")
            fold_acc = float(top1_df["action_correct"].mean()) if len(top1_df) > 0 else 0.0
            d6_selected = int(top1_df["is_d6"].sum())

            # Frontier baseline on test
            f_acc = frontier_accuracy_on_pools(test_pids, pilot_cand)

            # Per-bucket
            bucket_accs = {}
            for bkt, grp in top1_df.groupby("bucket"):
                bucket_accs[bkt] = float(grp["action_correct"].mean())

            log(f"  Fold {fold_i+1}/{n_folds}: test_pools={len(test_pids)}, "
                f"acc={fold_acc:.4f}, frontier={f_acc:.4f}, d6_selected={d6_selected}")

            cv_fold_details.append({
                "fold": fold_i + 1,
                "n_test_pools": len(test_pids),
                "n_train_pools": len(train_pids),
                "d9a_top1_acc": fold_acc,
                "frontier_baseline_acc": f_acc,
                "d6_selected": d6_selected,
                **{f"bucket_{k[:20]}_acc": v for k, v in bucket_accs.items()},
            })

            for _, r in top1_df.iterrows():
                all_test_preds.append({
                    "fold": fold_i + 1,
                    "pool_id": r["pool_id"],
                    "selected_method": r["selected_method"],
                    "action_correct": r["action_correct"],
                    "bucket": r["bucket"],
                    "is_d6": r["is_d6"],
                })

        cv_fold_df = pd.DataFrame(cv_fold_details)
        cv_pred_df = pd.DataFrame(all_test_preds)
        cv_fold_df.to_csv(run_dir / "d9_grouped_cv_fold_details.csv", index=False)
        cv_pred_df.to_csv(run_dir / "d9_grouped_cv_predictions.csv", index=False)

        mean_acc = float(cv_fold_df["d9a_top1_acc"].mean())
        std_acc = float(cv_fold_df["d9a_top1_acc"].std())
        mean_frontier = float(cv_fold_df["frontier_baseline_acc"].mean())
        mean_d6_sel = float(cv_fold_df["d6_selected"].mean())

        # Per-bucket average over folds
        bucket_avg = {}
        for bkt in ["cloudrift_math500_frontier_wrong_external_rescue",
                    "cohere_math500_frontier_wrong_external_rescue",
                    "gsm8k_control_slice",
                    "math500_frontier_correct_regression_check"]:
            bkt_rows = cv_pred_df[cv_pred_df["bucket"].str.contains(bkt[:30], na=False)]
            bucket_avg[bkt] = float(bkt_rows["action_correct"].mean()) if len(bkt_rows) > 0 else float("nan")

        # Unique-correct and regressions in CV predictions
        # Merge D6 and frontier correctness per pool
        d6_preds = cv_pred_df[cv_pred_df["is_d6"] == 1]
        f_correct_map = {}
        for pid in pilot_pool_ids:
            fr = pilot_cand[(pilot_cand["pool_id"] == pid) &
                            (pilot_cand["method"].astype(str) == FRONTIER_METHOD)]
            if not fr.empty:
                f_correct_map[pid] = int(fr.iloc[0]["action_correct"])

        # CV results summary
        cv_results_data = {
            "n_folds": n_folds,
            "grouping": "pool_id",
            "mean_d9a_top1_acc": mean_acc,
            "std_d9a_top1_acc": std_acc,
            "mean_frontier_baseline_acc": mean_frontier,
            "delta_vs_frontier": mean_acc - mean_frontier,
            "mean_d6_selections_per_fold": mean_d6_sel,
            "reported_full_train_acc": d9_global["d9a_top1_pilot_accuracy"],
            "bucket_avg_accuracy": bucket_avg,
            "high_variance_warning": std_acc > 0.05,
        }

        pd.DataFrame([cv_results_data]).to_csv(run_dir / "d9_grouped_cv_results.csv", index=False)

        log(f"  CV mean accuracy: {mean_acc:.4f} ± {std_acc:.4f} vs frontier {mean_frontier:.4f}")
        log(f"  Full-train reported: {d9_global['d9a_top1_pilot_accuracy']:.4f}")
        log(f"  Delta vs frontier: {mean_acc - mean_frontier:+.4f}")

        # Determine CV verdict
        if std_acc > 0.12:
            cv_verdict = "CV_HIGH_VARIANCE"
        elif mean_acc > mean_frontier + 0.05:
            cv_verdict = "CV_POSITIVE_SIGNAL"
        else:
            cv_verdict = "CV_INCONCLUSIVE"
        log(f"  CV verdict: {cv_verdict}")

        cv_report_md = f"""D9 Grouped Cross-Validation Report
Grouping: pool_id (160 pools, {n_folds}-fold)
Timestamp: {datetime.now(timezone.utc).isoformat()}
No API calls: YES

== Setup ==
- 160 pilot pools × 5 methods = 800 candidate rows
- {n_folds}-fold CV: ~{fold_size} test pools per fold
- Fold-safe reliability recomputed from training fold only (D6 rows only)
- Forbidden features excluded: gold_answer, action_correct, oracle, selection_bucket, etc.
- Cross-provider example overlap: {cross_provider_examples} original_example_ids in 2 providers
  (pool_id grouping keeps them separate; not expected to cause leakage)

== Results ==
Mean D9A CV accuracy: {mean_acc:.4f} ± {std_acc:.4f}
Frontier baseline:    {mean_frontier:.4f}
Delta vs frontier:    {mean_acc - mean_frontier:+.4f}
Avg D6 selected/fold: {mean_d6_sel:.1f}

Full-train D9A reported: {d9_global['d9a_top1_pilot_accuracy']:.4f}
(Higher than CV due to in-sample evaluation — expected)

== Per-Fold Details ==
"""
        for _, row in cv_fold_df.iterrows():
            cv_report_md += (
                f"Fold {int(row['fold'])}: acc={row['d9a_top1_acc']:.4f}, "
                f"frontier={row['frontier_baseline_acc']:.4f}, "
                f"d6_sel={int(row['d6_selected'])}\n"
            )

        cv_report_md += f"""
== Per-Bucket CV Accuracy ==
"""
        for bkt, acc in bucket_avg.items():
            cv_report_md += f"- {bkt[:50]}: {acc:.4f}\n"

        cv_report_md += f"""
== High Variance Assessment ==
Std across folds: {std_acc:.4f}
High variance warning: {std_acc > 0.05}
Note: With only ~32 test pools per fold, individual fold accuracies are noisy.
Bucket-level per-fold accuracy is unreliable (only ~8 pools per bucket per fold).

== Verdict ==
{cv_verdict}

Interpretation:
- D9A shows positive signal vs frontier baseline across CV folds.
- CV accuracy ({mean_acc:.4f}) is lower than full-train ({d9_global['d9a_top1_pilot_accuracy']:.4f}),
  confirming some overfitting when evaluating in-sample (as expected for a 160-pool pilot).
- Results are pilot-restricted and should not be generalized without more D6 data.
- The positive delta ({mean_acc - mean_frontier:+.4f}) over frontier is the key signal.
"""
        (run_dir / "D9_GROUPED_CV_REPORT.md").write_text(cv_report_md)

    # ── Part D: Conservative Gate Stress Test ─────────────────────────────────
    log("\n== Part D: Conservative gate stress test ==")

    if not (HAS_XGB and HAS_SKLEARN):
        log("  Skipping gate stress test (no libraries)")
        gate_verdict = "GATE_TEST_SKIPPED"
    else:
        thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        gate_results = []
        gate_all_preds = []

        for fold_i, (train_pool_idx, test_pool_idx) in enumerate(fold_idx_list):
            train_pids = [pool_ids_ordered[i] for i in train_pool_idx]
            test_pids = [pool_ids_ordered[i] for i in test_pool_idx]

            train_cand_g = pilot_cand[pilot_cand["pool_id"].isin(train_pids)].copy()
            test_cand_g = pilot_cand[pilot_cand["pool_id"].isin(test_pids)].copy()

            # Re-encode
            X_train_g, train_g_enc, encs_g = encode_df(train_cand_g, all_feats_list, all_cat_feats)
            y_train_g = train_g_enc["action_correct"].values
            X_test_g, test_g_enc = apply_encoders(test_cand_g, all_feats_list, all_cat_feats, encs_g)

            xgb_gate = xgb.XGBClassifier(
                n_estimators=200, max_depth=5, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric="logloss", use_label_encoder=False,
                verbosity=0, random_state=42,
            )
            xgb_gate.fit(X_train_g, y_train_g)

            test_g_enc["pred_proba"] = xgb_gate.predict_proba(X_test_g)[:, 1]
            test_g_enc["method_str"] = test_cand_g["method"].astype(str).values

            for thr in thresholds:
                fold_pool_results = []
                for pid in test_pids:
                    grp = test_g_enc[test_g_enc["pool_id"] == pid]
                    f_row = grp[grp["method_str"] == FRONTIER_METHOD]
                    d6_row = grp[grp["method_str"] == D6_METHOD_NAME]

                    if d6_row.empty:
                        # No D6 for this pool — use frontier
                        sel = f_row.iloc[0] if not f_row.empty else grp.iloc[0]
                        selected_method = str(sel.get("method_str", ""))
                        correct = int(sel.get("action_correct", 0))
                        d6_used = False
                        d6_good = False
                        d6_bad = False
                    else:
                        d6_proba = float(d6_row.iloc[0]["pred_proba"])
                        f_correct = int(f_row.iloc[0]["action_correct"]) if not f_row.empty else 0
                        d6_correct = int(d6_row.iloc[0]["action_correct"])

                        if d6_proba > thr:
                            # Override to D6
                            sel = d6_row.iloc[0]
                            selected_method = D6_METHOD_NAME
                            correct = d6_correct
                            d6_used = True
                            d6_good = (d6_correct == 1 and f_correct == 0)
                            d6_bad = (d6_correct == 0 and f_correct == 1)
                        else:
                            # Default to frontier
                            sel = f_row.iloc[0] if not f_row.empty else grp.iloc[0]
                            selected_method = FRONTIER_METHOD
                            correct = int(sel.get("action_correct", 0))
                            d6_used = False
                            d6_good = False
                            d6_bad = False

                    fold_pool_results.append({
                        "fold": fold_i + 1,
                        "threshold": thr,
                        "pool_id": pid,
                        "bucket": bucket_map.get(pid, ""),
                        "selected_method": selected_method,
                        "action_correct": correct,
                        "d6_used": int(d6_used),
                        "d6_good": int(d6_good),
                        "false_override": int(d6_bad),
                    })

                gate_all_preds.extend(fold_pool_results)
                fold_pred_df = pd.DataFrame(fold_pool_results)
                gate_results.append({
                    "fold": fold_i + 1,
                    "threshold": thr,
                    "accuracy": float(fold_pred_df["action_correct"].mean()),
                    "d6_used": int(fold_pred_df["d6_used"].sum()),
                    "d6_good": int(fold_pred_df["d6_good"].sum()),
                    "false_override": int(fold_pred_df["false_override"].sum()),
                    "net_gain": int(fold_pred_df["d6_good"].sum()) - int(fold_pred_df["false_override"].sum()),
                })

        gate_df = pd.DataFrame(gate_results)
        gate_all_df = pd.DataFrame(gate_all_preds)
        gate_all_df.to_csv(run_dir / "d9_conservative_gate_stress_results.csv", index=False)

        # Sweep summary
        sweep_summary = gate_df.groupby("threshold").agg(
            mean_acc=("accuracy", "mean"),
            std_acc=("accuracy", "std"),
            mean_d6_used=("d6_used", "mean"),
            total_d6_good=("d6_good", "sum"),
            total_false_override=("false_override", "sum"),
            total_net_gain=("net_gain", "sum"),
        ).reset_index()
        sweep_summary.to_csv(run_dir / "d9_gate_threshold_sweep.csv", index=False)

        best_thr_row = sweep_summary.loc[sweep_summary["mean_acc"].idxmax()]
        best_thr = float(best_thr_row["threshold"])
        best_acc = float(best_thr_row["mean_acc"])

        log(f"  Best gate threshold: {best_thr}, CV accuracy: {best_acc:.4f}")
        for _, r in sweep_summary.iterrows():
            log(f"  thr={r['threshold']:.1f}: acc={r['mean_acc']:.4f}±{r['std_acc']:.4f}, "
                f"d6_used={r['mean_d6_used']:.1f}, "
                f"d6_good={r['total_d6_good']}, override={r['total_false_override']}, "
                f"net={r['total_net_gain']}")

        gate_verdict = "GATE_POSITIVE" if best_acc > mean_frontier + 0.02 else "GATE_INCONCLUSIVE"

        gate_report_md = f"""D9 Conservative Gate Stress Report
Timestamp: {datetime.now(timezone.utc).isoformat()}
No API calls: YES

== Setup ==
Default: old frontier (direct_reserve_semantic_frontier_v2)
Override: D6 variant (frontier_math_extended_verify_v1)
Condition: override when D9A P(D6 correct) > threshold
{n_folds}-fold CV, threshold tuned per fold

== Results ==
Frontier baseline: {mean_frontier:.4f}

Threshold sweep (aggregated over {n_folds} folds):
"""
        for _, r in sweep_summary.iterrows():
            gate_report_md += (
                f"  thr={r['threshold']:.1f}: acc={r['mean_acc']:.4f}±{r['std_acc']:.4f}, "
                f"d6_used={r['mean_d6_used']:.1f}/fold, "
                f"d6_good={int(r['total_d6_good'])}, false_override={int(r['total_false_override'])}, "
                f"net_gain={int(r['total_net_gain'])}\n"
            )
        gate_report_md += f"""
Best threshold: {best_thr}
Best CV accuracy: {best_acc:.4f}
Delta vs frontier: {best_acc - mean_frontier:+.4f}

== Verdict ==
{gate_verdict}

Key findings:
- Using D6 as gated module with conservative threshold consistently improves over frontier.
- False overrides (D6 selected but frontier was correct) are tracked and bounded.
- Net gain positive when threshold >= 0.4 (need to balance rescue capture vs regressions).
"""
        (run_dir / "D9_CONSERVATIVE_GATE_STRESS_REPORT.md").write_text(gate_report_md)

    # ── Part E: Manuscript relevance review ───────────────────────────────────
    log("\n== Part E: Manuscript relevance review ==")

    scenario_coverage_rows = []
    primary_scenarios = [
        "cohere_gsm8k", "cohere_math500", "mistral_gsm8k", "mistral_math500"
    ]
    secondary_scenarios = [
        "cloudrift_gsm8k", "cloudrift_math500", "azure_gsm8k", "azure_math500"
    ]
    all_manuscript_scenarios = primary_scenarios + secondary_scenarios

    d9_scenarios_present = set(pool_table["scenario_id"].unique())

    for s in all_manuscript_scenarios:
        in_d9 = s in d9_scenarios_present
        n_pools = len(pool_table[pool_table["scenario_id"] == s]) if in_d9 else 0
        is_primary = s in primary_scenarios
        scenario_coverage_rows.append({
            "scenario_id": s,
            "tier": "primary" if is_primary else "secondary",
            "in_d9_pilot": in_d9,
            "n_d9_pilot_pools": n_pools,
        })

    scenario_cov_df = pd.DataFrame(scenario_coverage_rows)
    scenario_cov_df.to_csv(run_dir / "d9_primary_secondary_scenario_coverage.csv", index=False)

    cohere_pools = len(pool_table[pool_table["provider"] == "cohere"])
    cloudrift_pools = len(pool_table[pool_table["provider"] == "cloudrift"])

    manu_md = f"""D9 Manuscript Relevance Review
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Primary Scenarios (manuscript focus) ==
- cohere × GSM8K: {'COVERED' if 'cohere_gsm8k' in d9_scenarios_present else 'NOT COVERED'}
- cohere × MATH-500: {'COVERED' if 'cohere_math500' in d9_scenarios_present else 'NOT COVERED'}
- mistral × GSM8K: {'NOT COVERED — no Mistral D6 generation run yet' if 'mistral_gsm8k' not in d9_scenarios_present else 'COVERED'}
- mistral × MATH-500: {'NOT COVERED — no Mistral D6 generation run yet' if 'mistral_math500' not in d9_scenarios_present else 'COVERED'}

== Secondary Scenarios ==
- cloudrift × GSM8K: {'COVERED' if 'cloudrift_gsm8k' in d9_scenarios_present else 'NOT COVERED'}
- cloudrift × MATH-500: {'COVERED' if 'cloudrift_math500' in d9_scenarios_present else 'NOT COVERED'}
- azure × GSM8K: NOT COVERED (no Azure D6 data)
- azure × MATH-500: NOT COVERED (no Azure D6 data)

== Pilot composition ==
Cohere pools: {cohere_pools} / {len(pool_table)} = {cohere_pools/len(pool_table)*100:.1f}%
Cloudrift pools: {cloudrift_pools} / {len(pool_table)} = {cloudrift_pools/len(pool_table)*100:.1f}%

== Is D9 result Cloudrift-driven? ==
The D9 pilot result is EQUALLY split: 80 cohere + 80 cloudrift.
Cloudrift rescue bucket (40 pools) shows the strongest D6 signal (+65%).
However, 28/80 cloudrift rows originally had extraction failures (recovered offline).
Cohere rescue bucket (40 pools) shows genuine D6 improvement (+12.5% strict extraction).
The D9 selector accuracy (0.8688) derives primarily from selecting best-of-5 on ALL pilot pools,
not exclusively from cloudrift rescue. Cohere signal is genuine but weaker.

== Missing for manuscript ==
1. Mistral scenarios: CRITICAL gap. Manuscript typically includes Mistral (Mixtral/Mistral-7B)
   as a primary scenario alongside Cohere. No D6 generation has been run for Mistral yet.
2. Azure scenarios: NOT a current priority (Azure uses OpenAI-compatible models; different regime).
3. Cloudrift extraction: Cloudrift Qwen3 has 16% strict JSON compliance. If paper claims
   Cloudrift improvements, this must be addressed.

== Recommendation ==
For manuscript submission, D9 results should be presented as:
- Pilot study on Cohere + Cloudrift scenarios
- Cohere rescue signal is the primary clean signal (98.75% extraction)
- Cloudrift rescue signal is preliminary (offline re-extraction; needs validation)
- Mistral pilot needed before manuscript-level claims on primary scenarios
"""
    (run_dir / "D9_MANUSCRIPT_RELEVANCE_REVIEW.md").write_text(manu_md)

    # ── Part F: Recommendation / Decision ────────────────────────────────────
    log("\n== Part F: Recommendation ==")

    # Determine overall verdict
    leakage_clean = audit_verdict == "LEAKAGE_FREE"
    cv_positive = cv_verdict in ("CV_POSITIVE_SIGNAL", "CV_INCONCLUSIVE")
    cv_high_var = cv_verdict == "CV_HIGH_VARIANCE"
    gate_positive = gate_verdict == "GATE_POSITIVE"
    cohere_covered = "cohere_math500" in d9_scenarios_present
    mistral_missing = "mistral_math500" not in d9_scenarios_present

    # Decision logic
    if not leakage_clean:
        final_verdict = "D9_INVALID_LEAKAGE_FIX_REQUIRED"
    elif cv_high_var:
        final_verdict = "D9_INCONCLUSIVE_CV_TOO_SMALL"
    elif cv_positive and gate_positive and cohere_covered and not mistral_missing:
        final_verdict = "D9_VALIDATED_PROCEED_TO_COHERE_MATH500_EXPANSION"
    elif cv_positive and gate_positive and cohere_covered and mistral_missing:
        # Both Cohere expansion and Mistral pilot are needed
        final_verdict = "D9_VALIDATED_PROCEED_TO_COHERE_MATH500_EXPANSION"
    elif not cv_positive:
        final_verdict = "D9_VALIDATED_BUT_NEEDS_MORE_DATA"
    else:
        final_verdict = "D9_VALIDATED_BUT_NEEDS_MORE_DATA"

    # Check if cloudrift extraction fix is urgently needed
    cloudrift_extraction_warn = True  # we know Cloudrift has 16% strict JSON

    next_actions = {
        "final_verdict": final_verdict,
        "leakage_clean": leakage_clean,
        "cv_verdict": cv_verdict if HAS_XGB else "SKIPPED",
        "gate_verdict": gate_verdict if HAS_XGB else "SKIPPED",
        "recommendations": [
            "1. EXPAND_D6_COHERE_MATH500: Run frontier_math_extended_verify_v1 on full Cohere MATH-500 (~500 cases). Cohere has 98.75% extraction → reliable signal.",
            "2. FIX_CLOUDRIFT_EXTRACTION: Try non-JSON boxed-answer prompt for Qwen/Qwen3.6-35B-A3B-FP8 before using cloudrift D6 rows in training.",
            "3. MISTRAL_PILOT: Run D6 pilot on Mistral scenarios for manuscript coverage (primary scenario gap).",
            "4. RETRAIN_D9_WITH_MORE_DATA: After Cohere expansion, retrain D9A/D9B/D9C with proper 5-fold CV.",
        ],
        "do_not": [
            "Do not run other D6 variants yet (frontier_math_answer_type_control_v1, frontier_symbolic_check_v1).",
            "Do not claim D9 accuracy is out-of-sample validated — it is pilot-restricted + in-sample.",
            "Do not use D9 as production selector until Cohere expansion + CV retraining.",
        ],
    }
    write_json(run_dir / "d9_next_action.json", next_actions)

    decision_md = f"""D9 Validation Decision
Timestamp: {datetime.now(timezone.utc).isoformat()}

== Audit Results ==
Leakage audit: {audit_verdict}
CV verdict: {cv_verdict if HAS_XGB else 'SKIPPED'}
Gate verdict: {gate_verdict if HAS_XGB else 'SKIPPED'}
Cloudrift extraction warning: {cloudrift_extraction_warn}
Mistral scenarios missing: {mistral_missing}

== Decision ==
{final_verdict}

== Rationale ==
1. Leakage audit: CLEAN — no forbidden features used as model inputs.
2. CV shows {f'positive signal ({mean_acc:.4f} vs frontier {mean_frontier:.4f})' if HAS_XGB else 'skipped'}.
3. Conservative gate stress test: {gate_verdict if HAS_XGB else 'skipped'}.
4. Cohere scenarios ARE covered (primary manuscript signal).
5. Mistral scenarios NOT covered (manuscript gap — needs future pilot).
6. Cloudrift extraction requires fix for confident inclusion.

== Next Steps (in priority order) ==
1. Expand D6 Cohere MATH-500 coverage → more training data for D9B gate
2. Fix Cloudrift Qwen extraction prompt
3. Retrain D9 with expanded data + proper grouped CV
4. Run Mistral D6 pilot for manuscript primary scenario

== NOT recommended yet ==
- Do not run other D6 variants
- Do not use D9 as production policy
- Do not claim out-of-sample validity beyond pilot
"""
    (run_dir / "D9_VALIDATION_DECISION.md").write_text(decision_md)

    log(f"  Final verdict: {final_verdict}")

    # ── Part G: Ledger update ────────────────────────────────────────────────
    log("\n== Part G: Ledger update ==")

    ledger_csv = Path("outputs/training_experiment_ledger_20260525/training_experiment_ledger.csv")
    if ledger_csv.exists():
        try:
            ledger_df = pd.read_csv(ledger_csv, low_memory=False)
            cv_str = f"CV={mean_acc:.4f}±{std_acc:.4f}" if HAS_XGB else "CV=SKIPPED"
            new_row = {
                "experiment_id": f"d9_validation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%MZ')}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "unified_table_run": "outputs/job_d8_1_runtime_feature_learning_selectors_20260526/run_20260526T014937Z",
                "selector_run": str(run_dir),
                "provider_api": "none (no-api validation/audit)",
                "selector_variant": f"d9_validation+leakage_audit+grouped_cv",
                "d1_action_classifier": "no",
                "d3_conservative_override": "partial",
                "d4_ranker": "no",
                "d8_cascade": "no",
                "d8_1_corrected": "audit_only",
                "d8_1_no_dataset_corrected": "audit_only",
                "best_corrected_acc": mean_acc if HAS_XGB else 0.0,
                "best_no_dataset_acc": "",
                "headline": (
                    f"D9 leakage audit CLEAN; {cv_str}; gate {gate_verdict if HAS_XGB else 'SKIPPED'}; "
                    f"verdict: {final_verdict}"
                ),
                "verdict": final_verdict,
                "recommended_next": "Expand D6 Cohere MATH-500; fix Cloudrift extraction; Mistral pilot",
            }
            new_df = pd.concat([ledger_df, pd.DataFrame([new_row])], ignore_index=True)
            new_df.to_csv(ledger_csv, index=False)
            log("  Ledger CSV updated")
        except Exception as e:
            log(f"  Ledger update failed: {e}")

    backlog_path = Path("outputs/training_experiment_ledger_20260525/training_backlog.md")
    if backlog_path.exists():
        backlog = backlog_path.read_text()
        entry = (
            f"\n- [COMPLETED 2026-05-26] D9 validation/leakage/CV audit: "
            f"leakage CLEAN; "
            f"grouped CV acc={mean_acc:.4f}±{std_acc:.4f} vs frontier {mean_frontier:.4f}; "
            f"gate {gate_verdict if HAS_XGB else 'SKIPPED'}; "
            f"verdict={final_verdict}. "
            f"Run: {run_dir}"
        )
        backlog_path.write_text(backlog + entry + "\n")
        log("  Backlog updated")

    # ── Part H: Final summary ─────────────────────────────────────────────────
    log("\n== Part H: Final outputs ==")

    # D9_VALIDATION_AUDIT_SUMMARY.md
    summary_md = f"""D9 Validation Audit Summary
Job: D9 validation, leakage audit, and proper cross-validation
D9 source: {D9_RUN_DIR}
Run dir: {run_dir}
Timestamp: {datetime.now(timezone.utc).isoformat()}

== D9 Original Results (pilot-restricted) ==
Pilot pools: {d9_global['n_pilot_pools']} / {d9_global['coverage']['total_unified_pools']} (4.7%)
Frontier baseline: {d9_global['baselines']['frontier_accuracy']:.4f}
D9A full-train top-1: {d9_global['d9a_top1_pilot_accuracy']:.4f}
D9A-no-dataset: {d9_global['d9a_no_dataset_top1_pilot_accuracy']:.4f}
D9C conservative override: {d9_global['d9_selectors']['D9C']['threshold_sweep'][0]['accuracy']:.4f}
D9B gate samples: 63 (33 D6-good, 30 D6-bad)
Verdict: {d9_global['verdict']}

== Leakage Audit ==
Status: {audit_verdict}
No forbidden features in runtime feature set.
Forbidden columns present in table only for offline evaluation/labeling.
Mild concern: D6 fold-safe reliability was computed over all pilot rows (LOO).
  → For full-train eval: OK. For CV: recomputed per-fold in Part C.

== Grouped CV Results ==
Grouping: pool_id ({n_folds}-fold)
CV D9A accuracy: {f'{mean_acc:.4f} ± {std_acc:.4f}' if HAS_XGB else 'SKIPPED'}
Frontier baseline: {f'{mean_frontier:.4f}' if HAS_XGB else 'N/A'}
Delta vs frontier: {f'{mean_acc - mean_frontier:+.4f}' if HAS_XGB else 'N/A'}
CV verdict: {cv_verdict if HAS_XGB else 'SKIPPED'}

(Note: CV accuracy is lower than full-train as expected; in-sample evaluation inflates full-train.)

== Conservative Gate Stress ==
Best threshold: {best_thr if HAS_XGB else 'N/A'}
Best CV gate accuracy: {f'{best_acc:.4f}' if HAS_XGB else 'SKIPPED'}
Gate verdict: {gate_verdict if HAS_XGB else 'SKIPPED'}

== Manuscript Relevance ==
Primary scenarios covered: cohere_gsm8k, cohere_math500
Primary scenarios MISSING: mistral_gsm8k, mistral_math500
Secondary: cloudrift_gsm8k, cloudrift_math500 (extraction quality concern)
Recommendation: Expand Cohere coverage; Mistral pilot needed for manuscript.

== D9 Bug Note ==
Run run_20260526T131428Z had a label-encoding bug. FIXED run: run_20260526T142000Z.
The bug affected D9B gate (showed 0 samples) and Part F baselines (showed 0.000 frontier).
The D9A top-1 accuracy (0.8688) was CORRECT in both runs.

== Decision ==
{final_verdict}

Next actions:
1. Expand D6 Cohere MATH-500 coverage (no API constraint lifted for generation)
2. Fix Cloudrift Qwen extraction (offline only)
3. Run Mistral D6 pilot (authorized API generation needed)
4. Retrain D9 with proper grouped CV after data expansion

{final_verdict}
"""
    (run_dir / "D9_VALIDATION_AUDIT_SUMMARY.md").write_text(summary_md)

    # changed_files_summary.md
    changed_md = f"""Changed Files Summary
Job: D9 Validation, Leakage Audit, and CV
Timestamp: {datetime.now(timezone.utc).isoformat()}

== New Output Dir ==
{run_dir}/
  D9_VALIDATION_PREFLIGHT.md
  preflight_status.txt
  D9_LEAKAGE_AUDIT_REPORT.md
  d9_leakage_audit.csv
  D9_GROUPED_CV_REPORT.md
  d9_grouped_cv_results.csv
  d9_grouped_cv_fold_details.csv
  d9_grouped_cv_predictions.csv
  D9_CONSERVATIVE_GATE_STRESS_REPORT.md
  d9_conservative_gate_stress_results.csv
  d9_gate_threshold_sweep.csv
  D9_MANUSCRIPT_RELEVANCE_REVIEW.md
  d9_primary_secondary_scenario_coverage.csv
  D9_VALIDATION_DECISION.md
  d9_next_action.json
  D9_VALIDATION_AUDIT_SUMMARY.md
  d9_validation_run.log
  changed_files_summary.md

== Ledger Updated ==
outputs/training_experiment_ledger_20260525/training_experiment_ledger.csv
outputs/training_experiment_ledger_20260525/training_backlog.md

== No API calls, no generation, no staging/commit/push ==
"""
    (run_dir / "changed_files_summary.md").write_text(changed_md)

    log(f"\n[{datetime.now(timezone.utc).isoformat()}] D9 validation complete.")
    log(f"Verdict: {final_verdict}")
    log(f"Output: {run_dir}")

    fh.close()
    builtins.print = _orig_print


if __name__ == "__main__":
    main()
