"""Tests for the dry-run provider payload builder."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = 'scripts/build_relation_verifier_provider_payloads.py'

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


def run_script(args, expect_success=True):
    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
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

_BASE_REQUEST = {
    'row_id': 'rrseed_test_001',
    'problem_id': 'test/problem/1',
    'question': 'How many apples are left?',
    'target_phrase': 'apples left',
    'target_semantic_type': 'number',
    'candidate_source': 'direct_formula_family',
    'candidate_answer': '5',
    'candidate_trace_short': '10 - 5 = 5',
    'prompt': _CLEAN_PROMPT,
    'expected_json_schema': _SCHEMA,
}

_BASE_REQUEST_2 = {**_BASE_REQUEST, 'row_id': 'rrseed_test_002'}

ALL_PROVIDERS = ['cohere', 'mistral', 'fireworks', 'cerebras', 'azure_openai']


# ---------------------------------------------------------------------------
# Output files
# ---------------------------------------------------------------------------

def test_writes_provider_payloads_and_report(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    assert (output_dir / 'provider_payloads.jsonl').exists()
    assert (output_dir / 'build_report.md').exists()


def test_output_dir_created_automatically(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'nonexistent' / 'nested'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    assert output_dir.exists()
    assert (output_dir / 'provider_payloads.jsonl').exists()


# ---------------------------------------------------------------------------
# Payload count and envelope fields
# ---------------------------------------------------------------------------

def test_payload_count_equals_requests_times_providers(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST, _BASE_REQUEST_2])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere,mistral',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert len(payloads) == 4  # 2 requests × 2 providers


def test_all_five_providers_produce_correct_count(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', ','.join(ALL_PROVIDERS),
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert len(payloads) == 5


def test_envelope_has_required_fields(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert len(payloads) == 1
    p = payloads[0]
    for field in ('row_id', 'provider', 'model', 'temperature', 'dry_run',
                  'api_call_made', 'prompt_sha256', 'payload', 'expected_json_schema'):
        assert field in p, f'Missing field: {field}'


def test_envelope_dry_run_and_api_call_made(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'mistral',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert payloads[0]['dry_run'] is True
    assert payloads[0]['api_call_made'] is False


def test_row_id_preserved_in_envelope(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST, _BASE_REQUEST_2])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    row_ids = {p['row_id'] for p in payloads}
    assert row_ids == {'rrseed_test_001', 'rrseed_test_002'}


def test_schema_preserved_in_envelope(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cerebras',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert payloads[0]['expected_json_schema'] == _SCHEMA


# ---------------------------------------------------------------------------
# Provider-specific payload shapes
# ---------------------------------------------------------------------------

def test_cohere_uses_message_key(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    p = payloads[0]['payload']
    assert 'message' in p
    assert 'messages' not in p
    assert p['message'] == _CLEAN_PROMPT


def test_cohere_has_json_response_format(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    p = payloads[0]['payload']
    assert p.get('response_format', {}).get('type') == 'json_object'


def test_mistral_uses_messages_list(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'mistral',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    p = payloads[0]['payload']
    assert 'messages' in p
    assert isinstance(p['messages'], list)
    assert p['messages'][0]['role'] == 'user'
    assert p['messages'][0]['content'] == _CLEAN_PROMPT


def test_fireworks_uses_messages_list_with_json_format(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'fireworks',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    p = payloads[0]['payload']
    assert 'messages' in p
    assert p.get('response_format', {}).get('type') == 'json_object'


def test_cerebras_uses_messages_list_no_json_format(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cerebras',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    p = payloads[0]['payload']
    assert 'messages' in p
    assert 'response_format' not in p


def test_azure_openai_uses_messages_list_with_json_format(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'azure_openai',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    p = payloads[0]['payload']
    assert 'messages' in p
    assert p.get('response_format', {}).get('type') == 'json_object'


def test_temperature_propagated_to_all_payloads(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere,mistral',
        '--temperature', '0',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    for p in payloads:
        assert p['temperature'] == 0
        assert p['payload']['temperature'] == 0


def test_temperature_envelope_field_reflects_arg(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
        '--temperature', '0.2',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert payloads[0]['temperature'] == pytest.approx(0.2)
    assert payloads[0]['payload']['temperature'] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# --max-rows
# ---------------------------------------------------------------------------

def test_max_rows_limits_payloads(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST, _BASE_REQUEST_2])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere,mistral',
        '--max-rows', '1',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert len(payloads) == 2  # 1 row × 2 providers


# ---------------------------------------------------------------------------
# --model-override
# ---------------------------------------------------------------------------

def test_model_override_changes_model_in_payload(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
        '--model-override', 'cohere=command-r-plus-04-2024',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert payloads[0]['model'] == 'command-r-plus-04-2024'
    assert payloads[0]['payload']['model'] == 'command-r-plus-04-2024'


def test_default_models_used_without_override(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'mistral',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert payloads[0]['model'] == 'mistral-small-latest'


# ---------------------------------------------------------------------------
# Prompt SHA-256
# ---------------------------------------------------------------------------

def test_prompt_sha256_matches_expected(tmp_path):
    import hashlib
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    expected = hashlib.sha256(_CLEAN_PROMPT.encode('utf-8')).hexdigest()
    assert payloads[0]['prompt_sha256'] == expected


def test_different_prompts_have_different_sha256(tmp_path):
    req2 = {**_BASE_REQUEST_2, 'prompt': _CLEAN_PROMPT + ' EXTRA'}
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST, req2])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    hashes = [p['prompt_sha256'] for p in payloads]
    assert hashes[0] != hashes[1]


# ---------------------------------------------------------------------------
# Safety / leakage
# ---------------------------------------------------------------------------

def test_leaky_prompt_row_is_skipped(tmp_path):
    bad_req = {**_BASE_REQUEST, 'prompt': _CLEAN_PROMPT + '\nrelation_ready_label_manual: ready'}
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [bad_req])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert len(payloads) == 0


def test_leaky_row_reported_in_build_report(tmp_path):
    bad_req = {**_BASE_REQUEST, 'prompt': _CLEAN_PROMPT + '\nlikely not_ready candidate here'}
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [bad_req])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    report = (output_dir / 'build_report.md').read_text()
    assert 'LEAKAGE' in report


def test_clean_rows_not_skipped(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST, _BASE_REQUEST_2])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert len(payloads) == 2


def test_missing_field_row_is_skipped(tmp_path):
    bad_req = {**_BASE_REQUEST, 'prompt': ''}
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [bad_req, _BASE_REQUEST_2])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    payloads = read_jsonl(output_dir / 'provider_payloads.jsonl')
    assert len(payloads) == 1
    assert payloads[0]['row_id'] == 'rrseed_test_002'


def test_private_fields_absent_from_payload_content(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', ','.join(ALL_PROVIDERS),
    ])

    payloads_text = (output_dir / 'provider_payloads.jsonl').read_text()
    for term in (
        'relation_ready_label_manual',
        'first_error_axis_manual',
        'notes_manual',
        'human_relation_ready_label',
        'human_first_error_axis',
        'gold_answer_metadata_only',
    ):
        assert term not in payloads_text, f'Private field leaked into payloads: {term!r}'


# ---------------------------------------------------------------------------
# Build report content
# ---------------------------------------------------------------------------

def test_build_report_confirms_no_api_calls(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ])

    report = (output_dir / 'build_report.md').read_text()
    assert 'No API calls' in report
    assert 'No provider SDK' in report


def test_build_report_lists_all_providers(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere,cerebras',
    ])

    report = (output_dir / 'build_report.md').read_text()
    assert 'cohere' in report
    assert 'cerebras' in report


def test_build_report_shows_payload_count(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST, _BASE_REQUEST_2])
    output_dir = tmp_path / 'output'

    run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'cohere,mistral',
    ])

    report = (output_dir / 'build_report.md').read_text()
    assert '4' in report  # 2 rows × 2 providers = 4 payloads


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_missing_requests_file_exits_nonzero(tmp_path):
    output_dir = tmp_path / 'output'
    result = run_script([
        '--requests-jsonl', str(tmp_path / 'nonexistent.jsonl'),
        '--output-dir', str(output_dir),
        '--providers', 'cohere',
    ], expect_success=False)
    assert result.returncode != 0


def test_unsupported_provider_exits_nonzero(tmp_path):
    requests_path = tmp_path / 'requests.jsonl'
    write_jsonl(requests_path, [_BASE_REQUEST])
    output_dir = tmp_path / 'output'

    result = run_script([
        '--requests-jsonl', str(requests_path),
        '--output-dir', str(output_dir),
        '--providers', 'badprovider',
    ], expect_success=False)
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# SDK / provider import safety
# ---------------------------------------------------------------------------

def test_no_provider_sdk_imports_in_script():
    script_text = Path(SCRIPT).read_text()
    forbidden = [
        'import anthropic',
        'from anthropic',
        'import openai',
        'from openai',
        'import cohere',
        'from cohere',
        'import boto3',
        'import requests',
        'import httpx',
        'urllib.request.urlopen',
        '.post(',
    ]
    for term in forbidden:
        assert term not in script_text, f'Script must not contain: {term!r}'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
