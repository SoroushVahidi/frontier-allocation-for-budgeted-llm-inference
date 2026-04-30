#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, math
from pathlib import Path
from datetime import datetime, timezone

DR='direct_reserve_semantic_frontier_v2'
PRM='direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1'
MODES=['hybrid_mean_min','min_step','mean_step','product','last_step','hybrid_mean_min_major_error_cap']

def nrm(x): return str(x or '').strip().lower()

def agg(steps,mode):
    vals=[max(min(float(s.get('validity_score',0.5)),1.0),0.0) for s in steps] or [0.0]
    mean=sum(vals)/len(vals); m=min(vals); last=vals[-1]; prod=math.exp(sum(math.log(max(v,1e-3)) for v in vals)/len(vals))
    q=0.7*mean+0.3*m; p=[s.get('progress_score') for s in steps if s.get('progress_score') is not None]
    hybrid=0.7*q+0.3*(sum(float(x) for x in p)/len(p) if p else q)
    score={'hybrid_mean_min':hybrid,'min_step':m,'mean_step':mean,'product':prod,'last_step':last,'hybrid_mean_min_major_error_cap':hybrid}[mode]
    if any(bool(s.get('major_error')) for s in steps) and mode in {'hybrid_mean_min','hybrid_mean_min_major_error_cap','product'}: score=min(score,0.25)
    return score

def resolve_input(path_arg: str) -> tuple[Path, Path]:
    p=Path(path_arg)
    if p.is_file() and p.name=='per_example_records.jsonl':
        return p.parent,p
    if p.is_dir():
        return p,p/'per_example_records.jsonl'
    if p.suffix == ".jsonl":
        return p.parent,p
    return p,p/'per_example_records.jsonl'

def nearby_paths(base: Path) -> list[str]:
    root=base if base.exists() else Path('outputs')
    found=sorted(str(x) for x in root.rglob('per_example_records.jsonl')) if root.exists() else []
    return found[:12]

def write_manifest(out_dir: Path, **kw):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir/'prm_aggregation_mode_sweep.manifest.json').write_text(json.dumps(kw,indent=2)+'\n',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--artifact-dir',required=True);a=ap.parse_args()
    out_dir,input_file=resolve_input(a.artifact_dir)
    if not input_file.exists():
        candidates=nearby_paths(Path('outputs'))
        write_manifest(out_dir,input_path=str(input_file),row_count=0,available_methods=[],available_aggregation_modes=MODES,timestamp=datetime.now(timezone.utc).isoformat(),status='pending_missing_input',nearby_candidate_paths=candidates)
        raise SystemExit('Missing input file: '+str(input_file)+'\nNearby per_example_records.jsonl:\n- '+'\n- '.join(candidates or ['(none found)']))
    rows=[json.loads(l) for l in input_file.read_text().splitlines() if l.strip()]
    methods=sorted({r.get('method','') for r in rows})
    idx={(r.get('example_id'),r.get('dataset'),r.get('seed'),r.get('budget'),r.get('method')):r for r in rows}
    dr_cases=[k for k in idx if k[-1]==DR]
    out=[]
    for mode in MODES:
        corr=over=w=t=l=0
        for k in dr_cases:
            d=idx[k]; p=idx.get((*k[:-1],PRM))
            if not p: continue
            md=p.get('result_metadata') or {}
            tsc={cid:agg(steps,mode) for cid,steps in (md.get('prm_step_scores') or {}).items() if isinstance(steps,list)}
            pool=md.get('selector_candidate_pool') or d.get('result_metadata',{}).get('selector_candidate_pool') or []
            ans_by={str(x.get('branch_id') or x.get('candidate_id')):nrm(x.get('predicted_answer') or x.get('final_answer') or x.get('answer')) for x in pool if isinstance(x,dict)}
            groups={}
            for cid,sc in tsc.items():
                akey=ans_by.get(cid,'')
                if akey: groups[akey]=groups.get(akey,0.0)+sc
            d_ans=nrm(d.get('final_answer_canonical') or d.get('final_answer_raw')); gold=nrm(d.get('gold_answer_canonical') or d.get('gold_answer'))
            pred=max(groups.items(),key=lambda x:x[1])[0] if groups else nrm(p.get('final_answer_canonical') or p.get('final_answer_raw') or d_ans)
            ok=(pred==gold); d_ok=(d_ans==gold)
            corr+=ok; over+=pred!=d_ans
            if ok and not d_ok: w+=1
            elif ok and d_ok: t+=1
            elif (not ok) and d_ok: l+=1
        denom=max(1,len(dr_cases))
        out.append({'mode':mode,'correct_count':corr,'accuracy':corr/denom,'paired_vs_dr_v2_w_t_l':f'{w}/{t}/{l}','overrides_vs_dr_v2':over,'beats_prm_20_of_30':corr>20,'beats_dr_v2_16_of_30':corr>16})
    with (out_dir/'prm_aggregation_mode_sweep.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
    best=max(out,key=lambda r:r['correct_count']) if out else None
    Path('docs/PRM_AGGREGATION_MODE_ANALYSIS_20260429.md').write_text('# PRM Aggregation Mode Analysis\n\nBest mode: '+json.dumps(best)+'\n',encoding='utf-8')
    write_manifest(out_dir,input_path=str(input_file),row_count=len(rows),available_methods=methods,available_aggregation_modes=MODES,timestamp=datetime.now(timezone.utc).isoformat(),status='complete')

if __name__=='__main__': main()
