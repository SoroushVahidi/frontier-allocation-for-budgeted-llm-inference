from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path
import subprocess

from experiments.adaptive_retry_router import compute_adaptive_retry_features, should_trigger_discovery3_diversity_retry
from experiments.final_target_verifier import final_target_verifier_features, select_with_final_target_verifier_v1
from experiments.targeted_discovery_retry import (
    build_discovery3_candidate_diversity_prompt,
    build_discovery3_patch_metadata,
)

REPO = Path(__file__).resolve().parents[1]


def test_prompt_builder_signature_is_gold_free() -> None:
    sig = inspect.signature(build_discovery3_candidate_diversity_prompt)
    assert "gold" not in sig.parameters
    assert "prediction" not in sig.parameters


def test_prompt_builder_includes_required_instructions() -> None:
    prompt = build_discovery3_candidate_diversity_prompt(
        "A tank has 100 liters. After using 35 liters and adding 12 liters, how much remains?",
        target_quantity_type="remaining",
        family_hint="state_update",
    )
    pl = prompt.lower()
    assert "identify the exact requested final quantity" in pl
    assert "decompose into concise equations" in pl
    assert "FINAL_ANSWER:" in prompt
    assert "Do not put units or words after the number on the FINAL_ANSWER line." in prompt
    assert "Do not give multiple final answers." in prompt
    assert "If the answer is a fraction or decimal, put only that value." in prompt


def test_router_trigger_fires_for_state_ratio_entity_value() -> None:
    text = "After day 1 and then day 2, each worker gets twice as many units. How many units now?"
    rf = compute_adaptive_retry_features(text)
    vf = final_target_verifier_features(text)
    assert should_trigger_discovery3_diversity_retry(
        text,
        rf,
        vf,
        {"target_quantity_type": "entity_value", "reasoning_family_guess": "state_update", "high_disagreement": True},
    )


def test_percent_base_disabled_by_default() -> None:
    text = "A battery loses 9% each hour for 5 hours. What is remaining?"
    rf = compute_adaptive_retry_features(text)
    vf = final_target_verifier_features(text)
    assert should_trigger_discovery3_diversity_retry(
        text,
        rf,
        vf,
        {"target_quantity_type": "remaining", "reasoning_family_guess": "unknown", "high_disagreement": False},
    ) is False


def test_selection_verifier_prefers_target_compatible_candidate() -> None:
    problem = "A and B together have 30. A has 18. How many more does A have than B?"
    vf = final_target_verifier_features(problem)
    md: dict[str, object] = {}
    out = select_with_final_target_verifier_v1(
        [
            {"answer": "30", "source": "our_candidate", "target_quantity_type": "total", "confidence": 0.9},
            {"answer": "6", "source": "retry_candidate", "target_quantity_type": "difference", "confidence": 0.6},
        ],
        problem,
        vf,
        md,
    )
    assert out["selected_answer"] == "6"
    assert out["selected_source"] == "retry_candidate"
    assert md["discovery3_selection_policy_applied"] is True
    assert "discovery3_selection_reason" in md


def test_patch_metadata_fields_exist() -> None:
    md = build_discovery3_patch_metadata(
        patch_enabled=True,
        retry_triggered=True,
        selected_scaffold="state_transition_consistency",
        selection_policy_applied=True,
        selection_reason="target_compatible_candidate_preferred",
        extra_calls_planned=1,
    )
    required = {
        "discovery3_patch_enabled",
        "discovery3_diversity_retry_triggered",
        "discovery3_selected_scaffold",
        "discovery3_selection_policy_applied",
        "discovery3_selection_reason",
        "discovery3_extra_calls_planned",
        "discovery3_extra_calls_used",
    }
    assert required.issubset(md.keys())


def test_dry_run_materialization_creates_15_cases_and_no_leakage(tmp_path: Path) -> None:
    design_dir = tmp_path / "design"
    dry_dir = tmp_path / "dry"
    cmd = [
        "python3",
        str(REPO / "scripts/materialize_discovery3_candidate_diversity_selection_v1.py"),
        "--design-output-dir",
        str(design_dir),
        "--dry-run-output-dir",
        str(dry_dir),
    ]
    subprocess.check_call(cmd, cwd=str(REPO))

    rows = list(csv.DictReader((dry_dir / "confirmation_cases.csv").open(encoding="utf-8")))
    assert len(rows) == 15
    manifest = json.loads((dry_dir / "dry_run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["no_api_calls"] is True
    assert manifest["planned_extra_calls"] <= 15
    assert manifest["no_gold_in_prompts_verified"] is True
    assert manifest["no_prediction_leakage_verified"] is True
    for r in rows:
        meta = json.loads(r["metadata_json"])
        assert "discovery3_patch_enabled" in meta
        prompt_path = REPO / r["prompt_path"] if not Path(r["prompt_path"]).is_absolute() else Path(r["prompt_path"])
        prompt_text = prompt_path.read_text(encoding="utf-8")
        assert "FINAL_ANSWER:" in prompt_text
