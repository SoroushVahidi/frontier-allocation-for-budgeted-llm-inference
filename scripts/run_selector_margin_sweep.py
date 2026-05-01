#!/usr/bin/env python3
import argparse, json, csv, subprocess, sys
from pathlib import Path

def mtag(x): return f"{x:.2f}".replace('.','p')

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--paired-records',required=True); ap.add_argument('--selected-config',required=True); ap.add_argument('--score-cache',required=True); ap.add_argument('--output-dir',required=True); ap.add_argument('--max-examples',type=int,required=True); ap.add_argument('--margins',required=True)
 a=ap.parse_args(); out=Path(a.output_dir); (out/'per_margin_comparisons').mkdir(parents=True,exist_ok=True)
 cfg=json.load(open(a.selected_config)); rows=[]
 for m in [float(x) for x in a.margins.split(',')]:
  cfg2=dict(cfg); cfg2['min_verifier_margin']=m
  cpath=out/f'cfg_{mtag(m)}.json'; cpath.write_text(json.dumps(cfg2))
  od=out/'per_margin_comparisons'/f'margin_{mtag(m)}'
  subprocess.check_call([sys.executable,'scripts/apply_selected_selector_to_paired_validation.py','--paired-records',a.paired_records,'--selected-config',str(cpath),'--score-cache',a.score_cache,'--max-examples',str(a.max_examples),'--output-dir',str(od),'--require-full-coverage'])
  s=json.load(open(od/'comparison_summary.json')); s['margin']=m; s['override_precision']=s['fixes']/max(1,s['actual_selector_overrides']); rows.append(s)
 best=sorted(rows,key=lambda r:(r['selected_selector_accuracy'],r['net_fixes_minus_breaks'],-r['breaks'],-r['actual_selector_overrides']),reverse=True)[0]
 (out/'margin_sweep_summary.json').write_text(json.dumps(rows,indent=2))
 with open(out/'margin_sweep_summary.csv','w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
 (out/'manifest.json').write_text(json.dumps({'margins':a.margins,'max_examples':a.max_examples},indent=2))
 (out/'margin_sweep_report.md').write_text('\n'.join([f"- margin {r['margin']:.2f}: acc={r['selected_selector_accuracy']:.3f}, breaks={r['breaks']}, net={r['net_fixes_minus_breaks']}" for r in rows]))
 d=out.parent/f"fully_scored_selector_pilot50_decision_{out.name.split('_')[-1]}"; d.mkdir(parents=True,exist_ok=True)
 decision={'recommended_margin':best['margin'],'margin_0p0_best':best['margin']==0.0,'selected_vs_external_delta_at_best':best['delta_selected_vs_external'],'residual_bottleneck':'selector_side' if best['selector_bottleneck_share_among_selected_wrong']>=best['discovery_bottleneck_share_among_selected_wrong'] else 'discovery_side','keep_config_unchanged':best['margin']==0.0}
 (d/'pilot50_selector_margin_decision.json').write_text(json.dumps(decision,indent=2))
 with open(d/'pilot50_selector_margin_decision.csv','w',newline='') as f:
  w=csv.writer(f); [w.writerow([k,v]) for k,v in decision.items()]
 (d/'pilot50_selector_margin_decision.md').write_text('\n'.join([f"- {k}: {v}" for k,v in decision.items()]))

if __name__=='__main__': main()
