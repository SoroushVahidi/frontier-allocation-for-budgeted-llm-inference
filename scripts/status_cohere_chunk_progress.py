#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv
from pathlib import Path

def load_csv(path):
 if not path.exists(): return []
 with path.open() as f: return list(csv.DictReader(f))

def main():
 p=argparse.ArgumentParser(); p.add_argument('--chunk-plan',required=True); p.add_argument('--timestamp',required=True); p.add_argument('--output-root',default='outputs'); a=p.parse_args()
 plan=load_csv(Path(a.chunk_plan))
 out=Path(a.output_root)/f'cohere_real_model_cost_normalized_validation_{a.timestamp}'
 out.mkdir(parents=True, exist_ok=True)
 slices=load_csv(out/'slice_summary.csv'); pair=load_csv(out/'pairwise_comparisons.csv')
 smap={(r['provider'],r['dataset'],r['seed'],r['budget'],r['method']):r for r in slices}
 pairset={(r.get('provider'),r.get('budget'),r.get('dataset')) for r in pair if r.get('comparison','').endswith('external_l1_max')}
 rows=[]
 for r in plan:
  k=('cohere',r['dataset'],r['seed'],r['budget'],r['method'])
  s=smap.get(k,{})
  scored=int(float(s.get('scored_examples',0) or 0)); target=int(r['target_scored_per_slice'])
  status='planned' if not s else ('completed' if scored>=target else ('failed' if int(float(s.get('failed_examples',0) or 0))>0 and scored==0 else 'incomplete'))
  rows.append({'chunk_id':r['chunk_id'],'dataset':r['dataset'],'budget':r['budget'],'seed':r['seed'],'method':r['method'],'status':status,'scored_count':scored,'target_scored_count':target,'accuracy':s.get('accuracy',0),'tokens':s.get('total_tokens',0),'estimated_cost':s.get('estimated_cost_usd',0),'failures':s.get('failed_examples',0),'skips':s.get('skipped_examples',0),'pairwise_vs_external_l1_max_available':'yes' if ('cohere',r['budget'],r['dataset']) in pairset else 'no'})
 field=list(rows[0].keys())
 with (out/'chunk_progress_status.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=field);w.writeheader();w.writerows(rows)
 print(f'wrote {out / "chunk_progress_status.csv"}')

if __name__=='__main__': main()
