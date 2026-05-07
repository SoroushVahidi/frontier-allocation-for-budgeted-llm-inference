"""Schema validation for present-not-selected replay fixtures (no runtime policy tests)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "present_not_selected_replay"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"

REQUIRED_KEYS = (
    "schema_version",
    "case_id",
    "question",
    "gold_answer",
    "current_pal_answer",
    "current_pal_correct",
    "external_correctness",
    "mechanism_label",
    "failure_stage",
    "replay_feasibility",
    "current_selected_source",
    "overlay_tiebreak_summary",
    "answer_group_histogram",
    "selector_candidate_pool_summary",
    "pal_execution_summary",
    "retry_summary",
    "expected_counterfactual_notes",
    "guardrail_or_target_role",
    "source_artifact_paths",
)

FORBIDDEN_KEY_NAMES = frozenset(
    {
        "action_trace",
        "final_nodes",
        "final_branch_states",
        "trace_steps",
        "reasoning_text",
        "full_action_trace",
    }
)

MAX_STRING_CHARS = 2500
MAX_FIXTURE_BYTES = 24_000


def _iter_json_values(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _iter_json_values(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _iter_json_values(x)
    elif isinstance(obj, str):
        yield obj


def _collect_keys(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            yield path, k
            yield from _collect_keys(v, path)
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            yield from _collect_keys(x, f"{prefix}[{i}]")


def _load_manifest():
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data.get("schema_version") == "1.0"
    return data


def _fixture_json_paths():
    return sorted(p for p in FIXTURE_DIR.glob("openai_gsm8k_*.json") if p.is_file())


def test_manifest_lists_fixture_files():
    manifest = _load_manifest()
    ids = manifest["fixture_case_ids"]
    paths = _fixture_json_paths()
    assert len(paths) == len(ids)
    for cid in ids:
        fp = FIXTURE_DIR / f"{cid}.json"
        assert fp.is_file(), f"missing fixture for {cid}"


def test_fixture_case_ids_unique():
    paths = _fixture_json_paths()
    seen = []
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        seen.append(data["case_id"])
    assert len(seen) == len(set(seen))


@pytest.mark.parametrize("fixture_path", _fixture_json_paths(), ids=lambda p: p.name)
def test_fixture_schema_and_size(fixture_path: Path):
    raw = fixture_path.read_bytes()
    assert len(raw) <= MAX_FIXTURE_BYTES, f"{fixture_path.name} exceeds size cap"

    data = json.loads(raw.decode("utf-8"))
    for key in REQUIRED_KEYS:
        assert key in data, f"{fixture_path.name} missing {key}"

    assert data["schema_version"] == "1.0"
    assert data["guardrail_or_target_role"] == "target_diagnostic_anchor"
    assert data["current_pal_correct"] is False

    mech = data["mechanism_label"]
    assert isinstance(mech, str) and len(mech.strip()) > 0

    sap = data["source_artifact_paths"]
    assert isinstance(sap, dict) and len(sap) >= 3
    for v in sap.values():
        assert isinstance(v, str) and len(v) > 0

    for path, key_name in _collect_keys(data):
        assert key_name not in FORBIDDEN_KEY_NAMES, f"forbidden key {path}"

    for s in _iter_json_values(data):
        if isinstance(s, str):
            assert len(s) <= MAX_STRING_CHARS, f"long string in {fixture_path.name}"

    manifest = _load_manifest()
    assert data["case_id"] in manifest["fixture_case_ids"]


def test_manifest_required_fields():
    m = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for k in (
        "schema_version",
        "created_at",
        "purpose",
        "source_bundle_path",
        "replay_report_path",
        "fixture_case_ids",
        "warnings",
    ):
        assert k in m
    assert "no_gold_at_runtime" in (m.get("warnings") or {})
