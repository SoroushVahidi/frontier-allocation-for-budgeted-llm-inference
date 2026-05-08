from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.final_target_verifier import final_target_verifier_features


REPO = Path(__file__).resolve().parents[1]


def test_feature_detection_synthetic_examples() -> None:
    a = final_target_verifier_features("A has 10 and B has 7. How many more does A have?")
    assert a["asks_difference"]
    assert a["sign_direction_cue"]

    b = final_target_verifier_features("There are 40 total; 12 left. How many were used?")
    assert b["asks_total"] or b["asks_remaining"]

    c = final_target_verifier_features("Adults and kids share by ratio 2:1. What percent does each adult get?")
    assert c["ratio_partition_risk"]
    assert c["asks_ratio_part"]

    d = final_target_verifier_features("Battery loses 9% per hour for 5 hours, then 7% per hour for 3 hours.")
    assert d["percent_base_denominator_risk"]
    assert d["state_update_risk"]

    e = final_target_verifier_features("Drop the lowest score and average the rest to reach target average 93.")
    assert e["dropped_lowest_average_risk"]
    assert e["asks_average_target"]


def test_verifier_has_no_gold_or_external_dependencies() -> None:
    text = "Simple total question with 3 and 4."
    f1 = final_target_verifier_features(text)
    f2 = final_target_verifier_features(text, candidate_answer_text="123", candidate_trace="target noted")
    assert set(f1.keys()) == set(f2.keys())


def test_fix_dry_run_prompts_have_no_gold_or_external_leak() -> None:
    out_dirs = sorted(REPO.glob("outputs/external_l1_only_fix_dry_run_*"))
    assert out_dirs, "missing fix dry-run outputs"
    out = out_dirs[-1]
    rows = list(csv.DictReader((out / "external_l1_only_fix_cases.csv").open(encoding="utf-8")))
    assert len(rows) == 7
    for r in rows:
        pp = out / r["prompt_path"]
        txt = pp.read_text(encoding="utf-8")
        gold = (r.get("gold_answer") or "").strip()
        ext = (r.get("external_l1_prediction") or "").strip()
        if gold:
            assert gold not in txt
        if ext:
            assert ext not in txt


def test_all_cases_have_non_unknown_fix_and_percent_flagged() -> None:
    out_dirs = sorted(REPO.glob("outputs/external_l1_only_fix_dry_run_*"))
    assert out_dirs, "missing fix dry-run outputs"
    out = out_dirs[-1]
    rows = list(csv.DictReader((out / "external_l1_only_fix_cases.csv").open(encoding="utf-8")))
    assert len(rows) == 7
    assert all((r.get("proposed_fix_type") or "") != "unknown" for r in rows)

    percent_rows = [r for r in rows if "percent_base_denominator_risk" in (r.get("verifier_features_json") or "")]
    assert percent_rows, "expected at least one percent-base flagged case"
    for r in percent_rows:
        vf = json.loads(r["verifier_features_json"])
        if vf.get("percent_base_denominator_risk"):
            assert r["selected_scaffold_candidate"] == "percent_base_denominator_v2"
