import json
from pathlib import Path

from scripts.analyze_cerebras_slowness_for_support import (
    parse_ts,
    provider_rows_per_hour,
    series_quantiles,
)


def test_parse_ts_iso_z():
    t = parse_ts("2026-05-24T19:01:39.879109Z")
    assert t is not None
    assert t.year == 2026
    assert t.tzinfo is not None


def test_series_quantiles_empty():
    q = series_quantiles([])
    assert q["median"] is None
    assert q["max"] is None


def test_provider_rows_per_hour_basic(tmp_path: Path):
    p = tmp_path / "rows.jsonl"
    rows = [
        {
            "provider": "x",
            "dataset": "d",
            "timestamp": "2026-05-24T00:00:00+00:00",
        },
        {
            "provider": "x",
            "dataset": "d",
            "timestamp": "2026-05-24T00:30:00+00:00",
        },
        {
            "provider": "x",
            "dataset": "d",
            "timestamp": "2026-05-24T01:00:00+00:00",
        },
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    out = provider_rows_per_hour(p, "dummy")
    assert out is not None
    assert out["rows"] == 3
    assert out["rows_per_hour"] == 3.0
    assert out["seconds_per_row"] == 1200.0
