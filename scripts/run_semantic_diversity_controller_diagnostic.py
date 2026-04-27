#!/usr/bin/env python3
"""Offline and live Cohere diagnostics for semantic-diversity experimental controllers."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import random
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.data import PilotExample, extract_final_answer
from experiments.frontier_matrix_core import (
    build_frontier_strategies,
    build_semantic_diversity_diagnostic_registry,
    generator_factory_for_mode,
    load_pilot_examples,
)
from experiments.scoring import SimpleBranchScorer, ScoreConfig

STRICT_F3_RUNTIME = (
    "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_"
    "repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
)

METHODS_COMPARE = [
    "external_l1_max",
    "strict_f3",
    "semantic_minimum_maturation_frontier_v1_d2",
    "semantic_minimum_maturation_frontier_v1_d3",
    "direct_reserve_semantic_frontier_v1",
    "branching_necessity_gate_v1",
    "semantic_minimum_maturation_plus_direct_reserve_v1",
]

DEFAULT_LOSS_JSONL = (
    REPO_ROOT
    / "outputs"
    / "cohere_absent_from_tree_loss_diagnostics_20260427T171917Z"
    / "loss_cases_absent_from_tree.jsonl"
)


def _load_readiness():
    p = REPO_ROOT / "scripts" / "run_cohere_trace_complete_loss_subset.py"
    spec = importlib.util.spec_from_file_location("cohere_tr_read", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        if fieldnames:
            with path.open("w", encoding="utf-8", newline="") as f:
                csv.DictWriter(f, fieldnames=fieldnames).writeheader()
        return
    fn = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fn})


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _method_runtime_key(method: str) -> str:
    return STRICT_F3_RUNTIME if method == "strict_f3" else method


def _build_specs_for_budget(
    *,
    use_api: bool,
    model: str,
    budget: int,
    selection_seed: int,
    temperature: float,
    max_output_tokens: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    rng = random.Random(selection_seed + budget)
    factory = generator_factory_for_mode(
        use_openai_api=use_api,
        rng=rng,
        openai_model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        api_provider="cohere" if use_api else None,
    )
    specs = build_frontier_strategies(
        generator_factory=factory,
        budget=budget,
        adaptive_min_expand_grid=[1],
        rng=rng,
        use_openai_api=use_api,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
    )
    diag = build_semantic_diversity_diagnostic_registry(factory, SimpleBranchScorer(ScoreConfig()), budget)
    merged = {**specs, **diag}
    return merged


def _extract_semantic_row(meta: dict[str, Any]) -> dict[str, Any]:
    d = meta.get("diagnostic_semantic_diversity") or {}
    if not d and "global_diversity_aggregation" in str(meta.get("method_family", "")):
        d = {k: v for k, v in meta.items() if k in {"semantic_family_count", "family_redundancy_ratio"}}
    return {
        "semantic_family_count": d.get("semantic_family_count", ""),
        "family_redundancy_ratio": d.get("family_redundancy_ratio", ""),
        "root_branch_count": d.get("root_branch_count", ""),
        "branching_necessity_score": d.get("branching_necessity_score", ""),
    }


def _loss_row_has_question_and_gold(r: dict[str, Any]) -> bool:
    """Loss JSONL sometimes omits question/gold; skip those rows for live reruns."""
    q = str(r.get("question") or "").strip()
    g = str(r.get("gold_answer") or r.get("gold_answer_canonical") or "").strip()
    return len(q) >= 12 and len(g) >= 1


def _select_live_cases(
    loss_rows: list[dict[str, Any]],
    max_cases: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Prefer internal-wrong external-correct, confirmed absent-from-tree."""
    rng = random.Random(seed)
    pool = [
        r
        for r in loss_rows
        if str(r.get("internal_method_name", "")) == "strict_f3" and _loss_row_has_question_and_gold(r)
    ]
    scored: list[tuple[tuple[int, int, int], dict[str, Any]]] = []
    for r in pool:
        strict_ok = str(r.get("strict_f3_is_correct", r.get("internal_is_correct", ""))).lower() in {"1", "true", "yes"}
        ext_ok = str(r.get("external_l1_max_is_correct", r.get("external_is_correct", ""))).lower() in {
            "1",
            "true",
            "yes",
        }
        conf = 0 if str(r.get("absent_from_tree_status", "")) == "confirmed_absent_from_tree" else 1
        miss = 0 if "wrong" in str(r.get("strict_f3_is_correct", "")).lower() and ext_ok else 1
        pri = (miss, conf, 0)
        scored.append((pri, r))
    scored.sort(key=lambda x: (x[0], rng.random()))
    out = [r for _, r in scored[: max_cases * 3]]
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in out:
        eid = str(r.get("example_id", ""))
        if not eid or eid in seen:
            continue
        seen.add(eid)
        unique.append(r)
        if len(unique) >= max_cases:
            break
    return unique


