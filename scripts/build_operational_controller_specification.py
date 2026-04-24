#!/usr/bin/env python3
"""Build manuscript operational controller specification artifacts (static audit only)."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.scoring import ScoreConfig, SimpleBranchScorer
from scripts.run_matched_surface_multiseed_main_comparison import METHOD_RUNTIME_MAP

DOCS = REPO_ROOT / "docs"
OUTPUTS = REPO_ROOT / "outputs"

STRICT_F3 = "strict_f3"
STRICT_GATE = "strict_gate1_cap_k6"
STRICT_F2 = "strict_f2"
L1_MAX = "l1_max"

METHODS = [STRICT_F3, STRICT_GATE, STRICT_F2, L1_MAX]


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _serialize(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.10g}"
    return str(v)


def _runtime_name(method_key: str) -> str:
    return METHOD_RUNTIME_MAP[method_key]


def _instantiate_controllers() -> dict[str, Any]:
    scorer = SimpleBranchScorer(ScoreConfig())
    generator_factory = generator_factory_for_mode(
        use_openai_api=False,
        rng=__import__("random").Random(0),
        openai_model="gpt-4.1-mini",
        temperature=0.0,
        max_output_tokens=128,
        timeout_seconds=15,
    )
    specs = build_frontier_strategies(
        generator_factory,
        budget=8,
        adaptive_min_expand_grid=[0, 1],
        rng=__import__("random").Random(0),
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_tale_baseline=False,
        include_external_s1_baseline=False,
    )
    out = {}
    for m in METHODS:
        out[m] = specs[_runtime_name(m)]
    return out


def _extract_hyperparams(controller: Any) -> dict[str, Any]:
    keep = {}
    for k, v in controller.__dict__.items():
        if k in {"generator", "scorer"}:
            continue
        if k.startswith("_"):
            continue
        if isinstance(v, (int, float, str, bool)):
            keep[k] = v
    return keep


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_spec(timestamp: str) -> tuple[Path, Path]:
    out_dir = OUTPUTS / f"operational_controller_specification_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    doc_path = DOCS / f"OPERATIONAL_CONTROLLER_SPECIFICATION_FOR_MANUSCRIPT_{timestamp}.md"

    ctrls = _instantiate_controllers()
    hp = {k: _extract_hyperparams(v) for k, v in ctrls.items()}

    symbol_rows = [
        {
            "manuscript_symbol_or_object": "branch b",
            "operational_definition": "One `BranchState` object with reasoning trajectory, score, predicted answer, depth/action history.",
            "source_file": "experiments/branching.py",
            "source_function_or_class": "BranchState",
            "notes_for_manuscript": "Branch includes mutable control state (`is_done`, `is_pruned`, `verify_count`) and score trace.",
        },
        {
            "manuscript_symbol_or_object": "frontier F_t",
            "operational_definition": "Active list `branches` in `GlobalDiversityAggregationController.run()` after pruning done/pruned branches.",
            "source_file": "experiments/controllers.py",
            "source_function_or_class": "GlobalDiversityAggregationController.run",
            "notes_for_manuscript": "Frontier starts with two root branches and evolves by expand/verify/prune actions.",
        },
        {
            "manuscript_symbol_or_object": "answer group g",
            "operational_definition": "Normalized answer key from `_normalize_answer(predicted_answer)`; tracked in `answer_support_counts`.",
            "source_file": "experiments/controllers.py",
            "source_function_or_class": "GlobalDiversityAggregationController._normalize_answer",
            "notes_for_manuscript": "Numeric extraction fallback, else lowercase text token; unknown mapped to `__unknown__`.",
        },
        {
            "manuscript_symbol_or_object": "branch family",
            "operational_definition": "Root-derived family id in `branch_family_ids`; family-level repeat/cap controls operate on this key.",
            "source_file": "experiments/controllers.py",
            "source_function_or_class": "GlobalDiversityAggregationController.run",
            "notes_for_manuscript": "Family-level counters drive repeat-expansion penalties and hard max-family caps.",
        },
        {
            "manuscript_symbol_or_object": "V_t(b)",
            "operational_definition": "Primary continuation value `self.scorer.score_branch(b)` with additive anti-collapse adjustments.",
            "source_file": "experiments/controllers.py",
            "source_function_or_class": "GlobalDiversityAggregationController._branch_priority",
            "notes_for_manuscript": "No single closed-form scalar in code; implemented as composed score + penalties/bonuses.",
        },
        {
            "manuscript_symbol_or_object": "A_t(b)",
            "operational_definition": "Allocation priority after anti-collapse adjustment: `priority + adjusted_priority_delta`.",
            "source_file": "experiments/controllers.py",
            "source_function_or_class": "GlobalDiversityAggregationController._anti_collapse_priority_adjustments",
            "notes_for_manuscript": "Encodes diversity pressure, duplicate penalties, repeat-family controls, cooldowns, and gates.",
        },
        {
            "manuscript_symbol_or_object": "C_t(b)",
            "operational_definition": "Commit/selection evidence from answer-group support summary and readiness metrics.",
            "source_file": "experiments/controllers.py",
            "source_function_or_class": "GlobalDiversityAggregationController._group_support_summary",
            "notes_for_manuscript": "Uses discounted support, quality/readiness means, support margin, and one-step continuation estimate.",
        },
        {
            "manuscript_symbol_or_object": "R_t(b)",
            "operational_definition": "Deterministic output-layer repair policy on selected final-node answer and extracted answer.",
            "source_file": "experiments/output_layer_repair.py",
            "source_function_or_class": "choose_repair_answer",
            "notes_for_manuscript": "Rescue only if canonical-consensus support trigger holds; otherwise preserve selected branch answer.",
        },
        {
            "manuscript_symbol_or_object": "commit rule",
            "operational_definition": "Commit when top support/margin/readiness thresholds pass and one-step continuation value is below threshold.",
            "source_file": "experiments/controllers.py",
            "source_function_or_class": "GlobalDiversityAggregationController._commit_by_answer_group_margin",
            "notes_for_manuscript": "Alternative incumbent-challenger commit mode may override via metalevel checks.",
        },
        {
            "manuscript_symbol_or_object": "budget B in {4,6,8}",
            "operational_definition": "Hard cap `max_actions_per_problem` checked in run loop `while actions < self.max_actions`.",
            "source_file": "experiments/controllers.py",
            "source_function_or_class": "GlobalDiversityAggregationController.run",
            "notes_for_manuscript": "Budget counts controller actions (expand/verify) and bounds all internal policies.",
        },
        {
            "manuscript_symbol_or_object": "external_l1_max boundary",
            "operational_definition": "Length-control baseline (`L1LengthControlController`, control_mode='max').",
            "source_file": "experiments/frontier_matrix_core.py",
            "source_function_or_class": "build_frontier_strategies",
            "notes_for_manuscript": "Used as near-direct external comparator, not part of frontier-allocation family.",
        },
    ]
    _write_csv(
        out_dir / "symbol_to_code_map.csv",
        symbol_rows,
        [
            "manuscript_symbol_or_object",
            "operational_definition",
            "source_file",
            "source_function_or_class",
            "notes_for_manuscript",
        ],
    )

    hp_rows = []
    for method in [STRICT_F3, STRICT_GATE, STRICT_F2]:
        runtime = _runtime_name(method)
        for k, v in sorted(hp[method].items()):
            hp_rows.append(
                {
                    "method": method,
                    "runtime_method_name": runtime,
                    "hyperparameter": k,
                    "value": _serialize(v),
                }
            )
    _write_csv(
        out_dir / "method_hyperparameter_table.csv",
        hp_rows,
        ["method", "runtime_method_name", "hyperparameter", "value"],
    )

    diff_rows = []
    keys = sorted(set(hp[STRICT_F3]) | set(hp[STRICT_GATE]))
    for k in keys:
        v_f3 = hp[STRICT_F3].get(k)
        v_g = hp[STRICT_GATE].get(k)
        if v_f3 != v_g:
            diff_rows.append(
                {
                    "hyperparameter": k,
                    "strict_f3_value": _serialize(v_f3),
                    "strict_gate1_cap_k6_value": _serialize(v_g),
                    "difference_note": "different",
                }
            )
    _write_csv(
        out_dir / "strict_f3_vs_gate1_diff_table.csv",
        diff_rows,
        ["hyperparameter", "strict_f3_value", "strict_gate1_cap_k6_value", "difference_note"],
    )

    unresolved = {
        "unresolved_or_partially_resolved": [
            {
                "gap": "No single explicit closed-form V_t(b), A_t(b), C_t(b), R_t(b) equations in code.",
                "evidence": "Controller implements compositional heuristics across multiple helper functions.",
                "impact_on_manuscript": "Paper should present high-level symbolic abstraction and point to appendix operational mapping.",
            },
            {
                "gap": "Several configuration values are encoded in long runtime strategy names.",
                "evidence": "Method runtime names in `METHOD_RUNTIME_MAP` include policy mode/cap semantics.",
                "impact_on_manuscript": "Appendix should map strategy-name tokens to concrete flags and thresholds.",
            },
            {
                "gap": "Certain gating/anti-collapse decisions are heuristic and branch-history-dependent.",
                "evidence": "Repeat penalties, cooldown triggers, near-tie forcing, and conditional family-cap relax modes.",
                "impact_on_manuscript": "State clearly that implementation is deterministic but heuristic, not pure closed-form optimization.",
            },
        ],
        "overall_status": "partially formalized, implementation-specified",
    }
    (out_dir / "unresolved_method_spec_gaps.json").write_text(json.dumps(unresolved, indent=2), encoding="utf-8")

    status = f"""# Operational controller specification status

