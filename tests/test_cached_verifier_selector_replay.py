import json
import subprocess
import sys
from pathlib import Path


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.write_text(",".join(header) + "\n" + "\n".join(",".join(r) for r in rows) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_override_when_challenger_beats_incumbent_by_margin(tmp_path: Path):
    diag = tmp_path / "candidate_diagnostics.csv"
    per = tmp_path / "per_case_results.csv"
    scores = tmp_path / "verifier_scores.jsonl"
    out = tmp_path / "out"

    # candidate_diagnostics.csv needs guarded row with incumbent + gold (gold only for eval)
    _write_csv(
        diag,
        header=[
            "case_id",
            "method",
            "example_id",
            "effective_gold_for_eval",
            "normalized_prediction",
            "distinct_normalized_candidate_count",
        ],
        rows=[
            ["c1", "guarded", "e1", "B", "A", "2"],
        ],
    )
    _write_csv(
        per,
        header=["case_id", "guarded_gold_present"],
        rows=[["c1", "yes"]],
    )
    # ambiguous136-style score rows: support_score in top-level, ids in payload
    _write_jsonl(
        scores,
        rows=[
            {"plan_id": "c1::A", "parse_ok": True, "support_score": 0.10, "payload": {"case_id": "c1", "normalized_answer": "A"}},
            {"plan_id": "c1::B", "parse_ok": True, "support_score": 0.30, "payload": {"case_id": "c1", "normalized_answer": "B"}},
        ],
    )

    subprocess.check_call(
        [
            sys.executable,
            "scripts/run_cached_verifier_selector_replay.py",
            "--per-case-results",
            str(per),
            "--candidate-diagnostics",
            str(diag),
            "--verifier-scores",
            str(scores),
            "--output-dir",
            str(out),
            "--margin",
            "0.15",
            "--method",
            "guarded",
        ]
    )
    summary = json.loads((out / "selector_replay_summary.json").read_text(encoding="utf-8"))
    assert summary["single_margin_summary"]["fixes_vs_guarded"] == 1
    assert summary["single_margin_summary"]["breaks_vs_guarded"] == 0
    cb = (out / "selector_replay_casebook.csv").read_text(encoding="utf-8")
    assert "verifier_pred" in cb and ",B," in cb


def test_below_margin_keeps_incumbent(tmp_path: Path):
    diag = tmp_path / "candidate_diagnostics.csv"
    per = tmp_path / "per_case_results.csv"
    scores = tmp_path / "verifier_scores.jsonl"
    out = tmp_path / "out"

    _write_csv(
        diag,
        header=["case_id", "method", "example_id", "effective_gold_for_eval", "normalized_prediction", "distinct_normalized_candidate_count"],
        rows=[["c1", "guarded", "e1", "A", "A", "2"]],
    )
    _write_csv(per, header=["case_id", "guarded_gold_present"], rows=[["c1", "yes"]])
    _write_jsonl(
        scores,
        rows=[
            {"plan_id": "c1::A", "parse_ok": True, "support_score": 0.80, "payload": {"case_id": "c1", "normalized_answer": "A"}},
            {"plan_id": "c1::B", "parse_ok": True, "support_score": 0.85, "payload": {"case_id": "c1", "normalized_answer": "B"}},
        ],
    )

    subprocess.check_call(
        [
            sys.executable,
            "scripts/run_cached_verifier_selector_replay.py",
            "--per-case-results",
            str(per),
            "--candidate-diagnostics",
            str(diag),
            "--verifier-scores",
            str(scores),
            "--output-dir",
            str(out),
            "--margin",
            "0.15",
            "--method",
            "guarded",
        ]
    )
    cb = (out / "selector_replay_casebook.csv").read_text(encoding="utf-8")
    assert ",A," in cb  # verifier_pred should stay A
    summary = json.loads((out / "selector_replay_summary.json").read_text(encoding="utf-8"))
    assert summary["single_margin_summary"]["trigger_count_ambiguous"] == 0


def test_missing_incumbent_score_keeps_incumbent_and_records_reason(tmp_path: Path):
    diag = tmp_path / "candidate_diagnostics.csv"
    per = tmp_path / "per_case_results.csv"
    scores = tmp_path / "verifier_scores.jsonl"
    out = tmp_path / "out"

    _write_csv(
        diag,
        header=["case_id", "method", "example_id", "effective_gold_for_eval", "normalized_prediction", "distinct_normalized_candidate_count"],
        rows=[["c1", "guarded", "e1", "A", "A", "2"]],
    )
    _write_csv(per, header=["case_id", "guarded_gold_present"], rows=[["c1", "yes"]])
    _write_jsonl(
        scores,
        rows=[
            {"plan_id": "c1::B", "parse_ok": True, "support_score": 0.90, "payload": {"case_id": "c1", "normalized_answer": "B"}},
        ],
    )

    subprocess.check_call(
        [
            sys.executable,
            "scripts/run_cached_verifier_selector_replay.py",
            "--per-case-results",
            str(per),
            "--candidate-diagnostics",
            str(diag),
            "--verifier-scores",
            str(scores),
            "--output-dir",
            str(out),
            "--margin",
            "0.05",
            "--method",
            "guarded",
        ]
    )
    cb = (out / "selector_replay_casebook.csv").read_text(encoding="utf-8")
    assert "missing_incumbent_score_kept_incumbent" in cb
    assert ",A," in cb


def test_gold_fields_do_not_affect_decision(tmp_path: Path):
    diag = tmp_path / "candidate_diagnostics.csv"
    per = tmp_path / "per_case_results.csv"
    scores = tmp_path / "verifier_scores.jsonl"
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    _write_csv(
        diag,
        header=["case_id", "method", "example_id", "effective_gold_for_eval", "normalized_prediction", "distinct_normalized_candidate_count"],
        rows=[["c1", "guarded", "e1", "A", "A", "2"]],
    )
    _write_csv(per, header=["case_id", "guarded_gold_present"], rows=[["c1", "yes"]])
    _write_jsonl(
        scores,
        rows=[
            {"plan_id": "c1::A", "parse_ok": True, "support_score": 0.10, "payload": {"case_id": "c1", "normalized_answer": "A"}},
            {"plan_id": "c1::B", "parse_ok": True, "support_score": 0.30, "payload": {"case_id": "c1", "normalized_answer": "B"}},
        ],
    )

    subprocess.check_call(
        [
            sys.executable,
            "scripts/run_cached_verifier_selector_replay.py",
            "--per-case-results",
            str(per),
            "--candidate-diagnostics",
            str(diag),
            "--verifier-scores",
            str(scores),
            "--output-dir",
            str(out1),
            "--margin",
            "0.15",
            "--method",
            "guarded",
        ]
    )

    # Change gold only; decision should remain override to B.
    _write_csv(
        diag,
        header=["case_id", "method", "example_id", "effective_gold_for_eval", "normalized_prediction", "distinct_normalized_candidate_count"],
        rows=[["c1", "guarded", "e1", "B", "A", "2"]],
    )
    subprocess.check_call(
        [
            sys.executable,
            "scripts/run_cached_verifier_selector_replay.py",
            "--per-case-results",
            str(per),
            "--candidate-diagnostics",
            str(diag),
            "--verifier-scores",
            str(scores),
            "--output-dir",
            str(out2),
            "--margin",
            "0.15",
            "--method",
            "guarded",
        ]
    )

    cb1 = (out1 / "selector_replay_casebook.csv").read_text(encoding="utf-8")
    cb2 = (out2 / "selector_replay_casebook.csv").read_text(encoding="utf-8")
    assert ",B," in cb1 and ",B," in cb2

