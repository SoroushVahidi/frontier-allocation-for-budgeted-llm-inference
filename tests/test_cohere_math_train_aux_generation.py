"""
Tests for cohere_math_train_aux_generation (2026-05-25)

Tests cover:
- exact-case row schema validation
- overlap checker (official overlap = 0)
- call plan has all 4 required methods
- no duplicate (example_id, method) pairs
- official overlap exclusion enforced
- call cap enforced (≤ 2000)
"""

import json
import pandas as pd
import pytest
from pathlib import Path

OUT = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/cohere_math_train_aux_generation_20260524")
OFFICIAL_CASE_TABLE = Path("/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/router_v2_manuscript_reproduction_20260524/reproduced_official4_case_table.csv")

REQUIRED_METHODS = {
    "direct_reserve_semantic_frontier_v2",
    "external_l1_max",
    "external_s1_budget_forcing",
    "external_tale_prompt_budgeting",
}
CALL_CAP = 2000


# ============================================================
# 1. Exact-case row schema
# ============================================================

def test_exact_cases_file_exists():
    """Exact-cases JSONL must exist."""
    assert (OUT / "cohere_math_train_aux_exact_cases.jsonl").exists()


def test_exact_cases_required_fields():
    """Every exact-case row must have example_id, question, and gold answer."""
    path = OUT / "cohere_math_train_aux_exact_cases.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    assert len(rows) > 0, "Exact-cases file is empty"
    for i, row in enumerate(rows):
        assert "example_id" in row and row["example_id"], f"Row {i}: missing example_id"
        assert "question" in row and row["question"], f"Row {i}: missing question"
        has_gold = any(k in row for k in ("gold_answer_canonical", "gold_answer", "gold"))
        assert has_gold, f"Row {i}: missing gold answer field"


def test_exact_cases_unique_ids():
    """All example_ids in exact-cases JSONL must be unique."""
    path = OUT / "cohere_math_train_aux_exact_cases.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    ids = [r["example_id"] for r in rows]
    assert len(ids) == len(set(ids)), f"Duplicate example_ids found: {len(ids) - len(set(ids))} duplicates"


def test_exact_cases_count():
    """Exact-cases file must have exactly 200 rows (non-official MATH-500 examples)."""
    path = OUT / "cohere_math_train_aux_exact_cases.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    assert len(rows) == 200, f"Expected 200 cases, got {len(rows)}"


def test_exact_cases_dataset_field():
    """All rows must specify the correct dataset."""
    path = OUT / "cohere_math_train_aux_exact_cases.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    for row in rows:
        assert row.get("dataset") == "HuggingFaceH4/MATH-500", (
            f"Unexpected dataset: {row.get('dataset')} for {row['example_id']}"
        )


# ============================================================
# 2. Overlap checker — official overlap must be zero
# ============================================================

def test_official_overlap_zero():
    """No exact-case example_id must appear in the official test case table."""
    path = OUT / "cohere_math_train_aux_exact_cases.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    aux_ids = {r["example_id"] for r in rows}

    official_df = pd.read_csv(OFFICIAL_CASE_TABLE)
    official_math_ids = set(
        official_df[official_df["dataset"] == "HuggingFaceH4/MATH-500"]["example_id"].unique()
    )
    overlap = aux_ids & official_math_ids
    assert len(overlap) == 0, (
        f"Official overlap detected! {len(overlap)} IDs in common: {sorted(overlap)[:5]}"
    )


def test_overlap_report_exists():
    """Overlap report CSV must exist."""
    assert (OUT / "cohere_math_train_aux_overlap_report.csv").exists()


def test_overlap_report_official_column_all_false():
    """Overlap report must show in_official_seed71=False for all rows."""
    df = pd.read_csv(OUT / "cohere_math_train_aux_overlap_report.csv")
    assert "in_official_seed71" in df.columns
    assert df["in_official_seed71"].sum() == 0, (
        f"{df['in_official_seed71'].sum()} rows have in_official_seed71=True (should be 0)"
    )


# ============================================================
# 3. Call plan has all 4 methods
# ============================================================

def test_call_plan_has_all_4_methods():
    """Call plan CSV must include all 4 required methods."""
    df = pd.read_csv(OUT / "cohere_math_train_aux_call_plan.csv")
    methods_in_plan = set(df["method"].unique())
    missing = REQUIRED_METHODS - methods_in_plan
    assert len(missing) == 0, f"Missing methods in call plan: {missing}"


def test_call_plan_method_counts_equal():
    """Each method must appear the same number of times in the call plan."""
    df = pd.read_csv(OUT / "cohere_math_train_aux_call_plan.csv")
    counts = df["method"].value_counts()
    assert counts.nunique() == 1, (
        f"Unequal method counts: {counts.to_dict()}"
    )


