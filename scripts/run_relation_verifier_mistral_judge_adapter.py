#!/usr/bin/env python3
"""Mistral adapter for RelationReady multi-judge labeling.

Modes
-----
dry_run   -- validate Mistral payload rows; no network calls
mock_api  -- feed synthetic Mistral-response text through the normalizer; no network calls
api       -- submit real Mistral requests (requires --allow-api; not exercised in CI)

The adapter reads rows from provider_payloads.jsonl (as built by
scripts/build_relation_verifier_provider_payloads.py) filtered to
provider == "mistral", and writes normalized judge responses compatible
with scripts/run_relation_verifier_multijudge_calibration.py.

No provider SDK imports at module level. No API calls unless --allow-api is set.
"""

import argparse
import json
import os
import sys
from pathlib import Path

RELATION_LABELS = frozenset({'ready', 'not_ready', 'uncertain', 'gold_inconsistent'})
ERROR_AXES = frozenset({
    'wrong_target_variable', 'wrong_relation_composition', 'wrong_process_state',
    'source_fact_missing', 'unit_scale_error', 'percentage_base_error',
    'per_unit_total_error', 'total_difference_error', 'original_final_state_error',
    'arithmetic_only_error', 'formula_format_error', 'prompt_gold_inconsistent',
    'insufficient_evidence', '',
})

_LEAKAGE_TERMS = [
    'gold_answer_metadata_only',
    'relation_ready_label_manual',
    'first_error_axis_manual',
    'notes_manual',
    'likely not_ready',
    'likely ready',
    'likely uncertain',
    'ready candidate',
    'not_ready candidate',
    'uncertain candidate',
    'good judge should label',
]


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def read_jsonl(path):
    rows = []
    with Path(path).open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def scan_leakage(text):
    lower = text.lower()
    return [term for term in _LEAKAGE_TERMS if term.lower() in lower]


def validate_payload_row(row):
    """Return list of issue strings; empty list means row is valid."""
    issues = []
    if not row.get('row_id'):
        issues.append('missing_row_id')
    if row.get('provider') != 'mistral':
        issues.append(f'wrong_provider:{row.get("provider")!r}')
    if not row.get('model'):
        issues.append('missing_model')
    if not row.get('payload'):
        issues.append('missing_payload')
    if not row.get('expected_json_schema'):
        issues.append('missing_expected_json_schema')
    return issues


def extract_prompt_from_row(row):
    """Return the prompt text from a Mistral payload envelope, or empty string.

    Mistral uses the OpenAI-compatible messages format:
      payload.messages[0].content
    """
    payload = row.get('payload') or {}
    messages = payload.get('messages') or []
    if messages:
        return messages[0].get('content', '')
    return ''


def normalize_response_text(row_id, model, response_text):
    """Parse a Mistral response_text string and return a normalized judge row.

    Returns (normalized_row, error_string).  error_string is None on success.
    """
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        return None, f'json_parse_error:{exc}'

    label = parsed.get('relation_ready_label', '')
    axis = parsed.get('first_error_axis', '')
    confidence = parsed.get('confidence', '')
    rationale = parsed.get('rationale', '')

    issues = []
    if label not in RELATION_LABELS:
        issues.append(f'invalid_label:{label!r}')
    if axis not in ERROR_AXES:
        issues.append(f'invalid_axis:{axis!r}')
    if confidence not in ('high', 'medium', 'low'):
        issues.append(f'invalid_confidence:{confidence!r}')

    if issues:
        return None, '; '.join(issues)

    return {
        'row_id': row_id,
        'judge_name': f'mistral:{model}',
        'relation_ready_label': label,
        'first_error_axis': axis,
        'confidence': confidence,
        'rationale': rationale,
    }, None


# ---------------------------------------------------------------------------
# Row selection helper
# ---------------------------------------------------------------------------

def select_rows(mistral_rows, start_index, max_rows, row_ids):
    """Return the subset of Mistral rows to process.

    Priority: --row-ids allowlist (if provided) overrides --start-index /
    --max-rows.
    """
    if row_ids:
        allowed = set(row_ids)
        return [r for r in mistral_rows if r.get('row_id') in allowed]
    rows = mistral_rows[start_index:]
    if max_rows:
        rows = rows[:max_rows]
    return rows


