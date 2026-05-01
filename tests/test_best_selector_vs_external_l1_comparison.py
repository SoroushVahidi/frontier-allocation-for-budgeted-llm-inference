import json, tempfile, subprocess, sys
from pathlib import Path

def test_comparison_outputs_and_no_gold_leakage():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        paired=d/'per.jsonl'; cfg=d/'cfg.json'; scores=d/'scores.jsonl'; out=d/'out'
        rows=[
          {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'direct_reserve_semantic_frontier_v2','exact_match':0,'selected_answer_canonical':'2','gold_answer_canonical':'3','question':'q','result_metadata':{'selector_candidate_pool':[{'candidate_id':'c1','normalized_answer':'3','trace':'t'},{'candidate_id':'c2','normalized_answer':'2','trace':'t'}]}},
          {'dataset':'openai/gsm8k','example_id':'e1','seed':1,'budget':8,'method':'external_l1_max','exact_match':1,'selected_answer_canonical':'3','gold_answer_canonical':'3'},
        ]
        paired.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        cfg.write_text(json.dumps({'require_trace_for_override':True}))
        scores.write_text(json.dumps({'case_id':'openai/gsm8k::e1::1::8','candidate_id':'c1','verifier_score':1.0})+'\n')
        subprocess.check_call([sys.executable,'scripts/apply_selected_selector_to_paired_validation.py','--paired-records',str(paired),'--selected-config',str(cfg),'--score-cache',str(scores),'--output-dir',str(out)])
        s=json.loads((out/'comparison_summary.json').read_text())
        assert s['selected_selector_accuracy']==1.0
        per=[json.loads(x) for x in (out/'per_case_comparison.jsonl').read_text().splitlines() if x.strip()]
        assert per[0]['selected_selector_fixed']==1
        assert 'gold' not in (out/'manifest.json').read_text().lower()
