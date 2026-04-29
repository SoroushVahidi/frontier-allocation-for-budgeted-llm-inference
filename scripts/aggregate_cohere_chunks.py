#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,math,random
from collections import defaultdict
from pathlib import Path

def load_csv(path):
 if not path.exists(): return []
 with path.open() as f: return list(csv.DictReader(f))

def boot(vals,n=1000):
 if len(vals)<5:return (None,None)
 rng=random.Random(7);b=[];L=len(vals)
 for _ in range(n): b.append(sum(vals[rng.randrange(L)] for __ in range(L))/L)
 b.sort(); return (b[int(.025*(n-1))],b[int(.975*(n-1))])

def main():
 p=argparse.ArgumentParser(); p.add_argument('--chunk-plan',required=True); p.add_argument('--timestamp',required=True); p.add_argument('--output-root',default='outputs'); a=p.parse_args()
 out=Path(a.output_root)/f'cohere_real_model_cost_normalized_validation_{a.timestamp}'
 plan=load_csv(Path(a.chunk_plan)); slices=load_csv(out/'slice_summary.csv'); pairs=load_csv(out/'pairwise_comparisons.csv')
 target={(r['dataset'],r['budget'],r['seed'],r['method']):int(r['target_scored_per_slice']) for r in plan}
 final=[]; failed=[]
 for s in slices:
  k=(s['dataset'],s['budget'],s['seed'],s['method']); t=target.get(k,0); scored=int(float(s.get('scored_examples',0) or 0))
  s['target_scored_count']=t; s['is_final']='yes' if scored>=t and t>0 else 'no';
  (final if s['is_final']=='yes' else failed).append(s)
 with (out/'codex_per_slice_finality.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list((final or failed or [{}])[0].keys())); w.writeheader(); w.writerows(final+failed)
 m=defaultdict(lambda:{'n':0,'acc':[],'tok':0.0,'cost':0.0,'lat':[]})
 for s in final:
  mm=m[s['method']]; mm['n']+=1; mm['acc'].append(float(s.get('accuracy',0) or 0)); mm['tok']+=float(s.get('total_tokens',0) or 0); mm['cost']+=float(s.get('estimated_cost_usd',0) or 0); mm['lat'].append(float(s.get('avg_latency_seconds',0) or 0))
 mrows=[]
 for k,v in m.items(): mrows.append({'method':k,'final_slices':v['n'],'mean_accuracy':sum(v['acc'])/max(1,len(v['acc'])),'total_tokens':v['tok'],'total_cost_usd':v['cost'],'mean_latency_seconds':sum(v['lat'])/max(1,len(v['lat']))})
 with (out/'codex_method_summary_final_only.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list((mrows or [{}])[0].keys())); w.writeheader(); w.writerows(mrows)
 pairrows=[]
 for p0 in pairs:
  if p0.get('method_b')=='external_l1_max':
   d=float(p0.get('accuracy_delta_a_minus_b',0) or 0); pairrows.append({**p0,'ci95_lo':boot([d])[0],'ci95_hi':boot([d])[1]})
 with (out/'codex_pairwise_vs_external_l1_max.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list((pairrows or [{}])[0].keys())); w.writeheader(); w.writerows(pairrows)
 (out/'codex_failed_or_incomplete_slices.csv').write_text('')
 if failed:
  with (out/'codex_failed_or_incomplete_slices.csv').open('w',newline='',encoding='utf-8') as f:
   w=csv.DictWriter(f,fieldnames=list(failed[0].keys()));w.writeheader();w.writerows(failed)
 md=Path('docs')/f'CODEX_LOCAL_COHERE_AGGREGATE_{a.timestamp}.md'
 md.write_text(f"# Codex local aggregate ({a.timestamp})\n\nFinal slices: {len(final)} / {len(target)} planned.\n\nPartial run only unless all planned slices final.\n",encoding='utf-8')
 print(f'wrote aggregate artifacts under {out} and {md}')

if __name__=='__main__': main()
