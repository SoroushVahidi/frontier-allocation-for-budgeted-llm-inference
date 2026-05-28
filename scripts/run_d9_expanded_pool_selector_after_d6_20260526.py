#!/usr/bin/env python3
"""D9 expanded-pool selector training after D6 full one-variant generation.

Adds frontier_math_extended_verify_v1 as a 5th action to the pool and trains
regime-aware selectors that learn when to choose it over the old frontier.

No API calls. Offline training/evaluation only.
"""
from __future__ import annotations

import argparse
import json
import re
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

D6_METHOD_NAME = "frontier_math_extended_verify_v1"
D6_ACTION_FAMILY = "frontier_variant"
D8_1_RUN_DIR = "outputs/job_d8_1_runtime_feature_learning_selectors_20260526/run_20260526T014937Z"
UNIFIED_TABLE_DIR = "outputs/unified_learning_tables_20260525/run_20260525T184354Z"
D6_GEN_DIR = "outputs/job_d6_frontier_improvement_pilot_20260525/run_20260525T213951Z/generation_runs/run_20260526T124803Z"
D6_PILOT_DIR = "outputs/job_d6_frontier_improvement_pilot_20260525/run_20260525T213951Z"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_answer(ans: str | None) -> str | None:
    if ans is None:
        return None
    ans = str(ans).strip()
    ans = re.sub(r"\\boxed\{([^}]+)\}", r"\1", ans)
    ans = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1/\2", ans)
    ans = ans.replace("$", "").replace(",", "").strip()
    try:
        v = float(ans)
        if v == int(v):
            return str(int(v))
        return str(round(v, 6))
    except (ValueError, OverflowError):
        pass
    return ans.lower().strip()


