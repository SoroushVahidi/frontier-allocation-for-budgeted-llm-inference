import json, subprocess, sys
from pathlib import Path


def write_jsonl(p: Path, rows):
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_build_unified_selector_evidence(tmp_path: Path):
    in1 = tmp_path / "a.jsonl"
    in2 = tmp_path / "b.jsonl"
    out = tmp_path / "out"

    base = {
        "case_id": "c1", "dataset": "d", "example_id": "1", "seed": 0, "budget": 100, "our_method_name": "m",
        "problem_statement": "p", "gold_in_aggregate_answer_groups": True,
        "gold_in_extracted_terminal_node_finals": False,
        "selected_answer_in_extracted_terminal_node_finals": False,
        "candidate_nodes": [{"candidate_id": "a", "trace_text": ""}],
        "evaluation_only": {"gold_answer": "10", "oracle_selector_would_fix": True},
        "verifier_input": {"problem_statement": "p", "candidate_nodes": [{"candidate_id": "a"}]},
    }
    better_dup = dict(base)
    better_dup["case_id"] = "c1b"
    better_dup["candidate_nodes"] = [{"candidate_id": "a", "trace_text": "t1"}, {"candidate_id": "b", "trace_text": "t2"}]
    better_dup["gold_in_extracted_terminal_node_finals"] = True

    unique2 = {
        "case_id": "c2", "dataset": "d", "example_id": "2", "seed": 0, "budget": 100, "our_method_name": "m",
        "problem_statement": "p2", "candidate_nodes": [{"candidate_id": "x", "step_text": "s"}],
        "evaluation_only": {"gold_answer": "8", "our_correct": True},
        "verifier_input": {"problem_statement": "p2", "candidate_nodes": [{"candidate_id": "x"}]},
        "gold_in_aggregate_answer_groups": True,
        "gold_in_extracted_terminal_node_finals": True,
        "selected_answer_in_extracted_terminal_node_finals": True,
    }
    write_jsonl(in1, [base, unique2])
    write_jsonl(in2, [better_dup])

    subprocess.check_call([
        sys.executable, "scripts/build_unified_selector_evidence.py",
        "--input", f"{in1}:s1", "--input", f"{in2}:s2", "--output-dir", str(out),
        "--prefer-source-label", "s2", "--no-gold-in-verifier-input"
    ], cwd=Path(__file__).resolve().parents[1])

    kept = [json.loads(x) for x in (out / "unified_candidate_trace_enriched.jsonl").read_text().splitlines() if x.strip()]
    assert len(kept) == 2
    rec = next(r for r in kept if r["example_id"] == "1")
    assert rec["provenance_source"] == "s2"
    assert len(rec["candidate_nodes"]) == 2
    assert rec["has_any_candidate_trace"] is True
    assert "gold_answer" in rec["evaluation_only"]
    assert "gold_answer" not in json.dumps(rec["verifier_input"])

    excluded = [json.loads(x) for x in (out / "excluded_or_duplicate_cases.jsonl").read_text().splitlines() if x.strip()]
    assert len(excluded) == 1

    summary = json.loads((out / "unified_selector_evidence_summary.json").read_text())
    assert summary["overall"]["total_input_records"] == 3
    assert summary["overall"]["total_unique_records"] == 2
    assert summary["overall"]["total_duplicates_excluded"] == 1
    assert summary["by_provenance_source"]["s1"]["input_records"] == 2
    assert summary["by_provenance_source"]["s2"]["input_records"] == 1
