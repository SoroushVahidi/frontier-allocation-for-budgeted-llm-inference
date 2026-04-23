#!/usr/bin/env python3
"""Generate a canonical external-baseline fairness + integration package for four target papers."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BaselineRecord:
    baseline_id: str
    paper_title: str
    source_url: str
    source_url_2: str
    current_repo_presence_status: str
    evidence_paths: str
    current_taxonomy_class: str
    control_primitive: str
    budget_unit: str
    allowed_actions: str
    counted_compute: str
    uncounted_compute: str
    controller_overhead_policy: str
    offline_calibration_training_budget_policy: str
    backbone_model: str
    prompt_template: str
    decoding_settings: str
    sampling_settings: str
    verifier_usage: str
    reward_model_usage: str
    answer_extraction_rule: str
    final_aggregation_rule: str
    stopping_rule: str
    success_metric: str
    dataset_eligibility: str
    fairness_eligibility_tier: str
    downgrade_reason: str
    must_hold_fixed: str
    unfair_if: str
    placement: str
    exact_next_implementation_step_required: str


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "outputs" / f"canonical_external_baseline_fairness_checklist_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [
        BaselineRecord(
            baseline_id="zhai_constrained_budget_selector",
            paper_title="Adaptive Test-Time Compute Allocation for Reasoning LLMs via Constrained Policy Optimization",
            source_url="https://arxiv.org/abs/2604.14853",
            source_url_2="",
            current_repo_presence_status="not_present",
            evidence_paths="",
            current_taxonomy_class="not_registered_yet",
            control_primitive="constrained_policy_optimization_for_adaptive_attempt_allocation",
            budget_unit="must_be_normalized_to_repo_attempt_or_token_budget_contract",
            allowed_actions="allocate_next_attempt_or_stop_under_global_budget",
            counted_compute="all_generation_attempts_plus_any_verifier_or_controller_calls_under_shared_contract",
            uncounted_compute="none_by_default_except_dataset_io_and_static_prompt_loading",
            controller_overhead_policy="count_controller_overhead_or_calibrate_to_zero-overhead proxy consistently across all methods",
            offline_calibration_training_budget_policy="must_declare_and amortize any offline policy optimization cost; otherwise downgrade",
            backbone_model="must_match_canonical_matched_surface_backbone",
            prompt_template="must_match_shared_template",
            decoding_settings="must_match_shared_decoding",
            sampling_settings="must_match_shared_temperature_top_p_seed_policy",
            verifier_usage="only_if_shared_verifier_lane_enabled_for_all_methods",
            reward_model_usage="forbidden_unless_shared_across_all_methods",
            answer_extraction_rule="must_match_repo_canonical_answer_extraction",
            final_aggregation_rule="must_match_shared_finalization_rule",
            stopping_rule="budget_exhaustion_or_solved_under_shared_contract",
            success_metric="same_endpoint_accuracy_or_coverage_metric_as_main_surface",
            dataset_eligibility="eligible_after_contract_instantiation_and_audited_runner",
            fairness_eligibility_tier="candidate_main_table_cleanest_target",
            downgrade_reason="currently_not_present_in_registry_docs_or_runners",
            must_hold_fixed="backbone prompt decoding sampling answer extraction final selection metric",
            unfair_if="changes stack beyond allocation or uses asymmetric overhead/training budget",
            placement="main_table_candidate_after_contract_and_runner",
            exact_next_implementation_step_required="add baseline registry entry + contract config + audited runner on canonical matched surface",
        ),
        BaselineRecord(
            baseline_id="dipa_difficulty_proxy_allocator",
            paper_title="Adaptive Test-Time Compute Allocation via Training-Free Difficulty Proxies",
            source_url="https://openreview.net/forum?id=ztGHhyicWs",
            source_url_2="https://openreview.net/pdf?id=ztGHhyicWs",
            current_repo_presence_status="already_present_partial",
            evidence_paths=(
                "external/training_free_difficulty_proxies/README.md | "
                "docs/training_free_difficulty_proxies_integration.md | "
                "configs/training_free_difficulty_proxies_mode_a_v1.json | "
                "scripts/run_training_free_difficulty_proxies_mode_a.py | "
                "docs/external_baseline_paper_readiness_decision_matrix.csv"
            ),
            current_taxonomy_class="official_paper_record_discuss_only_plus_mode_a_adapter_based_adjacent",
            control_primitive="query_level_difficulty_proxy_based_allocation_over_unsolved_instances",
            budget_unit="per_attempt_global_budget_over_batch",
            allowed_actions="choose_next_unsolved_instance_for_new_attempt_or_stop_when_budget_exhausted",
            counted_compute="all_attempts_and_any_auxiliary_scoring_calls",
            uncounted_compute="dataset_io_and_static_feature_prep_only",
            controller_overhead_policy="must_count_proxy_scoring_if_nontrivial_or justify negligible constant cost",
            offline_calibration_training_budget_policy="training_free_required_for_main-table lane; any fitting/calibration must be disclosed",
            backbone_model="must_match_shared_backbone",
            prompt_template="must_match_shared_template",
            decoding_settings="must_match_shared_decoding",
            sampling_settings="must_match_shared_sampling",
            verifier_usage="none_unless symmetric verifier lane for all",
            reward_model_usage="none",
            answer_extraction_rule="must_match_shared extraction",
            final_aggregation_rule="per_item first correct or fixed final-attempt rule under common contract",
            stopping_rule="success or budget exhaustion",
            success_metric="same matched-surface metric",
            dataset_eligibility="main_table_only_for_verifiable_tasks_with_compatible per-attempt accounting",
            fairness_eligibility_tier="conditional_main_table",
            downgrade_reason="official code unverified and current repo lane is paper-inspired adapter",
            must_hold_fixed="per-attempt contract backbone prompt decoding extraction finalization",
            unfair_if="different answer extraction finalization or hidden proxy/controller cost",
            placement="main_table_conditional_else_appendix",
            exact_next_implementation_step_required="publish explicit per-attempt/verifiable-task contract and rerun audited multi-seed adapter under that contract",
        ),
        BaselineRecord(
            baseline_id="compute_optimal_tts",
            paper_title="Scaling LLM Test-Time Compute Optimally Can Be More Effective than Scaling Model Parameters",
            source_url="https://openreview.net/forum?id=4FWAwZtd2n",
            source_url_2="https://arxiv.org/abs/2408.03314",
            current_repo_presence_status="already_present_blocked",
            evidence_paths=(
                "external/compute_optimal_tts/README.md | "
                "docs/compute_optimal_tts_integration.md | "
                "outputs/external_baseline_completeness/compute_optimal_tts_status.json | "
                "outputs/external_baseline_completeness/compute_optimal_tts_provenance_check.json | "
                "configs/external_baselines_registry.json"
            ),
            current_taxonomy_class="blocked_adjacent",
            control_primitive="compute_scaling_policy_over_sample_count_or_deliberation_depth",
            budget_unit="paper_specific_test-time_compute proxy requiring normalization",
            allowed_actions="scale attempts/depth/compute schedule",
            counted_compute="must be normalized to same counted budget object",
            uncounted_compute="none beyond shared exclusions",
            controller_overhead_policy="must align with shared accounting before direct comparison",
            offline_calibration_training_budget_policy="must disclose tuning sweeps and offline scaling calibration",
            backbone_model="must match shared backbone for fair lane",
            prompt_template="must match shared template",
            decoding_settings="must match shared decoding",
            sampling_settings="must match shared sampling",
            verifier_usage="none unless shared",
            reward_model_usage="none unless shared",
            answer_extraction_rule="must match shared rule",
            final_aggregation_rule="must match shared aggregation",
            stopping_rule="budget schedule completion or solved",
            success_metric="same matched-surface metric",
            dataset_eligibility="appendix_only_unless_same_mechanism_family_and_accounting_are_instantiated",
            fairness_eligibility_tier="appendix_only",
            downgrade_reason="paper-repo mapping unresolved + no fair matched adapter protocol",
            must_hold_fixed="all shared surface parameters",
            unfair_if="uses non-normalized compute units or altered inference stack",
            placement="appendix_only",
            exact_next_implementation_step_required="verify official paper↔repo mapping then implement import-validated matched-accounting adapter lane",
        ),
        BaselineRecord(
            baseline_id="bilal_adaptive_ttc",
            paper_title="What If We Allocate Test-Time Compute Adaptively?",
            source_url="https://arxiv.org/abs/2602.01070",
            source_url_2="",
            current_repo_presence_status="already_present_partial",
            evidence_paths=(
                "docs/DIRECT_COMPARATOR_IMPLEMENTATION_NOTE_2602_01070.md | "
                "docs/CURRENT_STRATEGIC_UPDATE_2026_04_16.md"
            ),
            current_taxonomy_class="direct_comparator_note_only_unregistered",
            control_primitive="adaptive_allocation_with_possible_prm_tool_or_search_dependencies",
            budget_unit="paper-specific mixed compute object likely including verifier/search",
            allowed_actions="allocate compute adaptively potentially with external verifier/search modules",
            counted_compute="must include generator + verifier + tool/search overhead",
            uncounted_compute="none except shared static costs",
            controller_overhead_policy="count all controller and tool orchestration calls",
            offline_calibration_training_budget_policy="must disclose PRM/verifier training and calibration cost",
            backbone_model="must match shared backbone for fair direct lane",
            prompt_template="must match shared template",
            decoding_settings="must match shared decoding",
            sampling_settings="must match shared sampling",
            verifier_usage="likely central; only fair if genuinely shared infra",
            reward_model_usage="likely present in some variants; only fair if shared",
            answer_extraction_rule="must match shared rule",
            final_aggregation_rule="must match shared rule",
            stopping_rule="contractual budget exhaustion/success",
            success_metric="same matched-surface metric",
            dataset_eligibility="adjacent_only_until_shared prm/tool/search stack exists",
            fairness_eligibility_tier="adjacent_only",
            downgrade_reason="only paper-level note exists; no registered runner/contract/artifacts",
            must_hold_fixed="all shared surface knobs plus verifier/tool access symmetry",
            unfair_if="asymmetric verifier or tool/search access and uncounted overhead",
            placement="adjacent_only",
            exact_next_implementation_step_required="define shared PRM/tool/search infrastructure contract and add auditable adapter runner before any table eligibility upgrade",
        ),
    ]

    contract_rows = [asdict(r) for r in records]
    _write_csv(out_dir / "baseline_contract_matrix.csv", contract_rows)
    (out_dir / "baseline_contract_matrix.json").write_text(json.dumps(contract_rows, indent=2) + "\n", encoding="utf-8")

    presence_rows = [
        {
            "baseline_id": r.baseline_id,
            "paper_title": r.paper_title,
            "source_url": r.source_url,
            "current_repo_presence_status": r.current_repo_presence_status,
            "evidence_paths": r.evidence_paths,
            "current_taxonomy_class": r.current_taxonomy_class,
            "exact_next_implementation_step_required": r.exact_next_implementation_step_required,
        }
        for r in records
    ]
    _write_csv(out_dir / "baseline_presence_audit.csv", presence_rows)

    eligibility_rows = [
        {
            "baseline_id": r.baseline_id,
            "placement": r.placement,
            "fairness_eligibility_tier": r.fairness_eligibility_tier,
            "downgrade_reason": r.downgrade_reason,
            "main_table_eligible_now": "yes" if r.placement.startswith("main_table") else "no",
        }
        for r in records
    ]
    _write_csv(out_dir / "main_table_eligibility.csv", eligibility_rows)

    fairness_violations = [
        {
            "violation_code": "budget_unit_mismatch_without_normalization",
            "applies_to": "all",
            "severity": "high",
            "trigger": "budget/accounting object differs and normalization rule absent",
            "required_fix": "normalize to shared counted-compute unit",
        },
        {
            "violation_code": "answer_extraction_rule_mismatch",
            "applies_to": "all",
            "severity": "high",
            "trigger": "different extraction regex/verifier without controlled contract",
            "required_fix": "use canonical extractor or dual-reported controlled ablation",
        },
        {
            "violation_code": "uncontrolled_final_selection",
            "applies_to": "all",
            "severity": "high",
            "trigger": "final aggregation differs (e.g., best-of-n vs first-correct) without matched rule",
            "required_fix": "lock shared final aggregation contract",
        },
        {
            "violation_code": "asymmetric_verifier_or_reward_model_access",
            "applies_to": "bilal_adaptive_ttc,zhai_constrained_budget_selector",
            "severity": "high",
            "trigger": "method receives verifier/RM unavailable to others",
            "required_fix": "share identical verifier/RM stack or downgrade to adjacent-only",
        },
        {
            "violation_code": "controller_overhead_inconsistently_counted",
            "applies_to": "all",
            "severity": "medium",
            "trigger": "selector/proxy/tool overhead counted for some baselines but not others",
            "required_fix": "publish uniform overhead policy and recompute",
        },
        {
            "violation_code": "hidden_offline_calibration_cost",
            "applies_to": "zhai_constrained_budget_selector,compute_optimal_tts",
            "severity": "high",
            "trigger": "offline optimization/sweeps omitted from budget statement",
            "required_fix": "declare and amortize offline cost or mark not comparable",
        },
        {
            "violation_code": "backbone_prompt_temperature_mismatch",
            "applies_to": "all",
            "severity": "high",
            "trigger": "backbone/prompt/temperature differ across compared rows",
            "required_fix": "re-run on canonical matched surface",
        },
        {
            "violation_code": "endpoint_metric_mismatch",
            "applies_to": "all",
            "severity": "high",
            "trigger": "different success metrics across methods",
            "required_fix": "single endpoint metric contract",
        },
        {
            "violation_code": "tool_or_search_overhead_ignored",
            "applies_to": "bilal_adaptive_ttc",
            "severity": "high",
            "trigger": "search/tool calls not counted",
            "required_fix": "count all external calls in compute ledger",
        },
        {
            "violation_code": "whole_stack_change_not_just_allocator",
            "applies_to": "compute_optimal_tts,bilal_adaptive_ttc",
            "severity": "high",
            "trigger": "method modifies inference stack beyond allocation under fixed substrate",
            "required_fix": "instantiate mechanism as matched-substrate adapter or keep appendix/adjacent",
        },
    ]
    _write_csv(out_dir / "fairness_violations.csv", fairness_violations)

    normalization_rules = {
        "version": "v1",
        "canonical_counted_budget_unit": "generation_attempt_equivalent_on_shared_backbone_prompt_decoding",
        "rules": [
            "All methods must map their budget to generation_attempt_equivalent (GAE) units.",
            "Verifier/tool/reward-model invocations must be converted to GAE via fixed cost multipliers and included.",
            "Controller scoring overhead above negligible threshold must be counted.",
            "Answer extraction and final aggregation must use repository canonical rules.",
            "Any offline calibration/training must be explicitly declared and either amortized or marked non-comparable.",
        ],
        "matched_surface_requirements": {
            "backbone_model": "fixed",
            "prompt_template": "fixed",
            "decoding_settings": "fixed",
            "sampling_settings": "fixed",
            "success_metric": "fixed",
        },
    }
    (out_dir / "normalization_rules.json").write_text(json.dumps(normalization_rules, indent=2) + "\n", encoding="utf-8")

    required_infra = {
        "shared_infrastructure_version": "v1",
        "required_components": [
            "canonical matched-surface runner interface",
            "uniform compute ledger (attempts + verifier/tool/controller overhead)",
            "shared answer extraction and final aggregation module",
            "dataset eligibility manifest with verifiable-task tags",
            "multi-seed evaluation harness with fixed prompts/decoding",
            "baseline registry entries with provenance + fairness tier",
        ],
        "per_baseline_blockers": {
            "zhai_constrained_budget_selector": [
                "registry entry missing",
                "contract config missing",
                "audited runner missing",
            ],
            "dipa_difficulty_proxy_allocator": [
                "official lane remains discuss-only",
                "main-table contract needs per-attempt verifiable-task lock",
                "audited multi-seed artifact bundle missing for upgraded lane",
            ],
            "compute_optimal_tts": [
                "paper↔repo provenance unresolved",
                "matched-accounting adapter protocol missing",
            ],
            "bilal_adaptive_ttc": [
                "only note-level presence",
                "shared PRM/tool/search infra not established",
                "runner + contract + auditable outputs missing",
            ],
        },
    }
    (out_dir / "required_shared_infrastructure.json").write_text(json.dumps(required_infra, indent=2) + "\n", encoding="utf-8")

    summary_lines = [
        "# Canonical external baseline fairness checklist summary",
        "",
        f"Generated UTC timestamp: `{ts}`",
        "",
        "## Presence audit",
        "- `zhai_constrained_budget_selector`: `not_present`.",
        "- `dipa_difficulty_proxy_allocator`: `already_present_partial` (official discuss-only record + MODE A adapter lane).",
        "- `compute_optimal_tts`: `already_present_blocked`.",
        "- `bilal_adaptive_ttc`: `already_present_partial` (docs-only comparator note).",
        "",
        "## Placement conclusions",
        "- Zhai: cleanest **main-table candidate** once contract+runner are added.",
        "- DIPA: **main-table only conditionally** under per-attempt/verifiable-task matched contract; else appendix.",
        "- compute_optimal_tts: **appendix-only** unless re-instantiated under same mechanism family/accounting and provenance is verified.",
        "- Bilal: **adjacent-only** unless PRM/tool/search infrastructure is genuinely shared and counted.",
        "",
        "## Guardrail",
        "No benchmark results are fabricated in this package; this is integration/fairness scaffolding only.",
    ]
    (out_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / "docs" / f"CANONICAL_EXTERNAL_BASELINE_FAIRNESS_CHECKLIST_{ts}.md"
    doc_lines = [
        "# Canonical external baseline fairness checklist",
        "",
        f"Timestamp (UTC): `{ts}`",
        "",
        "This document is generated for reviewer-defensible external baseline integration across four specific paper targets.",
        "",
        "## Canonical conclusions",
        "1. **Zhai (2026 / arXiv:2604.14853) is the cleanest main-table target** once a matched-surface contract and runner are added.",
        "2. **DIPA (OpenReview ztGHhyicWs) is main-table only under a compatible per-attempt/verifiable-task contract**; otherwise appendix-only.",
        "3. **compute-optimal TTS (OpenReview 4FWAwZtd2n; arXiv:2408.03314) is appendix-only** unless re-instantiated under the same mechanism family and accounting with resolved provenance.",
        "4. **Bilal et al. (arXiv:2602.01070) is adjacent-only** unless PRM/tool/search infrastructure is genuinely shared and counted.",
        "",
        "## Artifact bundle",
        f"- `outputs/canonical_external_baseline_fairness_checklist_{ts}/baseline_contract_matrix.csv`",
        f"- `outputs/canonical_external_baseline_fairness_checklist_{ts}/baseline_contract_matrix.json`",
        f"- `outputs/canonical_external_baseline_fairness_checklist_{ts}/main_table_eligibility.csv`",
        f"- `outputs/canonical_external_baseline_fairness_checklist_{ts}/fairness_violations.csv`",
        f"- `outputs/canonical_external_baseline_fairness_checklist_{ts}/normalization_rules.json`",
        f"- `outputs/canonical_external_baseline_fairness_checklist_{ts}/required_shared_infrastructure.json`",
        f"- `outputs/canonical_external_baseline_fairness_checklist_{ts}/baseline_presence_audit.csv`",
        f"- `outputs/canonical_external_baseline_fairness_checklist_{ts}/summary.md`",
        "",
        "## Presence interpretation notes",
        "- `already_present_partial` means evidence exists in docs/registry/adapter artifacts but no fully fair canonical direct-comparison lane is ready.",
        "- `already_present_blocked` means baseline is tracked with explicit blocker artifacts.",
        "- `not_present` means no meaningful footprint in current repo taxonomy/registry/docs/scripts/outputs.",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")

    print(f"Wrote canonical fairness checklist package to: {out_dir}")
    print(f"Wrote canonical checklist doc: {doc_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
