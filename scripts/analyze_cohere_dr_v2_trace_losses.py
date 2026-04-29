#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path


def read_csv(p: Path):
    if not p.exists() or p.stat().st_size==0:return []
    with p.open('r',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def write_csv(p: Path, rows, fieldnames=None):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8',newline='') as f:
        if not rows:
            if fieldnames: csv.DictWriter(f,fieldnames=fieldnames).writeheader()
            return
        w=csv.DictWriter(f,fieldnames=fieldnames or list(rows[0].keys()));w.writeheader();w.writerows(rows)

def b(x):
    return str(x).strip().lower() in {'1','true','yes'}

def classify(r):
    dr=b(r.get('exact_match',0)); l1=b(r.get('external_l1_exact_match',0))
    if dr and l1:return 'both_correct'
    if dr and not l1:return 'dr_v2_only_correct'
    if (not dr) and (not l1): return 'both_wrong'
    if b(r.get('dr_v2_absent_from_frontier',0)): return 'proposal_failure_absent_from_frontier'
    if b(r.get('dr_v2_present_not_selected',0)): return 'selection_failure_present_not_selected'
    if b(r.get('dr_v2_extraction_suspected',0)): return 'extraction_or_normalization_failure'
    if b(r.get('dr_v2_trace_available',0)): return 'commit_or_over_exploration_failure'
    return 'trace_missing_unclassifiable'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input-dir',required=True)
    args=ap.parse_args()
    d=Path(args.input_dir)
    rows=read_csv(d/'trace_audit_per_case.csv')
    out=[]; cnt=Counter()
    for r in rows:
        c=classify(r); rr=dict(r); rr['loss_taxonomy']=c; out.append(rr); cnt[c]+=1
    write_csv(d/'dr_v2_vs_l1_loss_cases.csv',out, fieldnames=list(out[0].keys()) if out else ['loss_taxonomy'])
    write_csv(d/'dr_v2_loss_taxonomy_summary.csv',[{'loss_taxonomy':k,'count':v} for k,v in sorted(cnt.items())],fieldnames=['loss_taxonomy','count'])
    fields=['dr_v2_candidate_answers_raw','dr_v2_candidate_answers_normalized','dr_v2_selected_answer_group','dr_v2_trace_available','external_l1_exact_match']
    cov=[]
    for f in fields:
        non=sum(1 for r in rows if str(r.get(f,'')).strip()!='')
        cov.append({'field':f,'non_empty':non,'total':len(rows),'coverage':(non/len(rows) if rows else 0.0)})
    write_csv(d/'dr_v2_trace_field_coverage.csv',cov)
    priority=['proposal_failure_absent_from_frontier','selection_failure_present_not_selected','extraction_or_normalization_failure','commit_or_over_exploration_failure']
    mapping={
        'proposal_failure_absent_from_frontier':'improve_branch_proposal',
        'selection_failure_present_not_selected':'improve_final_selection_or_reranking',
        'extraction_or_normalization_failure':'fix_extraction_normalization',
        'commit_or_over_exploration_failure':'improve_commit_stop_rule',
    }
    dom=max(priority,key=lambda k:cnt.get(k,0)) if sum(cnt.get(k,0) for k in priority)>0 else None
    decision='collect_more_trace_data' if dom is None else mapping[dom]
    (d/'dr_v2_next_algorithm_decision.json').write_text(json.dumps({'dominant_loss_class':dom,'recommended_action':decision,'counts':cnt},default=dict,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
