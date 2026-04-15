#!/usr/bin/env python3
"""Stub CLI for the heavy oracle-label generator interface.

This script defines and checks the expected generator contract used by the HPC wrapper.
It does NOT implement heavy oracle rollouts.

Behavior:
- Without --mock-mode: validates inputs, prints guidance, exits non-zero.
- With --mock-mode: writes clearly-labeled mock/testing artifacts for interface wiring tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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


def _stable_unit_float(key: str) -> float:
    dig = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(dig[:12], 16) / float(16**12)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stub heavy oracle-label generator interface")
    p.add_argument("--pilot-config", default="configs/stop_vs_act_oracle_label_pilot_v1.json")
    p.add_argument("--state-manifest", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--teacher-mode", default="")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-states", type=int, default=0, help="Optional cap for testing (0 means all)")
    p.add_argument("--mock-mode", action="store_true", help="Write mock interface-testing outputs (NOT real oracle labels)")
    p.add_argument("--labels-out", default="")
    p.add_argument("--manifest-out", default="")
    return p.parse_args()


def _check_config_and_manifest(pilot_cfg: dict[str, Any], rows: list[dict[str, Any]], teacher_mode_override: str) -> list[str]:
    errs: list[str] = []

    teacher = pilot_cfg.get("teacher", {})
    expected_mode = str(teacher.get("teacher_mode", "")).strip()
    if expected_mode == "":
        errs.append("pilot config missing teacher.teacher_mode")

    if teacher_mode_override and expected_mode and teacher_mode_override != expected_mode:
        errs.append(
            f"--teacher-mode ({teacher_mode_override}) does not match config teacher_mode ({expected_mode})"
        )

    if len(rows) == 0:
        errs.append("state manifest has zero rows")

    required_manifest_fields = ["state_id", "budget", "remaining_budget", "current_branch_id"]
    missing_count = 0
    for r in rows[:50]:
        if any(k not in r for k in required_manifest_fields):
            missing_count += 1
    if missing_count > 0:
        errs.append(
            "state manifest missing required fields on sampled rows: "
            + ", ".join(required_manifest_fields)
        )

    return errs


def _finite(v: float) -> float:
    if not math.isfinite(v):
        raise ValueError("non-finite value generated in mock mode")
    return v


def _build_mock_rows(rows: list[dict[str, Any]], pilot_cfg: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    teacher = pilot_cfg.get("teacher", {})
    teacher_mode = str(teacher.get("teacher_mode", "unknown_teacher_mode"))
    horizon = int(teacher.get("horizon", 0))
    depth = int(teacher.get("rollout_depth", 0))

    mock_rows: list[dict[str, Any]] = []
    for idx, r in enumerate(rows):
        state_id = str(r.get("state_id", f"missing_state_{idx}"))
        key = f"{seed}|{state_id}|{idx}"

        # Tiny deterministic synthetic values for interface testing only.
        q_stop = _finite((_stable_unit_float(key + "|stop") - 0.5) * 0.20)
        delta = _finite((_stable_unit_float(key + "|delta") - 0.5) * 0.30)
        q_act = _finite(q_stop + delta)
        gap = _finite(q_act - q_stop)
        label = 1 if gap > 0 else 0

        row = {
            "state_id": state_id,
            "example_id": str(r.get("episode_id", state_id)),
            "budget": int(r.get("budget", 0)),
            "remaining_budget": int(r.get("remaining_budget", 0)),
            "current_branch_id": str(r.get("current_branch_id", "unknown_branch")),
            "q_act": q_act,
            "q_stop": q_stop,
            "oracle_action_gap": gap,
            "oracle_label_act": label,
            "horizon": horizon,
            "rollout_depth": depth,
            "teacher_mode": teacher_mode,
            "paired_randomness_used": True,
            "mock_interface_only": True,
            "non_oracle_warning": "MOCK_INTERFACE_OUTPUT_ONLY_NOT_REAL_ORACLE_LABEL",
            "mock_source": "run_oracle_label_generator_interface_stub.py",
        }
        mock_rows.append(row)

    return mock_rows


def main() -> None:
    args = parse_args()

    pilot_cfg_path = Path(args.pilot_config)
    manifest_path = Path(args.state_manifest)
    output_dir = Path(args.output_dir)

    if not pilot_cfg_path.exists():
        raise SystemExit(f"Missing --pilot-config: {pilot_cfg_path}")
    if not manifest_path.exists():
        raise SystemExit(f"Missing --state-manifest: {manifest_path}")

    pilot_cfg = _load_json(pilot_cfg_path)
    manifest_rows = _read_jsonl(manifest_path)

    if args.max_states > 0:
        manifest_rows = manifest_rows[: int(args.max_states)]

    errs = _check_config_and_manifest(pilot_cfg, manifest_rows, args.teacher_mode)
    if errs:
        for e in errs:
            print(f"INTERFACE_ERROR: {e}")
        raise SystemExit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    labels_path = Path(args.labels_out) if args.labels_out else output_dir / "oracle_stop_vs_act_labels.jsonl"
    run_manifest_path = Path(args.manifest_out) if args.manifest_out else output_dir / "oracle_label_manifest.json"

    if not args.mock_mode:
        print("Heavy oracle-label generation is NOT implemented in this stub.")
        print("Interface prechecks passed.")
        print("To test wiring only, re-run with --mock-mode.")
        print("Important: mock mode is testing-only and must not be treated as real oracle labels.")
        raise SystemExit(3)

    mock_rows = _build_mock_rows(manifest_rows, pilot_cfg, seed=int(args.seed))
    with labels_path.open("w", encoding="utf-8") as f:
        for row in mock_rows:
            f.write(json.dumps(row) + "\n")

    run_manifest = {
        "pilot_name": pilot_cfg.get("pilot_name"),
        "generator_contract": "oracle_label_generator_interface_v1",
        "generator_impl": "stub_interface_only",
        "mock_mode": True,
        "non_oracle_warning": "MOCK_INTERFACE_OUTPUT_ONLY_NOT_REAL_ORACLE_LABEL",
        "heavy_oracle_generation_performed": False,
        "state_manifest_path": str(manifest_path),
        "pilot_config_path": str(pilot_cfg_path),
        "labels_path": str(labels_path),
        "rows_written": len(mock_rows),
        "seed": int(args.seed),
        "teacher_mode": str(pilot_cfg.get("teacher", {}).get("teacher_mode", "")),
        "horizon": int(pilot_cfg.get("teacher", {}).get("horizon", 0)),
        "rollout_depth": int(pilot_cfg.get("teacher", {}).get("rollout_depth", 0)),
    }
    run_manifest_path.write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")

    diagnostics_path = output_dir / "oracle_label_mock_diagnostics.json"
    diagnostics = {
        "mock_mode": True,
        "non_oracle_warning": "MOCK_INTERFACE_OUTPUT_ONLY_NOT_REAL_ORACLE_LABEL",
        "rows_with_mock_flag": sum(1 for r in mock_rows if r.get("mock_interface_only") is True),
        "rows": len(mock_rows),
    }
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")

    print(json.dumps({"status": "mock_outputs_written", "labels": str(labels_path), "manifest": str(run_manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
