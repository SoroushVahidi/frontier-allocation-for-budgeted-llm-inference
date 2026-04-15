#!/usr/bin/env python3
"""Deterministic sharding + merge utility for oracle-label pilot execution.

This utility prepares pilot-scale runs by splitting a full state manifest into
stable shards and merging per-shard generator outputs back into one combined
label file with provenance checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Shard and merge utilities for oracle-label pilot")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_split = sub.add_parser("split", help="Split a pilot state manifest into deterministic shards")
    p_split.add_argument("--state-manifest", required=True)
    p_split.add_argument("--output-dir", required=True)
    p_split.add_argument("--num-shards", type=int, required=True)
    p_split.add_argument("--shard-prefix", default="shard")

    p_merge = sub.add_parser("merge", help="Merge per-shard labels into one ordered label file")
    p_merge.add_argument("--split-manifest", required=True, help="Path to shard_split_manifest.json from split step")
    p_merge.add_argument(
        "--shard-run-root",
        required=True,
        help="Root dir containing per-shard run dirs named <shard-prefix>_NNN_of_NNN",
    )
    p_merge.add_argument("--output-dir", required=True)
    p_merge.add_argument("--labels-filename", default="oracle_stop_vs_act_labels.jsonl")
    p_merge.add_argument("--manifest-filename", default="oracle_label_manifest.json")
    p_merge.add_argument("--allow-missing-shards", action="store_true")
    return p.parse_args()


def _split_manifest(args: argparse.Namespace) -> None:
    manifest_path = Path(args.state_manifest)
    rows = _read_jsonl(manifest_path)
    if not rows:
        raise SystemExit("State manifest has no rows")

    num_shards = int(args.num_shards)
    if num_shards <= 0:
        raise SystemExit("--num-shards must be > 0")

    for idx, row in enumerate(rows):
        if "state_id" not in row:
            raise SystemExit(f"Row {idx} missing required field: state_id")

    out_dir = Path(args.output_dir)
    shard_manifest_dir = out_dir / "shard_manifests"
    shard_manifest_dir.mkdir(parents=True, exist_ok=True)

    shard_rows: list[list[dict[str, Any]]] = [[] for _ in range(num_shards)]
    shard_state_ids: list[list[str]] = [[] for _ in range(num_shards)]

    for idx, row in enumerate(rows):
        shard_id = idx % num_shards
        shard_rows[shard_id].append(row)
        shard_state_ids[shard_id].append(str(row["state_id"]))

    shards_meta: list[dict[str, Any]] = []
    for shard_id in range(num_shards):
        shard_name = f"{args.shard_prefix}_{shard_id:03d}_of_{num_shards:03d}"
        shard_path = shard_manifest_dir / f"{shard_name}.jsonl"
        _write_jsonl(shard_path, shard_rows[shard_id])

        shards_meta.append(
            {
                "shard_id": shard_id,
                "shard_name": shard_name,
                "manifest_path": str(shard_path),
                "rows": len(shard_rows[shard_id]),
                "first_state_id": shard_state_ids[shard_id][0] if shard_state_ids[shard_id] else None,
                "last_state_id": shard_state_ids[shard_id][-1] if shard_state_ids[shard_id] else None,
                "state_ids": shard_state_ids[shard_id],
            }
        )

    split_manifest = {
        "tool": "oracle_label_pilot_sharding_v1",
        "split_strategy": "stable_round_robin_by_manifest_row_index",
        "source_state_manifest": str(manifest_path.resolve()),
        "source_state_manifest_sha256": _sha256_file(manifest_path),
        "rows_total": len(rows),
        "num_shards": num_shards,
        "shard_prefix": args.shard_prefix,
        "shards": shards_meta,
        "notes": [
            "Shard rows preserve original manifest row content.",
            "Merged output should be re-ordered by original state-manifest row index.",
        ],
    }

    split_manifest_path = out_dir / "shard_split_manifest.json"
    split_manifest_path.write_text(json.dumps(split_manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "rows_total": len(rows),
                "num_shards": num_shards,
                "split_manifest": str(split_manifest_path),
                "shard_manifest_dir": str(shard_manifest_dir),
            },
            indent=2,
        )
    )


def _merge_shards(args: argparse.Namespace) -> None:
    split_manifest_path = Path(args.split_manifest)
    split_manifest = _load_json(split_manifest_path)

    source_manifest_path = Path(split_manifest["source_state_manifest"])
    source_rows = _read_jsonl(source_manifest_path)
    source_order = [str(r["state_id"]) for r in source_rows]
    state_to_index = {sid: idx for idx, sid in enumerate(source_order)}

    shard_root = Path(args.shard_run_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    allow_missing = bool(args.allow_missing_shards)
    labels_filename = str(args.labels_filename)
    manifest_filename = str(args.manifest_filename)

    merged_by_state: dict[str, dict[str, Any]] = {}
    missing_shards: list[str] = []
    duplicate_states: list[str] = []
    unknown_states: list[str] = []
    per_shard_summary: list[dict[str, Any]] = []

    for shard in split_manifest.get("shards", []):
        shard_name = str(shard["shard_name"])
        run_dir = shard_root / shard_name
        labels_path = run_dir / labels_filename
        gen_manifest_path = run_dir / manifest_filename

        expected_state_ids = list(shard.get("state_ids", []))

        if not labels_path.exists():
            missing_shards.append(shard_name)
            per_shard_summary.append(
                {
                    "shard_name": shard_name,
                    "status": "missing_labels",
                    "run_dir": str(run_dir),
                    "labels_path": str(labels_path),
                }
            )
            continue

        shard_rows = _read_jsonl(labels_path)
        shard_seen: set[str] = set()
        for row in shard_rows:
            state_id = str(row.get("state_id", ""))
            if not state_id:
                continue
            if state_id in merged_by_state:
                duplicate_states.append(state_id)
                continue
            if state_id not in state_to_index:
                unknown_states.append(state_id)
                continue
            merged_by_state[state_id] = row
            shard_seen.add(state_id)

        missing_from_shard = sorted(set(expected_state_ids) - shard_seen)
        shard_manifest_payload: dict[str, Any] = {}
        if gen_manifest_path.exists():
            shard_manifest_payload = _load_json(gen_manifest_path)

        per_shard_summary.append(
            {
                "shard_name": shard_name,
                "status": "ok",
                "run_dir": str(run_dir),
                "labels_path": str(labels_path),
                "generator_manifest_path": str(gen_manifest_path),
                "rows_read": len(shard_rows),
                "rows_expected": len(expected_state_ids),
                "missing_expected_state_ids": missing_from_shard,
                "generator_manifest": shard_manifest_payload,
            }
        )

    merged_rows: list[dict[str, Any]] = []
    missing_states: list[str] = []
    for state_id in source_order:
        row = merged_by_state.get(state_id)
        if row is None:
            missing_states.append(state_id)
            continue
        merged_rows.append(row)

    merged_labels_path = output_dir / "oracle_stop_vs_act_labels.jsonl"
    _write_jsonl(merged_labels_path, merged_rows)

    merge_report = {
        "tool": "oracle_label_pilot_sharding_v1",
        "split_manifest": str(split_manifest_path.resolve()),
        "source_manifest": str(source_manifest_path.resolve()),
        "source_rows": len(source_rows),
        "merged_rows": len(merged_rows),
        "missing_shards": missing_shards,
        "missing_states": missing_states,
        "duplicate_states": sorted(set(duplicate_states)),
        "unknown_states": sorted(set(unknown_states)),
        "allow_missing_shards": allow_missing,
        "per_shard_summary": per_shard_summary,
        "merged_labels_path": str(merged_labels_path),
    }

    merged_manifest_path = output_dir / "oracle_label_manifest.json"
    merged_manifest_path.write_text(json.dumps(merge_report, indent=2), encoding="utf-8")

    print(json.dumps(merge_report, indent=2))

    hard_failure = bool(duplicate_states or unknown_states)
    if allow_missing:
        if hard_failure:
            raise SystemExit(2)
        return

    if missing_shards or missing_states or hard_failure:
        raise SystemExit(2)


def main() -> None:
    args = _parse_args()
    if args.cmd == "split":
        _split_manifest(args)
        return
    if args.cmd == "merge":
        _merge_shards(args)
        return
    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    main()
