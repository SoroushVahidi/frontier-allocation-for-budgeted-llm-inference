#!/usr/bin/env python3
import argparse, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

def jlines(p):
    for l in open(p):
        if l.strip(): yield json.loads(l)

def canon(x): return '' if x is None else str(x).strip()

def score_key(case_id,cid):
    return hashlib.sha256(f"{case_id}|{cid}".encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--paired-records',required=True)
    ap.add_argument('--selected-config',required=True)
    ap.add_argument('--existing-cache',required=True)
    ap.add_argument('--pilot-cases',type=int,default=25)
    ap.add_argument('--max-new-calls-cap',type=int,default=150)
    ap.add_argument('--output-dir',required=True)
    a=ap.parse_args()
    cfg=json.load(open(a.selected_config))
    existing=set()
    for r in jlines(a.existing_cache):
        k=r.get('item_hash') or score_key(r.get('case_id'),r.get('candidate_id'))
        existing.add(k)
    by={}
    for r in jlines(a.paired_records):
        k=(r.get('dataset'),r.get('example_id'),r.get('seed'),r.get('budget'))
        by.setdefault(k,{})[r.get('method')]=r
    keys=[k for k,v in by.items() if 'direct_reserve_semantic_frontier_v2' in v and 'external_l1_max' in v]
    keys=sorted(keys)[:a.pilot_cases]
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    pilot=[]; items=[]
    for ds,eid,seed,budget in keys:
        dr=by[(ds,eid,seed,budget)]['direct_reserve_semantic_frontier_v2']
        case_id=f"{ds}::{eid}::{seed}::{budget}"
        pool=((dr.get('result_metadata') or {}).get('selector_candidate_pool') or [])
        pilot.append({'dataset':ds,'example_id':eid,'seed':seed,'budget':budget,'case_id':case_id,'question':dr.get('question')})
        for c in pool:
            row={
                'case_id':case_id,'candidate_id':canon(c.get('candidate_id')),'problem_statement':dr.get('question',''),
                'final_answer':canon(c.get('predicted_answer') or c.get('normalized_answer')),
                'normalized_answer':canon(c.get('normalized_answer')),
                'trace_text':canon(c.get('trace') or c.get('reasoning_text')),
            }
            if any(t in json.dumps(row).lower() for t in ['gold_answer','evaluation_only','oracle']):
                raise SystemExit('unsafe call plan fields')
            items.append(row)
    ded={}
    for it in items:
        h=score_key(it['case_id'],it['candidate_id']); it['item_hash']=h; ded[h]=it
    missing=[v for h,v in ded.items() if h not in existing]
    (out/'pilot_cases.jsonl').write_text('\n'.join(json.dumps(r) for r in pilot)+'\n')
    (out/'missing_verifier_call_plan.jsonl').write_text('\n'.join(json.dumps(r) for r in missing)+'\n')
    summary={
        'pilot_case_count':len(keys),'candidate_nodes':len(items),'total_scoring_items_before_dedupe':len(items),
        'total_scoring_items_after_dedupe':len(ded),'existing_cached_scores_reused':len(ded)-len(missing),
        'missing_scores_to_call':len(missing),'max_new_calls_cap':a.max_new_calls_cap,
        'selected_selector_config':a.selected_config,
        'gold_oracle_evaluation_only_free_confirmation':True
    }
    (out/'call_plan_summary.json').write_text(json.dumps(summary,indent=2))
    (out/'manifest.json').write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'paired_records':a.paired_records,'existing_cache':a.existing_cache,'selected_config':cfg,'pilot_cases_requested':a.pilot_cases},indent=2))
    (out/'call_plan_report.md').write_text(f"# Fully scored selector pilot call plan\n\n- pilot cases: {len(keys)}\n- candidate nodes: {len(items)}\n- deduped items: {len(ded)}\n- cached reused: {len(ded)-len(missing)}\n- missing to call: {len(missing)}\n")

if __name__=='__main__': main()
