#!/usr/bin/env python3
"""Artifact-only cross-provider (OpenAI + Cohere) real-model main-run audit."""

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
OUTPUTS = REPO_ROOT / "outputs"
DOCS = REPO_ROOT / "docs"
SLURM_LOGS = REPO_ROOT / "logs" / "slurm"

MAIN_OPENAI_STAMP = "20260424T_OPENAI_REAL_MAIN"
MAIN_COHERE_STAMP = "20260424T_COHERE_REAL_MAIN"

EXPECTED_CONTRACT = {
    "openai": {"model": "gpt-4.1-mini"},
    "cohere": {"model": "command-r-plus-08-2024"},
    "datasets": ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"],
    "budgets": [4, 6, 8],
    "seeds": [11, 23],
    "subset_size": 20,
    "methods": ["strict_f3", "strict_gate1_cap_k6", "strict_f2", "external_l1_max", "self_consistency_3"],
}


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


def _group_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return mean(valid)


def _dataset_slug(dataset: str) -> str:
    return dataset.replace("/", "_")


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
    openai_audit_dirs = sorted(OUTPUTS.glob("openai_real_model_main_run_audit_*"))
    canonical_openai_dirs = sorted(
        p for p in OUTPUTS.glob(f"canonical_real_model_validation_*{MAIN_OPENAI_STAMP}*") if p.is_dir()
    )
    canonical_cohere_dirs = sorted(
        p for p in OUTPUTS.glob(f"canonical_real_model_validation_*{MAIN_COHERE_STAMP}*") if p.is_dir()
    )
    doc_files = sorted(list(DOCS.glob("*OPENAI*REAL_MODEL*.md")) + list(DOCS.glob("*COHERE*REAL_MODEL*.md")))
    slurm_logs = sorted(
        list(SLURM_LOGS.glob("*openai*real*main*.*")) + list(SLURM_LOGS.glob("*cohere*real*main*.*"))
    )
    return {
        "openai_audit_dirs": openai_audit_dirs,
        "canonical_openai_dirs": canonical_openai_dirs,
        "canonical_cohere_dirs": canonical_cohere_dirs,
        "doc_files": doc_files,
        "slurm_logs": slurm_logs,
    }


