"""No-API tests for disjoint direct-reserve scorer planning."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCR = REPO / "scripts" / "plan_disjoint_direct_reserve_scorer_cases.py"


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


def _loss_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i in range(1, 13):
        rows.append(
            {
                "example_id": f"p{i}",
                "dataset": "openai/gsm8k",
                "question": f"Question {i}?",
                "gold_answer": str(i),
                "absent_from_tree": int(i <= 4),
                "present_not_selected": int(5 <= i <= 8),
                "is_correct": int(i >= 9),
            }
        )
    return rows


def test_planner_excludes_prior_packages_and_writes_overlap_report(tmp_path: Path) -> None:
    loss = tmp_path / "loss.csv"
    first = tmp_path / "first"
    second = tmp_path / "second"
    out = tmp_path / "plan"
    _write_csv(loss, _loss_rows())
    _write_csv(first / "planned_cases.csv", [{"example_id": "p1"}, {"example_id": "p2"}])
    _write_csv(second / "per_case_method_results.csv", [{"example_id": "p3"}, {"example_id": "p4"}])

    subprocess.check_call(
        [
            sys.executable,
            str(SCR),
            "--loss-artifact",
            str(loss),
            "--exclude-output",
            str(first),
            "--exclude-output",
            str(second),
            "--max-cases",
            "6",
            "--absent-count",
            "2",
            "--present-count",
            "2",
            "--control-count",
            "2",
            "--seed",
            "37",
            "--output-dir",
            str(out),
        ],
        cwd=REPO,
    )

    planned = _read_csv(out / "planned_cases.csv")
    planned_ids = {row["example_id"] for row in planned}
    assert planned_ids
    assert not (planned_ids & {"p1", "p2", "p3", "p4"})
    overlap = _read_csv(out / "overlap_report.csv")
    assert {row["source_label"] for row in overlap} == {"first_slice", "second_slice"}
    assert all(row["total_overlap_count"] == "0" for row in overlap)


def test_planner_reports_insufficient_disjoint_candidates(tmp_path: Path) -> None:
    loss = tmp_path / "loss.csv"
    prior = tmp_path / "prior"
    out = tmp_path / "plan"
    _write_csv(loss, _loss_rows()[:5])
    _write_csv(prior / "case_level_selection.csv", [{"example_id": "p1"}, {"example_id": "p2"}, {"example_id": "p3"}])

    subprocess.check_call(
        [
            sys.executable,
            str(SCR),
            "--loss-artifact",
            str(loss),
            "--exclude-output",
            str(prior),
            "--max-cases",
            "5",
            "--absent-count",
            "2",
            "--present-count",
            "2",
            "--control-count",
            "1",
            "--output-dir",
            str(out),
        ],
        cwd=REPO,
    )

    planned = _read_csv(out / "planned_cases.csv")
    assert len(planned) == 2
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "insufficient_disjoint_candidates" in readme
    assert all(row["total_overlap_count"] == "0" for row in _read_csv(out / "overlap_report.csv"))
