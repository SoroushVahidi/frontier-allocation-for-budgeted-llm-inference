#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path


def read_jsonl(p: Path):
    out=[]
    with p.open('r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line: out.append(json.loads(line))
    return out

def write_csv(p: Path, rows, fieldnames):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input-dir',required=True)
    args=ap.parse_args()
    d=Path(args.input_dir)
    rows=[r for r in read_jsonl(d/'per_example_records.jsonl') if r.get('status')=='scored']
    key=lambda r:(r['dataset'],str(r['example_id']),str(r['seed']),str(r['budget']))
    by={}
    for r in rows: by.setdefault(key(r),{})[r['method']]=r
    out=[]
    for (dataset,example_id,seed,budget),m in sorted(by.items()):
        dr=m.get('direct_reserve_semantic_frontier_v2'); fx=m.get('direct_reserve_semantic_frontier_v2_selection_fix_v1'); l1=m.get('external_l1_max')
        if not (dr and fx and l1):
            continue
        md0=dr.get('result_metadata') or {}
        md1=fx.get('result_metadata') or {}
        fn0=dr.get('final_nodes') or []
        fn1=fx.get('final_nodes') or []
        c0=sorted(set(str(x.get('predicted_answer_normalized') or '') for x in fn0 if str(x.get('predicted_answer_normalized') or '').strip()))
        c1=sorted(set(str(x.get('predicted_answer_normalized') or '') for x in fn1 if str(x.get('predicted_answer_normalized') or '').strip()))
        gold=str(dr.get('gold_answer_canonical') or '')
        dr_present=int(gold in c0) if gold else 0
        fx_present=int(gold in c1) if gold else 0
        dr_wrong=not bool(int(dr.get('exact_match',0))); l1_ok=bool(int(l1.get('exact_match',0))); fx_ok=bool(int(fx.get('exact_match',0)))
        dr_sel=str(md0.get('selected_group') or md0.get('final_answer_group') or '')
        fx_sel=str(md1.get('selected_group') or md1.get('final_answer_group') or '')
        dr_pns=int(dr_wrong and dr_present and dr_sel!=gold and gold!='')
        fx_pns=int((not fx_ok) and fx_present and fx_sel!=gold and gold!='')
        applied=bool(md1.get('selection_fix_applied',False)); considered=bool(md1.get('selection_fix_considered',False))
        ds=int(md1.get('selection_fix_direct_support',0) or 0); fs=int(md1.get('selection_fix_frontier_support',0) or 0)
        if fx_ok:
            why='already_correct'
        elif l1_ok and dr_wrong:
            if not considered or not applied:
                why='gold_group_present_but_lower_support' if fx_present and fs<=ds else 'fix_not_applied'
            elif str(fx.get('final_answer_canonical'))==str(dr.get('final_answer_canonical')):
                why='fix_applied_same_wrong_answer'
            elif fx_present and fx_sel!=gold:
                why='fix_applied_to_wrong_frontier_group'
            elif fx_present and fs<=ds:
                why='gold_group_present_but_lower_support'
            else:
                why='support_signal_does_not_identify_gold_group'
        elif l1_ok and (not dr_wrong):
            why='external_l1_only_correct_unresolved'
        else:
            why='trace_missing_unclassifiable'
        out.append({
            'dataset':dataset,'example_id':example_id,'seed':seed,'budget':budget,'gold_answer':dr.get('gold_answer_canonical',''),
            'external_l1_answer':l1.get('final_answer_canonical',''),'external_l1_correct':int(l1.get('exact_match',0)),
            'dr_v2_answer':dr.get('final_answer_canonical',''),'dr_v2_correct':int(dr.get('exact_match',0)),
            'selection_fix_answer':fx.get('final_answer_canonical',''),'selection_fix_correct':int(fx.get('exact_match',0)),
            'dr_v2_candidate_answers_normalized':json.dumps(c0),'selection_fix_candidate_answers_normalized':json.dumps(c1),
            'dr_v2_selected_answer_group':dr_sel,'selection_fix_selected_answer_group':fx_sel,
            'dr_v2_gold_answer_group_present':dr_present,'selection_fix_gold_answer_group_present':fx_present,
            'dr_v2_present_not_selected':dr_pns,'selection_fix_present_not_selected':fx_pns,
            'selection_fix_considered':int(considered),'selection_fix_applied':int(applied),'selection_fix_reason':md1.get('selection_fix_reason',''),
            'direct_support':ds,'frontier_support':fs,'support_gap':fs-ds,'why_fix_did_not_help':why,
        })
    fields=list(out[0].keys()) if out else []
    write_csv(d/'selection_fix_case_audit.csv',out,fields)
    c=Counter(r['why_fix_did_not_help'] for r in out)
    write_csv(d/'selection_fix_failure_summary.csv',[{'why_fix_did_not_help':k,'count':v,'fraction':v/len(out) if out else 0.0} for k,v in sorted(c.items())],['why_fix_did_not_help','count','fraction'])
    decision='support_signal_does_not_identify_gold_group'
    if c.get('gold_group_present_but_lower_support',0)>0: decision='support_only_signal_insufficient'
    (d/'selection_fix_next_decision.json').write_text(json.dumps({'n_cases':len(out),'why_counts':c,'next_decision':decision},default=dict,indent=2)+'\n')

if __name__=='__main__': main()