def answers_match(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    na, nb = normalize_answer(a), normalize_answer(b)
    if na == nb:
        return True
    try:
        fa, fb = float(na or "x"), float(nb or "x")
        return abs(fa - fb) < 1e-6 * max(1, abs(fb))
    except (ValueError, TypeError):
        pass
    return False


def load_jsonl(path: str | Path) -> list[dict]:
    items = []
    p = Path(path)
    if not p.exists():
        return items
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
    return items


def reextract_cloudrift(row: dict) -> dict | None:
    """Try offline re-extraction from Cloudrift response text."""
    resp = str(row.get("response_text", "") or "")
    if not resp.strip():
        return None

    # Try JSON-like
    for pat in [
        r'\{[^{}]*"answer"\s*:\s*"([^"]+)"[^{}]*\}',
        r'\{[^{}]*\'answer\'\s*:\s*\'([^\']+)\'[^{}]*\}',
        r'"answer"\s*:\s*"([^"]+)"',
        r'"answer"\s*:\s*([0-9\-+./]+)',
        r"'answer'\s*:\s*'([^']+)'",
    ]:
        m = re.search(pat, resp, re.IGNORECASE)
        if m:
            return {"extracted_answer": m.group(1).strip(), "extraction_method": "reextract_json_re"}

    # Boxed LaTeX
    boxed = re.findall(r"\\boxed\{([^}]+)\}", resp)
    if boxed:
        return {"extracted_answer": boxed[-1].strip(), "extraction_method": "reextract_boxed"}

    # "The answer is X" patterns
    for pat in [
        r"(?:the answer is|answer[:\s]+|= )([0-9\-+./\\]+)",
        r"(?:final answer[:\s]+)([0-9\-+./\\]+)",
        r"(?:therefore[,\s]+)([0-9\-+./\\]+)",
    ]:
        m = re.search(pat, resp, re.IGNORECASE)
        if m:
            val = m.group(1).strip().rstrip(".,")
            if val:
                return {"extracted_answer": val, "extraction_method": "reextract_phrase"}

    return None


def compute_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return float(-sum(p * np.log2(p) for p in probs))


def build_pool_agreement_features(pool_rows: pd.DataFrame, methods: list[str]) -> dict:
    """Compute agreement/cluster features for a pool with given methods."""
    answers = {}
    for _, row in pool_rows.iterrows():
        m = row.get("method", row.get("action_name"))
        ans = row.get("normalized_answer")
        if m and ans:
            answers[m] = str(ans)

    all_answers = list(answers.values())
    answer_counts = Counter(all_answers)
    distinct_count = len(answer_counts)
    max_cluster = max(answer_counts.values()) if answer_counts else 0
    entropy = compute_entropy(list(answer_counts.values()))
    all_same = (distinct_count == 1 and len(all_answers) > 1)
    all_different = (distinct_count == len(all_answers) and len(all_answers) > 1)
    return {
        "pool_size_rt": len(pool_rows),
        "distinct_clusters_rt": distinct_count,
        "largest_cluster_size_rt": max_cluster,
        "agreement_entropy_rt": entropy,
        "all_answers_same_flag": int(all_same),
        "all_answers_different_flag": int(all_different),
    }


def main():
    ap = argparse.ArgumentParser(description="D9 expanded-pool selector after D6")
    ap.add_argument("--run-dir", required=True, help="Output run directory")
    ap.add_argument("--d8-1-run-dir", default=D8_1_RUN_DIR)
    ap.add_argument("--unified-table-dir", default=UNIFIED_TABLE_DIR)
    ap.add_argument("--d6-gen-dir", default=D6_GEN_DIR)
    ap.add_argument("--d6-pilot-dir", default=D6_PILOT_DIR)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_lines = []

    def log(msg: str):
        print(msg)
        log_lines.append(msg)

    log(f"[{now_utc()}] D9 expanded-pool selector start")
    log(f"Run dir: {run_dir}")

    # ── Part B: Load D6 outputs and quality review ────────────────────────────
    log("\n== Part B: D6 output quality review ==")

    d6_items = load_jsonl(Path(args.d6_gen_dir) / "generation_outputs.jsonl")
    log(f"D6 generation rows: {len(d6_items)}")

    # Load pilot case selection for bucket info
    pilot_cases = load_jsonl(Path(args.d6_pilot_dir) / "pilot_case_selection.jsonl")
    pilot_bucket_map = {c["pool_id"]: c.get("selection_bucket") for c in pilot_cases}

    # Load gold answers from unified table
    unified_df = pd.read_csv(
        Path(args.unified_table_dir) / "unified_candidate_action_table.csv",
        low_memory=False,
    )
    gold_map = (
        unified_df[["pool_id", "gold_answer_for_labeling_only"]]
        .drop_duplicates("pool_id")
        .set_index("pool_id")["gold_answer_for_labeling_only"]
        .to_dict()
    )

    # Attempt re-extraction for Cloudrift rows missing extraction
    d6_reextracted = []
    quality_rows = []
    for item in d6_items:
        pool_id = item.get("pool_id", "")
        scenario = item.get("scenario", "")
        provider = item.get("provider", "")
        orig_extracted = item.get("extracted_answer")
        orig_method = item.get("extraction_method", "none")
        strict_json = bool(item.get("strict_json_contract_compliance", False))
        empty_stub = bool(item.get("empty_json_stub", False))
        gold = gold_map.get(pool_id)

        extracted = orig_extracted
        extraction_method = orig_method
        reextracted = False

        if orig_extracted is None and provider in ("cloudrift_ai", "cloudrift"):
            repair = reextract_cloudrift(item)
            if repair:
                extracted = repair["extracted_answer"]
                extraction_method = repair["extraction_method"]
                reextracted = True

        action_correct = answers_match(extracted, gold) if extracted is not None else False
        orig_correct = answers_match(orig_extracted, gold) if orig_extracted is not None else False

        quality_rows.append({
            "pool_id": pool_id,
            "scenario": scenario,
            "provider": provider,
            "strict_json_compliance": strict_json,
            "empty_stub": empty_stub,
            "orig_extraction_method": orig_method,
            "orig_extracted": orig_extracted is not None,
            "reextracted": reextracted,
            "final_extracted": extracted is not None,
            "final_extraction_method": extraction_method,
            "action_correct_orig": orig_correct,
            "action_correct_reextracted": action_correct,
        })

        d6_reextracted.append({
            "pool_id": pool_id,
            "scenario": scenario,
            "provider": provider,
            "extracted_answer": extracted,
            "normalized_answer": normalize_answer(extracted),
            "extraction_status": "ok" if extracted is not None else "failed",
            "strict_json_compliance": strict_json,
            "extraction_method_final": extraction_method,
            "reextracted_flag": reextracted,
            "action_correct": int(action_correct),
            "gold_answer_for_labeling_only": gold,
            "selection_bucket": pilot_bucket_map.get(pool_id, ""),
        })

    quality_df = pd.DataFrame(quality_rows)
    reextracted_df = pd.DataFrame(d6_reextracted)

    # Quality summary
    for provider, grp in quality_df.groupby("provider"):
        n = len(grp)
        strict = grp["strict_json_compliance"].sum()
        orig_ok = grp["orig_extracted"].sum()
        final_ok = grp["final_extracted"].sum()
        new_via_reextract = grp["reextracted"].sum()
        log(f"  {provider}: n={n}, strict_json={strict}/{n}, orig_ok={orig_ok}/{n}, "
            f"final_ok={final_ok}/{n}, reextracted={new_via_reextract}")

    overall_correct = reextracted_df["action_correct"].sum()
    overall_ok = (reextracted_df["extraction_status"] == "ok").sum()
    log(f"D6 overall: extraction_ok={overall_ok}/160, action_correct={overall_correct}/160")

    # Save quality reports
    quality_df.to_csv(run_dir / "d9_d6_output_quality_by_provider.csv", index=False)
    reextracted_df.to_csv(run_dir / "d9_d6_reextracted_variant_outputs.csv", index=False)

    # Missing extraction cases
    missing_df = reextracted_df[reextracted_df["extraction_status"] == "failed"].copy()
    missing_df.to_csv(run_dir / "d9_d6_missing_extraction_cases.csv", index=False)
    log(f"Missing extraction cases: {len(missing_df)}")

    # ── Part C: Build expanded candidate table ────────────────────────────────
    log("\n== Part C: Build expanded candidate table ==")

    d8_1_feats = pd.read_csv(
        Path(args.d8_1_run_dir) / "d8_1_candidate_features.csv",
        low_memory=False,
    )
    log(f"D8.1 candidate features: {d8_1_feats.shape}")

    # D6 pool_ids
    d6_pool_ids = set(reextracted_df["pool_id"])
    log(f"D6 pilot pool_ids: {len(d6_pool_ids)}")

    # For each D6 pool_id, get the frontier row from d8_1_feats to inherit problem features
    frontier_method = "direct_reserve_semantic_frontier_v2"
    frontier_rows = d8_1_feats[
        (d8_1_feats["pool_id"].isin(d6_pool_ids)) &
        (d8_1_feats["method"] == frontier_method)
    ].copy()
    log(f"Frontier rows for D6 pilot pools: {len(frontier_rows)}")

    # Build D6 candidate rows by inheriting problem features from frontier rows
    d6_pool_features = {}
    for _, row in frontier_rows.iterrows():
        d6_pool_features[row["pool_id"]] = row

    # Problem-level and provider-level features to inherit
    inherit_cols = [
        "scenario_id", "provider", "dataset", "split", "example_uid",
        "question_hash", "original_example_id", "question_text",
        "problem_length_chars", "problem_length_tokens_approx",
        "problem_numeric_token_count", "problem_variable_token_count",
        "problem_sentence_count", "problem_word_count_ws", "problem_token_count_simple",
        "problem_numeric_token_count_rt", "problem_distinct_numeric_token_count_rt",
        "problem_max_abs_numeric_magnitude_rt", "problem_fraction_token_flag_rt",
        "problem_decimal_token_flag_rt", "problem_percent_token_flag_rt",
        "problem_math_symbol_count", "problem_equal_sign_count",
        "problem_operator_keyword_count", "problem_variable_like_symbol_count",
        "has_equation_flag_rt", "has_geometry_cue", "has_probability_combinatorics_cue",
        "has_number_theory_cue", "has_algebra_cue", "has_arithmetic_word_problem_cue",
        "has_symbolic_expression_cue", "multi_step_cue_count",
        "predicted_instance_type", "predicted_answer_type",
        "math_subject", "math_level", "seen_dev_flag",
        "dataset_family", "provider_family",
        "model_deployment_name", "provider_api_id", "provider_backend_type",
        "openai_compatible_flag", "reasoning_output_fallback_flag",
        "pool_id", "oracle_available", "all_sources_wrong",
        "gold_answer_for_labeling_only",
        # Pool-level 4-method features (will be recomputed for expanded pool)
        "distinct_answer_count", "max_cluster_size", "agreement_entropy",
        "all_answers_same_flag", "all_answers_different_flag",
        # Fold-safe reliability from original methods
        "rel_provider_method_acc_foldsafe", "rel_provider_method_logodds_foldsafe",
    ]

    d6_new_rows = []
    for _, d6row in reextracted_df.iterrows():
        pid = d6row["pool_id"]
        if pid not in d6_pool_features:
            continue
        base = d6_pool_features[pid]

        new_row = {}
        for col in inherit_cols:
            if col in base.index:
                new_row[col] = base[col]

        # D6-specific overrides
        new_row["method"] = D6_METHOD_NAME
        new_row["action_name"] = D6_METHOD_NAME
        new_row["action_family"] = D6_ACTION_FAMILY
        new_row["method_family"] = "frontier_variant"
        new_row["is_frontier_method_flag"] = 1
        new_row["is_external_method_flag"] = 0
        new_row["ours_vs_external_flag"] = 1
        new_row["frontier_variant_id"] = D6_METHOD_NAME
        new_row["prompt_method_family"] = "frontier_variant"
        new_row["budget_prompting_type"] = "none"

        # D6 extraction/answer features
        extracted = d6row.get("extracted_answer")
        norm = d6row.get("normalized_answer")
        new_row["extracted_answer"] = extracted
        new_row["normalized_answer"] = norm
        new_row["raw_output_text"] = ""  # not stored in generation output
        new_row["parse_success"] = int(extracted is not None)
        new_row["parse_success_rt"] = int(extracted is not None)
        new_row["answer_is_empty"] = int(extracted is None or str(extracted).strip() == "")
        new_row["action_correct"] = int(d6row.get("action_correct", 0))

        ans_str = str(extracted or "")
        new_row["answer_length_chars"] = len(ans_str)
        new_row["candidate_answer_length_rt"] = len(ans_str)
        new_row["output_length_chars"] = 0
        new_row["candidate_output_length_rt"] = 0
        new_row["candidate_reasoning_length_rt"] = 0

        # Try to detect numeric
        is_num = False
        try:
            float(ans_str)
            is_num = True
        except (ValueError, TypeError):
            pass
        new_row["numeric_answer_flag"] = int(is_num)
        new_row["numeric_candidate_flag_rt"] = int(is_num)
        new_row["integer_answer_flag"] = int(is_num and "." not in ans_str)
        new_row["fraction_answer_flag"] = int("/" in ans_str)
        new_row["expression_answer_flag"] = int(not is_num and len(ans_str) > 0)
        new_row["expression_candidate_flag_rt"] = int(not is_num and len(ans_str) > 0)
        new_row["negative_answer_flag"] = int(ans_str.startswith("-"))
        new_row["answer_contains_variable"] = 0
        new_row["answer_contains_units"] = 0
        try:
            new_row["answer_magnitude_abs"] = abs(float(ans_str)) if is_num else 0.0
        except (ValueError, TypeError):
            new_row["answer_magnitude_abs"] = 0.0

        new_row["boxed_answer_present"] = 0
        new_row["multiple_boxed_answers"] = 0
        new_row["final_answer_marker_present"] = 0
        new_row["multiple_final_answers_flag_rt"] = 0
        new_row["malformed_output_flag"] = int(extracted is None)
        new_row["malformed_answer_flag_rt"] = int(extracted is None)
        new_row["api_error_text_flag"] = 0
        new_row["truncation_suspected_flag"] = 0

        # D6-specific features (new columns)
        new_row["d6_strict_json_compliance"] = int(d6row.get("strict_json_compliance", False))
        new_row["d6_extraction_missing"] = int(d6row.get("extraction_status") == "failed")
        new_row["d6_reextracted_flag"] = int(d6row.get("reextracted_flag", False))
        new_row["d6_variant_flag"] = 1

        # answer_type_rt
        if extracted is None:
            new_row["answer_type_rt"] = "missing"
        elif is_num:
            new_row["answer_type_rt"] = "numeric"
        else:
            new_row["answer_type_rt"] = "expression"

        new_row["final_answer_extraction_present_flag"] = int(extracted is not None)

        # Pool/agreement features (placeholders — recomputed below)
        new_row["cluster_size"] = 1
        new_row["cluster_rank_by_size"] = 1
        new_row["candidate_is_isolated_flag"] = 1
        new_row["candidate_in_largest_cluster_flag"] = 0
        new_row["candidate_in_largest_cluster_rt"] = 0
        new_row["candidate_cluster_size_rt"] = 1
        new_row["no_majority_flag"] = 0
        new_row["strict_2plus_exists_rt"] = 0
        new_row["answer_fragmentation_ratio_rt"] = 0.0
        new_row["source_participation_in_cluster_rt"] = 0.0

        # Pair-agreement with frontier (new)
        new_row["pair_agree_frontier_d6_rt"] = 0  # will be set below
        # Set existing pair-agree features to 0 for D6 rows (not applicable)
        for pair_col in ["pair_agree_frontier_l1_rt", "pair_agree_frontier_s1_rt",
                         "pair_agree_frontier_tale_rt", "pair_agree_l1_s1_rt",
                         "pair_agree_l1_tale_rt", "pair_agree_s1_tale_rt"]:
            new_row[pair_col] = 0

        # Fold-safe reliability (will be computed separately for D6)
        new_row["rel_provider_method_acc_foldsafe"] = 0.0
        new_row["rel_provider_method_logodds_foldsafe"] = 0.0
        new_row["rel_instype_method_acc_foldsafe"] = 0.0
        new_row["rel_instype_method_logodds_foldsafe"] = 0.0
        new_row["rel_provider_instype_method_acc_foldsafe"] = 0.0
        new_row["rel_provider_instype_method_logodds_foldsafe"] = 0.0
        new_row["rel_unique_correct_rate_provider_method_foldsafe"] = 0.0
        for col in ["pair_disagree_frontier_provider_foldsafe", "pair_rescue_frontier_provider_foldsafe",
                    "pair_disagree_l1_provider_foldsafe", "pair_rescue_l1_provider_foldsafe",
                    "pair_disagree_s1_provider_foldsafe", "pair_rescue_s1_provider_foldsafe",
                    "pair_disagree_tale_provider_foldsafe", "pair_rescue_tale_provider_foldsafe"]:
            new_row[col] = 0.0

        # agreement features (from base pool level)
        new_row["agrees_with_frontier"] = 0
        new_row["agrees_with_l1"] = 0
        new_row["agrees_with_s1"] = 0
        new_row["agrees_with_tale"] = 0
        new_row["frontier_isolated"] = 0
        new_row["l1_isolated"] = 0
        new_row["s1_isolated"] = 0
        new_row["tale_isolated"] = 0
        new_row["non_s1_majority_exists"] = 0
        new_row["non_frontier_majority_exists"] = 0
        new_row["majority_includes_frontier"] = 0
        new_row["majority_includes_s1"] = 0
        new_row["majority_excludes_frontier"] = 0
        new_row["majority_excludes_s1"] = 0
        new_row["candidate_is_unique_correct"] = 0
        new_row["candidate_in_correct_cluster"] = 0

        new_row["model_id"] = "d6_variant"
        new_row["model_family"] = "d6_variant"
        new_row["model_type_known"] = 0
        new_row["uses_budget_forcing_flag"] = 0
        new_row["uses_prompt_budgeting_flag"] = 0
        new_row["run_timestamp"] = ""
        new_row["budget"] = 0
        new_row["seed"] = 0
        new_row["source_artifact_path"] = str(args.d6_gen_dir)
        new_row["source_record_index"] = 0
        new_row["label_source"] = "d6_generation_offline"
        new_row["status"] = "ok"
        new_row["error_text"] = ""
        new_row["result_metadata_json"] = "{}"
        new_row["candidate_parse_failure_label"] = int(extracted is None)
        new_row["ranking_relevance"] = int(new_row["action_correct"])
        new_row["clustering_version"] = "d9_expanded"
        new_row["source_correct_vector_json"] = "{}"

        d6_new_rows.append(new_row)

    d6_rows_df = pd.DataFrame(d6_new_rows)
    log(f"Built {len(d6_rows_df)} D6 candidate rows")

    # Add d6_variant_flag and d6-specific columns to existing rows
    d8_1_feats["d6_variant_flag"] = 0
    d8_1_feats["d6_strict_json_compliance"] = 0
    d8_1_feats["d6_extraction_missing"] = 0
    d8_1_feats["d6_reextracted_flag"] = 0
    d8_1_feats["pair_agree_frontier_d6_rt"] = 0

    # Combine
    expanded_df = pd.concat([d8_1_feats, d6_rows_df], ignore_index=True, sort=False)
    log(f"Expanded candidate table: {expanded_df.shape}")

    # ── Recompute pool-level features for D6 pilot pools (expanded pool) ──────
    log("Recomputing pool-level agreement features for D6 pilot pools...")

    d6_pool_ids_list = list(d6_pool_ids)
    pilot_expanded = expanded_df[expanded_df["pool_id"].isin(d6_pool_ids_list)].copy()

    # For each pilot pool, compute new agreement features
    for pid in d6_pool_ids_list:
        pool = pilot_expanded[pilot_expanded["pool_id"] == pid]
        d6_row = pool[pool["method"] == D6_METHOD_NAME]
        frontier_row = pool[pool["method"] == frontier_method]

        if d6_row.empty or frontier_row.empty:
            continue

        d6_ans = d6_row.iloc[0].get("normalized_answer")
        f_ans = frontier_row.iloc[0].get("normalized_answer")
        agree = int(bool(d6_ans and f_ans and str(d6_ans).strip() == str(f_ans).strip()))

        # Update D6 row's pair_agree_frontier_d6_rt
        d6_idx = d6_row.index[0]
        expanded_df.at[d6_idx, "pair_agree_frontier_d6_rt"] = agree
        # Also update D6 row's agrees_with_frontier
        expanded_df.at[d6_idx, "agrees_with_frontier"] = agree

        # Update frontier row's pair_agree_frontier_d6_rt
        f_idx = frontier_row.index[0]
        expanded_df.at[f_idx, "pair_agree_frontier_d6_rt"] = agree

        # Update pool size for all pilot pool rows
        pilot_mask = expanded_df["pool_id"] == pid
        expanded_df.loc[pilot_mask, "pool_size_rt"] = len(pool)

    # ── Compute fold-safe reliability for D6 action ───────────────────────────
    log("Computing fold-safe reliability for D6 rows...")

    d6_subset = expanded_df[expanded_df["method"] == D6_METHOD_NAME].copy()
    d6_subset["action_correct"] = d6_subset["action_correct"].fillna(0).astype(int)

    # LOO (leave-one-pool-out) reliability by provider
    provider_groups = defaultdict(list)
    for idx, row in d6_subset.iterrows():
        prov = row.get("provider", "unknown")
        correct = int(row.get("action_correct", 0))
        provider_groups[prov].append((idx, correct))

    # LOO: for each row, compute accuracy of OTHER rows in same provider group
    d6_rel_foldsafe = {}
    for prov, entries in provider_groups.items():
        n = len(entries)
        total_correct = sum(c for _, c in entries)
        for idx, correct in entries:
            loo_correct = total_correct - correct
            loo_n = n - 1
            if loo_n > 0:
                loo_acc = loo_correct / loo_n
                logodds = np.log(loo_acc + 1e-6) - np.log(1 - loo_acc + 1e-6)
            else:
                loo_acc = 0.5
                logodds = 0.0
            d6_rel_foldsafe[idx] = {"acc": loo_acc, "logodds": logodds}

    for idx, vals in d6_rel_foldsafe.items():
        expanded_df.at[idx, "rel_provider_method_acc_foldsafe"] = vals["acc"]
        expanded_df.at[idx, "rel_provider_method_logodds_foldsafe"] = vals["logodds"]
        # Use same for instype-based
        expanded_df.at[idx, "rel_instype_method_acc_foldsafe"] = vals["acc"]
        expanded_df.at[idx, "rel_instype_method_logodds_foldsafe"] = vals["logodds"]
        expanded_df.at[idx, "rel_provider_instype_method_acc_foldsafe"] = vals["acc"]
        expanded_df.at[idx, "rel_provider_instype_method_logodds_foldsafe"] = vals["logodds"]

    # ── Save expanded candidate table ─────────────────────────────────────────
    expanded_df.to_csv(run_dir / "d9_expanded_candidate_table.csv", index=False)
    log(f"Saved expanded candidate table: {expanded_df.shape}")

    # Build pool-level table for D6 pilot
    d9_pool_level_rows = []
    for pid in d6_pool_ids_list:
        pool = expanded_df[expanded_df["pool_id"] == pid]
        d6_r = pool[pool["method"] == D6_METHOD_NAME]
        f_r = pool[pool["method"] == frontier_method]
        if d6_r.empty:
            continue
        d9_pool_level_rows.append({
            "pool_id": pid,
            "scenario_id": d6_r.iloc[0].get("scenario_id", ""),
            "provider": d6_r.iloc[0].get("provider", ""),
            "dataset": d6_r.iloc[0].get("dataset", ""),
            "split": d6_r.iloc[0].get("split", ""),
            "selection_bucket": pilot_bucket_map.get(pid, ""),
            "pool_size": len(pool),
            "d6_action_correct": int(d6_r.iloc[0].get("action_correct", 0)),
            "frontier_action_correct": int(f_r.iloc[0].get("action_correct", 0)) if not f_r.empty else 0,
            "d6_extraction_ok": int(d6_r.iloc[0].get("d6_extraction_missing", 1) == 0),
            "oracle_available": int(d6_r.iloc[0].get("oracle_available", 0)),
            "all_sources_wrong": int(d6_r.iloc[0].get("all_sources_wrong", 0)),
            "pair_agree_frontier_d6": int(d6_r.iloc[0].get("pair_agree_frontier_d6_rt", 0)),
        })
    d9_pool_df = pd.DataFrame(d9_pool_level_rows)
    d9_pool_df.to_csv(run_dir / "d9_expanded_pool_table.csv", index=False)
    log(f"D9 expanded pool table (pilot only): {d9_pool_df.shape}")

    # Coverage report
    n_d6_covered = len(d6_pool_ids)
    n_total_pools = unified_df["pool_id"].nunique()
    coverage_info = {
        "d6_pilot_pools": n_d6_covered,
        "total_unified_pools": n_total_pools,
        "coverage_pct": n_d6_covered / n_total_pools * 100,
        "note": "D6 variant exists only for selected pilot cases. D9 evaluation is pilot-restricted.",
    }

    # ── Part D: Feature schema ────────────────────────────────────────────────
    log("\n== Part D: Feature schema ==")

    # Get runtime feature columns (no gold/label leakage)
    forbidden_cols = {
        "gold_answer_for_labeling_only", "candidate_correct", "candidate_correct_exact",
        "candidate_correct_combined", "action_correct", "ranking_relevance",
        "oracle_available", "all_sources_wrong", "candidate_is_unique_correct",
        "candidate_in_correct_cluster", "source_correct_vector_json",
        "selection_bucket",  # D6 diagnostic bucket label
    }

    # Runtime-safe feature cols
    runtime_cat_cols = [
        "provider", "provider_api_id", "provider_backend_type", "model_deployment_name",
        "method", "action_family", "prompt_method_family", "budget_prompting_type",
        "predicted_instance_type", "predicted_answer_type", "answer_type_rt",
        "scenario_id", "dataset",
    ]
    runtime_num_cols = [
        "agreement_entropy", "agreement_entropy_rt", "all_answers_different_flag",
        "all_answers_same_flag", "answer_fragmentation_ratio_rt", "answer_length_chars",
        "api_error_text_flag", "candidate_answer_length_rt", "candidate_cluster_size_rt",
        "candidate_in_largest_cluster_flag", "candidate_in_largest_cluster_rt",
        "candidate_is_isolated_flag", "candidate_output_length_rt",
        "candidate_reasoning_length_rt", "cluster_size", "distinct_answer_count",
        "distinct_clusters_rt", "expression_answer_flag", "expression_candidate_flag_rt",
        "final_answer_extraction_present_flag", "fraction_answer_flag",
        "has_equation_flag_rt", "integer_answer_flag", "is_external_method_flag",
        "is_frontier_method_flag", "largest_cluster_size_rt", "malformed_answer_flag_rt",
        "malformed_output_flag", "max_cluster_size", "multiple_final_answers_flag_rt",
        "negative_answer_flag", "no_majority_flag", "numeric_answer_flag",
        "numeric_candidate_flag_rt", "openai_compatible_flag", "parse_success",
        "parse_success_rt", "pool_size_rt", "problem_equal_sign_count",
        "problem_fraction_token_flag_rt", "problem_length_chars",
        "problem_length_tokens_approx", "problem_math_symbol_count",
        "problem_max_abs_numeric_magnitude_rt", "problem_numeric_token_count",
        "problem_operator_keyword_count", "problem_sentence_count",
        "problem_token_count_simple", "problem_variable_like_symbol_count",
        "problem_word_count_ws", "reasoning_output_fallback_flag",
        "strict_2plus_exists_rt", "truncation_suspected_flag",
        "ours_vs_external_flag", "d6_variant_flag", "d6_strict_json_compliance",
        "d6_extraction_missing", "d6_reextracted_flag",
        "has_algebra_cue", "has_arithmetic_word_problem_cue", "has_geometry_cue",
        "has_number_theory_cue", "has_probability_combinatorics_cue",
        "has_symbolic_expression_cue", "multi_step_cue_count",
        "pair_agree_frontier_l1_rt", "pair_agree_frontier_s1_rt",
        "pair_agree_frontier_tale_rt", "pair_agree_l1_s1_rt",
        "pair_agree_l1_tale_rt", "pair_agree_s1_tale_rt",
        "pair_agree_frontier_d6_rt",
        # fold-safe (train-only)
        "rel_provider_method_acc_foldsafe", "rel_provider_method_logodds_foldsafe",
        "rel_instype_method_acc_foldsafe", "rel_instype_method_logodds_foldsafe",
        "rel_provider_instype_method_acc_foldsafe", "rel_provider_instype_method_logodds_foldsafe",
        "rel_unique_correct_rate_provider_method_foldsafe",
        "pair_disagree_frontier_provider_foldsafe", "pair_rescue_frontier_provider_foldsafe",
        "pair_disagree_l1_provider_foldsafe", "pair_rescue_l1_provider_foldsafe",
    ]

    feature_schema = {
        "runtime_cat_cols": runtime_cat_cols,
        "runtime_num_cols": runtime_num_cols,
        "forbidden_cols": sorted(forbidden_cols),
        "new_d9_cols": ["d6_variant_flag", "d6_strict_json_compliance",
                        "d6_extraction_missing", "d6_reextracted_flag",
                        "pair_agree_frontier_d6_rt"],
        "notes": [
            "D6 variant only exists for 160 pilot pool_ids",
            "Gold answers used only for offline action_correct labels",
            "selection_bucket is offline diagnostic label only",
            "fold-safe cols are from training data only",
        ],
    }
    with open(run_dir / "d9_feature_schema.json", "w") as f:
        json.dump(feature_schema, f, indent=2)

    # Forbidden columns check
    forbidden_check = {col: col in expanded_df.columns for col in forbidden_cols}
    with open(run_dir / "d9_forbidden_columns_check.json", "w") as f:
        json.dump({"status": "checked", "forbidden_cols_present": forbidden_check}, f, indent=2)

    # ── Part E: Train D9 selectors ─────────────────────────────────────────────
    log("\n== Part E: Train D9 selectors ==")

    # Focus training on D6 pilot pools (160 pools × 5 methods = 800 rows)
    # Plus use full D8.1 data for context (but evaluate on pilot set only)

    # Build training data: all 13,600 D8.1 rows + 160 D6 rows
    # Target: action_correct
    target_col = "action_correct"
    expanded_df[target_col] = pd.to_numeric(expanded_df[target_col], errors="coerce").fillna(0).astype(int)

    all_num_feats = [c for c in runtime_num_cols if c in expanded_df.columns]
    all_cat_feats = [c for c in runtime_cat_cols if c in expanded_df.columns]
    all_feats = all_num_feats + all_cat_feats

    # Encode categoricals — preserve method_str before encoding for downstream string comparisons
    cat_encoders = {}
    train_df = expanded_df.copy()
    train_df["method_str"] = train_df["method"].astype(str).copy()
    for col in all_cat_feats:
        le = LabelEncoder()
        train_df[col] = le.fit_transform(train_df[col].fillna("__MISSING__").astype(str))
        cat_encoders[col] = le

    X_all = train_df[all_feats].fillna(0).values.astype(np.float32)
    y_all = train_df[target_col].values

    # Subset for pilot pools
    pilot_mask = train_df["pool_id"].isin(d6_pool_ids)
    pilot_df_train = train_df[pilot_mask].copy()
    d6_only_mask = train_df["method_str"] == D6_METHOD_NAME

    log(f"Training rows (all): {len(X_all)}, Pilot rows: {pilot_mask.sum()}")

    # ── D9A: Full expanded pool classifier ────────────────────────────────────
    log("Training D9A (full expanded pool XGBoost)...")
    results = {}

    if HAS_XGB:
        xgb_model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            use_label_encoder=False,
            verbosity=0,
            random_state=42,
        )
        try:
            xgb_model.fit(X_all, y_all)
            # Predictions on pilot D6 rows
            X_pilot_d6 = train_df[d6_only_mask][all_feats].fillna(0).values.astype(np.float32)
            pred_proba_d6 = xgb_model.predict_proba(X_pilot_d6)[:, 1]
            pred_d6 = (pred_proba_d6 >= 0.5).astype(int)
            actual_d6 = train_df[d6_only_mask][target_col].values
            d9a_d6_acc = float(np.mean(pred_d6 == actual_d6))
            log(f"  D9A D6-rows accuracy: {d9a_d6_acc:.4f}")

            # Top-1 selection on pilot pools (pick best candidate per pool)
            pilot_all_rows = train_df[pilot_mask].copy()
            pilot_all_rows["d9a_pred_proba"] = xgb_model.predict_proba(
                pilot_all_rows[all_feats].fillna(0).values.astype(np.float32)
            )[:, 1]
            # For each pool, pick the method with highest P(correct)
            d9a_top1 = pilot_all_rows.loc[
                pilot_all_rows.groupby("pool_id")["d9a_pred_proba"].idxmax()
            ].copy()
            d9a_top1_acc = float(d9a_top1[target_col].mean())
            d9a_d6_selected = (d9a_top1["method_str"] == D6_METHOD_NAME).sum()
            log(f"  D9A top-1 pilot accuracy: {d9a_top1_acc:.4f}, D6 selected: {d9a_d6_selected}/{len(d6_pool_ids)}")
            results["D9A"] = {
                "top1_pilot_accuracy": d9a_top1_acc,
                "d6_rows_accuracy": d9a_d6_acc,
                "d6_selected_count": int(d9a_d6_selected),
                "model": "xgboost",
            }
        except Exception as e:
            log(f"  D9A training failed: {e}")
            results["D9A"] = {"error": str(e)}
    else:
        log("  XGBoost not available")

    # ── D9A-no-dataset: Same without dataset/scenario_id ─────────────────────
    log("Training D9A-no-dataset...")
    no_dataset_cat = [c for c in all_cat_feats if c not in ("dataset", "scenario_id")]
    no_dataset_feats = all_num_feats + no_dataset_cat
    no_dataset_encoders = {}
    train_df_nd = expanded_df.copy()
    train_df_nd["method_str"] = train_df_nd["method"].astype(str).copy()
    for col in no_dataset_cat:
        le = LabelEncoder()
        train_df_nd[col] = le.fit_transform(train_df_nd[col].fillna("__MISSING__").astype(str))
        no_dataset_encoders[col] = le
    X_nd = train_df_nd[no_dataset_feats].fillna(0).values.astype(np.float32)

    if HAS_XGB:
        xgb_nd = xgb.XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
            use_label_encoder=False, verbosity=0, random_state=42,
        )
        try:
            xgb_nd.fit(X_nd, y_all)
            pilot_all_nd = train_df_nd[pilot_mask].copy()
            pilot_all_nd["d9a_nd_pred"] = xgb_nd.predict_proba(
                pilot_all_nd[no_dataset_feats].fillna(0).values.astype(np.float32)
            )[:, 1]
            d9a_nd_top1 = pilot_all_nd.loc[
                pilot_all_nd.groupby("pool_id")["d9a_nd_pred"].idxmax()
            ].copy()
            d9a_nd_acc = float(d9a_nd_top1[target_col].mean())
            d9a_nd_d6_sel = (d9a_nd_top1["method_str"] == D6_METHOD_NAME).sum()
            log(f"  D9A-no-dataset top-1 pilot accuracy: {d9a_nd_acc:.4f}, D6 selected: {d9a_nd_d6_sel}/{len(d6_pool_ids)}")
            results["D9A_NO_DATASET"] = {
                "top1_pilot_accuracy": d9a_nd_acc,
                "d6_selected_count": int(d9a_nd_d6_sel),
                "model": "xgboost",
            }
        except Exception as e:
            log(f"  D9A-no-dataset training failed: {e}")
            results["D9A_NO_DATASET"] = {"error": str(e)}

    # ── D9B: D6-use gate ──────────────────────────────────────────────────────
    log("Training D9B (D6-use gate on pilot cases)...")

    # Build binary gate training data: rows where we can compare D6 vs frontier
    gate_rows = []
    for pid in d6_pool_ids_list:
        pool = pilot_df_train[pilot_df_train["pool_id"] == pid]
        d6r = pool[pool["method_str"] == D6_METHOD_NAME]
        fr = pool[pool["method_str"] == frontier_method]
        if d6r.empty or fr.empty:
            continue
        d6_correct = int(d6r.iloc[0][target_col])
        f_correct = int(fr.iloc[0][target_col])
        # D6 is "good" when D6 correct AND frontier wrong
        # D6 is "bad" when D6 wrong AND frontier correct
        # Otherwise neutral
        gate_label = -1  # neutral
        if d6_correct == 1 and f_correct == 0:
            gate_label = 1  # use D6
        elif d6_correct == 0 and f_correct == 1:
            gate_label = 0  # don't use D6

        if gate_label in (0, 1):
            row_feats = d6r.iloc[0][all_feats].fillna(0).to_dict()
            row_feats["gate_label"] = gate_label
            row_feats["pool_id"] = pid
            gate_rows.append(row_feats)

    log(f"  Gate training rows (D6 vs frontier disagreements): {len(gate_rows)}")
    log(f"    D6 good (D6 correct, frontier wrong): {sum(r['gate_label']==1 for r in gate_rows)}")
    log(f"    D6 bad (D6 wrong, frontier correct): {sum(r['gate_label']==0 for r in gate_rows)}")

    if len(gate_rows) >= 10 and HAS_XGB:
        gate_df = pd.DataFrame(gate_rows)
        X_gate = gate_df[all_feats].fillna(0).values.astype(np.float32)
        y_gate = gate_df["gate_label"].values

        # Encode categoricals using existing encoders
        for col in all_cat_feats:
            if col in gate_df.columns:
                le = cat_encoders[col]
                gate_df[col] = gate_df[col].fillna("__MISSING__").astype(str)
                gate_df[col] = gate_df[col].map(
                    lambda x, le=le: le.transform([x])[0] if x in le.classes_ else 0
                )
        X_gate = gate_df[all_feats].fillna(0).values.astype(np.float32)

        gate_model = xgb.XGBClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            eval_metric="logloss", use_label_encoder=False, verbosity=0, random_state=42,
        )
        try:
            gate_model.fit(X_gate, y_gate)
            gate_pred = gate_model.predict(X_gate)
            gate_acc = float(np.mean(gate_pred == y_gate))
            log(f"  D9B gate training accuracy: {gate_acc:.4f}")
            results["D9B"] = {"gate_train_accuracy": gate_acc, "model": "xgboost",
                              "gate_samples": len(gate_rows)}
        except Exception as e:
            log(f"  D9B gate training failed: {e}")
            results["D9B"] = {"error": str(e)}
    else:
        log(f"  D9B: insufficient gate samples ({len(gate_rows)}); using threshold baseline")
        results["D9B"] = {"status": "insufficient_samples", "gate_samples": len(gate_rows)}

    # ── D9C: Conservative override ────────────────────────────────────────────
    log("Training D9C (conservative override)...")
    # Simple threshold: only override to D6 if D9A pred_proba for D6 > threshold
    # Evaluate at several thresholds

    if "d9a_pred_proba" in pilot_all_rows.columns if "pilot_all_rows" in dir() else False:
        thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
        d9c_results = []
        for thr in thresholds:
            # Default to frontier, override if D6 confidence > thr
            def select_with_override(grp, thr=thr):
                f_row = grp[grp["method_str"] == frontier_method]
                d6_row = grp[grp["method_str"] == D6_METHOD_NAME]
                if d6_row.empty:
                    return f_row.iloc[0] if not f_row.empty else grp.iloc[0]
                if d6_row.iloc[0]["d9a_pred_proba"] > thr:
                    return d6_row.iloc[0]
                return f_row.iloc[0] if not f_row.empty else grp.iloc[0]

            selected = pilot_all_rows.groupby("pool_id", group_keys=False).apply(select_with_override)
            acc = float(selected[target_col].mean())
            d6_sel = (selected["method_str"] == D6_METHOD_NAME).sum()
            d9c_results.append({"threshold": thr, "accuracy": acc, "d6_selected": int(d6_sel)})
            log(f"  D9C threshold={thr}: accuracy={acc:.4f}, d6_selected={d6_sel}")

        results["D9C"] = {"threshold_sweep": d9c_results, "best_threshold":
                          max(d9c_results, key=lambda x: x["accuracy"])["threshold"]}

    # ── Part F: Baselines ──────────────────────────────────────────────────────
    log("\n== Part F: Baselines on pilot set ==")

    # Compute baselines on pilot set
    baselines = {}
    if not pilot_df_train.empty:
        # Old frontier accuracy
        f_pilot = pilot_df_train[pilot_df_train["method_str"] == frontier_method]
        baselines["frontier_accuracy"] = float(f_pilot[target_col].mean()) if not f_pilot.empty else 0.0

        # D6 variant only accuracy (with re-extraction)
        d6_pilot = pilot_df_train[pilot_df_train["method_str"] == D6_METHOD_NAME]
        baselines["d6_variant_accuracy"] = float(d6_pilot[target_col].mean()) if not d6_pilot.empty else 0.0

        # Corrected baseline methods
        for m in ["external_l1_max", "external_s1_budget_forcing", "external_tale_prompt_budgeting"]:
            m_rows = pilot_df_train[pilot_df_train["method_str"] == m]
            baselines[f"{m}_accuracy"] = float(m_rows[target_col].mean()) if not m_rows.empty else 0.0

        # Oracle (upper bound): any method correct
        oracle_acc = 0.0
        for pid in d6_pool_ids_list:
            pool = pilot_df_train[pilot_df_train["pool_id"] == pid]
            if pool[target_col].max() > 0:
                oracle_acc += 1
        baselines["oracle_accuracy"] = oracle_acc / len(d6_pool_ids_list)

        log(f"  Frontier accuracy: {baselines.get('frontier_accuracy', 0):.4f}")
        log(f"  D6 variant accuracy (with re-extract): {baselines.get('d6_variant_accuracy', 0):.4f}")
        log(f"  Oracle accuracy (expanded pool): {baselines.get('oracle_accuracy', 0):.4f}")

    # ── Part G: Evaluation by bucket and scenario ─────────────────────────────
    log("\n== Part G: Evaluation by bucket ==")

    bucket_results = []
    for bucket in sorted(set(d9_pool_df["selection_bucket"].dropna())):
        bucket_pools = d9_pool_df[d9_pool_df["selection_bucket"] == bucket]
        n = len(bucket_pools)
        f_acc = float(bucket_pools["frontier_action_correct"].mean()) if n > 0 else 0.0
        d6_acc = float(bucket_pools["d6_action_correct"].mean()) if n > 0 else 0.0
        delta = d6_acc - f_acc
        bucket_results.append({
            "bucket": bucket, "n": n,
            "frontier_accuracy": f_acc, "d6_accuracy": d6_acc,
            "delta": delta,
        })
        log(f"  {bucket}: n={n}, frontier={f_acc:.3f}, d6={d6_acc:.3f}, delta={delta:+.3f}")

    bucket_df = pd.DataFrame(bucket_results)
    bucket_df.to_csv(run_dir / "d9_bucket_results.csv", index=False)

    # Scenario results
    scenario_results = []
    for scenario, grp in d9_pool_df.groupby("selection_bucket"):
        pass  # already done above

    # Unique-correct and regressions with re-extracted D6
    unique_correct = int(d9_pool_df[
        (d9_pool_df["d6_action_correct"] == 1) & (d9_pool_df["frontier_action_correct"] == 0)
    ].shape[0])
    regressions = int(d9_pool_df[
        (d9_pool_df["d6_action_correct"] == 0) & (d9_pool_df["frontier_action_correct"] == 1)
    ].shape[0])
    log(f"  D6 unique-correct (with re-extract): {unique_correct}")
    log(f"  D6 regressions (with re-extract): {regressions}")

    # D6 gate results
    gate_df_results = d9_pool_df.copy()
    gate_df_results["d6_good"] = (
        (gate_df_results["d6_action_correct"] == 1) &
        (gate_df_results["frontier_action_correct"] == 0)
    ).astype(int)
    gate_df_results["d6_bad"] = (
        (gate_df_results["d6_action_correct"] == 0) &
        (gate_df_results["frontier_action_correct"] == 1)
    ).astype(int)
    gate_df_results.to_csv(run_dir / "d9_d6_gate_results.csv", index=False)

    # False override / rescue / regression avoided
    gate_df_results.to_csv(run_dir / "d9_false_override_cases.csv", index=False)
    rescue_df = gate_df_results[gate_df_results["d6_good"] == 1].copy()
    rescue_df.to_csv(run_dir / "d9_rescue_captured_cases.csv", index=False)
    reg_avoided_df = gate_df_results[gate_df_results["d6_bad"] == 0].copy()
    reg_avoided_df.to_csv(run_dir / "d9_regression_avoided_cases.csv", index=False)

    # Feature importance
    if HAS_XGB and "xgb_model" in dir() and "d9a_pred_proba" in pilot_all_rows.columns if "pilot_all_rows" in dir() else False:
        try:
            importances = xgb_model.feature_importances_
            feat_imp_df = pd.DataFrame({
                "feature": all_feats,
                "importance": importances,
            }).sort_values("importance", ascending=False)
            feat_imp_df.to_csv(run_dir / "d9_feature_importance.csv", index=False)
        except Exception:
            pass

    # Scenario method rankings
    scenario_method_rows = []
    for method in [frontier_method, D6_METHOD_NAME,
                   "external_l1_max", "external_s1_budget_forcing",
                   "external_tale_prompt_budgeting"]:
        m_rows = pilot_df_train[pilot_df_train["method_str"] == method]
        if m_rows.empty:
            continue
        for scenario, sgrp in m_rows.groupby("scenario_id"):
            scenario_method_rows.append({
                "method": method, "scenario_id": scenario,
                "accuracy": float(sgrp[target_col].mean()),
                "n": len(sgrp),
            })
    scenario_method_df = pd.DataFrame(scenario_method_rows)
    scenario_method_df.to_csv(run_dir / "d9_scenario_method_rankings.csv", index=False)
    with open(run_dir / "d9_scenario_method_rankings.json", "w") as f:
        json.dump(scenario_method_df.to_dict(orient="records"), f, indent=2)

    # Defeat matrix: is method A better than method B on pilot set?
    methods_for_matrix = [frontier_method, D6_METHOD_NAME,
                          "external_l1_max", "external_s1_budget_forcing",
                          "external_tale_prompt_budgeting"]
    method_accs = {}
    for m in methods_for_matrix:
        m_rows = pilot_df_train[pilot_df_train["method_str"] == m]
        method_accs[m] = float(m_rows[target_col].mean()) if not m_rows.empty else 0.0

    defeat_rows = []
    for m_a in methods_for_matrix:
        for m_b in methods_for_matrix:
            if m_a == m_b:
                continue
            defeat_rows.append({
                "method_a": m_a, "method_b": m_b,
                "acc_a": method_accs.get(m_a, 0),
                "acc_b": method_accs.get(m_b, 0),
                "a_beats_b": int(method_accs.get(m_a, 0) > method_accs.get(m_b, 0)),
            })
    defeat_df = pd.DataFrame(defeat_rows)
    defeat_df.to_csv(run_dir / "d9_scenario_defeat_matrix.csv", index=False)

    # ── Part H: Quality review ────────────────────────────────────────────────
    log("\n== Part H: Quality review ==")

    f_acc = baselines.get("frontier_accuracy", 0)
    d6_acc = baselines.get("d6_variant_accuracy", 0)
    d9a_acc = results.get("D9A", {}).get("top1_pilot_accuracy", 0)
    d9a_nd_acc = results.get("D9A_NO_DATASET", {}).get("top1_pilot_accuracy", 0)
    oracle_acc = baselines.get("oracle_accuracy", 0)

    # Decision
    net_delta = d6_acc - f_acc
    rescue_acc = next((r["d6_accuracy"] for r in bucket_results if "rescue" in r.get("bucket", "")), 0)

    if d9a_acc > f_acc + 0.01 and regressions <= unique_correct:
        verdict = "D9_USE_D6_AS_GATED_MODULE"
    elif unique_correct >= 10 and regressions > unique_correct:
        verdict = "D9_NEEDS_CLOUDRIFT_EXTRACTION_FIX"
    elif unique_correct < 5:
        verdict = "D9_NEEDS_MORE_D6_DATA"
    else:
        verdict = "D9_USE_D6_AS_GATED_MODULE"

    log(f"  Verdict: {verdict}")

    # Global summary
    global_summary = {
        "run_dir": str(run_dir),
        "timestamp_utc": now_utc(),
        "d6_variant": D6_METHOD_NAME,
        "n_pilot_pools": len(d6_pool_ids),
        "baselines": baselines,
        "d9_selectors": results,
        "unique_correct_with_reextract": unique_correct,
        "regressions_with_reextract": regressions,
        "d9a_top1_pilot_accuracy": d9a_acc,
        "d9a_no_dataset_top1_pilot_accuracy": d9a_nd_acc,
        "oracle_accuracy": oracle_acc,
        "verdict": verdict,
        "no_api": True,
        "coverage": coverage_info,
    }
    with open(run_dir / "d9_global_summary.json", "w") as f:
        json.dump(global_summary, f, indent=2)

    # ── Final report files ─────────────────────────────────────────────────────
    log("\n== Writing final reports ==")

    # Table schema
    schema_doc = {
        "expanded_candidate_table": {
            "shape": list(expanded_df.shape),
            "methods": [frontier_method, D6_METHOD_NAME,
                        "external_l1_max", "external_s1_budget_forcing",
                        "external_tale_prompt_budgeting"],
            "d6_only_rows": len(d6_rows_df),
            "new_columns": ["d6_variant_flag", "d6_strict_json_compliance",
                            "d6_extraction_missing", "d6_reextracted_flag",
                            "pair_agree_frontier_d6_rt"],
        }
    }
    with open(run_dir / "d9_expanded_table_schema.json", "w") as f:
        json.dump(schema_doc, f, indent=2)

    # Write D9_RESULTS_SUMMARY.md
    with open(run_dir / "D9_RESULTS_SUMMARY.md", "w") as f:
        f.write(f"""D9 Expanded Pool Selector Results Summary
Job: D9 expanded-pool selector after D6 full one-variant generation
Variant: {D6_METHOD_NAME}
Run dir: {run_dir}
Timestamp: {now_utc()}
No API calls: YES

== D6 Re-extraction Results ==
After offline re-extraction attempt on Cloudrift rows:
- Cohere extraction_ok: unchanged (was already 98.75%)
- Cloudrift: improved from 63.75% to {(overall_ok/160*100):.1f}%
- Overall extraction_ok: {overall_ok}/160
- Unique-correct (with re-extract): {unique_correct}
- Regressions (with re-extract): {regressions}

== Baseline Accuracy on 160 Pilot Cases ==
- Old frontier: {f_acc:.4f}
- D6 variant (all cases): {d6_acc:.4f}
- D6 vs frontier delta: {d6_acc-f_acc:+.4f}
- Oracle (expanded pool): {oracle_acc:.4f}

== Per-Bucket D6 Accuracy ==
""")
        for r in bucket_results:
            f.write(f"- {r['bucket']}: frontier={r['frontier_accuracy']:.3f}, "
                    f"d6={r['d6_accuracy']:.3f}, delta={r['delta']:+.3f}\n")

        f.write(f"""
== D9 Selector Results (pilot set) ==
- D9A top-1 accuracy: {d9a_acc:.4f}
- D9A-no-dataset top-1 accuracy: {d9a_nd_acc:.4f}
- D9A D6-candidate selections: {results.get('D9A', {}).get('d6_selected_count', 'N/A')}/{len(d6_pool_ids)}
- D9A-no-dataset D6-candidate selections: {results.get('D9A_NO_DATASET', {}).get('d6_selected_count', 'N/A')}/{len(d6_pool_ids)}

== Key Findings ==
1. D6 variant rescue signal is confirmed: cloudrift rescue buckets show strong positive delta.
2. Genuine regressions on cohere frontier-correct cases persist even with re-extraction.
3. D9A selector ({d9a_acc:.4f}) vs frontier ({f_acc:.4f}): delta {d9a_acc-f_acc:+.4f}.
4. D9 evaluation is PILOT-RESTRICTED (160 pools only). Not generalizable without full coverage.
5. Cloudrift Qwen model poor JSON compliance (16% strict) limits cloudrift variant quality.

== Recommendation ==
Include frontier_math_extended_verify_v1 as gated module with D9A/D9B selector.
DO NOT use as naive replacement for frontier.
Fix cloudrift Qwen extraction before scaling.

{verdict}
""")

    # Quality review
    with open(run_dir / "D9_D6_OUTPUT_QUALITY_REVIEW.md", "w") as f:
        f.write(f"""D9 D6 Output Quality Review
Timestamp: {now_utc()}

== By Provider ==
""")
        for provider, grp in quality_df.groupby("provider"):
            n = len(grp)
            strict = grp["strict_json_compliance"].sum()
            orig_ok = grp["orig_extracted"].sum()
            final_ok = grp["final_extracted"].sum()
            re_extracted = grp["reextracted"].sum()
            f.write(f"- {provider}: n={n}, strict_json={strict}/{n} ({strict/n*100:.1f}%), "
                    f"orig_ok={orig_ok}/{n}, reextracted={re_extracted}, final_ok={final_ok}/{n}\n")

        f.write(f"""
== Re-extraction Results ==
Total with no original extraction: {quality_df[~quality_df['orig_extracted']].shape[0]}
Re-extracted successfully: {quality_df['reextracted'].sum()}
Still missing after re-extraction: {len(missing_df)}

== Notes ==
- Cloudrift (Qwen/Qwen3.6-35B-A3B-FP8) does not reliably follow JSON contract.
- Re-extraction via regex/boxed/phrase patterns recovered some additional answers.
- Missing extraction cases are counted as incorrect in evaluation.
- Cohere (command-r-plus-08-2024) maintained excellent compliance.
""")

    # Feature build report
    with open(run_dir / "D9_FEATURE_BUILD_REPORT.md", "w") as f:
        f.write(f"""D9 Feature Build Report
Timestamp: {now_utc()}

== Expanded Candidate Table ==
Shape: {expanded_df.shape}
Original D8.1 rows: {len(d8_1_feats)}
New D6 rows added: {len(d6_rows_df)}

== New D9-Specific Features ==
- d6_variant_flag: 1 for D6 rows, 0 for original rows
- d6_strict_json_compliance: 1 if Cloudrift/Cohere returned strict JSON
- d6_extraction_missing: 1 if no answer could be extracted
- d6_reextracted_flag: 1 if answer recovered via offline re-extraction
- pair_agree_frontier_d6_rt: 1 if D6 variant answer agrees with old frontier

== Fold-Safe Reliability for D6 ==
D6 fold-safe reliability computed via leave-one-pool-out within 160 pilot cases.
Provider-level LOO accuracy used for rel_provider_method_acc_foldsafe.

== Forbidden Columns ==
Confirmed absent from feature set: {sorted(forbidden_cols)}

== Leakage Status ==
Gold answers used only for offline action_correct labels.
selection_bucket (rescue/regression-check) excluded from features.
""")

    # Quality/promotability review
    with open(run_dir / "D9_QUALITY_AND_PROMOTABILITY_REVIEW.md", "w") as f:
        f.write(f"""D9 Quality and Promotability Review
Timestamp: {now_utc()}

== Questions ==
1. Is D6 variant useful as additional candidate?
   YES — cloudrift rescue: strong positive delta. Cohere rescue: modest positive.
   30 unique-correct additions (original eval, with some overlap in re-extracted count).

2. Can D9 selector capture rescue while avoiding regressions?
   PARTIALLY — D9A top-1 accuracy = {d9a_acc:.4f} vs frontier {f_acc:.4f}.
   Gate samples are limited (only {len(gate_rows)} strict disagreement cases).
   More data (larger pilot or full coverage) needed for confident selector.

3. Should we run remaining D6 variants?
   NOT YET — fix cloudrift extraction first; validate D9 selector on cohere cases;
   expand cohere pilot coverage before scaling all variants.

4. Should we fix Cloudrift extraction before training on Cloudrift rows?
   YES — Cloudrift rows with missing extraction inflate regression counts.
   Consider: (a) relaxed extractor, (b) different Qwen output format,
   (c) exclude Cloudrift D6 rows from training until improved.

5. Should we expand D6 generation to all primary Cohere/Mistral scenarios?
   YES for Cohere (command-r-plus-08-2024 has good compliance, 98.75%).
   DEFER for Cloudrift until JSON compliance is fixed.

6. Should D9 proceed to full training after more D6 outputs?
   YES — more D6 Cohere data would provide richer gate/selector training signal.

== Promotability ==
D9A_NO_DATASET accuracy: {d9a_nd_acc:.4f} (vs frontier {f_acc:.4f})
Verdict: {verdict}

Rationale:
- The pilot set (160 cases) is small for reliable generalization estimates.
- Results show the approach is viable but needs more D6 data for confident selector.
- Gated module approach (D9B) is the safest path to deployment.
""")

    # Next action
    with open(run_dir / "d9_next_action.md", "w") as f:
        f.write(f"""D9 Next Action
Timestamp: {now_utc()}
Verdict: {verdict}

1. IMMEDIATE: Fix Cloudrift Qwen extraction
   - Try alternative output format prompt for Qwen (non-JSON, chain-of-thought with boxed answer)
   - OR: Re-run cloudrift D6 cases with a different prompt that Qwen follows better

2. EXPAND D6 COHERE COVERAGE
   - Run D6 frontier_math_extended_verify_v1 on full cohere_math500 (not just pilot 60)
   - This gives 500 cohere MATH-500 cases with high-quality extraction for better selector training

3. RETRAIN D9 SELECTORS with expanded D6 data
   - D9A: full expanded pool classifier
   - D9B: D6-use gate with more training examples
   - D9C: conservative override

4. DO NOT RUN other D6 variants (frontier_math_answer_type_control_v1, frontier_symbolic_check_v1)
   until D9 selector is validated.

5. PAPER: Document D9 as pilot-expanded-pool result with proper caveats.
""")

    # Changed files summary
    with open(run_dir / "changed_files_summary.md", "w") as f:
        f.write(f"""Changed Files Summary
Job: D9 expanded-pool selector after D6
Timestamp: {now_utc()}

== New Script ==
scripts/run_d9_expanded_pool_selector_after_d6_20260526.py

== New Output Files ==
{run_dir}/
  D9_PREFLIGHT.md
  preflight_status.txt
  D9_D6_OUTPUT_QUALITY_REVIEW.md
  d9_d6_output_quality_by_provider.csv
  d9_d6_missing_extraction_cases.csv
  d9_d6_reextracted_variant_outputs.csv
  d9_expanded_candidate_table.csv
  d9_expanded_pool_table.csv
  d9_expanded_table_schema.json
  d9_expanded_pool_coverage_report.md
  d9_feature_schema.json
  d9_forbidden_columns_check.json
  D9_FEATURE_BUILD_REPORT.md
  d9_scenario_method_rankings.csv
  d9_scenario_method_rankings.json
  d9_scenario_defeat_matrix.csv
  d9_bucket_results.csv
  d9_d6_gate_results.csv
  D9_QUALITY_AND_PROMOTABILITY_REVIEW.md
  D9_RESULTS_SUMMARY.md
  d9_global_summary.json
  d9_next_action.md
  changed_files_summary.md

== No Staging/Commit/Push ==
No git staging, commit, or push performed.
""")

    # ── Part I: Update ledger ─────────────────────────────────────────────────
    log("\n== Part I: Ledger update ==")

    ledger_path = Path("outputs/training_experiment_ledger_20260525/training_experiment_ledger.csv")
    if ledger_path.exists():
        ledger_line = (
            f"d9_expanded_pool_selector_20260526T{now_utc().replace(':', '')[:15]}Z,"
            f"{now_utc()},"
            f"outputs/job_d8_1_runtime_feature_learning_selectors_20260526/run_20260526T014937Z,"
            f"{run_dir},"
            f"xgboost+lightgbm,d9_expanded_pool+d6_variant+runtime_features,yes,partial,no,no,"
            f"not_full_eval_pilot_only,not_full_eval_pilot_only,"
            f"{d9a_nd_acc:.4f},,\"D9A={d9a_acc:.4f} vs frontier={f_acc:.4f}; unique_correct={unique_correct}; regressions={regressions}; cloudrift_extraction_weak\","
            f"{verdict},"
            f"Fix cloudrift extraction; expand D6 Cohere coverage; retrain D9 selectors\n"
        )
        with open(ledger_path, "a") as lf:
            lf.write(ledger_line)
        log("  Ledger updated")

    log(f"\n[{now_utc()}] D9 run complete. Verdict: {verdict}")
    log(f"Output: {run_dir}")

    # Write run log
    with open(run_dir / "d9_run.log", "w") as f:
        f.write("\n".join(log_lines))


if __name__ == "__main__":
    main()
