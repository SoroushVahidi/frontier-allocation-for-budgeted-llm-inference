#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,subprocess,time,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--chunk-id',type=int,required=True)
 p.add_argument('--chunk-plan',required=True)
 p.add_argument('--timestamp',required=True)
 p.add_argument('--max-walltime-minutes',type=int,default=20)
 p.add_argument('--providers',default='cohere')
 p.add_argument('--cohere-model',default='command-r-plus-08-2024')
 p.add_argument('--output-root',default='outputs')
 a=p.parse_args()
 with Path(a.chunk_plan).open() as f:
  row=next((r for r in csv.DictReader(f) if int(r['chunk_id'])==a.chunk_id),None)
 if not row: raise SystemExit(f'chunk_id {a.chunk_id} not found')
 cmd=[sys.executable,'scripts/run_cohere_real_model_cost_normalized_validation.py','--timestamp',a.timestamp,'--providers',a.providers,'--cohere-model',a.cohere_model,'--datasets',row['dataset'],'--budgets',row['budget'],'--seeds',row['seed'],'--methods',row['method'],'--target-scored-per-slice',row['target_scored_per_slice'],'--max-examples',row['target_scored_per_slice'],'--resume','--emit-trace-audit','--output-root',a.output_root]
 print('command:', ' '.join(cmd))
 t0=time.time();
 proc=subprocess.run(cmd,timeout=max(60,a.max_walltime_minutes*60),check=False)
 print(f'exit_code={proc.returncode} elapsed_sec={time.time()-t0:.1f}')
 return proc.returncode

if __name__=='__main__': raise SystemExit(main())
