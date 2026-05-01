#!/usr/bin/env python3
import argparse, json, hashlib
from pathlib import Path

def key(r): return r.get('item_hash') or hashlib.sha256((str(r.get('case_id'))+'|'+str(r.get('candidate_id'))).encode()).hexdigest()

def main():
 p=argparse.ArgumentParser(); p.add_argument('--cache',action='append',required=True); p.add_argument('--call-plan'); p.add_argument('--output-dir',required=True); a=p.parse_args()
 out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
 m={}; total=0
 for c in a.cache:
  for l in open(c):
   if l.strip(): r=json.loads(l); m[key(r)]=r; total+=1
 with open(out/'verifier_scores_merged.jsonl','w') as f:
  for r in m.values(): f.write(json.dumps(r)+'\n')
 missing=0
 if a.call_plan:
  for l in open(a.call_plan):
   if l.strip() and key(json.loads(l)) not in m: missing+=1
 s={'input_rows':total,'merged_rows':len(m),'duplicates_removed':total-len(m),'missing_call_plan_items_after_merge':missing,'no_gold_oracle_evaluation_only_correct_answer_in_scores':all(all(t not in json.dumps(r).lower() for t in ['gold_answer','oracle','evaluation_only','correct_answer']) for r in m.values())}
 (out/'merge_summary.json').write_text(json.dumps(s,indent=2)); (out/'merge_report.md').write_text('\n'.join([f"- {k}: {v}" for k,v in s.items()]))

if __name__=='__main__': main()
