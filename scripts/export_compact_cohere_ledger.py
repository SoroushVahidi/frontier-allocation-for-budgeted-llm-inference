#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

FIELDS=["provider","dataset","seed","budget","method","example_id","status","exact_match","attempted","scored","failed","skipped","retry_attempts","input_tokens","output_tokens","total_tokens","latency_seconds","estimated_cost_usd"]

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--timestamp',required=True)
 p.add_argument('--output-root',default='outputs')
 p.add_argument('--out-csv',default='compact_per_example_ledger.csv')
 a=p.parse_args()
 out=Path(a.output_root)/f'cohere_real_model_cost_normalized_validation_{a.timestamp}'
 src=out/'per_example_records.jsonl'; dst=out/a.out_csv
 rows=[]
 if src.exists():
  for line in src.open(encoding='utf-8'):
   r=json.loads(line)
   rows.append({k:r.get(k,'') for k in FIELDS})
 with dst.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
 print(f'wrote {len(rows)} rows to {dst}')

if __name__=='__main__': main()