- Generated static implementation audit with no OpenAI/Cohere API calls.
- Methods covered: strict_f3, strict_gate1_cap_k6, strict_f2 (plus external_l1_max boundary notes).
- Main unresolved status: deterministic implementation is fully inspectable, but closed-form symbolic equations are partial abstractions over heuristic logic.
"""
    (out_dir / "STATUS.md").write_text(status, encoding="utf-8")

    strict_f3_name = _runtime_name(STRICT_F3)
    strict_gate_name = _runtime_name(STRICT_GATE)
    strict_f2_name = _runtime_name(STRICT_F2)
    l1_name = _runtime_name(L1_MAX)

    doc = f"""# Operational controller specification for manuscript ({timestamp})

This document maps the manuscript controller description to exact implementation-level behavior in code.

## Scope

- Primary manuscript-facing methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`
- Comparator-boundary method: `external_l1_max`
- Source implementation family: `GlobalDiversityAggregationController` + output-layer repair pipeline

## Operational definitions

- **Branch data structure**: `BranchState` stores branch id, steps, score, predicted answer, done/pruned flags, verify count, and histories.
- **Frontier state**: mutable `branches` list in `GlobalDiversityAggregationController.run()`; active frontier is non-pruned subset.
- **Answer-group construction**: `_normalize_answer()` canonicalizes numeric/text outputs into answer-group keys; per-step support tracked in `answer_support_counts`.
- **Branch family definition**: `branch_family_ids` assigns each branch to a root-family lineage; repeat/cap controls operate per family.
- **V_t(b) implementation**: continuation value base from `self.scorer.score_branch(b)`, then combined with quality/readiness/diversity-derived terms.
- **A_t(b) implementation**: allocation priority after anti-collapse adjustments (`adjusted_priority_delta`) and optional gate interventions.
- **C_t(b) implementation**: commit evidence from group support margin, top-group readiness, and one-step continuation estimate.
- **R_t(b) implementation**: output-layer repair via deterministic extraction/canonicalization and bounded rescue (`choose_repair_answer`).
- **Commit rule**: `_commit_by_answer_group_margin` requires action minimum + support threshold + support margin + readiness + low continuation value.
- **Budget enforcement (4/6/8)**: action loop guarded by `while actions < self.max_actions`; each expand/verify consumes budget action units.

## Method instantiations used in manuscript runs

- `strict_f3` runtime strategy name:
  - `{strict_f3_name}`
- `strict_gate1_cap_k6` runtime strategy name:
  - `{strict_gate_name}`
- `strict_f2` runtime strategy name:
  - `{strict_f2_name}`
- `external_l1_max` runtime strategy name:
  - `{l1_name}`

## strict_f3 vs strict_gate1_cap_k6 (implementation difference)

- Both share the same core global-diversity/anti-collapse machinery.
- `strict_gate1_cap_k6` additionally enables hard max-family expansion cap logic (base cap 6 with mode-controlled relax behavior).
- `strict_f3` does not apply the strict gate-k6 cap and uses depth-3 early root coverage forcing configuration.
- `strict_f2` is the depth-2 coverage-forced variant without k6 family-cap gating.

## Heuristic vs closed-form boundary

- Implementation is deterministic and auditable, but several control terms are not encoded as a single closed-form formula.
- The score used operationally is a composition of continuation scoring + support/quality/readiness + anti-collapse gates/penalties.
- Strategy names encode some operational semantics (e.g., gate/cap mode), requiring explicit lookup tables for manuscript transparency.

## Appendix: Operational controller specification

We instantiate the manuscript controller as a deterministic fixed-budget allocator over a frontier of branch states. At each step, every active branch receives an implementation-level continuation priority composed from branch score, answer-group support structure, and anti-collapse regularizers. The controller then applies bounded intervention gates (coverage floor, early answer-group preservation, repeat-family cooldown, conditional family cap) before selecting a single action. The commit mechanism is not free-form: it is triggered only when support concentration and readiness exceed predefined thresholds while one-step continuation value is sufficiently low. Output extraction and repair are likewise deterministic: branch-local answer extraction is preferred, canonicalization is dataset-aware, and rescue only applies under explicit consensus conditions. This appendix-level specification should be treated as the experiment-level ground truth for reproducibility.

## Recommended main-text replacement paragraph

“Our controller score should be interpreted as a compact abstraction of a deterministic operational policy rather than a single closed-form objective. The experiments use an explicit implementation-level controller with fixed thresholds, branch-family caps, answer-group support aggregation, and bounded output-layer repair; Appendix X provides the exact operational definitions and code-level parameterization used in all reported runs.”
"""
    doc_path.write_text(doc, encoding="utf-8")
    return out_dir, doc_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build operational controller specification audit artifacts.")
    parser.add_argument("--timestamp", default=_now_stamp())
    args = parser.parse_args()

    out_dir, doc_path = build_spec(args.timestamp)
    print(json.dumps({"status": "ok", "out_dir": str(out_dir), "doc_path": str(doc_path)}, indent=2))


if __name__ == "__main__":
    main()
