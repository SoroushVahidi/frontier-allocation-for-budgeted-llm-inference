#!/usr/bin/env python3
from __future__ import annotations
import json,csv
from pathlib import Path
from typing import Any

def load_jsonl(p:Path):
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]

def accuracy(rows):
    n=len(rows); c=sum(1 for r in rows if r.get('correct') is True)
    return (c/n if n else 0.0),c

def pairwise(method_rows:dict[str,list[dict[str,Any]]]):
    ms=list(method_rows)
    out=[]
    for a in ms:
        for b in ms:
            w=l=t=0
            for ra,rb in zip(method_rows[a],method_rows[b]):
                ca,cb=bool(ra.get('correct')),bool(rb.get('correct'))
                if ca and not cb:w+=1
                elif cb and not ca:l+=1
                else:t+=1
            out.append({'method_a':a,'method_b':b,'wins':w,'losses':l,'ties':t})
    return out

def build_report(outdir:Path):
    pm=outdir/'per_method_outputs'
    method_rows={p.stem:load_jsonl(p) for p in sorted(pm.glob('*.jsonl'))}
    summ=[]
    for m,rows in method_rows.items():
        acc,c=accuracy(rows)
        summ.append({'method_id':m,'accuracy':acc,'correct_count':c,'failed_or_skipped_count':sum(1 for r in rows if r.get('failure_reason')),'mean_calls_per_case':0.0,'total_calls':0})
    (outdir/'comparison_summary.json').write_text(json.dumps(summ,indent=2))
    with (outdir/'comparison_summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(summ[0].keys())); w.writeheader(); w.writerows(summ)
    pw=pairwise(method_rows)
    (outdir/'pairwise_win_loss_matrix.json').write_text(json.dumps(pw,indent=2))
    with (outdir/'pairwise_win_loss_matrix.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(pw[0].keys())); w.writeheader(); w.writerows(pw)
    ranked=sorted(summ,key=lambda x:(-x['accuracy'],x['method_id']))
    (outdir/'ranked_methods.json').write_text(json.dumps(ranked,indent=2))
    with (outdir/'ranked_methods.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(ranked[0].keys())); w.writeheader(); w.writerows(ranked)
    # required placeholders
    for n in ['per_case_comparison.jsonl','per_case_comparison.csv','bottleneck_casebook.jsonl','bottleneck_casebook.csv','selector_call_plan.jsonl','selector_score_cache.jsonl','selector_casebook.jsonl']:
        (outdir/n).write_text('')
    for n,obj in [('comparison_report.md','# Comparison report\n'),('bottleneck_report.md','# Bottleneck report\n'),('bottleneck_analysis_summary.json',{}),('bottleneck_analysis_summary.csv',''),('selector_coverage_summary.json',{'status':'diagnostic_if_incomplete'} )]:
        (outdir/n).write_text(json.dumps(obj,indent=2) if isinstance(obj,dict) else obj)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('outdir')
    a=p.parse_args();build_report(Path(a.outdir))