def test_call_plan_method_count_equals_cases():
    """Each method must appear exactly once per example (200 cases → 200 rows per method)."""
    df = pd.read_csv(OUT / "cohere_math_train_aux_call_plan.csv")
    cases = pd.read_csv(OUT / "cohere_math_train_aux_case_inventory.csv")
    n_cases = len(cases)
    for method in REQUIRED_METHODS:
        count = (df["method"] == method).sum()
        assert count == n_cases, (
            f"Method '{method}' has {count} rows, expected {n_cases}"
        )


# ============================================================
# 4. No duplicate (example_id, method) pairs
# ============================================================

def test_no_duplicate_example_method_pairs():
    """No duplicate (example_id, method) pairs in call plan."""
    df = pd.read_csv(OUT / "cohere_math_train_aux_call_plan.csv")
    pairs = df[["example_id", "method"]]
    n_pairs = len(pairs)
    n_unique = pairs.drop_duplicates().shape[0]
    assert n_pairs == n_unique, (
        f"Found {n_pairs - n_unique} duplicate (example_id, method) pairs"
    )


# ============================================================
# 5. Official overlap exclusion enforced via allowed-ids JSONL
# ============================================================

def test_allowed_ids_no_official_overlap():
    """Allowed-IDs JSONL must contain no official test example IDs."""
    path = OUT / "cohere_math_train_aux_allowed_ids.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    allowed_ids = {r["example_id"] for r in rows}

    official_df = pd.read_csv(OFFICIAL_CASE_TABLE)
    official_math_ids = set(
        official_df[official_df["dataset"] == "HuggingFaceH4/MATH-500"]["example_id"].unique()
    )
    overlap = allowed_ids & official_math_ids
    assert len(overlap) == 0, (
        f"Allowed IDs contain {len(overlap)} official test IDs!"
    )


def test_allowed_ids_all_4_methods():
    """Allowed-IDs JSONL must have all 4 methods."""
    path = OUT / "cohere_math_train_aux_allowed_ids.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    methods_found = {r.get("method") or r.get("our_method_name") for r in rows}
    missing = REQUIRED_METHODS - methods_found
    assert len(missing) == 0, f"Missing methods in allowed IDs: {missing}"


# ============================================================
# 6. Call cap enforced
# ============================================================

def test_call_cap_enforced():
    """Total planned calls must not exceed the 2000-call cap."""
    path = OUT / "cohere_math_train_aux_allowed_ids.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    n_calls = len(rows)
    assert n_calls <= CALL_CAP, (
        f"Planned calls ({n_calls}) exceeds cap ({CALL_CAP})"
    )


def test_call_plan_summary_within_cap():
    """Call plan summary JSON must confirm within_cap=True."""
    summary = json.loads((OUT / "cohere_math_train_aux_call_plan_summary.json").read_text())
    assert summary.get("within_cap") is True, (
        f"Call plan summary reports within_cap={summary.get('within_cap')}"
    )
    assert summary.get("n_planned_calls", 99999) <= CALL_CAP, (
        f"n_planned_calls={summary.get('n_planned_calls')} exceeds cap"
    )


# ============================================================
# 7. Preflight file checks
# ============================================================

def test_preflight_json_exists():
    """Preflight JSON must exist."""
    assert (OUT / "cohere_math_train_aux_preflight.json").exists()


def test_preflight_passes():
    """Preflight JSON must show PASS decision."""
    pf = json.loads((OUT / "cohere_math_train_aux_preflight.json").read_text())
    assert pf.get("dry_run_passed") is True, "Preflight dry_run_passed is not True"
    assert pf.get("within_cap") is True, "Preflight within_cap is not True"
    assert pf.get("official_overlap_count", 1) == 0, "Preflight reports official overlap"
    assert "PASS" in str(pf.get("preflight_decision", "")), (
        f"Preflight decision is not PASS: {pf.get('preflight_decision')}"
    )


# ============================================================
# 8. Output artifact inventory
# ============================================================

@pytest.mark.parametrize("fname", [
    "cohere_math_train_aux_exact_cases.jsonl",
    "cohere_math_train_aux_case_inventory.csv",
    "cohere_math_train_aux_overlap_report.csv",
    "cohere_math_train_aux_allowed_ids.jsonl",
    "cohere_math_train_aux_call_plan.csv",
    "cohere_math_train_aux_call_plan_summary.json",
    "cohere_math_train_aux_preflight.json",
    "dataset_runner_capability_audit.json",
])
def test_required_artifact_exists(fname):
    """Required artifact must exist in output directory."""
    assert (OUT / fname).exists(), f"Missing artifact: {fname}"
