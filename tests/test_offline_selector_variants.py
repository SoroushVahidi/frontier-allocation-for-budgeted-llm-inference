import json, subprocess, sys
from pathlib import Path


def _write(path, rows):
    path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n', encoding='utf-8')


def test_selector_gap_uses_actual_dr(tmp_path):
    p=tmp_path/'per_example_records.jsonl'
    rows=[
      {'example_id':'e1','dataset':'d','seed':1,'budget':4,'method':'external_l1_max','gold_answer_canonical':'10','final_answer_canonical':'10'},
      {'example_id':'e1','dataset':'d','seed':1,'budget':4,'method':'direct_reserve_semantic_frontier_v2','gold_answer_canonical':'10','final_answer_canonical':'9','result_metadata':{'selector_candidate_pool':[{'predicted_answer':'9'},{'predicted_answer':'10'}]}},
      {'example_id':'e2','dataset':'d','seed':1,'budget':4,'method':'external_l1_max','gold_answer_canonical':'5','final_answer_canonical':'5'},
      {'example_id':'e2','dataset':'d','seed':1,'budget':4,'method':'direct_reserve_semantic_frontier_v2','gold_answer_canonical':'5','final_answer_canonical':'5','result_metadata':{'selector_candidate_pool':[{'predicted_answer':'5'}]}},
    ]
    _write(p,rows)
    out=tmp_path/'diag'; out.mkdir()
    subprocess.check_call([sys.executable,'scripts/analyze_selector_oracle_ceiling.py','--artifact-dir',str(p),'--output-dir',str(out)])
    s=json.loads((out/'selector_oracle_ceiling_summary.json').read_text())
    assert abs(s['selector_gap']-(s['oracle_selector_accuracy']-s['dr_v2_accuracy']))<1e-9


def test_offline_selector_variants_outputs_and_skip(tmp_path):
    p=tmp_path/'per_example_records.jsonl'
    rows=[
      {'example_id':'e1','dataset':'d','seed':1,'budget':4,'method':'external_l1_max','gold_answer_canonical':'10','final_answer_canonical':'10'},
      {'example_id':'e1','dataset':'d','seed':1,'budget':4,'method':'direct_reserve_semantic_frontier_v2','gold_answer_canonical':'10','final_answer_canonical':'9','question_raw':'q1','result_metadata':{'selector_candidate_pool':[{'predicted_answer':'9','source':'direct_reserve'},{'predicted_answer':'10','source':'frontier'}]}},
      {'example_id':'e2','dataset':'d','seed':1,'budget':4,'method':'external_l1_max','gold_answer_canonical':'8','final_answer_canonical':'8'},
      {'example_id':'e2','dataset':'d','seed':1,'budget':4,'method':'direct_reserve_semantic_frontier_v2','gold_answer_canonical':'8','final_answer_canonical':'8','question_raw':'day of week?','result_metadata':{'selector_candidate_pool':[{'predicted_answer':'8','source':'direct_reserve'},{'predicted_answer':'monday','source':'frontier'}]}},
    ]
    _write(p,rows)
    out=tmp_path/'diag'
    subprocess.check_call([sys.executable,'scripts/analyze_offline_selector_variants.py','--artifact-dir',str(p),'--output-dir',str(out)])
    assert (out/'offline_selector_variant_results.csv').is_file()
    assert (out/'offline_selector_variant_summary.json').is_file()
    assert (out/'offline_selector_variant_casebook.csv').is_file()
    assert (out/'offline_selector_variant_report.md').is_file()
    s=json.loads((out/'offline_selector_variant_summary.json').read_text())
    assert any('ov_score_selector' in x for x in s['skipped_selectors'])


def test_support_break_but_consistency_avoids_break(tmp_path):
    p=tmp_path/'per_example_records.jsonl'
    rows=[
      {'example_id':'e1','dataset':'d','seed':1,'budget':4,'method':'external_l1_max','gold_answer_canonical':'8','final_answer_canonical':'8'},
      {'example_id':'e1','dataset':'d','seed':1,'budget':4,'method':'direct_reserve_semantic_frontier_v2','gold_answer_canonical':'8','final_answer_canonical':'8','question_raw':'day of week','result_metadata':{'selector_candidate_pool':[{'predicted_answer':'8','source':'direct_reserve'},{'predicted_answer':'monday','source':'frontier'},{'predicted_answer':'monday','source':'frontier'}]}},
    ]
    _write(p,rows)
    out=tmp_path/'diag'
    subprocess.check_call([sys.executable,'scripts/analyze_offline_selector_variants.py','--artifact-dir',str(p),'--output-dir',str(out)])
    res=(out/'offline_selector_variant_results.csv').read_text()
    assert 'support_only' in res and 'consistency_penalized' in res


def test_runtime_defaults_unchanged():
    text=Path('experiments/frontier_matrix_core.py').read_text(encoding='utf-8')
    assert 'direct_reserve_semantic_frontier_v2_l1_direct_injection_v1' in text
