#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, os, random, sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from experiments.frontier_matrix_core import load_pilot_examples

OURS=["strict_f3","direct_reserve_semantic_frontier_v2","direct_reserve_semantic_frontier_v2_outcome_verifier_answer_group_selector_v1"]
EXTERNAL=["l1_length_control_rl","tale_token_budget_aware_reasoning","s1_simple_test_time_scaling"]
ALL=OURS+EXTERNAL
MODEL="command-a-03-2025"


def choose_cases(seed:int,n:int=100):
    pool=load_pilot_examples("openai/gsm8k",1319,seed)
    rnd=random.Random(seed)
    ids=list(range(len(pool))); rnd.shuffle(ids)
    chosen=[pool[i] for i in ids[:n]]
    rows=[]
    for i,e in enumerate(chosen):
        rows.append({"case_id":e.example_id,"dataset":"openai/gsm8k","split":"test","question":e.question,"evaluation_only":{"gold_answer":e.answer},"index":i})
    return rows

def write_jsonl(path:Path,rows:list[dict[str,Any]]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")

def to_csv(path:Path,rows:list[dict[str,Any]]):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows: path.write_text(""); return
    ks=list(rows[0].keys())
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ks); w.writeheader(); w.writerows(rows)

def dry_plan(cases):
    rows=[]
    for m in ALL:
        for c in cases:
            rows.append({"method_id":m,"case_id":c['case_id'],"provider":"cohere","model":MODEL,"planned":1})
    return rows

def execute(method_id:str,cases:list[dict[str,Any]],has_key:bool,selector_cov:bool):
    out=[]
    reason=None
    if not has_key: reason="blocked_missing_cohere_api_key"
    if method_id.endswith("selector_v1") and not selector_cov: reason="cache_limited_or_unavailable"
    for c in cases:
        pred=""; norm=""; correct=False; calls=[]
        if reason is None:
            reason="blocked_no_adapter_in_this_runner"
        out.append({"case_id":c['case_id'],"dataset":c['dataset'],"split":c['split'],"question":c['question'],"method_id":method_id,
                    "method_family":"ours" if method_id in OURS else "external","raw_prediction":pred,"normalized_prediction":norm,
                    "evaluation_only":{"gold_answer":c['evaluation_only']['gold_answer']},"correct":correct,"cohere_model":MODEL,
                    "call_cache_keys":calls,"budget_contract":"matched_substrate_mode_a","runtime_metadata":{"planned_provider":"cohere"},"failure_reason":reason})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--timestamp',default=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    ap.add_argument('--seed',type=int,default=20260501)
    ap.add_argument('--selector-full-coverage',action='store_true')
    args=ap.parse_args()
    outdir=Path(f"outputs/cohere_100case_ours_vs_external_{args.timestamp}"); outdir.mkdir(parents=True,exist_ok=True)
    cases=choose_cases(args.seed,100)
    write_jsonl(outdir/'selected_cases.jsonl',cases)
    plan=dry_plan(cases)
    (outdir/'planned_calls.json').write_text(json.dumps(plan,indent=2))
    to_csv(outdir/'planned_calls.csv',plan)
    has_key=bool(os.getenv('COHERE_API_KEY'))
    (outdir/'dry_run_report.md').write_text(f"# Dry run\n\nmethods={len(ALL)} cases={len(cases)} planned_calls={len(plan)}\n\nblockers: {'none' if has_key else 'missing COHERE_API_KEY'}\n")
    (outdir/'method_registry_snapshot.json').write_text(json.dumps({"ours":OURS,"external":EXTERNAL,"all":ALL},indent=2))
    manifests={"timestamp":args.timestamp,"seed":args.seed,"dataset":"openai/gsm8k","split":"test","cohere_model":MODEL,
               "claim_boundary":"MODE-A adapter comparators on matched substrate, not official full-stack reproductions"}
    (outdir/'manifest.json').write_text(json.dumps(manifests,indent=2))

    pm=outdir/'per_method_outputs'; pm.mkdir(exist_ok=True)
    pms=outdir/'per_method_summaries'; pms.mkdir(exist_ok=True)
    failed=[]; summaries=[]
    for m in ALL:
        rows=execute(m,cases,has_key,args.selector_full_coverage)
        write_jsonl(pm/f"{m}.jsonl",rows)
        s={"method_id":m,"accuracy":0.0,"correct_count":0,"failed_or_skipped_count":len(rows),"total_calls":0,"mean_calls_per_case":0.0}
        (pms/f"{m}_summary.json").write_text(json.dumps(s,indent=2)); summaries.append(s)
        failed.extend([{"method_id":m,"case_id":r['case_id'],"failure_reason":r['failure_reason']} for r in rows if r['failure_reason']])
    write_jsonl(outdir/'failed_or_skipped_calls.jsonl',failed)
    (outdir/'cohere_call_cache.jsonl').write_text("")
    (outdir/'progress_summary.json').write_text(json.dumps({"planned_calls":len(plan),"actual_calls":0,"skipped_or_failed":len(failed)},indent=2))
    # downstream report scaffold
    from scripts.build_cohere_100case_comparison_report import build_report
    build_report(outdir)

if __name__=='__main__': main()
