#!/usr/bin/env python3
import json,csv,argparse
from pathlib import Path
import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.selector_reconstruction import reconstruct_groups, support_only_choice

def n(x): return str(x or '').strip().lower()

def main():
 p=argparse.ArgumentParser();p.add_argument('--artifact-dir',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args()
 ad=Path(a.artifact_dir);out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 rows=[json.loads(l) for l in open(ad/'per_example_records.jsonl') if l.strip()]
 idx={(r['example_id'],r['dataset'],r['seed'],r['budget'],r['method']):r for r in rows}
 cases=[]
 for k,r in idx.items():
  if r['method']!='direct_reserve_semantic_frontier_v2': continue
  kk=k[:-1]; l1=idx.get((*kk,'external_l1_max'))
  if not l1: continue
  groups=reconstruct_groups(r)
  counts={g['normalized_answer']:g['support_count'] for g in groups}; fam={g['normalized_answer']:set(g['source_families']) for g in groups}
  dr_ans=n(r.get('final_answer_canonical') or r.get('final_answer_raw')); gold=n(r.get('gold_answer_canonical') or r.get('gold_answer'))
  sup=support_only_choice(groups, dr_ans)
  dr_ok=dr_ans==gold; sup_ok=sup==gold
  cand=list(counts.keys())
  gold_present=gold in counts
  if (not dr_ok) and sup_ok: ctype='support_only_fix'
  elif dr_ok and (not sup_ok): ctype='support_only_break'
  elif (not dr_ok) and (not sup_ok) and gold_present: ctype='oracle_only_recoverable'
  elif (not dr_ok) and (not sup_ok): ctype='unchanged_failure'
  else: ctype='unchanged_correct_or_irrelevant'
  if ctype=='unchanged_correct_or_irrelevant': continue
  cases.append({'example_id':kk[0],'dataset':kk[1],'seed':kk[2],'budget':kk[3],'case_type':ctype,'gold_answer':gold,'dr_selected':dr_ans,'dr_correct':int(dr_ok),'support_selected':sup,'support_correct':int(sup_ok),'all_candidates':'|'.join(cand),'support_counts':json.dumps(counts,sort_keys=True),'source_families':json.dumps({k:sorted(v) for k,v in fam.items()},sort_keys=True),'multi_family_answers':'|'.join(sorted([a for a,v in fam.items() if len(v)>1])),'question':r.get('question','')})
 with open(out/'support_only_casebook.csv','w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(cases[0].keys()) if cases else ['example_id']);w.writeheader();w.writerows(cases)
 from collections import Counter
 c=Counter(x['case_type'] for x in cases)
 lines=['# Support-only pattern analysis','',f"- total_casebook_rows: {len(cases)}",f"- support_only_fixes: {c.get('support_only_fix',0)}",f"- support_only_breaks: {c.get('support_only_break',0)}",f"- unchanged_failures: {c.get('unchanged_failure',0)}",f"- oracle_only_recoverable: {c.get('oracle_only_recoverable',0)}",'', '## Main pattern','- Fixes tend to be higher-support alternatives; breaks occur where support plurality selects a wrong but frequent answer without stronger reliability signals.']
 (out/'support_only_pattern_report.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__': main()
