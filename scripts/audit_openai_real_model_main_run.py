#!/usr/bin/env python3
"""Artifact-only OpenAI real-model main-run audit.

Aggregates existing OpenAI main-run artifacts in-repo without issuing new API calls.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _to_int(value: Optional[str], default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Optional[str]) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ExampleRow:
    provider: str
    model: str
    dataset: str
    seed: str
    budget: str
    example_id: str
    method: str
    is_correct: int
    absent_from_tree: int
    output_layer_mismatch: int
    actions_used: Optional[float]
    expansions: Optional[float]


def discover_sources() -> Dict[str, List[Path]]:
    output_root = REPO_ROOT / "outputs"
    docs_root = REPO_ROOT / "docs"
    logs_root = REPO_ROOT / "logs" / "slurm"

    real_model_dirs = sorted(
        p
        for p in output_root.glob("real_model_ours_vs_external_validation_*OPENAI_REAL_MAIN*")
        if p.is_dir()
    )
    canonical_dirs = sorted(
        p
        for p in output_root.glob("canonical_real_model_validation_*OPENAI_REAL_MAIN*")
        if p.is_dir()
    )
    doc_files = sorted(
        list(docs_root.glob("*OPENAI*REAL_MODEL*.md")) + list(docs_root.glob("*REAL_MODEL*OPENAI*.md"))
    )
    slurm_logs = sorted(logs_root.glob("*openai*real*main*.*"))

    return {
        "real_model_dirs": real_model_dirs,
        "canonical_dirs": canonical_dirs,
        "doc_files": doc_files,
        "slurm_logs": slurm_logs,
    }


def load_run_contract(real_model_dirs: Iterable[Path]) -> Dict[str, object]:
    contracts: List[Dict[str, object]] = []
    for run_dir in real_model_dirs:
        cfg = run_dir / "run_config.json"
        if cfg.exists():
            contracts.append(json.loads(cfg.read_text(encoding="utf-8")))
    if not contracts:
        return {}
    # Use latest as canonical contract for this audit.
    return contracts[-1]


def load_retry_errors(real_model_dirs: Iterable[Path]) -> Dict[Tuple[str, str, str, str], int]:
    """Map (dataset, budget, seed, method) -> retry/error count."""
    counts: Dict[Tuple[str, str, str, str], int] = defaultdict(int)
    for run_dir in real_model_dirs:
        retry_csv = run_dir / "openai" / "retry_error_log.csv"
        if not retry_csv.exists():
            continue
        with retry_csv.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                key = (
                    row.get("dataset", ""),
                    str(row.get("budget", "")),
                    str(row.get("seed", "")),
                    row.get("method", ""),
                )
                counts[key] += 1
    return counts


def load_examples(real_model_dirs: Iterable[Path], canonical_dirs: Iterable[Path]) -> List[ExampleRow]:
    paths: List[Path] = []
    for run_dir in real_model_dirs:
        p = run_dir / "openai" / "per_example_rows.csv"
        if p.exists():
            paths.append(p)
    for run_dir in canonical_dirs:
        p = run_dir / "per_example_rows.csv"
        if p.exists():
            paths.append(p)

    rows: List[ExampleRow] = []
    seen = set()
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                key = (
                    row.get("provider", ""),
                    row.get("model", ""),
                    row.get("dataset", ""),
                    str(row.get("seed", "")),
                    str(row.get("budget", "")),
                    row.get("example_id", ""),
                    row.get("method", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    ExampleRow(
                        provider=row.get("provider", ""),
                        model=row.get("model", ""),
                        dataset=row.get("dataset", ""),
                        seed=str(row.get("seed", "")),
                        budget=str(row.get("budget", "")),
                        example_id=row.get("example_id", ""),
                        method=row.get("method", ""),
                        is_correct=_to_int(row.get("is_correct")),
                        absent_from_tree=_to_int(row.get("absent_from_tree")),
                        output_layer_mismatch=_to_int(row.get("output_layer_mismatch")),
                        actions_used=_to_float(row.get("actions_used")),
                        expansions=_to_float(row.get("expansions")),
                    )
                )
    return rows


def _group_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return mean(valid)


def write_summary_by_dataset_budget_method(
    out_path: Path,
    examples: List[ExampleRow],
    retry_counts: Dict[Tuple[str, str, str, str], int],
) -> None:
    groups: Dict[Tuple[str, str, str, str, str, str], List[ExampleRow]] = defaultdict(list)
    for row in examples:
        groups[(row.provider, row.model, row.dataset, row.budget, row.seed, row.method)].append(row)

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "provider",
            "model",
            "dataset",
            "budget",
            "seed",
            "method",
            "n_evaluated_examples",
            "accuracy",
            "absent_from_tree_rate",
            "output_layer_mismatch_rate",
            "retry_error_count",
            "mean_actions",
            "mean_expansions",
            "mean_latency_seconds",
            "mean_prompt_tokens",
            "mean_completion_tokens",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(groups.keys()):
            group_rows = groups[key]
            provider, model, dataset, budget, seed, method = key
            n = len(group_rows)
            writer.writerow(
                {
                    "provider": provider,
                    "model": model,
                    "dataset": dataset,
                    "budget": budget,
                    "seed": seed,
                    "method": method,
                    "n_evaluated_examples": n,
                    "accuracy": sum(r.is_correct for r in group_rows) / n if n else 0.0,
                    "absent_from_tree_rate": sum(r.absent_from_tree for r in group_rows) / n if n else 0.0,
                    "output_layer_mismatch_rate": sum(r.output_layer_mismatch for r in group_rows) / n if n else 0.0,
                    "retry_error_count": retry_counts.get((dataset, budget, seed, method), 0),
                    "mean_actions": _group_mean(r.actions_used for r in group_rows),
                    "mean_expansions": _group_mean(r.expansions for r in group_rows),
                    # Token/latency diagnostics are not available in these artifacts.
                    "mean_latency_seconds": None,
                    "mean_prompt_tokens": None,
                    "mean_completion_tokens": None,
                }
            )


def write_summary_by_method(out_path: Path, examples: List[ExampleRow]) -> None:
    groups: Dict[Tuple[str, str, str], List[ExampleRow]] = defaultdict(list)
    for row in examples:
        groups[(row.provider, row.model, row.method)].append(row)

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "provider",
            "model",
            "method",
            "n_evaluated_examples",
            "datasets_covered",
            "budgets_covered",
            "seeds_covered",
            "accuracy",
            "absent_from_tree_rate",
            "output_layer_mismatch_rate",
            "mean_actions",
            "mean_expansions",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(groups.keys()):
            provider, model, method = key
            group_rows = groups[key]
            n = len(group_rows)
            writer.writerow(
                {
                    "provider": provider,
                    "model": model,
                    "method": method,
                    "n_evaluated_examples": n,
                    "datasets_covered": "|".join(sorted({r.dataset for r in group_rows})),
                    "budgets_covered": "|".join(sorted({r.budget for r in group_rows}, key=lambda b: int(b))),
                    "seeds_covered": "|".join(sorted({r.seed for r in group_rows}, key=lambda s: int(s))),
                    "accuracy": sum(r.is_correct for r in group_rows) / n if n else 0.0,
                    "absent_from_tree_rate": sum(r.absent_from_tree for r in group_rows) / n if n else 0.0,
                    "output_layer_mismatch_rate": sum(r.output_layer_mismatch for r in group_rows) / n if n else 0.0,
                    "mean_actions": _group_mean(r.actions_used for r in group_rows),
                    "mean_expansions": _group_mean(r.expansions for r in group_rows),
                }
            )


def build_claim_safety(examples: List[ExampleRow]) -> Dict[str, object]:
    method_rows: Dict[str, List[ExampleRow]] = defaultdict(list)
    per_cell: Dict[Tuple[str, str, str], Dict[str, List[ExampleRow]]] = defaultdict(lambda: defaultdict(list))

    for row in examples:
        method_rows[row.method].append(row)
        per_cell[(row.dataset, row.seed, row.budget)][row.method].append(row)

    def acc(rows: List[ExampleRow]) -> Optional[float]:
        if not rows:
            return None
        return sum(r.is_correct for r in rows) / len(rows)

    strict_f3_acc = acc(method_rows["strict_f3"])
    gate_acc = acc(method_rows["strict_gate1_cap_k6"])
    ext_l1_acc = acc(method_rows["external_l1_max"])

    frontier_methods = {"strict_f3", "strict_gate1_cap_k6", "strict_f2"}
    frontier_rows = [r for m in frontier_methods for r in method_rows.get(m, [])]
    frontier_acc = acc(frontier_rows)

    strict_vs_gate_support = strict_f3_acc is not None and gate_acc is not None and strict_f3_acc > gate_acc
    frontier_dominates_external = frontier_acc is not None and ext_l1_acc is not None and frontier_acc > ext_l1_acc

    cell_wins = 0
    comparable_cells = 0
    for _, cell in per_cell.items():
        if "strict_f3" in cell and "external_l1_max" in cell:
            comparable_cells += 1
            if acc(cell["strict_f3"]) > acc(cell["external_l1_max"]):
                cell_wins += 1

    if frontier_dominates_external:
        headline_disposition = "headline-safe"
    elif strict_vs_gate_support and not frontier_dominates_external:
        headline_disposition = "appendix-only"
    else:
        headline_disposition = "not-usable-for-dominance-claims"

    return {
        "questions": {
            "A_strict_f3_dominates_strict_gate1_cap_k6": {
                "answer": "yes" if strict_vs_gate_support else "no",
                "strict_f3_accuracy": strict_f3_acc,
                "strict_gate1_cap_k6_accuracy": gate_acc,
            },
            "B_frontier_allocation_dominates_external_l1_max": {
                "answer": "yes" if frontier_dominates_external else "no",
                "frontier_accuracy": frontier_acc,
                "external_l1_max_accuracy": ext_l1_acc,
                "strict_f3_cell_win_rate_vs_external_l1_max": (
                    cell_wins / comparable_cells if comparable_cells else None
                ),
            },
            "C_frontier_competitive_not_dominant": {
                "answer": "yes" if (strict_vs_gate_support and not frontier_dominates_external) else "no",
            },
            "D_recommended_disposition": {"answer": headline_disposition},
        },
        "n_total_evaluated_rows": len(examples),
        "frontier_methods": sorted(frontier_methods),
        "dominance_note": (
            "OpenAI evidence should not be used to claim broad dominance over external_l1_max "
            "unless per-dataset/per-budget reruns produce materially different outcomes."
        ),
    }


def write_status_md(out_path: Path, claim_safety: Dict[str, object], sources: Dict[str, List[Path]]) -> None:
    q = claim_safety["questions"]
    status = f"""# OpenAI real-model main-run audit status

