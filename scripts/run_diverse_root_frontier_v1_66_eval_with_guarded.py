#!/usr/bin/env python3
"""Evaluation of diverse_root_frontier_v1 variants on 66 gold-absent cases.

Compares three methods:
1. Baseline: direct_reserve_strategy_seeded_semantic_frontier_v2_final
2. V1: direct_reserve_diverse_root_frontier_v1
3. Guarded: direct_reserve_diverse_root_frontier_v1_guarded (falls back when baseline has strong support)

Primary metric: gold_present_in_candidate_groups.
No API calls; uses simulator mode.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    generator_factory_for_mode,
)
from experiments.data import NUMBER_PATTERN, PilotExample, extract_final_answer
from experiments.hf_datasets import resolve_dataset_spec, sample_hf_examples
from experiments.selector_candidate_extraction import (
    CandidateExtractionDiagnostics,
    build_candidates_from_metadata,
    build_candidates_from_metadata_diagnostic,
)

BASELINE_METHOD = "direct_reserve_strategy_seeded_semantic_frontier_v2_final"
V1_METHOD = "direct_reserve_diverse_root_frontier_v1"
GUARDED_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate diverse_root_frontier_v1 variants on 66 gold-absent cases."
    )
    p.add_argument(
        "--case-list",
        default="outputs/strategy_seeded_discovery_on_66_gold_absent_20260502T222129Z/gold_absent_case_list.csv",
    )
    p.add_argument("--limit", type=int, default=0, help="Limit number of cases (0=all)")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--budget", type=int, default=6)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-output-tokens", type=int, default=180)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--output-root", default="outputs")
    p.add_argument(
        "--diagnostic-candidates",
        action="store_true",
        help="Also write candidate_diagnostics.csv per case/method for gold/candidate/trace inspection.",
    )
    return p.parse_args()


def read_csv(path: Path | str) -> list[dict[str, str]]:
    """Read CSV file."""
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
    *,
    quoting: int = csv.QUOTE_MINIMAL,
) -> None:
    """Write CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames or ["empty"], quoting=quoting)
            w.writeheader()
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fieldnames or list(rows[0].keys()),
            quoting=quoting,
        )
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)


