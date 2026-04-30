#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--source-artifact',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
 src=Path(a.source_artifact); src=src if src.is_file() else src/'per_example_records.jsonl'
 rows=[json.loads(l) for l in src.read_text().splitlines() if l.strip()]
 out=[]
 for r in rows:
  m=str(r.get('method',''))
  if m=='direct_reserve_frontier_gate_v1':
   r=dict(r); r['method']='direct_reserve_semantic_frontier_v2'
  if r.get('method') in {'direct_reserve_semantic_frontier_v2','external_l1_max'}:
   out.append(r)
 od=Path(a.output_dir); od.mkdir(parents=True,exist_ok=True)
 (od/'per_example_records.jsonl').write_text('\n'.join(json.dumps(r) for r in out)+'\n')
 (od/'manifest.json').write_text(json.dumps({'source':str(src),'rows':len(out),'note':'compact export for selector tournament; DR v1 alias remapped to direct_reserve_semantic_frontier_v2'},indent=2)+'\n')
 (od/'README.md').write_text('# Compact selector tournament artifact\n\nGenerated from existing local artifact for offline tournament only.\n')
 print(od)

if __name__=='__main__': main()
