"""Tests for the Cohere RelationReady judge adapter."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = 'scripts/run_relation_verifier_cohere_judge_adapter.py'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')


def read_jsonl(path):
    rows = []
    with Path(path).open('r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_script(args, expect_success=True, env=None):
    # When env is provided it is used directly (not merged) so callers can
    # remove specific vars by constructing the env themselves.
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CLEAN_PROMPT = (
    'Please evaluate whether the following candidate trace and answer '
    'correctly represent the semantic relation requested by the question.\n\n'
    'QUESTION:\nHow many apples are left?\n\n'
    'TARGET PHRASE:\napples left\n\n'
    'CANDIDATE ANSWER:\n5\n\n'
    'CANDIDATE TRACE:\n10 - 5 = 5\n\n'
    'TASK:\nRespond with JSON containing relation_ready_label, first_error_axis, '
    'confidence, rationale.'
)

_SCHEMA = {
    'type': 'object',
    'properties': {
        'relation_ready_label': {'type': 'string'},
        'first_error_axis': {'type': 'string'},
        'confidence': {'type': 'string'},
        'rationale': {'type': 'string'},
    },
    'required': ['relation_ready_label', 'first_error_axis', 'confidence', 'rationale'],
}

def _cohere_payload_row(row_id='rrseed_test_001', prompt=None, model='command-r-plus-08-2024'):
    return {
        'row_id': row_id,
        'provider': 'cohere',
        'model': model,
        'temperature': 0.0,
        'dry_run': True,
        'api_call_made': False,
        'prompt_sha256': 'abc123',
        'payload': {
            'model': model,
            'message': prompt or _CLEAN_PROMPT,
            'temperature': 0.0,
            'response_format': {'type': 'json_object'},
        },
        'expected_json_schema': _SCHEMA,
    }


def _mock_response(row_id='rrseed_test_001', label='ready', axis='',
                   confidence='high', rationale='Trace is correct.'):
    text = json.dumps({
        'relation_ready_label': label,
        'first_error_axis': axis,
        'confidence': confidence,
        'rationale': rationale,
    })
    return {'row_id': row_id, 'response_text': text}


# ---------------------------------------------------------------------------
# dry_run — output files
# ---------------------------------------------------------------------------

def test_dry_run_writes_manifest_and_report(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    assert (output_dir / 'cohere_dry_run_manifest.jsonl').exists()
    assert (output_dir / 'cohere_adapter_report.md').exists()


def test_dry_run_manifest_has_correct_row_id(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row('rrseed_abc')])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 1
    assert manifest[0]['row_id'] == 'rrseed_abc'
    assert manifest[0]['has_payload'] is True
    assert manifest[0]['has_schema'] is True


def test_dry_run_filters_non_cohere_rows(tmp_path):
    mistral_row = {**_cohere_payload_row(), 'provider': 'mistral'}
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row(), mistral_row])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 1
    assert manifest[0]['row_id'] == 'rrseed_test_001'


def test_dry_run_max_rows(tmp_path):
    rows = [_cohere_payload_row(f'rrseed_{i:03d}') for i in range(5)]
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, rows)
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run',
                '--max-rows', '2'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 2


def test_dry_run_report_confirms_no_api_calls(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    report = (output_dir / 'cohere_adapter_report.md').read_text()
    assert 'No API calls' in report
    assert 'No provider SDK' in report


# ---------------------------------------------------------------------------
# dry_run — field validation
# ---------------------------------------------------------------------------

def test_dry_run_detects_missing_payload(tmp_path):
    bad_row = {**_cohere_payload_row(), 'payload': None}
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [bad_row])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert any('missing_payload' in str(m['field_issues']) for m in manifest)


def test_dry_run_detects_wrong_provider(tmp_path):
    bad_row = {**_cohere_payload_row(), 'provider': 'openai'}
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [bad_row])
    output_dir = tmp_path / 'output'

    # Wrong-provider rows are filtered out entirely before validation;
    # the manifest should be empty.
    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 0


# ---------------------------------------------------------------------------
# dry_run — leakage detection
# ---------------------------------------------------------------------------

def test_dry_run_detects_leakage_in_prompt(tmp_path):
    bad_prompt = _CLEAN_PROMPT + '\nrelation_ready_label_manual: ready'
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row(prompt=bad_prompt)])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert 'relation_ready_label_manual' in manifest[0]['leakage_terms']

    report = (output_dir / 'cohere_adapter_report.md').read_text()
    assert 'LEAKAGE' in report


def test_dry_run_clean_prompt_has_no_leakage(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert manifest[0]['leakage_terms'] == []


def test_dry_run_leakage_terms_checked(tmp_path):
    leakage_cases = [
        'gold_answer_metadata_only is here',
        'first_error_axis_manual set to something',
        'notes_manual present',
        'likely not_ready outcome',
        'good judge should label this as ready',
    ]
    for leaky in leakage_cases:
        bad_prompt = _CLEAN_PROMPT + f'\n{leaky}'
        payloads_path = tmp_path / 'payloads.jsonl'
        write_jsonl(payloads_path, [_cohere_payload_row(prompt=bad_prompt)])
        output_dir = tmp_path / f'out_{hash(leaky) % 100000}'

        run_script(['--payloads-jsonl', str(payloads_path),
                    '--output-dir', str(output_dir),
                    '--mode', 'dry_run'])

        manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
        assert len(manifest[0]['leakage_terms']) > 0, f'Leakage not detected for: {leaky!r}'


# ---------------------------------------------------------------------------
# api mode — refuses without --allow-api
# ---------------------------------------------------------------------------

def test_api_mode_refuses_without_allow_api(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    output_dir = tmp_path / 'output'

    result = run_script(['--payloads-jsonl', str(payloads_path),
                         '--output-dir', str(output_dir),
                         '--mode', 'api'],
                        expect_success=False)

    assert result.returncode != 0
    assert '--allow-api' in result.stderr


def test_api_mode_fails_with_missing_api_key(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    output_dir = tmp_path / 'output'

    # Use a guaranteed-absent env var name so the key check always fires,
    # regardless of whether COHERE_API_KEY happens to be set in CI.
    result = run_script(['--payloads-jsonl', str(payloads_path),
                         '--output-dir', str(output_dir),
                         '--mode', 'api',
                         '--allow-api',
                         '--api-key-env', 'COHERE_API_KEY_DEFINITELY_NOT_SET_XYZ'],
                        expect_success=False)

    # Either a missing-key error or a missing-SDK error is acceptable here.
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# mock_api mode — normalization
# ---------------------------------------------------------------------------

def test_mock_api_normalizes_valid_response(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    write_jsonl(mock_path, [_mock_response(label='ready')])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 1
    row = normalized[0]
    assert row['row_id'] == 'rrseed_test_001'
    assert row['relation_ready_label'] == 'ready'
    assert row['first_error_axis'] == ''
    assert row['confidence'] == 'high'
    assert row['judge_name'] == 'cohere:command-r-plus-08-2024'


def test_mock_api_judge_name_includes_model(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row(model='command-r-08-2024')])
    write_jsonl(mock_path, [_mock_response()])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert normalized[0]['judge_name'] == 'cohere:command-r-08-2024'


def test_mock_api_normalized_row_has_all_fields(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    write_jsonl(mock_path, [_mock_response(label='not_ready', axis='arithmetic_only_error',
                                           confidence='medium', rationale='Wrong sum.')])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 1
    row = normalized[0]
    for field in ('row_id', 'judge_name', 'relation_ready_label',
                  'first_error_axis', 'confidence', 'rationale'):
        assert field in row, f'Missing field: {field}'


def test_mock_api_invalid_label_excluded_from_normalized(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    bad_resp = _mock_response()
    bad_resp['response_text'] = json.dumps({
        'relation_ready_label': 'TOTALLY_WRONG',
        'first_error_axis': '',
        'confidence': 'high',
        'rationale': 'test',
    })
    write_jsonl(mock_path, [bad_resp])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 0


def test_mock_api_invalid_axis_excluded(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    bad_resp = _mock_response()
    bad_resp['response_text'] = json.dumps({
        'relation_ready_label': 'not_ready',
        'first_error_axis': 'FAKE_AXIS',
        'confidence': 'high',
        'rationale': 'test',
    })
    write_jsonl(mock_path, [bad_resp])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 0


def test_mock_api_invalid_json_response_text_excluded(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    write_jsonl(mock_path, [{'row_id': 'rrseed_test_001', 'response_text': 'not json {{{{'}])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 0


def test_mock_api_unknown_row_id_excluded(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row('rrseed_real')])
    write_jsonl(mock_path, [_mock_response('rrseed_ghost')])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 0


def test_mock_api_multiple_valid_responses(tmp_path):
    rows = [_cohere_payload_row(f'rrseed_{i:03d}') for i in range(3)]
    mocks = [_mock_response(f'rrseed_{i:03d}', label='ready') for i in range(3)]
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, rows)
    write_jsonl(mock_path, mocks)
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    normalized = read_jsonl(output_dir / 'normalized_judge_responses.jsonl')
    assert len(normalized) == 3


def test_mock_api_report_confirms_no_api_calls(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    mock_path = tmp_path / 'mock.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    write_jsonl(mock_path, [_mock_response()])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'mock_api',
                '--mock-response-jsonl', str(mock_path)])

    report = (output_dir / 'cohere_adapter_report.md').read_text()
    assert 'No API calls' in report
    assert 'No provider SDK' in report


# ---------------------------------------------------------------------------
# mock_api — requires --mock-response-jsonl
# ---------------------------------------------------------------------------

def test_mock_api_requires_mock_response_jsonl_arg(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    output_dir = tmp_path / 'output'

    result = run_script(['--payloads-jsonl', str(payloads_path),
                         '--output-dir', str(output_dir),
                         '--mode', 'mock_api'],
                        expect_success=False)
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_missing_payloads_file_exits_nonzero(tmp_path):
    result = run_script(['--payloads-jsonl', str(tmp_path / 'nonexistent.jsonl'),
                         '--output-dir', str(tmp_path / 'output'),
                         '--mode', 'dry_run'],
                        expect_success=False)
    assert result.returncode != 0


def test_output_dir_created_automatically(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row()])
    output_dir = tmp_path / 'nested' / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run'])

    assert output_dir.exists()


# ---------------------------------------------------------------------------
# SDK / network import safety
# ---------------------------------------------------------------------------

def test_no_sdk_or_network_imports_at_module_level():
    script_text = Path(SCRIPT).read_text()
    # Module-level forbidden imports
    forbidden_module_level = [
        'import cohere\n',
        'from cohere import',
        'import openai',
        'import boto3',
        'import httpx\n',
        'urllib.request.urlopen',
    ]
    for term in forbidden_module_level:
        assert term not in script_text, f'Forbidden module-level import: {term!r}'


def test_requests_post_not_used():
    script_text = Path(SCRIPT).read_text()
    assert 'requests.post' not in script_text
    assert 'httpx.post' not in script_text


# ---------------------------------------------------------------------------
# Row slicing — --start-index and --row-ids
# ---------------------------------------------------------------------------

def test_dry_run_start_index_slices_rows(tmp_path):
    rows = [_cohere_payload_row(f'rrseed_{i:03d}') for i in range(10)]
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, rows)
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run',
                '--start-index', '5',
                '--max-rows', '5'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 5
    assert manifest[0]['row_id'] == 'rrseed_005'
    assert manifest[-1]['row_id'] == 'rrseed_009'


def test_dry_run_start_index_zero_is_default_behaviour(tmp_path):
    rows = [_cohere_payload_row(f'rrseed_{i:03d}') for i in range(5)]
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, rows)
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run',
                '--start-index', '0',
                '--max-rows', '3'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 3
    assert manifest[0]['row_id'] == 'rrseed_000'


def test_dry_run_row_ids_selects_specific_rows(tmp_path):
    rows = [_cohere_payload_row(f'rrseed_{i:03d}') for i in range(10)]
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, rows)
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run',
                '--row-ids', 'rrseed_002,rrseed_007'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 2
    selected_ids = {m['row_id'] for m in manifest}
    assert selected_ids == {'rrseed_002', 'rrseed_007'}


def test_dry_run_row_ids_takes_precedence_over_start_index(tmp_path):
    rows = [_cohere_payload_row(f'rrseed_{i:03d}') for i in range(10)]
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, rows)
    output_dir = tmp_path / 'output'

    # --start-index 8 would select rows 8-9, but --row-ids should win
    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run',
                '--start-index', '8',
                '--row-ids', 'rrseed_001,rrseed_003'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 2
    selected_ids = {m['row_id'] for m in manifest}
    assert selected_ids == {'rrseed_001', 'rrseed_003'}


def test_dry_run_report_includes_start_index(tmp_path):
    rows = [_cohere_payload_row(f'rrseed_{i:03d}') for i in range(10)]
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, rows)
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run',
                '--start-index', '5',
                '--max-rows', '5'])

    report = (output_dir / 'cohere_adapter_report.md').read_text()
    assert 'Start index' in report
    assert '5' in report


def test_dry_run_row_ids_unknown_id_yields_empty_manifest(tmp_path):
    payloads_path = tmp_path / 'payloads.jsonl'
    write_jsonl(payloads_path, [_cohere_payload_row('rrseed_real')])
    output_dir = tmp_path / 'output'

    run_script(['--payloads-jsonl', str(payloads_path),
                '--output-dir', str(output_dir),
                '--mode', 'dry_run',
                '--row-ids', 'rrseed_ghost'])

    manifest = read_jsonl(output_dir / 'cohere_dry_run_manifest.jsonl')
    assert len(manifest) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
