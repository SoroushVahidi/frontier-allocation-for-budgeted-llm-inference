#!/usr/bin/env python3
"""Held-out GSM8K simulator evaluation: DR baseline / V1 / guarded (no paid API).

Samples a fixed-size cohort from the GSM8K test split (HF loader), excluding the 66-case
diagnostic ``example_id`` rows, then evaluates three controllers with matched budget.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import PilotExample, extract_final_answer
from experiments.frontier_matrix_core import build_frontier_strategies, generator_factory_for_mode
from experiments.gsm8k_held_out_sampling import exclusion_example_ids_from_csv_rows, held_out_sample_example_ids
from experiments.hf_datasets import resolve_dataset_spec, sample_hf_examples

DEFAULT_EXCLUDE_CSV = (
    "outputs/strategy_seeded_discovery_on_66_gold_absent_20260502T222129Z/gold_absent_case_list.csv"
)
GSM8K_POOL_SAMPLE_SEED = 42
"""Must match the common HF pilot shuffle convention (same as guarded eval caches)."""

GSM8K_POOL_PILOT_SIZE = 1319
"""OpenAI GSM8K ``test`` split size; ``sample_hf_examples`` truncates to dataset length."""


def _load_guard_eval_runtime() -> Any:
    path = REPO_ROOT / "scripts/run_diverse_root_frontier_v1_66_eval_with_guarded.py"
    spec = importlib.util.spec_from_file_location("_guard_dr_eval_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load guarded evaluator module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Held-out GSM8K DR baseline/V1/guarded comparison (simulator).")
    p.add_argument(
        "--exclude-case-list",
        default=DEFAULT_EXCLUDE_CSV,
        help="CSV containing diagnostic example_id rows to remove from the GSM8K pool.",
    )
    p.add_argument("--held-out-seed", type=int, default=20260503, help="RNG seed for sampling held-out IDs.")
    p.add_argument("--held-out-size", type=int, default=100, help="Number of examples to sample after exclusions.")
    p.add_argument("--limit", type=int, default=0, help="Evaluate only the first N sampled IDs (smoke).")
    p.add_argument("--dry-run-manifest-only", action="store_true", help="Write manifest + summaries only; no eval.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--budget", type=int, default=6)
    p.add_argument("--seed", type=int, default=42, help="Simulator RNG seed passed into controllers.")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-root", default="outputs")
    p.add_argument(
        "--diagnostic-candidates",
        action="store_true",
        help="Write candidate_diagnostics.csv using guarded evaluator diagnostics.",
    )
    return p.parse_args()


def _build_example_caches_from_pool(
    pool_rows: list[dict[str, str]], picked_ids: list[str]
) -> tuple[dict[str, PilotExample], dict[str, str]]:
    picked = set(picked_ids)
    examples: dict[str, PilotExample] = {}
    raw_by_id: dict[str, str] = {}
    for r in pool_rows:
        eid = r["example_id"]
        if eid not in picked:
            continue
        raw_by_id[eid] = str(r.get("answer", "") or "")
        examples[eid] = PilotExample(
            example_id=eid,
            question=r["question"],
            answer=extract_final_answer(r["answer"]),
        )
    return examples, raw_by_id


def _prediction_correct(bundle: dict[str, Any]) -> bool:
    res = bundle.get("result")
    return bool(res and getattr(res, "is_correct", False))


def _candidate_stats(_ge: Any, bundle: dict[str, Any]) -> tuple[int, int]:
    candidates = bundle["candidates"]
    cand_norm = [_ge._normalize_answer_for_comparison(getattr(c, "normalized_answer", None) or "") for c in candidates]
    distinct = len({n for n in cand_norm if str(n).strip()})
    return len(candidates), distinct


def _near_numeric_miss_le2(_ge: Any, bundle: dict[str, Any], effective_gold: str) -> bool:
    if bundle["gold_present"] or not str(effective_gold).strip():
        return False
    md = _ge._min_abs_numeric_delta_vs_candidates(str(effective_gold), bundle["candidates"])
    return _ge._near_numeric_match_label(md, 2.0) == "yes"


def main() -> None:
    args = parse_args()
    _ge = _load_guard_eval_runtime()
    _ge.configure_logical_api_call_budget(None)

    exclude_path = REPO_ROOT / args.exclude_case_list if not Path(args.exclude_case_list).is_absolute() else Path(
        args.exclude_case_list
    )
    exclude_rows = _ge.read_csv(str(exclude_path))
    exclude_ids = exclusion_example_ids_from_csv_rows(exclude_rows)

    spec = resolve_dataset_spec("openai/gsm8k")
    pool_rows = sample_hf_examples(
        dataset_name="openai/gsm8k",
        pilot_size=GSM8K_POOL_PILOT_SIZE,
        seed=GSM8K_POOL_SAMPLE_SEED,
        split=spec.default_split,
        config_name=spec.default_config,
    )
    pool_ids = [r["example_id"] for r in pool_rows]
    exclude_missing = sorted(exclude_ids - set(pool_ids))

    try:
        sampled_full = held_out_sample_example_ids(
            pool_example_ids=pool_ids,
            exclude=exclude_ids,
            held_out_seed=args.held_out_seed,
            k=args.held_out_size,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    picked_ids = sampled_full[: args.limit] if args.limit > 0 else sampled_full

    output_dir = REPO_ROOT / args.output_root / f"gsm8k_held_out_dr_comparison_{args.timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []
    for eid in picked_ids:
        row = next((r for r in pool_rows if r["example_id"] == eid), None)
        gold_hint = extract_final_answer(row["answer"]) if row else ""
        manifest_rows.append(
            {
                "example_id": eid,
                "dataset": "openai/gsm8k",
                "evaluator_seed": args.seed,
                "budget": args.budget,
                "gsm8k_pool_sample_seed": GSM8K_POOL_SAMPLE_SEED,
                "gsm8k_pool_pilot_size": GSM8K_POOL_PILOT_SIZE,
                "held_out_seed": args.held_out_seed,
                "held_out_size": args.held_out_size,
                "gold_answer_canonical_hint": gold_hint,
            }
        )
    _ge.write_csv(output_dir / "held_out_case_manifest.csv", manifest_rows)

    summary_meta: dict[str, Any] = {
        "timestamp": args.timestamp,
        "output_dir": str(output_dir.relative_to(REPO_ROOT)),
        "exclude_case_list": str(exclude_path.relative_to(REPO_ROOT) if exclude_path.is_relative_to(REPO_ROOT) else exclude_path),
        "exclude_row_count": len(exclude_rows),
        "exclude_distinct_ids": len(exclude_ids),
        "exclude_ids_missing_from_pool_count": len(exclude_missing),
        "gsm8k_pool_rows": len(pool_rows),
        "gsm8k_pool_sample_seed": GSM8K_POOL_SAMPLE_SEED,
        "held_out_seed": args.held_out_seed,
        "held_out_size_requested": args.held_out_size,
        "held_out_sampled_count": len(sampled_full),
        "cases_evaluated": len(picked_ids),
        "evaluator_seed": args.seed,
        "budget": args.budget,
        "dry_run_manifest_only": args.dry_run_manifest_only,
        "diagnostic_candidates": args.diagnostic_candidates,
        "methods": [
            _ge.BASELINE_METHOD,
            _ge.V1_METHOD,
            _ge.GUARDED_METHOD,
        ],
    }

    summary_csv_row: dict[str, Any] = {"timestamp": args.timestamp, "cases_evaluated": len(picked_ids)}

    if args.dry_run_manifest_only:
        summary_meta["note"] = "dry_run_manifest_only: no controller evaluation performed"
        _ge.write_json(output_dir / "summary.json", summary_meta)
        _ge.write_csv(output_dir / "summary.csv", [summary_csv_row])
        print(f"Dry-run manifest written to {output_dir}")
        return

    example_cache, raw_gsm8k_answer_by_id = _build_example_caches_from_pool(pool_rows, picked_ids)

    rng = random.Random(args.seed)
    gen_factory_fn = generator_factory_for_mode(
        use_openai_api=False,
        rng=rng,
        openai_model="gpt-4.1-mini",
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
    )
    strategies = build_frontier_strategies(
        generator_factory=gen_factory_fn,
        budget=args.budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
    )
    baseline_ctrl = strategies.get(_ge.BASELINE_METHOD)
    v1_ctrl = strategies.get(_ge.V1_METHOD)
    guarded_ctrl = strategies.get(_ge.GUARDED_METHOD)
    if not baseline_ctrl or not v1_ctrl or not guarded_ctrl:
        raise SystemExit("Required DR strategies missing from build_frontier_strategies.")

    cases: list[dict[str, str]] = []
    for eid in picked_ids:
        row = next((r for r in pool_rows if r["example_id"] == eid))
        cases.append(
            {
                "dataset": "openai/gsm8k",
                "example_id": eid,
                "seed": str(args.seed),
                "budget": str(args.budget),
                "gold_answer_canonical_hint": extract_final_answer(row["answer"]),
            }
        )

    per_case_results: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    baseline_gc = v1_gc = guarded_gc = 0
    baseline_ok = v1_ok = guarded_ok = 0
    near_b = near_v1 = near_g = 0

    v1_rec: list[str] = []
    guarded_rec: list[str] = []
    v1_reg: list[str] = []
    guarded_reg: list[str] = []
    gold_hint_source_counts: Counter[str] = Counter()

    for i, case in enumerate(cases):
        case_id = _ge.get_case_key(case)
        print(f"[{i+1}/{len(cases)}] {case_id}...", end=" ", flush=True)

        dataset_name = case.get("dataset", "openai/gsm8k")
        example_id = case.get("example_id", "")
        gold_answer_hint = case.get("gold_answer_canonical_hint", "")
        effective_gold_hint, gold_hint_source = _ge.get_effective_gold_hint_for_eval(
            gold_answer_hint,
            example_id,
            dataset_name,
            example_cache,
        )
        gold_hint_source_counts[gold_hint_source] += 1

        question_text = _ge.get_example_question(example_id, dataset_name, example_cache)
        gold_norm = _ge._normalize_answer_for_comparison(effective_gold_hint)
        gold_for_ctrl = gold_answer_hint or ""

        baseline_b = _ge._eval_one_method(
            baseline_ctrl,
            question_text,
            gold_for_ctrl,
            gold_norm,
            want_extraction_diag=args.diagnostic_candidates,
        )
        v1_b = _ge._eval_one_method(
            v1_ctrl, question_text, gold_for_ctrl, gold_norm, want_extraction_diag=args.diagnostic_candidates
        )
        guarded_b = _ge._eval_one_method(
            guarded_ctrl,
            question_text,
            gold_for_ctrl,
            gold_norm,
            want_extraction_diag=args.diagnostic_candidates,
        )

        if baseline_b["error"]:
            print(f"baseline error: {baseline_b['error']}", end=" ")
        if v1_b["error"]:
            print(f"v1 error: {v1_b['error']}", end=" ")
        if guarded_b["error"]:
            print(f"guarded error: {guarded_b['error']}", end=" ")

        bp, vp, gp = baseline_b["gold_present"], v1_b["gold_present"], guarded_b["gold_present"]
        if bp:
            baseline_gc += 1
        if vp:
            v1_gc += 1
        if gp:
            guarded_gc += 1

        bc, vc, gc = _prediction_correct(baseline_b), _prediction_correct(v1_b), _prediction_correct(guarded_b)
        if bc:
            baseline_ok += 1
        if vc:
            v1_ok += 1
        if gc:
            guarded_ok += 1

        b_cc, b_dn = _candidate_stats(_ge, baseline_b)
        v1_cc, v1_dn = _candidate_stats(_ge, v1_b)
        g_cc, g_dn = _candidate_stats(_ge, guarded_b)

        if _near_numeric_miss_le2(_ge, baseline_b, effective_gold_hint):
            near_b += 1
        if _near_numeric_miss_le2(_ge, v1_b, effective_gold_hint):
            near_v1 += 1
        if _near_numeric_miss_le2(_ge, guarded_b, effective_gold_hint):
            near_g += 1

        if vp and not bp:
            v1_rec.append(case_id)
        elif not vp and bp:
            v1_reg.append(case_id)
        if gp and not bp:
            guarded_rec.append(case_id)
        elif not gp and bp:
            guarded_reg.append(case_id)

        v1_status = (
            "recovered" if (vp and not bp) else "regressed" if (not vp and bp) else "no_change"
        )
        guarded_status = (
            "recovered" if (gp and not bp) else "regressed" if (not gp and bp) else "no_change"
        )

        raw_gsm8k_backfill = ""
        if gold_hint_source == "dataset_backfill":
            raw_gsm8k_backfill = raw_gsm8k_answer_by_id.get(example_id, "")

        common_diag = dict(
            case_id=case_id,
            example_id=example_id,
            seed=str(case.get("seed", "")),
            budget=str(case.get("budget", "")),
            gold_hint_source=gold_hint_source,
            raw_gold_hint_case_list=gold_answer_hint,
            raw_gsm8k_answer_if_backfilled=raw_gsm8k_backfill,
            effective_gold_for_eval=effective_gold_hint,
            normalized_gold_for_eval=gold_norm,
        )
        if args.diagnostic_candidates:
            diagnostic_rows.append(_ge.diagnostic_row_from_eval(**common_diag, method="baseline", bundle=baseline_b))
            diagnostic_rows.append(_ge.diagnostic_row_from_eval(**common_diag, method="v1", bundle=v1_b))
            diagnostic_rows.append(_ge.diagnostic_row_from_eval(**common_diag, method="guarded", bundle=guarded_b))

        per_case_results.append(
            {
                "case_id": case_id,
                "dataset": dataset_name,
                "example_id": example_id,
                "seed": case.get("seed", ""),
                "budget": case.get("budget", ""),
                "gold_answer": gold_answer_hint,
                "effective_gold_answer_for_eval": effective_gold_hint,
                "gold_hint_source": gold_hint_source,
                "baseline_correct": "yes" if bc else "no",
                "v1_correct": "yes" if vc else "no",
                "guarded_correct": "yes" if gc else "no",
                "baseline_gold_present": "yes" if bp else "no",
                "v1_gold_present": "yes" if vp else "no",
                "guarded_gold_present": "yes" if gp else "no",
                "baseline_candidate_count": b_cc,
                "v1_candidate_count": v1_cc,
                "guarded_candidate_count": g_cc,
                "baseline_distinct_normalized_candidate_count": b_dn,
                "v1_distinct_normalized_candidate_count": v1_dn,
                "guarded_distinct_normalized_candidate_count": g_dn,
                "v1_status": v1_status,
                "guarded_status": guarded_status,
            }
        )
        print(f"B_acc={bc} V1_acc={vc} G_acc={gc} | gold∈cand B={bp} V1={vp} G={gp}")

    n = len(cases)
    summary_eval = {
        **summary_meta,
        "total_cases": n,
        "baseline_method": _ge.BASELINE_METHOD,
        "v1_method": _ge.V1_METHOD,
        "guarded_method": _ge.GUARDED_METHOD,
        "baseline_exact_accuracy": baseline_ok / n if n else 0.0,
        "v1_exact_accuracy": v1_ok / n if n else 0.0,
        "guarded_exact_accuracy": guarded_ok / n if n else 0.0,
        "baseline_gold_present_rate": baseline_gc / n if n else 0.0,
        "v1_gold_present_rate": v1_gc / n if n else 0.0,
        "guarded_gold_present_rate": guarded_gc / n if n else 0.0,
        "v1_delta_gold_present": v1_gc - baseline_gc,
        "guarded_delta_gold_present": guarded_gc - baseline_gc,
        "v1_newly_recovered_count": len(v1_rec),
        "v1_newly_regressed_count": len(v1_reg),
        "guarded_newly_recovered_count": len(guarded_rec),
        "guarded_newly_regressed_count": len(guarded_reg),
        "near_numeric_exact_miss_le2_count_baseline": near_b,
        "near_numeric_exact_miss_le2_count_v1": near_v1,
        "near_numeric_exact_miss_le2_count_guarded": near_g,
        "gold_hint_source_counts": dict(gold_hint_source_counts),
        "generation_mode": "simulator",
    }

    summary_csv_row.update(
        {
            "baseline_exact_accuracy": summary_eval["baseline_exact_accuracy"],
            "v1_exact_accuracy": summary_eval["v1_exact_accuracy"],
            "guarded_exact_accuracy": summary_eval["guarded_exact_accuracy"],
            "baseline_gold_present_rate": summary_eval["baseline_gold_present_rate"],
            "v1_gold_present_rate": summary_eval["v1_gold_present_rate"],
            "guarded_gold_present_rate": summary_eval["guarded_gold_present_rate"],
        }
    )

    _ge.write_csv(output_dir / "per_case_results.csv", per_case_results)
    _ge.write_json(output_dir / "summary.json", summary_eval)
    _ge.write_csv(output_dir / "summary.csv", [summary_csv_row])

    diag_fieldnames = [
        "case_id",
        "method",
        "example_id",
        "seed",
        "budget",
        "gold_hint_source",
        "raw_gold_hint_case_list",
        "raw_gsm8k_answer_if_backfilled",
        "effective_gold_for_eval",
        "normalized_gold",
        "prediction_final_answer",
        "normalized_prediction",
        "candidate_normalized_answers",
        "candidate_extractor_normalized_answers",
        "candidate_raw_answers",
        "candidate_count",
        "distinct_normalized_candidate_count",
        "extraction_sources_used",
        "extraction_metadata_keys_present",
        "extraction_skip_counts",
        "exact_gold_match_found",
        "near_numeric_abs_diff_min",
        "near_numeric_match_le_1",
        "near_numeric_match_le_2",
        "near_numeric_match_abs_le_2",
        "candidate_has_gold_as_substring",
        "gold_has_candidate_as_substring",
        "normalization_artifact_suspected",
        "notes",
    ]
    if args.diagnostic_candidates:
        _ge.write_csv(
            output_dir / "candidate_diagnostics.csv",
            diagnostic_rows,
            diag_fieldnames,
            quoting=csv.QUOTE_NONNUMERIC,
        )

    print("=" * 72)
    print(f"Wrote results under {output_dir}")
    print(
        f"accuracy baseline/v1/guarded: {summary_eval['baseline_exact_accuracy']:.3f} / "
        f"{summary_eval['v1_exact_accuracy']:.3f} / {summary_eval['guarded_exact_accuracy']:.3f}"
    )
    print(
        f"gold∈cand rates: {summary_eval['baseline_gold_present_rate']:.3f} / "
        f"{summary_eval['v1_gold_present_rate']:.3f} / {summary_eval['guarded_gold_present_rate']:.3f}"
    )


if __name__ == "__main__":
    main()
