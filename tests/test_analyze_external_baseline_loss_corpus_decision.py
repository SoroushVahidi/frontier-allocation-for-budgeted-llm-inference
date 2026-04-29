from pathlib import Path
import subprocess


def test_decision_script_runs_on_latest_corpus(tmp_path: Path) -> None:
    roots = sorted(Path('outputs').glob('external_baseline_loss_case_collection_*'))
    assert roots, 'expected at least one corpus output directory'
    out = tmp_path / 'decision'
    subprocess.run([
        'python',
        'scripts/analyze_external_baseline_loss_corpus_decision.py',
        '--input-dir', str(roots[-1]),
        '--output-dir', str(out),
    ], check=True)
    assert (out / 'decision_summary.json').exists()
    assert (out / 'decision_note.md').exists()
    assert (out / 'decision_table.csv').exists()
