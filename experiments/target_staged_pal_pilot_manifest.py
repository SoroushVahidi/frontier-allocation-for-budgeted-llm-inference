"""Load and validate deployable target-staged PAL retry pilot manifests (offline only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.target_staged_pal_prompt import (
    DEPLOYABLE_VARIANTS,
    NON_DEPLOYABLE_VARIANTS,
    VARIANT_C,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

PRIMARY_PILOT_MANIFEST_PATH = (
    REPO_ROOT / "manifests" / "target_staged_pal_retry_primary_11_20260507.json"
)

EXPECTED_PRIMARY_CASE_IDS: tuple[str, ...] = (
    "openai_gsm8k_1099",
    "openai_gsm8k_1125",
    "openai_gsm8k_1155",
    "openai_gsm8k_1166",
    "openai_gsm8k_1187",
    "openai_gsm8k_1198",
    "openai_gsm8k_1215",
    "openai_gsm8k_1230",
    "openai_gsm8k_1244",
    "openai_gsm8k_1248",
    "openai_gsm8k_1281",
)


def load_primary_pilot_manifest() -> dict[str, Any]:
    return json.loads(PRIMARY_PILOT_MANIFEST_PATH.read_text(encoding="utf-8"))


def validate_pilot_manifest_structure(manifest: dict[str, Any]) -> None:
    """Shared structural checks for primary-11 deployable pilot (API flag not checked)."""
    if manifest.get("hard_logical_call_cap") != 120:
        raise ValueError("hard_logical_call_cap must be 120 for this pilot contract")
    if manifest.get("primary_case_count") != 11:
        raise ValueError("primary_case_count must be 11")
    allowed = frozenset(manifest.get("allowed_deployable_template_variants") or [])
    if not allowed.issubset(DEPLOYABLE_VARIANTS):
        raise ValueError("allowed_deployable_template_variants must be deployable only")
    if allowed & NON_DEPLOYABLE_VARIANTS:
        raise ValueError("non-deployable variants cannot appear in allowed list")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 11:
        raise ValueError("manifest must contain exactly 11 cases")
    per = int(manifest.get("per_case_budget") or 0)
    hard = int(manifest.get("hard_logical_call_cap") or 0)
    if per * len(cases) > hard:
        raise ValueError("planned per_case_budget * case count exceeds hard_logical_call_cap")
    ids: list[str] = []
    for i, row in enumerate(cases):
        if not isinstance(row, dict):
            raise ValueError(f"case {i} must be an object")
        cid = str(row.get("source_case_id") or "")
        if not cid:
            raise ValueError(f"case {i} missing source_case_id")
        ids.append(cid)
        if row.get("deployable") is not True:
            raise ValueError(f"case {cid} must have deployable: true")
        tv = str(row.get("template_variant") or "")
        if tv in NON_DEPLOYABLE_VARIANTS:
            raise ValueError(f"case {cid} uses non-deployable template {tv!r}")
        if tv not in DEPLOYABLE_VARIANTS:
            raise ValueError(f"case {cid} has unknown or unsupported template {tv!r}")
        if tv not in allowed:
            raise ValueError(f"case {cid} template {tv!r} not in allowed_deployable_template_variants")
        for k in ("required_schemas", "pal_failure_modes"):
            if k not in row or not str(row.get(k) or "").strip():
                raise ValueError(f"case {cid} missing {k}")
    if len(set(ids)) != 11:
        raise ValueError("duplicate or missing source_case_id entries")
    if tuple(sorted(ids)) != tuple(sorted(EXPECTED_PRIMARY_CASE_IDS)):
        raise ValueError("case ID set does not match expected primary 11 pilot list")


def validate_deployable_pilot_manifest(manifest: dict[str, Any]) -> None:
    """Raise ValueError if manifest violates deployable **offline** pilot constraints."""
    validate_pilot_manifest_structure(manifest)
    if manifest.get("api_execution_enabled") is not False:
        raise ValueError("api_execution_enabled must be false for offline manifest validation")


def assert_oracle_variant_rejected_for_pilot(template_variant: str) -> None:
    if template_variant in NON_DEPLOYABLE_VARIANTS:
        raise ValueError(f"{template_variant!r} cannot be used in a deployable pilot manifest")
