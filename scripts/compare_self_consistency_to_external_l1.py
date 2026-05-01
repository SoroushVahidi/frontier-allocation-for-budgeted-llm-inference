#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,sys
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from experiments.self_consistency_majority_selector import select_self_consistency_answer, evaluate_self_consistency_case, normalize_gsm8k_numeric_answer

def load_jsonl(p):
    with open(p,encoding='utf-8') as f:
        for l in f:
            if l.strip(): yield json.loads(l)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--paired-records',required=True); ap.add_argument('--output-dir',required=True); ap.add_argument('--max-examples',type=int,default=100); args=ap.parse_args()
    by=defaultdict(dict)
    for r in load_jsonl(args.paired_records):
        k=(r.get('dataset'),r.get('example_id'),r.get('seed'),r.get('budget')); by[k][r.get('method')]=r
    keys=[k for k,v in by.items() if 'direct_reserve_semantic_frontier_v2' in v and 'external_l1_max' in v][:args.max_examples]
    per=[]
    for k in keys:
        dr=by[k]['direct_reserve_semantic_frontier_v2']; ex=by[k]['external_l1_max']
        nodes=(dr.get('candidate_nodes') or (dr.get('result_metadata') or {}).get('selector_candidate_pool') or [])
        d=select_self_consistency_answer(nodes)
        e=evaluate_self_consistency_case(dr,d)
        gold=normalize_gsm8k_numeric_answer(dr.get('gold_answer_canonical') or '')
        orig=normalize_gsm8k_numeric_answer(dr.get('selected_answer_canonical') or dr.get('final_answer_canonical') or '')
        ext=normalize_gsm8k_numeric_answer(ex.get('selected_answer_canonical') or ex.get('final_answer_canonical') or '')
        sc=d['selected_normalized_answer']
        row={'dataset':k[0],'example_id':k[1],'seed':k[2],'budget':k[3],'original_dr_v2_answer':orig,'original_dr_v2_correct':int(orig==gold),'self_consistency_answer':sc,'self_consistency_correct':int(sc==gold), 'external_l1_max_answer':ext,'external_l1_max_correct':int(ext==gold), 'selected_cohere_answer':None,'selected_cohere_correct':None,
             'both_correct':int(sc==gold and ext==gold),'both_wrong':int(sc!=gold and ext!=gold),'self_consistency_only_correct':int(sc==gold and ext!=gold),'external_only_correct':int(ext==gold and sc!=gold),
             'fix':int((orig!=gold) and (sc==gold)),'break':int((orig==gold) and (sc!=gold))}
        if row['both_correct']: ft='both_correct'
        elif row['both_wrong']: ft='both_wrong'
        elif row['fix']: ft='self_consistency_fixed'
        elif row['break']: ft='self_consistency_broke'
        elif (sc!=gold) and any(normalize_gsm8k_numeric_answer((c.get('normalized_answer') or c.get('final_answer') or c.get('predicted_answer') or ''))==gold for c in nodes): ft='self_consistency_missed_gold_present'
        else: ft='discovery_absent_gold'
        row['failure_type']=ft
        row['vote_share']=d['vote_share']; row['tie_flag']=int(d['tie_flag']); row['valid_vote_count']=d['valid_vote_count']
        per.append(row)
    out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    n=max(1,len(per)); summary={'num_examples':len(per),'original_dr_v2_accuracy':sum(r['original_dr_v2_correct'] for r in per)/n,'self_consistency_accuracy':sum(r['self_consistency_correct'] for r in per)/n,'external_l1_max_accuracy':sum(r['external_l1_max_correct'] for r in per)/n,'fixes':sum(r['fix'] for r in per),'breaks':sum(r['break'] for r in per)}
    summary['net_fixes_minus_breaks']=summary['fixes']-summary['breaks']; summary['overrides_vs_original']=sum(int(r['self_consistency_answer']!=r['original_dr_v2_answer']) for r in per)
    summary['both_correct']=sum(r['both_correct'] for r in per); summary['both_wrong']=sum(r['both_wrong'] for r in per); summary['self_consistency_only_correct']=sum(r['self_consistency_only_correct'] for r in per); summary['external_only_correct']=sum(r['external_only_correct'] for r in per)
    summary['valid_answer_rate']=sum(r['valid_vote_count'] for r in per)/max(1,sum(r['valid_vote_count'] for r in per)); summary['tie_rate']=sum(r['tie_flag'] for r in per)/n; summary['average_vote_share']=sum(r['vote_share'] for r in per)/n
    (out/'per_case_comparison.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in per),encoding='utf-8')
    with (out/'per_case_comparison.csv').open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=list(per[0].keys()) if per else ['dataset']); w.writeheader(); w.writerows(per)
    (out/'comparison_summary.json').write_text(json.dumps(summary,indent=2)+'\n');
    with (out/'comparison_summary.csv').open('w',newline='',encoding='utf-8') as f: w=csv.writer(f); w.writerow(['metric','value']); [w.writerow([k,v]) for k,v in summary.items()]
    (out/'failure_breakdown.json').write_text(json.dumps(dict(Counter(r['failure_type'] for r in per)),indent=2)+'\n')
    (out/'self_consistency_casebook.jsonl').write_text((out/'per_case_comparison.jsonl').read_text(encoding='utf-8'),encoding='utf-8')
    (out/'vote_histograms.jsonl').write_text('',encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'paired_records':args.paired_records},indent=2)+'\n')
    (out/'comparison_report.md').write_text('# Self-consistency vs external_l1_max\n',encoding='utf-8')
    print(out)
if __name__=='__main__': main()
