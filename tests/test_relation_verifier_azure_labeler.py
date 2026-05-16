"""Tests for the Azure OpenAI RelationReady assisted labeler."""

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = 'scripts/run_relation_verifier_azure_labeler.py'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_csv(path, rows, fieldnames=None):
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with Path(path).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    with p.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_script(args, expect_success=True, env=None):
    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
        env=env,
    )
    if expect_success:
        assert result.returncode == 0, (
            f'Script failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}'
        )
    return result


_FIELDNAMES = [
    'row_id', 'problem_id', 'case_id', 'candidate_source',
    'question', 'target_phrase', 'candidate_answer', 'candidate_trace_short',
    'source_artifact', 'trace_quality_flags',
    'is_correct_offline_metadata',
    'relation_ready_label_manual', 'first_error_axis_manual', 'notes_manual',
]


def _make_row(row_id, labeled=False, label='ready', gold='yes'):
    return {
        'row_id': row_id,
        'problem_id': f'prob_{row_id}',
        'case_id': f'case_{row_id}',
        'candidate_source': 'pal_seed_0',
        'question': 'How many apples are left after eating 3 of 10?',
        'target_phrase': 'apples left',
        'candidate_answer': '7',
        'candidate_trace_short': 'apples_left = 10 - 3',
        'source_artifact': 'some/artifact',
        'trace_quality_flags': 'has_code|has_arithmetic|answer_present',
        'is_correct_offline_metadata': gold,
        'relation_ready_label_manual': label if labeled else '',
        'first_error_axis_manual': '' if labeled else '',
        'notes_manual': '',
    }


def _make_csv(tmp_path, rows):
    p = tmp_path / 'input.csv'
    write_csv(p, rows, fieldnames=_FIELDNAMES)
    return p


# ---------------------------------------------------------------------------
# dry_run — basic output files
# ---------------------------------------------------------------------------

