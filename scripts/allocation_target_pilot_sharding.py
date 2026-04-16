#!/usr/bin/env python3
"""Deterministic sharding + merge utility for allocation target artifacts.

Split mode: deterministic state-manifest sharding.
Merge mode: merges per-shard outside/pairwise label outputs with manifest-order checks.
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
    p = argparse.ArgumentParser(description="Shard and merge allocation target artifacts")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_split = sub.add_parser("split")
    p_split.add_argument("--state-manifest", required=True)
    p_split.add_argument("--output-dir", required=True)
    p_split.add_argument("--num-shards", type=int, required=True)
    p_split.add_argument("--shard-prefix", default="shard")

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("--split-manifest", required=True)
    p_merge.add_argument("--shard-run-root", required=True)
    p_merge.add_argument("--output-dir", required=True)
    p_merge.add_argument("--outside-filename", default="outside_allocation_labels.jsonl")
    p_merge.add_argument("--pairwise-filename", default="pairwise_allocation_labels.jsonl")
    p_merge.add_argument("--manifest-filename", default="allocation_label_manifest.json")
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
        shards_meta.append({
            "shard_id": shard_id,
            "shard_name": shard_name,
            "manifest_path": str(shard_path),
            "rows": len(shard_rows[shard_id]),
            "first_state_id": shard_state_ids[shard_id][0] if shard_state_ids[shard_id] else None,
            "last_state_id": shard_state_ids[shard_id][-1] if shard_state_ids[shard_id] else None,
            "state_ids": shard_state_ids[shard_id],
        })

    split_manifest = {
        "tool": "allocation_target_pilot_sharding_v1",
        "split_strategy": "stable_round_robin_by_manifest_row_index",
        "source_state_manifest": str(manifest_path.resolve()),
        "source_state_manifest_sha256": _sha256_file(manifest_path),
        "rows_total": len(rows),
        "num_shards": num_shards,
        "shard_prefix": args.shard_prefix,
        "shards": shards_meta,
    }
    split_manifest_path = out_dir / "shard_split_manifest.json"
    split_manifest_path.write_text(json.dumps(split_manifest, indent=2), encoding="utf-8")
    print(json.dumps({"rows_total": len(rows), "num_shards": num_shards, "split_manifest": str(split_manifest_path)}, indent=2))


def _merge(args: argparse.Namespace) -> None:
    split_manifest_path = Path(args.split_manifest)
    split_manifest = _load_json(split_manifest_path)
    source_manifest_path = Path(split_manifest["source_state_manifest"])
    source_rows = _read_jsonl(source_manifest_path)
    source_order = [str(r["state_id"]) for r in source_rows]
    state_to_index = {sid: idx for idx, sid in enumerate(source_order)}

    shard_root = Path(args.shard_run_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    outside_by_state: dict[str, dict[str, Any]] = {}
    pairwise_rows: list[dict[str, Any]] = []
    missing_shards: list[str] = []
    duplicate_outside_state_ids: list[str] = []
    unknown_outside_state_ids: list[str] = []
    duplicate_pair_keys: list[str] = []
    unknown_pair_anchor_states: list[str] = []
    pair_seen_keys: set[str] = set()
    per_shard_summary: list[dict[str, Any]] = []

    for shard in split_manifest.get("shards", []):
        shard_name = str(shard["shard_name"])
        run_dir = shard_root / shard_name
        outside_path = run_dir / str(args.outside_filename)
        pairwise_path = run_dir / str(args.pairwise_filename)
        manifest_path = run_dir / str(args.manifest_filename)
        expected_state_ids = [str(x) for x in shard.get("state_ids", [])]

        if not outside_path.exists() or not pairwise_path.exists():
            missing_shards.append(shard_name)
            per_shard_summary.append({"shard_name": shard_name, "status": "missing_artifacts", "run_dir": str(run_dir)})
            continue

        outside_rows = _read_jsonl(outside_path)
        shard_seen_outside: set[str] = set()
        for row in outside_rows:
            sid = str(row.get("state_id", ""))
            if not sid:
                continue
            if sid in outside_by_state:
                duplicate_outside_state_ids.append(sid)
                continue
            if sid not in state_to_index:
                unknown_outside_state_ids.append(sid)
                continue
            outside_by_state[sid] = row
            shard_seen_outside.add(sid)

        local_pair_rows = _read_jsonl(pairwise_path)
        for row in local_pair_rows:
            anchor = str(row.get("anchor_state_id", ""))
            a = str(row.get("branch_a_id", ""))
            b = str(row.get("branch_b_id", ""))
            if not anchor:
                continue
            if anchor not in state_to_index:
                unknown_pair_anchor_states.append(anchor)
                continue
            k = f"{anchor}|{a}|{b}"
            if k in pair_seen_keys:
                duplicate_pair_keys.append(k)
                continue
            pair_seen_keys.add(k)
            pairwise_rows.append(row)

        per_shard_summary.append({
            "shard_name": shard_name,
            "status": "ok",
            "rows_expected": len(expected_state_ids),
            "outside_rows_read": len(outside_rows),
            "pairwise_rows_read": len(local_pair_rows),
            "missing_expected_outside_state_ids": sorted(set(expected_state_ids) - shard_seen_outside),
            "generator_manifest_path": str(manifest_path),
            "generator_manifest_present": manifest_path.exists(),
        })

    merged_outside_rows: list[dict[str, Any]] = []
    missing_outside_states: list[str] = []
    for sid in source_order:
        row = outside_by_state.get(sid)
        if row is None:
            missing_outside_states.append(sid)
            continue
        merged_outside_rows.append(row)

    merged_outside_path = output_dir / "outside_allocation_labels.jsonl"
    merged_pairwise_path = output_dir / "pairwise_allocation_labels.jsonl"
    _write_jsonl(merged_outside_path, merged_outside_rows)
    _write_jsonl(merged_pairwise_path, pairwise_rows)

    merge_report = {
        "tool": "allocation_target_pilot_sharding_v1",
        "split_manifest": str(split_manifest_path.resolve()),
        "source_manifest": str(source_manifest_path.resolve()),
        "source_rows": len(source_rows),
        "merged_outside_rows": len(merged_outside_rows),
        "merged_pairwise_rows": len(pairwise_rows),
        "missing_shards": missing_shards,
        "missing_outside_states": missing_outside_states,
        "duplicate_outside_state_ids": sorted(set(duplicate_outside_state_ids)),
        "unknown_outside_state_ids": sorted(set(unknown_outside_state_ids)),
        "duplicate_pair_keys": sorted(set(duplicate_pair_keys)),
        "unknown_pair_anchor_states": sorted(set(unknown_pair_anchor_states)),
        "allow_missing_shards": bool(args.allow_missing_shards),
        "per_shard_summary": per_shard_summary,
        "merged_outside_labels_path": str(merged_outside_path),
        "merged_pairwise_labels_path": str(merged_pairwise_path),
    }
    merged_manifest_path = output_dir / "allocation_label_manifest.json"
    merged_manifest_path.write_text(json.dumps(merge_report, indent=2), encoding="utf-8")
    print(json.dumps(merge_report, indent=2))

    hard_failure = bool(duplicate_outside_state_ids or unknown_outside_state_ids or duplicate_pair_keys or unknown_pair_anchor_states)
    if args.allow_missing_shards:
        if hard_failure:
            raise SystemExit(2)
        return
    if missing_shards or missing_outside_states or hard_failure:
        raise SystemExit(2)


def main() -> None:
    args = _parse_args()
    if args.cmd == "split":
        _split_manifest(args)
        return
    if args.cmd == "merge":
        _merge(args)
        return
    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    main()
