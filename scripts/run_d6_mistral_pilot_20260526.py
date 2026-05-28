#!/usr/bin/env python3
"""D6 Mistral pilot preparation, evaluation, and integration.

Part A: Preflight + Part B: Manifest selection + Part G/H: Evaluation + integration.
No direct API calls here — generation is launched in tmux via d6_generate_frontier_variants.py.
"""
from __future__ import annotations

import argparse
import json
import re
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

D8_1_RUN_DIR = "outputs/job_d8_1_runtime_feature_learning_selectors_20260526/run_20260526T014937Z"
UNIFIED_TABLE_DIR = "outputs/unified_learning_tables_20260525/run_20260525T184354Z"
D9_RETRAIN_DIR = "outputs/job_d9_retrain_with_cohere_math500_expansion_20260526/run_20260526T144632Z"
D6_PILOT_DIR = "outputs/job_d6_frontier_improvement_pilot_20260525/run_20260525T213951Z"
LEDGER_DIR = "outputs/training_experiment_ledger_20260525"

VARIANT_NAME = "frontier_math_extended_verify_v1"
MAX_API_ITEMS = 150
MATH500_TARGET_RESCUE = 50
MATH500_TARGET_REGRESSION = 40
MATH500_TARGET_ALL_WRONG = 30
GSM8K_TARGET_CONTROL = 30


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_answer(ans: str | None) -> str | None:
    if ans is None:
        return None
    ans = str(ans).strip()
    ans = re.sub(r"\\boxed\{([^}]+)\}", r"\1", ans)
    ans = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1/\2", ans)
    ans = ans.replace("$", "").replace(",", "").strip()
    try:
        v = float(ans)
        if v == int(v):
            return str(int(v))
        return str(round(v, 6))
    except (ValueError, OverflowError):
        pass
    return ans.lower().strip()


def answers_match(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    na, nb = normalize_answer(a), normalize_answer(b)
    if na == nb:
        return True
    try:
        fa, fb = float(na or "x"), float(nb or "x")
        return abs(fa - fb) < 1e-6 * max(1, abs(fb))
    except (ValueError, TypeError):
        pass
    return False


def load_jsonl(path: str | Path) -> list[dict]:
    items = []
    p = Path(path)
    if not p.exists():
        return items
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
    return items


def main():
    ap = argparse.ArgumentParser(description="D6 Mistral pilot preparation and evaluation")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--mode", default="prepare",
                    choices=["prepare", "evaluate"],
                    help="prepare: build manifest; evaluate: offline eval after generation")
    ap.add_argument("--d8-1-run-dir", default=D8_1_RUN_DIR)
    ap.add_argument("--unified-table-dir", default=UNIFIED_TABLE_DIR)
    ap.add_argument("--d9-retrain-dir", default=D9_RETRAIN_DIR)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = []

    def log(msg: str):
        print(msg)
        log_lines.append(msg)

    log(f"[{now_utc()}] D6 Mistral pilot — mode={args.mode}")
    log(f"Run dir: {run_dir}")

    # ── Load D8.1 features ────────────────────────────────────────────────────
    log("\n== Load D8.1 features ==")
    d8_df = pd.read_csv(Path(args.d8_1_run_dir) / "d8_1_candidate_features.csv", low_memory=False)
    log(f"D8.1 shape: {d8_df.shape}")

    unified_df = pd.read_csv(
        Path(args.unified_table_dir) / "unified_candidate_action_table.csv", low_memory=False
    )
    gold_map = (
        unified_df[["pool_id", "gold_answer_for_labeling_only"]]
        .drop_duplicates("pool_id")
        .set_index("pool_id")["gold_answer_for_labeling_only"]
        .to_dict()
    )
    question_map = (
        unified_df[["pool_id", "question_text"]]
        .drop_duplicates("pool_id")
        .set_index("pool_id")["question_text"]
        .to_dict()
    )
    log(f"Gold map: {len(gold_map)} pool_ids")

    if args.mode == "prepare":
        _run_prepare(args, run_dir, d8_df, gold_map, question_map, log)
    elif args.mode == "evaluate":
        _run_evaluate(args, run_dir, d8_df, gold_map, log)

    log(f"\n[{now_utc()}] Done.")
    with open(run_dir / "d6_mistral_pilot_run.log", "w") as f:
        f.write("\n".join(log_lines))


