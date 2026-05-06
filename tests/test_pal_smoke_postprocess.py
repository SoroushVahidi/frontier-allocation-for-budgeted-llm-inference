from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.materialize_pal_smoke_summary import materialize_pal_smoke


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_postprocess_prefers_result_metadata_for_pal_counts(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir(parents=True, exist_ok=True)

    (in_dir / "selected_cases.csv").write_text("example_id,bucket\nopenai_gsm8k_1,B1_empty_or_no_usable_candidates\n", encoding="utf-8")
    (in_dir / "pal_summary.json").write_text("{}", encoding="utf-8")
    (in_dir / "pal_casebook.csv").write_text("", encoding="utf-8")

    row = {
        "method": "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal",
        "example_id": "openai_gsm8k_1",
        "cohere_logical_api_calls": 3,
        "exact_match": 1,
        "gold_in_tree": 0,
        "parse_extraction_failure": 0,
        "result_metadata": {
            "pal_enabled": True,
            "pal_seed_ran": 1,
            "pal_budget_cost_planned": 1,
            "pal_budget_cost_observed": 1,
            "frontier_budget_before_pal": 4,
            "frontier_budget_after_pal": 3,
            "pal_execution": {
                "pal_code": "a=1\nanswer=2\nprint(answer)",
                "pal_json_answer": "2",
                "pal_confidence": 0.9,
                "pal_parse_ok": True,
                "pal_safety_ok": True,
                "pal_exec_ok": True,
                "pal_candidate_is_strong": True,
                "pal_execution_result": {
                    "pal_stdout": "2\n",
                    "pal_answer_raw": "2",
                    "pal_answer_normalized": "2",
                    "pal_error_type": "",
                },
            },
            "pal_overlay": {"pal_overlay_applied": False},
        },
    }
    _write_jsonl(in_dir / "per_example_records.jsonl", [row])

    summary = materialize_pal_smoke(in_dir, out_dir)
    assert summary["pal_seed_ran"]["num"] == 1
    assert summary["pal_parse_ok"]["num"] == 1
    assert summary["pal_safety_ok"]["num"] == 1
    assert summary["pal_exec_ok"]["num"] == 1

    corrected = json.loads((out_dir / "corrected_pal_summary.json").read_text(encoding="utf-8"))
    assert corrected["pal_seed_ran"]["num"] == 1
    assert corrected["pal_exec_ok"]["num"] == 1

    with (out_dir / "corrected_pal_casebook.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["pal_parse_ok"] == "1"
