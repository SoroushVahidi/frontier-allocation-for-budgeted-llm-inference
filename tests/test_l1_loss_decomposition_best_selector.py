import json, subprocess, sys
from pathlib import Path

from scripts.run_l1_loss_decomposition_for_best_selector import choose_selected_method


def test_selected_method_decision_excludes_mock_backed_artifacts():
    d=choose_selected_method()
    assert d['selected_method_id'] is None
    assert d['is_real_cohere'] is False


def test_no_fake_accuracy_written_when_blocked(tmp_path: Path):
    out=tmp_path/'out'
    p=subprocess.run([sys.executable,'scripts/run_l1_loss_decomposition_for_best_selector.py','--timestamp','T','--output-dir',str(out)], capture_output=True, text=True)
    assert p.returncode!=0
    assert (out/'cohere_readiness_failure_report.json').is_file()
    assert not (out/'l1_loss_decomposition_summary.json').exists()


def test_readiness_failure_report_contains_no_secret_values(tmp_path: Path):
    out=tmp_path/'out2'
    subprocess.run([sys.executable,'scripts/run_l1_loss_decomposition_for_best_selector.py','--timestamp','T2','--output-dir',str(out)], check=False)
    r=json.loads((out/'cohere_readiness_failure_report.json').read_text())
    blob=json.dumps(r).lower()
    assert 'cohere_api_key' in blob
    assert 'sk-' not in blob
    assert 'api_key=' not in blob
