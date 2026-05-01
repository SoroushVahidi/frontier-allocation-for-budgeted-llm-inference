#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.analyze_offline_selector_variants import load_cases, select
from scripts.run_conservative_outcome_verifier_override_v1 import conservative_override_choice, conservative_override_choice_v2

def resolve(p:str)->Path:
    q=Path(p)
    return q if q.is_file() else q/'per_example_records.jsonl'

def run(rows:list[dict]):
    cases=load_cases(rows)
    idx={(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'),r.get('method')):r for r in rows}
    dr_key='direct_reserve_semantic_frontier_v2'
    selectors=['current_dr_v2','support_only','support_only_with_guard_v1','conservative_outcome_verifier_override_v1','conservative_outcome_verifier_override_v2','consistency_penalized','unified_confidence_error','hybrid_support_confidence_consistency','source_aware_direct_reserve_prior','oracle_selector']
    out=[]; casebook=[]
    dr_acc=sum(int(c['dr_pred']==c['gold']) for c in cases)/max(1,len(cases))
    l1_acc=sum(int(c['l1_pred']==c['gold']) for c in cases)/max(1,len(cases))
    for s in selectors:
        corr=fix=brk=ov=ovc=gp=ga=fail_sel=fail_cov=0
        for c in cases:
            k=c['key']; drrow=idx.get((*k,dr_key),{})
            if s=='current_dr_v2': pred=c['dr_pred']; reasons=['keep_current']
            elif s=='conservative_outcome_verifier_override_v1':
                g,rs=conservative_override_choice(drrow); pred=g if g in [x['normalized_answer'] for x in c['groups']] else c['dr_pred']; reasons=rs.get('reasons',[])
            elif s=='conservative_outcome_verifier_override_v2':
                g,rs=conservative_override_choice_v2(drrow); pred=g if g in [x['normalized_answer'] for x in c['groups']] else c['dr_pred']; reasons=rs.get('reasons',[])+rs.get('blocked_conditions',[])
            else:
                rule='actual_current_selector' if s=='current_dr_v2' else s
                pred=select(rule,c); reasons=[]
            ok=int(pred==c['gold']); dr_ok=int(c['dr_pred']==c['gold']); corr+=ok
            changed=int(pred!=c['dr_pred']); ov+=changed; ovc+=int(changed and ok)
            fix+=int((not dr_ok) and ok); brk+=int(dr_ok and (not ok))
            gold_present=any(g['normalized_answer']==c['gold'] for g in c['groups'])
            gp += int((not dr_ok) and ok and gold_present)
            ga += int((not dr_ok) and ok and (not gold_present))
            fail_sel += int(gold_present and (not ok)); fail_cov += int((not gold_present) and (not ok))
            if changed:
                casebook.append({'selector':s,'example_id':k[0],'gold':c['gold'],'l1_answer':c['l1_pred'],'l1_correct':int(c['l1_pred']==c['gold']),'dr_answer':c['dr_pred'],'dr_correct':dr_ok,'selector_answer':pred,'selector_correct':ok,'candidate_groups':json.dumps([g['normalized_answer'] for g in c['groups']]),'support_counts':json.dumps({g['normalized_answer']:g.get('support_count',0) for g in c['groups']}),'source_families':json.dumps({g['normalized_answer']:g.get('source_family','') for g in c['groups']}),'decision_reasons':'|'.join(reasons),'change_type':'fix' if ((not dr_ok) and ok) else ('break' if (dr_ok and (not ok)) else 'other')})
        acc=corr/max(1,len(cases))
        out.append({'selector':s,'accuracy':acc,'delta_vs_current_dr_v2':acc-dr_acc,'delta_vs_external_l1_max':acc-l1_acc,'fixes':fix,'breaks':brk,'net_fixes_minus_breaks':fix-brk,'overrides':ov,'override_precision':(ovc/ov if ov else 0.0),'gold_present_failure_recoveries':gp,'gold_absent_failure_recoveries':ga,'selector_failure_remaining':fail_sel,'coverage_failure_remaining':fail_cov})
    deploy=[r for r in out if r['selector']!='oracle_selector']
    deploy.sort(key=lambda r:(-r['accuracy'],-r['net_fixes_minus_breaks'],r['breaks'],len(r['selector'])))
    return out, casebook, (deploy[0] if deploy else None)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--artifact-dir',required=True);ap.add_argument('--output-dir',required=True);a=ap.parse_args()
    rows=[json.loads(l) for l in resolve(a.artifact_dir).read_text().splitlines() if l.strip()]
    out,casebook,best=run(rows)
    od=Path(a.output_dir);od.mkdir(parents=True,exist_ok=True)
    with open(od/'selector_tournament_results.csv','w',newline='') as f:
      w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
    with open(od/'selector_tournament_casebook.csv','w',newline='') as f:
      w=csv.DictWriter(f,fieldnames=list(casebook[0].keys()) if casebook else ['selector']);w.writeheader();w.writerows(casebook)
    summ={'selectors':out,'best_deployable_selector':best}
    (od/'selector_tournament_summary.json').write_text(json.dumps(summ,indent=2)+'\n')
    (od/'selector_tournament_report.md').write_text('# Selector tournament\n\n- best deployable: '+(best['selector'] if best else 'none')+'\n')
    print(od)

if __name__=='__main__': main()
