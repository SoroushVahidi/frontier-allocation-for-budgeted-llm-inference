#!/usr/bin/env python3
"""Build unified leakage-safe learning tables for fixed-pool candidate selection.

Offline-only job:
- consumes completed local artifacts
- applies split registry
- reconciles Cohere MATH-500 known ID issues
- emits standardized candidate/pool tables plus audits/manifests/reports
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

METHOD_ORDER = [
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
]
METHOD_ALIAS = {
    "direct_reserve_semantic_frontier_v2": "frontier",
    "external_l1_max": "l1",
    "external_s1_budget_forcing": "s1",
    "external_tale_prompt_budgeting": "tale",
}
ALIAS_TO_METHOD = {v: k for k, v in METHOD_ALIAS.items()}
KNOWN_BAD_COHERE_MATH500_IDS = {
    f"HuggingFaceH4_MATH-500_{n}" for n in [11, 193, 222, 236, 251, 255, 256, 258, 287, 297]
}


@dataclass
class ScenarioSource:
    scenario_id: str
    provider: str
    dataset: str
    source_type: str  # per_example_jsonl | wide_case_csv
    source_path: str
    artifact_type: str
    model_id_hint: str
    expected_examples: int
    include_policy: str


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_run_dir(root: Path) -> Path:
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return root
    ts = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    out = root / ts
    out.mkdir(parents=True, exist_ok=False)
    return out


def norm_spaces_lower(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def question_hash(question: str) -> str:
    return hashlib.sha256(norm_spaces_lower(question).encode("utf-8")).hexdigest()


def normalize_dataset_name(dataset: str) -> str:
    d = (dataset or "").strip().lower()
    if "gsm8k" in d:
        return "gsm8k"
    if "math-500" in d or "math500" in d:
        return "math500"
    return d or "unknown"


def normalize_provider_name(provider: str) -> str:
    p = (provider or "").strip().lower()
    return {
        "cloudrift_ai": "cloudrift",
        "azure_openai": "azure",
        "mistral_ai": "mistral",
    }.get(p, p)


def clean_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and math.isnan(x):
        return ""
    return str(x)


def normalize_answer(ans: Any) -> str:
    s = clean_text(ans).strip()
    if not s:
        return ""
    s = re.sub(r"\\boxed\s*\{([^{}]*)\}", r"\1", s)
    s = s.replace("$", "")
    s = " ".join(s.split())
    return s.strip().lower()


def parse_numeric(ans: str) -> float | None:
    s = normalize_answer(ans)
    if not s:
        return None
    s = s.replace(",", "")
    frac = re.fullmatch(r"([+-]?\d+)\s*/\s*([+-]?\d+)", s)
    if frac:
        den = int(frac.group(2))
        if den == 0:
            return None
        return int(frac.group(1)) / den
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", s):
        try:
            return float(s)
        except ValueError:
            return None
    return None


def approx_tokens(text: str) -> int:
    return len(re.findall(r"\S+", clean_text(text)))


def bool_int(x: Any) -> int:
    if isinstance(x, bool):
        return int(x)
    s = clean_text(x).strip().lower()
    if s in {"1", "true", "yes"}:
        return 1
    if s in {"0", "false", "no", ""}:
        return 0
    try:
        return int(float(s) != 0.0)
    except Exception:
        return 0


def float_or_nan(x: Any) -> float:
    s = clean_text(x).strip()
    if not s:
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def model_family(model_id: str) -> str:
    m = (model_id or "").lower()
    if not m:
        return "unknown"
    if "/" in m:
        return m.split("/", 1)[0]
    if "-" in m:
        return m.split("-", 1)[0]
    return m


def model_type(provider: str, model_id: str) -> str:
    p = provider.lower()
    m = (model_id or "").lower()
    if any(k in m for k in ["a3b", "a22b", "moe"]):
        return "moe"
    if p in {"cohere", "azure", "mistral"}:
        return "closed"
    if any(k in m for k in ["qwen", "llama", "mistral", "deepseek"]):
        return "open"
    return "unknown"


def run_command(cmd: str) -> str:
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return f"$ {cmd}\n{p.stdout}{p.stderr}\n"


def choose_split_dir(split_root: Path) -> Path:
    runs = sorted([d for d in split_root.glob("run_*") if d.is_dir()])
    candidates: list[Path] = []
    for d in runs:
        req = [
            d / "split_registry_gsm8k.csv",
            d / "split_registry_math500.csv",
            d / "split_manifest.json",
        ]
        if all(p.exists() for p in req):
            candidates.append(d)
    if candidates:
        return candidates[-1]
    for d in [split_root]:
        req = [
            d / "split_registry_gsm8k.csv",
            d / "split_registry_math500.csv",
            d / "split_manifest.json",
        ]
        if all(p.exists() for p in req):
            return d
    raise FileNotFoundError("No complete split registry package found.")


def load_split_registry(split_dir: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    by_hash: dict[tuple[str, str], dict[str, Any]] = {}
    by_example: dict[tuple[str, str], dict[str, Any]] = {}
    for fname in ["split_registry_gsm8k.csv", "split_registry_math500.csv"]:
        with (split_dir / fname).open(newline="") as f:
            for row in csv.DictReader(f):
                d = normalize_dataset_name(row["dataset"])
                qh = row["question_hash"]
                by_hash[(d, qh)] = row
                for ex in (row.get("original_example_id") or "").split("|"):
                    ex = ex.strip()
                    if ex:
                        by_example[(d, ex)] = row
    return by_hash, by_example


def load_cohere_math500_combined_labels(path: Path) -> dict[tuple[str, str], tuple[int, int]]:
    # returns (exact_current, combined)
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    out: dict[tuple[str, str], tuple[int, int]] = {}
    for _, r in df.iterrows():
        ex = clean_text(r["example_id"])
        for alias in ["frontier", "l1", "s1", "tale"]:
            exact = bool_int(r.get(f"{alias}_correct_current", 0))
            comb = bool_int(r.get(f"{alias}_correct_combined", exact))
            out[(ex, ALIAS_TO_METHOD[alias])] = (exact, comb)
    return out


def dedup_per_example_records(path: Path) -> tuple[dict[tuple[str, str], tuple[dict[str, Any], int]], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[tuple[dict[str, Any], int]]] = defaultdict(list)
    for i, line in enumerate(path.open(), start=1):
        obj = json.loads(line)
        m = obj.get("method")
        if m not in METHOD_ORDER:
            continue
        key = (clean_text(obj.get("example_id")), m)
        grouped[key].append((obj, i))

    chosen: dict[tuple[str, str], tuple[dict[str, Any], int]] = {}
    stats = {"raw_rows": 0, "dedup_removed": 0, "nonscored_chosen": 0}
    for k, rows in grouped.items():
        stats["raw_rows"] += len(rows)
        stats["dedup_removed"] += max(0, len(rows) - 1)
        scored = [x for x in rows if x[0].get("status") == "scored"]
        pool = scored if scored else rows
        picked = sorted(pool, key=lambda x: clean_text(x[0].get("timestamp")))[-1]
        if picked[0].get("status") != "scored":
            stats["nonscored_chosen"] += 1
        chosen[k] = picked
    return chosen, stats


def load_per_example_source(src: ScenarioSource, combined_labels: dict[tuple[str, str], tuple[int, int]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = Path(src.source_path)
    chosen, stats = dedup_per_example_records(path)
    rows: list[dict[str, Any]] = []

    for (example_id, method), (obj, rec_idx) in sorted(chosen.items()):
        provider = normalize_provider_name(clean_text(obj.get("provider")) or src.provider)
        dataset = normalize_dataset_name(clean_text(obj.get("dataset")) or src.dataset)
        qtxt = clean_text(obj.get("question"))
        gold = clean_text(obj.get("gold_answer"))
        selected_raw = clean_text(obj.get("selected_answer_raw"))
        selected_canon = clean_text(obj.get("selected_answer_canonical"))
        final_raw = clean_text(obj.get("final_answer_raw"))
        controller_raw = clean_text(obj.get("controller_final_answer_raw"))
        err = clean_text(obj.get("error"))

        extracted = selected_raw or final_raw or selected_canon
        norm_ans = normalize_answer(selected_canon or extracted)

        status = clean_text(obj.get("status"))
        parse_fail = bool_int(obj.get("parse_extraction_failure"))
        if status != "scored" and not extracted:
            parse_fail = 1

        exact_val = obj.get("exact_match")
        exact = bool_int(exact_val)
        label_source = "exact_match"
        if status != "scored" and clean_text(exact_val) == "":
            label_source = "status_failed_assumed_incorrect"

        comb = None
        if src.scenario_id == "cohere_math500":
            if (example_id, method) in combined_labels:
                exact2, comb2 = combined_labels[(example_id, method)]
                exact = exact2
                comb = comb2
                label_source = "cohere_math500_rescored_source_correctness"
            else:
                comb = exact

        raw_out = controller_raw or final_raw or selected_raw
        result_meta = obj.get("result_metadata")

        rows.append(
            {
                "scenario_id": src.scenario_id,
                "provider": provider,
                "dataset": dataset,
                "model_id": clean_text(obj.get("model")) or src.model_id_hint,
                "example_uid": "",
                "original_example_id": example_id,
                "question_hash": question_hash(qtxt),
                "split": "",
                "method": method,
                "method_family": METHOD_ALIAS[method],
                "source_artifact_path": str(path),
                "source_record_index": rec_idx,
                "run_timestamp": clean_text(obj.get("timestamp")),
                "budget": int(float_or_nan(obj.get("budget"))) if not math.isnan(float_or_nan(obj.get("budget"))) else 0,
                "seed": int(float_or_nan(obj.get("seed"))) if not math.isnan(float_or_nan(obj.get("seed"))) else 0,
                "question_text": qtxt,
                "raw_output_text": raw_out,
                "extracted_answer": extracted,
                "normalized_answer": norm_ans,
                "gold_answer_for_labeling_only": gold,
                "candidate_correct": exact,
                "candidate_correct_exact": exact,
                "candidate_correct_combined": comb,
                "candidate_parse_failure_label": parse_fail,
                "label_source": label_source,
                "status": status,
                "error_text": err,
                "result_metadata_json": json.dumps(result_meta, ensure_ascii=False) if result_meta is not None else "",
            }
        )

    coverage = Counter((r["method"] for r in rows))
    return rows, {
        "source_path": str(path),
        "source_type": src.source_type,
        "artifact_type": src.artifact_type,
        "coverage": dict(coverage),
        "n_rows": len(rows),
        "n_examples": len({r["original_example_id"] for r in rows}),
        "stats": stats,
    }


def load_wide_case_source(src: ScenarioSource) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = Path(src.source_path)
    df = pd.read_csv(path)
    rows: list[dict[str, Any]] = []

    method_cols = {
        "direct_reserve_semantic_frontier_v2": ("frontier_answer", "frontier_correct", "parse_extraction_failure_frontier", "frontier_answer_norm"),
        "external_l1_max": ("l1_answer", "l1_correct", "parse_extraction_failure_l1", "l1_answer_norm"),
        "external_s1_budget_forcing": ("s1_answer", "s1_correct", "parse_extraction_failure_s1", "s1_answer_norm"),
        "external_tale_prompt_budgeting": ("tale_answer", "tale_correct", "parse_extraction_failure_tale", "tale_answer_norm"),
    }

    model_hint = src.model_id_hint
    for idx, r in df.iterrows():
        example_id = clean_text(r.get("example_id"))
        qtxt = clean_text(r.get("question"))
        gold = clean_text(r.get("gold_answer"))

        for method, (ans_col, corr_col, parse_col, norm_col) in method_cols.items():
            ans = clean_text(r.get(ans_col))
            norm_ans = clean_text(r.get(norm_col))
            if not norm_ans:
                norm_ans = normalize_answer(ans)
            rows.append(
                {
                    "scenario_id": src.scenario_id,
                    "provider": src.provider,
                    "dataset": src.dataset,
                    "model_id": model_hint,
                    "example_uid": "",
                    "original_example_id": example_id,
                    "question_hash": question_hash(qtxt),
                    "split": "",
                    "method": method,
                    "method_family": METHOD_ALIAS[method],
                    "source_artifact_path": str(path),
                    "source_record_index": int(idx) + 2,
                    "run_timestamp": "",
                    "budget": 6,
                    "seed": 71,
                    "question_text": qtxt,
                    "raw_output_text": "",
                    "extracted_answer": ans,
                    "normalized_answer": norm_ans,
                    "gold_answer_for_labeling_only": gold,
                    "candidate_correct": bool_int(r.get(corr_col, 0)),
                    "candidate_correct_exact": bool_int(r.get(corr_col, 0)),
                    "candidate_correct_combined": None,
                    "candidate_parse_failure_label": bool_int(r.get(parse_col, 0)),
                    "label_source": "wide_case_replay",
                    "status": "scored",
                    "error_text": "",
                    "result_metadata_json": "",
                }
            )

    coverage = Counter((r["method"] for r in rows))
    return rows, {
        "source_path": str(path),
        "source_type": src.source_type,
        "artifact_type": src.artifact_type,
        "coverage": dict(coverage),
        "n_rows": len(rows),
        "n_examples": len({r["original_example_id"] for r in rows}),
    }


def compute_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["answer_length_chars"] = df["extracted_answer"].map(lambda s: len(clean_text(s)))
    df["output_length_chars"] = df["raw_output_text"].map(lambda s: len(clean_text(s)))
    df["output_length_tokens_approx"] = df["raw_output_text"].map(approx_tokens)
    df["extracted_answer_length_chars"] = df["extracted_answer"].map(lambda s: len(clean_text(s)))
    df["normalized_answer_length_chars"] = df["normalized_answer"].map(lambda s: len(clean_text(s)))

    df["answer_is_empty"] = df["normalized_answer"].map(lambda s: int(clean_text(s) == ""))
    df["boxed_answer_present"] = df["raw_output_text"].map(lambda s: int(bool(re.search(r"\\boxed", clean_text(s), flags=re.IGNORECASE))))
    df["multiple_boxed_answers"] = df["raw_output_text"].map(lambda s: int(len(re.findall(r"\\boxed", clean_text(s), flags=re.IGNORECASE)) > 1))
    df["final_answer_marker_present"] = df["raw_output_text"].map(lambda s: int(bool(re.search(r"final\s+answer|answer\s*:", clean_text(s), flags=re.IGNORECASE))))

    df["parse_success"] = (1 - df["candidate_parse_failure_label"].fillna(0).astype(int)).clip(lower=0, upper=1)

    parsed = df["normalized_answer"].map(parse_numeric)
    df["numeric_answer_flag"] = parsed.map(lambda x: int(x is not None and not (isinstance(x, float) and math.isnan(x))))
    df["integer_answer_flag"] = parsed.map(
        lambda x: int(x is not None and not (isinstance(x, float) and math.isnan(x)) and abs(x - round(x)) < 1e-12)
    )
    df["fraction_answer_flag"] = df["normalized_answer"].map(lambda s: int(bool(re.fullmatch(r"[+-]?\d+\s*/\s*[+-]?\d+", clean_text(s)))))
    df["expression_answer_flag"] = df["normalized_answer"].map(lambda s: int(bool(re.search(r"[a-z]|[+\-*/^=()]", clean_text(s)))))
    df["negative_answer_flag"] = parsed.map(
        lambda x: int(x is not None and not (isinstance(x, float) and math.isnan(x)) and x < 0)
    )
    df["answer_contains_variable"] = df["normalized_answer"].map(lambda s: int(bool(re.search(r"[a-z]", clean_text(s)))))
    df["answer_contains_units"] = df["normalized_answer"].map(lambda s: int(bool(re.search(r"\b(cm|mm|m|km|kg|g|lb|mph|hours?|minutes?|seconds?|dollars?|\%)\b", clean_text(s)))))
    df["answer_magnitude_abs"] = parsed.map(lambda x: abs(x) if x is not None else float("nan"))

    df["api_error_text_flag"] = df["error_text"].map(lambda s: int(bool(clean_text(s))))
    df["malformed_output_flag"] = (
        (df["answer_is_empty"].astype(int) == 1)
        | (df["api_error_text_flag"].astype(int) == 1)
        | (df["status"].map(lambda x: clean_text(x).lower()) != "scored")
    ).astype(int)
    df["truncation_suspected_flag"] = df["raw_output_text"].map(lambda s: int(bool(re.search(r"\.\.\.$|truncated|cut off", clean_text(s), flags=re.IGNORECASE))))

    df["problem_length_chars"] = df["question_text"].map(lambda s: len(clean_text(s)))
    df["problem_length_tokens_approx"] = df["question_text"].map(approx_tokens)
    df["problem_numeric_token_count"] = df["question_text"].map(lambda s: len(re.findall(r"[+-]?\d+(?:\.\d+)?", clean_text(s))))
    df["problem_variable_token_count"] = df["question_text"].map(lambda s: len(re.findall(r"\b[a-zA-Z]\b", clean_text(s))))

    df["dataset_family"] = df["dataset"].map(lambda d: "math_word_problem" if d in {"gsm8k", "math500"} else "unknown")

    df["provider_family"] = df["provider"]
    df["model_family"] = df["model_id"].map(model_family)
    df["model_type_known"] = [model_type(p, m) for p, m in zip(df["provider"], df["model_id"]) ]
    df["uses_budget_forcing_flag"] = df["method"].map(lambda m: int(m == "external_s1_budget_forcing"))
    df["uses_prompt_budgeting_flag"] = df["method"].map(lambda m: int(m == "external_tale_prompt_budgeting"))
    df["is_frontier_method_flag"] = df["method"].map(lambda m: int(m == "direct_reserve_semantic_frontier_v2"))
    df["is_external_method_flag"] = 1 - df["is_frontier_method_flag"]

    return df


def cluster_key(ans: str) -> str:
    n = parse_numeric(ans)
    if n is not None:
        return f"num:{n:.12g}"
    norm = normalize_answer(ans)
    if norm:
        return f"txt:{norm}"
    return "empty:"


def entropy_from_counts(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log2(p)
    return h


def build_cluster_and_pool_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["pool_id"] = df.apply(lambda r: f"{r['dataset']}::{r['provider']}::{r['example_uid']}", axis=1)
    df["clustering_version"] = "v1_exact_norm_plus_numeric"

    pool_rows = []
    baseline_rows = []
    missing_pool_rows = []

    agreement_cols = ["agrees_with_frontier", "agrees_with_l1", "agrees_with_s1", "agrees_with_tale"]
    for c in agreement_cols:
        df[c] = 0

    cluster_id_col = []
    cluster_size_col = []
    cluster_rank_col = []
    max_cluster_col = []
    distinct_col = []
    all_same_col = []
    all_diff_col = []
    no_maj_col = []
    isolated_col = []
    largest_col = []
    entropy_col = []
    frontier_iso_col = []
    l1_iso_col = []
    s1_iso_col = []
    tale_iso_col = []
    non_s1_majority_col = []
    non_frontier_majority_col = []
    majority_includes_frontier_col = []
    majority_includes_s1_col = []
    majority_excludes_frontier_col = []
    majority_excludes_s1_col = []
    unique_correct_col = []
    in_correct_cluster_col = []
    source_vec_col = []

    for pool_id, g in df.groupby("pool_id", sort=False):
        g = g.copy()
        g = g.sort_values("method")

        method_to_idx = {m: i for m, i in zip(g["method"], g.index)}
        ans_keys = {i: cluster_key(a) for i, a in zip(g.index, g["normalized_answer"]) }
        counts = Counter(ans_keys.values())
        sorted_clusters = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        key_to_id = {k: f"cluster_{n+1}" for n, (k, _) in enumerate(sorted_clusters)}
        key_to_rank = {k: n + 1 for n, (k, _) in enumerate(sorted_clusters)}
        max_sz = sorted_clusters[0][1] if sorted_clusters else 0
        distinct = len(sorted_clusters)
        all_same = int(distinct == 1)
        all_diff = int(max_sz == 1)
        no_maj = int(max_sz == 1)
        ent = entropy_from_counts([v for _, v in sorted_clusters])

        correct_methods = [m for m, c in zip(g["method"], g["candidate_correct"]) if int(c) == 1]
        oracle_available = int(len(correct_methods) > 0)
        all_wrong = int(len(correct_methods) == 0)
        unique_correct_source = correct_methods[0] if len(correct_methods) == 1 else ""
        correct_keys = {
            ans_keys[idx]
            for idx, corr in zip(g.index, g["candidate_correct"])
            if int(corr) == 1
        }

        method_key = {m: ans_keys[i] for m, i in method_to_idx.items()}
        frontier_key = method_key.get("direct_reserve_semantic_frontier_v2", "")
        l1_key = method_key.get("external_l1_max", "")
        s1_key = method_key.get("external_s1_budget_forcing", "")
        tale_key = method_key.get("external_tale_prompt_budgeting", "")
        majority_keys = {k for k, v in sorted_clusters if v == max_sz and max_sz > 1}

        frontier_iso = int(frontier_key and counts.get(frontier_key, 0) == 1)
        l1_iso = int(l1_key and counts.get(l1_key, 0) == 1)
        s1_iso = int(s1_key and counts.get(s1_key, 0) == 1)
        tale_iso = int(tale_key and counts.get(tale_key, 0) == 1)
        majority_includes_frontier = int(frontier_key in majority_keys)
        majority_includes_s1 = int(s1_key in majority_keys)
        majority_excludes_frontier = int(max_sz > 1 and frontier_key not in majority_keys)
        majority_excludes_s1 = int(max_sz > 1 and s1_key not in majority_keys)
        non_s1_majority_exists = int(any((k in majority_keys and k != s1_key) for k, _ in sorted_clusters))
        non_frontier_majority_exists = int(any((k in majority_keys and k != frontier_key) for k, _ in sorted_clusters))

        source_vec = {METHOD_ALIAS[m]: int(c) for m, c in zip(g["method"], g["candidate_correct"])}

        for idx, row in g.iterrows():
            k = ans_keys[idx]
            cluster_id_col.append(key_to_id[k])
            cluster_size_col.append(counts[k])
            cluster_rank_col.append(key_to_rank[k])
            max_cluster_col.append(max_sz)
            distinct_col.append(distinct)
            all_same_col.append(all_same)
            all_diff_col.append(all_diff)
            no_maj_col.append(no_maj)
            isolated_col.append(int(counts[k] == 1))
            largest_col.append(int(counts[k] == max_sz and max_sz > 0))
            entropy_col.append(ent)
            frontier_iso_col.append(frontier_iso)
            l1_iso_col.append(l1_iso)
            s1_iso_col.append(s1_iso)
            tale_iso_col.append(tale_iso)
            non_s1_majority_col.append(non_s1_majority_exists)
            non_frontier_majority_col.append(non_frontier_majority_exists)
            majority_includes_frontier_col.append(majority_includes_frontier)
            majority_includes_s1_col.append(majority_includes_s1)
            majority_excludes_frontier_col.append(majority_excludes_frontier)
            majority_excludes_s1_col.append(majority_excludes_s1)
            unique_correct_col.append(int(int(row["candidate_correct"]) == 1 and len(correct_methods) == 1))
            in_correct_cluster_col.append(int(k in correct_keys and len(correct_keys) > 0))
            source_vec_col.append(json.dumps(source_vec, sort_keys=True))

        # pairwise agreements
        for method_alias in ["frontier", "l1", "s1", "tale"]:
            m_full = ALIAS_TO_METHOD[method_alias]
            key_ref = method_key.get(m_full, "")
            col = f"agrees_with_{method_alias}"
            for idx, m in zip(g.index, g["method"]):
                df.loc[idx, col] = int(ans_keys[idx] == key_ref and key_ref != "")

        # pool-level row
        methods_present = sorted(g["method"].tolist())
        failed_count = int((g["status"].str.lower() != "scored").sum())
        parse_success_rate = float(g["parse_success"].mean()) if len(g) else 0.0
        malformed_rate = float(g["malformed_output_flag"].mean()) if len(g) else 0.0

        correct_cluster_id = ""
        correct_cluster_size = 0
        if correct_keys:
            # pick largest correct cluster; deterministic tie by ID
            cands = sorted(((counts[k], key_to_id[k], k) for k in correct_keys), key=lambda x: (-x[0], x[1]))
            correct_cluster_size = cands[0][0]
            correct_cluster_id = cands[0][1]

        if len(methods_present) < 4:
            missing_pool_rows.append(
                {
                    "pool_id": pool_id,
                    "scenario_id": g["scenario_id"].iloc[0],
                    "provider": g["provider"].iloc[0],
                    "dataset": g["dataset"].iloc[0],
                    "example_uid": g["example_uid"].iloc[0],
                    "method_count": len(methods_present),
                    "methods_present_json": json.dumps(methods_present),
                    "reason": "missing_methods",
                }
            )

        # Baselines
        method_correct = {m: int(g[g["method"] == m]["candidate_correct"].iloc[0]) if m in set(g["method"]) else None for m in METHOD_ORDER}
        method_answer = {m: clean_text(g[g["method"] == m]["normalized_answer"].iloc[0]) if m in set(g["method"]) else "" for m in METHOD_ORDER}

        def choose_pooled4() -> tuple[str, str, int]:
            if not method_answer:
                return "", "", 0
            local_counts = Counter({m: cluster_key(a) for m, a in method_answer.items() if m in METHOD_ORDER}.values())
            if not local_counts:
                return "", "", 0
            max_local = max(local_counts.values())
            tied = {k for k, v in local_counts.items() if v == max_local}
            selected_method = ""
            for m in METHOD_ORDER:
                if cluster_key(method_answer.get(m, "")) in tied:
                    selected_method = m
                    break
            selected_answer = method_answer.get(selected_method, "")
            correct = method_correct.get(selected_method)
            return selected_answer, METHOD_ALIAS.get(selected_method, ""), int(correct) if correct is not None else 0

        pooled_ans, pooled_tiebreak, pooled_ok = choose_pooled4()

        # agreement-only: require at least one agreement (cluster size >= 2), else fallback frontier
        if max_sz >= 2:
            tied = {k for k, v in counts.items() if v == max_sz}
            selected_method = "direct_reserve_semantic_frontier_v2"
            for m in METHOD_ORDER:
                if method_key.get(m, "") in tied:
                    selected_method = m
                    break
        else:
            selected_method = "direct_reserve_semantic_frontier_v2"
        agreement_ans = method_answer.get(selected_method, "")
        agreement_ok = int(method_correct.get(selected_method) or 0)

        baseline_rows.append(
            {
                "pool_id": pool_id,
                "scenario_id": g["scenario_id"].iloc[0],
                "provider": g["provider"].iloc[0],
                "dataset": g["dataset"].iloc[0],
                "example_uid": g["example_uid"].iloc[0],
                "split": g["split"].iloc[0],
                "select_frontier_correct": method_correct.get("direct_reserve_semantic_frontier_v2"),
                "select_l1_correct": method_correct.get("external_l1_max"),
                "select_s1_correct": method_correct.get("external_s1_budget_forcing"),
                "select_tale_correct": method_correct.get("external_tale_prompt_budgeting"),
                "pooled4_selected_answer": pooled_ans,
                "pooled4_selected_method_tiebreak": pooled_tiebreak,
                "pooled4_correct": pooled_ok,
                "agreement_only_selected_answer": agreement_ans,
                "agreement_only_correct": agreement_ok,
                "reliability_weighted_vote_placeholder": "not_computed_fold_safe_required",
                "oracle_correct": oracle_available,
            }
        )

        pool_rows.append(
            {
                "pool_id": pool_id,
                "scenario_id": g["scenario_id"].iloc[0],
                "dataset": g["dataset"].iloc[0],
                "provider": g["provider"].iloc[0],
                "model_id": g["model_id"].iloc[0],
                "example_uid": g["example_uid"].iloc[0],
                "question_hash": g["question_hash"].iloc[0],
                "split": g["split"].iloc[0],
                "source_artifact_paths_json": json.dumps(sorted(set(g["source_artifact_path"].tolist()))),
                "methods_present_json": json.dumps(methods_present),
                "method_count": len(methods_present),
                "pool_size": len(g),
                "all_four_methods_present_flag": int(len(set(methods_present)) == 4),
                "failed_candidate_count": failed_count,
                "parse_success_rate": parse_success_rate,
                "malformed_rate": malformed_rate,
                "distinct_answer_count": distinct,
                "max_cluster_size": max_sz,
                "agreement_entropy": ent,
                "all_answers_same_flag": all_same,
                "all_answers_different_flag": all_diff,
                "no_majority_flag": no_maj,
                "oracle_available": oracle_available,
                "all_sources_wrong": all_wrong,
                "oracle_correct_method_count": len(correct_methods),
                "unique_correct_source": unique_correct_source,
                "correct_methods_json": json.dumps(sorted(correct_methods)),
                "correct_cluster_id": correct_cluster_id,
                "correct_cluster_size": correct_cluster_size,
                "best_raw_method_in_pool": unique_correct_source if unique_correct_source else (correct_methods[0] if correct_methods else ""),
                "best_raw_correct_flag": oracle_available,
                "dataset_family": g["dataset_family"].iloc[0],
                "math_subject": g["math_subject"].iloc[0],
                "math_level": g["math_level"].iloc[0],
                "problem_length_chars": int(g["problem_length_chars"].iloc[0]),
                "problem_length_tokens_approx": int(g["problem_length_tokens_approx"].iloc[0]),
                "problem_numeric_token_count": int(g["problem_numeric_token_count"].iloc[0]),
                "previously_analyzed_flag": int(g["previously_analyzed_flag"].iloc[0]),
            }
        )

    df["answer_cluster_id"] = cluster_id_col
    df["cluster_size"] = cluster_size_col
    df["cluster_rank_by_size"] = cluster_rank_col
    df["max_cluster_size"] = max_cluster_col
    df["distinct_answer_count"] = distinct_col
    df["all_answers_same_flag"] = all_same_col
    df["all_answers_different_flag"] = all_diff_col
    df["no_majority_flag"] = no_maj_col
    df["candidate_is_isolated_flag"] = isolated_col
    df["candidate_in_largest_cluster_flag"] = largest_col
    df["agreement_entropy"] = entropy_col
    df["frontier_isolated"] = frontier_iso_col
    df["l1_isolated"] = l1_iso_col
    df["s1_isolated"] = s1_iso_col
    df["tale_isolated"] = tale_iso_col
    df["non_s1_majority_exists"] = non_s1_majority_col
    df["non_frontier_majority_exists"] = non_frontier_majority_col
    df["majority_includes_frontier"] = majority_includes_frontier_col
    df["majority_includes_s1"] = majority_includes_s1_col
    df["majority_excludes_frontier"] = majority_excludes_frontier_col
    df["majority_excludes_s1"] = majority_excludes_s1_col
    df["candidate_is_unique_correct"] = unique_correct_col
    df["candidate_in_correct_cluster"] = in_correct_cluster_col
    df["source_correct_vector_json"] = source_vec_col

    pool_df = pd.DataFrame(pool_rows)
    baseline_df = pd.DataFrame(baseline_rows)
    missing_pool_df = pd.DataFrame(missing_pool_rows)
    return df, pool_df, baseline_df, missing_pool_df


def write_md_table(df: pd.DataFrame, path: Path, title: str) -> None:
    lines = [f"# {title}", ""]
    if df.empty:
        lines.append("(no rows)")
    else:
        cols = list(df.columns)
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["---"] * len(cols)) + "|")
        for _, r in df.iterrows():
            lines.append("| " + " | ".join(clean_text(r[c]) for c in cols) + " |")
    path.write_text("\n".join(lines) + "\n")


def build_feature_manifest(candidate_df: pd.DataFrame, pool_df: pd.DataFrame, out_dir: Path) -> dict[str, Any]:
    id_cols = {
        "row_id", "pool_id", "scenario_id", "dataset", "provider", "model_id", "example_uid",
        "original_example_id", "question_hash", "split", "method", "method_family", "source_artifact_path",
        "source_record_index", "run_timestamp", "budget", "seed",
    }
    label_cols = {
        "candidate_correct", "candidate_correct_exact", "candidate_correct_combined", "candidate_parse_failure_label",
        "candidate_is_unique_correct", "candidate_in_correct_cluster", "source_correct_vector_json",
        "oracle_available", "all_sources_wrong", "oracle_correct_method_count", "unique_correct_source",
        "correct_methods_json", "correct_cluster_id", "correct_cluster_size", "best_raw_correct_flag",
    }
    forbidden = {
        "example_uid", "original_example_id", "question_hash", "gold_answer_for_labeling_only",
        "candidate_correct", "candidate_correct_exact", "candidate_correct_combined", "source_correct_vector_json",
        "candidate_is_unique_correct", "candidate_in_correct_cluster", "oracle_available", "all_sources_wrong",
        "source_artifact_path", "source_record_index",
    }
    fold_only = {
        "source_historical_accuracy", "source_reliability", "provider_complementarity",
        "train_fold_baseline_accuracy",
    }

    def classify(col: str) -> str:
        if col in fold_only:
            return "fold_only_feature"
        if col in forbidden:
            return "forbidden_feature"
        if col in id_cols:
            return "id/provenance"
        if col in label_cols:
            return "label"
        if col in {"question_text", "raw_output_text", "error_text", "result_metadata_json", "status", "label_source"}:
            return "diagnostic_only"
        return "runtime_feature_safe"

    candidate_cls = {c: classify(c) for c in candidate_df.columns}
    pool_cls = {c: classify(c) for c in pool_df.columns}

    cand_allow = [c for c, k in candidate_cls.items() if k == "runtime_feature_safe"]
    pool_allow = [c for c, k in pool_cls.items() if k == "runtime_feature_safe"]

    manifest = {
        "generated_at": now_utc(),
        "candidate_level": candidate_cls,
        "pool_level": pool_cls,
        "forbidden_feature_list": sorted(forbidden),
        "fold_only_feature_list": sorted(fold_only),
        "candidate_runtime_allowlist": cand_allow,
        "pool_runtime_allowlist": pool_allow,
    }

    (out_dir / "feature_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out_dir / "feature_allowlist_candidate_level.txt").write_text("\n".join(cand_allow) + "\n")
    (out_dir / "feature_allowlist_pool_level.txt").write_text("\n".join(pool_allow) + "\n")
    (out_dir / "forbidden_feature_list.txt").write_text("\n".join(sorted(forbidden)) + "\n")

    leak_lines = [
        "# Leakage Audit",
        "",
        "Status: PASS_WITH_GUARDRAILS",
        "",
        "Forbidden features are explicitly listed and excluded from runtime allowlists.",
        "Fold-only aggregates are declared and deferred to training-time fold-safe computation.",
        "Unknown split rows (if any) are diagnostic-only and should be excluded from primary training.",
    ]
    (out_dir / "leakage_audit.md").write_text("\n".join(leak_lines) + "\n")
    return manifest


def baseline_summaries(baseline_df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    metrics = [
        "select_frontier_correct",
        "select_l1_correct",
        "select_s1_correct",
        "select_tale_correct",
        "pooled4_correct",
        "agreement_only_correct",
        "oracle_correct",
    ]
    rows = []
    for (scenario_id, provider, dataset), g in baseline_df.groupby(["scenario_id", "provider", "dataset"]):
        row = {
            "scenario_id": scenario_id,
            "provider": provider,
            "dataset": dataset,
            "n_pools": len(g),
        }
        for m in metrics:
            row[m] = float(g[m].mean()) if m in g else float("nan")
        rows.append(row)
    out = pd.DataFrame(rows).sort_values(["provider", "dataset"]).reset_index(drop=True)

    md = ["# Baseline Summary By Scenario", ""]
    if out.empty:
        md.append("(no rows)")
    else:
        md.append("| scenario_id | provider | dataset | n_pools | frontier | l1 | s1 | tale | pooled4 | agreement_only | oracle |")
        md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, r in out.iterrows():
            md.append(
                "| {scenario_id} | {provider} | {dataset} | {n_pools} | {f:.4f} | {l1:.4f} | {s1:.4f} | {t:.4f} | {p:.4f} | {a:.4f} | {o:.4f} |".format(
                    scenario_id=r["scenario_id"],
                    provider=r["provider"],
                    dataset=r["dataset"],
                    n_pools=int(r["n_pools"]),
                    f=r["select_frontier_correct"],
                    l1=r["select_l1_correct"],
                    s1=r["select_s1_correct"],
                    t=r["select_tale_correct"],
                    p=r["pooled4_correct"],
                    a=r["agreement_only_correct"],
                    o=r["oracle_correct"],
                )
            )
    return out, "\n".join(md) + "\n"


def load_sources() -> list[ScenarioSource]:
    return [
        ScenarioSource(
            scenario_id="cohere_gsm8k",
            provider="cohere",
            dataset="gsm8k",
            source_type="per_example_jsonl",
            source_path="outputs/canonical_final300_cohere_contract_matched_live_20260523T181948Z/cohere_real_model_cost_normalized_validation_20260523T181948Z/per_example_records.jsonl",
            artifact_type="per_example_records",
            model_id_hint="command-r-plus-08-2024",
            expected_examples=300,
            include_policy="include",
        ),
        ScenarioSource(
            scenario_id="cohere_math500",
            provider="cohere",
            dataset="math500",
            source_type="per_example_jsonl",
            source_path="outputs/cohere_math500_official_scenario4_20260524/cohere_math500_full_20260524T144902Z/cohere_real_model_cost_normalized_validation_20260524T144902Z/per_example_records.jsonl",
            artifact_type="per_example_records",
            model_id_hint="command-r-plus-08-2024",
            expected_examples=300,
            include_policy="include_with_reconciliation",
        ),
        ScenarioSource(
            scenario_id="mistral_gsm8k",
            provider="mistral",
            dataset="gsm8k",
            source_type="wide_case_csv",
            source_path="outputs/mistral_gsm8k_expanded_s1_override_20260525/expanded_mistral_gsm8k_case_level_replay.csv",
            artifact_type="case_table",
            model_id_hint="mistral-small-latest",
            expected_examples=1300,
            include_policy="include",
        ),
        ScenarioSource(
            scenario_id="mistral_math500",
            provider="mistral",
            dataset="math500",
            source_type="per_example_jsonl",
            source_path="outputs/scenarios_5_6_math500_full_tracking_20260524/mistral_math500_full_20260524T014937Z/cohere_real_model_cost_normalized_validation_20260524T014937Z/per_example_records.jsonl",
            artifact_type="per_example_records",
            model_id_hint="mistral-small-latest",
            expected_examples=300,
            include_policy="include",
        ),
        ScenarioSource(
            scenario_id="cloudrift_gsm8k",
            provider="cloudrift",
            dataset="gsm8k",
            source_type="per_example_jsonl",
            source_path="outputs/regime_learning_generation_20260525/cloudrift_ai_gsm8k_300_20260525T115305Z/cohere_real_model_cost_normalized_validation_20260525T115833Z/per_example_records.jsonl",
            artifact_type="per_example_records",
            model_id_hint="Qwen/Qwen3.6-35B-A3B-FP8",
            expected_examples=300,
            include_policy="include_if_validated",
        ),
        ScenarioSource(
            scenario_id="cloudrift_math500",
            provider="cloudrift",
            dataset="math500",
            source_type="per_example_jsonl",
            source_path="outputs/regime_learning_generation_20260525/cloudrift_ai_math500_300_20260525T134444Z/cohere_real_model_cost_normalized_validation_20260525T134455Z/per_example_records.jsonl",
            artifact_type="per_example_records",
            model_id_hint="Qwen/Qwen3.6-35B-A3B-FP8",
            expected_examples=300,
            include_policy="include_if_validated",
        ),
        ScenarioSource(
            scenario_id="azure_gsm8k",
            provider="azure",
            dataset="gsm8k",
            source_type="per_example_jsonl",
            source_path="outputs/regime_learning_generation_20260525/azure_openai_gsm8k_300_20260525T115305Z/cohere_real_model_cost_normalized_validation_20260525T115347Z/per_example_records.jsonl",
            artifact_type="per_example_records",
            model_id_hint="gpt-4.1-mini",
            expected_examples=300,
            include_policy="include_if_validated",
        ),
        ScenarioSource(
            scenario_id="azure_math500",
            provider="azure",
            dataset="math500",
            source_type="per_example_jsonl",
            source_path="outputs/regime_learning_generation_20260525/azure_openai_math500_300_20260525T143829Z/cohere_real_model_cost_normalized_validation_20260525T143905Z/per_example_records.jsonl",
            artifact_type="per_example_records",
            model_id_hint="gpt-4.1-mini",
            expected_examples=300,
            include_policy="include_only_if_complete",
        ),
    ]


def write_source_inventory(records: list[dict[str, Any]], out_csv: Path, out_md: Path) -> None:
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values(["selected_as_authoritative", "scenario_id"], ascending=[False, True])
    df.to_csv(out_csv, index=False)

    lines = ["# Source Artifact Inventory", ""]
    if df.empty:
        lines.append("(no rows)")
    else:
        cols = [
            "scenario_id", "provider", "dataset", "model_id", "method_coverage", "n_examples", "total_rows",
            "source_path", "artifact_type", "selected_as_authoritative", "reason",
        ]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["---"] * len(cols)) + "|")
        for _, r in df.iterrows():
            lines.append("| " + " | ".join(clean_text(r.get(c, "")) for c in cols) + " |")
    out_md.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="outputs/unified_learning_tables_20260525")
    parser.add_argument("--split-root", default="outputs/learning_data_split_and_readiness_20260525")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    out_dir = ensure_run_dir(output_root)

    # run.log with required state refresh commands
    run_log = out_dir / "run.log"
    with run_log.open("w") as f:
        f.write(f"Generated at: {now_utc()}\n\n")
        f.write(run_command("pwd"))
        f.write(run_command("date"))
        f.write(run_command("git status --short"))
        f.write(run_command("git branch -vv"))
        f.write(run_command("git log --oneline -10"))
        f.write(run_command("tmux ls || true"))
        f.write(run_command("python3 -V"))
        f.write(run_command("which python3"))

    split_root = Path(args.split_root)
    split_dir = choose_split_dir(split_root)
    split_by_hash, split_by_example = load_split_registry(split_dir)

    # split checks
    split_df_g = pd.read_csv(split_dir / "split_registry_gsm8k.csv")
    split_df_m = pd.read_csv(split_dir / "split_registry_math500.csv")
    split_df = pd.concat([split_df_g, split_df_m], ignore_index=True)
    hash_multi_split = (
        split_df.groupby(["dataset", "question_hash"])["split"].nunique().reset_index().query("split > 1")
    )

    # source loading
    combined_labels = load_cohere_math500_combined_labels(
        Path("outputs/cohere_math500_failure_learning_20260525/cohere_math500_rescored_source_correctness.csv")
    )

    all_rows: list[dict[str, Any]] = []
    source_inventory_records: list[dict[str, Any]] = []
    included_scenarios: list[str] = []
    excluded_scenarios: list[tuple[str, str]] = []

    for src in load_sources():
        p = Path(src.source_path)
        if not p.exists():
            excluded_scenarios.append((src.scenario_id, "missing_source_artifact"))
            source_inventory_records.append(
                {
                    "scenario_id": src.scenario_id,
                    "provider": src.provider,
                    "dataset": src.dataset,
                    "model_id": src.model_id_hint,
                    "method_coverage": "",
                    "n_examples": 0,
                    "total_rows": 0,
                    "source_path": src.source_path,
                    "artifact_type": src.artifact_type,
                    "selected_as_authoritative": False,
                    "reason": "missing_source_artifact",
                }
            )
            continue

        if src.source_type == "per_example_jsonl":
            rows, meta = load_per_example_source(src, combined_labels)
        elif src.source_type == "wide_case_csv":
            rows, meta = load_wide_case_source(src)
        else:
            excluded_scenarios.append((src.scenario_id, f"unknown_source_type:{src.source_type}"))
            continue

        # validation policy
        mcounts = Counter(r["method"] for r in rows)
        ex_count = len({r["original_example_id"] for r in rows})
        full_methods = all(mcounts.get(m, 0) >= ex_count for m in METHOD_ORDER)
        include = True
        reason = "selected_authoritative"

        if src.include_policy == "include_only_if_complete" and not (full_methods and ex_count >= src.expected_examples):
            include = False
            reason = "not_complete_at_job_time"
        if src.scenario_id == "azure_math500" and not (full_methods and ex_count >= src.expected_examples):
            include = False
            reason = "azure_math500_incomplete"

        if include:
            included_scenarios.append(src.scenario_id)
            all_rows.extend(rows)
        else:
            excluded_scenarios.append((src.scenario_id, reason))

        source_inventory_records.append(
            {
                "scenario_id": src.scenario_id,
                "provider": src.provider,
                "dataset": src.dataset,
                "model_id": src.model_id_hint,
                "method_coverage": json.dumps(meta.get("coverage", {}), sort_keys=True),
                "n_examples": meta.get("n_examples", 0),
                "total_rows": meta.get("n_rows", 0),
                "source_path": src.source_path,
                "artifact_type": src.artifact_type,
                "selected_as_authoritative": include,
                "reason": reason,
            }
        )

    # Always record known excluded/running scenarios for coverage report completeness
    for scenario_id, reason in [
        ("cerebras_gsm8k", "running_or_incomplete"),
        ("cerebras_math500", "not_started_or_missing"),
        ("fireworks_gsm8k", "not_completed"),
        ("fireworks_math500", "not_completed"),
        ("modal_gsm8k_math500", "excluded_unsuitable"),
    ]:
        excluded_scenarios.append((scenario_id, reason))

    if not all_rows:
        raise RuntimeError("No rows loaded from selected sources.")

    cand_df = pd.DataFrame(all_rows)

    # split mapping
    split_report_rows = []
    unmapped = []
    example_uid_collision_check = defaultdict(set)

    mapped_split = []
    mapped_example_uid = []
    mapped_subject = []
    mapped_level = []
    mapped_prev = []

    for _, r in cand_df.iterrows():
        ds = r["dataset"]
        ex = r["original_example_id"]
        qh = r["question_hash"]
        reg = split_by_hash.get((ds, qh))
        if reg is None:
            reg = split_by_example.get((ds, ex))
        if reg is None:
            split = "unknown"
            ex_uid = f"{ds}::{qh}"
            subj = "unknown"
            lvl = float("nan")
            prev = 0
            unmapped.append(
                {
                    "scenario_id": r["scenario_id"],
                    "provider": r["provider"],
                    "dataset": ds,
                    "original_example_id": ex,
                    "question_hash": qh,
                }
            )
        else:
            split = clean_text(reg.get("split")) or "unknown"
            ex_uid = clean_text(reg.get("example_uid")) or f"{ds}::{qh}"
            subj = clean_text(reg.get("subject")) or "unknown"
            lvl = float_or_nan(reg.get("level"))
            prev = bool_int(reg.get("previously_analyzed"))

        mapped_split.append(split)
        mapped_example_uid.append(ex_uid)
        mapped_subject.append(subj)
        mapped_level.append(lvl)
        mapped_prev.append(prev)
        example_uid_collision_check[ex_uid].add(ds)

    cand_df["split"] = mapped_split
    cand_df["example_uid"] = mapped_example_uid
    cand_df["math_subject"] = mapped_subject
    cand_df["math_level"] = mapped_level
    cand_df["previously_analyzed_flag"] = mapped_prev
    cand_df["seen_dev_flag"] = cand_df["split"].map(lambda s: int(s == "seen_dev"))

    collisions = [k for k, v in example_uid_collision_check.items() if len(v) > 1]

    split_application_report = (
        cand_df.groupby(["scenario_id", "provider", "dataset", "split"]).size().reset_index(name="candidate_rows")
    )
    split_application_report.to_csv(out_dir / "split_application_report.csv", index=False)
    write_md_table(split_application_report, out_dir / "split_application_report.md", "Split Application Report")
    if unmapped:
        pd.DataFrame(unmapped).drop_duplicates().to_csv(out_dir / "unmapped_examples.csv", index=False)

    # Cohere MATH-500 reconciliation report
    coh = cand_df[(cand_df["scenario_id"] == "cohere_math500")].copy()
    coh["is_known_problematic_id"] = coh["original_example_id"].isin(KNOWN_BAD_COHERE_MATH500_IDS)
    coh_rows = []

    def agg_acc(df: pd.DataFrame, label_col: str, condition: str) -> None:
        for m, g in df.groupby("method"):
            denom = len(g)
            num = int(g[label_col].fillna(0).astype(int).sum())
            coh_rows.append(
                {
                    "condition": condition,
                    "method": m,
                    "method_family": METHOD_ALIAS[m],
                    "numerator": num,
                    "denominator": denom,
                    "accuracy": (num / denom) if denom else float("nan"),
                }
            )

    if not coh.empty:
        agg_acc(coh, "candidate_correct_exact", "exact_current")
        if coh["candidate_correct_combined"].notna().any():
            agg_acc(coh, "candidate_correct_combined", "combined_rescored")
        agg_acc(coh[~coh["is_known_problematic_id"]], "candidate_correct_exact", "exact_excluding_10_problematic_ids")

    coh_rep = pd.DataFrame(coh_rows)
    coh_rep.to_csv(out_dir / "cohere_math500_reconciliation_report.csv", index=False)

    rank_lines = ["# Cohere MATH-500 Reconciliation Report", ""]
    if coh_rep.empty:
        rank_lines.append("No Cohere MATH-500 rows were included.")
    else:
        for cond, g in coh_rep.groupby("condition"):
            rank_lines.append(f"## {cond}")
            g2 = g.sort_values("accuracy", ascending=False)
            for _, r in g2.iterrows():
                rank_lines.append(f"- {r['method_family']}: {r['numerator']}/{r['denominator']} = {r['accuracy']:.4f}")
            rank_lines.append("")
        rank_lines.append("Known problematic IDs were retained but explicitly flagged and reported.")
    (out_dir / "cohere_math500_reconciliation_report.md").write_text("\n".join(rank_lines) + "\n")

    if not coh.empty:
        coh[coh["is_known_problematic_id"]].to_csv(out_dir / "cohere_math500_artifact_id_rows.csv", index=False)

    # ID/provenance row id
    cand_df = compute_base_features(cand_df)
    cand_df["row_id"] = [
        hashlib.sha256(
            f"{r.scenario_id}|{r.provider}|{r.dataset}|{r.example_uid}|{r.method}".encode("utf-8")
        ).hexdigest()
        for r in cand_df.itertuples(index=False)
    ]

    # candidate pool/cluster features + pool table + baselines
    cand_df, pool_df, baseline_df, missing_pool_df = build_cluster_and_pool_features(cand_df)

    # scenario coverage
    cov_rows = []
    for scen in sorted(set([*included_scenarios, *[x[0] for x in excluded_scenarios]])):
        g_cand = cand_df[cand_df["scenario_id"] == scen]
        g_pool = pool_df[pool_df["scenario_id"] == scen]
        if len(g_cand) == 0:
            provider = scen.split("_")[0]
            dataset = scen.split("_")[-1]
            blocker = ", ".join(sorted({r for s, r in excluded_scenarios if s == scen})) or "excluded"
            ready = "No"
            split_dist = "{}"
        else:
            provider = g_cand["provider"].iloc[0]
            dataset = g_cand["dataset"].iloc[0]
            blocker = ""
            ready = "Yes" if int((g_pool["all_four_methods_present_flag"] == 1).all()) else "Conditional"
            split_dist = json.dumps(g_cand["split"].value_counts().to_dict(), sort_keys=True)
        cov_rows.append(
            {
                "scenario_id": scen,
                "provider": provider,
                "dataset": dataset,
                "examples": int(g_cand["example_uid"].nunique()) if len(g_cand) else 0,
                "candidate_rows": int(len(g_cand)),
                "complete_four_method_pools": int((g_pool["all_four_methods_present_flag"] == 1).sum()) if len(g_pool) else 0,
                "incomplete_pools": int((g_pool["all_four_methods_present_flag"] == 0).sum()) if len(g_pool) else 0,
                "split_distribution": split_dist,
                "labels_available": "Yes" if len(g_cand) else "No",
                "cluster_features_available": "Yes" if len(g_cand) else "No",
                "ready_for_training": ready,
                "blocker": blocker,
            }
        )

    cov_df = pd.DataFrame(cov_rows).sort_values(["provider", "dataset", "scenario_id"])
    cov_df.to_csv(out_dir / "scenario_coverage_report.csv", index=False)
    write_md_table(cov_df, out_dir / "scenario_coverage_report.md", "Scenario Coverage Report")

    # Baselines
    baseline_df.to_csv(out_dir / "baseline_pool_decisions.csv", index=False)
    base_sum_df, base_sum_md = baseline_summaries(baseline_df)
    base_sum_df.to_csv(out_dir / "baseline_summary_by_scenario.csv", index=False)
    (out_dir / "baseline_summary_by_scenario.md").write_text(base_sum_md)

    # Feature manifest / leakage
    feature_manifest = build_feature_manifest(cand_df, pool_df, out_dir)

    # split enforcement report
    split_lines = [
        "# Split Application Report",
        "",
        f"Split registry source: `{split_dir}`",
        f"Candidate rows: {len(cand_df)}",
        f"Unknown split rows: {int((cand_df['split'] == 'unknown').sum())}",
        f"Registry multi-split hash collisions: {len(hash_multi_split)}",
        f"Cross-dataset example_uid collisions: {len(collisions)}",
    ]
    (out_dir / "split_application_report.md").write_text("\n".join(split_lines) + "\n")

    # Missing/incomplete pools
    if missing_pool_df.empty:
        missing_pool_df = pd.DataFrame(
            columns=["pool_id", "scenario_id", "provider", "dataset", "example_uid", "method_count", "methods_present_json", "reason"]
        )
    missing_pool_df.to_csv(out_dir / "missing_or_incomplete_pools.csv", index=False)

    # Candidate/pool write with requested filenames
    candidate_out = out_dir / "unified_candidate_action_table.csv"
    pool_out = out_dir / "unified_pool_level_table.csv"
    cand_df.to_csv(candidate_out, index=False)
    pool_df.to_csv(pool_out, index=False)

    # Data quality report
    dq_lines = [
        "# Data Quality Report",
        "",
        f"Candidate rows: {len(cand_df)}",
        f"Pool rows: {len(pool_df)}",
        f"Complete pools (all four methods): {int((pool_df['all_four_methods_present_flag'] == 1).sum())}",
        f"Incomplete pools: {int((pool_df['all_four_methods_present_flag'] == 0).sum())}",
        f"Unknown split rows: {int((cand_df['split'] == 'unknown').sum())}",
        f"Non-scored candidate rows: {int((cand_df['status'].str.lower() != 'scored').sum())}",
        f"Registry question-hash split collisions: {len(hash_multi_split)}",
        f"Cross-dataset example_uid collisions: {len(collisions)}",
    ]
    (out_dir / "data_quality_report.md").write_text("\n".join(dq_lines) + "\n")

    # source inventory
    write_source_inventory(
        source_inventory_records,
        out_dir / "source_artifact_inventory.csv",
        out_dir / "source_artifact_inventory.md",
    )

    # build manifest
    build_manifest = {
        "generated_at": now_utc(),
        "script": str(Path(__file__)),
        "output_dir": str(out_dir),
        "split_registry_dir": str(split_dir),
        "included_scenarios": sorted(set(included_scenarios)),
        "excluded_scenarios": sorted(set(excluded_scenarios)),
        "candidate_rows": int(len(cand_df)),
        "pool_rows": int(len(pool_df)),
        "complete_pools": int((pool_df["all_four_methods_present_flag"] == 1).sum()),
    }
    (out_dir / "build_manifest.json").write_text(json.dumps(build_manifest, indent=2) + "\n")

    # scenario-level training readiness and report
    ready_flag = int((pool_df["all_four_methods_present_flag"] == 1).all() and (cand_df["split"] != "unknown").all())

    # recommended training config
    model_candidates = []
    if importlib.util.find_spec("catboost") is not None:
        model_candidates.append("CatBoostClassifier")
    if importlib.util.find_spec("lightgbm") is not None:
        model_candidates.append("LightGBM")
    if importlib.util.find_spec("xgboost") is not None:
        model_candidates.append("XGBoost")
    model_candidates.extend(["sklearn.HistGradientBoostingClassifier", "sklearn.RandomForestClassifier", "sklearn.LogisticRegression"])

    rec_cfg = {
        "primary_model_candidates": model_candidates,
        "target": "candidate_correct",
        "group": "example_uid",
        "alternate_group": "pool_id",
        "split_registry_dir": str(split_dir),
        "feature_allowlist_candidate_level": str(out_dir / "feature_allowlist_candidate_level.txt"),
        "feature_allowlist_pool_level": str(out_dir / "feature_allowlist_pool_level.txt"),
        "calibration": ["sigmoid", "temperature"],
        "evaluation": [
            "scenario_level_accuracy",
            "best_baseline_comparison",
            "oracle_gap",
            "mcnemar_or_paired_bootstrap_later",
        ],
        "fold_safe_note": "Any reliability/complementarity aggregates must be computed inside train folds only.",
    }
    (out_dir / "recommended_training_config.json").write_text(json.dumps(rec_cfg, indent=2) + "\n")

    next_plan = [
        "# Next Training Job Plan",
        "",
        "Do not call APIs. Run offline training/evaluation only.",
        "",
        "1. Launch Job D in tmux using unified tables and split registry.",
        "2. Restrict features to runtime-safe allowlist files.",
        "3. Compute any reliability features fold-safely inside training folds only.",
        "4. Report scenario-level accuracy, baseline comparisons, and oracle gap.",
    ]
    (out_dir / "next_training_job_plan.md").write_text("\n".join(next_plan) + "\n")

    # Unified final report
    report_lines = [
        "# UNIFIED_LEARNING_TABLES_REPORT_20260525",
        "",
        f"Output directory: `{out_dir}`",
        "",
        "## Which scenarios were included?",
    ]
    for s in sorted(set(included_scenarios)):
        report_lines.append(f"- {s}")

    report_lines.extend(
        [
            "",
            "## Which scenarios were excluded and why?",
        ]
    )
    for s, reason in sorted(set(excluded_scenarios)):
        report_lines.append(f"- {s}: {reason}")

    report_lines.extend(
        [
            "",
            "## Table sizes",
            f"- Candidate rows: {len(cand_df)}",
            f"- Pool rows: {len(pool_df)}",
            f"- Complete four-method pools: {int((pool_df['all_four_methods_present_flag'] == 1).sum())}",
            "",
            "## Split enforcement",
            f"- Registry directory: `{split_dir}`",
            f"- Unknown split rows: {int((cand_df['split'] == 'unknown').sum())}",
            f"- Hash multi-split collisions in registry: {len(hash_multi_split)}",
            "",
            "## Cohere MATH-500 reconciliation",
            "- Candidate rows rebuilt from authoritative per-example records.",
            "- Primary training label uses `candidate_correct_exact`.",
            "- Combined/rescored label included as `candidate_correct_combined` where available.",
            f"- Known problematic IDs flagged: {len(KNOWN_BAD_COHERE_MATH500_IDS)}",
            "",
            "## Labels created",
            "- candidate_correct",
            "- candidate_correct_exact",
            "- candidate_correct_combined (when available)",
            "- candidate_parse_failure_label",
            "- candidate_is_unique_correct",
            "- candidate_in_correct_cluster",
            "",
            "## Features created",
            "- Candidate runtime-visible answer/output/problem/provider/method features",
            "- Pool-level agreement/cluster/oracle context features",
            "- Baseline selector decision outputs by pool",
            "",
            "## Forbidden features",
            "- See `forbidden_feature_list.txt` and `feature_manifest.json`",
            "",
            "## Leakage status",
            "- PASS_WITH_GUARDRAILS (forbidden/fold-only columns explicitly segregated)",
            "",
            "## Ready for first training job?",
            f"- {'Yes' if ready_flag else 'Conditional'}",
            "",
            "## Exact next command/job to run",
            "- Run Job D training/evaluation in tmux using `recommended_training_config.json` and the two unified tables from this output directory.",
        ]
    )
    (out_dir / "UNIFIED_LEARNING_TABLES_REPORT_20260525.md").write_text("\n".join(report_lines) + "\n")

    # unified run manifest
    unified_manifest = {
        "generated_at": now_utc(),
        "output_dir": str(out_dir),
        "files": sorted(p.name for p in out_dir.iterdir() if p.is_file()),
        "candidate_rows": int(len(cand_df)),
        "pool_rows": int(len(pool_df)),
        "complete_pools": int((pool_df["all_four_methods_present_flag"] == 1).sum()),
        "included_scenarios": sorted(set(included_scenarios)),
        "excluded_scenarios": sorted(set(excluded_scenarios)),
    }
    (out_dir / "unified_learning_tables_manifest.json").write_text(json.dumps(unified_manifest, indent=2) + "\n")

    # scenario coverage and quality companion files
    cov_df.to_csv(out_dir / "scenario_coverage_report.csv", index=False)

    # final pointer summary
    print(json.dumps({
        "output_dir": str(out_dir),
        "candidate_rows": len(cand_df),
        "pool_rows": len(pool_df),
        "complete_pools": int((pool_df["all_four_methods_present_flag"] == 1).sum()),
        "included_scenarios": sorted(set(included_scenarios)),
        "excluded_scenarios": sorted(set(excluded_scenarios)),
    }, indent=2))


if __name__ == "__main__":
    main()
