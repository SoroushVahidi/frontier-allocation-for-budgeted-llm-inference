#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, time, csv
from pathlib import Path
import requests
from experiments.self_verification_cmv_selector import build_declarative_conclusion, build_cmv_prompt, parse_masked_value_prediction, normalize_gsm8k_numeric_answer
COHERE_URL='https://api.cohere.com/v2/chat'

def jlines(p: Path):
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]

def append(p: Path, row: dict):
    with p.open('a',encoding='utf-8') as f: f.write(json.dumps(row)+'\n'); f.flush()

def call(api_key, model, prompt, temperature, timeout):
    r=requests.post(COHERE_URL,headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json'},json={'model':model,'temperature':temperature,'messages':[{'role':'user','content':prompt}]},timeout=timeout)
    r.raise_for_status(); return r.json()['message']['content'][0]['text']

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--call-plan',required=True); ap.add_argument('--output-dir',required=True); ap.add_argument('--backend',default='cohere'); ap.add_argument('--model',default='command-a-03-2025'); ap.add_argument('--max-calls',type=int,default=150); ap.add_argument('--max-new-calls',type=int,default=50); ap.add_argument('--allow-api',action='store_true'); ap.add_argument('--cache-path',required=True); ap.add_argument('--temperature',type=float,default=0); ap.add_argument('--request-timeout-seconds',type=float,default=45); ap.add_argument('--max-retries',type=int,default=2); ap.add_argument('--retry-backoff-seconds',type=float,default=5); ap.add_argument('--resume',action='store_true'); ap.add_argument('--no-gold-features',action='store_true'); ap.add_argument('--validate-call-plan-only',action='store_true'); args=ap.parse_args()
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True); cache=Path(args.cache_path); cache.parent.mkdir(parents=True,exist_ok=True)
    failed=out/'failed_or_skipped_items.jsonl'; failed.write_text('',encoding='utf-8') if not failed.exists() else None
    existing={r['call_key']:r for r in jlines(cache)} if args.resume else {}
    items=jlines(Path(args.call_plan)); attempted=succeeded=skipped=fail_n=calls=0
    for it in items:
        k=it['call_key']
        if k in existing: skipped += 1; continue
        if args.validate_call_plan_only: attempted += 1; continue
        if calls>=args.max_calls or calls>=args.max_new_calls: break
        attempted += 1
        if not args.allow_api or not os.getenv('COHERE_API_KEY',''):
            append(failed,{'call_key':k,'error':'api_disabled_or_missing_key'}); fail_n += 1; continue
        conc=build_declarative_conclusion('',it['normalized_candidate_answer'])
        prompt=build_cmv_prompt(it['masked_problem_text'],it,it['normalized_candidate_answer'],conc)
        err=None
        for r in range(args.max_retries+1):
            try:
                txt=call(os.getenv('COHERE_API_KEY',''),args.model,prompt,args.temperature,args.request_timeout_seconds)
                pred=parse_masked_value_prediction(txt); np=normalize_gsm8k_numeric_answer(pred or '')
                row={'call_key':k,'case_id':it['case_id'],'candidate_id':it['candidate_id'],'condition_id':it['condition_id'],'repeat_index':it['repeat_index'],'normalized_original_value':it['normalized_original_value'],'predicted_x_value_raw':pred,'normalized_predicted_x_value':np,'match':bool(np is not None and np==it['normalized_original_value']),'reason':'cmv_check','backend':args.backend,'model':args.model,'prompt_truncated':False}
                append(cache,row); succeeded += 1; calls += 1; err=None; break
            except Exception as e:
                err=str(e); time.sleep(args.retry_backoff_seconds if r<args.max_retries else 0)
        if err: fail_n += 1; append(failed,{'call_key':k,'error':err})
    rows=jlines(cache)
    summary={'total_call_plan_items':len(items),'attempted_calls':attempted,'successful_scores':succeeded,'failed_calls':fail_n,'skipped_existing_cached_scores':skipped,'api_calls_made':calls,'max_calls':args.max_calls,'max_new_calls':args.max_new_calls,'no_gold_oracle_evaluation_only_in_prompts':True}
    (out/'manifest.json').write_text(json.dumps({'call_plan':args.call_plan,'cache_path':str(cache)},indent=2)+'\n')
    (out/'cmv_scores.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n' if rows else '',encoding='utf-8')
    (out/'cmv_scoring_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'cmv_scoring_summary.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=list(summary.keys())); w.writeheader(); w.writerow(summary)
    (out/'cmv_scoring_report.md').write_text('\n'.join([f"- {k}: {v}" for k,v in summary.items()])+'\n')
    (out/'progress_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
if __name__=='__main__': main()
