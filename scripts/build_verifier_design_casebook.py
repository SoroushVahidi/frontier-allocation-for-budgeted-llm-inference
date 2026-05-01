#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,datetime
from pathlib import Path
import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.analyze_offline_selector_variants import load_cases, select

def main():
 p=argparse.ArgumentParser();p.add_argument('--artifact-dir',required=True);p.add_argument('--tournament-results',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args()
 rows=[json.loads(l) for l in Path(a.artifact_dir,'per_example_records.jsonl').read_text().splitlines() if l.strip()]
 cases=load_cases(rows)
 results=list(csv.DictReader(open(a.tournament_results)))
 deploy=[r for r in results if r['selector']!='oracle_selector']
 best=max(deploy,key=lambda r:(float(r['accuracy']),float(r['net_fixes_minus_breaks']),-float(r['breaks'])))['selector']
 out=[]
 counts={'oracle_fixable':0,'heuristic_fixed':0,'heuristic_broken':0,'l1_correct_dr_wrong':0,'l1_wrong_dr_correct':0}
 for c in cases:
  gold=c['gold']; dr=c['dr_pred']; l1=c['l1_pred']; ora=select('oracle_selector',c); heu=select(best,c)
  dr_ok=dr==gold; l1_ok=l1==gold; ora_ok=ora==gold; heu_ok=heu==gold
  if (not dr_ok) and ora_ok: counts['oracle_fixable']+=1
  if (not dr_ok) and heu_ok: counts['heuristic_fixed']+=1
  if dr_ok and (not heu_ok): counts['heuristic_broken']+=1
  if l1_ok and (not dr_ok): counts['l1_correct_dr_wrong']+=1
  if (not l1_ok) and dr_ok: counts['l1_wrong_dr_correct']+=1
  out.append({'example_id':c['key'][0],'question':c.get('question',''),'gold_answer':gold,'l1_answer':l1,'l1_correct':int(l1_ok),'dr_answer':dr,'dr_correct':int(dr_ok),'oracle_answer':ora,'oracle_correct':int(ora_ok),'best_heuristic_selector':best,'best_heuristic_answer':heu,'best_heuristic_correct':int(heu_ok),'candidate_answers':'|'.join(g['normalized_answer'] for g in c['groups']),'candidate_support_counts':json.dumps({g['normalized_answer']:g.get('support_count',0) for g in c['groups']}),'source_families':json.dumps({g['normalized_answer']:g.get('source_family','') for g in c['groups']}),'reasoning_snippets':json.dumps({g['normalized_answer']:g.get('trace','')[:120] for g in c['groups']}),'consistency_flags':json.dumps({g['normalized_answer']:g.get('consistency_flags',{}) for g in c['groups']}),'heuristic_effect':('fix' if ((not dr_ok) and heu_ok) else ('break' if (dr_ok and (not heu_ok)) else 'no_change')),'ov_need':'distinguish numerically close candidates using final-answer validity + trace consistency'})
 od=Path(a.out_dir);od.mkdir(parents=True,exist_ok=True)
 with open(od/'verifier_design_casebook.csv','w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
 summary={'best_heuristic_selector':best,**counts,'total_cases':len(out)}
 (od/'verifier_design_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 rep=['# Verifier design casebook','',f"- best heuristic selector: {best}"]+[f"- {k}: {v}" for k,v in counts.items()]+['','## Pattern','- Heuristic fixes some DR misses but also breaks correct DR cases; verifier should use answer+trace quality margin to reduce false flips.']
 (od/'verifier_design_report.md').write_text('\n'.join(rep)+'\n')
 # design doc
 ts=datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
 doc=Path('docs',f'OUTCOME_VERIFIER_SELECTOR_DESIGN_FROM_50CASE_{ts}.md')
 doc.write_text('# Outcome verifier selector design\n\n- Input: question, candidate answer, optional trace snippet.\n- Candidate grouping: normalized answer groups with support/source-family features.\n- Score output: probability candidate is correct in [0,1].\n- Selection: keep DR default; override only if verifier margin >= m and challenger not flagged high-risk.\n- Logging: per-candidate score, margin, selected answer, blocked reasons, override flag.\n- Offline eval: replay compact artifact with mock scores; report accuracy/fixes/breaks/net/overrides.\n')
 print(od); print(doc)

if __name__=='__main__': main()