def test_dry_run_creates_output_dir(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'nested' / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    assert out.exists()


def test_dry_run_writes_requests_jsonl(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    assert (out / 'azure_label_requests.jsonl').exists()


def test_dry_run_writes_manifest(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    assert (out / 'run_manifest.json').exists()


def test_dry_run_writes_label_summary(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    assert (out / 'label_summary.md').exists()


def test_dry_run_manifest_records_correct_row_count(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(5)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    manifest = json.loads((out / 'run_manifest.json').read_text())
    assert manifest['rows_selected'] == 5
    assert manifest['total_rows_in_csv'] == 5


def test_dry_run_confirms_no_api_calls(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    manifest = json.loads((out / 'run_manifest.json').read_text())
    assert manifest['api_calls_made'] == 0


# ---------------------------------------------------------------------------
# dry_run — only unlabeled rows selected by default
# ---------------------------------------------------------------------------

def test_dry_run_skips_labeled_rows_by_default(tmp_path):
    rows = [_make_row('rrpool_001', labeled=True),
            _make_row('rrpool_002', labeled=False)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    assert reqs[0]['row_id'] == 'rrpool_002'


def test_dry_run_include_labeled_flag_selects_all(tmp_path):
    rows = [_make_row('rrpool_001', labeled=True),
            _make_row('rrpool_002', labeled=False)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--include-labeled'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 2


# ---------------------------------------------------------------------------
# dry_run — start-index and max-rows
# ---------------------------------------------------------------------------

def test_dry_run_start_index_slices_rows(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '5', '--max-rows', '3'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 3
    assert reqs[0]['row_id'] == 'rrpool_005'
    assert reqs[-1]['row_id'] == 'rrpool_007'


def test_dry_run_max_rows_limits_selection(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--max-rows', '2'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 2


def test_dry_run_start_index_stored_in_manifest(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '7'])
    manifest = json.loads((out / 'run_manifest.json').read_text())
    assert manifest['start_index'] == 7


# ---------------------------------------------------------------------------
# dry_run — row-ids selection
# ---------------------------------------------------------------------------

def test_dry_run_row_ids_selects_specific_rows(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--row-ids', 'rrpool_002,rrpool_007'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 2
    ids = {r['row_id'] for r in reqs}
    assert ids == {'rrpool_002', 'rrpool_007'}


def test_dry_run_row_ids_takes_precedence_over_start_index(tmp_path):
    rows = [_make_row(f'rrpool_{i:03d}') for i in range(10)]
    csv_path = _make_csv(tmp_path, rows)
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '8', '--row-ids', 'rrpool_001,rrpool_003'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 2
    ids = {r['row_id'] for r in reqs}
    assert ids == {'rrpool_001', 'rrpool_003'}


def test_dry_run_unknown_row_id_yields_empty_requests(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_real')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--row-ids', 'rrpool_ghost'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 0


# ---------------------------------------------------------------------------
# dry_run — gold metadata excluded from prompts
# ---------------------------------------------------------------------------

def test_dry_run_gold_metadata_excluded_from_prompt(tmp_path):
    row = _make_row('rrpool_001', gold='yes')
    csv_path = _make_csv(tmp_path, [row])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    prompt = reqs[0]['prompt']
    assert 'is_correct_offline_metadata' not in prompt
    assert 'gold_answer_metadata_only' not in prompt


def test_dry_run_manual_labels_excluded_from_prompt(tmp_path):
    row = _make_row('rrpool_001', labeled=True, label='ready')
    csv_path = _make_csv(tmp_path, [row])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                '--mode', 'dry_run', '--include-labeled'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    prompt = reqs[0]['prompt']
    assert 'relation_ready_label_manual' not in prompt
    assert 'first_error_axis_manual' not in prompt
    assert 'notes_manual' not in prompt


def test_dry_run_no_leakage_in_clean_row(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    summary = (out / 'label_summary.md').read_text()
    assert 'LEAKAGE' not in summary
    assert 'CLEAN' in summary


# ---------------------------------------------------------------------------
# api mode — refuses without --allow-api
# ---------------------------------------------------------------------------

def test_api_mode_refuses_without_allow_api(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    result = run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'api'],
                        expect_success=False)
    assert result.returncode != 0
    assert '--allow-api' in result.stderr


def test_api_mode_fails_with_missing_api_key(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    # Strip all Azure env vars so the key check fires
    env = {k: v for k, v in os.environ.items()
           if k not in ('AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT',
                        'AZURE_OPENAI_DEPLOYMENT', 'AZURE_OPENAI_API_VERSION')}
    result = run_script(['--input-csv', str(csv_path), '--output-dir', str(out),
                         '--mode', 'api', '--allow-api'],
                        expect_success=False, env=env)
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# JSON normalization (via script's normalize_response function directly)
# ---------------------------------------------------------------------------

def _import_normalize():
    """Import normalize_response from the script."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'azure_labeler', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.normalize_response


def test_normalize_valid_response():
    normalize = _import_normalize()
    text = json.dumps({
        'row_id': 'rrpool_001',
        'relation_ready_label': 'ready',
        'first_error_axis': '',
        'confidence': 'high',
        'is_hesitant': False,
        'hesitation_reason': '',
        'rationale': 'Trace is correct.',
    })
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', text, 'stop')
    assert err is None
    assert norm['relation_ready_label'] == 'ready'
    assert norm['first_error_axis'] == ''
    assert norm['confidence'] == 'high'
    assert norm['judge_name'] == 'azure:gpt-4.1-mini'
    assert norm['is_hesitant'] is False


def test_normalize_invalid_label_returns_error():
    normalize = _import_normalize()
    text = json.dumps({
        'relation_ready_label': 'WRONG',
        'first_error_axis': '',
        'confidence': 'high',
        'is_hesitant': False,
        'hesitation_reason': '',
        'rationale': 'test',
    })
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', text, 'stop')
    assert norm is None
    assert 'invalid_label' in err


def test_normalize_invalid_axis_returns_error():
    normalize = _import_normalize()
    text = json.dumps({
        'relation_ready_label': 'not_ready',
        'first_error_axis': 'FAKE_AXIS',
        'confidence': 'high',
        'is_hesitant': False,
        'hesitation_reason': '',
        'rationale': 'test',
    })
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', text, 'stop')
    assert norm is None
    assert 'invalid_axis' in err


def test_normalize_invalid_json_returns_error():
    normalize = _import_normalize()
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', 'not json {{{{', 'stop')
    assert norm is None
    assert 'json_parse_error' in err


def test_normalize_hesitant_flag_propagated():
    normalize = _import_normalize()
    text = json.dumps({
        'relation_ready_label': 'uncertain',
        'first_error_axis': '',
        'confidence': 'low',
        'is_hesitant': True,
        'hesitation_reason': 'Could be ready or not_ready',
        'rationale': 'Ambiguous trace.',
    })
    norm, err = normalize('rrpool_001', 'gpt-4.1-mini', text, 'stop')
    assert err is None
    assert norm['is_hesitant'] is True
    assert 'Could be ready' in norm['hesitation_reason']


def test_normalize_all_valid_labels():
    normalize = _import_normalize()
    for label in ('ready', 'not_ready', 'uncertain', 'gold_inconsistent'):
        text = json.dumps({
            'relation_ready_label': label,
            'first_error_axis': '',
            'confidence': 'high',
            'is_hesitant': False,
            'hesitation_reason': '',
            'rationale': 'test',
        })
        norm, err = normalize('rrpool_x', 'dep', text, 'stop')
        assert err is None, f'Label {label!r} should be valid but got error: {err}'


def test_normalize_all_valid_axes():
    normalize = _import_normalize()
    valid_axes = ['source_fact_missing', 'unit_scale_error', 'process_state_error',
                  'relation_type_error', 'arithmetic_error', 'other', '']
    for axis in valid_axes:
        text = json.dumps({
            'relation_ready_label': 'not_ready',
            'first_error_axis': axis,
            'confidence': 'medium',
            'is_hesitant': False,
            'hesitation_reason': '',
            'rationale': 'test',
        })
        norm, err = normalize('rrpool_x', 'dep', text, 'stop')
        assert err is None, f'Axis {axis!r} should be valid but got error: {err}'


# ---------------------------------------------------------------------------
# resume — skips already-normalized rows
# ---------------------------------------------------------------------------

def test_api_dry_run_requests_contain_expected_fields(tmp_path):
    csv_path = _make_csv(tmp_path, [_make_row('rrpool_001')])
    out = tmp_path / 'output'
    run_script(['--input-csv', str(csv_path), '--output-dir', str(out), '--mode', 'dry_run'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 1
    req = reqs[0]
    assert 'row_id' in req
    assert 'prompt' in req
    assert 'deployment' in req
    assert 'temperature' in req
    assert req['temperature'] == 0.0


# ---------------------------------------------------------------------------
# Missing input CSV
# ---------------------------------------------------------------------------

def test_missing_input_csv_exits_nonzero(tmp_path):
    result = run_script(['--input-csv', str(tmp_path / 'nonexistent.csv'),
                         '--output-dir', str(tmp_path / 'output'),
                         '--mode', 'dry_run'],
                        expect_success=False)
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# SDK / network import safety
# ---------------------------------------------------------------------------

def test_no_openai_import_at_module_level():
    """openai must only be imported inside the api-mode branch, not at module level."""
    script_text = Path(SCRIPT).read_text()
    lines = script_text.splitlines()
    # Collect top-level import lines (before any function/class def)
    top_level_imports = []
    for line in lines:
        stripped = line.strip()
        # Stop once we hit a function or class definition
        if stripped.startswith('def ') or stripped.startswith('class '):
            break
        if stripped.startswith('import openai') or stripped.startswith('from openai'):
            top_level_imports.append(stripped)
    assert top_level_imports == [], (
        f'openai must not be imported at module level: {top_level_imports}')


def test_no_azure_openai_client_used():
    """Script must use openai.OpenAI (not AzureOpenAI) per the confirmed endpoint style."""
    script_text = Path(SCRIPT).read_text()
    assert 'AzureOpenAI' not in script_text, (
        'Script must use openai.OpenAI with base_url, not AzureOpenAI')


def test_openai_client_uses_base_url():
    """Script must pass base_url= when constructing the OpenAI client."""
    script_text = Path(SCRIPT).read_text()
    assert 'base_url=' in script_text, (
        'OpenAI client must use base_url= to target the Azure /openai/v1 endpoint')


def test_no_requests_post_used():
    script_text = Path(SCRIPT).read_text()
    assert 'requests.post' not in script_text
    assert 'httpx.post' not in script_text


# ---------------------------------------------------------------------------
# 50/100 row boundary — real CSV
# ---------------------------------------------------------------------------

_REAL_CSV = Path(
    'outputs/relation_verifier_positive_candidate_batch_20260516T002059Z/'
    'positive_candidate_batch.csv'
)


@pytest.mark.skipif(not _REAL_CSV.exists(), reason='Real CSV not available')
def test_real_csv_rows_50_99_selects_50_unlabeled(tmp_path):
    out = tmp_path / 'output'
    run_script(['--input-csv', str(_REAL_CSV), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '50', '--max-rows', '50'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    assert len(reqs) == 50


@pytest.mark.skipif(not _REAL_CSV.exists(), reason='Real CSV not available')
def test_real_csv_no_gold_leakage_in_requests(tmp_path):
    out = tmp_path / 'output'
    run_script(['--input-csv', str(_REAL_CSV), '--output-dir', str(out),
                '--mode', 'dry_run', '--start-index', '50', '--max-rows', '50'])
    reqs = read_jsonl(out / 'azure_label_requests.jsonl')
    for req in reqs:
        prompt = req.get('prompt', '')
        assert 'is_correct_offline_metadata' not in prompt, (
            f'Gold leakage in row {req["row_id"]}')
        assert 'relation_ready_label_manual' not in prompt, (
            f'Label leakage in row {req["row_id"]}')
        assert 'notes_manual' not in prompt, (
            f'Notes leakage in row {req["row_id"]}')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
