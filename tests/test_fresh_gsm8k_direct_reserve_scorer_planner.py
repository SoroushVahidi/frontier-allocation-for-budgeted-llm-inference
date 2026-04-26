"""No-API tests for fresh GSM8K direct-reserve scorer planning."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCR = REPO / "scripts" / "plan_fresh_gsm8k_direct_reserve_scorer_cases.py"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _gsm8k_like_rows(n: int = 12) -> list[dict[str, object]]:
    return [
        {
            "example_id": f"openai_gsm8k_{i}",
            "question": f"If there are {i} apples and 2 more arrive, how many apples?",
            "answer": f"#### {i + 2}",
        }
        for i in range(n)
    ]


def test_fresh_planner_samples_synthetic_and_excludes_prior_ids(tmp_path: Path) -> None:
    source = tmp_path / "gsm8k.csv"
    first = tmp_path / "first"
    second = tmp_path / "second"
    replay = tmp_path / "replay"
    out = tmp_path / "plan"
    _write_csv(source, _gsm8k_like_rows())
    _write_csv(first / "planned_cases.csv", [{"example_id": "openai_gsm8k_0"}])
    _write_csv(second / "per_case_method_results.csv", [{"example_id": "openai_gsm8k_1"}])
    _write_csv(replay / "replay_case_list.csv", [{"problem_id": "openai_gsm8k_2"}])

    subprocess.check_call(
        [
            sys.executable,
            str(SCR),
            "--synthetic-input",
            str(source),
            "--exclude-output",
            str(first),
            "--exclude-output",
            str(second),
            "--exclude-output",
            str(replay),
            "--max-cases",
            "5",
            "--seed",
            "43",
            "--output-dir",
            str(out),
        ],
        cwd=REPO,
    )

    planned = _read_csv(out / "planned_cases.csv")
    assert len(planned) == 5
    planned_ids = {row["example_id"] for row in planned}
    assert not (planned_ids & {"openai_gsm8k_0", "openai_gsm8k_1", "openai_gsm8k_2"})
    assert all(row["budget"] == "4" for row in planned)
    assert all(row["stratum"] == "fresh_gsm8k_unseen" for row in planned)
    overlap = _read_csv(out / "overlap_report.csv")
    assert all(row["total_overlap_count"] == "0" for row in overlap)
    assert {row["source_label"] for row in overlap} == {
        "prior_scorer_slice_1",
        "prior_scorer_slice_2",
        "replay_seed",
    }


def test_fresh_planner_reports_insufficient_fresh_cases(tmp_path: Path) -> None:
    source = tmp_path / "gsm8k.csv"
    prior = tmp_path / "prior"
    out = tmp_path / "plan"
    _write_csv(source, _gsm8k_like_rows(4))
    _write_csv(prior / "case_level_selection.csv", [{"example_id": "openai_gsm8k_0"}])

    subprocess.check_call(
        [
            sys.executable,
            str(SCR),
            "--synthetic-input",
            str(source),
            "--exclude-output",
            str(prior),
            "--max-cases",
            "5",
            "--output-dir",
            str(out),
        ],
        cwd=REPO,
    )

    planned = _read_csv(out / "planned_cases.csv")
    assert len(planned) == 3
    manifest = (out / "manifest.json").read_text(encoding="utf-8")
    assert "insufficient_fresh_candidates" in manifest
    assert (out / "fresh_candidate_pool.csv").exists()
