#!/usr/bin/env python3
"""Dry-run provider payload builder for RelationReady multi-judge calls.

Reads a judge_requests.jsonl (from build_relation_verifier_multijudge_label_requests.py),
and for each (request, provider) pair builds a serialised chat payload in the
provider's native wire format — without making any network calls.

No provider SDK imports. No API keys. No gold answers in payloads.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

SUPPORTED_PROVIDERS = ('cohere', 'mistral', 'fireworks', 'cerebras', 'azure_openai')

DEFAULT_MODELS = {
    'cohere': 'command-r-plus-08-2024',
    'mistral': 'mistral-small-latest',
    'fireworks': 'accounts/fireworks/models/llama-v3p1-8b-instruct',
    'cerebras': 'llama3.1-8b',
    'azure_openai': 'gpt-4o-mini',
}

# Fields that must never appear in any provider payload.
_PRIVATE_FIELDS = frozenset({
    'gold_answer_metadata_only',
    'relation_ready_label_manual',
    'first_error_axis_manual',
    'notes_manual',
    'human_relation_ready_label',
    'human_first_error_axis',
    'human_notes',
    'likely not_ready',
    'likely ready',
    'likely uncertain',
    'ready candidate',
    'not_ready candidate',
    'uncertain candidate',
    'good judge should label',
})


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


def sha256_hex(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def scan_leakage(text):
    lower = text.lower()
    return [term for term in _PRIVATE_FIELDS if term.lower() in lower]


def build_cohere_payload(prompt, model, temperature):
    """Cohere Chat API format (uses `message`, not `messages`)."""
    return {
        'model': model,
        'message': prompt,
        'temperature': temperature,
        'response_format': {'type': 'json_object'},
    }


def build_openai_compat_payload(prompt, model, temperature, *, include_json_format=True):
    """OpenAI-compatible chat format used by Mistral, Fireworks, Cerebras, Azure OpenAI."""
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': temperature,
    }
    if include_json_format:
        payload['response_format'] = {'type': 'json_object'}
    return payload


_BUILDERS = {
    'cohere': lambda prompt, model, temp: build_cohere_payload(prompt, model, temp),
    'mistral': lambda prompt, model, temp: build_openai_compat_payload(prompt, model, temp),
    'fireworks': lambda prompt, model, temp: build_openai_compat_payload(prompt, model, temp),
    'cerebras': lambda prompt, model, temp: build_openai_compat_payload(
        prompt, model, temp, include_json_format=False
    ),
    'azure_openai': lambda prompt, model, temp: build_openai_compat_payload(prompt, model, temp),
}


def build_payload_envelope(req, provider, model, temperature):
    """Return a single provider_payloads.jsonl row for one (request, provider) pair."""
    prompt = req['prompt']
    return {
        'row_id': req['row_id'],
        'provider': provider,
        'model': model,
        'temperature': temperature,
        'dry_run': True,
        'api_call_made': False,
        'prompt_sha256': sha256_hex(prompt),
        'payload': _BUILDERS[provider](prompt, model, temperature),
        'expected_json_schema': req.get('expected_json_schema', {}),
    }


def validate_request(req):
    issues = []
    for field in ('row_id', 'prompt', 'expected_json_schema'):
        if not req.get(field):
            issues.append(f'missing_{field}')
    return issues


def build_payloads(requests_path, output_dir, providers, temperature, max_rows, model_overrides):
    requests = read_jsonl(requests_path)
    if max_rows:
        requests = requests[:max_rows]

    models = {**DEFAULT_MODELS, **model_overrides}

    payloads = []
    field_issues = []
    leakage_issues = []
    skipped = []

    for req in requests:
        row_id = req.get('row_id', '<unknown>')
        issues = validate_request(req)
        if issues:
            field_issues.append((row_id, issues))
            skipped.append(row_id)
            continue

        prompt = req['prompt']
        leaked = scan_leakage(prompt)
        if leaked:
            leakage_issues.append((row_id, leaked))
            skipped.append(row_id)
            continue

        for provider in providers:
            model = models[provider]
            envelope = build_payload_envelope(req, provider, model, temperature)
            payloads.append(envelope)

    write_jsonl(output_dir / 'provider_payloads.jsonl', payloads)

    n_requests = len(requests)
    n_valid = n_requests - len(skipped)
    n_payloads = len(payloads)

    lines = [
        '# RelationReady Multi-Judge — Provider Payload Build Report',
        '',
        '## Summary',
        '',
        f'- **Input:** `{requests_path}`',
        f'- **Total input rows:** {n_requests}',
        f'- **Valid rows (no field issues, no leakage):** {n_valid}',
        f'- **Skipped rows:** {len(skipped)}',
        f'- **Providers:** {", ".join(providers)}',
        f'- **Temperature:** {temperature}',
        f'- **Total payloads emitted:** {n_payloads}  ({n_valid} rows × {len(providers)} providers)',
        '',
        '## Models Used',
        '',
    ]
    for p in providers:
        lines.append(f'- **{p}**: `{models[p]}`')
    lines.append('')

    lines += [
        '## Safety Checks',
        '',
    ]
    if leakage_issues:
        lines.append('**LEAKAGE DETECTED — rows skipped:**')
        lines.append('')
        for row_id, terms in leakage_issues:
            lines.append(f'- `{row_id}`: {", ".join(terms)}')
        lines.append('')
    else:
        lines.append('✓ No leakage terms found in any prompt.')
        lines.append('')

    if field_issues:
        lines += ['## Field Issues', '']
        for row_id, issues in field_issues:
            lines.append(f'- `{row_id}`: {", ".join(issues)}')
        lines.append('')

    lines += [
        '## Payload Format Notes',
        '',
        '| Provider | Format | JSON mode |',
        '|---|---|---|',
        '| cohere | `message` (Cohere Chat) | `response_format: {type: json_object}` |',
        '| mistral | `messages` (OpenAI-compat) | `response_format: {type: json_object}` |',
        '| fireworks | `messages` (OpenAI-compat) | `response_format: {type: json_object}` |',
        '| cerebras | `messages` (OpenAI-compat) | none |',
        '| azure_openai | `messages` (OpenAI-compat) | `response_format: {type: json_object}` |',
        '',
        '## Confirmation',
        '',
        '✓ No API calls were made.',
        '✓ No provider SDK imports were used.',
        '✓ Gold answers and human labels were not included in any payload.',
    ]

    (output_dir / 'build_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return payloads, field_issues, leakage_issues, skipped


def main():
    parser = argparse.ArgumentParser(
        description='Dry-run provider payload builder for RelationReady multi-judge calls.'
    )
    parser.add_argument('--requests-jsonl', required=True,
                        help='Path to judge_requests.jsonl')
    parser.add_argument('--output-dir', required=True,
                        help='Directory to write provider_payloads.jsonl and build_report.md')
    parser.add_argument('--providers', default=','.join(SUPPORTED_PROVIDERS),
                        help=f'Comma-separated provider list. Supported: {", ".join(SUPPORTED_PROVIDERS)}')
    parser.add_argument('--temperature', type=float, default=0,
                        help='Sampling temperature (default: 0)')
    parser.add_argument('--max-rows', type=int,
                        help='Process at most N input rows')
    parser.add_argument('--model-override', action='append', default=[],
                        metavar='PROVIDER=MODEL',
                        help='Override default model for a provider, e.g. cohere=command-r-plus-04-2024')
    args = parser.parse_args()

    requests_path = Path(args.requests_jsonl)
    if not requests_path.exists():
        print(f'Error: requests file not found: {requests_path}', file=sys.stderr)
        sys.exit(1)

    providers = [p.strip() for p in args.providers.split(',') if p.strip()]
    bad = [p for p in providers if p not in SUPPORTED_PROVIDERS]
    if bad:
        print(f'Error: unsupported providers: {bad}. Supported: {list(SUPPORTED_PROVIDERS)}',
              file=sys.stderr)
        sys.exit(1)

    model_overrides = {}
    for spec in args.model_override:
        if '=' not in spec:
            print(f'Error: --model-override must be PROVIDER=MODEL, got: {spec!r}', file=sys.stderr)
            sys.exit(1)
        provider, model = spec.split('=', 1)
        if provider not in SUPPORTED_PROVIDERS:
            print(f'Error: unknown provider in --model-override: {provider!r}', file=sys.stderr)
            sys.exit(1)
        model_overrides[provider] = model

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payloads, field_issues, leakage_issues, skipped = build_payloads(
        requests_path, output_dir, providers, args.temperature, args.max_rows, model_overrides
    )

    n_input = len(read_jsonl(requests_path))
    if args.max_rows:
        n_input = min(n_input, args.max_rows)

    print(f'Build complete: {requests_path}')
    print(f'Output directory: {output_dir}')
    print()
    print(f'Input rows       : {n_input}')
    print(f'Skipped rows     : {len(skipped)}')
    print(f'Providers        : {len(providers)}')
    print(f'Payloads emitted : {len(payloads)}')
    print()
    print('Files written:')
    print('  - provider_payloads.jsonl')
    print('  - build_report.md')
    print()
    if leakage_issues:
        print(f'WARNING: {len(leakage_issues)} row(s) skipped due to leakage. See build_report.md.')
    print('✓ No API calls were made.')
    print('✓ No provider SDK imports were used.')
    print('✓ Gold answers and human labels were not included in any payload.')


if __name__ == '__main__':
    main()