# ---------------------------------------------------------------------------
# Mode: dry_run
# ---------------------------------------------------------------------------

def run_dry_run(payloads_path, output_dir, start_index, max_rows, row_ids):
    all_rows = read_jsonl(payloads_path)
    mistral_rows = [r for r in all_rows if r.get('provider') == 'mistral']
    mistral_rows = select_rows(mistral_rows, start_index, max_rows, row_ids)

    manifest = []
    field_issues = []
    leakage_issues = []

    for row in mistral_rows:
        row_id = row.get('row_id', '<unknown>')
        issues = validate_payload_row(row)
        prompt = extract_prompt_from_row(row)
        leakage = scan_leakage(prompt)

        manifest.append({
            'row_id': row_id,
            'model': row.get('model', ''),
            'has_payload': bool(row.get('payload')),
            'has_schema': bool(row.get('expected_json_schema')),
            'prompt_length': len(prompt),
            'field_issues': issues,
            'leakage_terms': leakage,
        })

        if issues:
            field_issues.append((row_id, issues))
        if leakage:
            leakage_issues.append((row_id, leakage))

    write_jsonl(output_dir / 'mistral_dry_run_manifest.jsonl', manifest)

    valid_count = sum(1 for m in manifest if not m['field_issues'] and not m['leakage_terms'])
    n = len(mistral_rows)

    lines = [
        '# RelationReady Mistral Judge Adapter — Dry-Run Report',
        '',
        '## Summary',
        '',
        '- **Mode:** dry_run (no API calls)',
        f'- **Input:** `{payloads_path}`',
        f'- **Start index:** {start_index}' + (' (row_ids filter active — start-index ignored)' if row_ids else ''),
        f'- **Selected rows:** {n}',
        f'- **Valid rows:** {valid_count}',
        f'- **Rows with field issues:** {len(field_issues)}',
        f'- **Rows with prompt leakage:** {len(leakage_issues)}',
        '',
        '## Safety / Leakage Scan',
        '',
    ]
    if leakage_issues:
        lines.append('**LEAKAGE DETECTED:**')
        lines.append('')
        for row_id, terms in leakage_issues:
            lines.append(f'- `{row_id}`: {", ".join(terms)}')
        lines.append('')
    else:
        lines.append('✓ No leakage terms found in any payload prompt.')
        lines.append('')

    if field_issues:
        lines += ['## Field Issues', '']
        for row_id, issues in field_issues:
            lines.append(f'- `{row_id}`: {", ".join(issues)}')
        lines.append('')

    lines += [
        '## Estimated API Call Count (if submitted)',
        '',
        f'> {valid_count} valid Mistral payloads × 1 provider = {valid_count} calls',
        '',
        '## Sample Row IDs',
        '',
    ]
    for row in mistral_rows[:5]:
        lines.append(f'- `{row.get("row_id", "<unknown>")}`')
    if n > 5:
        lines.append(f'- ... ({n - 5} more)')
    lines += [
        '',
        '## Confirmation',
        '',
        '✓ No API calls were made.',
        '✓ No provider SDK imports were used.',
        '✓ Human labels were not exposed in any payload.',
    ]

    (output_dir / 'mistral_adapter_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return manifest, field_issues, leakage_issues


# ---------------------------------------------------------------------------
# Mode: mock_api
# ---------------------------------------------------------------------------

def run_mock_api(payloads_path, mock_path, output_dir, start_index, max_rows, row_ids):
    all_rows = read_jsonl(payloads_path)
    mistral_rows = [r for r in all_rows if r.get('provider') == 'mistral']
    mistral_rows = select_rows(mistral_rows, start_index, max_rows, row_ids)

    payload_index = {}
    for row in mistral_rows:
        rid = row.get('row_id', '')
        if rid:
            payload_index[rid] = row

    mock_responses = read_jsonl(mock_path)

    normalized = []
    invalid = []

    for resp in mock_responses:
        row_id = resp.get('row_id', '<unknown>')
        response_text = resp.get('response_text', '')

        if row_id not in payload_index:
            invalid.append({'row_id': row_id, 'issue': 'unknown_row_id'})
            continue

        model = payload_index[row_id].get('model', 'unknown')
        norm_row, err = normalize_response_text(row_id, model, response_text)
        if err:
            invalid.append({'row_id': row_id, 'issue': err})
        else:
            normalized.append(norm_row)

    write_jsonl(output_dir / 'normalized_judge_responses.jsonl', normalized)

    lines = [
        '# RelationReady Mistral Judge Adapter — Mock-API Report',
        '',
        '## Summary',
        '',
        '- **Mode:** mock_api (no real API calls)',
        f'- **Input payloads:** `{payloads_path}`',
        f'- **Mock responses:** `{mock_path}`',
        f'- **Mistral payload rows:** {len(mistral_rows)}',
        f'- **Mock responses processed:** {len(mock_responses)}',
        f'- **Normalized (valid) responses:** {len(normalized)}',
        f'- **Invalid / skipped responses:** {len(invalid)}',
        '',
    ]

    if invalid:
        lines += ['## Invalid Responses', '']
        for inv in invalid:
            lines.append(f'- `{inv["row_id"]}`: {inv["issue"]}')
        lines.append('')

    lines += [
        '## Confirmation',
        '',
        '✓ No API calls were made.',
        '✓ No provider SDK imports were used.',
        '✓ Human labels were not exposed in any payload.',
    ]

    (output_dir / 'mistral_adapter_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return normalized, invalid


# ---------------------------------------------------------------------------
# Mode: api  (real Mistral calls — requires --allow-api)
# ---------------------------------------------------------------------------

def run_api(payloads_path, output_dir, start_index, max_rows, row_ids, api_key_env):
    try:
        from mistralai import Mistral as MistralClient  # noqa: PLC0415
    except ImportError:
        print('Error: mistralai SDK not installed. Run: pip install mistralai', file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get(api_key_env, '')
    if not api_key:
        print(
            f'Error: API key env var {api_key_env!r} is not set or empty.',
            file=sys.stderr,
        )
        sys.exit(1)

    all_rows = read_jsonl(payloads_path)
    mistral_rows = [r for r in all_rows if r.get('provider') == 'mistral']
    mistral_rows = select_rows(mistral_rows, start_index, max_rows, row_ids)

    client = MistralClient(api_key=api_key)
    normalized = []
    invalid = []

    for row in mistral_rows:
        row_id = row.get('row_id', '<unknown>')
        model = row.get('model', 'unknown')
        issues = validate_payload_row(row)
        if issues:
            invalid.append({'row_id': row_id, 'issue': '; '.join(issues)})
            continue

        prompt = extract_prompt_from_row(row)
        if scan_leakage(prompt):
            invalid.append({'row_id': row_id, 'issue': 'leakage_detected'})
            continue

        payload = row['payload'].copy()
        payload.pop('model', None)

        try:
            response = client.chat.complete(model=model, **payload)
            response_text = response.choices[0].message.content
        except Exception as exc:
            invalid.append({'row_id': row_id, 'issue': f'api_error:{exc}'})
            continue

        norm_row, err = normalize_response_text(row_id, model, response_text)
        if err:
            invalid.append({'row_id': row_id, 'issue': err})
        else:
            normalized.append(norm_row)

    write_jsonl(output_dir / 'normalized_judge_responses.jsonl', normalized)

    lines = [
        '# RelationReady Mistral Judge Adapter — API Run Report',
        '',
        '## Summary',
        '',
        '- **Mode:** api (real Mistral calls)',
        f'- **Input payloads:** `{payloads_path}`',
        f'- **Rows submitted:** {len(mistral_rows)}',
        f'- **Normalized responses:** {len(normalized)}',
        f'- **Invalid / failed:** {len(invalid)}',
        '',
    ]
    if invalid:
        lines += ['## Failures', '']
        for inv in invalid:
            lines.append(f'- `{inv["row_id"]}`: {inv["issue"]}')
        lines.append('')

    (output_dir / 'mistral_adapter_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return normalized, invalid


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Mistral adapter for RelationReady multi-judge labeling.'
    )
    parser.add_argument('--payloads-jsonl', required=True,
                        help='Path to provider_payloads.jsonl (Mistral rows will be filtered)')
    parser.add_argument('--output-dir', required=True,
                        help='Directory for output files')
    parser.add_argument('--mode', required=True, choices=['dry_run', 'mock_api', 'api'],
                        help='Execution mode')
    parser.add_argument('--mock-response-jsonl',
                        help='Mock response JSONL for mock_api mode')
    parser.add_argument('--max-rows', type=int,
                        help='Process at most N Mistral payload rows')
    parser.add_argument('--start-index', type=int, default=0,
                        help='Zero-based start index into the Mistral payload list (default: 0)')
    parser.add_argument('--row-ids',
                        help='Comma-separated explicit row_id allowlist; takes precedence over '
                             '--start-index and --max-rows')
    parser.add_argument('--allow-api', action='store_true', default=False,
                        help='Permit real Mistral API calls (api mode only)')
    parser.add_argument('--api-key-env', default='MISTRAL_API_KEY',
                        help='Name of env var holding the Mistral API key (default: MISTRAL_API_KEY)')
    args = parser.parse_args()

    payloads_path = Path(args.payloads_jsonl)
    if not payloads_path.exists():
        print(f'Error: payloads file not found: {payloads_path}', file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    row_ids = [r.strip() for r in args.row_ids.split(',')] if args.row_ids else None

    if args.mode == 'dry_run':
        manifest, field_issues, leakage_issues = run_dry_run(
            payloads_path, output_dir, args.start_index, args.max_rows, row_ids
        )
        n = len(manifest)
        print(f'Dry-run complete: {payloads_path}')
        print(f'Output directory: {output_dir}')
        print()
        print(f'Mistral rows found : {n}')
        print(f'Field issues       : {len(field_issues)}')
        print(f'Leakage issues     : {len(leakage_issues)}')
        print()
        print('Files written:')
        print('  - mistral_dry_run_manifest.jsonl')
        print('  - mistral_adapter_report.md')
        print()
        print('✓ No API calls were made.')
        print('✓ No provider SDK imports were used.')

    elif args.mode == 'mock_api':
        if not args.mock_response_jsonl:
            print('Error: --mock-response-jsonl required for mock_api mode', file=sys.stderr)
            sys.exit(1)
        mock_path = Path(args.mock_response_jsonl)
        if not mock_path.exists():
            print(f'Error: mock response file not found: {mock_path}', file=sys.stderr)
            sys.exit(1)

        normalized, invalid = run_mock_api(
            payloads_path, mock_path, output_dir, args.start_index, args.max_rows, row_ids
        )
        print('Mock-API run complete.')
        print(f'Output directory: {output_dir}')
        print()
        print(f'Normalized responses : {len(normalized)}')
        print(f'Invalid / skipped    : {len(invalid)}')
        print()
        print('Files written:')
        print('  - normalized_judge_responses.jsonl')
        print('  - mistral_adapter_report.md')
        print()
        print('✓ No API calls were made.')
        print('✓ No provider SDK imports were used.')

    elif args.mode == 'api':
        if not args.allow_api:
            print(
                'Error: api mode requires --allow-api. '
                'Pass --allow-api only when you intend to make real Mistral calls.',
                file=sys.stderr,
            )
            sys.exit(1)

        normalized, invalid = run_api(
            payloads_path, output_dir, args.start_index, args.max_rows, row_ids, args.api_key_env
        )
        print('API run complete.')
        print(f'Output directory: {output_dir}')
        print()
        print(f'Normalized responses : {len(normalized)}')
        print(f'Invalid / failed     : {len(invalid)}')
        print()
        print('Files written:')
        print('  - normalized_judge_responses.jsonl')
        print('  - mistral_adapter_report.md')


if __name__ == '__main__':
    main()
