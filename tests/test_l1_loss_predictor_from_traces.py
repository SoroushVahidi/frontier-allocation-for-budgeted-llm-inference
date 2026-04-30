import json, subprocess, sys
from pathlib import Path


def test_predictor_outputs_created(tmp_path):
    out = tmp_path / 'diag'
    subprocess.check_call([sys.executable, 'scripts/analyze_l1_loss_predictors_from_traces.py', '--output-dir', str(out)])
    assert (out / 'l1_loss_predictor_features.csv').is_file()
    assert (out / 'l1_loss_predictor_summary.json').is_file()
    assert (out / 'l1_loss_predictor_report.md').is_file()


def test_missing_artifact_falls_back_to_synth(tmp_path):
    out = tmp_path / 'diag'
    subprocess.check_call([sys.executable, 'scripts/analyze_l1_loss_predictors_from_traces.py', '--artifact', str(tmp_path / 'missing'), '--output-dir', str(out)])
    summary = json.loads((out / 'l1_loss_predictor_summary.json').read_text())
    assert summary['evidence_mode'] == 'synthetic_only'


def test_learned_model_skip_when_low_diversity(tmp_path):
    p = tmp_path / 'per_example_records.jsonl'
    rows = [
        {"example_id": "e1", "dataset": "d", "seed": 1, "budget": 4, "method": "external_l1_max", "gold_answer_canonical": "10", "final_answer_canonical": "10"},
        {"example_id": "e1", "dataset": "d", "seed": 1, "budget": 4, "method": "direct_reserve_semantic_frontier_v2", "gold_answer_canonical": "10", "final_answer_canonical": "10", "result_metadata": {"selector_candidate_pool": [{"predicted_answer": "10", "source": "direct_reserve"}]}}
    ]
    p.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    out = tmp_path / 'diag'
    subprocess.check_call([sys.executable, 'scripts/analyze_l1_loss_predictors_from_traces.py', '--artifact', str(p), '--output-dir', str(out), '--method', 'direct_reserve_semantic_frontier_v2'])
    summary = json.loads((out / 'l1_loss_predictor_summary.json').read_text())
    assert summary['learned_models']['l1_correct_ours_wrong']['status'] == 'skipped'


def test_no_runtime_default_change_guard():
    text = Path('experiments/frontier_matrix_core.py').read_text(encoding='utf-8')
    assert 'direct_reserve_semantic_frontier_v2_l1_direct_injection_v1' in text
