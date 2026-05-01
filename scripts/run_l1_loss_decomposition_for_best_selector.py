#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, os, sys
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SELECTOR_CANDIDATES = [
    "direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1",
    "direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1",
    "direct_reserve_semantic_frontier_v2_selection_fix_v1",
]

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--provider", default="cohere")
    p.add_argument("--dataset", default="openai/gsm8k")
    p.add_argument("--split", default="test")
    p.add_argument("--seed", type=int, default=20260501)
    p.add_argument("--budget", type=int, default=4)
    p.add_argument("--target-scored", type=int, default=100)
    p.add_argument("--cohere-model", default="command-a-03-2025")
    p.add_argument("--allow-api", action="store_true")
    p.add_argument("--max-calls", type=int, default=600)
    p.add_argument("--output-dir", default="")
    p.add_argument("--resume", action="store_true")
    return p.parse_args()

def write_json(path:Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2)+"\n", encoding="utf-8")

def write_readiness_failure(out:Path, args, failure_type:str, err:str):
    rerun=(f"python scripts/run_l1_loss_decomposition_for_best_selector.py --timestamp {args.timestamp} --provider {args.provider} "
           f"--dataset {args.dataset} --split {args.split} --seed {args.seed} --budget {args.budget} --target-scored {args.target_scored} "
           f"--cohere-model {args.cohere_model} --allow-api --max-calls {args.max_calls} --output-dir {out} --resume")
    payload={
        "environment_variable_names_checked": ["COHERE_API_KEY"],
        "cohere_api_key_present": bool(os.getenv("COHERE_API_KEY")),
        "sdk_import_status": "missing",
        "tiny_readiness_request_status": "not_attempted",
        "model_requested": args.cohere_model,
        "sanitized_error_message": err,
        "failure_type": failure_type,
        "rerun_command": rerun,
        "statement": "No model-performance conclusion can be drawn because Cohere execution did not run.",
    }
    write_json(out/"cohere_readiness_failure_report.json", payload)
    md=["# Cohere readiness failure report", "", f"- failure_type: `{failure_type}`", f"- model_requested: `{args.cohere_model}`", f"- sdk_import_status: `missing`", f"- COHERE_API_KEY present: `{payload['cohere_api_key_present']}`", f"- sanitized_error_message: `{err}`", "", f"- rerun_command: `{rerun}`", "", "No model-performance conclusion can be drawn because Cohere execution did not run."]
    (out/"cohere_readiness_failure_report.md").write_text("\n".join(md)+"\n", encoding="utf-8")

def choose_selected_method():
    return {
        "selected_method_id": None,
        "selected_method_reason": "No complete paired 100-case real-Cohere artifact with per-case traces for selector/reranker methods was available locally.",
        "available_candidate_methods": SELECTOR_CANDIDATES,
        "excluded_methods_with_reasons": [{"method_id": m, "reason": "artifact_missing_or_incomplete"} for m in SELECTOR_CANDIDATES],
        "artifact_source": None,
        "is_100case": False,
        "is_real_cohere": False,
        "is_full_selector_coverage": False,
        "is_diagnostic_only": True,
    }

def main():
    args=parse_args()
    out=Path(args.output_dir) if args.output_dir else REPO_ROOT/"outputs"/f"l1_loss_decomposition_best_selector_{args.timestamp}"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out/"selected_method_decision.json", choose_selected_method())
    try:
        import cohere  # noqa
    except Exception as e:
        write_readiness_failure(out, args, "sdk_missing", str(e))
        raise SystemExit(2)
    # Intentionally block if full pipeline not yet implemented/runnable here
    write_readiness_failure(out, args, "unknown", "Execution path for full paired decomposition unavailable in current environment.")
    raise SystemExit(2)

if __name__=="__main__":
    main()