def _examples_for_offline(n: int, seed: int) -> list[PilotExample]:
    return load_pilot_examples("openai/gsm8k", subset_size=n, seed=seed)


def _example_from_loss_row(r: dict[str, Any]) -> PilotExample:
    ga = str(r.get("gold_answer") or r.get("gold_answer_canonical") or r.get("answer") or "").strip() or "0"
    return PilotExample(
        example_id=str(r.get("example_id", "unknown")),
        question=str(r.get("question") or "").strip(),
        answer=extract_final_answer(ga),
    )


def run_offline(out_dir: Path, *, max_examples: int, seed: int, budgets: list[int]) -> None:
    missing = out_dir / "missing_data_report.md"
    ex = _examples_for_offline(max_examples, seed)
    if not ex:
        missing.write_text(
            "# Missing data (offline)\n\nCould not load HF pilot examples. "
            "Check network and `openai/gsm8k` availability, or re-run in an environment with dataset access.\n",
            encoding="utf-8",
        )
        return
    if len(ex) < 4:
        missing.write_text(
            "# Missing data (offline)\n\nToo few examples for a meaningful multi-method comparison. "
            "Increase subset or check dataset access.\n",
            encoding="utf-8",
        )

    per_case: list[dict[str, Any]] = []
    for b in budgets:
        specs = _build_specs_for_budget(
            use_api=False,
            model="command-r-plus-08-2024",
            budget=b,
            selection_seed=seed,
            temperature=0.2,
            max_output_tokens=512,
            timeout_seconds=60,
        )
        for ex0 in ex:
            for m in METHODS_COMPARE:
                key = _method_runtime_key(m)
                ctrl = specs.get(key)
                if ctrl is None:
                    per_case.append(
                        {
                            "mode": "offline",
                            "example_id": ex0.example_id,
                            "budget": b,
                            "method": m,
                            "error": "method_not_in_specs",
                        }
                    )
                    continue
                try:
                    res = ctrl.run(ex0.question, ex0.answer)
                    meta = res.metadata or {}
                    ds = _extract_semantic_row(meta)
                    ddiv = meta.get("diagnostic_semantic_diversity") or {}
                    per_case.append(
                        {
                            "mode": "offline",
                            "example_id": ex0.example_id,
                            "budget": b,
                            "method": m,
                            "is_correct": int(bool(res.is_correct)),
                            "prediction": str(res.prediction or ""),
                            "actions_used": res.actions_used,
                            "expansions": res.expansions,
                            "verifications": res.verifications,
                            "budget_exhausted": int(res.budget_exhausted),
                            "immediate_miss": int(
                                not bool(meta.get("gold_group_present_after_first_split", True)) and not bool(res.is_correct)
                            ),
                            "maturation_phase_len": len(ddiv.get("maturation_phase_audit", []) or []),
                            "commit_reason": str(meta.get("regime_failure_category", meta.get("early_divergence_failure_category", ""))),
                            "incumbent_replaced": meta.get("incumbent_replaced", ""),
                            "replacement_reason": str(meta.get("incumbent_replacement_reason", "")),
                            **ds,
                        }
                    )
                except Exception as e:  # noqa: BLE001
                    per_case.append(
                        {
                            "mode": "offline",
                            "example_id": ex0.example_id,
                            "budget": b,
                            "method": m,
                            "error": str(e)[:500],
                        }
                    )
    _write_csv(out_dir / "per_case_results.csv", per_case)
    _write_summaries(out_dir, per_case, mode="offline")


