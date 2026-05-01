#!/usr/bin/env python3
import argparse, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

def jlines(p):
    for l in open(p):
        if l.strip(): yield json.loads(l)

def canon(x): return '' if x is None else str(x).strip()
def score_key(case_id,cid): return hashlib.sha256(f"{case_id}|{cid}".encode()).hexdigest()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--paired-records','--paired-source',dest='paired_records',required=True)
    ap.add_argument('--selected-config','--selected-selector-config',dest='selected_config',required=True)
    ap.add_argument('--existing-cache','--existing-score-cache',dest='existing_caches',action='append',required=True)
    ap.add_argument('--pilot-cases',type=int,default=25)
    ap.add_argument('--max-new-calls-cap','--max-new-calls',dest='max_new_calls_cap',type=int,default=150)
    ap.add_argument('--output-dir',required=True)
    ap.add_argument('--no-gold-features',action='store_true')
    a=ap.parse_args()
    cfg=json.load(open(a.selected_config))
    existing=set()
    for cp in a.existing_caches:
        for r in jlines(cp):
            existing.add(r.get('item_hash') or score_key(r.get('case_id'),r.get('candidate_id')))
    by={}
    for r in jlines(a.paired_records):
        k=(r.get('dataset'),r.get('example_id'),r.get('seed'),r.get('budget'))
        by.setdefault(k,{})[r.get('method')]=r
    keys=[k for k,v in by.items() if 'direct_reserve_semantic_frontier_v2' in v and 'external_l1_max' in v]
    keys=sorted(keys)

    chosen=[]; items=[]
    for k in keys:
        if len(chosen)>=a.pilot_cases: break
        ds,eid,seed,budget=k; dr=by[k]['direct_reserve_semantic_frontier_v2']; case_id=f"{ds}::{eid}::{seed}::{budget}"
        pool=((dr.get('result_metadata') or {}).get('selector_candidate_pool') or [])
        new_items=[]
        for c in pool:
            row={'case_id':case_id,'candidate_id':canon(c.get('candidate_id')),'problem_statement':dr.get('question',''),'final_answer':canon(c.get('predicted_answer') or c.get('normalized_answer')),'normalized_answer':canon(c.get('normalized_answer')),'trace_text':canon(c.get('trace') or c.get('reasoning_text'))}
            if any(t in json.dumps(row).lower() for t in ['gold_answer','evaluation_only','oracle','correct_answer']): raise SystemExit('unsafe call plan fields')
            row['item_hash']=score_key(row['case_id'],row['candidate_id']); new_items.append(row)
        # check cap incrementally by missing unique hashes
        prospective={it['item_hash']:it for it in items+new_items}
        missing=sum(1 for h in prospective if h not in existing)
        if missing>a.max_new_calls_cap: break
        chosen.append({'dataset':ds,'example_id':eid,'seed':seed,'budget':budget,'case_id':case_id,'question':dr.get('question')})
        items.extend(new_items)

    ded={it['item_hash']:it for it in items}
    missing=[v for h,v in ded.items() if h not in existing]
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    (out/'pilot_cases.jsonl').write_text('\n'.join(json.dumps(r) for r in chosen)+'\n')
    (out/'missing_verifier_call_plan.jsonl').write_text('\n'.join(json.dumps(r) for r in missing)+'\n')
    summary={'requested_pilot_cases':a.pilot_cases,'actual_pilot_case_count':len(chosen),'pilot_case_count':len(chosen),'candidate_nodes':len(items),'total_scoring_items_before_dedupe':len(items),'total_scoring_items_after_dedupe':len(ded),'existing_cached_scores_reused':len(ded)-len(missing),'missing_scores_to_call':len(missing),'max_new_calls_cap':a.max_new_calls_cap,'selected_selector_config':a.selected_config,'no_gold_oracle_evaluation_only_in_call_plan':True}
    (out/'call_plan_summary.json').write_text(json.dumps(summary,indent=2))
    (out/'manifest.json').write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'paired_records':a.paired_records,'existing_caches':a.existing_caches,'selected_config':cfg},indent=2))
    (out/'call_plan_report.md').write_text('\n'.join([f"- {k}: {v}" for k,v in summary.items()])+'\n')

if __name__=='__main__': main()