- A (`strict_f3` dominates `strict_gate1_cap_k6`): **{q["A_strict_f3_dominates_strict_gate1_cap_k6"]["answer"]}**
- B (frontier-allocation dominates `external_l1_max`): **{q["B_frontier_allocation_dominates_external_l1_max"]["answer"]}**
- C (frontier-allocation is competitive but not dominant): **{q["C_frontier_competitive_not_dominant"]["answer"]}**
- D (manuscript disposition): **{q["D_recommended_disposition"]["answer"]}**

## Artifact coverage

- OpenAI main-run directories: {len(sources["real_model_dirs"])}
- OpenAI canonical validation directories: {len(sources["canonical_dirs"])}
- OpenAI real-model docs inspected: {len(sources["doc_files"])}
- OpenAI Slurm logs inspected: {len(sources["slurm_logs"])}

## Guardrail

This audit is artifact-only and does not issue new OpenAI API calls.
"""
    out_path.write_text(status, encoding="utf-8")


def write_doc_md(
    out_path: Path,
    timestamp: str,
    sources: Dict[str, List[Path]],
    run_contract: Dict[str, object],
    claim_safety: Dict[str, object],
) -> None:
    q = claim_safety["questions"]
    rel = lambda p: str(p.relative_to(REPO_ROOT))
    source_lines = []
    for key in ("real_model_dirs", "canonical_dirs", "doc_files", "slurm_logs"):
        for p in sources[key]:
            source_lines.append(f"- `{rel(p)}`")

    provider_model = run_contract.get("models", {}).get("openai", "unknown")
    datasets = run_contract.get("datasets_active", run_contract.get("datasets_requested", []))
    budgets = run_contract.get("budgets", [])
    seeds = run_contract.get("seeds", [])
    subset_size = run_contract.get("subset_size", "unknown")
    methods = run_contract.get("methods_runnable", run_contract.get("methods_requested", []))

    recommendation = q["D_recommended_disposition"]["answer"]
    support_label = (
        "supports"
        if recommendation == "headline-safe"
        else ("partially supports" if recommendation == "appendix-only" else "weakens")
    )

    doc = f"""# OpenAI real-model main-run audit ({timestamp})

