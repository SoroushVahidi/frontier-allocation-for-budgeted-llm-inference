import json
import subprocess
import sys
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_fast_selector_selection_outputs_and_oracle_exclusion(tmp_path: Path) -> None:
    art = tmp_path / "artifact"
    art.mkdir()
    rows = [
        {"example_id": "e1", "dataset": "d", "seed": 1, "budget": 4, "method": "external_l1_max", "gold_answer_canonical": "b", "final_answer_canonical": "b"},
        {"example_id": "e1", "dataset": "d", "seed": 1, "budget": 4, "method": "direct_reserve_semantic_frontier_v2", "gold_answer_canonical": "b", "final_answer_canonical": "a", "result_metadata": {"selector_candidate_pool": [{"predicted_answer": "a", "source": "direct", "is_original_selected": 1}, {"predicted_answer": "b", "source": "frontier"}, {"predicted_answer": "b", "source": "frontier"}]}}
    ]
    _write_jsonl(art / "per_example_records.jsonl", rows)
    out = tmp_path / "out"
    subprocess.check_call([sys.executable, "scripts/run_fast_selector_selection_experiment.py", "--artifact-dir", str(art), "--output-dir", str(out)])

    summary = json.loads((out / "selector_summary.json").read_text(encoding="utf-8"))
    assert summary["best_deployable_by_accuracy"]["selector"] != "oracle_selector"
    selectors = {r["selector"]: r for r in summary["selector_rows"]}
    assert selectors["support_only"]["fixes"] == 1
    assert selectors["support_only"]["breaks"] == 0
    assert selectors["support_only"]["override_precision"] == 1.0
    assert "risk_gated_support_override" in selectors
    assert "conservative_override" in selectors


def test_diagnose_reports_rejection_reasons(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    _write_jsonl(bad / "per_example_records.jsonl", [{"example_id": "x", "method": "external_l1_max"}])
    proc = subprocess.run([sys.executable, "scripts/run_fast_selector_selection_experiment.py", "--artifact-dir", str(bad), "--diagnose-artifacts"], check=True, text=True, capture_output=True)
    out = proc.stdout
    assert "REJECT" in out
    assert "no DR-v2 rows" in out
    assert "no gold answers" in out
    assert "zero usable paired examples" in out


def test_unusable_artifact_fails_loudly(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    _write_jsonl(bad / "per_example_records.jsonl", [{"example_id": "x", "method": "direct_reserve_semantic_frontier_v2"}])
    proc = subprocess.run([sys.executable, "scripts/run_fast_selector_selection_experiment.py", "--artifact-dir", str(bad), "--output-dir", str(tmp_path / "o")], text=True, capture_output=True)
    assert proc.returncode != 0
    assert "No usable selector artifact found" in (proc.stderr + proc.stdout)
