#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator
from experiments.data import normalize_answer_text
from experiments.frontier_matrix_core import build_frontier_strategies, load_pilot_examples
from experiments.output_layer_repair import canonicalize_answer, choose_repair_answer

STRICT_F3 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1"
STRICT_GATE1_CAP_K6 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control"
STRICT_F2 = "broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1"

METHODS: dict[str, dict[str, Any]] = {
    "strict_f3": {"runtime": STRICT_F3, "enable_output_repair": True},
    "strict_gate1_cap_k6": {"runtime": STRICT_GATE1_CAP_K6, "enable_output_repair": True},
    "strict_f3_anti_collapse_weak_v1": {"runtime": "strict_f3_anti_collapse_weak_v1", "enable_output_repair": True},
    "strict_f2": {"runtime": STRICT_F2, "enable_output_repair": True},
    "external_l1_max": {"runtime": "external_l1_max", "enable_output_repair": True},
    "self_consistency_3": {"runtime": "self_consistency_3", "enable_output_repair": True},
}

DEFAULT_PROVIDERS = "cohere"
DEFAULT_DATASETS = "openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024"
DEFAULT_METHODS = "strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,self_consistency_3"
DEFAULT_BUDGETS = "4,6,8"
DEFAULT_SEEDS = "11,23"


@dataclass(frozen=True)
class CaseKey:
    dataset: str
    seed: int
    budget: int
    method: str
    example_id: str


class ObservedGenerator:
    def __init__(self, base: APIBranchGenerator) -> None:
        self.base = base
        self.registry: dict[str, Any] = {}

    def init_branch(self, branch_id: str) -> Any:
        b = self.base.init_branch(branch_id)
        self.registry[b.branch_id] = b
        return b

    def expand(self, branch: Any, question: str, gold_answer: str) -> Any:
        return self.base.expand(branch, question, gold_answer)

    def verify(self, branch: Any, question: str) -> Any:
        return self.base.verify(branch, question)

    def prune(self, branch: Any) -> Any:
        return self.base.prune(branch)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real-model cost-normalized validation (provider-aware, resumable)")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--providers", default=DEFAULT_PROVIDERS)
    p.add_argument("--provider", default="", help="Deprecated alias for single-provider runs.")
    p.add_argument("--cohere-model", default="command-r-plus-08-2024")
    p.add_argument("--openai-model", default="gpt-4o-mini")
    p.add_argument("--datasets", default=DEFAULT_DATASETS)
    p.add_argument("--budgets", default=DEFAULT_BUDGETS)
    p.add_argument("--seeds", default=DEFAULT_SEEDS)
    p.add_argument("--methods", default=DEFAULT_METHODS)
    p.add_argument("--target-scored-per-slice", type=int, default=100)
    p.add_argument("--max-examples", type=int, default=0, help="Max attempted examples per dataset/seed/budget/method slice; 0=use target")
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument("--max-output-tokens", type=int, default=220)
    p.add_argument("--timeout-seconds", type=int, default=45)
    p.add_argument("--input-cost-per-1k", type=float, default=0.003)
    p.add_argument("--output-cost-per-1k", type=float, default=0.015)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--summarize-only", action="store_true", help="Skip new API calls and only recompute aggregate artifacts from existing records.")
    p.add_argument("--output-root", default="outputs")
    return p.parse_args()


