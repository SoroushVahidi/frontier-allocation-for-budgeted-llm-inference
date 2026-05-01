import csv
import json
from pathlib import Path

from scripts.inventory_trace_artifacts import _is_one, _read_csv, inventory


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for row in rows for k in row})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_is_one_accepts_common_true_values():
    assert _is_one("1")
    assert _is_one("true")
    assert _is_one("True")
    assert not _is_one("0")
    assert not _is_one("")


def test_read_csv_missing_file_returns_empty(tmp_path: Path):
    assert _read_csv(tmp_path / "missing.csv") == []


def test_inventory_counts_synthetic_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    _write_csv(
        Path("outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv"),
        [
            {"case_id": "a", "trace_available": "1", "gold_present_in_candidate_groups": "1", "oracle_selector_would_fix": "1"},
            {"case_id": "b", "trace_available": "1", "gold_present_in_candidate_groups": "0", "oracle_selector_would_fix": "1"},
        ],
    )

    enriched = {
        "focused_input_rows": 1,
        "raw_records_found": 1,
        "cases_with_candidate_nodes_positive": 1,
        "cases_with_at_least_one_candidate_trace": 1,
        "cases_with_all_candidate_traces": 1,
        "total_candidate_nodes_extracted": 2,
        "total_candidate_nodes_with_trace_text": 2,
        "cases_gold_canonical_in_extracted_node_finals": 1,
        "cases_gold_canonical_in_casebook_candidates_aggregate": 1,
    }
    p = Path("outputs/focused33_trace_enriched_20260501T000906Z/focused33_trace_enrichment_summary.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(enriched), encoding="utf-8")

    retry = {"total_trace_complete_losses_collected": 3, "gold_present_count": 3, "oracle_would_fix_count": 3}
    p2 = Path("outputs/trace_complete_external_losses_retry_20260430T204900Z/trace_complete_loss_summary.json")
    p2.parent.mkdir(parents=True, exist_ok=True)
    p2.write_text(json.dumps(retry), encoding="utf-8")

    trace_index = Path(
        "outputs/trace_complete_external_losses_retry_20260430T204900Z/"
        "cohere_real_model_cost_normalized_validation_20260430T204900Z/per_case_trace_index.csv"
    )
    _write_csv(
        trace_index,
        [
            {
                "dataset": "openai/gsm8k",
                "example_id": "e1",
                "seed": "11",
                "budget": "4",
                "method": "m",
                "trace_path": "traces/e1.json",
            },
            {
                "dataset": "openai/gsm8k",
                "example_id": "e2",
                "seed": "11",
                "budget": "4",
                "method": "m",
                "trace_path": "traces/missing.json",
            },
        ],
    )
    present_trace = trace_index.parent / "traces/e1.json"
    present_trace.parent.mkdir(parents=True, exist_ok=True)
    present_trace.write_text("{}", encoding="utf-8")

    rows, summary = inventory([Path("outputs")])

    assert summary["broad_trace_complete_rows"] == 2
    assert summary["focused_rows"] == 1
    assert summary["focused_candidate_nodes"] == 2
    assert summary["focused_traced_candidate_nodes"] == 2
    assert summary["retry_trace_complete_losses"] == 3
    assert summary["per_case_trace_index_rows"] == 2
    assert summary["per_case_trace_paths_missing"] == 1
    assert len(rows) == 4
