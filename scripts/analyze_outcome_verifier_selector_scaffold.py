#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.analyze_offline_selector_variants import load_cases

def load_scores(path:Path):
 d={}
 for r in csv.DictReader(path.open()):
  d[(r['example_id'],r['candidate_answer'])]=float(r['score'])
 return d

def main():
 p=argparse.ArgumentParser();p.add_argument('--artifact-dir',required=True);p.add_argument('--scores-csv',required=True);p.add_argument('--margin',type=float,default=0.1);p.add_argument('--out-dir',required=True);a=p.parse_args()
 cases=load_cases([json.loads(l) for l in Path(a.artifact_dir,'per_example_records.jsonl').read_text().splitlines() if l.strip()])
 sc=load_scores(Path(a.scores_csv))
 corr=fix=brk=ov=ovc=0
 for c in cases:
  dr=c['dr_pred']; gold=c['gold']
  cands=[g['normalized_answer'] for g in c['groups']]
  best=max(cands,key=lambda ans: sc.get((c['key'][0],ans),0.0)) if cands else dr
  best_s=sc.get((c['key'][0],best),0.0); dr_s=sc.get((c['key'][0],dr),0.0)
  pred=best if (best!=dr and best_s-dr_s>=a.margin) else dr
  dok=dr==gold; ok=pred==gold
  corr+=ok; ov+=int(pred!=dr); ovc+=int(pred!=dr and ok); fix+=int((not dok) and ok); brk+=int(dok and (not ok))
 out={'accuracy':corr/len(cases),'fixes':fix,'breaks':brk,'net_fixes_minus_breaks':fix-brk,'overrides':ov,'override_precision':(ovc/ov if ov else 0.0),'margin':a.margin,'total_cases':len(cases)}
 od=Path(a.out_dir);od.mkdir(parents=True,exist_ok=True)
 (od/'verifier_selector_scaffold_summary.json').write_text(json.dumps(out,indent=2)+'\n')
 print(od/'verifier_selector_scaffold_summary.json')

if __name__=='__main__': main()
