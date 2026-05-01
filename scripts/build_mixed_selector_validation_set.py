#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
from datetime import datetime,timezone

FORBIDDEN={'gold','oracle','evaluation_only','correct_answer'}

def has_trace(n):
    for k in ['trace_text','step_text','steps','reasoning_trace','trace','candidate_trace','terminal_trace']:
        v=n.get(k)
        if v not in (None,'',[]): return True
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--recovery-input',default='outputs/unified_selector_evidence_20260501T145906Z/unified_candidate_trace_enriched.jsonl')
    ap.add_argument('--risk-inventory',required=True)
    ap.add_argument('--output-dir',default='')
    args=ap.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=Path(args.output_dir) if args.output_dir else Path(f'outputs/mixed_selector_validation_{stamp}')
    out.mkdir(parents=True,exist_ok=True)

    rec=[json.loads(l) for l in Path(args.recovery_input).read_text(encoding='utf-8').splitlines() if l.strip()]
    inv=json.loads(Path(args.risk_inventory).read_text(encoding='utf-8'))
    risk=[]
    excluded=[]
    for r in inv:
        if r.get('rows',0)<=0: continue
        p=Path(r['path'])
        try:
            rows=[json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
            risk.extend(rows)
        except Exception as e:
            excluded.append({'path':str(p),'reason':str(e)})

    mixed=[]; seen=set()
    def norm(row,role,prov):
        ev=row.get('evaluation_only') or {}
        cands=row.get('candidate_nodes') or []
        vi=row.get('verifier_input') or {'candidates_for_verifier':[]}
        txt=json.dumps(vi).lower()
        if any(k in txt for k in FORBIDDEN):
            raise ValueError('forbidden verifier_input key')
        rec={
            'case_id':str(row.get('case_id') or f"{row.get('dataset','na')}::{row.get('example_id','na')}::{row.get('seed','na')}::{row.get('budget','na')}") ,
            'dataset':row.get('dataset'),'example_id':row.get('example_id'),'seed':row.get('seed'),'budget':row.get('budget'),'our_method_name':row.get('our_method_name'),
            'problem_statement':row.get('problem_statement') or row.get('problem') or row.get('question'),
            'selected_normalized_answer':row.get('selected_normalized_answer'),'current_normalized_answer':row.get('current_normalized_answer') or row.get('selected_normalized_answer'),
            'candidate_nodes':cands,'verifier_input':vi,'evaluation_only':ev,
            'provenance_source':prov,'validation_role':role,
            'gold_in_extracted_terminal_node_finals':row.get('gold_in_extracted_terminal_node_finals',False),
        }
        return rec

    for r in rec:
        m=norm(r,'recovery','present_not_selected_recovery')
        k=(m.get('dataset'),m.get('example_id'),m.get('seed'),m.get('budget'),m.get('our_method_name'),m.get('validation_role'))
        if k not in seen: seen.add(k); mixed.append(m)
    for r in risk:
        try:
            m=norm(r,'current_correct_risk','current_correct_risk')
            k=(m.get('dataset'),m.get('example_id'),m.get('seed'),m.get('budget'),m.get('our_method_name'),m.get('validation_role'))
            if k not in seen: seen.add(k); mixed.append(m)
        except Exception as e:
            excluded.append({'path':'risk_row','reason':str(e)})

    (out/'mixed_candidate_trace_enriched.jsonl').write_text('\n'.join(json.dumps(r) for r in mixed)+'\n',encoding='utf-8')
    (out/'excluded_or_unusable_cases.jsonl').write_text('\n'.join(json.dumps(r) for r in excluded)+('\n' if excluded else ''),encoding='utf-8')

    def summ(rows):
        total=len(rows); nodes=sum(len(r.get('candidate_nodes') or []) for r in rows); traced=sum(sum(1 for n in (r.get('candidate_nodes') or []) if has_trace(n)) for r in rows)
        with_nodes=sum(1 for r in rows if (r.get('candidate_nodes') or [])); with_trace=sum(1 for r in rows if any(has_trace(n) for n in (r.get('candidate_nodes') or [])))
        corr=wrong=0
        for r in rows:
            gold=str((r.get('evaluation_only') or {}).get('gold_answer','')).strip().lower(); cur=str(r.get('current_normalized_answer') or '').strip().lower()
            if gold and cur==gold: corr+=1
            elif gold: wrong+=1
        return {'records':total,'candidate_nodes':nodes,'traced_candidate_nodes':traced,'cases_with_candidate_nodes':with_nodes,'cases_with_at_least_one_candidate_trace':with_trace,'current_incumbent_correct_count':corr,'current_incumbent_wrong_count':wrong,'gold_present_in_extracted_terminal_node_finals':sum(1 for r in rows if r.get('gold_in_extracted_terminal_node_finals')),'usable_for_trace_aware_selector':with_nodes}
    overall=summ(mixed)
    by={}
    for role in ['recovery','current_correct_risk','mixed_other']:
        by[role]=summ([r for r in mixed if r.get('validation_role')==role])
    summary={'timestamp':stamp,'input_recovery':args.recovery_input,'risk_inventory':args.risk_inventory,'total_records':len(mixed),'by_validation_role':by,'overall':overall}
    (out/'manifest.json').write_text(json.dumps({'recovery_input':args.recovery_input,'risk_inventory':args.risk_inventory,'output':str(out)},indent=2)+'\n')
    (out/'mixed_selector_validation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (out/'mixed_selector_validation_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['scope']+list(overall.keys())); w.writeheader(); w.writerow({'scope':'overall',**overall});
        for k,v in by.items(): w.writerow({'scope':k,**v})
    (out/'mixed_selector_validation_report.md').write_text('# Mixed selector validation\n\n- total_records: %d\n- recovery: %d\n- current_correct_risk: %d\n' % (len(mixed),by['recovery']['records'],by['current_correct_risk']['records']),encoding='utf-8')
    print(out)

if __name__=='__main__':
    main()
