"""No-API tests for direct-reserve candidate scorer pipeline."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCR = REPO / "scripts"


def _write_synth(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "planned_cases.csv").write_text(
        "case_idx,example_id,dataset,question,gold_answer_raw,gold_answer,seed,budget,stratum,source_path,excluded_overlap\n"
        "1,ex1,openai/gsm8k,q1,10,10,1,4,absent_from_tree,s,0\n"
        "2,ex2,openai/gsm8k,q2,20,20,1,4,absent_from_tree,s,0\n",
        encoding="utf-8",
    )
    m = "direct_reserve_strong_plus_diverse_v1"
    hdr1 = "case_idx,example_id,dataset,question,stratum,seed,budget,provider,model,method,runtime_method,gold_answer,final_selected_answer,normalized_selected_answer,is_correct,gold_present,gold_selected,present_not_selected,absent_from_pool,candidate_branch_count,answer_group_count,top_answer_group,selected_answer_group,top2_support_gap,answer_entropy,action_count,expansion_count,verification_count,token_estimate,cost_estimate,latency_seconds,margin_gate_triggered,fallback_used,fallback_source,support_margin,num_answer_groups,prompt_style_agreement,selected_before_gate,selected_after_gate,gate_reason,failure_type\n"
    (out / "per_case_method_results.csv").write_text(
        hdr1
        + f"1,ex1,openai/gsm8k,q,abs,1,4,cohere,cm,{m},r,10,10,10,1,1,1,0,0,2,1,10,10,0.2,0.5,0,0,0,NA,NA,NA,0,0,NA,NA,NA,NA,NA,NA,NA,ok\n"
        + f"2,ex2,openai/gsm8k,q,abs,1,4,cohere,cm,{m},r,20,5,5,0,0,0,0,0,1,0,0,0,0.0,0.0,0,0,0,NA,NA,NA,0,0,NA,NA,NA,NA,NA,NA,NA,ok\n",
        encoding="utf-8",
    )
    h2 = "case_idx,example_id,dataset,question,stratum,seed,budget,provider,model,method,branch_id,parent_branch_id,branch_depth,branch_prompt_style,reasoning_text,raw_branch_text,predicted_answer,normalized_candidate_answer,answer_group,is_selected,is_gold_group,gold_answer,operation_sequence,intermediate_values,reasoning_role,useful_reasoning_diversity_bonus\n"
    (out / "candidate_branch_table.csv").write_text(
        h2
        + f"1,ex1,openai/gsm8k,q,abs,1,4,cohere,cm,{m},b0,,0,p,NA,NA,10,10,10,1,1,10,NA,NA,NA,NA\n"
        + f"1,ex1,openai/gsm8k,q,abs,1,4,cohere,cm,{m},b1,,0,p,NA,NA,1,1,1,0,0,10,NA,NA,NA,NA\n"
        + f"2,ex2,openai/gsm8k,q,abs,1,4,cohere,cm,{m},b0,,0,p,NA,NA,5,5,5,0,0,20,NA,NA,NA,NA\n"
        + f"2,ex2,openai/gsm8k,q,abs,1,4,cohere,cm,{m},b1,,0,p,NA,NA,20,20,20,1,1,20,NA,NA,NA,NA\n",
        encoding="utf-8",
    )
    h3 = "case_idx,example_id,seed,budget,method,stratum,answer_group,support,is_gold_group,is_selected_group\n"
    (out / "answer_group_summary.csv").write_text(
        h3
        + f"1,ex1,1,4,{m},abs,10,1,1,1\n"
        + f"1,ex1,1,4,{m},abs,1,1,0,0\n"
        + f"2,ex2,1,4,{m},abs,5,1,0,0\n"
        + f"2,ex2,1,4,{m},abs,20,1,1,1\n",
        encoding="utf-8",
    )


def test_build_dataset_synthetic(tmp_path: Path) -> None:
    pkg = tmp_path / "synth_pkg"
    _write_synth(pkg)
    subprocess.check_call(
        [sys.executable, str(SCR / "build_direct_reserve_candidate_scorer_dataset.py"), "--timestamp", "SYN", "--input-dirs", str(pkg.resolve())],
        cwd=REPO,
    )
    ex = REPO / "outputs" / "direct_reserve_candidate_scorer_dataset_SYN" / "examples.csv"
    assert ex.exists()
    with ex.open(encoding="utf-8", newline="") as f:
        r = list(csv.DictReader(f))
    eids = {x["example_id"] for x in r}
    assert eids == {"ex1", "ex2"}


def test_pairwise_trains_when_pos_neg_same_case() -> None:
    from scripts.train_direct_reserve_candidate_scorer import _build_pairs, _gid, DIVERSE

    base: dict = {
        "stratum": "a",
        "source_type": "b",
        "method": DIVERSE,
        "seed": 1,
        "budget": 4,
        "branch_depth": 0,
        "answer_group_support": 1,
        "answer_group_rank": 1,
        "action_count": 0,
        "top2_support_gap": 0.0,
        "answer_entropy": 0.0,
        "n_methods_sharing_norm_answer": 0,
        "selected_by_method": 0,
        "extraction_ok": 1,
        "problem_gold_present": 1,
        "problem_present_not_selected": 0,
        "diverse_gold_in_pool": 1,
        "match_strict_f3_final": 0,
        "match_external_l1_max_final": 0,
        "match_direct_reserve_strong_v1_final": 0,
        "match_direct_reserve_strong_plus_diverse_v1_final": 0,
    }
    r0 = {**base, "example_id": "e1", "is_gold_candidate": 1, "excluded_from_training": 0}
    r1 = {**base, "example_id": "e1", "is_gold_candidate": 0, "excluded_from_training": 0}
    rows, y = [r0, r1], [1, 0]
    g = [_gid(r) for r in rows]
    pv, lr = _build_pairs([0, 1], rows, y, g)
    assert pv is not None and lr is not None


def test_cohere_validation_dry_runs() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("COHERE_API_KEY", "OPENAI_API_KEY")}
    p = subprocess.run(
        [
            sys.executable,
            str(SCR / "run_cohere_direct_reserve_validation.py"),
            "--dry-run",
            "--timestamp",
            "TEST_CDR_NOKEY",
            "--max-cases",
            "1",
            "--seeds",
            "23",
            "--budgets",
            "4",
            "--absent-count",
            "1",
            "--present-count",
            "0",
            "--control-count",
            "0",
            "--loss-artifact",
            "outputs/matched_surface_multiseed_main_comparison_20260423T203259Z/raw_case_results.csv",
            "--include-method",
            "direct_reserve_strong_plus_diverse_v1",
            "--include-method",
            "direct_reserve_strong_plus_diverse_margin_gated_v1",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode() if p.stderr else ""


def test_eval_produces_artifacts() -> None:
    ds = REPO / "outputs" / "direct_reserve_candidate_scorer_dataset_20260426T150000Z" / "examples.csv"
    tr = REPO / "outputs" / "direct_reserve_candidate_scorer_train_20260426T150000Z" / "selected_model.joblib"
    pcase = (
        REPO
        / "outputs"
        / "cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z"
        / "per_case_method_results.csv"
    )
    if not ds.exists() or not tr.exists() or not pcase.exists():
        pytest.skip("full pipeline artifacts not in workspace")
    o = REPO / "outputs" / "direct_reserve_candidate_scorer_eval_PTEST"
    if o.exists():
        for f in o.iterdir():
            f.unlink()
        o.rmdir()
    subprocess.check_call(
        [
            sys.executable,
            str(SCR / "run_direct_reserve_candidate_scorer_eval.py"),
            "--timestamp",
            "PTEST",
            "--dataset-dir",
            "outputs/direct_reserve_candidate_scorer_dataset_20260426T150000Z",
            "--train-dir",
            "outputs/direct_reserve_candidate_scorer_train_20260426T150000Z",
            "--per-case",
            "outputs/cohere_direct_reserve_validation_direct_reserve_scorer_data_collection_20260426T150000Z/per_case_method_results.csv",
        ],
        cwd=REPO,
    )
    assert (o / "selector_comparison.csv").exists()
    assert (o / "case_level_selection.csv").exists()
