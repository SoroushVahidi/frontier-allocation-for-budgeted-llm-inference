#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,statistics
from collections import Counter,defaultdict
from pathlib import Path

def n(x): return str(x or '').strip().lower()

def resolve(p:str):
    q=Path(p)
    if q.is_file(): return q.parent,q
    return q,q/'per_example_records.jsonl'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--artifact',required=True)
    ap.add_argument('--method',action='append',default=[])
    ap.add_argument('--output-dir',default='')
    a=ap.parse_args()
    root,inp=resolve(a.artifact)
    out=Path(a.output_dir) if a.output_dir else root
    rows=[json.loads(l) for l in inp.read_text().splitlines() if l.strip()]
    idx=defaultdict(dict)
    for r in rows: idx[(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'))][r.get('method')]=r
    methods=a.method or sorted({r.get('method') for r in rows if str(r.get('method','')).startswith('direct_reserve_semantic_frontier_v2') and 'outcome' not in str(r.get('method')) and 'prm' not in str(r.get('method'))})
    summary={'total_scored_examples':len(idx),'l1_accuracy':0.0,'methods':{}}
    failures=[]
    l1_ok=0
    for key,mr in idx.items():
        l1=mr.get('external_l1_max')
        if not l1: continue
        gold=n(l1.get('gold_answer_canonical') or l1.get('gold_answer'))
        l1_pred=n(l1.get('final_answer_canonical') or l1.get('final_answer_raw'))
        l1c=(l1_pred==gold); l1_ok+=int(l1c)
        for m in methods:
            r=mr.get(m)
            if not r: continue
            md=r.get('result_metadata') or {}
            pool=md.get('selector_candidate_pool') or md.get('final_branch_states') or []
            cand=[n(x.get('predicted_answer') or x.get('final_answer') or x.get('answer')) for x in pool if isinstance(x,dict)]
            cand=[x for x in cand if x]
            groups=set(cand)
            pred=n(r.get('final_answer_canonical') or r.get('final_answer_raw') or r.get('selected_answer_canonical') or r.get('selected_answer_raw'))
            ok=(pred==gold)
            ms=summary['methods'].setdefault(m,{'accuracy_count':0,'l1_correct_ours_wrong':0,'gold_present':0,'gold_absent':0,'candidate_count':[],'answer_group_count':[],'direct_present':0,'frontier_present':0,'selected_direct':0,'selected_frontier':0,'l1_answer_in_pool':0,'common_absent_answers':Counter()})
            ms['accuracy_count']+=int(ok); ms['candidate_count'].append(len(cand)); ms['answer_group_count'].append(len(groups))
            srcs=[str(x.get('source_family') or x.get('source') or '') for x in pool if isinstance(x,dict)]
            ms['direct_present']+=int(any('direct' in s for s in srcs)); ms['frontier_present']+=int(any('frontier' in s for s in srcs))
            ms['selected_direct']+=int(any(n(x.get('predicted_answer'))==pred and 'direct' in str(x.get('source_family') or x.get('source') or '') for x in pool if isinstance(x,dict)))
            ms['selected_frontier']+=int(any(n(x.get('predicted_answer'))==pred and 'frontier' in str(x.get('source_family') or x.get('source') or '') for x in pool if isinstance(x,dict)))
            ms['l1_answer_in_pool']+=int(l1_pred in groups)
            if l1c and not ok:
                ms['l1_correct_ours_wrong']+=1
                if gold in groups: ms['gold_present']+=1
                else:
                    ms['gold_absent']+=1; ms['common_absent_answers'].update(groups or ['__empty__'])
                    failures.append({'example_id':key[0],'dataset':key[1],'method':m,'gold':gold,'ours_pred':pred,'l1_pred':l1_pred,'candidate_count':len(cand),'answer_group_count':len(groups),'l1_answer_in_pool':int(l1_pred in groups),'diagnosis':'true_generation_or_coverage_failure' if l1_pred not in groups else 'possible_extraction_or_normalization_failure'})
    total=max(1,len(idx)); summary['l1_accuracy']=l1_ok/total
    for m,ms in summary['methods'].items():
        nrows=max(1,len(ms['candidate_count']))
        ms['accuracy']=ms.pop('accuracy_count')/nrows
        for k in ['candidate_count','answer_group_count']:
            vals=ms[k]; ms[k+'_mean']=statistics.mean(vals) if vals else 0; ms[k+'_median']=statistics.median(vals) if vals else 0; ms[k+'_max']=max(vals) if vals else 0; del ms[k]
        ms['common_absent_answers']=ms['common_absent_answers'].most_common(10)
    out.mkdir(parents=True,exist_ok=True)
    with (out/'gold_absent_coverage_failures.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(failures[0].keys()) if failures else ['example_id','dataset','method']); w.writeheader(); w.writerows(failures)
    (out/'gold_absent_coverage_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(out/'gold_absent_coverage_failures.csv')
    print(out/'gold_absent_coverage_summary.json')
if __name__=='__main__': main()
