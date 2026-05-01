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


def test_trace_recovery_schema_variants_and_counts(tmp_path: Path):
    in1 = tmp_path / "trace_recovery.jsonl"
    in2 = tmp_path / "focused.jsonl"
    out = tmp_path / "out2"
    # trace-recovery shaped: candidate_nodes present
    tr_with_nodes = {
        "case_id": "tr1", "dataset": "d", "example_id": "10", "seed": 0, "budget": 100, "our_method_name": "m",
        "problem_statement": "p",
        "candidate_nodes": [
            {"candidate_id": "a", "final_answer": "1", "trace_text": "trace a"},
            {"candidate_id": "b", "final_answer": "2", "steps": ["s"]},
        ],
        "evaluation_only": {"gold_answer": "1"},
        "verifier_input": {"problem_statement": "p", "candidates_for_verifier": [{"candidate_id": "a"}]},
        "gold_in_aggregate_answer_groups": True, "gold_in_extracted_terminal_node_finals": True,
    }
    # trace-recovery shaped fallback: no candidate_nodes, reconstruct from verifier_input.candidates_for_verifier
    tr_from_verifier = {
        "case_id": "tr2", "dataset": "d", "example_id": "11", "seed": 0, "budget": 100, "our_method_name": "m",
        "problem_statement": "p2",
        "candidate_nodes": [],
        "evaluation_only": {"gold_answer": "3"},
        "verifier_input": {"problem_statement": "p2", "candidates_for_verifier": [{"candidate_id": "x", "final_answer": "3", "steps": ["s1", "s2"]}]},
        "gold_in_aggregate_answer_groups": True, "gold_in_extracted_terminal_node_finals": False,
    }
    # focused33 shaped record
    focused = {
        "case_id": "f1", "dataset": "d", "example_id": "12", "seed": 0, "budget": 100, "our_method_name": "m",
        "problem_statement": "p3",
        "candidate_nodes": [{"candidate_id": "f", "final_answer": "4", "step_text": "st"}],
        "evaluation_only": {"gold_answer": "4", "oracle_selector_would_fix": False},
        "verifier_input": {"problem_statement": "p3", "candidates_for_verifier": [{"candidate_id": "f"}], "gold_answer": "SHOULD_BE_REMOVED"},
        "gold_in_aggregate_answer_groups": True, "gold_in_extracted_terminal_node_finals": True,
    }
    write_jsonl(in1, [tr_with_nodes, tr_from_verifier])
    write_jsonl(in2, [focused])
    subprocess.check_call([
        sys.executable, "scripts/build_unified_selector_evidence.py",
        "--input", f"{in1}:new_cap100_trace_recovery", "--input", f"{in2}:focused33_wulver",
        "--output-dir", str(out), "--no-gold-in-verifier-input"
    ], cwd=Path(__file__).resolve().parents[1])
    kept = [json.loads(x) for x in (out / "unified_candidate_trace_enriched.jsonl").read_text().splitlines() if x.strip()]
    assert len(kept) == 3
    tr2 = next(r for r in kept if r["case_id"] == "tr2")
    assert len(tr2["candidate_nodes"]) == 1
    assert tr2["has_any_candidate_trace"] is True
    assert tr2["usable_for_trace_aware_selector"] is True
    assert "gold_answer" not in json.dumps(tr2["verifier_input"])
    assert "oracle" not in json.dumps(tr2["verifier_input"]).lower()
    assert "evaluation_only" not in json.dumps(tr2["verifier_input"])
    focused_kept = next(r for r in kept if r["case_id"] == "f1")
    assert "candidates_for_verifier" in focused_kept["verifier_input"]
    summary = json.loads((out / "unified_selector_evidence_summary.json").read_text())
    assert summary["overall"]["candidate_nodes"] == 4
    assert summary["overall"]["traced_candidate_nodes"] == 4
    assert summary["by_provenance_source"]["new_cap100_trace_recovery"]["candidate_nodes"] == 3
    assert summary["by_provenance_source"]["new_cap100_trace_recovery"]["traced_candidate_nodes"] == 3
    assert summary["by_provenance_source"]["new_cap100_trace_recovery"]["usable_for_trace_aware_selector"] == 2


def test_companion_matched_raw_recovery(tmp_path: Path):
    src = tmp_path / "pkg"
    src.mkdir()
    inp = src / "candidate_trace_enriched.jsonl"
    matched = src / "matched_raw_records.jsonl"
    out = tmp_path / "out3"
    shell = {
        "case_id": "k1", "dataset": "d", "example_id": "9", "seed": 0, "budget": 100, "our_method_name": "m",
        "problem_statement": "p", "candidate_nodes": [], "verifier_input": {"problem_statement": "p", "candidate_nodes": []},
        "evaluation_only": {"gold_answer": "7"}, "gold_in_aggregate_answer_groups": True
    }
    companion = {
        "case_id": "k1", "dataset": "d", "example_id": "9", "seed": 0, "budget": 100, "method": "m",
        "candidate_nodes": [{"candidate_id": "c", "final_answer": "7", "trace_text": "t"}]
    }
    write_jsonl(inp, [shell]); write_jsonl(matched, [companion])
    subprocess.check_call([sys.executable, "scripts/build_unified_selector_evidence.py", "--input", f"{inp}:new_cap100_trace_recovery", "--output-dir", str(out), "--no-gold-in-verifier-input"], cwd=Path(__file__).resolve().parents[1])
    kept = [json.loads(x) for x in (out / "unified_candidate_trace_enriched.jsonl").read_text().splitlines() if x.strip()]
    assert len(kept[0]["candidate_nodes"]) == 1
    assert kept[0]["usable_for_trace_aware_selector"] is True
    assert kept[0]["companion_candidates_recovered"] is True


def test_inventory_script_detects_candidates_and_sanitizes(tmp_path: Path):
    root = tmp_path / "r"; root.mkdir()
    f = root / "x.jsonl"
    write_jsonl(f, [{"case_id": "1", "candidate_nodes": [{"final_answer": "10", "trace_text": "abc"}], "gold_answer": "10"}])
    out = tmp_path / "inv"
    subprocess.check_call([sys.executable, "scripts/inventory_candidate_bearing_artifacts.py", "--roots", str(root), "--output-dir", str(out)], cwd=Path(__file__).resolve().parents[1])
    inv = json.loads((out / "candidate_artifact_inventory.json").read_text())
    row = next(r for r in inv["files"] if r.get("path", "").endswith("x.jsonl"))
    assert row["likely_candidate_bearing"] is True
    top = [json.loads(x) for x in (out / "candidate_artifact_inventory_top_candidates.jsonl").read_text().splitlines() if x.strip()]
    assert "[REDACTED]" in json.dumps(top)
