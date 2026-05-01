import json, subprocess, sys
from pathlib import Path


def test_builder_preserves_validation_role_and_hygiene(tmp_path):
    rec = tmp_path/'rec.jsonl'
    rec.write_text(json.dumps({'case_id':'c1','dataset':'d','example_id':'e','seed':0,'budget':1,'our_method_name':'m','problem_statement':'p','selected_normalized_answer':'a','candidate_nodes':[{'candidate_id':'x','trace_text':'t'}],'verifier_input':{'candidates_for_verifier':[]},'evaluation_only':{'gold_answer':'a'}})+'\n')
    inv = tmp_path/'inv.json'
    inv.write_text('[]')
    out = tmp_path/'out'
    subprocess.check_call([sys.executable,'scripts/build_mixed_selector_validation_set.py','--recovery-input',str(rec),'--risk-inventory',str(inv),'--output-dir',str(out)])
    rows=[json.loads(l) for l in (out/'mixed_candidate_trace_enriched.jsonl').read_text().splitlines() if l.strip()]
    assert rows[0]['validation_role']=='recovery'
    assert 'gold_answer' not in json.dumps(rows[0].get('verifier_input',{})).lower()


def test_margin_sweep_trace_quality_mode_runs(tmp_path):
    inp=tmp_path/'in.jsonl'
    inp.write_text(json.dumps({'case_id':'c1','problem_statement':'2+2','selected_normalized_answer':'4','candidate_nodes':[{'candidate_id':'a','normalized_answer':'4','trace_text':'x'}],'evaluation_only':{'gold_answer':'4'}})+'\n')
    out=tmp_path/'o'
    subprocess.check_call([sys.executable,'scripts/run_outcome_verifier_selector_margin_sweep.py','--input',str(inp),'--output-dir',str(out),'--scorer-mode','trace_quality_heuristic','--margins','0.0','0.1','--require-trace-for-override'])
    assert (out/'margin_sweep_summary.json').exists()