## Artifact sources inspected

{chr(10).join(source_lines)}

## OpenAI run contract

- Provider/model: `openai/{provider_model}`
- Datasets: `{datasets}`
- Budgets: `{budgets}`
- Seeds: `{seeds}`
- Subset size: `{subset_size}`
- Runnable methods: `{methods}`

## Main numerical summary (claim-safety focused)

- A (`strict_f3` > `strict_gate1_cap_k6`): **{q["A_strict_f3_dominates_strict_gate1_cap_k6"]["answer"]}**
- B (frontier-allocation > `external_l1_max`): **{q["B_frontier_allocation_dominates_external_l1_max"]["answer"]}**
- C (frontier competitive but not dominant): **{q["C_frontier_competitive_not_dominant"]["answer"]}**
- D (disposition): **{recommendation}**

## Manuscript interpretation

Current OpenAI real-model main-run evidence: **{support_label}** the strongest manuscript dominance framing.
Use this as a calibration signal, not a standalone headline claim.

## Recommended manuscript wording

“On the OpenAI real-model main-run slice (`gpt-4.1-mini`), our frontier-style methods remain competitive and improve over selected internal neighbors, but dominance over matched external baselines is not consistently observed. We therefore treat OpenAI real-model evidence as a robustness/appendix signal rather than a primary headline result.”