def _write_summaries(out_dir: Path, per_case: list[dict[str, Any]], *, mode: str) -> None:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_case:
        if r.get("error"):
            continue
        by_method[str(r.get("method", ""))].append(r)
    acc_rows = []
    for m, rows in by_method.items():
        n = max(1, len(rows))
        acc_rows.append(
            {
                "method": m,
                "n": len(rows),
                "accuracy": sum(int(x.get("is_correct", 0) or 0) for x in rows) / n,
                "avg_actions": sum(float(x.get("actions_used", 0) or 0) for x in rows) / n,
            }
        )
    _write_csv(out_dir / "method_accuracy_summary.csv", acc_rows)

    paired = []
    for r in per_case:
        if r.get("error"):
            continue
        eid, b = r.get("example_id"), r.get("budget")
        sf = next((x for x in by_method.get("strict_f3", []) if x.get("example_id") == eid and x.get("budget") == b), None)
        exl1 = next(
            (x for x in by_method.get("external_l1_max", []) if x.get("example_id") == eid and x.get("budget") == b), None
        )
        if sf and r.get("method") not in {"strict_f3", "external_l1_max"}:
            paired.append(
                {
                    "example_id": eid,
                    "budget": b,
                    "method": r.get("method"),
                    "delta_vs_strict_f3": int(r.get("is_correct", 0)) - int(sf.get("is_correct", 0)),
                    "delta_vs_external_l1_max": int(r.get("is_correct", 0)) - int(exl1.get("is_correct", 0)) if exl1 else "",
                }
            )
    _write_csv(out_dir / "paired_summary.csv", paired)

    # Semantic / audits (simplified)
    sem = [
        {**_extract_semantic_row({"diagnostic_semantic_diversity": r}), "method": r.get("method"), "example_id": r.get("example_id")}
        for r in per_case
        if not r.get("error")
    ]
    _write_csv(out_dir / "semantic_family_summary.csv", sem)
    _write_csv(
        out_dir / "maturation_phase_audit.csv",
        [
            {
                "example_id": r.get("example_id"),
                "budget": r.get("budget"),
                "method": r.get("method"),
                "maturation_phase_len": r.get("maturation_phase_len", ""),
            }
            for r in per_case
            if not r.get("error")
        ],
    )
    _write_csv(
        out_dir / "branching_necessity_audit.csv",
        [
            {
                "example_id": r.get("example_id"),
                "budget": r.get("budget"),
                "method": r.get("method"),
                "branching_necessity_score": r.get("branching_necessity_score", ""),
            }
            for r in per_case
            if not r.get("error")
        ],
    )
    _write_csv(
        out_dir / "incumbent_replacement_audit.csv",
        [
            {
                "example_id": r.get("example_id"),
                "budget": r.get("budget"),
                "method": r.get("method"),
                "incumbent_replaced": r.get("incumbent_replaced", ""),
                "replacement_reason": r.get("replacement_reason", ""),
            }
            for r in per_case
            if not r.get("error")
        ],
    )


