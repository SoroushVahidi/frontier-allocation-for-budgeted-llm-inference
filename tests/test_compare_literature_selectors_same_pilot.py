import json, subprocess, sys
from pathlib import Path


def _wjsonl(p: Path, rows):
    p.write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')


def test_same_pilot_comparison_and_pairwise(tmp_path: Path):
    paired=tmp_path/'paired.jsonl'; scores=tmp_path/'scores.jsonl'; cfg=tmp_path/'cfg.json'; out=tmp_path/'out'
    rows=[
      {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'direct_reserve_semantic_frontier_v2','selected_answer_canonical':'2','gold_answer_canonical':'3','result_metadata':{'selector_candidate_pool':[{'candidate_id':'c1','normalized_answer':'3','trace':'t'},{'candidate_id':'c2','normalized_answer':'2','trace':'t'}]}},
      {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'external_l1_max','selected_answer_canonical':'3','gold_answer_canonical':'3'}
    ]
    _wjsonl(paired,rows)
    _wjsonl(scores,[{'case_id':'openai/gsm8k::e1::1::8','candidate_id':'c1','verifier_score':0.9},{'case_id':'openai/gsm8k::e1::1::8','candidate_id':'c2','verifier_score':0.1}])
    cfg.write_text(json.dumps({'min_verifier_margin':0.0,'require_trace_for_override':True}),encoding='utf-8')
    subprocess.check_call([sys.executable,'scripts/compare_literature_selectors_same_pilot.py','--pilot-cases',str(paired),'--cohere-score-cache',str(scores),'--selected-selector-config',str(cfg),'--output-dir',str(out)])
    s=json.loads((out/'selector_comparison_summary.json').read_text())
    assert s['pilot_case_count']==1 and s['cohere_missing_score_count']==0
    p=json.loads((out/'pairwise_disagreement_breakdown.json').read_text())
    assert p['self_vs_cohere']['both_correct']==1


def test_full_coverage_failure_blocks(tmp_path: Path):
    paired=tmp_path/'paired.jsonl'; scores=tmp_path/'scores.jsonl'; cfg=tmp_path/'cfg.json'; out=tmp_path/'out'
    rows=[
      {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'direct_reserve_semantic_frontier_v2','selected_answer_canonical':'2','gold_answer_canonical':'3','result_metadata':{'selector_candidate_pool':[{'candidate_id':'c1','normalized_answer':'3','trace':'t'}]}},
      {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'external_l1_max','selected_answer_canonical':'3','gold_answer_canonical':'3'}
    ]
    _wjsonl(paired,rows)
    _wjsonl(scores,[])
    cfg.write_text(json.dumps({'min_verifier_margin':0.0,'require_trace_for_override':True}),encoding='utf-8')
    cp=subprocess.run([sys.executable,'scripts/compare_literature_selectors_same_pilot.py','--pilot-cases',str(paired),'--cohere-score-cache',str(scores),'--selected-selector-config',str(cfg),'--output-dir',str(out),'--require-full-cohere-coverage'],capture_output=True,text=True)
    assert cp.returncode!=0