def parse_csv_list(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def parse_csv_ints(text: str) -> list[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as f:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
            else:
                f.write("")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def mean(vals: list[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def classify_failure(error_text: str) -> str:
    t = error_text.lower()
    if "401" in t or "unauthorized" in t or "invalid api" in t:
        return "authentication failure"
    if "quota" in t or "insufficient" in t:
        return "quota failure"
    if "429" in t or "rate" in t:
        return "rate limit"
    if "timed out" in t or "network" in t or "temporary failure" in t:
        return "network error"
    if "model" in t and ("not found" in t or "unavailable" in t):
        return "model unavailable"
    return "other"


def normalize_providers(args: argparse.Namespace) -> list[str]:
    if args.provider:
        providers = [args.provider]
    else:
        providers = parse_csv_list(args.providers)
    normed = [p.strip().lower() for p in providers if p.strip()]
    allowed = {"cohere", "openai"}
    bad = [p for p in normed if p not in allowed]
    if bad:
        raise ValueError(f"Unsupported provider(s): {bad}; allowed={sorted(allowed)}")
    if not normed:
        raise ValueError("At least one provider is required.")
    return normed


def ensure_cohere_readiness(*, model: str, timestamp: str) -> tuple[bool, str]:
    key = os.getenv("COHERE_API_KEY", "")
    checked = ["COHERE_API_KEY"]
    status = "present" if key else "missing_or_empty"
    if not key:
        err = "COHERE_API_KEY is missing or empty"
        report_path = write_readiness_failure_report(
            timestamp=timestamp,
            checked_envs=checked,
            env_state={"COHERE_API_KEY": status},
            failure_type="missing key",
            command_attempted="python scripts/run_cohere_real_model_cost_normalized_validation.py ...",
            error_message=err,
            remediation="Set COHERE_API_KEY to a valid Cohere API key and rerun.",
        )
        print("Cohere experiment cancelled before execution because Cohere API access was not usable.")
        print(f"Failure report: {report_path}")
        return False, err

    try:
        import cohere  # type: ignore
    except ModuleNotFoundError:
        install_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "cohere"]
        subprocess.run(install_cmd, check=False)
        try:
            import cohere  # type: ignore # noqa: F401
        except Exception as exc:  # noqa: BLE001
            err = f"Module import failed after installation attempt: {type(exc).__name__}: {str(exc)[:500]}"
            report_path = write_readiness_failure_report(
                timestamp=timestamp,
                checked_envs=checked,
                env_state={"COHERE_API_KEY": status},
                failure_type="SDK/import problem",
                command_attempted="python -m pip install --upgrade cohere && tiny cohere chat request",
                error_message=err,
                remediation="Ensure pip install succeeds in this runtime and rerun readiness.",
            )
            print("Cohere experiment cancelled before execution because Cohere API access was not usable.")
            print(f"Failure report: {report_path}")
            return False, err

    cmd = [
        sys.executable,
        "-c",
        (
            "import os,cohere;"
            "c=cohere.ClientV2(api_key=os.environ['COHERE_API_KEY']);"
            f"r=c.chat(model='{model}',messages=[{{'role':'user','content':'Reply with exactly: OK'}}],max_tokens=4);"
            "print('READINESS_OK',bool(r))"
        ),
    ]
    probe = subprocess.run(cmd, capture_output=True, text=True)
    if probe.returncode != 0:
        err = (probe.stderr or probe.stdout or "unknown readiness failure")[:1000]
        report_path = write_readiness_failure_report(
            timestamp=timestamp,
            checked_envs=checked,
            env_state={"COHERE_API_KEY": status},
            failure_type=classify_failure(err),
            command_attempted=" ".join(cmd),
            error_message=err,
            remediation="Verify key validity/permissions/quota/network/model availability and rerun.",
        )
        print("Cohere experiment cancelled before execution because Cohere API access was not usable.")
        print(f"Failure report: {report_path}")
        return False, err
    print("Cohere readiness check passed: tiny authenticated request succeeded.")
    return True, "ok"


def ensure_openai_readiness(*, timestamp: str) -> tuple[bool, str]:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return False, "OPENAI_API_KEY is missing or empty"
    cmd = [
        sys.executable,
        "-c",
        "import os; assert os.environ.get('OPENAI_API_KEY'); print('READINESS_OK', True)",
    ]
    probe = subprocess.run(cmd, capture_output=True, text=True)
    if probe.returncode != 0:
        err = (probe.stderr or probe.stdout or "unknown readiness failure")[:1000]
        return False, err
    return True, "ok"


def write_readiness_failure_report(
    *,
    timestamp: str,
    checked_envs: list[str],
    env_state: dict[str, str],
    failure_type: str,
    command_attempted: str,
    error_message: str,
    remediation: str,
) -> str:
    docs = REPO_ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    path = docs / f"COHERE_API_READINESS_FAILURE_{timestamp}.md"
    lines = [
        "# Cohere API Readiness Failure Report",
        "",
        f"- Timestamp (UTC): {timestamp}",
        "",
        "## 1) Environment variables checked (names only)",
        *[f"- `{x}`" for x in checked_envs],
        "",
        "## 2) Presence status",
        *[f"- `{k}`: {v}" for k, v in env_state.items()],
        "",
        "## 3) Failure type",
        f"- {failure_type}",
        "",
        "## 4) Exact command attempted",
        "```bash",
        command_attempted,
        "```",
        "",
        "## 5) Sanitized exception/error message",
        "```text",
        error_message.replace(os.getenv("COHERE_API_KEY", ""), "[REDACTED]") if os.getenv("COHERE_API_KEY") else error_message,
        "```",
        "",
        "## 6) What must be fixed before rerunning",
        f"- {remediation}",
        "",
        "## 7) Cancellation line",
        "**Cohere experiment cancelled before execution because Cohere API access was not usable.**",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path.relative_to(REPO_ROOT))


def to_case_key(row: dict[str, Any]) -> CaseKey:
    provider = str(row.get("provider", "cohere"))
    method = str(row["method"])
    scoped_method = method if method.startswith(f"{provider}:") else f"{provider}:{method}"
    return CaseKey(
        dataset=str(row["dataset"]),
        seed=int(row["seed"]),
        budget=int(row["budget"]),
        method=scoped_method,
        example_id=str(row["example_id"]),
    )


def load_existing_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def evaluate_example(result: Any, dataset: str, gold_answer: str, final_nodes: list[dict[str, Any]], enable_output_repair: bool) -> int:
    md = result.metadata or {}
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=md.get("selected_group"),
        dataset=dataset,
        enable_rescue=bool(enable_output_repair),
    )
    surfaced_can = canonicalize_answer(repaired.get("surfaced_final_answer_raw"), dataset=dataset)
    gold_can = canonicalize_answer(gold_answer, dataset=dataset)
    return int(bool(surfaced_can == gold_can and surfaced_can is not None))


def evaluate_with_diagnostics(
    result: Any,
    dataset: str,
    gold_answer: str,
    final_nodes: list[dict[str, Any]],
    enable_output_repair: bool,
) -> dict[str, Any]:
    md = result.metadata or {}
    repaired = choose_repair_answer(
        final_nodes=final_nodes,
        selected_group_hint=md.get("selected_group"),
        dataset=dataset,
        enable_rescue=bool(enable_output_repair),
    )
    surfaced_raw = repaired.get("surfaced_final_answer_raw")
    surfaced_can = canonicalize_answer(surfaced_raw, dataset=dataset)
    gold_can = canonicalize_answer(gold_answer, dataset=dataset)
    exact_match = int(bool(surfaced_can == gold_can and surfaced_can is not None))
    gold_in_tree = int(any(n.get("predicted_answer_normalized") == gold_can for n in final_nodes))
    parse_failure = int(not exact_match and surfaced_can is None)
    if exact_match:
        failure_tag = "correct"
    elif parse_failure:
        failure_tag = "parse/extraction failure"
    elif not gold_in_tree:
        failure_tag = "correct answer absent from explored tree"
    elif gold_in_tree:
        failure_tag = "correct answer present but not selected"
    else:
        failure_tag = "unknown"
    return {
        "exact_match": exact_match,
        "gold_answer_canonical": gold_can,
        "surfaced_final_answer_raw": surfaced_raw,
        "surfaced_final_answer_canonical": surfaced_can,
        "chosen_final_node_answer_raw": repaired.get("chosen_final_node_answer_raw"),
        "chosen_final_node_answer_canonical": repaired.get("chosen_final_node_answer_canonical"),
        "gold_in_tree": gold_in_tree,
        "parse_extraction_failure": parse_failure,
        "failure_tag": failure_tag,
    }


def bootstrap_paired_ci(diffs: list[float], n_boot: int = 1000, seed: int = 7) -> tuple[float, float]:
    if not diffs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(diffs)
    boots = []
    for _ in range(n_boot):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boots.append(sum(sample) / len(sample))
    boots.sort()
    lo = boots[int(0.025 * (len(boots) - 1))]
    hi = boots[int(0.975 * (len(boots) - 1))]
    return (float(lo), float(hi))


def main() -> None:
    args = parse_args()
    providers = normalize_providers(args)
    datasets = parse_csv_list(args.datasets)
    budgets = parse_csv_ints(args.budgets)
    seeds = parse_csv_ints(args.seeds)
    methods = parse_csv_list(args.methods)
    for m in methods:
        if m not in METHODS:
            raise ValueError(f"Unknown method: {m}")

    model_by_provider = {
        "cohere": args.cohere_model,
        "openai": args.openai_model,
    }
    provider_status: dict[str, dict[str, str]] = {}
    if args.summarize_only:
        provider_status = {p: {"ready": "1", "reason": "summarize_only"} for p in providers}
    else:
        for provider in providers:
            if provider == "cohere":
                ok, reason = ensure_cohere_readiness(model=model_by_provider["cohere"], timestamp=args.timestamp)
            else:
                ok, reason = ensure_openai_readiness(timestamp=args.timestamp)
            provider_status[provider] = {"ready": "1" if ok else "0", "reason": reason}

    if (not args.summarize_only) and all(s["ready"] != "1" for s in provider_status.values()):
        print("No configured provider is ready; exiting without API execution.")
        raise SystemExit(1)

    out_dir = REPO_ROOT / args.output_root / f"cohere_real_model_cost_normalized_validation_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    per_example_path = out_dir / "per_example_records.jsonl"

    existing = load_existing_records(per_example_path) if (args.resume or args.summarize_only) else []
    seen = {to_case_key(r) for r in existing}
    records = list(existing)

    api_keys = {
        "cohere": os.getenv("COHERE_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
    }
    dataset_load_failures: dict[tuple[str, str, int], str] = {}
    runtime_missing: set[tuple[str, str, int, int, str]] = set()

    if not args.summarize_only:
        for provider in providers:
            if provider_status[provider]["ready"] != "1":
                continue
            for dataset in datasets:
                for seed in seeds:
                    target_n = args.target_scored_per_slice
                    max_attempt = args.max_examples if args.max_examples > 0 else target_n
                    pool_n = max(max_attempt, target_n)
                    try:
                        examples = load_pilot_examples(dataset, subset_size=pool_n, seed=seed)
                    except Exception as exc:  # noqa: BLE001
                        dataset_load_failures[(provider, dataset, seed)] = f"{type(exc).__name__}: {str(exc)[:500]}"
                        continue
                    for budget in budgets:
                        rng = random.Random(1000003 * seed + 97 * budget + len(dataset))

                        def factory() -> Any:
                            return ObservedGenerator(
                                APIBranchGenerator(
                                    provider=provider,
                                    api_key=api_keys[provider],
                                    model=model_by_provider[provider],
                                    temperature=args.temperature,
                                    max_tokens=args.max_output_tokens,
                                    timeout_seconds=args.timeout_seconds,
                                )
                            )

                        specs = build_frontier_strategies(
                            factory,
                            budget,
                            [1],
                            rng,
                            use_openai_api=(provider == "openai"),
                            include_broad_diversity_aggregation_methods=True,
                            include_external_l1_baseline=True,
                            include_external_s1_baseline=True,
                        )

                        for method in methods:
                            runtime = METHODS[method]["runtime"]
                            enable_repair = bool(METHODS[method]["enable_output_repair"])
                            if runtime not in specs:
                                runtime_missing.add((provider, dataset, seed, budget, method))
                                continue
                            attempted = 0
                            scored = 0
                            for ex in examples:
                                if attempted >= max_attempt or scored >= target_n:
                                    break
                                ck = CaseKey(dataset=dataset, seed=seed, budget=budget, method=f"{provider}:{method}", example_id=str(ex.example_id))
                                if ck in seen:
                                    continue
                                attempted += 1
                                t0 = time.perf_counter()
                                controller = specs[runtime]
                                if hasattr(controller, "generator") and hasattr(controller.generator, "base") and hasattr(controller.generator.base, "reset_usage_counters"):
                                    controller.generator.base.reset_usage_counters()
                                status = "scored"
                                err_text = ""
                                retry_attempts = 0
                                in_tok = 0
                                out_tok = 0
                                total_tok = 0
                                exact_match = 0
                                eval_diag: dict[str, Any] = {}
                                result_metadata: dict[str, Any] = {}
                                final_nodes: list[dict[str, Any]] = []
                                try:
                                    result = controller.run(ex.question, ex.answer)
                                    latency = time.perf_counter() - t0
                                    obs = controller.generator
                                    result_metadata = dict(getattr(result, "metadata", {}) or {})
                                    if hasattr(obs, "registry"):
                                        for _, b in sorted(obs.registry.items(), key=lambda kv: kv[0]):
                                            reasoning_text = "\n".join(str(x) for x in getattr(b, "steps", [])) if getattr(b, "steps", None) else ""
                                            pred = b.predicted_answer
                                            pred_norm = normalize_answer_text(str(pred) if pred is not None else None).get("normalized_answer")
                                            final_nodes.append(
                                                {
                                                    "branch_id": b.branch_id,
                                                    "reasoning_text": reasoning_text,
                                                    "predicted_answer": pred,
                                                    "predicted_answer_normalized": pred_norm,
                                                }
                                            )
                                    eval_diag = evaluate_with_diagnostics(result, dataset, str(ex.answer), final_nodes, enable_repair)
                                    exact_match = int(eval_diag["exact_match"])
                                    scored += 1
                                    if hasattr(controller, "generator") and hasattr(controller.generator, "base") and hasattr(controller.generator.base, "snapshot_usage_counters"):
                                        usage = controller.generator.base.snapshot_usage_counters()
                                        in_tok = int(usage.get("input_tokens", 0))
                                        out_tok = int(usage.get("output_tokens", 0))
                                        total_tok = int(usage.get("total_tokens", in_tok + out_tok))
                                        retry_attempts = int(usage.get("retry_attempts", 0))
                                except Exception as exc:  # noqa: BLE001
                                    latency = time.perf_counter() - t0
                                    status = "failed"
                                    err_text = f"{type(exc).__name__}: {str(exc)[:800]}"

                                cost = (in_tok / 1000.0) * args.input_cost_per_1k + (out_tok / 1000.0) * args.output_cost_per_1k
                                row = {
                                    "provider": provider,
                                    "model": model_by_provider[provider],
                                    "dataset": dataset,
                                    "seed": seed,
                                    "budget": budget,
                                    "method": method,
                                    "example_id": str(ex.example_id),
                                    "status": status,
                                    "error": err_text,
                                    "exact_match": int(exact_match),
                                    "question": str(ex.question),
                                    "gold_answer": str(ex.answer),
                                    "gold_answer_canonical": eval_diag.get("gold_answer_canonical"),
                                    "final_answer_raw": eval_diag.get("surfaced_final_answer_raw"),
                                    "final_answer_canonical": eval_diag.get("surfaced_final_answer_canonical"),
                                    "selected_answer_raw": eval_diag.get("chosen_final_node_answer_raw"),
                                    "selected_answer_canonical": eval_diag.get("chosen_final_node_answer_canonical"),
                                    "gold_in_tree": int(eval_diag.get("gold_in_tree", 0)),
                                    "parse_extraction_failure": int(eval_diag.get("parse_extraction_failure", 0)),
                                    "failure_tag": (eval_diag.get("failure_tag") if status == "scored" else "API/runtime failure"),
                                    "result_metadata": result_metadata if status == "scored" else {},
                                    "final_nodes": final_nodes if status == "scored" else [],
                                    "attempted": 1,
                                    "scored": int(status == "scored"),
                                    "failed": int(status == "failed"),
                                    "skipped": 0,
                                    "retry_attempts": int(retry_attempts),
                                    "input_tokens": int(in_tok),
                                    "output_tokens": int(out_tok),
                                    "total_tokens": int(total_tok),
                                    "latency_seconds": float(round(latency, 6)),
                                    "estimated_cost_usd": float(cost),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                                append_jsonl(per_example_path, row)
                                records.append(row)
                                seen.add(ck)
                                if status == "failed":
                                    append_jsonl(raw_dir / "failures.jsonl", row)

    slices: dict[tuple[str, str, int, int, str], list[dict[str, Any]]] = {}
    for r in records:
        key = (str(r.get("provider", "cohere")), str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["method"]))
        slices.setdefault(key, []).append(r)

    expected_slices = [(p, d, s, b, m) for p in providers for d in datasets for s in seeds for b in budgets for m in methods]
    slice_rows: list[dict[str, Any]] = []
    incomplete_rows: list[dict[str, Any]] = []
    for (provider, dataset, seed, budget, method) in expected_slices:
        rows = slices.get((provider, dataset, seed, budget, method), [])
        attempted = sum(int(x.get("attempted", 0)) for x in rows)
        scored = sum(int(x.get("scored", 0)) for x in rows)
        failed = sum(int(x.get("failed", 0)) for x in rows)
        skipped = sum(int(x.get("skipped", 0)) for x in rows)
        retries = sum(int(x.get("retry_attempts", 0)) for x in rows)
        acc_float = mean([float(x.get("exact_match", 0)) for x in rows if int(x.get("scored", 0)) == 1])
        in_tok = sum(int(x.get("input_tokens", 0)) for x in rows)
        out_tok = sum(int(x.get("output_tokens", 0)) for x in rows)
        tot_tok = sum(int(x.get("total_tokens", 0)) for x in rows)
        lat = sum(float(x.get("latency_seconds", 0.0)) for x in rows)
        cost = sum(float(x.get("estimated_cost_usd", 0.0)) for x in rows)
        target_n = args.target_scored_per_slice
        incomplete = scored < target_n
        if provider_status[provider]["ready"] != "1":
            reason = "provider_unavailable"
        elif (provider, dataset, seed) in dataset_load_failures:
            reason = "dataset_loading_failure"
        elif (provider, dataset, seed, budget, method) in runtime_missing:
            reason = "runtime_missing"
        elif not rows:
            reason = "missing_slice_zero_records"
        elif failed > 0 and scored == 0:
            reason = "api_failures"
        elif incomplete:
            reason = "insufficient_scored_examples"
        else:
            reason = "target_reached"
        row = {
            "provider": provider,
            "model": model_by_provider[provider],
            "dataset": dataset,
            "seed": seed,
            "budget": budget,
            "method": method,
            "attempted_examples": attempted,
            "successfully_scored_examples": scored,
            "skipped_examples": skipped,
            "failed_examples": failed,
            "retry_counts": retries,
            "accuracy": ("NA" if scored == 0 else acc_float),
            "exact_match": ("NA" if scored == 0 else acc_float),
            "total_input_tokens": in_tok,
            "total_output_tokens": out_tok,
            "total_tokens": tot_tok,
            "mean_input_tokens_per_scored_example": (in_tok / scored) if scored else 0.0,
            "mean_output_tokens_per_scored_example": (out_tok / scored) if scored else 0.0,
            "mean_total_tokens_per_scored_example": (tot_tok / scored) if scored else 0.0,
            "total_latency_seconds": lat,
            "mean_latency_seconds_per_scored_example": (lat / scored) if scored else 0.0,
            "estimated_dollar_cost": cost,
            "accuracy_per_1k_tokens": (acc_float / (tot_tok / 1000.0)) if tot_tok > 0 and scored > 0 else 0.0,
            "accuracy_per_estimated_dollar": (acc_float / cost) if cost > 0 and scored > 0 else 0.0,
            "incomplete_slice": int(incomplete),
            "incomplete_reason": reason,
        }
        slice_rows.append(row)
        if incomplete or reason != "target_reached":
            incomplete_rows.append(row)

    write_csv(out_dir / "slice_summary.csv", slice_rows)

    by_method: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in slice_rows:
        by_method.setdefault((str(r["provider"]), str(r["method"])), []).append(r)
    method_rows = []
    cost_rows = []
    for (provider, m), rows in sorted(by_method.items()):
        scored = sum(int(x["successfully_scored_examples"]) for x in rows)
        tot_tok = sum(float(x["total_tokens"]) for x in rows)
        total_cost = sum(float(x["estimated_dollar_cost"]) for x in rows)
        avg_acc = mean([float(x["accuracy"]) for x in rows if str(x["accuracy"]) != "NA"])
        method_rows.append(
            {
                "provider": provider,
                "method": m,
                "n_slices": len(rows),
                "total_scored_examples": scored,
                "mean_accuracy_across_slices": avg_acc,
                "mean_total_tokens_per_scored_example": (tot_tok / scored) if scored else 0.0,
                "mean_latency_seconds_per_scored_example": mean([float(x["mean_latency_seconds_per_scored_example"]) for x in rows]),
                "estimated_total_cost_usd": total_cost,
            }
        )
        cost_rows.append(
            {
                "provider": provider,
                "method": m,
                "mean_accuracy": avg_acc,
                "accuracy_per_1k_tokens": (avg_acc / (tot_tok / 1000.0)) if tot_tok > 0 else 0.0,
                "accuracy_per_estimated_dollar": (avg_acc / total_cost) if total_cost > 0 else 0.0,
                "total_tokens": tot_tok,
                "estimated_total_cost_usd": total_cost,
            }
        )

    write_csv(out_dir / "method_summary.csv", method_rows)
    write_csv(out_dir / "cost_normalized_summary.csv", cost_rows)
    write_csv(out_dir / "incomplete_slices.csv", incomplete_rows, fieldnames=list(slice_rows[0].keys()) if slice_rows else None)

    per_group: dict[tuple[str, str, int, int, str], dict[str, int]] = {}
    for r in records:
        if int(r.get("scored", 0)) != 1:
            continue
        k = (str(r["provider"]), str(r["dataset"]), int(r["seed"]), int(r["budget"]), str(r["example_id"]))
        per_group.setdefault(k, {})[str(r["method"])] = int(r["exact_match"])

    def paired_rows(provider: str, a: str, b: str, label: str) -> list[dict[str, Any]]:
        diffs = []
        wins_a = 0
        wins_b = 0
        ties = 0
        for (p, _, _, _, _), m in per_group.items():
            if p != provider:
                continue
            if a in m and b in m:
                d = m[a] - m[b]
                diffs.append(float(d))
                if d > 0:
                    wins_a += 1
                elif d < 0:
                    wins_b += 1
                else:
                    ties += 1
        mdiff = mean(diffs)
        lo, hi = bootstrap_paired_ci(diffs)
        status = "evaluable" if diffs else "not_evaluable_zero_matched_examples"
        return [
            {
                "provider": provider,
                "comparison": label,
                "method_a": a,
                "method_b": b,
                "matched_examples": len(diffs),
                "mean_accuracy_delta_a_minus_b": ("NA" if not diffs else mdiff),
                "bootstrap95_low": ("NA" if not diffs else lo),
                "bootstrap95_high": ("NA" if not diffs else hi),
                "wins_a": wins_a,
                "wins_b": wins_b,
                "ties": ties,
                "comparison_status": status,
            }
        ]

    pairwise = []
    for provider in providers:
        pairwise.extend(paired_rows(provider, "strict_f3", "external_l1_max", "strict_f3_vs_external_l1_max"))
        pairwise.extend(paired_rows(provider, "strict_f3", "strict_gate1_cap_k6", "strict_f3_vs_strict_gate1_cap_k6"))
        fa_methods = [m for m in ["strict_f3", "strict_gate1_cap_k6", "strict_f2"] if (provider, m) in by_method]
        if fa_methods:
            best_fa = max(
                fa_methods,
                key=lambda m: mean([float(x["accuracy"]) for x in by_method[(provider, m)] if str(x["accuracy"]) != "NA"]),
            )
            pairwise.extend(paired_rows(provider, best_fa, "external_l1_max", "best_frontier_vs_external_l1_max"))
            if (provider, "self_consistency_3") in by_method:
                pairwise.extend(paired_rows(provider, best_fa, "self_consistency_3", "frontier_family_best_vs_self_consistency_3"))
    write_csv(out_dir / "pairwise_comparisons.csv", pairwise)

    pmap = {(r["provider"], r["comparison"]): r for r in pairwise}
    cohere_row = pmap.get(("cohere", "strict_f3_vs_external_l1_max"), {})
    cohere_evaluable = cohere_row.get("comparison_status") == "evaluable"
    cohere_delta = cohere_row.get("mean_accuracy_delta_a_minus_b", "NA")
    mixed = False
    for r in pairwise:
        if "external" not in str(r.get("comparison", "")) or r.get("comparison_status") != "evaluable":
            continue
        mixed = mixed or float(r.get("mean_accuracy_delta_a_minus_b", 0.0)) <= 0

    provider_answers = []
    for provider in providers:
        row = pmap.get((provider, "strict_f3_vs_external_l1_max"), {})
        if row.get("comparison_status") != "evaluable":
            verdict = "not_evaluable_zero_matched_examples"
            evidence = f"matched={int(row.get('matched_examples', 0))}"
        else:
            delta = float(row["mean_accuracy_delta_a_minus_b"])
            verdict = "yes" if delta > 0 else "no_or_mixed"
            evidence = f"delta={delta:+.4f}, matched={int(row['matched_examples'])}"
        provider_answers.append({"question": f"Under provider={provider}, does strict_f3 beat external_l1_max?", "answer": verdict, "evidence": evidence})

    claim_rows = [
        {
            "question": "Did Cohere produce an evaluable strict_f3 vs external_l1_max comparison?",
            "answer": "yes" if cohere_evaluable else "no",
            "evidence": f"matched={int(cohere_row.get('matched_examples', 0))}",
        },
        {
            "question": "If not, why not?",
            "answer": ("na_evaluable" if cohere_evaluable else str(cohere_row.get("comparison_status", "not_evaluable_zero_matched_examples"))),
            "evidence": f"delta={cohere_delta}",
        },
        {
            "question": "Was OpenAI fallback used?",
            "answer": "yes" if ("openai" in providers and provider_status.get("openai", {}).get("ready") == "1") else "no",
            "evidence": provider_status.get("openai", {}).get("reason", "not_requested"),
        },
        {
            "question": "Is the evidence still appendix-only, or strong enough for main-paper use?",
            "answer": "yes" if (not mixed and len(incomplete_rows) == 0) else "no_appendix_only",
            "evidence": f"incomplete_slices={len(incomplete_rows)}, mixed={mixed}",
        },
    ]
    claim_rows.extend(provider_answers)
    write_csv(out_dir / "claim_safety_table.csv", claim_rows)

    manifest = {
        "artifact_family": "cohere_real_model_cost_normalized_validation",
        "timestamp": args.timestamp,
        "providers": providers,
        "models": model_by_provider,
        "datasets": datasets,
        "budgets": budgets,
        "seeds": seeds,
        "methods": methods,
        "target_scored_per_slice": args.target_scored_per_slice,
        "max_examples": args.max_examples,
        "provider_status": provider_status,
        "pricing": {"input_cost_per_1k": args.input_cost_per_1k, "output_cost_per_1k": args.output_cost_per_1k},
        "outputs": [
            "manifest.json",
            "slice_summary.csv",
            "method_summary.csv",
            "cost_normalized_summary.csv",
            "pairwise_comparisons.csv",
            "incomplete_slices.csv",
            "claim_safety_table.csv",
            "per_example_records.jsonl",
            "raw/failures.jsonl",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    doc_path = REPO_ROOT / "docs" / f"COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION_{args.timestamp}.md"
    total_expected = len(expected_slices)
    completed = sum(1 for r in slice_rows if int(r["incomplete_slice"]) == 0)
    zero_records = sum(1 for r in slice_rows if int(r["attempted_examples"]) == 0)
    by_provider_counts = {p: {"completed": 0, "expected": 0} for p in providers}
    by_method_counts = {m: {"completed": 0, "expected": 0} for m in methods}
    by_dataset_counts = {d: {"completed": 0, "expected": 0} for d in datasets}
    for r in slice_rows:
        by_provider_counts[str(r["provider"])]["expected"] += 1
        by_method_counts[str(r["method"])]["expected"] += 1
        by_dataset_counts[str(r["dataset"])]["expected"] += 1
        if int(r["incomplete_slice"]) == 0:
            by_provider_counts[str(r["provider"])]["completed"] += 1
            by_method_counts[str(r["method"])]["completed"] += 1
            by_dataset_counts[str(r["dataset"])]["completed"] += 1
    acc_table = "\n".join(
        [
            f"- provider={r['provider']} method={r['method']}: mean_accuracy={float(r['mean_accuracy_across_slices']):.4f}, total_scored={int(r['total_scored_examples'])}"
            for r in method_rows
        ]
    )
    tok_table = "\n".join(
        [
            f"- provider={r['provider']} method={r['method']}: total_tokens={int(float(r['total_tokens']))}, estimated_total_cost_usd={float(r['estimated_total_cost_usd']):.6f}"
            for r in cost_rows
        ]
    )
    pair_table = "\n".join(
        [
            (
                f"- provider={r['provider']} {r['comparison']}: status={r['comparison_status']}, "
                f"delta={r['mean_accuracy_delta_a_minus_b']}, matched={int(r['matched_examples'])}"
            )
            for r in pairwise
        ]
    )
    claim_lines = "\n".join([f"- {r['question']} **{r['answer']}** ({r['evidence']})" for r in claim_rows])
    doc_lines = [
        "# COHERE_REAL_MODEL_COST_NORMALIZED_VALIDATION",
        "",
        f"- Timestamp: `{args.timestamp}`",
        f"- Exact command: `python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp {args.timestamp} --resume --max-examples {args.max_examples} --target-scored-per-slice {args.target_scored_per_slice}`",
        f"- Providers: `{providers}`",
        f"- Provider models: `{model_by_provider}`",
        f"- Datasets: `{datasets}`",
        f"- Budgets: `{budgets}`",
        f"- Seeds: `{seeds}`",
        f"- Methods: `{methods}`",
        f"- Sample-size target per slice: `{args.target_scored_per_slice}` (max-examples cap `{args.max_examples}`)",
        "",
        "## Completion status",
        f"- Total expected slices: `{total_expected}`",
        f"- Completed slices: `{completed}`",
        f"- Incomplete slices: `{total_expected - completed}`",
        f"- Zero-record slices: `{zero_records}`",
        "- Per-provider completion counts:",
        *[f"  - {p}: {c['completed']}/{c['expected']}" for p, c in sorted(by_provider_counts.items())],
        "- Per-method completion counts:",
        *[f"  - {m}: {c['completed']}/{c['expected']}" for m, c in sorted(by_method_counts.items())],
        "- Per-dataset completion counts:",
        *[f"  - {d}: {c['completed']}/{c['expected']}" for d, c in sorted(by_dataset_counts.items())],
        "",
        "## Staged status",
        f"- Stage 1 (GSM8K): {by_dataset_counts.get('openai/gsm8k', {}).get('completed', 0)}/{by_dataset_counts.get('openai/gsm8k', {}).get('expected', 0)} slices completed.",
        f"- Stage 2 (MATH-500): {by_dataset_counts.get('HuggingFaceH4/MATH-500', {}).get('completed', 0)}/{by_dataset_counts.get('HuggingFaceH4/MATH-500', {}).get('expected', 0)} slices completed.",
        f"- Stage 3 (AIME 2024): {by_dataset_counts.get('HuggingFaceH4/aime_2024', {}).get('completed', 0)}/{by_dataset_counts.get('HuggingFaceH4/aime_2024', {}).get('expected', 0)} slices completed.",
        f"- Provider status: {provider_status}",
        "",
        "## Main accuracy table",
        acc_table or "- (no rows)",
        "",
        "## Token/latency/cost table",
        tok_table or "- (no rows)",
        "",
        "## Cost-normalized performance table",
        "- See `cost_normalized_summary.csv` in artifact directory.",
        "",
        "## Paired comparison table",
        pair_table or "- (no pairwise rows)",
        "",
        "## Clear answers",
        claim_lines,
        "",
        "## Manuscript-safe wording",
        "- Treat Cohere evidence as bounded external-validity evidence under this matched setup.",
        "- If slices are incomplete or mixed, keep appendix-only / competitive-non-dominant framing.",
        "",
        "## Forbidden overclaim wording",
        "- Do not claim universal dominance across providers/datasets/budgets from this single Cohere run.",
        "",
        f"## Artifact directory\n- `outputs/cohere_real_model_cost_normalized_validation_{args.timestamp}/`",
    ]
    doc_path.write_text("\n".join(doc_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