def run_cohere_live(
    out_dir: Path,
    *,
    max_cases: int,
    allow_large: bool,
    model: str,
    budgets: list[int],
    loss_jsonl: Path,
    seed: int,
) -> tuple[bool, str]:
    if max_cases > 30 and not allow_large:
        return False, "refuse: max-cases>30 without --allow-large-run"
    rmod = _load_readiness()
    ok, fclass, _sm = rmod.run_readiness_check(model=model, smoke_timeout_seconds=45)
    if not ok:
        rmod.write_issue_report(
            out_dir=out_dir,
            timestamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            model=model,
            key_present=bool(os.getenv("COHERE_API_KEY")),
            failure_class=fclass,
            error_message=str(_sm.get("error", "")),
            rerun_command="python scripts/run_semantic_diversity_controller_diagnostic.py --mode cohere --run-live-cohere",
        )
        return False, f"readiness:{fclass}"

    rows = _read_jsonl(loss_jsonl)
    picked = _select_live_cases(rows, max_cases, seed)
    ex_list = [_example_from_loss_row(r) for r in picked]
    _write_jsonl(out_dir / "selected_cases.jsonl", picked)

    per_case: list[dict[str, Any]] = []
    run_exc: str | None = None
    try:
        for b in budgets:
            specs = _build_specs_for_budget(
                use_api=True,
                model=model,
                budget=b,
                selection_seed=seed,
                temperature=0.2,
                max_output_tokens=768,
                timeout_seconds=90,
            )
            for ex0 in ex_list:
                for m in METHODS_COMPARE:
                    key = _method_runtime_key(m)
                    ctrl = specs.get(key)
                    if ctrl is None:
                        per_case.append(
                            {
                                "mode": "cohere",
                                "example_id": ex0.example_id,
                                "budget": b,
                                "method": m,
                                "error": "method_not_in_specs",
                            }
                        )
                        continue
                    res = ctrl.run(ex0.question, ex0.answer)
                    meta = res.metadata or {}
                    dsem = meta.get("diagnostic_semantic_diversity") or {}
                    fmeta = (meta.get("frontier_metadata") or {}) if isinstance(meta.get("frontier_metadata"), dict) else {}
                    dsem2 = fmeta.get("diagnostic_semantic_diversity") or {}
                    per_case.append(
                        {
                            "mode": "cohere",
                            "example_id": ex0.example_id,
                            "budget": b,
                            "method": m,
                            "is_correct": int(bool(res.is_correct)),
                            "prediction": str(res.prediction or ""),
                            "actions_used": res.actions_used,
                            "expansions": res.expansions,
                            "verifications": res.verifications,
                            "budget_exhausted": int(res.budget_exhausted),
                            "semantic_family_count": dsem.get("semantic_family_count", "") or dsem2.get("semantic_family_count", ""),
                            "family_redundancy_ratio": dsem.get("family_redundancy_ratio", "")
                            or dsem2.get("family_redundancy_ratio", ""),
                            "branching_necessity_last": dsem.get("branching_necessity_score", "")
                            or dsem2.get("branching_necessity_score", ""),
                            "incumbent_replaced": meta.get("incumbent_replaced", ""),
                            "replacement_reason": str(meta.get("incumbent_replacement_reason", "")),
                        }
                    )
    except Exception as e:  # noqa: BLE001
        run_exc = traceback.format_exc()
        (out_dir / "run_failure_issue.md").write_text(
            f"# Run failure (post-readiness)\n\n```text\n{run_exc[:8000]}\n```\n", encoding="utf-8"
        )
        return False, "post_readiness_failure"

    _write_csv(out_dir / "per_case_results.csv", per_case)
    _write_summaries(out_dir, per_case, mode="cohere")
    # token/cost/latency placeholder — API generator may not expose consistently here
    _write_csv(
        out_dir / "token_cost_latency_summary.csv",
        [
            {
                "note": "Estimates: actions*64 as rough token proxy when API usage not in metadata; diagnostic only",
                "mode": "cohere",
            }
        ],
    )
    (out_dir / "failure_taxonomy.csv").write_text("category,count\n", encoding="utf-8")
    (out_dir / "absent_from_tree_rescue_audit.csv").write_text("example_id,method,rescue\n", encoding="utf-8")

    nxt = out_dir / "candidate_next_steps.md"
    nxt.write_text(
        "# Candidate next steps\n\n"
        "- This is a **diagnostic 10-case** run: do not treat as paper-ready.\n"
        "- If a variant shows consistent gains vs `strict_f3` on the paired summary, consider a 30-case run with "
        "`--allow-large-run`.\n"
        "- Cross-check `per_case_results.csv` and failure modes before any manuscript text changes.\n",
        encoding="utf-8",
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "diagnostic": True,
                "experimental_methods": [x for x in METHODS_COMPARE if x not in ("strict_f3", "external_l1_max")],
                "readiness": "passed",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return True, "ok"


def write_report_doc(out_dir: Path, ts: str) -> None:
    doc = REPO_ROOT / f"docs/SEMANTIC_DIVERSITY_CONTROLLER_DIAGNOSTIC_{ts}.md"
    doc.write_text(
        f"# Semantic diversity controller diagnostic ({ts})\n\n"
        "## Status\n\n"
        "Experimental / diagnostic only. A 10-case live Cohere run is **not** sufficient to support manuscript claims.\n\n"
        "## Questions (see CSVs in output dir)\n\n"
        "- Which variant had the best accuracy–cost tradeoff on `method_accuracy_summary.csv`?\n"
        "- Do semantic maturation variants increase `semantic_family_count` vs `strict_f3` in `per_case_results.csv`?\n"
        "- Do paired deltas in `paired_summary.csv` show improvement over `strict_f3` and movement toward `external_l1_max`?\n"
        "\n## Next experiment\n\n"
        "If a single variant is consistently better on **paired** accuracy vs `strict_f3` in two budgets, run 30 cases with "
        "`--allow-large-run` and the same case-selection policy.\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--mode", choices=["offline", "cohere"], default="offline")
    p.add_argument("--run-live-cohere", action="store_true", help="Required for real API in cohere mode.")
    p.add_argument("--max-cases", type=int, default=10)
    p.add_argument("--allow-large-run", action="store_true")
    p.add_argument("--selection-seed", type=int, default=31)
    p.add_argument("--model", default="command-r-plus-08-2024")
    p.add_argument("--budgets", default="4,6,8")
    p.add_argument("--loss-jsonl", default=str(DEFAULT_LOSS_JSONL))
    p.add_argument("--offline-examples", type=int, default=8)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ts = str(args.timestamp)
    out = REPO_ROOT / f"outputs/semantic_diversity_controller_diagnostic_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    budgets = [int(x) for x in str(args.budgets).split(",") if x.strip()]

    if args.mode == "offline":
        run_offline(out, max_examples=int(args.offline_examples), seed=int(args.selection_seed), budgets=budgets)
        (out / "missing_data_report.md").write_text(
            "# Offline data availability\n\n"
            "Offline mode uses the **local simulator** and freshly sampled GSM8K examples; it does not replay historical "
            "Cohere logs. Comparing new variants against archived Cohere runs requires a **live** `--mode cohere` re-run on "
            "the same `example_id` set (see `selected_cases.jsonl` in live mode).\n",
            encoding="utf-8",
        )
        _write_csv(out / "token_cost_latency_summary.csv", [{"mode": "offline", "note": "Simulated: no real API tokens"}])
        (out / "manifest.json").write_text(
            json.dumps({"mode": "offline", "diagnostic": True, "budgets": budgets}, indent=2) + "\n", encoding="utf-8"
        )
        (out / "selected_cases.jsonl").write_text("", encoding="utf-8")
        write_report_doc(out, ts)
        print(f"offline_ok out_dir={out}")
        return 0

    if args.mode == "cohere" and not args.run_live_cohere:
        (out / "cohere_api_key_issue.md").write_text(
            "# Cohere not run\n\nPass `--run-live-cohere` to enable live Cohere execution.\n", encoding="utf-8"
        )
        return 1

    ok, msg = run_cohere_live(
        out,
        max_cases=int(args.max_cases),
        allow_large=bool(args.allow_large_run),
        model=str(args.model),
        budgets=budgets,
        loss_jsonl=Path(str(args.loss_jsonl)),
        seed=int(args.selection_seed),
    )
    write_report_doc(out, ts)
    print(f"cohere_mode ok={ok} msg={msg} out_dir={out}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
