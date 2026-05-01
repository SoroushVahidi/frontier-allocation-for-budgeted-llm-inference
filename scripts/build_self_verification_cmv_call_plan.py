#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path
from datetime import datetime, timezone
from experiments.self_verification_cmv_selector import extract_candidate_final_answer, extract_numeric_conditions, mask_condition

def jlines(p: Path):
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]

def stamp(): return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--paired-source'); ap.add_argument('--input'); ap.add_argument('--pilot-cases',type=int,default=25); ap.add_argument('--max-api-calls',type=int,default=150); ap.add_argument('--p-repeats',type=int,default=3); ap.add_argument('--max-conditions-per-problem',type=int,default=4); ap.add_argument('--output-dir',required=True); ap.add_argument('--dataset',default='gsm8k'); ap.add_argument('--no-gold-features',action='store_true'); args=ap.parse_args()
    src=Path(args.paired_source or args.input)
    rows=jlines(src)
    chosen=rows[:args.pilot_cases]
    while True:
        items=[]; cand_count=valid=invalid=conds_total=0
        for ridx,r in enumerate(chosen):
            case_id=str(r.get('example_id') or r.get('case_id') or f'case_{ridx}')
            problem=str(r.get('problem_statement') or r.get('problem_text') or r.get('question') or '')
            conds=extract_numeric_conditions(problem,args.max_conditions_per_problem); conds_total += len(conds)
            cands=r.get('candidate_nodes') or r.get('candidates') or []
            for cidx,c in enumerate(cands):
                cand_count += 1
                cid=str(c.get('candidate_id') or f'{case_id}_cand_{cidx}')
                ans=extract_candidate_final_answer(c)
                if ans is None: invalid += 1; continue
                valid += 1
                for cond in conds:
                    masked = mask_condition(problem, tuple(cond['span']))
                    mph = hashlib.sha256(masked.encode()).hexdigest()
                    for rep in range(1,args.p_repeats+1):
                        key = hashlib.sha256(f"{case_id}|{cid}|{ans}|{cond['condition_id']}|{rep}|{mph}".encode()).hexdigest()
                        items.append({'call_key':key,'case_id':case_id,'candidate_id':cid,'condition_id':cond['condition_id'],'repeat_index':rep,'masked_problem_text':masked,'masked_problem_hash':mph,'normalized_candidate_answer':ans,'normalized_original_value':cond['normalized_value'],'dataset':args.dataset})
        ded={x['call_key']:x for x in items}; items=list(ded.values())
        if len(items)<=args.max_api_calls or len(chosen)<=1: break
        chosen=chosen[:-1]
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'pilot_cases.jsonl').write_text('\n'.join(json.dumps(r) for r in chosen)+'\n',encoding='utf-8')
    (out/'cmv_call_plan.jsonl').write_text('\n'.join(json.dumps(r) for r in items)+'\n',encoding='utf-8')
    summary={'requested_pilot_cases':args.pilot_cases,'actual_pilot_case_count':len(chosen),'candidate_count':cand_count,'valid_candidate_answers':valid,'invalid_candidate_answers':invalid,'numeric_conditions_total':conds_total,'p_repeats':args.p_repeats,'max_conditions_per_problem':args.max_conditions_per_problem,'planned_api_calls':len(items),'max_api_calls':args.max_api_calls,'no_gold_oracle_evaluation_only_in_call_plan':True}
    (out/'call_plan_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'source':str(src),'timestamp':stamp()},indent=2)+'\n',encoding='utf-8')
    (out/'call_plan_report.md').write_text('\n'.join([f"- {k}: {v}" for k,v in summary.items()])+'\n',encoding='utf-8')
if __name__=='__main__': main()