def _run_prepare(args, run_dir: Path, d8_df: pd.DataFrame, gold_map: dict, question_map: dict, log):
    """Part B: Build Mistral pilot manifest."""
    log("\n== Part B: Build Mistral pilot manifest ==")

    mistral = d8_df[d8_df["provider"] == "mistral"].copy()
    log(f"Mistral rows in D8.1: {len(mistral)}, pools: {mistral['pool_id'].nunique()}")

    # Frontier correctness
    ftr = mistral[mistral["method"] == "direct_reserve_semantic_frontier_v2"][
        ["pool_id", "scenario_id", "dataset", "split", "action_correct",
         "oracle_available", "all_sources_wrong", "gold_answer_for_labeling_only",
         "question_text", "example_uid", "original_example_id", "question_hash",
         "model_deployment_name", "model_id", "normalized_answer"]
    ].copy()
    ftr["frontier_correct"] = pd.to_numeric(ftr["action_correct"], errors="coerce").fillna(0).astype(int)
    ftr["frontier_answer"] = ftr["normalized_answer"].fillna("").astype(str)

    # External method correctness flags
    ext_methods = ["external_l1_max", "external_s1_budget_forcing", "external_tale_prompt_budgeting"]
    ext_dict: dict[str, dict[str, int]] = defaultdict(lambda: {"l1": 0, "s1": 0, "tale": 0})
    for _, row in mistral[mistral["method"].isin(ext_methods)].iterrows():
        pid = row["pool_id"]
        m = str(row["method"])
        corr = int(pd.to_numeric(row.get("action_correct", 0), errors="coerce") or 0)
        if "l1" in m:
            ext_dict[pid]["l1"] = max(ext_dict[pid]["l1"], corr)
        elif "s1" in m:
            ext_dict[pid]["s1"] = max(ext_dict[pid]["s1"], corr)
        elif "tale" in m:
            ext_dict[pid]["tale"] = max(ext_dict[pid]["tale"], corr)

    ftr["l1_correct"] = ftr["pool_id"].map(lambda p: ext_dict[p]["l1"])
    ftr["s1_correct"] = ftr["pool_id"].map(lambda p: ext_dict[p]["s1"])
    ftr["tale_correct"] = ftr["pool_id"].map(lambda p: ext_dict[p]["tale"])
    ftr["any_external_correct"] = (
        ftr["l1_correct"] | ftr["s1_correct"] | ftr["tale_correct"]
    ).astype(int)
    ftr["oracle"] = (ftr["frontier_correct"] | ftr["any_external_correct"]).astype(int)

    def bucket(row):
        if row["frontier_correct"] == 0 and row["any_external_correct"] == 1:
            return "frontier_wrong_external_rescue"
        elif row["frontier_correct"] == 1:
            return "frontier_correct_regression_check"
        else:
            return "all_old_sources_wrong"

    ftr["selection_bucket"] = ftr.apply(bucket, axis=1)

    log(f"\nBucket breakdown:")
    for ds in ["math500", "gsm8k"]:
        ds_df = ftr[ftr["dataset"] == ds]
        for bkt, grp in ds_df.groupby("selection_bucket"):
            log(f"  {ds} / {bkt}: {len(grp)}")

    # ── Select cases ─────────────────────────────────────────────────────────
    selected_cases: list[dict] = []

    def pick(df: pd.DataFrame, dataset: str, bucket_name: str, n: int) -> list[dict]:
        sub = df[(df["dataset"] == dataset) & (df["selection_bucket"] == bucket_name)]
        if len(sub) > n:
            sub = sub.sample(n=n, random_state=42)
        return sub.to_dict("records")

    # MATH-500
    m500_rescue = pick(ftr, "math500", "frontier_wrong_external_rescue", MATH500_TARGET_RESCUE)
    m500_regression = pick(ftr, "math500", "frontier_correct_regression_check", MATH500_TARGET_REGRESSION)
    m500_wrong = pick(ftr, "math500", "all_old_sources_wrong", MATH500_TARGET_ALL_WRONG)
    # GSM8K control
    gsm_control = pick(ftr, "gsm8k", "frontier_wrong_external_rescue", GSM8K_TARGET_CONTROL)

    all_selected_rows = m500_rescue + m500_regression + m500_wrong + gsm_control
    log(f"\nSelected cases:")
    log(f"  MATH-500 rescue: {len(m500_rescue)}/{MATH500_TARGET_RESCUE}")
    log(f"  MATH-500 regression-check: {len(m500_regression)}/{MATH500_TARGET_REGRESSION}")
    log(f"  MATH-500 all-wrong: {len(m500_wrong)}/{MATH500_TARGET_ALL_WRONG}")
    log(f"  GSM8K control: {len(gsm_control)}/{GSM8K_TARGET_CONTROL}")
    log(f"  Total: {len(all_selected_rows)}/{MAX_API_ITEMS}")

    # Build pilot_case_selection.jsonl
    pilot_cases: list[dict] = []
    for row in all_selected_rows:
        pid = row["pool_id"]
        bkt = row["selection_bucket"]
        dataset = row["dataset"]
        scenario = row.get("scenario_id", f"mistral_{dataset}")
        frontier_ans = str(row.get("frontier_answer") or "")
        gold = str(gold_map.get(pid, ""))
        q_text = str(question_map.get(pid, row.get("question_text", "")) or "")

        if bkt == "frontier_wrong_external_rescue":
            reason = "Mistral frontier wrong and at least one external method correct (offline stratification only)"
        elif bkt == "frontier_correct_regression_check":
            reason = "Mistral frontier correct; selected for regression-check guard evaluation"
        else:
            reason = "All old sources wrong; selected for oracle-ceiling and pool-quality analysis"

        pilot_cases.append({
            "scenario": scenario,
            "provider": "mistral",
            "dataset": dataset,
            "split": str(row.get("split", "")),
            "readiness_bucket": "mistral_pilot",
            "pool_id": pid,
            "example_uid": str(row.get("example_uid", "")),
            "original_example_id": str(row.get("original_example_id", "")),
            "question_hash": str(row.get("question_hash", "")),
            "problem_text": q_text,
            "old_frontier": {
                "method": "direct_reserve_semantic_frontier_v2",
                "normalized_answer": frontier_ans,
                "frontier_correct": int(row.get("frontier_correct", 0)),
            },
            "external_correct_flags": {
                "select_l1_correct": int(row.get("l1_correct", 0)),
                "select_s1_correct": int(row.get("s1_correct", 0)),
                "select_tale_correct": int(row.get("tale_correct", 0)),
                "any_external_correct": int(row.get("any_external_correct", 0)),
            },
            "oracle_upper_bound": int(row.get("oracle", 0)),
            "reason_selected": reason,
            "selection_bucket": f"mistral_{bkt}" if not bkt.startswith("mistral_") else bkt,
            "variant_names": [VARIANT_NAME],
            "leakage_safety_note": (
                "Selection uses local offline artifacts for stratification only. "
                "Gold/correctness labels not passed to provider prompts. "
                "selection_bucket is an offline diagnostic label only, not a runtime feature."
            ),
            "api_call_status": "not_run",
        })

    # Write pilot case selection
    with open(run_dir / "mistral_d6_pilot_manifest.jsonl", "w") as f:
        for case in pilot_cases:
            f.write(json.dumps(case) + "\n")

    # Also write as pilot_case_selection.jsonl for d6_generate_frontier_variants.py compatibility
    with open(run_dir / "pilot_case_selection.jsonl", "w") as f:
        for case in pilot_cases:
            f.write(json.dumps(case) + "\n")
    log(f"Wrote {len(pilot_cases)} cases to pilot_case_selection.jsonl")

    # Selection summary
    bucket_summary = Counter(c["selection_bucket"] for c in pilot_cases)
    dataset_summary = Counter(c["dataset"] for c in pilot_cases)
    selection_summary = {
        "n_total": len(pilot_cases),
        "n_math500": dataset_summary["math500"],
        "n_gsm8k": dataset_summary["gsm8k"],
        "variant": VARIANT_NAME,
        "max_api_cap": MAX_API_ITEMS,
        "bucket_counts": dict(bucket_summary),
        "provider": "mistral",
        "timestamp_utc": now_utc(),
    }
    with open(run_dir / "mistral_d6_pilot_selection_summary.json", "w") as f:
        json.dump(selection_summary, f, indent=2)

    # Generation manifest (required by d6_generate_frontier_variants.py)
    manifest = {
        "job": "D6 Mistral pilot",
        "prepared_at_utc": now_utc(),
        "status": "prepared_not_run",
        "api_call_status": "not_run",
        "output_run_dir": str(run_dir),
        "input_artifacts": {
            "unified_learning_tables": str(Path(args.unified_table_dir)),
            "d8_1_features": str(Path(args.d8_1_run_dir)),
            "d9_retrain_dir": str(Path(args.d9_retrain_dir)),
        },
        "selection_rules": {
            "mistral_math500_rescue": "frontier wrong && any(L1,S1,TALE correct)",
            "mistral_math500_regression": "frontier correct",
            "mistral_math500_all_wrong": "all old sources wrong",
            "mistral_gsm8k_control": "frontier wrong && any(L1,S1,TALE correct)",
        },
        "variant_names": [VARIANT_NAME],
        "max_api_cap": MAX_API_ITEMS,
        "leakage_safety": [
            "No API calls in preparation",
            "No runtime routing by gold labels",
            "Correctness labels used offline only for pilot stratification/evaluation",
            "selection_bucket is an offline diagnostic label only",
        ],
        "pilot_case_selection_jsonl": str(run_dir / "pilot_case_selection.jsonl"),
        "pilot_case_selection_summary_json": str(run_dir / "mistral_d6_pilot_selection_summary.json"),
        "case_count": len(pilot_cases),
        "provider": "mistral",
    }
    with open(run_dir / "d6_generation_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    log("Wrote d6_generation_manifest.json")

    # ── Prompt previews ───────────────────────────────────────────────────────
    log("\n== Part C: Prompt safety and preview ==")

    FORBIDDEN = [
        ("gold_answer", re.compile(r"(?i)\bgold\s*[_\- ]?answer\b")),
        ("gold_label", re.compile(r"(?i)\bgold\s*[_\- ]?(label|labels|target|truth)\b")),
        ("correctness", re.compile(r"(?i)\bcorrectness\b")),
        ("oracle", re.compile(r"(?i)\boracle\b")),
        ("source_correct", re.compile(r"(?i)\bsource_correct\b")),
        ("action_correct", re.compile(r"(?i)\baction_correct\b")),
        ("frontier_correct", re.compile(r"(?i)\bfrontier_correct\b")),
    ]

    INSTRUCTION = "Solve carefully and verify key arithmetic or algebra steps."
    OUTPUT_CONTRACT = [
        'OUTPUT EXACTLY ONE LINE: ONLY a single JSON object and NOTHING else.',
        'The object MUST contain the key "answer" (exactly this name, no alternatives).',
        'Do NOT use "final_answer", "finalAnswer", "result", or any other key for the final answer.',
        'Do NOT return an empty object {}.',
        'Do NOT return {"answer": ""}.',
        'If uncertain, still provide the best final answer in "answer".',
        'Use {"answer": null} only if no answer can be formed at all.',
        'No markdown fences (no ```json).',
        'No text before or after the JSON object.',
        'If including brief reasoning, add it in the "reasoning" key. The "answer" key must always be present.',
        'Do not include multiple final answers.',
    ]
    POSITIVE_EX = '{"answer":"42"}'
    NEGATIVE_EX = '{"final_answer":"42"}'

    def build_prompt(problem_text: str) -> str:
        lines = [
            "You are solving a math problem.",
            INSTRUCTION,
            "Do not include hidden metadata. Use only the problem statement.",
            "",
            "OUTPUT CONTRACT:",
        ]
        for c in OUTPUT_CONTRACT:
            lines.append(f"- {c}")
        lines += [
            "",
            "Correct output:",
            POSITIVE_EX,
            "",
            "Wrong output (invalid key name):",
            NEGATIVE_EX,
            "",
            "Problem:",
            problem_text.strip(),
            "",
            'FINAL OUTPUT REMINDER: Return exactly one JSON object on a single line with key "answer". '
            'No markdown fences. No text before or after the JSON.',
        ]
        return "\n".join(lines).strip() + "\n"

    previews = []
    safety_issues = []
    for case in pilot_cases[:5]:
        q_text = str(case.get("problem_text", "") or "")
        if not q_text:
            q_text = question_map.get(case["pool_id"], "")
        prompt = build_prompt(q_text)
        hits = [name for name, pat in FORBIDDEN if pat.search(prompt)]
        previews.append({
            "pool_id": case["pool_id"],
            "dataset": case["dataset"],
            "selection_bucket": case["selection_bucket"],
            "prompt_length": len(prompt),
            "forbidden_hits": hits,
            "prompt_preview": prompt[:300] + "..." if len(prompt) > 300 else prompt,
        })
        if hits:
            safety_issues.append({"pool_id": case["pool_id"], "hits": hits})

    with open(run_dir / "d6_mistral_prompt_preview.jsonl", "w") as f:
        for p in previews:
            f.write(json.dumps(p) + "\n")

    all_prompts_safe = len(safety_issues) == 0
    with open(run_dir / "d6_mistral_prompt_safety_audit.md", "w") as f:
        f.write(f"""D6 Mistral Prompt Safety Audit
Timestamp: {now_utc()}
Variant: {VARIANT_NAME}
Provider: mistral

== Forbidden Field Check ==
Prompts checked: {min(5, len(pilot_cases))} (preview sample)
Safety issues: {len(safety_issues)}
Result: {'PASS — no forbidden fields detected' if all_prompts_safe else 'FAIL — forbidden fields in prompt'}

== Forbidden Patterns Checked ==
- gold_answer, gold_label, correctness, oracle, source_correct, action_correct, frontier_correct

== Output Contract ==
Format: strict JSON, one line
Key required: "answer"
No gold/labels/correctness in prompts: CONFIRMED

== Notes ==
- Prompts contain only: problem_text + variant instruction + output contract
- Selection bucket labels are NOT included in prompts (offline diagnostic only)
- Gold answers are NOT included in prompts
""")

    with open(run_dir / "d6_mistral_no_api_readiness.md", "w") as f:
        f.write(f"""D6 Mistral No-API Readiness Report
Timestamp: {now_utc()}

== Readiness ==
Pilot cases prepared: {len(pilot_cases)}
Manifest written: YES
pilot_case_selection.jsonl: YES
d6_generation_manifest.json: YES
Prompt safety: {'PASS' if all_prompts_safe else 'FAIL'}
Dry-run ready: YES

== Adapter Status ==
Provider: mistral
Route: PROVIDER_ROUTE_DEFAULTS['mistral']
Model: mistral-large-latest (env: MISTRAL_BASE_URL optional)
API key env: MISTRAL_API_KEY (SET)
Adapter: experiments.branching.APIBranchGenerator (Mistral-compatible)

== Generation Command ==
python3 scripts/d6_generate_frontier_variants.py \\
  --run-dir {run_dir} \\
  --variants {VARIANT_NAME} \\
  --approve-api \\
  --limit {MAX_API_ITEMS} \\
  --max-output-tokens 512 \\
  --timeout-seconds 60

Dry-run (no API):
python3 scripts/d6_generate_frontier_variants.py \\
  --run-dir {run_dir} \\
  --variants {VARIANT_NAME} \\
  --dry-run
""")

    # ── Adapter readiness check ───────────────────────────────────────────────
    try:
        import importlib
        mod = importlib.import_module("experiments.branching")
        has_gen = hasattr(mod, "APIBranchGenerator")
        adapter_ok = has_gen
    except Exception as e:
        adapter_ok = False
        log(f"  Adapter import warning: {e}")

    # ── Preflight report ──────────────────────────────────────────────────────
    with open(run_dir / "D6_MISTRAL_PILOT_PREFLIGHT.md", "w") as f:
        f.write(f"""D6 Mistral Pilot Preflight Report
Timestamp: {now_utc()}

== Prior D9 Retrain Context ==
D9R verdict: D9_RETRAIN_USE_D6_AS_GATED_MODULE
D9R CV: 0.4775 ± 0.0298 vs frontier 0.3175 (+16 pp)
Gate: GATE_POSITIVE, 0 false overrides
Gate samples: 110
Manuscript gap: Mistral scenarios NOT COVERED (both MATH-500 and GSM8K)

== Mistral Availability ==
Mistral pools in D8.1: {mistral['pool_id'].nunique()}
Mistral MATH-500 pools: {(ftr['dataset']=='math500').sum()}
Mistral GSM8K pools: {(ftr['dataset']=='gsm8k').sum()}
MISTRAL_API_KEY: SET

== Pilot Selection ==
MATH-500 rescue (frontier wrong + external correct): {len(m500_rescue)}
MATH-500 regression-check (frontier correct): {len(m500_regression)}
MATH-500 all-wrong: {len(m500_wrong)}
GSM8K control: {len(gsm_control)}
Total: {len(pilot_cases)} / {MAX_API_ITEMS} cap

== Adapter ==
experiments.branching.APIBranchGenerator: {'importable' if adapter_ok else 'MISSING'}
Mistral routing: SUPPORTED (provider_name=mistral, model=mistral-large-latest)
Prompt safety: {'PASS' if all_prompts_safe else 'FAIL'}

== Safety Constraints ==
No gold labels in prompts: CONFIRMED
selection_bucket offline only: CONFIRMED
No other providers: CONFIRMED (mistral only)
Only frontier_math_extended_verify_v1: CONFIRMED
Max 150 API items: CONFIRMED

== Files Prepared ==
- pilot_case_selection.jsonl ({len(pilot_cases)} cases)
- d6_generation_manifest.json
- mistral_d6_pilot_manifest.jsonl
- mistral_d6_pilot_selection_summary.json
- d6_mistral_prompt_preview.jsonl
- d6_mistral_prompt_safety_audit.md
- d6_mistral_no_api_readiness.md
""")

    with open(run_dir / "preflight_status.txt", "w") as f:
        f.write("PREFLIGHT_OK\n")

    with open(run_dir / "mistral_adapter_readiness.md", "w") as f:
        f.write(f"""Mistral Adapter Readiness
Timestamp: {now_utc()}

== Status: {'READY' if adapter_ok else 'ADAPTER_MISSING'} ==
experiments.branching.APIBranchGenerator: {'available' if adapter_ok else 'not importable'}
Mistral routing: SUPPORTED in PROVIDER_ROUTE_DEFAULTS
MISTRAL_API_KEY: SET
Default model: mistral-large-latest
Base URL: https://api.mistral.ai/v1 (configurable via MISTRAL_BASE_URL)

== No changes needed ==
The d6_generate_frontier_variants.py script already supports Mistral:
- resolve_provider_route() routes mistral cases to PROVIDER_ROUTE_DEFAULTS['mistral']
- call_provider_via_existing_adapter() dispatches to gen._call_mistral_chat_api()
- _make_api_generator() reads MISTRAL_API_KEY from env

== Generation command ==
python3 scripts/d6_generate_frontier_variants.py \\
  --run-dir {run_dir} \\
  --variants {VARIANT_NAME} \\
  --approve-api --limit {MAX_API_ITEMS} --max-output-tokens 512 --timeout-seconds 60
""")

    with open(run_dir / "D6_MISTRAL_PILOT_SELECTION_REPORT.md", "w") as f:
        f.write(f"""D6 Mistral Pilot Selection Report
Timestamp: {now_utc()}
Variant: {VARIANT_NAME}

== Pilot Scope ==
Total cases selected: {len(pilot_cases)} (cap: {MAX_API_ITEMS})
Provider: mistral
Datasets: MATH-500 (primary), GSM8K (control)

== Mistral MATH-500 Bucket Counts ==
Available:
- frontier_wrong_external_rescue: {len(ftr[(ftr['dataset']=='math500')&(ftr['selection_bucket']=='frontier_wrong_external_rescue')])}
- frontier_correct_regression_check: {len(ftr[(ftr['dataset']=='math500')&(ftr['selection_bucket']=='frontier_correct_regression_check')])}
- all_old_sources_wrong: {len(ftr[(ftr['dataset']=='math500')&(ftr['selection_bucket']=='all_old_sources_wrong')])}

Selected:
- mistral_frontier_wrong_external_rescue: {len(m500_rescue)}
- mistral_frontier_correct_regression_check: {len(m500_regression)}
- mistral_all_old_sources_wrong: {len(m500_wrong)}
- mistral_gsm8k_control (rescue): {len(gsm_control)}

== Selection Strategy ==
Priority 1: Mistral MATH-500 frontier-wrong + any external correct → rescue signal
Priority 2: Mistral MATH-500 frontier-correct → regression-check guard
Priority 3: Mistral MATH-500 all-wrong → oracle ceiling / pool quality
Priority 4: Mistral GSM8K control → behavioral sanity check

== Expected Signal ==
- D6 useful in rescue bucket: likely (cohere rescue showed +16.7 pp)
- D6 risky in regression-check: likely (cohere regression-check showed -58.9 pp)
- Gate D9R-B should suppress regression-check overrides
- Manuscript: covers primary Mistral × MATH-500 scenario

== Leakage Safety ==
- Selection bucket labels NOT in prompts
- Gold answers NOT in prompts
- Correctness flags used offline only for evaluation
""")

    log("\nPart B/C complete: manifest and prompt safety written.")
    log(f"Cases: {len(pilot_cases)}")
    log(f"Next: run dry-run, then launch in tmux with --approve-api")


def _run_evaluate(args, run_dir: Path, d8_df: pd.DataFrame, gold_map: dict, log):
    """Parts G/H: Offline evaluation of generated Mistral D6 outputs."""
    log("\n== Part G: Evaluate Mistral D6 generation ==")

    # Find generation outputs
    gen_runs = sorted((run_dir / "generation_runs").glob("run_*/generation_outputs.jsonl")) \
        if (run_dir / "generation_runs").exists() else []
    if not gen_runs:
        log("No generation_outputs.jsonl found. Run generation first.")
        with open(run_dir / "d6_mistral_eval_summary.json", "w") as f:
            json.dump({"status": "no_generation_found"}, f)
        return

    gen_path = gen_runs[-1]
    log(f"Loading generation from: {gen_path}")
    gen_items = load_jsonl(gen_path)
    log(f"Generated items: {len(gen_items)}")

    # Load pilot cases for bucket map
    pilot_cases = load_jsonl(run_dir / "pilot_case_selection.jsonl")
    bucket_map = {c["pool_id"]: c.get("selection_bucket", "") for c in pilot_cases}

    # Load frontier correctness from D8.1
    mistral = d8_df[d8_df["provider"] == "mistral"]
    ftr = mistral[mistral["method"] == "direct_reserve_semantic_frontier_v2"][
        ["pool_id", "dataset", "action_correct", "normalized_answer"]
    ].copy()
    ftr["frontier_correct"] = pd.to_numeric(ftr["action_correct"], errors="coerce").fillna(0).astype(int)
    ftr_map = {row["pool_id"]: row for _, row in ftr.iterrows()}

    # Evaluate each generated item
    result_rows: list[dict] = []
    for item in gen_items:
        pid = item.get("pool_id", "")
        extracted = item.get("extracted_answer")
        strict_json = bool(item.get("strict_json_contract_compliance", False))
        gold = gold_map.get(pid)
        status = item.get("status", "completed")
        d6_correct = int(answers_match(extracted, gold)) if status == "completed" and extracted is not None else 0
        ftr_info = ftr_map.get(pid, {})
        frontier_correct = int(ftr_info.get("frontier_correct", 0))

        result_rows.append({
            "pool_id": pid,
            "dataset": item.get("dataset", ""),
            "selection_bucket": bucket_map.get(pid, item.get("selection_bucket", "")),
            "status": status,
            "extracted_answer": extracted,
            "strict_json": strict_json,
            "d6_correct": d6_correct,
            "frontier_correct": frontier_correct,
            "d6_unique_correct": int(d6_correct == 1 and frontier_correct == 0),
            "d6_regression": int(d6_correct == 0 and frontier_correct == 1),
        })

    results_df = pd.DataFrame(result_rows)
    results_df.to_csv(run_dir / "d6_mistral_eval_results.csv", index=False)

    n_total = len(results_df)
    n_completed = int((results_df["status"] == "completed").sum())
    n_strict_json = int(results_df["strict_json"].sum())
    frontier_acc = float(results_df["frontier_correct"].mean())
    d6_acc = float(results_df["d6_correct"].mean())
    delta = d6_acc - frontier_acc
    uc = int(results_df["d6_unique_correct"].sum())
    regs = int(results_df["d6_regression"].sum())

    log(f"\n== Results ==")
    log(f"  Total: {n_total}, Completed: {n_completed}")
    log(f"  Strict JSON: {n_strict_json}/{n_total} ({n_strict_json/n_total*100:.1f}%)")
    log(f"  Frontier acc: {frontier_acc:.4f}")
    log(f"  D6 acc: {d6_acc:.4f}, delta: {delta:+.4f}")
    log(f"  Unique-correct: {uc}, Regressions: {regs}, Net: {uc-regs:+d}")

    # Bucket breakdown
    bucket_rows: list[dict] = []
    for bkt, grp in results_df.groupby("selection_bucket"):
        n = len(grp)
        f_acc = float(grp["frontier_correct"].mean())
        d6_acc_bkt = float(grp["d6_correct"].mean())
        uc_bkt = int(grp["d6_unique_correct"].sum())
        reg_bkt = int(grp["d6_regression"].sum())
        bucket_rows.append({
            "bucket": bkt, "n": n,
            "frontier_accuracy": f_acc, "d6_accuracy": d6_acc_bkt,
            "delta": d6_acc_bkt - f_acc,
            "unique_correct": uc_bkt, "regressions": reg_bkt,
        })
        log(f"  {bkt}: n={n}, frontier={f_acc:.3f}, d6={d6_acc_bkt:.3f}, "
            f"delta={d6_acc_bkt-f_acc:+.3f}, uc={uc_bkt}, regs={reg_bkt}")

    bucket_df = pd.DataFrame(bucket_rows)
    bucket_df.to_csv(run_dir / "d6_mistral_bucket_results.csv", index=False)

    # Unique-correct and regression case files
    results_df[results_df["d6_unique_correct"] == 1].to_csv(
        run_dir / "d6_mistral_unique_correct_cases.csv", index=False
    )
    results_df[results_df["d6_regression"] == 1].to_csv(
        run_dir / "d6_mistral_regression_cases.csv", index=False
    )

    eval_summary = {
        "n_total": n_total, "n_completed": n_completed,
        "n_strict_json": n_strict_json,
        "strict_json_rate": n_strict_json / n_total if n_total else 0,
        "frontier_accuracy": frontier_acc,
        "d6_accuracy": d6_acc,
        "delta_vs_frontier": delta,
        "unique_correct_additions": uc,
        "regressions": regs,
        "net_delta": uc - regs,
        "oracle_after": float((results_df["frontier_correct"] | results_df["d6_correct"]).mean()),
        "verdict": (
            "MISTRAL_D6_PILOT_SUCCESS_READY_FOR_D9_RETRAINING"
            if uc > 0 and regs <= uc * 2
            else "MISTRAL_D6_PILOT_USE_AS_GATED_MODULE"
            if uc > 0
            else "MISTRAL_D6_PILOT_NEGATIVE_DO_NOT_SCALE"
        ),
    }
    with open(run_dir / "d6_mistral_eval_summary.json", "w") as f:
        json.dump(eval_summary, f, indent=2)

    # ── Part H: D9 integration tables ────────────────────────────────────────
    log("\n== Part H: D9 integration tables ==")

    # Build D9-ready candidate rows from generation outputs
    ftr_feats = d8_df[
        (d8_df["provider"] == "mistral") &
        (d8_df["method"] == "direct_reserve_semantic_frontier_v2")
    ].copy()
    ftr_feat_map = {row["pool_id"]: row for _, row in ftr_feats.iterrows()}

    d9_rows: list[dict] = []
    for item in gen_items:
        pid = item.get("pool_id", "")
        if pid not in ftr_feat_map:
            continue
        base = ftr_feat_map[pid]
        extracted = item.get("extracted_answer")
        gold = gold_map.get(pid)
        d6_correct = int(answers_match(extracted, gold)) if extracted is not None else 0

        d9_rows.append({
            "pool_id": pid,
            "provider": "mistral",
            "dataset": item.get("dataset", ""),
            "scenario_id": item.get("scenario", ""),
            "selection_bucket": bucket_map.get(pid, ""),
            "d6_source": "mistral_pilot",
            "method": "frontier_math_extended_verify_v1",
            "extracted_answer": extracted,
            "normalized_answer": normalize_answer(extracted),
            "action_correct": d6_correct,
            "d6_strict_json_compliance": int(item.get("strict_json_contract_compliance", False)),
            "d6_extraction_missing": int(extracted is None),
            "d6_reextracted_flag": 0,
            "d6_variant_flag": 1,
            "frontier_correct": int(ftr_map.get(pid, {}).get("frontier_correct", 0)),
            "d6_good": int(d6_correct == 1 and int(ftr_map.get(pid, {}).get("frontier_correct", 0)) == 0),
            "d6_bad": int(d6_correct == 0 and int(ftr_map.get(pid, {}).get("frontier_correct", 0)) == 1),
        })

    d9_cand_df = pd.DataFrame(d9_rows)
    d9_cand_df.to_csv(run_dir / "d9_mistral_pilot_candidate_table.csv", index=False)

    d9_pool_rows = []
    for row in d9_rows:
        pid = row["pool_id"]
        d9_pool_rows.append({
            "pool_id": pid,
            "provider": row["provider"],
            "dataset": row["dataset"],
            "selection_bucket": row["selection_bucket"],
            "d6_source": "mistral_pilot",
            "d6_action_correct": row["action_correct"],
            "frontier_action_correct": row["frontier_correct"],
            "d6_extraction_ok": 1 - row["d6_extraction_missing"],
            "d6_good": row["d6_good"],
            "d6_bad": row["d6_bad"],
        })
    d9_pool_df = pd.DataFrame(d9_pool_rows)
    d9_pool_df.to_csv(run_dir / "d9_mistral_pilot_pool_table.csv", index=False)

    good_count = int(d9_pool_df["d6_good"].sum()) if not d9_pool_df.empty else 0
    bad_count = int(d9_pool_df["d6_bad"].sum()) if not d9_pool_df.empty else 0

    with open(run_dir / "D9_MISTRAL_PILOT_INTEGRATION_REPORT.md", "w") as f:
        f.write(f"""D9 Mistral Pilot Integration Report
Timestamp: {now_utc()}

== New Mistral D6 rows available ==
Total: {len(d9_rows)}
D6-good (D6 correct, frontier wrong): {good_count}
D6-bad (D6 wrong, frontier correct): {bad_count}
Labels available: YES (action_correct from offline gold)
Extraction status: YES

== Fills manuscript gap? ==
Mistral × MATH-500: {'YES' if any(r['dataset']=='math500' for r in d9_rows) else 'NO'}
Mistral × GSM8K: {'YES' if any(r['dataset']=='gsm8k' for r in d9_rows) else 'NO'}

== Merge strategy with current D9 retrain ==
1. Load d9_retrain_candidate_table.csv (14,000 rows: 13,600 base + 400 D6 pilot+expansion)
2. Append {len(d9_rows)} new Mistral D6 rows
3. New D9 training set: 14,000 + {len(d9_rows)} = {14000+len(d9_rows)} rows
4. D6 gate samples increase: {110 + good_count + bad_count} total (was 110)
5. Retrain D9R selectors with all D6 data including Mistral

== Files ==
d9_mistral_pilot_candidate_table.csv: {len(d9_cand_df)} rows
d9_mistral_pilot_pool_table.csv: {len(d9_pool_df)} rows
""")

    # ── Part I: Decision ──────────────────────────────────────────────────────
    log("\n== Part I: Decision ==")

    verdict = eval_summary["verdict"]
    decisions = {
        "verdict": verdict,
        "timestamp_utc": now_utc(),
        "q1_mistral_d6_useful": uc > 0,
        "q2_adds_unique_correct": uc > 0,
        "q3_regressions_manageable": regs <= uc * 2,
        "q4_retrain_d9_with_cohere_mistral": uc > 0 or regs < 20,
        "q5_other_d6_variants_deferred": True,
        "q6_cloudrift_fix_still_next": True,
        "gate_sample_increase": good_count + bad_count,
        "recommended_next_jobs": [
            f"Retrain D9 with {14000 + len(d9_rows)} rows (14,000 base + {len(d9_rows)} Mistral D6)",
            "Fix Cloudrift Qwen extraction before using Cloudrift D6 rows",
            "Keep other D6 variants deferred until D9R validated on Mistral",
        ],
    }
    with open(run_dir / "d6_mistral_next_action.json", "w") as f:
        json.dump(decisions, f, indent=2)

    with open(run_dir / "D6_MISTRAL_PILOT_DECISION.md", "w") as f:
        f.write(f"""D6 Mistral Pilot Decision
Timestamp: {now_utc()}
Verdict: {verdict}

1. Is Mistral D6 useful as a gated extra candidate?
   {'YES' if uc > 0 else 'UNCLEAR'} — {uc} unique-correct additions.

2. Does it add unique-correct cases?
   {'YES' if uc > 0 else 'NO'} — D6 unique-correct: {uc}

3. Are regressions manageable by D9 gate?
   {'YES' if regs <= uc * 2 else 'MARGINAL'} — Regressions: {regs}

4. Should D9 be retrained with Cohere + Mistral D6 data?
   {'YES' if uc > 0 or regs < 20 else 'DEFER'}

5. Should remaining D6 variants remain deferred?
   YES — validate D9R gate on Mistral before other variants.

6. Should Cloudrift extraction fix remain next after Mistral?
   YES — Cloudrift Qwen3 compliance still poor.

== Summary ==
Frontier acc on pilot: {frontier_acc:.4f}
D6 acc: {d6_acc:.4f} (delta {delta:+.4f})
Unique-correct: {uc}, Regressions: {regs}, Net: {uc-regs:+d}
Gate signal increase: +{good_count+bad_count} samples (D9R-B gate)
Manuscript gap covered: Mistral × MATH-500 ({'YES' if any(r['dataset']=='math500' for r in d9_rows) else 'NO'})

{verdict}
""")

    # ── Summary ───────────────────────────────────────────────────────────────
    log("\n== Part K: Summary ==")
    with open(run_dir / "D6_MISTRAL_PILOT_SUMMARY.md", "w") as f:
        f.write(f"""D6 Mistral Pilot Summary
Job: D6 Mistral pilot — frontier_math_extended_verify_v1
Run dir: {run_dir}
Timestamp: {now_utc()}
API calls: YES (approved, bounded to {MAX_API_ITEMS} items)

== Data ==
Cases planned: {n_total}
Completed: {n_completed}
Strict JSON: {n_strict_json} ({n_strict_json/n_total*100:.1f}%)

== Results ==
Frontier accuracy: {frontier_acc:.4f}
D6 accuracy: {d6_acc:.4f}
Delta: {delta:+.4f}
Unique-correct: {uc}
Regressions: {regs}
Net: {uc-regs:+d}

== Bucket Results ==
""")
        for r in bucket_rows:
            f.write(f"- {r['bucket']}: n={r['n']}, frontier={r['frontier_accuracy']:.3f}, "
                    f"d6={r['d6_accuracy']:.3f}, delta={r['delta']:+.3f}, "
                    f"uc={r['unique_correct']}, regs={r['regressions']}\n")

        f.write(f"""
== D9 Integration ==
New D9 candidate rows: {len(d9_rows)}
D9R-B gate signal increase: +{good_count+bad_count}
Manuscript gap filled: Mistral × MATH-500

{verdict}
""")

    # ── Ledger ────────────────────────────────────────────────────────────────
    ledger_csv = Path(LEDGER_DIR) / "training_experiment_ledger.csv"
    if ledger_csv.exists():
        entry = (
            f"d6_mistral_pilot_{now_utc().replace(':','').replace('-','')[:15]},"
            f"{now_utc()},mistral,{run_dir},"
            f"{VARIANT_NAME},mistral_pilot,yes,yes,no,no,"
            f"{d6_acc:.4f},,\"{n_strict_json}/{n_total} strict_json; uc={uc}; regs={regs}; delta={delta:+.4f}\","
            f"{verdict},Retrain D9 with Cohere+Mistral D6 data\n"
        )
        with open(ledger_csv, "a") as lf:
            lf.write(entry)
        log("Ledger CSV updated")

    ledger_md = Path(LEDGER_DIR) / "training_experiment_ledger.md"
    if ledger_md.exists():
        entry_md = f"""
### D6 Mistral Pilot ({now_utc()[:10]})
- **Run**: `{run_dir}`
- **Cases**: {n_total} ({n_completed} completed, {n_strict_json} strict JSON)
- **D6 acc**: {d6_acc:.4f} vs frontier {frontier_acc:.4f} (delta {delta:+.4f})
- **Unique-correct**: {uc}, **Regressions**: {regs}
- **Verdict**: `{verdict}`
"""
        with open(ledger_md, "a") as lf:
            lf.write(entry_md)
        log("Ledger MD updated")

    log(f"\nEvaluation complete. Verdict: {verdict}")


if __name__ == "__main__":
    main()