## Overclaim warning

If OpenAI outcomes remain mixed across datasets/budgets/seeds, do **not** claim generalized dominance over `external_l1_max` from this slice alone.
"""
    out_path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit OpenAI real-model main-run artifacts.")
    parser.add_argument("--timestamp", default=_now_utc_stamp())
    args = parser.parse_args()

    timestamp = args.timestamp
    out_dir = REPO_ROOT / "outputs" / f"openai_real_model_main_run_audit_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = discover_sources()
    run_contract = load_run_contract(sources["real_model_dirs"])
    retry_counts = load_retry_errors(sources["real_model_dirs"])
    examples = load_examples(sources["real_model_dirs"], sources["canonical_dirs"])
    if not examples:
        raise SystemExit("No OpenAI real-model main-run examples found to audit.")

    write_summary_by_dataset_budget_method(
        out_dir / "openai_summary_by_dataset_budget_method.csv",
        examples,
        retry_counts,
    )
    write_summary_by_method(out_dir / "openai_summary_by_method.csv", examples)

    claim_safety = build_claim_safety(examples)
    (out_dir / "openai_claim_safety_assessment.json").write_text(
        json.dumps(claim_safety, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_status_md(out_dir / "STATUS.md", claim_safety, sources)

    doc_path = REPO_ROOT / "docs" / f"OPENAI_REAL_MODEL_MAIN_RUN_AUDIT_{timestamp}.md"
    write_doc_md(doc_path, timestamp, sources, run_contract, claim_safety)

    print(json.dumps({"status": "ok", "out_dir": str(out_dir), "doc_path": str(doc_path)}, indent=2))


if __name__ == "__main__":
    main()