def load_examples(canonical_dirs: Iterable[Path]) -> List[ExampleRow]:
    rows: List[ExampleRow] = []
    seen = set()
    for run_dir in canonical_dirs:
        p = run_dir / "per_example_rows.csv"
        if not p.exists():
            continue
        with p.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                provider = row.get("provider", "").lower()
                if provider not in {"openai", "cohere"}:
                    continue
                key = (
                    provider,
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
                        provider=provider,
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


def missing_or_incomplete_rows(canonical_dirs: Dict[str, List[Path]]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    expected_rows = EXPECTED_CONTRACT["subset_size"] * len(EXPECTED_CONTRACT["methods"])
    for provider in ("openai", "cohere"):
        stamp = MAIN_OPENAI_STAMP if provider == "openai" else MAIN_COHERE_STAMP
        by_name = {d.name: d for d in canonical_dirs[provider]}
        for dataset in EXPECTED_CONTRACT["datasets"]:
            dslug = _dataset_slug(dataset)
            for seed in EXPECTED_CONTRACT["seeds"]:
                for budget in EXPECTED_CONTRACT["budgets"]:
                    dirname = f"canonical_real_model_validation_{stamp}_{provider}_{seed}_{budget}_{dslug}"
                    dpath = by_name.get(dirname)
                    issues: List[str] = []
                    n_rows = 0
                    n_methods = 0
                    if dpath is None:
                        issues.append("missing_output_directory")
                    else:
                        if not (dpath / "manifest.json").exists():
                            issues.append("missing_manifest")
                        p = dpath / "per_example_rows.csv"
                        if not p.exists():
                            issues.append("missing_per_example_rows")
                        else:
                            with p.open(newline="", encoding="utf-8") as handle:
                                rows = list(csv.DictReader(handle))
                            n_rows = len(rows)
                            methods = {r.get("method", "") for r in rows}
                            n_methods = len(methods)
                            if n_rows < expected_rows:
                                issues.append(f"insufficient_scored_examples:{n_rows}<{expected_rows}")
                            if n_methods < len(EXPECTED_CONTRACT["methods"]):
                                issues.append(
                                    f"insufficient_methods:{n_methods}<{len(EXPECTED_CONTRACT['methods'])}"
                                )
                                missing = [m for m in EXPECTED_CONTRACT["methods"] if m not in methods]
                                if missing:
                                    issues.append(f"missing_methods:{'|'.join(missing)}")

                    out.append(
                        {
                            "provider": provider,
                            "model": EXPECTED_CONTRACT[provider]["model"],
                            "dataset": dataset,
                            "seed": seed,
                            "budget": budget,
                            "subset_size_expected": EXPECTED_CONTRACT["subset_size"],
                            "n_scored_examples": n_rows,
                            "n_methods_found": n_methods,
                            "is_missing_or_incomplete": int(bool(issues)),
                            "issues": "|".join(issues) if issues else "ok",
                            "expected_output_dir": f"outputs/{dirname}",
                        }
                    )
    return out


def write_summary_by_provider_dataset_budget_method(out_path: Path, examples: List[ExampleRow]) -> None:
    groups: Dict[Tuple[str, str, str, str, str, str, str], List[ExampleRow]] = defaultdict(list)
    for row in examples:
        groups[(row.provider, row.model, row.dataset, row.budget, row.seed, row.method, "20")].append(row)

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "provider",
            "model",
            "dataset",
            "budget",
            "seed",
            "subset_size_expected",
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
            provider, model, dataset, budget, seed, method, subset = key
            rows = groups[key]
            n = len(rows)
            writer.writerow(
                {
                    "provider": provider,
                    "model": model,
                    "dataset": dataset,
                    "budget": budget,
                    "seed": seed,
                    "subset_size_expected": subset,
                    "method": method,
                    "n_evaluated_examples": n,
                    "accuracy": sum(r.is_correct for r in rows) / n if n else 0.0,
                    "absent_from_tree_rate": sum(r.absent_from_tree for r in rows) / n if n else 0.0,
                    "output_layer_mismatch_rate": sum(r.output_layer_mismatch for r in rows) / n if n else 0.0,
                    "retry_error_count": None,
                    "mean_actions": _group_mean(r.actions_used for r in rows),
                    "mean_expansions": _group_mean(r.expansions for r in rows),
                    "mean_latency_seconds": None,
                    "mean_prompt_tokens": None,
                    "mean_completion_tokens": None,
                }
            )


def write_summary_by_provider_method(out_path: Path, examples: List[ExampleRow]) -> None:
    groups: Dict[Tuple[str, str, str], List[ExampleRow]] = defaultdict(list)
    for row in examples:
        groups[(row.provider, row.model, row.method)].append(row)

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "provider",
            "model",
            "method",
            "subset_size_expected",
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
            rows = groups[key]
            n = len(rows)
            writer.writerow(
                {
                    "provider": provider,
                    "model": model,
                    "method": method,
                    "subset_size_expected": EXPECTED_CONTRACT["subset_size"],
                    "n_evaluated_examples": n,
                    "datasets_covered": "|".join(sorted({r.dataset for r in rows})),
                    "budgets_covered": "|".join(sorted({r.budget for r in rows}, key=lambda b: int(b))),
                    "seeds_covered": "|".join(sorted({r.seed for r in rows}, key=lambda s: int(s))),
                    "accuracy": sum(r.is_correct for r in rows) / n if n else 0.0,
                    "absent_from_tree_rate": sum(r.absent_from_tree for r in rows) / n if n else 0.0,
                    "output_layer_mismatch_rate": sum(r.output_layer_mismatch for r in rows) / n if n else 0.0,
                    "mean_actions": _group_mean(r.actions_used for r in rows),
                    "mean_expansions": _group_mean(r.expansions for r in rows),
                }
            )


def provider_claim(examples: List[ExampleRow], provider: str) -> Dict[str, object]:
    rows = [r for r in examples if r.provider == provider]
    m: Dict[str, List[ExampleRow]] = defaultdict(list)
    for r in rows:
        m[r.method].append(r)

    def acc(rr: List[ExampleRow]) -> Optional[float]:
        return (sum(x.is_correct for x in rr) / len(rr)) if rr else None

    strict_f3 = acc(m["strict_f3"])
    gate = acc(m["strict_gate1_cap_k6"])
    ext = acc(m["external_l1_max"])
    frontier_rows = m["strict_f3"] + m["strict_gate1_cap_k6"] + m["strict_f2"]
    frontier = acc(frontier_rows)

    a = strict_f3 is not None and gate is not None and strict_f3 > gate
    b = frontier is not None and ext is not None and frontier > ext
    c = a and not b
    d = "headline-safe" if b else ("appendix-only" if c else "not-usable-for-dominance-claims")
    return {
        "A": {"answer": "yes" if a else "no", "strict_f3_accuracy": strict_f3, "strict_gate1_cap_k6_accuracy": gate},
        "B": {"answer": "yes" if b else "no", "frontier_accuracy": frontier, "external_l1_max_accuracy": ext},
        "C": {"answer": "yes" if c else "no"},
        "D": {"answer": d},
    }


def build_claim_safety(examples: List[ExampleRow]) -> Dict[str, object]:
    openai = provider_claim(examples, "openai")
    cohere = provider_claim(examples, "cohere")
    agree = (
        openai["A"]["answer"] == cohere["A"]["answer"]
        and openai["B"]["answer"] == cohere["B"]["answer"]
        and openai["D"]["answer"] == cohere["D"]["answer"]
    )
    return {
        "openai": openai,
        "cohere": cohere,
        "questions": {
            "A_strict_f3_dominates_strict_gate1_cap_k6": {
                "openai": openai["A"]["answer"],
                "cohere": cohere["A"]["answer"],
            },
            "B_frontier_allocation_dominates_external_l1_max": {
                "openai": openai["B"]["answer"],
                "cohere": cohere["B"]["answer"],
            },
            "C_frontier_competitive_not_dominant": {
                "openai": openai["C"]["answer"],
                "cohere": cohere["C"]["answer"],
            },
            "D_recommended_disposition": {
                "openai": openai["D"]["answer"],
                "cohere": cohere["D"]["answer"],
            },
            "E_openai_and_cohere_agree_or_conflict": {"answer": "agree" if agree else "conflict"},
        },
        "n_total_evaluated_rows": len(examples),
        "cross_provider_recommendation": (
            "appendix-only"
            if (openai["D"]["answer"] != "headline-safe" and cohere["D"]["answer"] != "headline-safe")
            else "headline-safe"
        ),
    }


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_status(path: Path, claim: Dict[str, object], sources: Dict[str, List[Path]], gaps: List[Dict[str, object]]) -> None:
    q = claim["questions"]
    text = f"""# Cross-provider real-model main-run audit status

- A (`strict_f3` dominates `strict_gate1_cap_k6`): OpenAI={q["A_strict_f3_dominates_strict_gate1_cap_k6"]["openai"]}, Cohere={q["A_strict_f3_dominates_strict_gate1_cap_k6"]["cohere"]}
- B (frontier-allocation dominates `external_l1_max`): OpenAI={q["B_frontier_allocation_dominates_external_l1_max"]["openai"]}, Cohere={q["B_frontier_allocation_dominates_external_l1_max"]["cohere"]}
- C (competitive not dominant): OpenAI={q["C_frontier_competitive_not_dominant"]["openai"]}, Cohere={q["C_frontier_competitive_not_dominant"]["cohere"]}
- D (disposition): OpenAI={q["D_recommended_disposition"]["openai"]}, Cohere={q["D_recommended_disposition"]["cohere"]}
- E (agreement): **{q["E_openai_and_cohere_agree_or_conflict"]["answer"]}**

## Coverage
- OpenAI canonical dirs: {len(sources["canonical_openai_dirs"])}
- Cohere canonical dirs: {len(sources["canonical_cohere_dirs"])}
- OpenAI audit dirs: {len(sources["openai_audit_dirs"])}
- Docs inspected: {len(sources["doc_files"])}
- Slurm logs inspected: {len(sources["slurm_logs"])}
- Missing/incomplete slices: {sum(int(r['is_missing_or_incomplete']) for r in gaps)}

Cross-provider recommendation: **{claim["cross_provider_recommendation"]}**
"""
    path.write_text(text, encoding="utf-8")


def write_doc(path: Path, timestamp: str, claim: Dict[str, object], gaps: List[Dict[str, object]]) -> None:
    q = claim["questions"]
    missing = [r for r in gaps if int(r["is_missing_or_incomplete"]) == 1]
    gap_text = (
        "\n".join(f"- `{r['provider']}` `{r['dataset']}` seed `{r['seed']}` budget `{r['budget']}`: {r['issues']}" for r in missing)
        if missing
        else "- None."
    )
    text = f"""# Cross-provider real-model main-run audit ({timestamp})

## Contract checked
- Providers/models: `openai/gpt-4.1-mini`, `cohere/command-r-plus-08-2024`
- Datasets: `{EXPECTED_CONTRACT["datasets"]}`
- Budgets: `{EXPECTED_CONTRACT["budgets"]}`
- Seeds: `{EXPECTED_CONTRACT["seeds"]}`
- Subset size: `{EXPECTED_CONTRACT["subset_size"]}`
- Methods: `{EXPECTED_CONTRACT["methods"]}`

## Claim-safety answers
- A: OpenAI={q["A_strict_f3_dominates_strict_gate1_cap_k6"]["openai"]}, Cohere={q["A_strict_f3_dominates_strict_gate1_cap_k6"]["cohere"]}
- B: OpenAI={q["B_frontier_allocation_dominates_external_l1_max"]["openai"]}, Cohere={q["B_frontier_allocation_dominates_external_l1_max"]["cohere"]}
- C: OpenAI={q["C_frontier_competitive_not_dominant"]["openai"]}, Cohere={q["C_frontier_competitive_not_dominant"]["cohere"]}
- D: OpenAI={q["D_recommended_disposition"]["openai"]}, Cohere={q["D_recommended_disposition"]["cohere"]}
- E: **{q["E_openai_and_cohere_agree_or_conflict"]["answer"]}**

## Missing or incomplete slices
{gap_text}

## Safe interpretation
Real-model evidence is appendix-only unless both providers consistently establish frontier-allocation dominance over `external_l1_max`. Current safe framing is competitive and diagnostically informative, not universally dominant.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit cross-provider real-model main-run artifacts.")
    parser.add_argument("--timestamp", default=_now_utc_stamp())
    args = parser.parse_args()
    timestamp = args.timestamp

    out_dir = OUTPUTS / f"cross_provider_real_model_main_run_audit_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = discover_sources()

    examples = load_examples(sources["canonical_openai_dirs"] + sources["canonical_cohere_dirs"])
    if not examples:
        raise SystemExit("No canonical OpenAI/Cohere real-model examples found.")

    write_summary_by_provider_dataset_budget_method(
        out_dir / "cross_provider_summary_by_provider_dataset_budget_method.csv", examples
    )
    write_summary_by_provider_method(out_dir / "cross_provider_summary_by_provider_method.csv", examples)

    gaps = missing_or_incomplete_rows(
        {"openai": sources["canonical_openai_dirs"], "cohere": sources["canonical_cohere_dirs"]}
    )
    write_csv(out_dir / "missing_or_incomplete_slices.csv", gaps)

    claim = build_claim_safety(examples)
    (out_dir / "cross_provider_claim_safety_assessment.json").write_text(
        json.dumps(claim, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_status(out_dir / "STATUS.md", claim, sources, gaps)

    doc_path = DOCS / f"CROSS_PROVIDER_REAL_MODEL_MAIN_RUN_AUDIT_{timestamp}.md"
    write_doc(doc_path, timestamp, claim, gaps)
    print(json.dumps({"status": "ok", "out_dir": str(out_dir), "doc_path": str(doc_path)}, indent=2))


if __name__ == "__main__":
    main()
