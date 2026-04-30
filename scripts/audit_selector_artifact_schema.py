#!/usr/bin/env python3
from __future__ import annotations
import csv,json,argparse
from pathlib import Path
from datetime import datetime,timezone

def has_any(row, keys): return any(k in row and row.get(k) not in (None,'',[]) for k in keys)

def audit_file(path:Path):
    lines=path.read_text().splitlines()
    rows=[json.loads(l) for l in lines if l.strip()]
    methods=sorted({r.get('method','') for r in rows})
    datasets=sorted({r.get('dataset','') for r in rows})
    sample=rows[:20]
    h={
      'artifact_path':str(path),'row_count':len(rows),'method_names':'|'.join(methods),'dataset_names':'|'.join(datasets),
      'has_example_id':any(has_any(r,['example_id']) for r in sample),
      'has_question':any(has_any(r,['question','question_raw']) for r in sample),
      'has_gold_answer':any(has_any(r,['gold_answer','gold_answer_canonical']) for r in sample),
      'has_selected_answer':any(has_any(r,['selected_answer_raw','selected_answer_canonical','final_answer_raw','final_answer_canonical']) for r in sample),
      'has_exact_match_or_correct':any(('exact_match' in r) or ('is_correct' in r) for r in sample),
      'has_candidate_groups':any(has_any((r.get('result_metadata') or {}),['answer_groups','prm_group_scores','ov_rerank_group_scores']) for r in sample),
      'has_candidate_answers':any(has_any(r,['final_nodes']) or has_any((r.get('result_metadata') or {}),['selector_candidate_pool','final_branch_states']) for r in sample),
      'has_normalized_candidate_answers':any(has_any((r.get('result_metadata') or {}),['selected_answer_canonical','selected_normalized_answer']) for r in sample),
      'has_candidate_source_family':any('source' in x for r in sample for x in (r.get('final_nodes') or []) if isinstance(x,dict)),
      'has_direct_reserve_vs_frontier_source':any(str(x.get('source','')).lower() in {'direct_reserve','frontier'} for r in sample for x in (r.get('final_nodes') or []) if isinstance(x,dict)),
      'has_support_counts':any(has_any((r.get('result_metadata') or {}),['answer_support_counts']) for r in sample),
      'has_ov_scores':any(has_any((r.get('result_metadata') or {}),['ov_rerank_group_scores','ov_rerank_candidate_scores']) for r in sample),
      'has_prm_scores':any(has_any((r.get('result_metadata') or {}),['prm_group_scores','prm_trace_scores']) for r in sample),
      'has_selector_metadata':any(bool(r.get('result_metadata')) for r in sample),
    }
    usable = h['has_gold_answer'] and h['has_selected_answer'] and h['has_exact_match_or_correct'] and (h['has_candidate_groups'] or h['has_candidate_answers'])
    if usable: cls='usable_now'; reason=''
    elif h['has_gold_answer'] and h['has_selected_answer'] and (h['has_candidate_answers'] or h['has_support_counts']): cls='schema_adaptable'; reason='candidate pool present but expected selector fields missing/renamed'
    elif h['has_gold_answer'] and h['has_selected_answer']: cls='final_rows_only'; reason='selected answers present but no candidate pool/groups'
    elif len(rows)==0: cls='not_scored_or_empty'; reason='no rows'
    else: cls='unknown_needs_manual_inspection'; reason='insufficient selector fields'
    h['usable_for_selector_oracle']=usable
    h['artifact_class']=cls
    h['reason_if_not_usable']=reason
    return h

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-root',default='outputs');a=ap.parse_args()
    files=sorted(Path('outputs').rglob('per_example_records.jsonl'))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    outd=Path(a.output_root)/f'selector_artifact_schema_audit_{stamp}'; outd.mkdir(parents=True,exist_ok=True)
    recs=[audit_file(p) for p in files]
    cols=list(recs[0].keys()) if recs else ['artifact_path']
    with (outd/'selector_artifact_schema_audit.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(recs)
    (outd/'selector_artifact_schema_audit.json').write_text(json.dumps(recs,indent=2)+'\n',encoding='utf-8')
    md=Path('docs')/f'SELECTOR_ARTIFACT_SCHEMA_AUDIT_{stamp}.md'
    lines=['# Selector Artifact Schema Audit','','Artifacts found: '+str(len(files)),'',f'CSV: {outd/"selector_artifact_schema_audit.csv"}',f'JSON: {outd/"selector_artifact_schema_audit.json"}','']
    for r in recs: lines.append(f"- {r['artifact_path']} => {r['artifact_class']} ({r['reason_if_not_usable'] or 'usable'})")
    md.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(outd)
    print(md)

if __name__=='__main__': main()
