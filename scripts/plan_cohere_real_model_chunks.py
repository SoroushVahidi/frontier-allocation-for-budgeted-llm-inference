#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, itertools
from pathlib import Path

DATASETS="openai/gsm8k,HuggingFaceH4/MATH-500"
BUDGETS="2,4,6,8"
SEEDS="11,13,17"
METHODS="strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3"

def parse_csv(s): return [x.strip() for x in s.split(',') if x.strip()]

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--chunk-plan',required=True)
 p.add_argument('--datasets',default=DATASETS)
 p.add_argument('--budgets',default=BUDGETS)
 p.add_argument('--seeds',default=SEEDS)
 p.add_argument('--methods',default=METHODS)
 p.add_argument('--target-scored-per-slice',type=int,default=100)
 a=p.parse_args()
 rows=[]
 for i,(d,b,s,m) in enumerate(itertools.product(parse_csv(a.datasets),parse_csv(a.budgets),parse_csv(a.seeds),parse_csv(a.methods)),start=1):
  rows.append({'chunk_id':i,'dataset':d,'budget':int(b),'seed':int(s),'method':m,'target_scored_per_slice':a.target_scored_per_slice,'status':'planned'})
 out=Path(a.chunk_plan); out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
 print(f'wrote {len(rows)} chunks to {out}')

if __name__=='__main__': main()