def as_int(v: Any, d: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return d


def as_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _normalize_answer_for_comparison(ans: str | None) -> str:
    """Normalize answer for comparison."""
    if not ans:
        return ""
    s = str(ans).strip().lower()
    for ch in "[](){}":
        s = s.replace(ch, "")
    return s.strip()


def _is_gold_in_candidates(candidates: list[dict[str, Any]], gold_norm: str) -> bool:
    """Check if gold is in candidate groups."""
    if not gold_norm or gold_norm.lower() in ("", "na", "none"):
        return False
    for cand in candidates:
        cand_norm = _normalize_answer_for_comparison(cand.get("normalized_answer", ""))
        if cand_norm == gold_norm:
            return True
    return False


def _primary_numeric_scalar(text: str | None) -> float | None:
    """Parse a primary numeric score from GSM8K/MATH-like answer text (extract_final_answer path)."""
    if text is None or not str(text).strip():
        return None
    ext = extract_final_answer(str(text).strip())
    nums = NUMBER_PATTERN.findall(ext.replace(",", ""))
    if nums:
        try:
            return float(nums[-1].replace(",", ""))
        except ValueError:
            pass
    try:
        return float(str(ext).replace(",", "").strip())
    except ValueError:
        return None


def _min_abs_numeric_delta_vs_candidates(gold_text: str, candidates: list[Any]) -> float | None:
    gold_val = _primary_numeric_scalar(gold_text)
    if gold_val is None:
        return None
    best: float | None = None
    for cand in candidates:
        for fragment in (
            cand.final_answer,
            getattr(cand, "normalized_answer", None) or "",
        ):
            cval = _primary_numeric_scalar(str(fragment))
            if cval is None:
                continue
            d = abs(cval - gold_val)
            if best is None or d < best:
                best = d
    return best


def _near_numeric_match_label(min_diff: float | None, threshold: float) -> str:
    if min_diff is None:
        return "na"
    return "yes" if min_diff <= threshold else "no"


def _substring_match_flags(gold_eff: str, candidates: list[Any]) -> tuple[str, str]:
    """Diagnostic yes/no: gold substring of candidate raw answer; candidate substring of gold."""
    g = str(gold_eff).strip().casefold()
    if not g:
        return "no", "no"
    cand_has_gold = "no"
    gold_has_cand = "no"
    for cand in candidates:
        r = str(cand.final_answer).strip().casefold()
        if not r:
            continue
        if g in r:
            cand_has_gold = "yes"
        if r in g:
            gold_has_cand = "yes"
        if cand_has_gold == "yes" and gold_has_cand == "yes":
            break
    return cand_has_gold, gold_has_cand


def _semicolon_join(values: list[str]) -> str:
    escaped = []
    for v in values:
        s = str(v).replace("\\", "\\\\").replace(";", "\\;")
        escaped.append(s)
    return "; ".join(escaped)


def _eval_one_method(
    controller: Any,
    question_text: str,
    gold_answer_hint_controller: str,
    gold_norm_for_eval: str,
    *,
    want_extraction_diag: bool = False,
) -> dict[str, Any]:
    """Run one controller once; mirrors prior try/except + candidate wiring."""
    extraction_sources: list[str] = []
    extraction_diag: CandidateExtractionDiagnostics | None = None
    candidates = []
    result = None
    err = ""
    try:
        result = controller.run(question_text, gold_answer_hint_controller or "")
        if result and result.metadata:
            if want_extraction_diag:
                got, extraction_sources_raw, extraction_diag = build_candidates_from_metadata_diagnostic(
                    question_text, result.metadata
                )
                candidates = list(got)
                extraction_sources = list(extraction_sources_raw)
            else:
                got, extraction_sources_raw = build_candidates_from_metadata(question_text, result.metadata)
                candidates = list(got)
                extraction_sources = list(extraction_sources_raw)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    gold_present = _is_gold_in_candidates(
        [{"normalized_answer": c.normalized_answer} for c in candidates],
        gold_norm_for_eval,
    )
    return {
        "gold_present": gold_present,
        "candidates": candidates,
        "result": result,
        "error": err,
        "extraction_sources": extraction_sources,
        "extraction_diag": extraction_diag,
    }


def diagnostic_row_from_eval(
    *,
    case_id: str,
    method: str,
    example_id: str,
    seed: str,
    budget: str,
    gold_hint_source: str,
    raw_gold_hint_case_list: str,
    raw_gsm8k_answer_if_backfilled: str,
    effective_gold_for_eval: str,
    normalized_gold_for_eval: str,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    """CSV row describing gold/candidates/predictions using the existing eval normalization path."""
    candidates: list[Any] = bundle["candidates"]
    result = bundle["result"]
    err = str(bundle["error"]).strip()
    extraction_sources = bundle["extraction_sources"]
    ext_diag: CandidateExtractionDiagnostics | None = bundle.get("extraction_diag")

    cand_norm_strings = [_normalize_answer_for_comparison(c.normalized_answer or "") for c in candidates]
    extractor_norm_strings = [str(c.normalized_answer or "") for c in candidates]
    distinct_nonempty = {n for n in cand_norm_strings if n.strip()}

    prediction = getattr(result, "prediction", None) if result else None
    prediction_s = str(prediction) if prediction is not None else ""
    normalization_pred_basis = prediction_s.strip()
    normalized_prediction = (
        _normalize_answer_for_comparison(extract_final_answer(normalization_pred_basis))
        if normalization_pred_basis
        else ""
    )

    min_abs_diff = _min_abs_numeric_delta_vs_candidates(str(effective_gold_for_eval), candidates)
    near_min_str = "" if min_abs_diff is None else f"{min_abs_diff:.8g}"
    near_le1 = _near_numeric_match_label(min_abs_diff, 1.0)
    near_le2 = _near_numeric_match_label(min_abs_diff, 2.0)
    cand_sub_gold, gold_sub_cand = _substring_match_flags(str(effective_gold_for_eval), candidates)

    exact_hit = bundle["gold_present"]
    normalization_artifact_suspected = "no"
    if not exact_hit:
        if (
            near_le2 == "yes"
            or cand_sub_gold == "yes"
            or gold_sub_cand == "yes"
        ):
            normalization_artifact_suspected = "yes"

    notes: list[str] = []
    if err:
        notes.append(err)
    if not result:
        notes.append("no_method_result_after_exception_or_return")
    else:
        md = getattr(result, "metadata", None)
        if md is None:
            notes.append("metadata_none_candidate_extraction_blocked")
        elif not candidates:
            md_keys = ",".join(sorted(str(k) for k in md.keys()))
            src = ",".join(extraction_sources) if extraction_sources else ""
            notes.append(f"zero_candidates_extracted;metadata_keys={md_keys};reported_sources={src}")

    src_join = ",".join(extraction_sources)
    ext_meta_keys = ext_diag.metadata_keys_present if ext_diag else ""
    ext_skip_counts = ext_diag.extraction_skip_counts if ext_diag else ""

    return {
        "case_id": case_id,
        "method": method,
        "example_id": example_id,
        "seed": seed,
        "budget": budget,
        "gold_hint_source": gold_hint_source,
        "raw_gold_hint_case_list": raw_gold_hint_case_list,
        "raw_gsm8k_answer_if_backfilled": raw_gsm8k_answer_if_backfilled,
        "effective_gold_for_eval": effective_gold_for_eval,
        "normalized_gold": normalized_gold_for_eval,
        "prediction_final_answer": prediction_s,
        "normalized_prediction": normalized_prediction,
        "candidate_normalized_answers": _semicolon_join(cand_norm_strings),
        "candidate_extractor_normalized_answers": _semicolon_join(extractor_norm_strings),
        "candidate_raw_answers": _semicolon_join([str(c.final_answer) for c in candidates]),
        "candidate_count": len(candidates),
        "distinct_normalized_candidate_count": len(distinct_nonempty),
        "extraction_sources_used": src_join,
        "extraction_metadata_keys_present": ext_meta_keys,
        "extraction_skip_counts": ext_skip_counts,
        "exact_gold_match_found": "yes" if bundle["gold_present"] else "no",
        "near_numeric_abs_diff_min": near_min_str,
        "near_numeric_match_le_1": near_le1,
        "near_numeric_match_le_2": near_le2,
        "near_numeric_match_abs_le_2": near_le2,
        "candidate_has_gold_as_substring": cand_sub_gold,
        "gold_has_candidate_as_substring": gold_sub_cand,
        "normalization_artifact_suspected": normalization_artifact_suspected,
        "notes": "|".join(notes) if notes else "",
    }


def load_case_list(case_list_path: str) -> list[dict[str, Any]]:
    """Load and parse case list CSV."""
    rows = read_csv(case_list_path)
    if not rows:
        raise SystemExit(f"No cases found in {case_list_path}")
    return rows


def _load_gsm8k_example_and_raw_answer_caches(
    subset_size: int = 1000, seed: int = 42
) -> tuple[dict[str, PilotExample], dict[str, str]]:
    """Same HF slice as the prior evaluator; adds raw GSM8K `answer` strings for diagnostics."""
    spec = resolve_dataset_spec("openai/gsm8k")
    hf_ok = bool(os.getenv("HF_TOKEN"))
    hub_ok = bool(os.getenv("HUGGINGFACE_HUB_TOKEN"))
    try:
        rows = sample_hf_examples(
            dataset_name="openai/gsm8k",
            pilot_size=subset_size,
            seed=seed,
            split=spec.default_split,
            config_name=spec.default_config,
        )
    except Exception as exc:
        raise SystemExit(
            "Hugging Face dataset download/load failed for openai/gsm8k "
            "(required for GSM8K questions and evaluation-only gold backfill). "
            f"HF_TOKEN_present={hf_ok} HUGGINGFACE_HUB_TOKEN_present={hub_ok}. "
            f"Evaluator command-path: _load_gsm8k_example_and_raw_answer_caches -> sample_hf_examples. "
            f"Error: {type(exc).__name__}: {exc}"
        ) from exc
    examples: dict[str, PilotExample] = {}
    raw_by_id: dict[str, str] = {}
    for r in rows:
        eid = r["example_id"]
        raw_by_id[eid] = str(r.get("answer", "") or "")
        examples[eid] = PilotExample(
            example_id=eid,
            question=r["question"],
            answer=extract_final_answer(r["answer"]),
        )
    return examples, raw_by_id


def get_example_question(
    example_id: str, dataset_name: str, example_cache: dict[str, PilotExample]
) -> str:
    """Get the actual question text for an example."""
    if dataset_name != "openai/gsm8k":
        return f"[{dataset_name}] {example_id}"

    if not example_cache:
        return f"[{dataset_name}] {example_id}"

    example = example_cache.get(example_id)
    if example:
        return example.question

    return f"[{dataset_name}] {example_id}"


def get_effective_gold_hint_for_eval(
    case_gold_hint: str,
    example_id: str,
    dataset_name: str,
    example_cache: dict[str, PilotExample],
) -> tuple[str, str]:
    """Return evaluation gold hint and source; never used for controller decisions."""
    if str(case_gold_hint or "").strip():
        return str(case_gold_hint), "case_list"
    if dataset_name == "openai/gsm8k":
        ex = example_cache.get(example_id)
        if ex and str(ex.answer or "").strip():
            return str(ex.answer), "dataset_backfill"
    return "", "missing"


def get_case_key(case: dict[str, str]) -> str:
    """Extract unique case key."""
    return (
        f"{case.get('dataset', 'unknown')}::{case.get('example_id', '')}::"
        f"{case.get('seed', '')}::{case.get('budget', '')}"
    )


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    # Load cases
    case_list_path = REPO_ROOT / args.case_list if not Path(args.case_list).is_absolute() else Path(args.case_list)
    cases = load_case_list(str(case_list_path))

    if args.limit > 0:
        cases = cases[:args.limit]

    print(f"Loaded {len(cases)} cases from {case_list_path}")

    print("Loading GSM8K examples...", end=" ", flush=True)
    example_cache, raw_gsm8k_answer_by_id = _load_gsm8k_example_and_raw_answer_caches()
    print(f"Done ({len(example_cache)} examples)")

    # Create output directory
    output_dir = REPO_ROOT / args.output_root / f"diverse_root_frontier_v1_guarded_66_eval_{args.timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Build strategies
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

    baseline_ctrl = strategies.get(BASELINE_METHOD)
    v1_ctrl = strategies.get(V1_METHOD)
    guarded_ctrl = strategies.get(GUARDED_METHOD)

    if not baseline_ctrl:
        raise SystemExit(f"Strategy {BASELINE_METHOD} not found")
    if not v1_ctrl:
        raise SystemExit(f"Strategy {V1_METHOD} not found")
    if not guarded_ctrl:
        raise SystemExit(f"Strategy {GUARDED_METHOD} not found")

    print(f"Using baseline: {BASELINE_METHOD}")
    print(f"Using v1: {V1_METHOD}")
    print(f"Using guarded: {GUARDED_METHOD}")

    # Run evaluation
    per_case_results = []
    baseline_gold_count = 0
    v1_gold_count = 0
    guarded_gold_count = 0

    v1_recovered = []
    guarded_recovered = []
    v1_regressed = []
    guarded_regressed = []
    gold_hint_source_counts: Counter[str] = Counter()
    diagnostic_rows: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        case_id = get_case_key(case)
        print(f"[{i+1}/{len(cases)}] {case_id}...", end=" ", flush=True)

        dataset_name = case.get("dataset", "openai/gsm8k")
        example_id = case.get("example_id", "")
        gold_answer_hint = case.get("gold_answer_canonical_hint", "")
        effective_gold_hint, gold_hint_source = get_effective_gold_hint_for_eval(
            gold_answer_hint,
            example_id,
            dataset_name,
            example_cache,
        )
        gold_hint_source_counts[gold_hint_source] += 1

        question_text = get_example_question(example_id, dataset_name, example_cache)
        gold_norm = _normalize_answer_for_comparison(effective_gold_hint)

        gold_for_ctrl = gold_answer_hint or ""

        baseline_b = _eval_one_method(
            baseline_ctrl,
            question_text,
            gold_for_ctrl,
            gold_norm,
            want_extraction_diag=args.diagnostic_candidates,
        )
        if baseline_b["error"]:
            print(f"baseline error: {baseline_b['error']}", end=" ")
        baseline_gold_present = baseline_b["gold_present"]

        v1_b = _eval_one_method(
            v1_ctrl,
            question_text,
            gold_for_ctrl,
            gold_norm,
            want_extraction_diag=args.diagnostic_candidates,
        )
        if v1_b["error"]:
            print(f"v1 error: {v1_b['error']}", end=" ")
        v1_gold_present = v1_b["gold_present"]

        guarded_b = _eval_one_method(
            guarded_ctrl,
            question_text,
            gold_for_ctrl,
            gold_norm,
            want_extraction_diag=args.diagnostic_candidates,
        )
        if guarded_b["error"]:
            print(f"guarded error: {guarded_b['error']}", end=" ")
        guarded_gold_present = guarded_b["gold_present"]

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
            diagnostic_rows.append(
                diagnostic_row_from_eval(**common_diag, method="baseline", bundle=baseline_b)
            )
            diagnostic_rows.append(
                diagnostic_row_from_eval(**common_diag, method="v1", bundle=v1_b)
            )
            diagnostic_rows.append(
                diagnostic_row_from_eval(**common_diag, method="guarded", bundle=guarded_b)
            )

        # Count hits
        if baseline_gold_present:
            baseline_gold_count += 1
        if v1_gold_present:
            v1_gold_count += 1
        if guarded_gold_present:
            guarded_gold_count += 1

        # Track recovery/regression
        if v1_gold_present and not baseline_gold_present:
            v1_recovered.append(case_id)
        elif not v1_gold_present and baseline_gold_present:
            v1_regressed.append(case_id)

        if guarded_gold_present and not baseline_gold_present:
            guarded_recovered.append(case_id)
        elif not guarded_gold_present and baseline_gold_present:
            guarded_regressed.append(case_id)

        # Determine statuses
        v1_status = (
            "recovered" if (v1_gold_present and not baseline_gold_present)
            else "regressed" if (not v1_gold_present and baseline_gold_present)
            else "no_change"
        )
        guarded_status = (
            "recovered" if (guarded_gold_present and not baseline_gold_present)
            else "regressed" if (not guarded_gold_present and baseline_gold_present)
            else "no_change"
        )
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
                "baseline_gold_present": "yes" if baseline_gold_present else "no",
                "v1_gold_present": "yes" if v1_gold_present else "no",
                "guarded_gold_present": "yes" if guarded_gold_present else "no",
                "v1_status": v1_status,
                "guarded_status": guarded_status,
            }
        )

        print(f"B={baseline_gold_present} V1={v1_gold_present} G={guarded_gold_present}")

    # Calculate summary metrics
    total_cases = len(cases)
    baseline_rate = baseline_gold_count / total_cases if total_cases > 0 else 0.0
    v1_rate = v1_gold_count / total_cases if total_cases > 0 else 0.0
    guarded_rate = guarded_gold_count / total_cases if total_cases > 0 else 0.0

    summary = {
        "timestamp": args.timestamp,
        "total_cases": total_cases,
        "baseline_method": BASELINE_METHOD,
        "baseline_gold_present_count": baseline_gold_count,
        "baseline_recovery_rate": baseline_rate,
        "v1_method": V1_METHOD,
        "v1_gold_present_count": v1_gold_count,
        "v1_recovery_rate": v1_rate,
        "v1_delta_gold_present": v1_gold_count - baseline_gold_count,
        "v1_newly_recovered_count": len(v1_recovered),
        "v1_newly_regressed_count": len(v1_regressed),
        "guarded_method": GUARDED_METHOD,
        "guarded_gold_present_count": guarded_gold_count,
        "guarded_recovery_rate": guarded_rate,
        "guarded_delta_gold_present": guarded_gold_count - baseline_gold_count,
        "guarded_newly_recovered_count": len(guarded_recovered),
        "guarded_newly_regressed_count": len(guarded_regressed),
        "gold_hint_source_counts": dict(gold_hint_source_counts),
    }

    # Write outputs
    write_csv(output_dir / "per_case_results.csv", per_case_results)
    write_json(output_dir / "summary.json", summary)
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
        write_csv(
            output_dir / "candidate_diagnostics.csv",
            diagnostic_rows,
            diag_fieldnames,
            quoting=csv.QUOTE_NONNUMERIC,
        )

    # Write recovery/regression lists
    with (output_dir / "v1_recovered_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in v1_recovered:
            f.write(f"{case_id}\n")
    with (output_dir / "v1_regressed_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in v1_regressed:
            f.write(f"{case_id}\n")
    with (output_dir / "guarded_recovered_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in guarded_recovered:
            f.write(f"{case_id}\n")
    with (output_dir / "guarded_regressed_case_ids.txt").open("w", encoding="utf-8") as f:
        for case_id in guarded_regressed:
            f.write(f"{case_id}\n")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total cases: {total_cases}")
    print(f"\nBaseline ({BASELINE_METHOD}): {baseline_gold_count}/{total_cases} ({baseline_rate:.2%})")
    print(f"V1 ({V1_METHOD}): {v1_gold_count}/{total_cases} ({v1_rate:.2%})")
    print(f"  Delta: {v1_gold_count - baseline_gold_count:+d} | Recovered: {len(v1_recovered)} | Regressed: {len(v1_regressed)}")
    print(f"Guarded ({GUARDED_METHOD}): {guarded_gold_count}/{total_cases} ({guarded_rate:.2%})")
    print(f"  Delta: {guarded_gold_count - baseline_gold_count:+d} | Recovered: {len(guarded_recovered)} | Regressed: {len(guarded_regressed)}")
    print("=" * 80)
    print(f"Output saved to: {output_dir}")


if __name__ == "__main__":
    main()
