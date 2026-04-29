#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

def read_csv(p: Path):
    if not p.exists() or p.stat().st_size==0: return []
    with p.open('r',encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def write_csv(p: Path, rows, fieldnames=None):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8',newline='') as f:
        if not rows:
            if fieldnames: csv.DictWriter(f,fieldnames=fieldnames).writeheader()
            return
        w=csv.DictWriter(f,fieldnames=fieldnames or list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def f(x, d=0.0):
    try:return float(x)
    except:return d

def i(x, d=0):
    try:return int(float(x))
    except:return d

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output-dir',required=True)
    args=ap.parse_args()
    out=Path(args.output_dir); out = out if out.is_absolute() else REPO_ROOT/out

    per_case=read_csv(out/'per_case_results.csv')
    method_summary=read_csv(out/'method_summary.csv')
    pairwise=read_csv(out/'pairwise_comparisons.csv')
    token_summary=read_csv(out/'token_latency_cost_summary.csv')
    manifest_path=out/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    grouped=defaultdict(list)
    for r in per_case:
        status = str(r.get('status', '')).strip().lower()
        if status and status != 'scored':
            continue
        grouped[r.get('method','')].append(r)
    uniq_rows=[]
    for m,rows in sorted(grouped.items()):
        by_ex={}
        for r in rows: by_ex.setdefault(r.get('example_id',''),[]).append(r)
        vals=[]
        for lst in by_ex.values():
            vals.append(max(i(x.get('exact_match', x.get('is_correct', x.get('status_ok', 0)))) for x in lst))
        uniq_rows.append({'method':m,'n_unique_examples':len(vals),'unique_example_accuracy':round(sum(vals)/len(vals),6) if vals else 0.0})
    write_csv(out/'unique_example_method_summary.csv', uniq_rows, fieldnames=['method','n_unique_examples','unique_example_accuracy'])

    # paired vs best external
    externals={'external_l1_max','tale','external_tale_prompt_budgeting','s1','external_s1_budget_forcing'}
    ext_methods=[m for m in grouped if m in externals]
    best_ext='external_l1_max'
    if method_summary:
        acc={r.get('method',''):f(r.get('mean_accuracy_across_slices',r.get('accuracy',0))) for r in method_summary}
        if ext_methods:
            best_ext=max(ext_methods,key=lambda m:acc.get(m,0.0))
    paired_best=[r for r in pairwise if r.get('method_a')==best_ext or r.get('method_b')==best_ext or best_ext in str(r.get('comparison',''))]
    write_csv(out/'paired_vs_best_external.csv', paired_best, fieldnames=list(pairwise[0].keys()) if pairwise else None)

    # cost normalized leaderboard
    cost_rows=[]
    for r in token_summary:
        acc=f(r.get('accuracy',0)); cost=f(r.get('avg_estimated_cost_usd',0)); acts=f(r.get('avg_actions',0))
        cost_rows.append({'method':r.get('method',''),'accuracy':acc,'avg_actions':acts,'avg_estimated_cost_usd':cost,'acc_per_cost':(acc/cost if cost>0 else 0.0),'acc_per_action':(acc/acts if acts>0 else 0.0)})
    cost_rows=sorted(cost_rows,key=lambda x:x['acc_per_cost'],reverse=True)
    write_csv(out/'cost_normalized_leaderboard.csv', cost_rows)

    # coverage gap report
    expected = len(
        set(
            (r.get('dataset', ''), r.get('seed', ''), r.get('budget', ''), r.get('example_id', ''))
            for r in per_case
            if str(r.get('example_id', '')).strip()
        )
    )
    gaps=[]
    for m,rows in grouped.items():
        seen=len(set((r.get('dataset',''),r.get('seed',''),r.get('budget',''),r.get('example_id','')) for r in rows if r.get('example_id')))
        gaps.append({'method':m,'expected_slots':expected,'covered_slots':seen,'missing_slots':max(0,expected-seen)})
    write_csv(out/'coverage_gap_report.csv', gaps)

    requested=manifest.get('methods') or []
    available=set(grouped)
    excluded=[{'method':m,'reason':'no_scored_rows'} for m in requested if m not in available]
    write_csv(out/'methods_excluded.csv', excluded, fieldnames=['method','reason'])

    status={'output_dir':str(out),'has_per_case_results':(out/'per_case_results.csv').exists(),'has_method_summary':(out/'method_summary.csv').exists(),'postprocess_ok':True}
    (out/'run_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
