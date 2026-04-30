#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _key(r: dict[str, Any]) -> tuple[str, str, int, int]:
    return (
        str(r.get("dataset", "NA")),
        str(r.get("example_id", "NA")),
        int(r.get("seed", 0)),
        int(r.get("budget", 0)),
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--scan-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--require-paired-l1", action="store_true")
    p.add_argument("--deduplicate", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    scan_dir = Path(args.scan_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scan_rows = _read_csv(scan_dir / "artifact_scan.csv")

    kept_rows = [
        r
        for r in scan_rows
        if int(float(r.get("usable", "0") or 0)) == 1
        and float(r.get("oracle_minus_l1", "0") or 0) > 0
        and float(r.get("oracle_minus_dr", "0") or 0) > 0
        and str(r.get("reconstructed_path", "")).strip()
    ]
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, int]] = set()
    source_count: dict[str, int] = {}
    for row in kept_rows:
        source = str(row["artifact_path"])
        path = Path(row["reconstructed_path"])
        for ex in _read_jsonl(path):
            if args.require_paired_l1:
                if "external_l1_max_answer" not in ex or "current_dr_v2_answer" not in ex:
                    continue
            if "candidate_groups" not in ex or not ex["candidate_groups"]:
                continue
            k = _key(ex)
            if args.deduplicate and k in seen:
                continue
            seen.add(k)
            ex["source_artifact_path"] = source
            records.append(ex)
            source_count[source] = source_count.get(source, 0) + 1

    out_path = out_dir / "per_example_records.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {
        "scan_dir": str(scan_dir),
        "output_dir": str(out_dir),
        "input_usable_positive_artifacts": len(kept_rows),
        "output_examples": len(records),
        "deduplicated": bool(args.deduplicate),
        "sources": source_count,
    }
    (out_dir / "build_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Wrote {out_dir / 'build_summary.json'}")


if __name__ == "__main__":
    main()
