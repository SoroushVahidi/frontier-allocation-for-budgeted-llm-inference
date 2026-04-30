import subprocess, sys
from pathlib import Path

def test_threshold_script_runs():
    art=Path('outputs/cohere_real_model_cost_normalized_validation_20260429T_SELECTOR_COMPARISON_30CASE_COHERE')
    if not (art/'per_example_records.jsonl').exists():
        return
    subprocess.check_call([sys.executable,'scripts/analyze_selector_override_thresholds.py','--artifact-dir',str(art),'--timestamp','20260429T_SELECTOR_COMPARISON_30CASE_COHERE'])
    assert (art/'selector_override_threshold_sweep.csv').exists()
